import asyncio

import websockets
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from collections import OrderedDict

import aiohttp
import time
import requests
import uuid, hmac, hashlib, base64
import json

from urllib.parse import urlencode

from config.config import BLOCKFIN_BASE_URL, BLOCKFIN_WS_BASE_URL, BLOCKFIN_API_KEY, BLOCKFIN_API_SECRET, BLOCKFIN_API_PASSPHRASE

router = APIRouter(
    prefix='/api/v1/blockfin',
    tags=['Blockfin'],
    include_in_schema=True,
)



def auth_headers(signature: str, timestamp: str, nonce: str) -> dict:
    return {
        "ACCESS-KEY": BLOCKFIN_API_KEY,
        "ACCESS-SIGN": signature,
        "ACCESS-TIMESTAMP": timestamp,
        "ACCESS-NONCE": nonce,
        "ACCESS-PASSPHRASE": BLOCKFIN_API_PASSPHRASE
    }


def generate_signature(method: str, request_path: str, query_params: str, body: dict = None) -> str:
    timestamp = str(int(time.time() * 1000))
    nonce = str(uuid.uuid4())
    query_string = urlencode(query_params)
    body_str = ""
    if body is not None and len(body) > 0:
        body_str = json.dumps(body, separators=(",", ":"))

    pre_hash = f"{request_path}?{query_string}{method}{timestamp}{nonce}{body_str}"

    hex_signature = hmac.new(
        BLOCKFIN_API_SECRET.encode(),
        pre_hash.encode(),
        hashlib.sha256
    ).hexdigest().encode()

    signature = base64.b64encode(hex_signature).decode()

    return timestamp, nonce, query_string, signature

@router.get('/user/spot/asset')
async def user_spot_asset():
    query_params = {
        "accountType": "funding"
    }
    request_path = '/api/v1/asset/balances'
    timestamp, nonce, query_string, signature = generate_signature(method='GET', request_path=request_path, query_params=query_params)

    headers = auth_headers(signature, timestamp, nonce)

    response_json = requests.get(url=f"{BLOCKFIN_BASE_URL}{request_path}?{query_string}", headers=headers).json()
    print(response_json)

    if "data" in response_json:
        response_json = [asset for asset in response_json["data"] if float(asset.get("balance", 0)) > 0]

    return response_json


@router.get('/order/book')
async def get_order_book(inst_id: str = None):
    query_params = {
        "instId": inst_id # BTC-USDT
    }
    request_path = '/api/v1/market/books'

    timestamp, nonce, query_string, signature = generate_signature(method='GET', request_path=request_path, query_params=query_params)

    headers = auth_headers(signature, timestamp, nonce)

    response_json = requests.get(url=f"{BLOCKFIN_BASE_URL}{request_path}?{query_string}", headers=headers).json()
    print(response_json) # {'code': '0', 'msg': 'success', 'data': [{'asks': [['109476.9', '7344']], 'bids': [['109476.8', '2442']], 'ts': '1761217581477'}]}

    return response_json


@router.get('/symbols')
async def get_symbols(inst_id: str = None):
    query_params = {
        "instId": inst_id  # BTC-USDT
    }
    request_path = '/api/v1/market/instruments'

    timestamp, nonce, query_string, signature = generate_signature(method='GET', request_path=request_path, query_params=query_params)

    headers = auth_headers(signature, timestamp, nonce)

    response_json = requests.get(url=f"{BLOCKFIN_BASE_URL}{request_path}?{query_string}", headers=headers).json()
    print(response_json)  # {'code': '0', 'msg': 'success', 'data': [{'instId': 'BTC-USDT', 'baseCurrency': 'BTC', 'quoteCurrency': 'USDT', 'contractValue': '0.001', 'listTime': '1673517600000', 'expireTime': '2521900800000', 'maxLeverage': '150', 'minSize': '0.1', 'lotSize': '0.1', 'tickSize': '0.1', 'instType': 'SWAP', 'contractType': 'linear', 'maxLimitSize': '210000', 'maxMarketSize': '100000', 'state': 'live', 'contractValueMultiplier': '0.1', 'settleCurrency': 'USDT'}]}

    return response_json


# TODO: GET Futures Account Balance --> GET /api/v1/account/balance --> https://docs.blockfin.com/index.html#get-futures-account-balance
# TODO: Place Order --> POST /api/v1/trade/order --> https://docs.blockfin.com/index.html#place-order
# TODO: Set Leverage --> POST /api/v1/account/set-leverage --> https://docs.blockfin.com/index.html#get-futures-account-balance
# TODO: GET Futures Account Balance --> GET /api/v1/account/balance --> https://docs.blockfin.com/index.html#get-futures-account-balance