import os

from dotenv import load_dotenv

root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
file = os.path.join(root, 'config')
static_path = os.path.join(root, 'static')
templates_path = os.path.join(root, 'templates')

load_dotenv(os.path.join(file, 'config.env'))


BINANCE_API_KEY = os.getenv('BINANCE_API_KEY')
BINANCE_API_SECRET = os.getenv('BINANCE_API_SECRET')
BINANCE_BASE_URL = os.getenv('BINANCE_BASE_URL')
BINANCE_BASE_F_URL = os.getenv('BINANCE_BASE_F_URL')
BINANCE_WS_API_BASE_URL = os.getenv('BINANCE_WS_API_BASE_URL')
BINANCE_WS_STREAM_BASE_URL = os.getenv('BINANCE_WS_STREAM_BASE_URL')
BINANCE_WS_F_STREAM_BASE_URL = os.getenv('BINANCE_WS_F_STREAM_BASE_URL')
BINANCE_WS_COMBINED_STREAM_BASE_URL = os.getenv('BINANCE_WS_COMBINED_STREAM_BASE_URL')

BITGET_API_KEY = os.getenv('BITGET_API_KEY')
BITGET_API_SECRET = os.getenv('BITGET_API_SECRET')
BITGET_API_PASSPHRASE = os.getenv('BITGET_API_PASSPHRASE')
BITGET_BASE_URL = os.getenv('BITGET_BASE_URL')
BITGET_WS_BASE_URL = os.getenv('BITGET_WS_BASE_URL')

BLOCKFIN_API_KEY = os.getenv('BLOCKFIN_API_KEY')
BLOCKFIN_API_SECRET = os.getenv('BLOCKFIN_API_SECRET')
BLOCKFIN_API_PASSPHRASE = os.getenv('BLOCKFIN_API_PASSPHRASE')
BLOCKFIN_BASE_URL = os.getenv('BLOCKFIN_BASE_URL')
BLOCKFIN_WS_BASE_URL = os.getenv('BLOCKFIN_WS_BASE_URL')
