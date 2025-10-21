import time
import asyncio

from fastapi import APIRouter, WebSocket
from collections import OrderedDict
from urllib.parse import urlencode

import hmac, hashlib, string
import requests
import websockets

from domain.v1.bitget.router import keep_alive
from config.models.binance import BinanceSpotTrade, BinanceFutureTrade, BinanceWithdrawal
from config.config import (BINANCE_BASE_URL, BINANCE_BASE_F_URL, BINANCE_WS_STREAM_BASE_URL,
                           BINANCE_WS_F_STREAM_BASE_URL, BINANCE_API_KEY, BINANCE_API_SECRET)


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
        if symbol['quoteAsset'] == 'USDT' and symbol['status'] == 'TRADING':
            spot_usdt_available.append(symbol['symbol'].lower() + "@ticker")
    print(len(spot_usdt_available))
    return spot_usdt_available


def get_usdt_future_symbols():
    future_info = requests.get(BINANCE_BASE_F_URL + '/fapi/v1/exchangeInfo').json()
    symbols = future_info['symbols']
    future_usdt_available = []
    for symbol in symbols:
        if symbol['quoteAsset'] == 'USDT' and symbol['status'] == 'TRADING':
            future_usdt_available.append(symbol['symbol'] + "@ticker")

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
    future_symbols = get_usdt_future_symbols()
    symbols = ""
    for symbol in future_symbols:
        symbols += ('/' + symbol)

    await websocket.accept()

    async with websockets.connect(BINANCE_WS_F_STREAM_BASE_URL + symbols) as binance_ws:
        asyncio.create_task(keep_alive(binance_ws))

        while True:
            msg = await binance_ws.recv()
            print(msg)
            await websocket.send_text(msg)


# SPOT 현재가 ticker
# TODO: 유저가 가진 자산만 골라서 보내기
@router.websocket('/ws/currency')
async def get_currency(websocket: WebSocket):
    spot_symbols = get_usdt_spot_symbols()
    symbols = ""
    for symbol in spot_symbols:
        symbols += ('/' + symbol)

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
    print("레버리지 설정:", lev_res.json())

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
    print("마진모드 설정:", margin_res.json())

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
    elif trade_model.type.upper()== "STOP" or "TAKE_PROFIT":
        order_params["quantity"] = trade_model.quantity
        order_params["price"] = trade_model.price
        order_params["stopPrice"] = trade_model.stop_price
    elif trade_model.type.upper()== "STOP_MARKET" or "TAKE_PROFIT_MARKET":
        order_params["stopPrice"] = trade_model.stop_price
    elif trade_model.type.upper()== "TRAILING_STOP_MARKET":
        order_params["callbackRate"] = trade_model.callback_rate

    query_string = urlencode(order_params, doseq=True)
    print(query_string)
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