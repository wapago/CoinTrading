from typing import Optional

from .base import *

class LoginForm(Base):
    uid: str
    api_key: str
    secret_key: str
    passphrase: str


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
    side: Optional[str] = Field(default=None) # buy/sell
    order_type: Optional[str] = Field(default=None)
    price: Optional[str] = Field(default=None)
    size: Optional[float] = Field(default=None)

    reduce_only: Optional[str] = Field(default=None)
    client_order_id: Optional[str] = Field(default=None)
    tp_trigger_price: Optional[str] = Field(default=None)
    tp_order_price: Optional[str] = Field(default=None)
    sl_trigger_price: Optional[str] = Field(default=None)
    sl_order_price: Optional[str] = Field(default=None)
    broker_id: Optional[str] = Field(default=None)

    leverage: str
    position_side: str # long/short
    position_mode: Optional[str] = Field(default=None) # long_short_mode


class BlockFinLeverage(Base):
    inst_id: str
    leverage: str
    margin_mode: str
    position_side: Optional[str] = Field(default=None)