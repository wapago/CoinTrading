import asyncio

from fastapi import APIRouter, WebSocket

import hmac, hashlib
import requests
import pprint
import websockets

from domain.v1.bitget.router import keep_alive
from config.config import BINANCE_BASE_URL, BINANCE_WS_STREAM_BASE_URL, BINANCE_API_KEY, BINANCE_API_SECRET


router = APIRouter(
    prefix='/api/v1/binance',
    tags=['Binance'],
    include_in_schema=True,
)


servertime = requests.get(url=BINANCE_BASE_URL + '/time').json()['serverTime']
query_string = f"timestamp={servertime}&recvWindow=60000"
signature = hmac.new(BINANCE_API_SECRET.encode(), query_string.encode(), hashlib.sha256).hexdigest()
headers = {"X-MBX-APIKEY": BINANCE_API_KEY}


@router.post('/user/asset')
async def user_asset():
    url = f"https://api.binance.com/sapi/v3/asset/getUserAsset?{query_string}&signature={signature}"
    response = requests.post(url, headers=headers)
    return response.json()


@router.websocket('/ws/currency')
async def get_currency(websocket: WebSocket):
    await websocket.accept()

    async with websockets.connect(BINANCE_WS_STREAM_BASE_URL + '/btcusdt@ticker') as binance_ws:
        asyncio.create_task(keep_alive(binance_ws))

        while True:
            msg = await binance_ws.recv()
            print(msg)
            await websocket.send_text(msg)


@router.get("/exchange_info")
async def exchange_info():
    response = requests.get(url=BINANCE_BASE_URL + '/exchangeInfo', params={"symbolStatus":"TRADING"})
    return response.json()


@router.get("/avg_price")
async def avg_price():
    response = requests.get(url=BINANCE_BASE_URL + '/avgPrice', params={"symbol":"BTCUSDT"})
    return response.json()