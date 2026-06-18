from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any, Generic, TypeVar

from .enums import AdditionalDiscountType, DiscountType, PrintMode, ReceiptSubType, ReceiptType, SaleType, TaxRegime
from .utils import clean_none, ensure_scale, quantize_money, quantize_quantity, to_decimal

T = TypeVar("T")


@dataclass(slots=True)
class APIResponse(Generic[T]):
    code: int
    message: str
    result: T | None = None
    error_message: str | None = None


@dataclass(slots=True)
class DepartmentConfig:
    dep: int
    tax_regime: TaxRegime

    def to_payload(self) -> dict[str, Any]:
        return {"dep": self.dep, "taxRegime": int(self.tax_regime)}


@dataclass(slots=True)
class Good:
    good_name: str
    good_code: str
    price: Decimal

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "Good":
        return cls(
            good_name=payload["goodName"],
            good_code=payload["goodCode"],
            price=to_decimal(payload["price"]),
        )


@dataclass(slots=True)
class GoodsList:
    list_name: str
    tax_regime_name: str
    goods: list[Good]

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "GoodsList":
        return cls(
            list_name=payload["listname"],
            tax_regime_name=payload["taxRegimeName"],
            goods=[Good.from_dict(item) for item in payload.get("goods", [])],
        )


@dataclass(slots=True)
class GoodsListResult:
    good_lists: list[GoodsList]

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "GoodsListResult":
        return cls(good_lists=[GoodsList.from_dict(item) for item in payload.get("goodLists", [])])


@dataclass(slots=True)
class ProductReceiptItem:
    adg_code: str
    dep: int
    good_code: str
    good_name: str
    quantity: Decimal
    unit: str
    price: Decimal
    additional_discount: Decimal | None = None
    additional_discount_type: AdditionalDiscountType = AdditionalDiscountType.PRICE
    discount: Decimal | None = None
    discount_type: DiscountType = DiscountType.PERCENT

    def __post_init__(self) -> None:
        self.quantity = to_decimal(self.quantity)
        self.price = to_decimal(self.price)
        ensure_scale(self.quantity, 3, "quantity")
        ensure_scale(self.price, 2, "price")
        if self.quantity <= 0:
            raise ValueError("quantity must be greater than zero")
        if self.price <= 0:
            raise ValueError("price must be greater than zero")
        if self.additional_discount is not None:
            self.additional_discount = to_decimal(self.additional_discount)
            ensure_scale(self.additional_discount, 2, "additional_discount")
        if self.discount is not None:
            self.discount = to_decimal(self.discount)
            ensure_scale(self.discount, 2, "discount")

    def to_payload(self) -> dict[str, Any]:
        payload = {
            "adgCode": self.adg_code,
            "dep": self.dep,
            "goodCode": self.good_code,
            "goodName": self.good_name,
            "quantity": quantize_quantity(self.quantity),
            "unit": self.unit,
            "price": quantize_money(self.price),
        }
        if self.additional_discount is not None:
            payload["additionalDiscount"] = quantize_money(self.additional_discount)
            payload["additionalDiscountType"] = int(self.additional_discount_type)
        if self.discount is not None:
            payload["discount"] = quantize_money(self.discount)
            payload["discountType"] = int(self.discount_type)
        return clean_none(payload)


@dataclass(slots=True)
class ProductReceiptRequest:
    card_amount: Decimal
    cash_amount: Decimal
    partial_amount: Decimal
    pre_payment_amount: Decimal
    cashier_id: int
    items: list[ProductReceiptItem]
    partner_tin: str | None = None
    emarks: list[str] = field(default_factory=list)
    mode: PrintMode = field(init=False, default=PrintMode.PRODUCTS)

    def __post_init__(self) -> None:
        self.card_amount = to_decimal(self.card_amount)
        self.cash_amount = to_decimal(self.cash_amount)
        self.partial_amount = to_decimal(self.partial_amount)
        self.pre_payment_amount = to_decimal(self.pre_payment_amount)
        if not self.items:
            raise ValueError("items are required for product receipts")
        for name in ("card_amount", "cash_amount", "partial_amount", "pre_payment_amount"):
            ensure_scale(getattr(self, name), 2, name)
        _validate_partner_tin(self.partner_tin)
        _validate_emarks(self.emarks)

    def to_payload(self) -> dict[str, Any]:
        return clean_none(
            {
                "cardAmount": quantize_money(self.card_amount),
                "cashAmount": quantize_money(self.cash_amount),
                "partialAmount": quantize_money(self.partial_amount),
                "prePaymentAmount": quantize_money(self.pre_payment_amount),
                "cashierId": self.cashier_id,
                "mode": int(self.mode),
                "partnerTin": self.partner_tin,
                "items": [item.to_payload() for item in self.items],
                "emarks": self.emarks or None,
            }
        )


