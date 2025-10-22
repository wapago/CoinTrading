import time
import asyncio

from fastapi import APIRouter, WebSocket
from collections import OrderedDict
from urllib.parse import urlencode

import hmac, hashlib, string
import requests
import websockets
from starlette.websockets import WebSocketState

from domain.v1.bitget.router import keep_alive
from config.models.binance import BinanceSpotTrade, BinanceFutureTrade, BinanceWithdrawal, BinanceSymbol
from config.config import (BINANCE_BASE_URL, BINANCE_BASE_F_URL, BINANCE_WS_STREAM_BASE_URL,
                           BINANCE_WS_F_STREAM_BASE_URL, BINANCE_WS_COMBINED_STREAM_BASE_URL,
                           BINANCE_API_KEY, BINANCE_API_SECRET)


router = APIRouter(
    prefix='/api/v1/binance',
    tags=['Binance'],
    include_in_schema=True,
)

HEADERS = {"X-MBX-APIKEY": BINANCE_API_KEY}


def get_usdt_spot_symbols():
    spot_info = requests.get(BINANCE_BASE_URL + '/api/v3/exchangeInfo').json()
    symbols = spot_info['symbols']
    spot_usdt_available = []

    for symbol in symbols:
        if symbol['quoteAsset'] == 'USDT' and symbol['status'] == 'TRADING' and symbol["symbol"].isascii():
            spot_usdt_available.append(symbol['symbol'].lower() + "@ticker")

    return spot_usdt_available


def get_usdt_future_symbols():
    """
    @ticker: 현재가
    @kline_1m: 1분봉 캔들(OHLC)
    {
      "e": "24hrTicker",
      "E": 1729485220000,
      "s": "BTCUSDT",
      "p": "-54.20000000",
      "P": "-0.16",
      "w": "33350.38", ---> 24시간 동안의 평균 가격
      "x": "33400.00",
      "c": "33345.80", ---> 현재가(마지막 체결가)
      "Q": "0.008",
      "b": "33345.70",
      "B": "0.018",
      "a": "33345.80",
      "A": "0.086",
      "o": "33399.80",
      "h": "33550.00",
      "l": "33260.00",
      "v": "8254.12", ---> 거래량
      "q": "275411018.93",
      "O": 1729398820000,
      "C": 1729485219999,
      "F": 123456789,
      "L": 123456999,
      "n": 211
    }
    :return:
    """
    future_info = requests.get(BINANCE_BASE_F_URL + '/fapi/v1/exchangeInfo').json()
    symbols = future_info['symbols']
    future_usdt_available = []

    for symbol in symbols:
        if symbol['quoteAsset'] == 'USDT' and symbol['status'] == 'TRADING' and symbol["symbol"].isascii():
            future_usdt_available.append(symbol['symbol'].lower() + "@ticker")

    return future_usdt_available


# 유저 자산조회
@router.post('/user/asset')
async def user_asset():
    servertime = str(requests.get(url=BINANCE_BASE_URL + '/api/v3/time').json()['serverTime'])
    query_string = f"timestamp={servertime}&recvWindow=60000"
    signature = hmac.new(BINANCE_API_SECRET.encode(), query_string.encode(), hashlib.sha256).hexdigest()
    url = f"https://api.binance.com/sapi/v3/asset/getUserAsset?{query_string}&signature={signature}"
    response = requests.post(url, headers=HEADERS)

    return response.json()


# FUTURE 현재가 ticker
@router.websocket('/ws/future/currency')
async def get_currency(websocket: WebSocket):
    await websocket.accept()

    future_symbols = get_usdt_future_symbols()
    symbols = future_symbols[0]
    for symbol in future_symbols[1:]:
        symbols += ('/' + symbol)
    stream_url = BINANCE_WS_COMBINED_STREAM_BASE_URL + symbols

    ping_task = None

    try:
        async with websockets.connect(stream_url, ping_interval=None) as binance_ws:
            ping_task = asyncio.create_task(keep_alive(binance_ws))
            while True:
                msg = await binance_ws.recv()
                print(msg)
                if websocket.client_state == WebSocketState.DISCONNECTED:
                    print("클라이언트와 연결 끊김")
                    break
                elif websocket.client_state == WebSocketState.CONNECTED:
                    await websocket.send_text(msg)
    except websockets.ConnectionClosedOK:
        print("websocket 정상종료")
    except websockets.ConnectionClosedError as e:
        print(f"websocket 비정상종료: {e}")
    except RuntimeError as e:
        print(f"클라이언트가 연결을 끊은 후 send 시도: {e}")
    finally:
        print("연결상태: ", websocket.client_state)
        if websocket.client_state != WebSocketState.DISCONNECTED:
            ping_task.cancel()
            await websocket.close()
        print("클라이언트 연결 닫힘")


