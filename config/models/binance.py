from typing import Optional

from .base import *

class BinanceSymbol(Base):
    symbol: str

class BinanceSpotTrade(BinanceSymbol):
    side: str
    type: str
    quantity: Optional[str] = Field(default=None, description="Only required for limit orders")
    quote_order_qty: Optional[str] = Field(default=None, description="Only required for limit orders")
    time_in_force: Optional[str] = Field(default=None, description="Only required for limit orders")
    price: Optional[str] = Field(default=None, description="Only required for limit orders")
    force: Optional[str] = Field(default=None, description="Only required for limit orders")


class BinanceFutureTrade(BinanceSymbol):
    leverage: str
    margin_type: str
    side: str
    position_side: str
    type: str
    time_in_force: Optional[str] = Field(default=None, description="Only required for limit orders")
    quantity: Optional[str] = Field(default=None, description="Required for limit orders")
    price: Optional[str] = Field(default=None, description="Only required for limit orders")
    quote_order_qty: Optional[str] = Field(default=None, description="Only required for limit orders")


class BinanceWithdrawal(Base):
    coin: str
    network: str
    address: str
    amount: str