@dataclass(slots=True)
class PrepaymentReceiptRequest:
    card_amount: Decimal
    cash_amount: Decimal
    partial_amount: Decimal
    pre_payment_amount: Decimal
    cashier_id: int
    partner_tin: str | None = None
    mode: PrintMode = field(init=False, default=PrintMode.PREPAYMENT)

    def __post_init__(self) -> None:
        self.card_amount = to_decimal(self.card_amount)
        self.cash_amount = to_decimal(self.cash_amount)
        self.partial_amount = to_decimal(self.partial_amount)
        self.pre_payment_amount = to_decimal(self.pre_payment_amount)
        for name in ("card_amount", "cash_amount", "partial_amount", "pre_payment_amount"):
            ensure_scale(getattr(self, name), 2, name)
        _validate_partner_tin(self.partner_tin)

    def to_payload(self) -> dict[str, Any]:
        return clean_none(
            {
                "cardAmount": quantize_money(self.card_amount),
                "cashAmount": quantize_money(self.cash_amount),
                "partialAmount": quantize_money(self.partial_amount),
                "prePaymentAmount": quantize_money(self.pre_payment_amount),
                "cashierId": self.cashier_id,
                "mode": int(self.mode),
                "partnerTin": self.partner_tin,
                "items": None,
            }
        )


@dataclass(slots=True)
class ReceiptSummary:
    receipt_id: str
    crn: str
    sn: str
    tin: str
    taxpayer: str
    address: str
    time: int
    total: Decimal
    change: Decimal
    emark_count: int
    emark_verification_code: str
    qr: str
    fiscal: str | None = None

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "ReceiptSummary":
        count_value = payload.get("emarkCount", payload.get("emarkAccount", 0))
        return cls(
            receipt_id=str(payload["receiptId"]),
            crn=payload["crn"],
            sn=payload["sn"],
            tin=payload["tin"],
            taxpayer=payload["taxpayer"],
            address=payload["address"],
            time=int(payload["time"]),
            total=to_decimal(payload["total"]),
            change=to_decimal(payload["change"]),
            emark_count=int(count_value),
            emark_verification_code=payload["emarkVerificationCode"],
            qr=payload["qr"],
            fiscal=payload.get("fiscal"),
        )


PrintReceiptResult = ReceiptSummary
ReceiptCopyResult = ReceiptSummary


@dataclass(slots=True)
class ReturnedReceiptItem:
    receipt_product_id: int
    quantity: Decimal
    additional_discount: Decimal | None
    additional_discount_type: int | None
    dep: int
    discount: Decimal | None
    discount_type: int | None
    vat: Decimal
    tax_regime: int
    good_code: str
    good_name: str
    adg_code: str
    unit: str
    price: Decimal
    total_without_taxes: Decimal
    total_with_taxes: Decimal

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "ReturnedReceiptItem":
        return cls(
            receipt_product_id=int(payload["receiptProductId"]),
            quantity=to_decimal(payload["quantity"]),
            additional_discount=to_decimal(payload["additionalDiscount"]) if payload.get("additionalDiscount") is not None else None,
            additional_discount_type=payload.get("additionalDiscountType"),
            dep=int(payload["dep"]),
            discount=to_decimal(payload["discount"]) if payload.get("discount") is not None else None,
            discount_type=payload.get("discountType"),
            vat=to_decimal(payload["vat"]),
            tax_regime=int(payload["taxRegime"]),
            good_code=payload["goodCode"],
            good_name=payload["goodName"],
            adg_code=payload["adgCode"],
            unit=payload["unit"],
            price=to_decimal(payload["price"]),
            total_without_taxes=to_decimal(payload["totalWithoutTaxes"]),
            total_with_taxes=to_decimal(payload["totalWithTaxes"]),
        )


