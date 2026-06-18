from __future__ import annotations

import asyncio

from .client import EHDMClient
from .enums import TaxRegime
from .models import (
    DepartmentConfig,
    GoodsListResult,
    PrepaymentReceiptRequest,
    PrintReceiptResult,
    ProductReceiptRequest,
    ReceiptCopyResult,
    ReturnReceiptInfo,
    ReturnReceiptRequest,
)


class AsyncEHDMClient:
    def __init__(self, *args, **kwargs) -> None:
        self._client = EHDMClient(*args, **kwargs)

    async def check_connection(self) -> str:
        return await asyncio.to_thread(self._client.check_connection)

    async def activate(self) -> str:
        return await asyncio.to_thread(self._client.activate)

    async def configure_departments(self, departments: list[DepartmentConfig]) -> str:
        return await asyncio.to_thread(self._client.configure_departments, departments)

    async def get_good_list(self, tax_regime: TaxRegime, tin: str) -> GoodsListResult:
        return await asyncio.to_thread(self._client.get_good_list, tax_regime, tin)

    async def print_receipt(self, request: ProductReceiptRequest | PrepaymentReceiptRequest) -> PrintReceiptResult:
        return await asyncio.to_thread(self._client.print_receipt, request)

    async def print_copy(self, receipt_id: str | int) -> ReceiptCopyResult:
        return await asyncio.to_thread(self._client.print_copy, receipt_id)

    async def get_returned_receipt_info(self, receipt_id: str | int, source_crn: str) -> ReturnReceiptInfo:
        return await asyncio.to_thread(self._client.get_returned_receipt_info, receipt_id, source_crn)

    async def print_return_receipt(self, request: ReturnReceiptRequest) -> PrintReceiptResult:
        return await asyncio.to_thread(self._client.print_return_receipt, request)

