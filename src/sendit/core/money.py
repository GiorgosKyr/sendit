"""Money handling.

Rule: ``Decimal`` at the API boundary, integer minor units (cents) everywhere inside and in the
database. Floats are never used for money because they cannot represent 0.10 exactly.
"""

from decimal import Decimal
from typing import Annotated

from pydantic import Field

MINOR_UNITS_PER_MAJOR = 100
_TWO_PLACES = Decimal("0.01")

# Reusable DTO field type: strictly positive, at most 2 decimal places. Pydantic parses JSON
# strings like "100.50" straight into Decimal without ever going through a float.
Amount = Annotated[Decimal, Field(gt=0, max_digits=15, decimal_places=2)]


def to_minor_units(amount: Decimal) -> int:
    """``Decimal("12.34")`` -> ``1234``. Rejects anything finer than a cent instead of rounding."""
    scaled = amount * MINOR_UNITS_PER_MAJOR
    if scaled != scaled.to_integral_value():
        raise ValueError(f"{amount} has more than 2 decimal places")
    return int(scaled)


def to_decimal(minor_units: int) -> Decimal:
    """``1234`` -> ``Decimal("12.34")``, always rendered with two decimal places."""
    return (Decimal(minor_units) / MINOR_UNITS_PER_MAJOR).quantize(_TWO_PLACES)
