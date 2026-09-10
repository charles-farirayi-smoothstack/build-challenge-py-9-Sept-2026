"""Functional-style analysis over a collection of SaleRecord objects.

Every method here favors functional techniques over manual accumulation loops: list/dict
comprehensions, generator expressions, ``map``/``filter``, ``functools.reduce``,
``itertools.groupby`` (over pre-sorted data), and ``collections.defaultdict``/``Counter``.

Convention: :meth:`SalesAnalyzer.get_sales_by_date_range` treats both endpoints as **inclusive**
(``from_date <= record.date <= to_date``). This mirrors the Java implementation and is pinned
down by unit tests.
"""

from __future__ import annotations

import statistics
from collections import defaultdict
from datetime import date
from functools import reduce
from itertools import groupby
from typing import Dict, List, Optional, Sequence

from .models import SaleRecord, SalespersonTotal


class SalesAnalyzer:
    def __init__(self, records: Sequence[SaleRecord]):
        self._records: List[SaleRecord] = list(records)

    @property
    def records(self) -> List[SaleRecord]:
        return list(self._records)

    # ------------------------------------------------------------------
    # Rule 1: Filtering by date range, region, or category
    # ------------------------------------------------------------------

    def get_sales_by_date_range(self, from_date: date, to_date: date) -> List[SaleRecord]:
        """Inclusive on both ends: ``from_date <= date <= to_date``."""
        if from_date is None or to_date is None:
            raise ValueError("from_date and to_date must not be None")
        filtered = filter(lambda r: from_date <= r.date <= to_date, self._records)
        return sorted(filtered, key=lambda r: r.date)

    def get_sales_by_region(self, region: str) -> List[SaleRecord]:
        return [r for r in self._records if r.region.casefold() == region.casefold()]

    def get_sales_by_category(self, category: str) -> List[SaleRecord]:
        return [r for r in self._records if r.product_category.casefold() == category.casefold()]

    # ------------------------------------------------------------------
    # Rule 2: Grouping by multiple dimensions
    # ------------------------------------------------------------------

    def get_total_sales_by_region(self) -> Dict[str, float]:
        totals: Dict[str, float] = defaultdict(float)
        for r in self._records:
            totals[r.region] += r.total_amount
        return dict(sorted(totals.items()))

    def get_average_sale_by_category(self) -> Dict[str, float]:
        buckets: Dict[str, List[float]] = defaultdict(list)
        for r in self._records:
            buckets[r.product_category].append(r.total_amount)
        return {category: statistics.fmean(amounts) for category, amounts in sorted(buckets.items())}

    def get_total_sales_by_region_and_category(self) -> Dict[str, Dict[str, float]]:
        """Groups by region, then by product category, summing totalAmount within each cell.

        Uses itertools.groupby over data pre-sorted by (region, category), as recommended for
        the grouping guidance in the spec.
        """
        by_region: Dict[str, Dict[str, float]] = {}
        sorted_records = sorted(self._records, key=lambda r: (r.region, r.product_category))
        for region, region_group in groupby(sorted_records, key=lambda r: r.region):
            region_records = list(region_group)
            by_category: Dict[str, float] = {}
            for category, category_group in groupby(
                sorted(region_records, key=lambda r: r.product_category),
                key=lambda r: r.product_category,
            ):
                by_category[category] = sum(r.total_amount for r in category_group)
            by_region[region] = dict(sorted(by_category.items()))
        return dict(sorted(by_region.items()))

    def get_monthly_sales_trend(self) -> Dict[str, float]:
        """Chronological "yyyy-mm" -> total sales for that month."""
        totals: Dict[str, float] = defaultdict(float)
        for r in self._records:
            month_key = f"{r.date.year:04d}-{r.date.month:02d}"
            totals[month_key] += r.total_amount
        return dict(sorted(totals.items()))

    # ------------------------------------------------------------------
    # Rule 3: Totals and statistics
    # ------------------------------------------------------------------

    def get_grand_total(self) -> float:
        return reduce(lambda acc, r: acc + r.total_amount, self._records, 0.0)

    def get_total_amount_statistics(self) -> Dict[str, float]:
        amounts = [r.total_amount for r in self._records]
        if not amounts:
            return {"count": 0, "min": 0.0, "max": 0.0, "sum": 0.0, "average": 0.0}
        return {
            "count": len(amounts),
            "min": min(amounts),
            "max": max(amounts),
            "sum": sum(amounts),
            "average": statistics.fmean(amounts),
        }

    def get_statistics_by_region(self) -> Dict[str, Dict[str, float]]:
        buckets: Dict[str, List[float]] = defaultdict(list)
        for r in self._records:
            buckets[r.region].append(r.total_amount)
        return {
            region: {
                "count": len(amounts),
                "min": min(amounts),
                "max": max(amounts),
                "sum": sum(amounts),
                "average": statistics.fmean(amounts),
            }
            for region, amounts in sorted(buckets.items())
        }

    # ------------------------------------------------------------------
    # Rule 4: Identifying top performers
    # ------------------------------------------------------------------

    def get_top_salespersons(self, n: int) -> List[SalespersonTotal]:
        """Top ``n`` salespersons by total sales amount, descending. Ties are broken by
        salesperson name ascending for a deterministic ordering. Non-positive ``n`` returns an
        empty list; ``n`` larger than the number of distinct salespersons returns all of them.
        """
        if n <= 0:
            return []

        buckets: Dict[str, List[SaleRecord]] = defaultdict(list)
        for r in self._records:
            buckets[r.salesperson].append(r)

        totals = [
            SalespersonTotal(
                salesperson=name,
                total_sales=sum(r.total_amount for r in recs),
                transaction_count=len(recs),
            )
            for name, recs in buckets.items()
        ]
        totals.sort(key=lambda t: (-t.total_sales, t.salesperson))
        return totals[:n]

    def get_top_region_by_total_sales(self) -> Optional[str]:
        totals = self.get_total_sales_by_region()
        if not totals:
            return None
        return max(totals.items(), key=lambda kv: kv[1])[0]

    # ------------------------------------------------------------------
    # Summary report
    # ------------------------------------------------------------------

    def generate_summary_report(self) -> str:
        lines: List[str] = []
        lines.append("===== Sales Summary Report =====")
        lines.append(f"Total transactions analyzed: {len(self._records)}")
        lines.append(f"Grand total sales: {self.get_grand_total():.2f}")

        stats = self.get_total_amount_statistics()
        lines.append(
            "Per-transaction amount stats: "
            f"min={stats['min']:.2f}, max={stats['max']:.2f}, "
            f"avg={stats['average']:.2f}, count={stats['count']}"
        )

        lines.append("")
        lines.append("-- Total Sales by Region --")
        lines.extend(
            f"  {region:<10} {total:10.2f}" for region, total in self.get_total_sales_by_region().items()
        )

        lines.append("")
        lines.append("-- Average Sale by Category --")
        lines.extend(
            f"  {category:<12} {avg:10.2f}"
            for category, avg in self.get_average_sale_by_category().items()
        )

        lines.append("")
        lines.append("-- Monthly Sales Trend --")
        lines.extend(
            f"  {month:<8} {total:10.2f}" for month, total in self.get_monthly_sales_trend().items()
        )

        lines.append("")
        lines.append("-- Top 5 Salespersons --")
        lines.extend(
            f"  {sp.salesperson:<18} total={sp.total_sales:10.2f}  transactions={sp.transaction_count}"
            for sp in self.get_top_salespersons(5)
        )

        top_region = self.get_top_region_by_total_sales()
        if top_region is not None:
            lines.append("")
            lines.append(f"Top region by total sales: {top_region}")

        lines.append("=================================")
        return "\n".join(lines) + "\n"