# SPOT 현재가 ticker
# TODO: 유저가 가진 자산만 골라서 보내기
@router.websocket('/ws/currency')
async def get_currency(websocket: WebSocket):
    spot_symbols = get_usdt_spot_symbols()
    symbols = ""
    for symbol in spot_symbols:
        symbols += ('/' + symbol)

    print(BINANCE_WS_STREAM_BASE_URL + symbols)

    # 클라이언트 연결 수락
    await websocket.accept()
    # 바이낸스 웹소켓 서버 연결
    async with websockets.connect(BINANCE_WS_STREAM_BASE_URL + symbols) as binance_ws:
        asyncio.create_task(keep_alive(binance_ws))

        while True:
            msg = await binance_ws.recv() # 주기적 요청 X. 바이낸스서버가 push하면 즉시 수신
            print(msg)
            await websocket.send_text(msg)


# SPOT 트레이드
@router.post('/spot/trade')
async def spot_trade(trade_model: BinanceSpotTrade):
    servertime = str(requests.get(url=BINANCE_BASE_URL + '/api/v3/time').json()['serverTime'])

    params = OrderedDict([
        ("symbol", trade_model.symbol),
        ("side", trade_model.side),
        ("type", trade_model.type),
        ("timestamp", servertime),
        ("recvWindow", 60000),
    ])
    if trade_model.type.upper()== "LIMIT":
        params["timeInForce"] = trade_model.time_in_force
        params["quantity"] = trade_model.quantity
        params["price"] = trade_model.price
    elif trade_model.type.upper()== "MARKET":
        params["quoteOrderQty"] = trade_model.quote_order_qty

    query_string = urlencode(params, doseq=True)
    signature = hmac.new(
        BINANCE_API_SECRET.encode(),
        query_string.encode(),
        hashlib.sha256
    ).hexdigest()

    url = f"{BINANCE_BASE_URL}/api/v3/order?{query_string}&signature={signature}"
    response = requests.post(url, headers=HEADERS)
    return response.json()


# FUTURE 트레이드
@router.post('/future/trade')
async def future_trade(trade_model: BinanceFutureTrade):
    """
        1. 심볼별 레버리지 변경
        2. 심볼별 마진 모드 변경
        3. 실제 주문 실행
        GTC: 체결될 때까지 계속 유지 (기본값)
        IOC: 즉시 체결 가능한 만큼만 체결, 나머지는 취소
        FOK: 전량이 즉시 체결되지 않으면 전부 취소
        GTX: 즉시 체결될 상황이면 자동 취소
        :param trade_model:
        :return:
    """
    # 바이낸스 서버시간 동기화
    servertime = str(requests.get(url=BINANCE_BASE_F_URL + '/fapi/v1/time').json()['serverTime'])

    # 레버리지 설정
    lev_params = OrderedDict([
        ("symbol", trade_model.symbol.upper()),
        ("leverage", trade_model.leverage),
        ("timestamp", servertime),
        ("recvWindow", 60000),
    ])
    lev_query = urlencode(lev_params)
    lev_signature = hmac.new(
        BINANCE_API_SECRET.encode(),
        lev_query.encode(),
        hashlib.sha256
    ).hexdigest()

    lev_url = f"{BINANCE_BASE_F_URL}/fapi/v1/leverage?{lev_query}&signature={lev_signature}"
    lev_res = requests.post(lev_url, headers=HEADERS)

    # 마진 모드 설정(Cross or Isolated)
    margin_params = OrderedDict([
        ("symbol", trade_model.symbol.upper()),
        ("marginType", trade_model.margin_type.upper()),  # ISOLATED 또는 CROSSED
        ("timestamp", servertime),
        ("recvWindow", 60000),
    ])
    margin_query = urlencode(margin_params)
    margin_signature = hmac.new(
        BINANCE_API_SECRET.encode(),
        margin_query.encode(),
        hashlib.sha256
    ).hexdigest()

    margin_url = f"{BINANCE_BASE_F_URL}/fapi/v1/marginType?{margin_query}&signature={margin_signature}"
    margin_res = requests.post(margin_url, headers=HEADERS)

    # 주문설정
    order_params = OrderedDict([
        ("symbol", trade_model.symbol.upper()),
        ("side", trade_model.side.upper()),
        ("positionSide", trade_model.position_side.upper()),
        ("type", trade_model.type.upper()),
        ("timestamp", servertime),
        ("recvWindow", 60000),
    ])
    if trade_model.type.upper()== "LIMIT":
        order_params["timeInForce"] = trade_model.time_in_force
        order_params["quantity"] = trade_model.quantity
        order_params["price"] = trade_model.price
    elif trade_model.type.upper()== "MARKET":
        order_params["quantity"] = trade_model.quantity

    query_string = urlencode(order_params, doseq=True)
    signature = hmac.new(
        BINANCE_API_SECRET.encode(),
        query_string.encode(),
        hashlib.sha256
    ).hexdigest()

    order_url = f"{BINANCE_BASE_F_URL}/fapi/v1/order?{query_string}&signature={signature}"
    order_res = requests.post(order_url, headers=HEADERS)

    return {
        "leverage": lev_res.json(),
        "marginType": margin_res.json(),
        "order": order_res.json()
    }


