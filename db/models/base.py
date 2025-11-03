from datetime import datetime, date
from typing_extensions import Annotated

from sqlalchemy.sql import func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
from sqlalchemy import Integer, ForeignKey, JSON, PrimaryKeyConstraint, TIMESTAMP, UniqueConstraint


class Base(DeclarativeBase):
    pass
