from __future__ import annotations

import asyncio
import json
import ssl
import unittest
import urllib.error
from dataclasses import dataclass
from decimal import Decimal
from unittest.mock import patch

import e_hdm
from e_hdm import (
    APIResponse,
    AsyncEHDMClient,
    DepartmentConfig,
    EHDMAPIError,
    EHDMClient,
    EHDMError,
    EHDMTransportError,
    GoodsListResult,
    Language,
    PrepaymentReceiptRequest,
    PrintMode,
    PrintReceiptResult,
    ProductReceiptItem,
    ProductReceiptRequest,
    ReceiptCopyResult,
    ReceiptSubType,
    ReceiptType,
    ReturnReceiptInfo,
    ReturnReceiptItem,
    ReturnReceiptRequest,
    SaleType,
    TaxRegime,
)
from e_hdm.enums import AdditionalDiscountType, DiscountType
from e_hdm.exceptions import EHDMAPIError as DirectAPIError
from e_hdm.models import Good, GoodsList, ReceiptSummary, ReturnedReceiptItem
from e_hdm.transport import SSLConfig, SyncTransport
from e_hdm.utils import clean_none, ensure_scale, quantize_money, quantize_quantity, timestamp_ms_to_datetime, to_decimal


class FakeTransport:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []

    def post_json(self, url, headers, payload):
        self.calls.append({"url": url, "headers": headers, "payload": payload})
        return self.responses.pop(0)


class DummyResponse:
    def __init__(self, payload: str):
        self._payload = payload.encode("utf-8")

    def read(self):
        return self._payload

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


@dataclass
class DummyData:
    status: Language
    amount: Decimal


class ExportTests(unittest.TestCase):
    def test_package_exports_expected_symbols(self):
        self.assertIs(e_hdm.EHDMClient, EHDMClient)
        self.assertIs(e_hdm.AsyncEHDMClient, AsyncEHDMClient)
        self.assertIs(e_hdm.EHDMError, EHDMError)
        self.assertIs(e_hdm.EHDMTransportError, EHDMTransportError)
        self.assertIs(e_hdm.EHDMAPIError, DirectAPIError)
        self.assertIn("ReturnReceiptRequest", e_hdm.__all__)
        self.assertIn("GoodsListResult", e_hdm.__all__)


class UtilsTests(unittest.TestCase):
    def test_to_decimal_handles_decimal_and_str(self):
        value = Decimal("1.23")
        self.assertIs(to_decimal(value), value)
        self.assertEqual(to_decimal("2.50"), Decimal("2.50"))

    def test_quantizers_and_scale_checks(self):
        self.assertEqual(quantize_money("1.005"), Decimal("1.01"))
        self.assertEqual(quantize_quantity("1.2346"), Decimal("1.235"))
        ensure_scale(Decimal("1.23"), 2, "amount")
        with self.assertRaises(ValueError):
            ensure_scale(Decimal("1.234"), 2, "amount")

    def test_timestamp_conversion(self):
        dt = timestamp_ms_to_datetime(0)
        self.assertEqual(dt.isoformat(), "1970-01-01T00:00:00+00:00")

    def test_clean_none_handles_enum_decimal_dataclass_dict_list_and_passthrough(self):
        payload = {
            "status": Language.EN,
            "amount": Decimal("1.20"),
            "nested": DummyData(status=Language.HY, amount=Decimal("2.30")),
            "items": [Language.RU, Decimal("3.40"), None, {"x": None, "y": Decimal("4.50")}],
            "ignore": None,
        }
        cleaned = clean_none(payload)
        self.assertEqual(
            cleaned,
            {
                "status": "en",
                "amount": "1.20",
                "nested": {"status": "hy", "amount": "2.30"},
                "items": ["ru", "3.40", None, {"y": "4.50"}],
            },
        )
        self.assertEqual(clean_none("plain"), "plain")


