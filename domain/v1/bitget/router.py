import asyncio

import websockets
from fastapi import APIRouter, WebSocket
from collections import OrderedDict

import aiohttp
import time
import requests
import hmac
import hashlib
import base64
import json

from urllib.parse import urlencode
from config.models.bitget import BitgetTrade
from config.config import BITGET_API_KEY, BITGET_API_SECRET, BITGET_API_PASSPHRASE, BITGET_BASE_URL, BITGET_WS_BASE_URL

router = APIRouter(
    prefix='/api/v1/bitget',
    tags=['Bitget'],
    include_in_schema=True,
)


def get_server_time():
    return str(requests.get(BITGET_BASE_URL + '/public/time').json()['data']['serverTime'])


def auth_headers(access_sign: str, server_time: str) -> dict:
    return {
        "ACCESS-KEY": BITGET_API_KEY,
        "ACCESS-PASSPHRASE": BITGET_API_PASSPHRASE,
        "ACCESS-SIGN": access_sign,
        "ACCESS-TIMESTAMP": server_time,
        "Content-Type": "application/json",
        "locale": "en-US",
    }


def generate_signature(server_time: str, method: str, request_path: str,
                       query_params: dict = None, body: dict = None) -> str:
    query_string = ""
    if query_params:
        query_string = urlencode(query_params)

    body_str = ""
    if body is not None and len(body) > 0:
        body_str = json.dumps(body, separators=(", ", ": "))

    if query_string:
        pre_hash = f"{server_time}{method.upper()}{request_path}?{query_string}{body_str}"
    else:
        pre_hash = f"{server_time}{method.upper()}{request_path}{body_str}"

    signature_bytes = hmac.new(
        BITGET_API_SECRET.encode('utf-8'),
        pre_hash.encode('utf-8'),
        hashlib.sha256
    ).digest()

    signature = base64.b64encode(signature_bytes).decode('utf-8')

    return signature


async def keep_alive(ws):
    while True:
        try:
            print("ping 시도")
            await ws.ping()
        except Exception as e:
            print("ping 실패: ", e)
            break
        await asyncio.sleep(30)


# 전체 심볼 조회
@router.get('/spot/public/symbols')
async def spot_symbols():
    response = requests.get(url=BITGET_BASE_URL + '/spot/public/symbols')
    return response.json()


# TODO: 현재가 조회 Ticker spot/future 분기처리
@router.websocket('/ws/spot/currency')
async def get_spot_currency(websocket: WebSocket):
    await websocket.accept()
    async with websockets.connect(BITGET_WS_BASE_URL, ping_interval=None) as bitget_ws:
        # 구독 메시지 세팅 (args 추가 가능)
        subscribe_msg = {
            "op": "subscribe",
            "args": [
                {
                    "instType": "SPOT",
                    "channel": "ticker",
                    "instId": "BTCUSDT"
                }
            ]
        }
        # Bitget 서버에 구독 요청
        await bitget_ws.send(json.dumps(subscribe_msg))
        # Ping 루프 병렬 실행
        asyncio.create_task(keep_alive(bitget_ws))
        # Bitget -> 서버 -> 클라이언트로 브로드캐스팅
        try:
            while True:
                msg = await bitget_ws.recv()
                print(msg)
                await websocket.send_text(msg)
        except websockets.exceptions.ConnectionClosed as e:
            print(f"Bitget WS 연결 종료: {e}")
        finally:
            await websocket.close()


# SPOT 출금
@router.post('/spot/wallet/withdrawal')
async def spot_withdrawal():
    server_time = get_server_time()

    path = "/api/v2/spot/wallet/withdrawal"
    body = OrderedDict([
        ("coin", "TRX"),
        ("transferType", "on_chain"),
        ("address", "TYG9kqrCvhYSZSVD4N4dxpDCwo6fqGh7n1"),
        ("chain", "TRX"),
        ("size", "29")
    ])

    signature = generate_signature(server_time, 'POST', path, None, body)
    headers = auth_headers(signature, server_time)

    response = requests.post(url=BITGET_BASE_URL + '/spot/wallet/withdrawal', headers=headers, json=body)
    return response.json()


# SPOT 트레이드
@router.post('/spot/trade')
async def spot_trade(trade_model: BitgetTrade):
    server_time = get_server_time()

    path = "/api/v2/spot/trade/place-order"
    body = OrderedDict([
        ("symbol", trade_model.symbol),
        ("side", trade_model.side),
        ("orderType", trade_model.order_type),
    ])
    if trade_model.order_type == "limit":
        body["price"] = trade_model.price
        body["force"] = trade_model.force
    body["size"] = trade_model.size

    signature = generate_signature(server_time, 'POST', path, None, body)
    headers = auth_headers(signature, server_time)

    response = requests.post(url=BITGET_BASE_URL + '/spot/trade/place-order', headers=headers, json=body)
    return response.json()


# TODO: FUTURE 현재가 조회 Ticker
@router.websocket('/ws/future/currency')
async def get_future_currency(websocket: WebSocket):
    await websocket.accept()
    async with websockets.connect(BITGET_WS_BASE_URL, ping_interval=None) as bitget_ws:
        subscribe_msg = {
            "op": "subscribe",
            "args": [
                {
                    "instType": "COIN-FUTURES",
                    "channel": "ticker",
                    "instId": "POPCATPERP_CMCBL"
                }
            ]
        }
        await bitget_ws.send(json.dumps(subscribe_msg))
        asyncio.create_task(keep_alive(bitget_ws))
        try:
            while True:
                msg = await bitget_ws.recv()
                print(msg)
                await websocket.send_text(msg)
        except websockets.exceptions.ConnectionClosed as e:
            print(f"Bitget WS 연결 종료: {e}")
        finally:
            await websocket.close()


# TODO: 유저 자산 조회 spot/future 분기처리
@router.get('/user/spot/asset')
async def user_spot_asset():
    timestamp = str(int(time.time() * 1000))
    signature = generate_signature(timestamp, 'GET', '/api/v2/spot/account/assets')

    headers = auth_headers(signature, timestamp)

    response = requests.get(url=BITGET_BASE_URL + '/spot/account/assets', headers=headers)

    return response.json()