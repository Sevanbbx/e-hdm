from __future__ import annotations

from dataclasses import asdict, is_dataclass
from datetime import datetime, UTC
from decimal import Decimal, ROUND_HALF_UP
from enum import Enum
from typing import Any


MONEY_QUANT = Decimal("0.01")
QUANTITY_QUANT = Decimal("0.001")


def to_decimal(value: Any) -> Decimal:
    if isinstance(value, Decimal):
        return value
    return Decimal(str(value))


def quantize_money(value: Any) -> Decimal:
    return to_decimal(value).quantize(MONEY_QUANT, rounding=ROUND_HALF_UP)


def quantize_quantity(value: Any) -> Decimal:
    return to_decimal(value).quantize(QUANTITY_QUANT, rounding=ROUND_HALF_UP)


def ensure_scale(value: Decimal, scale: int, field_name: str) -> None:
    exponent = abs(value.as_tuple().exponent)
    if exponent > scale:
        raise ValueError(f"{field_name} allows at most {scale} decimal places")


def timestamp_ms_to_datetime(value: int) -> datetime:
    return datetime.fromtimestamp(value / 1000, tz=UTC)


def clean_none(value: Any) -> Any:
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, Decimal):
        return str(value)
    if is_dataclass(value):
        value = asdict(value)
    if isinstance(value, dict):
        return {k: clean_none(v) for k, v in value.items() if v is not None}
    if isinstance(value, list):
        return [clean_none(item) for item in value]
    return value

