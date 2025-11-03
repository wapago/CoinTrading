import time
import json
import asyncio
import websockets
import uuid, hmac, hashlib, base64
import aiohttp

from urllib.parse import urlencode
from setting import SETTINGS


BLOCKFIN_BASE_URL = 'https://openapi.blockfin.com'
BLOCKFIN_WS_BASE_URL = 'wss://openapi.blockfin.com/ws/public'
BLOCKFIN_WS_PRIVATE_URL = 'wss://openapi.blockfin.com/ws/private'


class BlockFin:
    def __init__(self, uid, api_key, secret_key, passphrase):
        self.uid = uid
        self.api_key = api_key
        self.secret_key = secret_key
        self.passphrase = passphrase


    async def generate_signature(self, method: str, request_path: str, query_params: str = None, body: dict = None) -> str:
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
            self.secret_key.encode(),
            pre_hash.encode(),
            hashlib.sha256
        ).hexdigest().encode()

        signature = base64.b64encode(hex_signature).decode()

        return timestamp, nonce, query_string, signature


    async def set_auth_headers(self, signature: str, timestamp: str, nonce: str) -> dict:
        return {
            "ACCESS-KEY": self.api_key,
            "ACCESS-SIGN": signature,
            "ACCESS-TIMESTAMP": timestamp,
            "ACCESS-NONCE": nonce,
            "ACCESS-PASSPHRASE": self.passphrase
        }


