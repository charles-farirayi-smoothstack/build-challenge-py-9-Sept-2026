from pathlib import Path

import pytest

from sales import SalesDataError, SalesDataLoader

FIXTURE_CANDIDATES = [
    "../../data/v5/challenge-4/sales.csv",
    "data/v5/challenge-4/sales.csv",
]


def find_fixture() -> Path:
    for candidate in FIXTURE_CANDIDATES:
        path = Path(candidate)
        if path.exists():
            return path
    raise RuntimeError(f"Could not locate sales.csv fixture for tests; tried: {FIXTURE_CANDIDATES}")


@pytest.fixture
def loader():
    return SalesDataLoader()


def test_load_missing_file_raises_clean_sales_data_error(loader):
    missing = Path("this/path/does/not/exist/sales.csv")
    with pytest.raises(SalesDataError) as exc_info:
        loader.load(missing)
    message = str(exc_info.value)
    assert "not found" in message
    assert "sales.csv" in message


def test_load_real_fixture_finds_expected_valid_and_malformed_counts(loader):
    fixture = find_fixture()
    result = loader.load(fixture)

    # The fixture has 99 data rows total: 93 valid transactions and 6 intentionally malformed
    # rows (TXN9001-TXN9006), verified by direct inspection of the file.
    assert result.valid_count == 93
    assert result.malformed_count == 6
    assert result.valid_count + result.malformed_count == 99


def test_load_real_fixture_malformed_rows_include_expected_transaction_ids(loader):
    fixture = find_fixture()
    result = loader.load(fixture)

    malformed_raw = [m.raw_line for m in result.malformed_rows]
    for expected_id in ["TXN9001", "TXN9002", "TXN9003", "TXN9004", "TXN9005", "TXN9006"]:
        assert any(line.startswith(expected_id) for line in malformed_raw), (
            f"Expected a malformed row starting with {expected_id}"
        )


def test_load_empty_file_returns_empty_result(loader, tmp_path):
    empty = tmp_path / "empty.csv"
    empty.write_text("")
    result = loader.load(empty)
    assert result.valid_count == 0
    assert result.malformed_count == 0


def test_load_header_only_returns_empty_result(loader, tmp_path):
    header_only = tmp_path / "header_only.csv"
    header_only.write_text(
        "transactionId,date,region,salesperson,productCategory,quantity,unitPrice,totalAmount\n"
    )
    result = loader.load(header_only)
    assert result.valid_count == 0
    assert result.malformed_count == 0


def test_load_mix_of_valid_and_malformed_rows_partitions_correctly(loader, tmp_path):
    csv_file = tmp_path / "mini.csv"
    content = "\n".join(
        [
            "transactionId,date,region,salesperson,productCategory,quantity,unitPrice,totalAmount",
            "T1,2024-01-01,NORTH,Alice,TOYS,1,10.00,10.00",
            "T2,not-a-date,NORTH,Alice,TOYS,1,10.00,10.00",
            "T3,2024-01-02,NORTH,Alice,TOYS,abc,10.00,10.00",
            "T4,2024-01-03,NORTH,Alice,TOYS,1,10.00",  # missing column
            "T5,2024-01-04,NORTH,Alice,TOYS,1,$10.00,10.00",
            "",
        ]
    )
    csv_file.write_text(content)

    result = loader.load(csv_file)
    assert result.valid_count == 1
    assert result.malformed_count == 4
    assert result.records[0].transaction_id == "T1"


def test_load_none_path_raises_sales_data_error(loader):
    with pytest.raises(SalesDataError):
        loader.load(None)
