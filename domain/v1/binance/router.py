import time
import asyncio

from fastapi import APIRouter, WebSocket
from collections import OrderedDict
from urllib.parse import urlencode

import hmac, hashlib
import requests
import websockets

from domain.v1.bitget.router import keep_alive
from config.models.binance import BinanceTrade, BinanceWithdrawal
from config.config import BINANCE_BASE_URL, BINANCE_WS_STREAM_BASE_URL, BINANCE_API_KEY, BINANCE_API_SECRET


router = APIRouter(
    prefix='/api/v1/binance',
    tags=['Binance'],
    include_in_schema=True,
)

HEADERS = {"X-MBX-APIKEY": BINANCE_API_KEY}


@router.get("/exchange_info")
async def exchange_info():
    response = requests.get(url=BINANCE_BASE_URL + '/exchangeInfo', params={"symbolStatus":"TRADING"})
    return response.json()


# 유저 자산조회
@router.post('/user/asset')
async def user_asset():
    servertime = str(requests.get(url=BINANCE_BASE_URL + '/time').json()['serverTime'])
    query_string = f"timestamp={servertime}&recvWindow=60000"
    signature = hmac.new(BINANCE_API_SECRET.encode(), query_string.encode(), hashlib.sha256).hexdigest()
    url = f"https://api.binance.com/sapi/v3/asset/getUserAsset?{query_string}&signature={signature}"
    response = requests.post(url, headers=HEADERS)

    return response.json()


# 특정코인 현재가 조회 웹소켓
@router.websocket('/ws/currency')
async def get_currency(websocket: WebSocket):
    await websocket.accept()

    async with websockets.connect(BINANCE_WS_STREAM_BASE_URL + '/btcusdt@ticker') as binance_ws:
        asyncio.create_task(keep_alive(binance_ws))

        while True:
            msg = await binance_ws.recv()
            print(msg)
            await websocket.send_text(msg)

# SPOT 트레이드
@router.post('/spot/trade')
async def spot_trade(trade_model: BinanceTrade):
    servertime = str(requests.get(url=BINANCE_BASE_URL + '/time').json()['serverTime'])

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


# SPOT 출금
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