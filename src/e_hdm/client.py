from __future__ import annotations

from typing import Any

from .enums import Language, TaxRegime
from .exceptions import EHDMAPIError
from .models import (
    APIResponse,
    DepartmentConfig,
    GoodsListResult,
    PrepaymentReceiptRequest,
    PrintReceiptResult,
    ProductReceiptRequest,
    ReceiptCopyResult,
    ReturnReceiptInfo,
    ReturnReceiptRequest,
)
from .transport import SSLConfig, SyncTransport


class EHDMClient:
    def __init__(
        self,
        crn: str,
        base_url: str,
        cert: str | None = None,
        key: str | None = None,
        verify: str | bool | None = True,
        language: Language = Language.HY,
        transport: SyncTransport | None = None,
    ) -> None:
        self.crn = crn
        self.base_url = base_url.rstrip("/")
        self.language = language
        self._transport = transport or SyncTransport(SSLConfig(cert=cert, key=key, verify=verify))

    def check_connection(self) -> str:
        return self._post("/api/v1.0/checkConnection", {}).result or ""

    def activate(self) -> str:
        return self._post("/api/v1.0/activate", {}).result or ""

    def configure_departments(self, departments: list[DepartmentConfig]) -> str:
        payload = {"departments": [item.to_payload() for item in departments]}
        return self._post("/api/v1.0/configureDepartments", payload).result or ""

    def get_good_list(self, tax_regime: TaxRegime, tin: str) -> GoodsListResult:
        response = self._post("/api/v1.0/getGoodList", {"taxRegime": int(tax_regime), "tin": tin})
        return GoodsListResult.from_dict(response.result or {})

    def print_receipt(self, request: ProductReceiptRequest | PrepaymentReceiptRequest) -> PrintReceiptResult:
        response = self._post("/api/v1.0/print", request.to_payload())
        return PrintReceiptResult.from_dict(response.result or {})

    def print_copy(self, receipt_id: str | int) -> ReceiptCopyResult:
        response = self._post("/api/v1.0/printCopy", {"receiptId": str(receipt_id)})
        return ReceiptCopyResult.from_dict(response.result or {})

    def get_returned_receipt_info(self, receipt_id: str | int, source_crn: str) -> ReturnReceiptInfo:
        response = self._post(
            "/api/v1.0/getReturnedReceiptInfo",
            {"receiptId": str(receipt_id), "sourceCrn": source_crn},
        )
        return ReturnReceiptInfo.from_dict(response.result or {})

    def print_return_receipt(self, request: ReturnReceiptRequest) -> PrintReceiptResult:
        response = self._post("/api/v1.0/printReturnReceipt", request.to_payload())
        return PrintReceiptResult.from_dict(response.result or {})

    def post_json(self, path: str, payload: dict[str, Any]) -> APIResponse[dict[str, Any]]:
        return self._post(path, payload)

    def _post(self, path: str, payload: dict[str, Any]) -> APIResponse[Any]:
        merged_payload = {"crn": self.crn, **payload}
        raw = self._transport.post_json(
            url=f"{self.base_url}{path}",
            headers={
                "Content-Type": "application/json; charset=utf-8",
                "Accept": "application/json",
                "language": self.language.value,
            },
            payload=merged_payload,
        )
        response = APIResponse(
            code=int(raw["code"]),
            message=raw["message"],
            result=raw.get("result"),
            error_message=raw.get("errorMessage"),
        )
        if response.code != 0:
            raise EHDMAPIError(
                code=response.code,
                message=response.message,
                error_message=response.error_message,
                payload=raw,
            )
        return response

