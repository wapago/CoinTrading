import os

from dotenv import load_dotenv

root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
env_path = os.path.join(root, 'config', 'config.env')

load_dotenv(env_path)

DB = os.getenv('DB')
DRIVER = os.getenv('DRIVER')
HOST = os.getenv('HOST')
PORT = os.getenv('PORT')
DB_NAME = os.getenv('DB_NAME')
DB_URI = f'{DB}+{DRIVER}://{os.getenv("DB_USER")}:{os.getenv("PASSWORD")}@{HOST}:{PORT}/{DB_NAME}'