@dataclass(slots=True)
class ReturnReceiptInfo:
    cashier_id: int
    card_amount: Decimal
    cash_amount: Decimal
    partner_tin: str | None
    partial_amount: Decimal
    pre_payment: Decimal
    sale_type: SaleType
    receipt_type: ReceiptType
    receipt_sub_type: ReceiptSubType
    total_amount: Decimal
    time: int
    items: list[ReturnedReceiptItem]
    emarks: list[str]

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "ReturnReceiptInfo":
        return cls(
            cashier_id=int(payload["cashierId"]),
            card_amount=to_decimal(payload["cardAmount"]),
            cash_amount=to_decimal(payload["cashAmount"]),
            partner_tin=payload.get("partnerTin"),
            partial_amount=to_decimal(payload["partialAmount"]),
            pre_payment=to_decimal(payload["prePayment"]),
            sale_type=SaleType(payload["saleType"]),
            receipt_type=ReceiptType(payload["receiptType"]),
            receipt_sub_type=ReceiptSubType(payload["receiptSubType"]),
            total_amount=to_decimal(payload["totalAmount"]),
            time=int(payload["time"]),
            items=[ReturnedReceiptItem.from_dict(item) for item in payload.get("items", [])],
            emarks=list(payload.get("emarks", [])),
        )

    def build_full_return(self, card_amount: Decimal, cash_amount: Decimal, pre_payment_amount: Decimal = Decimal("0.00")) -> "ReturnReceiptRequest":
        return ReturnReceiptRequest(
            receipt_id="",
            source_crn="",
            card_amount_for_return=card_amount,
            cash_amount_for_return=cash_amount,
            pre_payment_amount_for_return=pre_payment_amount,
            return_item_list=[
                ReturnReceiptItem(receipt_product_id=item.receipt_product_id, quantity=item.quantity)
                for item in self.items
            ],
            emarks=self.emarks,
        )


@dataclass(slots=True)
class ReturnReceiptItem:
    receipt_product_id: int
    quantity: Decimal

    def __post_init__(self) -> None:
        self.quantity = to_decimal(self.quantity)
        ensure_scale(self.quantity, 3, "quantity")
        if self.quantity <= 0:
            raise ValueError("quantity must be greater than zero")

    def to_payload(self) -> dict[str, Any]:
        return {
            "receiptProductId": self.receipt_product_id,
            "quantity": quantize_quantity(self.quantity),
        }


@dataclass(slots=True)
class ReturnReceiptRequest:
    receipt_id: str
    source_crn: str
    card_amount_for_return: Decimal
    cash_amount_for_return: Decimal
    pre_payment_amount_for_return: Decimal
    return_item_list: list[ReturnReceiptItem]
    emarks: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        self.card_amount_for_return = to_decimal(self.card_amount_for_return)
        self.cash_amount_for_return = to_decimal(self.cash_amount_for_return)
        self.pre_payment_amount_for_return = to_decimal(self.pre_payment_amount_for_return)
        for name in ("card_amount_for_return", "cash_amount_for_return", "pre_payment_amount_for_return"):
            ensure_scale(getattr(self, name), 2, name)
        if not self.return_item_list:
            raise ValueError("return_item_list is required")
        _validate_emarks(self.emarks)

    def to_payload(self) -> dict[str, Any]:
        return clean_none(
            {
                "receiptId": self.receipt_id,
                "sourceCrn": self.source_crn,
                "cardAmountForReturn": quantize_money(self.card_amount_for_return),
                "cashAmountForReturn": quantize_money(self.cash_amount_for_return),
                "prePaymentAmountForReturn": quantize_money(self.pre_payment_amount_for_return),
                "returnItemList": [item.to_payload() for item in self.return_item_list],
                "emarks": self.emarks or None,
            }
        )


def _validate_partner_tin(value: str | None) -> None:
    if value is None:
        return
    if not (len(value) == 8 and value.isdigit()):
        raise ValueError("partner_tin must be an 8-digit TIN or None")


def _validate_emarks(values: list[str]) -> None:
    for value in values:
        if not (29 <= len(value) <= 128):
            raise ValueError("each emark must be between 29 and 128 characters")

