# e-hdm

`e-hdm` is an open source Python client for the Armenian electronic HDM API described in the April 2026 integration manual.

It covers the full documented API surface:

- `checkConnection`
- `activate`
- `configureDepartments`
- `getGoodList`
- `print`
- `printCopy`
- `getReturnedReceiptInfo`
- `printReturnReceipt`

## Features

- Sync and async clients
- Mutual TLS support
- `Decimal` for money fields
- Typed request/response models
- Client-side validation for documented constraints
- Domain-specific exceptions with original API payloads attached

## Installation

```bash
pip install e-hdm
```

## Quick start

```python
from decimal import Decimal

from e_hdm import (
    DepartmentConfig,
    EHDMClient,
    Language,
    PrintMode,
    ProductReceiptItem,
    ProductReceiptRequest,
    TaxRegime,
)

client = EHDMClient(
    crn="52014201",
    base_url="https://ecrm.taxservice.am/taxsystem-rs-vcr",
    cert="/path/to/client.crt",
    key="/path/to/client.key",
    verify="/path/to/ca-root.crt",
    language=Language.HY,
)

client.check_connection()
client.activate()

client.configure_departments(
    [
        DepartmentConfig(dep=1, tax_regime=TaxRegime.VAT),
        DepartmentConfig(dep=2, tax_regime=TaxRegime.NO_VAT),
    ]
)

goods = client.get_good_list(tax_regime=TaxRegime.VAT, tin="00493113")

receipt = client.print_receipt(
    ProductReceiptRequest(
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
        emarks=[
            "04859996301235j8FdgGkUmp3Z2N2",
        ],
    )
)

copy = client.print_copy(receipt.receipt_id)
```

## Notes

- The API requires HTTPS with a registered certificate.
- The `crn` in every request must match the certificate-bound CRN.
- Returned timestamps are UTC-based epoch milliseconds.
- Money uses `Decimal` throughout the library.