class ModelTests(unittest.TestCase):
    def test_department_config_to_payload(self):
        self.assertEqual(
            DepartmentConfig(dep=1, tax_regime=TaxRegime.VAT).to_payload(),
            {"dep": 1, "taxRegime": 1},
        )

    def test_good_and_goods_list_parsing(self):
        good = Good.from_dict({"goodName": "A", "goodCode": "1", "price": "12.50"})
        self.assertEqual(good.price, Decimal("12.50"))
        goods_list = GoodsList.from_dict({"listname": "List", "taxRegimeName": "VAT", "goods": []})
        self.assertEqual(goods_list.list_name, "List")
        result = GoodsListResult.from_dict({"goodLists": [{"listname": "L", "taxRegimeName": "VAT", "goods": []}]})
        self.assertEqual(len(result.good_lists), 1)

    def test_product_receipt_item_payload_with_discounts(self):
        item = ProductReceiptItem(
            adg_code="9205",
            dep=1,
            good_code="9205-13",
            good_name="երգեհոն",
            quantity=Decimal("2.000"),
            unit="հատ",
            price=Decimal("25000.00"),
            additional_discount=Decimal("1000.00"),
            additional_discount_type=AdditionalDiscountType.PRICE,
            discount=Decimal("10.00"),
            discount_type=DiscountType.PERCENT,
        )
        payload = item.to_payload()
        self.assertEqual(payload["additionalDiscountType"], 16)
        self.assertEqual(payload["discountType"], 1)

    def test_product_receipt_item_validation_errors(self):
        with self.assertRaises(ValueError):
            ProductReceiptItem(
                adg_code="9205",
                dep=1,
                good_code="9205-13",
                good_name="երգեհոն",
                quantity=Decimal("0.000"),
                unit="հատ",
                price=Decimal("1.00"),
            )
        with self.assertRaises(ValueError):
            ProductReceiptItem(
                adg_code="9205",
                dep=1,
                good_code="9205-13",
                good_name="երգեհոն",
                quantity=Decimal("1.000"),
                unit="հատ",
                price=Decimal("0.00"),
            )
        with self.assertRaises(ValueError):
            ProductReceiptItem(
                adg_code="9205",
                dep=1,
                good_code="9205-13",
                good_name="երգեհոն",
                quantity=Decimal("1.000"),
                unit="հատ",
                price=Decimal("1.001"),
            )
        with self.assertRaises(ValueError):
            ProductReceiptItem(
                adg_code="9205",
                dep=1,
                good_code="9205-13",
                good_name="երգեհոն",
                quantity=Decimal("1.000"),
                unit="հատ",
                price=Decimal("1.00"),
                additional_discount=Decimal("0.001"),
            )
        with self.assertRaises(ValueError):
            ProductReceiptItem(
                adg_code="9205",
                dep=1,
                good_code="9205-13",
                good_name="երգեհոն",
                quantity=Decimal("1.000"),
                unit="հատ",
                price=Decimal("1.00"),
                discount=Decimal("0.001"),
            )

    def test_product_receipt_request_validation_and_payload(self):
        item = ProductReceiptItem(
            adg_code="9205",
            dep=1,
            good_code="9205-13",
            good_name="երգեհոն",
            quantity=Decimal("2.000"),
            unit="հատ",
            price=Decimal("25000.00"),
        )
        request = ProductReceiptRequest(
            card_amount=Decimal("40000.00"),
            cash_amount=Decimal("0.00"),
            partial_amount=Decimal("0.00"),
            pre_payment_amount=Decimal("4000.00"),
            cashier_id=3,
            partner_tin="00493113",
            items=[item],
            emarks=["04859996301235j8FdgGkUmp3Z2N2"],
        )
        payload = request.to_payload()
        self.assertEqual(payload["mode"], PrintMode.PRODUCTS)
        self.assertEqual(payload["partnerTin"], "00493113")
        self.assertEqual(payload["cardAmount"], "40000.00")
        with self.assertRaises(ValueError):
            ProductReceiptRequest(
                card_amount=Decimal("1.001"),
                cash_amount=Decimal("0.00"),
                partial_amount=Decimal("0.00"),
                pre_payment_amount=Decimal("0.00"),
                cashier_id=1,
                items=[item],
            )
        with self.assertRaises(ValueError):
            ProductReceiptRequest(
                card_amount=Decimal("1.00"),
                cash_amount=Decimal("0.00"),
                partial_amount=Decimal("0.00"),
                pre_payment_amount=Decimal("0.00"),
                cashier_id=1,
                items=[],
            )

    def test_prepayment_request_validation_and_payload(self):
        request = PrepaymentReceiptRequest(
            card_amount=Decimal("1.00"),
            cash_amount=Decimal("2.00"),
            partial_amount=Decimal("3.00"),
            pre_payment_amount=Decimal("4.00"),
            cashier_id=1,
            partner_tin=None,
        )
        payload = request.to_payload()
        self.assertEqual(payload["mode"], PrintMode.PREPAYMENT)
        self.assertNotIn("items", payload)
        with self.assertRaises(ValueError):
            PrepaymentReceiptRequest(
                card_amount=Decimal("1.00"),
                cash_amount=Decimal("2.000"),
                partial_amount=Decimal("3.00"),
                pre_payment_amount=Decimal("4.00"),
                cashier_id=1,
            )
        with self.assertRaises(ValueError):
            PrepaymentReceiptRequest(
                card_amount=Decimal("1.00"),
                cash_amount=Decimal("2.00"),
                partial_amount=Decimal("3.00"),
                pre_payment_amount=Decimal("4.00"),
                cashier_id=1,
                partner_tin="123",
            )

    def test_receipt_summary_parses_emark_count_and_emark_account(self):
        first = ReceiptSummary.from_dict(
            {
                "receiptId": "8",
                "crn": "52014201",
                "sn": "SN",
                "tin": "00493113",
                "taxpayer": "Test",
                "address": "Addr",
                "time": 1,
                "total": "10.00",
                "change": "1.00",
                "emarkCount": "2",
                "emarkVerificationCode": "ABC",
                "qr": "QR",
                "fiscal": "F",
            }
        )
        second = ReceiptSummary.from_dict(
            {
                "receiptId": "9",
                "crn": "52014201",
                "sn": "SN",
                "tin": "00493113",
                "taxpayer": "Test",
                "address": "Addr",
                "time": 1,
                "total": "10.00",
                "change": "1.00",
                "emarkAccount": "3",
                "emarkVerificationCode": "ABC",
                "qr": "QR",
            }
        )
        self.assertEqual(first.fiscal, "F")
        self.assertEqual(second.emark_count, 3)
        self.assertIsNone(second.fiscal)

    def test_returned_receipt_item_parsing_with_optional_discounts(self):
        item = ReturnedReceiptItem.from_dict(
            {
                "receiptProductId": 0,
                "quantity": "2.000",
                "additionalDiscount": "1.00",
                "additionalDiscountType": 16,
                "dep": 1,
                "discount": "2.00",
                "discountType": 1,
                "vat": "16.67",
                "taxRegime": 1,
                "goodCode": "9205-13",
                "goodName": "երգեհոն",
                "adgCode": "9205",
                "unit": "հատ",
                "price": "25000.00",
                "totalWithoutTaxes": "36665.20",
                "totalWithTaxes": "44000.00",
            }
        )
        self.assertEqual(item.additional_discount, Decimal("1.00"))
        without_optionals = ReturnedReceiptItem.from_dict(
            {
                "receiptProductId": 0,
                "quantity": "2.000",
                "dep": 1,
                "vat": "16.67",
                "taxRegime": 1,
                "goodCode": "9205-13",
                "goodName": "երգեհոն",
                "adgCode": "9205",
                "unit": "հատ",
                "price": "25000.00",
                "totalWithoutTaxes": "36665.20",
                "totalWithTaxes": "44000.00",
            }
        )
        self.assertIsNone(without_optionals.additional_discount)
        self.assertIsNone(without_optionals.discount)

    def test_return_receipt_info_parsing_and_helper(self):
        info = ReturnReceiptInfo.from_dict(
            {
                "cashierId": 3,
                "cardAmount": "40000.00",
                "cashAmount": "0.00",
                "partnerTin": None,
                "partialAmount": "0.00",
                "prePayment": "4000.00",
                "saleType": 2,
                "receiptType": 0,
                "receiptSubType": 3,
                "totalAmount": "44000.00",
                "time": 1721140445000,
                "items": [
                    {
                        "receiptProductId": 0,
                        "quantity": "2.000",
                        "dep": 1,
                        "vat": "16.67",
                        "taxRegime": 1,
                        "goodCode": "9205-13",
                        "goodName": "երգեհոն",
                        "adgCode": "9205",
                        "unit": "հատ",
                        "price": "25000.00",
                        "totalWithoutTaxes": "36665.20",
                        "totalWithTaxes": "44000.00",
                    }
                ],
                "emarks": ["04859996301235j8FdgGkUmp3Z2N2"],
            }
        )
        self.assertEqual(info.sale_type, SaleType.PRODUCTS)
        self.assertEqual(info.receipt_type, ReceiptType.SALE)
        self.assertEqual(info.receipt_sub_type, ReceiptSubType.PREPAYMENT_USAGE)
        full_return = info.build_full_return(Decimal("1.00"), Decimal("0.00"))
        self.assertEqual(full_return.return_item_list[0].receipt_product_id, 0)
        self.assertEqual(full_return.emarks, info.emarks)

    def test_return_receipt_item_and_request_validation(self):
        item = ReturnReceiptItem(receipt_product_id=0, quantity=Decimal("1.000"))
        self.assertEqual(item.to_payload()["quantity"], Decimal("1.000"))
        request = ReturnReceiptRequest(
            receipt_id="8",
            source_crn="52014223",
            card_amount_for_return=Decimal("22000.00"),
            cash_amount_for_return=Decimal("0.00"),
            pre_payment_amount_for_return=Decimal("0.00"),
            return_item_list=[item],
            emarks=["04859996301235j8FdgGkUmp3Z2N2"],
        )
        payload = request.to_payload()
        self.assertEqual(payload["receiptId"], "8")
        with self.assertRaises(ValueError):
            ReturnReceiptItem(receipt_product_id=0, quantity=Decimal("0.000"))
        with self.assertRaises(ValueError):
            ReturnReceiptRequest(
                receipt_id="8",
                source_crn="52014223",
                card_amount_for_return=Decimal("1.001"),
                cash_amount_for_return=Decimal("0.00"),
                pre_payment_amount_for_return=Decimal("0.00"),
                return_item_list=[item],
            )
        with self.assertRaises(ValueError):
            ReturnReceiptRequest(
                receipt_id="8",
                source_crn="52014223",
                card_amount_for_return=Decimal("1.00"),
                cash_amount_for_return=Decimal("0.00"),
                pre_payment_amount_for_return=Decimal("0.00"),
                return_item_list=[],
            )
        with self.assertRaises(ValueError):
            ReturnReceiptRequest(
                receipt_id="8",
                source_crn="52014223",
                card_amount_for_return=Decimal("1.00"),
                cash_amount_for_return=Decimal("0.00"),
                pre_payment_amount_for_return=Decimal("0.00"),
                return_item_list=[item],
                emarks=["short"],
            )


