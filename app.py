import requests
import secrets

from starlette.middleware.cors import CORSMiddleware
from starlette.middleware.sessions import SessionMiddleware
from uvicorn import run
from fastapi import FastAPI
from contextlib import asynccontextmanager

from domain.v1 import binance, bitget, blockfin
from domain.v1.blockfin.router import generate_signature, set_auth_headers
from config import symbol_obj, BLOCKFIN_BASE_URL, SYMBOL_LIST


secret_key = secrets.token_hex(32)
session_max_age = 60 * 60 * 24 * 90


def set_symbols(symbol_list: list):
    return_obj = {}
    for symbol in symbol_list:
        query_params = {"instId": symbol}  # BTC-USDT
        request_path = '/api/v1/market/instruments'
        timestamp, nonce, query_string, signature = generate_signature(method='GET', request_path=request_path, query_params=query_params)
        headers = set_auth_headers(signature, timestamp, nonce)
        response_json = requests.get(url=f"{BLOCKFIN_BASE_URL}{request_path}?{query_string}", headers=headers).json()
        return_obj[symbol] = response_json
    return return_obj


@asynccontextmanager
async def set_symbols(_app: FastAPI):
    symbol_obj.update(set_symbols(SYMBOL_LIST))
    yield
    print("=========== SERVER SHUTDOWN ===========")


app = FastAPI(
    title='CoinTrading_test',
    version='0.0.1',
    lifespan=set_symbols
)
app.add_middleware(SessionMiddleware, secret_key=secret_key, max_age=session_max_age, same_site="strict")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 프론트엔드 도메인
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(binance.router)
app.include_router(bitget.router)
app.include_router(blockfin.router)



if __name__ == '__main__':
    run('app:app', host='0.0.0.0', port=9000, reload=True)
