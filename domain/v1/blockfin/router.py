import asyncio

import websockets
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, HTTPException
from collections import OrderedDict

import aiohttp
import time
import requests
import uuid, hmac, hashlib, base64
import json

from urllib.parse import urlencode

from config.models.blockfin import BlockFinTrade, BlockFinLeverage
from config.config import BLOCKFIN_BASE_URL, BLOCKFIN_WS_BASE_URL, BLOCKFIN_API_KEY, BLOCKFIN_API_SECRET, BLOCKFIN_API_PASSPHRASE, symbol_obj

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


def generate_signature(method: str, request_path: str, query_params: str = None, body: dict = None) -> str:
    timestamp = str(int(time.time() * 1000))
    nonce = str(uuid.uuid4())

    query_string = ""
    if query_params:
        query_string = urlencode(query_params)

    body_str = ""
    if body is not None and len(body) > 0:
        body_str = json.dumps(body, separators=(", ", ": "))

    if query_params:
        pre_hash = f"{request_path}?{query_string}{method}{timestamp}{nonce}{body_str}"
    else:
        pre_hash = f"{request_path}{method}{timestamp}{nonce}{body_str}"

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
        "accountType": "futures"
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

    return response_json


# TODO: FUTURE 밸런스 체크
@router.websocket('/ws/future/currency')
async def get_future_currency(websocket: WebSocket):
    await websocket.accept()
    async with websockets.connect(BLOCKFIN_WS_BASE_URL, ping_interval=30, ping_timeout=10) as blockfin_ws:
        subscribe_msg = {
            "op": "subscribe",
            "args": [
                {
                    "channel": "trades",
                    "instId": "BTC-USDT"
                }
            ]
        }
        await blockfin_ws.send(json.dumps(subscribe_msg))

        try:
            while True:
                msg = await blockfin_ws.recv()
                print(msg)
                await websocket.send_text(msg)
        except websockets.exceptions.ConnectionClosed as e:
            print(f"BLOCKFIN WS 연결 종료: {e}")
        finally:
            await websocket.close()


@router.get('/affiliates')
async def get_affiliates():
    request_path = '/api/v1/affiliate/basic'

    timestamp, nonce, query_string, signature = generate_signature(method='GET', request_path=request_path)

    headers = auth_headers(signature, timestamp, nonce)

    response_json = requests.get(url=f"{BLOCKFIN_BASE_URL}{request_path}", headers=headers).json()
    print(response_json)  # {"code": "80006", "msg": "non exist affiliate" }

    return response_json

# TODO: 부분청산
@router.post('/future/trade')
async def future_trade(trade_model: BlockFinTrade):
    # validate size
    inst_id = trade_model.inst_id.upper()
    input_size = trade_model.size
    contract_value = float(symbol_obj[inst_id]['data'][0]['contractValue'])
    lot_size = float(symbol_obj[inst_id]['data'][0]['lotSize'])

    if input_size / contract_value < lot_size:
        raise HTTPException(status_code=400, detail="Requested size is Too Small")

    req_size = str(input_size / contract_value)
    print(req_size)
    print(lot_size)

    # set position mode(one-way or hedge) 'net_mode' / 'long_short_mode'
    position_mode_request_path = '/api/v1/account/set-position-mode'
    body = dict(positionMode=trade_model.position_mode)
    timestamp, nonce, query_string, signature = generate_signature(method='POST', request_path=position_mode_request_path, query_params=None, body=body)
    headers = auth_headers(signature, timestamp, nonce)
    position_mode_response_json = requests.post(f"{BLOCKFIN_BASE_URL}{position_mode_request_path}", headers=headers, json=body).json()
    print(f"position_mode 응답: {position_mode_response_json}")

    # set margin_mode 'cross' / 'isolated'
    margin_mode_request_path = '/api/v1/account/set-margin-mode'
    body = dict(marginMode=trade_model.margin_mode)
    timestamp, nonce, query_string, signature = generate_signature(method='POST', request_path=margin_mode_request_path, query_params=None, body=body)
    headers = auth_headers(signature, timestamp, nonce)
    margin_mode_response_json = requests.post(url=f"{BLOCKFIN_BASE_URL}{margin_mode_request_path}", headers=headers, json=body).json()
    print(f"margin_mode_response_json 응답: {margin_mode_response_json}")

    # set leverage
    leverage_request_path = '/api/v1/account/set-leverage'
    body = dict(instId=inst_id, leverage=trade_model.leverage, marginMode=trade_model.margin_mode, positionSide=trade_model.position_side)
    timestamp, nonce, query_string, signature = generate_signature(method='POST', request_path=leverage_request_path, query_params=None, body=body)
    headers = auth_headers(signature, timestamp, nonce)
    leverage_response_json = requests.post(url=f"{BLOCKFIN_BASE_URL}{leverage_request_path}", headers=headers, json=body).json()
    print(f"leverage_response_json 응답: {leverage_response_json}")

    # place order
    request_path = '/api/v1/trade/order'
    print(f"입력 size: {trade_model.size}")
    body = dict(instId=inst_id, marginMode=trade_model.margin_mode, positionSide=trade_model.position_side, side=trade_model.side,
                orderType=trade_model.order_type, price=trade_model.price, size=req_size)

    timestamp, nonce, query_string, signature = generate_signature(method='POST', request_path=request_path, query_params=None, body=body)

    headers = auth_headers(signature, timestamp, nonce)

    print(f"timestamp: {timestamp}")
    print(f"{BLOCKFIN_BASE_URL}{request_path}")
    print(f"body: {body}")

    response_json = requests.post(url=f"{BLOCKFIN_BASE_URL}{request_path}", headers=headers, json=body).json()

    print(f"응답: {response_json}")

    return response_json


@router.post('/future/position-mode')
async def set_position_mode(postion_mode: str):
    request_path = '/api/v1/account/set-position-mode'
    body = { "positionMode": postion_mode }
    timestamp, nonce, query_string, signature = generate_signature(method='POST', request_path=request_path, query_params=None, body=body)
    headers = auth_headers(signature, timestamp, nonce)
    response_json = requests.post(f"{BLOCKFIN_BASE_URL}{request_path}", headers=headers, json=body).json()
    print(response_json)
    return response_json


@router.post('/set-leverage')
async def set_leverage(leverage_model: BlockFinLeverage):
    request_path = '/api/v1/account/set-leverage'
    body = {
        "instId": leverage_model.inst_id,
        "leverage": leverage_model.leverage,
        "marginMode": leverage_model.margin_mode,
        "positionSide": leverage_model.position_side
    }
    timestamp, nonce, query_string, signature = generate_signature(method='POST', request_path=request_path, query_params=None, body=body)
    headers = auth_headers(signature, timestamp, nonce)
    response_json = requests.post(f"{BLOCKFIN_BASE_URL}{request_path}", headers=headers, json=body).json()
    print(response_json)


@router.post('/get_position_mode')
async def get_position_mode():
    request_path = '/api/v1/account/position-mode'
    timestamp, nonce, query_string, signature = generate_signature(method='GET', request_path=request_path)
    headers = auth_headers(signature, timestamp, nonce)
    response_json = requests.get(f"{BLOCKFIN_BASE_URL}{request_path}", headers=headers).json()
    print(response_json)



# TODO: GET Futures Account Balance --> GET /api/v1/account/balance --> https://docs.blockfin.com/index.html#get-futures-account-balance