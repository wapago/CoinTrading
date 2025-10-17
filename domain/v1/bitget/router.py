import websockets
from fastapi import APIRouter, WebSocket

import aiohttp
import time
import requests
import hmac
import hashlib
import base64
import json

from urllib.parse import urlencode
from collections import OrderedDict
from config.config import BITGET_API_KEY, BITGET_API_SECRET, BITGET_API_PASSPHRASE, BITGET_BASE_URL, BITGET_WS_BASE_URL

router = APIRouter(
    prefix='/api/v1/bitget',
    tags=['Bitget'],
    include_in_schema=True,
)



# 전체 심볼 조회
@router.get('/exchange_info')
async def exchange_info():
    response = requests.get(url=BITGET_BASE_URL + '/spot/public/symbols')
    return response.json()


# 현재가 조회 Ticker
@router.websocket('/ws/currency')
async def get_currency(websocket: WebSocket):
    pass


# 유저 자산 조회(spot)
@router.get('/user/spot/asset')
async def user_spot_asset():
    timestamp = str(int(time.time() * 1000))
    signature = generate_signature(timestamp, 'GET', '/api/v2/spot/account/assets')

    headers = auth_headers(signature, timestamp)

    response = requests.get(url=BITGET_BASE_URL + '/spot/account/assets', headers=headers)

    return response.json()


# spot 출금
@router.post('/spot/wallet/withdrawal')
async def spot_withdrawal():
    # timestamp = str(int(time.time() * 1000))
    server_time = str(requests.get(BITGET_BASE_URL + '/public/time').json()['data']['serverTime'])

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


@router.websocket('/ws/currency')
async def get_currency(websocket: WebSocket):
    await websocket.accept()
    pass



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