# FUTURE 미청산 포지션 조회
@router.get('/future/unliquidated')
async def future_orders_unliquidated(symbol: str = None):
    servertime = str(requests.get(url=BINANCE_BASE_F_URL + '/fapi/v1/time').json()['serverTime'])

    params = OrderedDict([
        ("timestamp", servertime),
        ("recvWindow", 60000)
    ])
    if symbol:
        params['symbol'] = symbol

    query_string = urlencode(params, doseq=True)
    signature = hmac.new(
        BINANCE_API_SECRET.encode(),
        query_string.encode(),
        hashlib.sha256
    ).hexdigest()

    url = f"{BINANCE_BASE_F_URL}/fapi/v2/positionRisk?{query_string}&signature={signature}"

    response_json = requests.get(url, headers=HEADERS).json()
    unliquidated_symbol_list = []

    for resp in response_json:
        if float(resp['positionAmt']) != 0.0:
            unliquidated_symbol_list.append(resp)

    return unliquidated_symbol_list


# FUTURE 주문조회
@router.get('/future/all/orders')
async def future_orders(symbol: str = None):
    servertime = str(requests.get(url=BINANCE_BASE_F_URL + '/fapi/v1/time').json()['serverTime'])

    params = OrderedDict([
        ("timestamp", servertime),
        ("recvWindow", 60000)
    ])
    if symbol:
        params['symbol'] = symbol

    query_string = urlencode(params, doseq=True)
    signature = hmac.new(
        BINANCE_API_SECRET.encode(),
        query_string.encode(),
        hashlib.sha256
    ).hexdigest()

    url = f"{BINANCE_BASE_F_URL}/fapi/v1/allOrders?{query_string}&signature={signature}"

    response = requests.get(url, headers=HEADERS)
    return response.json()


# SPOT withdraw
# TODO: {"id": "ded217996129448682bc3544a4ed5728"} -> GET /sapi/v1/capital/withdraw/history
@router.post('/spot/wallet/withdrawal')
async def spot_withdrawal(withdraw_model: BinanceWithdrawal):
    servertime = str(requests.get(url=BINANCE_BASE_URL + '/api/v3/time').json()['serverTime'])

    params = OrderedDict([
        ("coin", withdraw_model.coin),
        ("network", withdraw_model.network),
        ("address", withdraw_model.address),
        ("amount", withdraw_model.amount),
        ("timestamp", servertime),
        ("recvWindow", 60000),
    ])

    query_string = urlencode(params, doseq=True)
    signature = hmac.new(
        BINANCE_API_SECRET.encode(),
        query_string.encode(),
        hashlib.sha256
    ).hexdigest()


    url = f"{BINANCE_BASE_URL}/sapi/v1/capital/withdraw/apply?{query_string}&signature={signature}"
    response = requests.post(url, headers=HEADERS)
    return response.json()


# @router.get("/exchange_info")
# async def exchange_info():
#     response = requests.get(url=BINANCE_BASE_URL + '/exchangeInfo', params={"symbolStatus":"TRADING"})
#     return response.json()