class BlockFinTrade:
    def __init__(self, uid, api_key, secret_key, passphrase):
        self.account = BlockFin(uid, api_key, secret_key, passphrase)
        self.interface_ws = None # LogicProcess가 나중에 주입.

    # 블록핀 웹소켓 로그인
    async def websocket_login(self):
        method = "GET"
        path = "/users/self/verify"
        timestamp, nonce, query_string, signature = await self.account.generate_signature(method, path)

        login_msg = {
            "op": "login",
            "args": [{
                "apiKey": self.account.api_key,
                "passphrase": self.account.passphrase,
                "timestamp": timestamp,
                "sign": signature,
                "nonce": nonce
            }]
        }
        async with websockets.connect(BLOCKFIN_WS_PRIVATE_URL, ping_interval=30, ping_timeout=10) as blockfin_ws:
            await blockfin_ws.send(json.dumps(login_msg))
            login_resp = await blockfin_ws.recv()
            print(f"LOGIN_RESP: {login_resp}")
            return login_resp

    # 1. 자산 조회
    async def fetch_wallet_balance(self) -> dict:
        async with websockets.connect(BLOCKFIN_WS_PRIVATE_URL, ping_interval=30, ping_timeout=10) as blockfin_ws:
            login_resp = self.websocket_login()
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
                        print(f"자산조회: {data}")
                    except Exception as e:
                        print(f"Error in recv loop: {e}")
                        break

    # 2. 실시간 가격 스트림
    async def fetch_symbol_price(self, inst_id: str = "BTC-USDT"):
        async with websockets.connect(BLOCKFIN_WS_BASE_URL, ping_interval=30, ping_timeout=10) as ws:
            subscribe_msg = {
                "op": "subscribe",
                "args": [{"channel": "trades", "instId": inst_id}]
            }
            await ws.send(json.dumps(subscribe_msg))
            print(f"[{inst_id}] trades 채널 구독 시작")

            while True:
                try:
                    msg = await ws.recv()
                    data = json.loads(msg)
                    if "data" in data and data["arg"]["channel"] == "trades":
                        price = float(data["data"][0]["price"])
                        yield price
                except Exception as e:
                    print(f"[fetch_symbol_price] 에러: {e}")
                    break

    # 3. 한번만 현재가 가져오기
    async def fetch_symbol_price_once(self, inst_id: str = "BTC-USDT") -> float:
        async for price in self.fetch_symbol_price(inst_id):
            return price  # 첫 번째 값만 받고 바로 종료

    # 3. 보유포지션 현황
    async def fetch_positions(self) -> dict:
        login_resp = self.websocket_login()

        async with websockets.connect(BLOCKFIN_WS_PRIVATE_URL) as blockfin_ws:
            if '"event":"login"' in login_resp and '"code":"0"' in login_resp:
                print("Login success, subscribing to positions...")
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
                        position_resp = await blockfin_ws.recv()
                        print(f"WSS POSITION RESP: {position_resp}")

                        return position_resp
                    except Exception as e:
                        print(f"Error in recv loop: {e}")
                        break

    # 4. 심볼설정값 가져오기
    async def set_symbols(self, inst_id: str):
        return_obj = {}

        query_params = {"instId": inst_id}  # BTC-USDT
        request_path = '/api/v1/market/instruments'
        timestamp, nonce, query_string, signature = self.account.generate_signature(method='GET', request_path=request_path, query_params=query_params)
        headers = self.account.set_auth_headers(signature, timestamp, nonce)
        async with aiohttp.ClientSession() as session:
            async with session.get(f"{BLOCKFIN_BASE_URL}{request_path}?{query_string}", headers=headers) as resp:
                response_data = await resp.json()
        return_obj[inst_id] = response_data
        return return_obj

    # 5. 주문 사이즈 검증
    async def validate_req_size(self, setting):
        inst_id = setting['inst_id']
        current_order_idx = setting['current_order_idx']
        leverage = setting['leverage']
        symbol_obj = await self.set_symbols(inst_id)

        # 수량 = (진입금액 * 레버리지) / 진입시점가격
        current_price = await self.fetch_symbol_price_once(inst_id)  # 현재가격

        amount = float(setting['additional'][current_order_idx]['amount'])  # 진입금액
        input_size = (amount * leverage) / current_price
        contract_value = float(symbol_obj[inst_id]['data'][0]['contractValue'])
        req_size = str(input_size / contract_value)
        lot_size = float(symbol_obj[inst_id]['data'][0]['lotSize'])
        print(f"요청사이즈 / 단위사이즈: {req_size} / {lot_size}")

        if input_size / contract_value < lot_size:
            print("Requested size is Too Small")
            return False, req_size
        else:
            return True, req_size

    # 6. 매수주문 함수
    async def place_order(self, inst_id: str, margin_mode: str, leverage: int, position_side: str, side: str, order_type: str, req_size:float):
        # set position mode(one-way or hedge) 'net_mode' / 'long_short_mode'
        position_mode_request_path = '/api/v1/account/set-position-mode'
        body = dict(positionMode='long_short_mode')
        timestamp, nonce, query_string, signature = self.account.generate_signature(method='POST', request_path=position_mode_request_path,
                                                                                    query_params=None, body=body)
        headers = self.account.set_auth_headers(signature, timestamp, nonce)
        async with aiohttp.ClientSession() as session:
            async with session.post(f"{BLOCKFIN_BASE_URL}{position_mode_request_path}", headers=headers, json=body) as resp:
                position_mode_response_json = await resp.json()
        print(f"position_mode 응답: {position_mode_response_json}")

        # --------------------------------------------------------------------------------------------------------

        # set  'cross' / 'imargin_modesolated'
        margin_mode_request_path = '/api/v1/account/set-margin-mode'
        body = dict(marginMode=margin_mode)
        timestamp, nonce, query_string, signature = self.account.generate_signature(method='POST', request_path=margin_mode_request_path,
                                                                                    query_params=None, body=body)
        headers = self.account.set_auth_headers(signature, timestamp, nonce)
        async with aiohttp.ClientSession() as session:
            async with session.post(f"{BLOCKFIN_BASE_URL}{margin_mode_request_path}", headers=headers, json=body) as resp:
                margin_mode_response_json = await resp.json()
        print(f"margin_mode_response_json 응답: {margin_mode_response_json}")

        # --------------------------------------------------------------------------------------------------------

        # set leverage
        leverage_request_path = '/api/v1/account/set-leverage'
        body = dict(instId=inst_id, leverage=leverage, marginMode=margin_mode, positionSide=position_side)
        timestamp, nonce, query_string, signature = self.account.generate_signature(method='POST', request_path=leverage_request_path,
                                                                                    query_params=None,
                                                                                    body=body)
        headers = self.account.set_auth_headers(signature, timestamp, nonce)
        async with aiohttp.ClientSession() as session:
            async with session.post(f"{BLOCKFIN_BASE_URL}{leverage_request_path}", headers=headers, json=body) as resp:
                leverage_response_json = await resp.json()
        print(f"leverage_response_json 응답: {leverage_response_json}")

        # --------------------------------------------------------------------------------------------------------

        # place order
        request_path = '/api/v1/trade/order'
        body = dict(instId=inst_id, marginMode=margin_mode, positionSide=position_side, side=side,
                    orderType=order_type, size=req_size)

        timestamp, nonce, query_string, signature = self.account.generate_signature(method='POST', request_path=request_path, query_params=None,
                                                                                    body=body)
        headers = self.account.set_auth_headers(signature, timestamp, nonce)
        async with aiohttp.ClientSession() as session:
            async with session.post(f"{BLOCKFIN_BASE_URL}{request_path}", headers=headers, json=body) as resp:
                order_response_json = await resp.json()
                return order_response_json

    # 7. 포지션 진입
    async def enter_position(self, position: str = "BTC_LONG") -> dict:
        setting = SETTINGS[position]

        current_order_idx = setting['additional_entry_idx']  # 현재 진입순서
        entry_length = len(setting['addtional_entry'])
        is_trading = setting['is_trading']
        is_stop = setting['is_stop']

        if not is_trading and not is_stop:
            inst_id = setting['inst_id']
            margin_mode = setting['margin_mode']
            position_side = setting['position_side']
            leverage = setting['leverage']
            order_type = setting['order_type']
            side = 'BUY'

            # validate size
            is_validate, req_size = await self.validate_req_size(setting)

            if is_validate:
                order_response_json = await self.place_order(inst_id, margin_mode, leverage, position_side, side, order_type, req_size)
                print(f"응답: {order_response_json}")
                # current_order_idx: 1 추가
                if entry_length > current_order_idx:
                    setting['additional_entry_idx'] += 1
                return order_response_json
            else:
                print("Requested size is Too Small")
        elif is_trading:
            return "트레이딩 중입니다"
        elif is_stop:
            return "재시작해주세요"

    # 8. 추가진입 체크
    async def check_additional_entry(self, position: str = "BTC_LONG") -> dict:
        setting = SETTINGS[position]
        inst_id = setting['inst_id']
        is_trading = setting['is_trading']
        is_stop = setting['is_stop']
        position_side = setting['position_side']
        entry_length = len(setting['addtional_entry'])
        current_order_idx = setting['current_order_idx']
        login_resp = self.websocket_login()

        if is_trading and not is_stop and current_order_idx != 0:
            async with websockets.connect(BLOCKFIN_WS_PRIVATE_URL) as blockfin_ws:
                if '"event":"login"' in login_resp and '"code":"0"' in login_resp:
                    print("Login success, subscribing to positions...")
                    # 구독 메시지: 보유포지션 현황
                    subscribe_msg = {
                        "op": "subscribe",
                        "args": [
                            {
                                "channel": "positions",
                                "inst_id": inst_id
                            }
                        ]
                    }
                    # 구독 메시지 요청
                    await blockfin_ws.send(json.dumps(subscribe_msg))
                    # 구독 데이터 수신 루프
                    while True:
                        try:
                            msg = await blockfin_ws.recv()
                            position_resp = json.loads(msg)
                            print(f"POSITION RESP: {position_resp}")
                            markPrice = position_resp['data'][0]['markPrice']   # 현재가
                            averagePrice = position_resp['data'][0]['averagePrice'] # 매수단가
                            leverage = position_resp['data'][0]['leverage']

                            gap = setting['addtional_entry'][current_order_idx]['gap']
                            multiplier = 1 if position_side == "long" else -1
                            roi = (markPrice - averagePrice) / averagePrice * leverage * 100 * multiplier
                            # 추가진입 판단
                            if roi < 0 and abs(roi) >= gap:
                                margin_mode = setting['margin_mode']
                                position_side = setting['position_side']
                                leverage = setting['leverage']
                                order_type = setting['order_type']
                                side = 'BUY'

                                is_validate, req_size = await self.validate_req_size(setting)

                                if is_validate:
                                    order_response_json = await self.place_order(inst_id, margin_mode, leverage, position_side, side, order_type,
                                                                                 req_size)
                                    print(f"응답: {order_response_json}")
                                    # current_order_idx: 1 추가
                                    if entry_length > current_order_idx:
                                        setting['additional_entry_idx'] += 1
                                else:
                                    print("Requested size is Too Small")
                        except Exception as e:
                            print(f"Error in recv loop: {e}")
                            break


