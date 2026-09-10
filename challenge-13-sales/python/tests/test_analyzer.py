from datetime import date

import pytest

from sales import SaleRecord, SalesAnalyzer


def rec(txn_id, iso_date, region, salesperson, category, qty, unit_price, total):
    return SaleRecord(
        transaction_id=txn_id,
        date=date.fromisoformat(iso_date),
        region=region,
        salesperson=salesperson,
        product_category=category,
        quantity=qty,
        unit_price=unit_price,
        total_amount=total,
    )


@pytest.fixture
def analyzer():
    fixture = [
        rec("T1", "2024-01-05", "NORTH", "Alice", "TOYS", 1, 10.00, 10.00),
        rec("T2", "2024-01-15", "NORTH", "Alice", "TOYS", 2, 10.00, 20.00),
        rec("T3", "2024-01-20", "SOUTH", "Bob", "ELECTRONICS", 1, 100.00, 100.00),
        rec("T4", "2024-02-01", "SOUTH", "Bob", "ELECTRONICS", 1, 200.00, 200.00),
        rec("T5", "2024-02-10", "SOUTH", "Carla", "TOYS", 3, 5.00, 15.00),
        rec("T6", "2024-02-15", "NORTH", "Alice", "ELECTRONICS", 1, 50.00, 50.00),
    ]
    return SalesAnalyzer(fixture)


def test_total_sales_by_region_sums_per_region(analyzer):
    by_region = analyzer.get_total_sales_by_region()
    assert by_region["NORTH"] == pytest.approx(80.00)
    assert by_region["SOUTH"] == pytest.approx(315.00)
    assert len(by_region) == 2


def test_total_sales_by_region_empty_dataset_is_empty_map():
    empty = SalesAnalyzer([])
    assert empty.get_total_sales_by_region() == {}


def test_total_sales_by_region_missing_region_not_present(analyzer):
    assert "WEST" not in analyzer.get_total_sales_by_region()


def test_average_sale_by_category_computes_mean(analyzer):
    avg = analyzer.get_average_sale_by_category()
    assert avg["TOYS"] == pytest.approx(15.0)  # (10+20+15)/3
    assert avg["ELECTRONICS"] == pytest.approx(350.0 / 3.0)  # (100+200+50)/3


def test_top_salespersons_orders_by_total_descending(analyzer):
    top = analyzer.get_top_salespersons(2)
    assert len(top) == 2
    assert top[0].salesperson == "Bob"
    assert top[0].total_sales == pytest.approx(300.0)
    assert top[1].salesperson == "Alice"
    assert top[1].total_sales == pytest.approx(80.0)


def test_top_salespersons_n_larger_than_available_returns_all(analyzer):
    top = analyzer.get_top_salespersons(100)
    assert len(top) == 3


def test_top_salespersons_non_positive_n_returns_empty(analyzer):
    assert analyzer.get_top_salespersons(0) == []
    assert analyzer.get_top_salespersons(-5) == []


def test_top_salespersons_tie_broken_by_name_ascending():
    tied = [
        rec("A1", "2024-01-01", "NORTH", "Zed", "TOYS", 1, 100.0, 100.0),
        rec("A2", "2024-01-02", "NORTH", "Amy", "TOYS", 1, 100.0, 100.0),
    ]
    top = SalesAnalyzer(tied).get_top_salespersons(2)
    assert top[0].salesperson == "Amy"
    assert top[1].salesperson == "Zed"


def test_monthly_sales_trend_groups_by_year_month(analyzer):
    trend = analyzer.get_monthly_sales_trend()
    assert trend["2024-01"] == pytest.approx(130.00)  # T1+T2+T3 = 10+20+100
    assert trend["2024-02"] == pytest.approx(265.00)  # T4+T5+T6 = 200+15+50
    assert len(trend) == 2


def test_date_range_is_inclusive_on_both_ends(analyzer):
    result = analyzer.get_sales_by_date_range(date(2024, 1, 5), date(2024, 1, 15))
    assert len(result) == 2


def test_date_range_excludes_just_outside_boundary(analyzer):
    result = analyzer.get_sales_by_date_range(date(2024, 1, 6), date(2024, 1, 14))
    assert result == []


def test_date_range_single_day_boundary_includes_exact_match(analyzer):
    result = analyzer.get_sales_by_date_range(date(2024, 1, 5), date(2024, 1, 5))
    assert len(result) == 1
    assert result[0].transaction_id == "T1"


def test_sales_by_region_and_category_filter_correctly(analyzer):
    assert len(analyzer.get_sales_by_region("north")) == 3
    assert len(analyzer.get_sales_by_category("toys")) == 3


def test_total_sales_by_region_and_category_groups_by_both_dimensions(analyzer):
    grouped = analyzer.get_total_sales_by_region_and_category()
    assert grouped["NORTH"]["TOYS"] == pytest.approx(30.00)
    assert grouped["NORTH"]["ELECTRONICS"] == pytest.approx(50.00)
    assert grouped["SOUTH"]["ELECTRONICS"] == pytest.approx(300.00)
    assert grouped["SOUTH"]["TOYS"] == pytest.approx(15.00)


def test_grand_total_sums_all_transactions(analyzer):
    assert analyzer.get_grand_total() == pytest.approx(395.00)


def test_total_amount_statistics_reports_min_max_avg_count(analyzer):
    stats = analyzer.get_total_amount_statistics()
    assert stats["count"] == 6
    assert stats["min"] == pytest.approx(10.0)
    assert stats["max"] == pytest.approx(200.0)


def test_generate_summary_report_contains_key_sections(analyzer):
    report = analyzer.generate_summary_report()
    assert "Sales Summary Report" in report
    assert "Total Sales by Region" in report
    assert "Top 5 Salespersons" in report or "Bob" in report


def test_top_region_by_total_sales_returns_highest_total(analyzer):
    assert analyzer.get_top_region_by_total_sales() == "SOUTH"


def test_top_region_by_total_sales_empty_dataset_returns_none():
    assert SalesAnalyzer([]).get_top_region_by_total_sales() is None
