import asyncio
from typing import Annotated

import websockets

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Form, HTTPException

import time
import requests
import uuid, hmac, hashlib, base64
import json

from urllib.parse import urlencode

from config.models.blockfin import LoginForm, BlockFinTrade, BlockFinLeverage
from config.config import (BLOCKFIN_BASE_URL, BLOCKFIN_WS_BASE_URL, BLOCKFIN_API_KEY, BLOCKFIN_API_SECRET,
                           BLOCKFIN_API_PASSPHRASE, BLOCKFIN_WS_PRIVATE_URL, symbol_obj)

router = APIRouter(
    prefix='/api/v1/blockfin',
    tags=['Blockfin'],
    include_in_schema=True,
)

register_waiting = {}

def set_auth_headers(signature: str, timestamp: str, nonce: str) -> dict:
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
    elif not query_params and body_str:
        pre_hash = f"{request_path}{method}{timestamp}{nonce}{body_str}"
    else:
        pre_hash = f"{request_path}{method}{timestamp}{nonce}"

    hex_signature = hmac.new(
        BLOCKFIN_API_SECRET.encode(),
        pre_hash.encode(),
        hashlib.sha256
    ).hexdigest().encode()

    signature = base64.b64encode(hex_signature).decode()

    return timestamp, nonce, query_string, signature


@router.post('/validate')
async def validate_key(login_data: Annotated[LoginForm, Form()]):
    # 블록핀서버에서 uid, api_key, passphrase 검증
    request_path = '/api/v1/user/query-apikey'
    timestamp, nonce, query_string, signature = generate_signature(method='GET', request_path=request_path)
    headers = {
        "ACCESS-KEY": login_data.api_key,
        "ACCESS-SIGN": signature,
        "ACCESS-TIMESTAMP": timestamp,
        "ACCESS-NONCE": nonce,
        "ACCESS-PASSPHRASE": login_data.passphrase
    }
    response_json = requests.get(url=f"{BLOCKFIN_BASE_URL}{request_path}?{query_string}", headers=headers).json()
    uid = response_json['data']['uid']

    return_obj = {
        'msg': response_json['msg']
    }
    if login_data.uid != uid:
        return_obj['msg'] = 'Invalidate UID'
        return_obj['valid'] = False

    if login_data.uid == uid and response_json['msg'] == 'success':
        return_obj['valid'] = True

    print(return_obj)
    return return_obj


@router.websocket('/ws/login')
async def login(login_data: Annotated[LoginForm, Form()], websocket: WebSocket):
    await websocket.accept()

    # select해서 없으면 insert처리
    return_obj = dict(success=True, is_validate=True, waiting=False, redirect='http://localhost:5000/main')
    return return_obj


# 유저 선물계좌조회
@router.get('/user/asset')
async def user_asset():
    query_params = {
        "accountType": "futures"
    }
    request_path = '/api/v1/asset/balances'
    timestamp, nonce, query_string, signature = generate_signature(method='GET', request_path=request_path, query_params=query_params)

    headers = set_auth_headers(signature, timestamp, nonce)

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

    headers = set_auth_headers(signature, timestamp, nonce)

    response_json = requests.get(url=f"{BLOCKFIN_BASE_URL}{request_path}?{query_string}", headers=headers).json()
    print(response_json)

    return response_json

# 심볼정보조회
@router.get('/symbols')
async def get_symbols(inst_id: str = None):
    query_params = {
        "instId": inst_id  # BTC-USDT
    }
    request_path = '/api/v1/market/instruments'

    timestamp, nonce, query_string, signature = generate_signature(method='GET', request_path=request_path, query_params=query_params)

    headers = set_auth_headers(signature, timestamp, nonce)

    response_json = requests.get(url=f"{BLOCKFIN_BASE_URL}{request_path}?{query_string}", headers=headers).json()

    return response_json


@router.websocket('/ws/account/future')
async def get_future(websocket: WebSocket):
    await websocket.accept()

    method = "GET"
    path = "/users/self/verify"
    timestamp, nonce, query_string, signature = generate_signature(method, path)

    login_msg = {
        "op": "login",
        "args": [{
            "apiKey": BLOCKFIN_API_KEY.strip(),
            "passphrase": BLOCKFIN_API_PASSPHRASE.strip(),
            "timestamp": timestamp.strip(),
            "sign": signature.strip(),
            "nonce": nonce
        }]
    }

    async with websockets.connect(BLOCKFIN_WS_PRIVATE_URL, ping_interval=30, ping_timeout=10) as blockfin_ws:
        await blockfin_ws.send(json.dumps(login_msg))
        login_resp = await blockfin_ws.recv()
        print(f"LOGIN_RESP: {login_resp}")

        if '"event":"login"' in login_resp and '"code":"0"' in login_resp:
            print("Login success")
            subscribe_msg = {
                "op": "subscribe",
                "args": [
                    {
                        "channel": "account"
                    }
                ]
            }
            await blockfin_ws.send(json.dumps(subscribe_msg))

            # push 데이터 수신 루프
            while True:
                try:
                    msg = await blockfin_ws.recv()
                    data = json.loads(msg)
                    print(data)
                except Exception as e:
                    print(f"Error in recv loop: {e}")
                    break


