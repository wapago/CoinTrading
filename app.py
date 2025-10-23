from uvicorn import run
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from domain.v1 import binance, bitget, blockfin
from config import static_path


app = FastAPI(
    title='CoinTrading_test',
    version='0.0.1'
)

app.mount('/static', StaticFiles(directory=static_path), name='static')
app.include_router(binance.router)
app.include_router(bitget.router)
app.include_router(blockfin.router)




if __name__ == '__main__':
    run('app:app', host='0.0.0.0', port=9000, reload=True)
