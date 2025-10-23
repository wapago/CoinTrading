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

from starlette.requests import Request

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


def generate_signature(timestamp: str, method: str, nonce: str, request_path: str, body: dict = None) -> str:
    body_str = ""
    if body is not None and len(body) > 0:
        body_str = json.dumps(body, separators=(",", ":"))

    pre_hash = f"{request_path}{method}{timestamp}{nonce}{body_str}"

    hex_signature = hmac.new(
        BLOCKFIN_API_SECRET.encode(),
        pre_hash.encode(),
        hashlib.sha256
    ).hexdigest().encode()

    signature = base64.b64encode(hex_signature).decode()

    return signature


@router.get('/user/spot/asset')
async def user_spot_asset():
    timestamp = str(int(time.time() * 1000))
    nonce = str(uuid.uuid4())
    query_params = {
        "accountType": "funding"
    }
    query_string = urlencode(query_params)
    signature = generate_signature(timestamp=timestamp, method='GET', nonce=nonce, request_path='/api/v1/asset/balances?' + query_string)

    headers = auth_headers(signature, timestamp, nonce)

    response_json = requests.get(url=BLOCKFIN_BASE_URL + '/api/v1/asset/balances?' + query_string, headers=headers).json()
    print(response_json)

    if "data" in response_json:
        response_json = [asset for asset in response_json["data"] if float(asset.get("balance", 0)) > 0]

    return response_json