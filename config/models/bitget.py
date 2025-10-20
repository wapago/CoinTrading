from typing import Optional

from .base import *

class BitgetTrade(Base):
    symbol: str
    side: str
    order_type: str
    price: Optional[str] = Field(default=None, description="Only required for limit orders")
    force: Optional[str] = Field(default=None, description="Only required for limit orders")
    size: str