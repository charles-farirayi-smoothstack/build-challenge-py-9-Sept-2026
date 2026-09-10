"""Sales data analysis package (Build Challenge 13).

Exposes SaleRecord, SalesDataLoader, SalesAnalyzer, and supporting types.
"""

from .models import SaleRecord, MalformedRow, SalesDataLoadResult, SalespersonTotal
from .exceptions import SalesDataError
from .loader import SalesDataLoader
from .analyzer import SalesAnalyzer

__all__ = [
    "SaleRecord",
    "MalformedRow",
    "SalesDataLoadResult",
    "SalespersonTotal",
    "SalesDataError",
    "SalesDataLoader",
    "SalesAnalyzer",
]
