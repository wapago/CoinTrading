from typing import Optional

from .base import *

class BlockFinTrade(Base):
    """
    market: market order
    limit: limit order
    post_only: Post-only order
    fok: Fill-or-kill order
    ioc: Immediate-or-cancel order
    """
    inst_id: str
    margin_mode: str
    position_side: str
    side: str
    order_type: Optional[str] = Field(default=None, description="")
    price: Optional[str] = Field(default=None, description="")
    size: float

    reduce_only: Optional[str] = Field(default=None, description="")
    client_order_id: Optional[str] = Field(default=None, description="")
    tp_trigger_price: Optional[str] = Field(default=None, description="")
    tp_order_price: Optional[str] = Field(default=None, description="")
    sl_trigger_price: Optional[str] = Field(default=None, description="")
    sl_order_price: Optional[str] = Field(default=None, description="")
    broker_id: Optional[str] = Field(default=None, description="")

    leverage: str
    position_side: str # long/short
    position_mode: Optional[str] = Field(default=None, description="") # long_short_mode


class BlockFinLeverage(Base):
    inst_id: str
    leverage: str
    margin_mode: str
    position_side: Optional[str] = Field(default=None)