# 현재가 조회
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

    headers = set_auth_headers(signature, timestamp, nonce)

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
    timestamp, nonce, query_string, signature = generate_signature(method='POST', request_path=position_mode_request_path,
                                                                   query_params=None, body=body)
    headers = set_auth_headers(signature, timestamp, nonce)
    position_mode_response_json = requests.post(f"{BLOCKFIN_BASE_URL}{position_mode_request_path}", headers=headers, json=body).json()
    print(f"position_mode 응답: {position_mode_response_json}")

    # set margin_mode 'cross' / 'isolated'
    margin_mode_request_path = '/api/v1/account/set-margin-mode'
    body = dict(marginMode=trade_model.margin_mode)
    timestamp, nonce, query_string, signature = generate_signature(method='POST', request_path=margin_mode_request_path, query_params=None, body=body)
    headers = set_auth_headers(signature, timestamp, nonce)
    margin_mode_response_json = requests.post(url=f"{BLOCKFIN_BASE_URL}{margin_mode_request_path}", headers=headers, json=body).json()
    print(f"margin_mode_response_json 응답: {margin_mode_response_json}")

    # set leverage
    leverage_request_path = '/api/v1/account/set-leverage'
    body = dict(instId=inst_id, leverage=trade_model.leverage, marginMode=trade_model.margin_mode, positionSide=trade_model.position_side)
    timestamp, nonce, query_string, signature = generate_signature(method='POST', request_path=leverage_request_path, query_params=None, body=body)
    headers = set_auth_headers(signature, timestamp, nonce)
    leverage_response_json = requests.post(url=f"{BLOCKFIN_BASE_URL}{leverage_request_path}", headers=headers, json=body).json()
    print(f"leverage_response_json 응답: {leverage_response_json}")

    # place order
    request_path = '/api/v1/trade/order'
    print(f"입력 size: {trade_model.size}")
    body = dict(instId=inst_id, marginMode=trade_model.margin_mode, positionSide=trade_model.position_side, side=trade_model.side,
                orderType=trade_model.order_type, price=trade_model.price, size=req_size)

    timestamp, nonce, query_string, signature = generate_signature(method='POST', request_path=request_path, query_params=None, body=body)

    headers = set_auth_headers(signature, timestamp, nonce)

    print(f"timestamp: {timestamp}")
    print(f"{BLOCKFIN_BASE_URL}{request_path}")
    print(f"body: {body}")

    response_json = requests.post(url=f"{BLOCKFIN_BASE_URL}{request_path}", headers=headers, json=body).json()

    print(f"응답: {response_json}")

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
    headers = set_auth_headers(signature, timestamp, nonce)
    response_json = requests.post(f"{BLOCKFIN_BASE_URL}{request_path}", headers=headers, json=body).json()
    print(response_json)


@router.post('/get_position_mode')
async def get_position_mode():
    request_path = '/api/v1/account/position-mode'
    timestamp, nonce, query_string, signature = generate_signature(method='GET', request_path=request_path)
    headers = set_auth_headers(signature, timestamp, nonce)
    response_json = requests.get(f"{BLOCKFIN_BASE_URL}{request_path}", headers=headers).json()
    print(response_json)


@router.websocket('/ws/future/authenticate')
async def blockfin_ws_login(websocket: WebSocket):
    await websocket.accept()

    method = "GET"
    path = "/users/self/verify"
    timestamp, nonce, query_string, signature = generate_signature(method, path)

    login_msg = {
        "op": "login",
        "args": [{
            "apiKey": BLOCKFIN_API_KEY.strip(),
            "passphrase": BLOCKFIN_API_PASSPHRASE.strip(),
            "timestamp": timestamp.strip(),
            "sign": signature.strip(),
            "nonce": nonce
        }]
    }

    # TODO: ROI * 레버리지 반영할 것.
    # 포지션이 존재하는 심볼만 response됨.
    async with websockets.connect(BLOCKFIN_WS_PRIVATE_URL) as blockfin_ws:
        await blockfin_ws.send(json.dumps(login_msg))
        login_resp = await blockfin_ws.recv()
        print(f"LOGIN_RESP: {login_resp}")

        if '"event":"login"' in login_resp and '"code":"0"' in login_resp:
            print("✅ Login success, subscribing to positions...")
            subscribe_msg = {
                "op": "subscribe",
                "args": [
                    {
                        "channel": "positions"
                    }
                ]
            }
            for symbol in ['BTC-USDT', 'ETH-USDT']:
                subscribe_msg['args'][0]['instId'] = symbol
                await blockfin_ws.send(json.dumps(subscribe_msg))

            # push 데이터 수신 루프
            while True:
                try:
                    msg = await blockfin_ws.recv()
                    data = json.loads(msg)
                    print(data)
                    # await blockfin_ws.send(json.dumps(position_msg))
                    # positions = await blockfin_ws.recv()
                    # print(f"POSITIONS: {positions}")
                except Exception as e:
                    print(f"Error in recv loop: {e}")
                    break