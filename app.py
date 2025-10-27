import requests
from uvicorn import run
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from contextlib import asynccontextmanager

from domain.v1 import binance, bitget, blockfin
from domain.v1.blockfin.router import generate_signature, auth_headers, BLOCKFIN_BASE_URL
from config import static_path, symbol_obj, SYMBOL_LIST


def set_symbols(symbol_list: list):
    return_obj = {}
    for symbol in symbol_list:
        query_params = {"instId": symbol}  # BTC-USDT
        request_path = '/api/v1/market/instruments'
        timestamp, nonce, query_string, signature = generate_signature(method='GET', request_path=request_path, query_params=query_params)
        headers = auth_headers(signature, timestamp, nonce)
        response_json = requests.get(url=f"{BLOCKFIN_BASE_URL}{request_path}?{query_string}", headers=headers).json()
        return_obj[symbol] = response_json
    return return_obj


@asynccontextmanager
async def lifespan(_app: FastAPI):
    symbol_obj.update(set_symbols(SYMBOL_LIST))
    yield
    print("=========== SERVER SHUTDOWN ===========")


app = FastAPI(
    title='CoinTrading_test',
    version='0.0.1',
    lifespan=lifespan
)

app.mount('/static', StaticFiles(directory=static_path), name='static')
app.include_router(binance.router)
app.include_router(bitget.router)
app.include_router(blockfin.router)



if __name__ == '__main__':
    run('app:app', host='0.0.0.0', port=9000, reload=True)