class ClientTests(unittest.TestCase):
    def setUp(self):
        self.summary_payload = {
            "receiptId": "8",
            "crn": "52014201",
            "sn": "2FECD1F8",
            "tin": "00493113",
            "taxpayer": "Test",
            "address": "Yerevan",
            "time": 1721140445000,
            "fiscal": "52517829",
            "total": "44000.00",
            "change": "0.00",
            "emarkCount": "1",
            "emarkVerificationCode": "23568974",
            "qr": "QR",
        }

    def test_check_connection_injects_crn_and_language(self):
        transport = FakeTransport([{"code": 0, "message": "OK", "result": "ready"}])
        client = EHDMClient(
            crn="52014201",
            base_url="https://example.test/",
            language=Language.EN,
            transport=transport,
        )
        result = client.check_connection()
        self.assertEqual(result, "ready")
        self.assertEqual(transport.calls[0]["payload"]["crn"], "52014201")
        self.assertEqual(transport.calls[0]["headers"]["language"], "en")
        self.assertEqual(transport.calls[0]["url"], "https://example.test/api/v1.0/checkConnection")

    def test_activate_and_configure_departments(self):
        transport = FakeTransport(
            [
                {"code": 0, "message": "OK", "result": "activated"},
                {"code": 0, "message": "OK", "result": "configured"},
            ]
        )
        client = EHDMClient(crn="52014201", base_url="https://example.test", transport=transport)
        self.assertEqual(client.activate(), "activated")
        self.assertEqual(
            client.configure_departments([DepartmentConfig(dep=1, tax_regime=TaxRegime.VAT)]),
            "configured",
        )

    def test_get_good_list_parses_result(self):
        transport = FakeTransport(
            [
                {
                    "code": 0,
                    "message": "OK",
                    "result": {
                        "goodLists": [
                            {
                                "listname": "List",
                                "taxRegimeName": "VAT",
                                "goods": [{"goodName": "A", "goodCode": "1", "price": 12.5}],
                            }
                        ]
                    },
                }
            ]
        )
        client = EHDMClient(crn="52014201", base_url="https://example.test", transport=transport)
        result = client.get_good_list(TaxRegime.VAT, "00493113")
        self.assertEqual(result.good_lists[0].goods[0].price, Decimal("12.5"))

    def test_print_receipt_product_and_prepayment_and_copy(self):
        transport = FakeTransport(
            [
                {"code": 0, "message": "OK", "result": self.summary_payload},
                {"code": 0, "message": "OK", "result": self.summary_payload},
                {"code": 0, "message": "OK", "result": self.summary_payload},
            ]
        )
        client = EHDMClient(crn="52014201", base_url="https://example.test", transport=transport)
        product_request = ProductReceiptRequest(
            card_amount=Decimal("40000.00"),
            cash_amount=Decimal("0.00"),
            partial_amount=Decimal("0.00"),
            pre_payment_amount=Decimal("4000.00"),
            cashier_id=3,
            partner_tin=None,
            items=[
                ProductReceiptItem(
                    adg_code="9205",
                    dep=1,
                    good_code="9205-13",
                    good_name="երգեհոն",
                    quantity=Decimal("2.000"),
                    unit="հատ",
                    price=Decimal("25000.00"),
                    additional_discount=Decimal("1000.00"),
                )
            ],
            emarks=["04859996301235j8FdgGkUmp3Z2N2"],
        )
        prepayment_request = PrepaymentReceiptRequest(
            card_amount=Decimal("2000.00"),
            cash_amount=Decimal("0.00"),
            partial_amount=Decimal("0.00"),
            pre_payment_amount=Decimal("0.00"),
            cashier_id=3,
            partner_tin=None,
        )
        result = client.print_receipt(product_request)
        prepayment_result = client.print_receipt(prepayment_request)
        copy_result = client.print_copy(8)
        self.assertIsInstance(result, PrintReceiptResult)
        self.assertIsInstance(prepayment_result, PrintReceiptResult)
        self.assertIsInstance(copy_result, ReceiptCopyResult)

    def test_get_returned_receipt_info_and_print_return_receipt(self):
        transport = FakeTransport(
            [
                {
                    "code": 0,
                    "message": "OK",
                    "result": {
                        "cashierId": 3,
                        "cardAmount": "40000.00",
                        "cashAmount": "0.00",
                        "partnerTin": None,
                        "partialAmount": "0.00",
                        "prePayment": "4000.00",
                        "saleType": 2,
                        "receiptType": 0,
                        "receiptSubType": 3,
                        "totalAmount": "44000.00",
                        "time": 1721140445000,
                        "items": [
                            {
                                "receiptProductId": 0,
                                "quantity": "2.000",
                                "dep": 1,
                                "vat": "16.67",
                                "taxRegime": 1,
                                "goodCode": "9205-13",
                                "goodName": "երգեհոն",
                                "adgCode": "9205",
                                "unit": "հատ",
                                "price": "25000.00",
                                "totalWithoutTaxes": "36665.20",
                                "totalWithTaxes": "44000.00",
                            }
                        ],
                        "emarks": ["04859996301235j8FdgGkUmp3Z2N2"],
                    },
                },
                {"code": 0, "message": "OK", "result": self.summary_payload},
            ]
        )
        client = EHDMClient(crn="52014201", base_url="https://example.test", transport=transport)
        info = client.get_returned_receipt_info(8, "52014223")
        result = client.print_return_receipt(
            ReturnReceiptRequest(
                receipt_id="8",
                source_crn="52014223",
                card_amount_for_return=Decimal("22000.00"),
                cash_amount_for_return=Decimal("0.00"),
                pre_payment_amount_for_return=Decimal("0.00"),
                return_item_list=[ReturnReceiptItem(receipt_product_id=0, quantity=Decimal("1.000"))],
                emarks=["04859996301235j8FdgGkUmp3Z2N2"],
            )
        )
        self.assertIsInstance(info, ReturnReceiptInfo)
        self.assertIsInstance(result, PrintReceiptResult)

    def test_post_json_and_error_branch(self):
        transport = FakeTransport(
            [
                {"code": 0, "message": "OK", "result": {"hello": "world"}},
                {"code": 195, "message": "CRM_ACTIVATION_FAILED", "errorMessage": "failed"},
            ]
        )
        client = EHDMClient(crn="52014201", base_url="https://example.test", transport=transport)
        response = client.post_json("/custom", {"x": 1})
        self.assertIsInstance(response, APIResponse)
        self.assertEqual(response.result["hello"], "world")
        with self.assertRaises(EHDMAPIError) as ctx:
            client.activate()
        self.assertEqual(str(ctx.exception), "[195] CRM_ACTIVATION_FAILED: failed")
        self.assertEqual(ctx.exception.payload["message"], "CRM_ACTIVATION_FAILED")

    def test_empty_result_paths_return_empty_string_or_empty_model(self):
        transport = FakeTransport(
            [
                {"code": 0, "message": "OK", "result": None},
                {"code": 0, "message": "OK", "result": None},
            ]
        )
        client = EHDMClient(crn="52014201", base_url="https://example.test", transport=transport)
        self.assertEqual(client.check_connection(), "")
        self.assertEqual(client.get_good_list(TaxRegime.VAT, "00493113").good_lists, [])


