from typing import Optional

from .base import *

class BinanceTrade(Base):
    symbol: str
    side: str
    type: str
    quantity: Optional[str] = Field(default=None, description="Only required for limit orders")
    quote_order_qty: Optional[str] = Field(default=None, description="Only required for limit orders")
    time_in_force: Optional[str] = Field(default=None, description="Only required for limit orders")
    price: Optional[str] = Field(default=None, description="Only required for limit orders")
    force: Optional[str] = Field(default=None, description="Only required for limit orders")


class BinanceWithdrawal(Base):
    coin: str
    network: str
    address: str
    amount: str
