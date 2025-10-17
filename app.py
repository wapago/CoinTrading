from uvicorn import run
from fastapi import FastAPI

from domain.v1 import binance, bitget


app = FastAPI(
    title='CoinTrading_test',
    version='0.0.1'
)

app.include_router(binance.router)
app.include_router(bitget.router)




if __name__ == '__main__':
    run('app:app', host='0.0.0.0', port=9000, reload=True)
