from __future__ import annotations

from enum import Enum, IntEnum


class Language(str, Enum):
    HY = "hy"
    EN = "en"
    RU = "ru"


class TaxRegime(IntEnum):
    VAT = 1
    NO_VAT = 2
    TURNOVER = 3
    MICRO = 7


class PrintMode(IntEnum):
    PRODUCTS = 2
    PREPAYMENT = 3


class SaleType(IntEnum):
    PREPAYMENT = 0
    PRODUCTS = 2


class ReceiptType(IntEnum):
    SALE = 0
    RETURN = 2
    PREPAYMENT = 3


class ReceiptSubType(IntEnum):
    SALE = 1
    PARTIAL_PAYMENT = 2
    PREPAYMENT_USAGE = 3
    RETURN_SALE = 4
    RETURN_PARTIAL_PAYMENT = 5
    RETURN_PREPAYMENT = 6


class DiscountType(IntEnum):
    PERCENT = 1
    PRICE = 2
    TOTAL = 4


class AdditionalDiscountType(IntEnum):
    PERCENT = 8
    PRICE = 16