class AsyncClientTests(unittest.TestCase):
    def setUp(self):
        self.summary_payload = {
            "receiptId": "8",
            "crn": "52014201",
            "sn": "2FECD1F8",
            "tin": "00493113",
            "taxpayer": "Test",
            "address": "Yerevan",
            "time": 1721140445000,
            "fiscal": "52517829",
            "total": "44000.00",
            "change": "0.00",
            "emarkCount": "1",
            "emarkVerificationCode": "23568974",
            "qr": "QR",
        }

    def test_async_client_all_wrappers(self):
        transport = FakeTransport(
            [
                {"code": 0, "message": "OK", "result": "ready"},
                {"code": 0, "message": "OK", "result": "activated"},
                {"code": 0, "message": "OK", "result": "configured"},
                {"code": 0, "message": "OK", "result": {"goodLists": []}},
                {"code": 0, "message": "OK", "result": self.summary_payload},
                {"code": 0, "message": "OK", "result": self.summary_payload},
                {
                    "code": 0,
                    "message": "OK",
                    "result": {
                        "cashierId": 3,
                        "cardAmount": "40000.00",
                        "cashAmount": "0.00",
                        "partnerTin": None,
                        "partialAmount": "0.00",
                        "prePayment": "4000.00",
                        "saleType": 2,
                        "receiptType": 0,
                        "receiptSubType": 3,
                        "totalAmount": "44000.00",
                        "time": 1721140445000,
                        "items": [],
                        "emarks": [],
                    },
                },
                {"code": 0, "message": "OK", "result": self.summary_payload},
            ]
        )
        client = AsyncEHDMClient(
            crn="52014201",
            base_url="https://example.test",
            transport=transport,
        )

        async def run():
            self.assertEqual(await client.check_connection(), "ready")
            self.assertEqual(await client.activate(), "activated")
            self.assertEqual(
                await client.configure_departments([DepartmentConfig(dep=1, tax_regime=TaxRegime.VAT)]),
                "configured",
            )
            self.assertEqual((await client.get_good_list(TaxRegime.VAT, "00493113")).good_lists, [])
            await client.print_receipt(
                ProductReceiptRequest(
                    card_amount=Decimal("1.00"),
                    cash_amount=Decimal("0.00"),
                    partial_amount=Decimal("0.00"),
                    pre_payment_amount=Decimal("0.00"),
                    cashier_id=1,
                    items=[
                        ProductReceiptItem(
                            adg_code="9205",
                            dep=1,
                            good_code="9205-13",
                            good_name="երգեհոն",
                            quantity=Decimal("1.000"),
                            unit="հատ",
                            price=Decimal("1.00"),
                        )
                    ],
                )
            )
            await client.print_copy(8)
            await client.get_returned_receipt_info(8, "52014223")
            await client.print_return_receipt(
                ReturnReceiptRequest(
                    receipt_id="8",
                    source_crn="52014223",
                    card_amount_for_return=Decimal("1.00"),
                    cash_amount_for_return=Decimal("0.00"),
                    pre_payment_amount_for_return=Decimal("0.00"),
                    return_item_list=[ReturnReceiptItem(receipt_product_id=0, quantity=Decimal("1.000"))],
                )
            )

        asyncio.run(run())


