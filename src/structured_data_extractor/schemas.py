import re
from datetime import date, datetime
from decimal import Decimal
from typing import Annotated, Literal, Self

from pydantic import (
    BaseModel,
    BeforeValidator,
    ConfigDict,
    Field,
    field_validator,
    model_validator,
)


def clean_money(value):
    """Convert amounts like '$1,249.50' into '1249.50'."""
    if isinstance(value, bool):
        raise ValueError("Money cannot be True or False")

    if isinstance(value, str):
        value = value.strip()
        value = re.sub(r"[$€£]", "", value)
        value = value.replace(",", "").strip()

    return value


Money = Annotated[
    Decimal,
    BeforeValidator(clean_money),
    Field(ge=0, allow_inf_nan=False, max_digits=14, decimal_places=2),
]

TOLERANCE = Decimal("0.02")


class LineItem(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    description: str = Field(min_length=1)
    quantity: int = Field(gt=0, strict=True)
    unit_price: Money = Field(gt=0)
    line_total: Money

    @model_validator(mode="after")
    def check_line_total(self) -> Self:
        expected = self.quantity * self.unit_price

        if abs(expected - self.line_total) > TOLERANCE:
            raise ValueError(
                f"Line total should be {expected}, "
                f"but received {self.line_total}"
            )

        return self


class InvoiceExtraction(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    invoice_number: str = Field(
        min_length=1,
        max_length=100,
        pattern=r"^[A-Za-z0-9][A-Za-z0-9._/-]*$",
    )
    vendor_name: str = Field(min_length=1)
    invoice_date: date
    line_items: list[LineItem] = Field(min_length=1)
    subtotal: Money
    tax_amount: Money
    total_amount: Money
    currency: Literal["USD", "EUR", "GBP"]

    @field_validator("invoice_date", mode="before")
    @classmethod
    def clean_date(cls, value):
        if not isinstance(value, str):
            return value

        value = value.strip()
        value = re.sub(r"(\d{1,2})(st|nd|rd|th)\b", r"\1", value)
        value = value.replace(" of ", " ")

        for date_format in (
            "%Y-%m-%d",
            "%d %b, %Y",
            "%d %B, %Y",
            "%B %d, %Y",
        ):
            try:
                return datetime.strptime(value, date_format).date()
            except ValueError:
                continue

        raise ValueError("Use YYYY-MM-DD or a date like 12th of Oct, 2024")

    @model_validator(mode="after")
    def check_invoice_totals(self) -> Self:
        items_total = sum(
            (item.line_total for item in self.line_items),
            Decimal("0"),
        )

        if abs(items_total - self.subtotal) > TOLERANCE:
            raise ValueError(
                f"Subtotal should be {items_total}, "
                f"but received {self.subtotal}"
            )

        expected_total = items_total + self.tax_amount

        if abs(expected_total - self.total_amount) > TOLERANCE:
            raise ValueError(
                f"Invoice total should be {expected_total}, "
                f"but received {self.total_amount}"
            )

        return self