class TransportTests(unittest.TestCase):
    def test_ssl_config_builds_verified_context_without_cafile(self):
        sentinel = ssl.create_default_context()
        with patch("e_hdm.transport.ssl.create_default_context", return_value=sentinel) as mock_create:
            context = SSLConfig(verify=True).build_context()
        self.assertIs(context, sentinel)
        mock_create.assert_called_once_with(cafile=None)

    def test_ssl_config_builds_verified_context_with_cafile_and_loads_cert_chain(self):
        class Context:
            def __init__(self):
                self.loaded = None

            def load_cert_chain(self, certfile, keyfile):
                self.loaded = (certfile, keyfile)

        context = Context()
        with patch("e_hdm.transport.ssl.create_default_context", return_value=context) as mock_create:
            built = SSLConfig(cert="client.crt", key="client.key", verify="ca.crt").build_context()
        self.assertIs(built, context)
        self.assertEqual(context.loaded, ("client.crt", "client.key"))
        mock_create.assert_called_once_with(cafile="ca.crt")

    def test_ssl_config_builds_unverified_context(self):
        sentinel = object()
        with patch("e_hdm.transport.ssl._create_unverified_context", return_value=sentinel) as mock_create:
            context = SSLConfig(verify=False).build_context()
        self.assertIs(context, sentinel)
        mock_create.assert_called_once()

    def test_sync_transport_success_json_error_and_url_error(self):
        transport = SyncTransport(SSLConfig())
        with patch.object(SSLConfig, "build_context", return_value=object()):
            with patch("e_hdm.transport.urllib.request.urlopen", return_value=DummyResponse(json.dumps({"ok": 1}))):
                result = transport.post_json("https://example.test", {"A": "B"}, {"x": "y"})
                self.assertEqual(result, {"ok": 1})

        with patch.object(SSLConfig, "build_context", return_value=object()):
            with patch("e_hdm.transport.urllib.request.urlopen", return_value=DummyResponse("not-json")):
                with self.assertRaises(EHDMTransportError) as ctx:
                    transport.post_json("https://example.test", {"A": "B"}, {"x": "y"})
                self.assertIn("Invalid JSON response", str(ctx.exception))

        with patch.object(SSLConfig, "build_context", return_value=object()):
            with patch(
                "e_hdm.transport.urllib.request.urlopen",
                side_effect=urllib.error.URLError("boom"),
            ):
                with self.assertRaises(EHDMTransportError) as ctx:
                    transport.post_json("https://example.test", {"A": "B"}, {"x": "y"})
                self.assertIn("boom", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
