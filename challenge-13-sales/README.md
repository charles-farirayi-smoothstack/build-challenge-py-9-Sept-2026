# Build Challenge 13: Sales Data Analysis

Two standalone, parallel implementations of the same sales analytics tool over the fixture at
`data/v5/challenge-4/sales.csv` (relative to the repository root, i.e.
`../../data/v5/challenge-4/sales.csv` from either project directory):

- `java/` — Maven project, Java 17, JUnit 5, implemented with the Streams API.
- `python/` — plain-Python package, pytest, implemented with comprehensions/`itertools`/
  `functools.reduce`/`collections.defaultdict`.

Both expose the same three classes/roles (`SaleRecord`, `SalesDataLoader`, `SalesAnalyzer`) and
the same analysis methods, and both produce numerically identical output against the fixture.

## Fixture row-count findings

`sales.csv` has 100 lines: 1 header + 99 data rows. Direct inspection (and both loaders'
real-CSV tests) confirm:

- **93 valid transactions**
- **6 intentionally malformed rows**, each with transaction id `TXN9001`–`TXN9006`:

| Line | Transaction | Problem |
|------|-------------|---------|
| 11 | TXN9001 | Only 6 columns (missing `unitPrice`, `totalAmount`) |
| 29 | TXN9002 | `quantity` is the text `"two"`, not a number |
| 46 | TXN9003 | `unitPrice` is `"$18.25"` — a currency symbol, not a plain decimal |
| 63 | TXN9004 | `date` is `"15/04/2024"` (DD/MM/YYYY) instead of ISO `yyyy-MM-dd` |
| 80 | TXN9005 | `quantity` and `totalAmount` are blank |
| 94 | TXN9006 | 9 columns — an extra trailing `EXTRA` field |

Both the Java and Python loaders identify exactly these six rows as malformed (verified by a
dedicated test in each suite that loads the real file), and both report the same aggregate
figures — e.g. grand total sales `110447.57` across the 93 valid rows.

## Parsing decisions (apply to both implementations)

- **Numbers/dates are parsed strictly.** `"$18.25"`, `"two"`, and `"15/04/2024"` are treated as
  malformed rather than silently cleaned/coerced (e.g. stripping `$`), since the tool has no way
  to know whether that's the full extent of the corruption in that row. This is a deliberate,
  documented choice — going the other way (best-effort cleaning) is also defensible, but would
  hide data-quality problems from the report.
- **Wrong column count is malformed**, whether too few (TXN9001) or too many (TXN9006).
- **Malformed rows never abort the load.** Each row is parsed independently; failures are
  collected as `(line number, raw line, reason)` and the load continues. A CSV with 0 valid rows
  (e.g. header-only, or entirely malformed) still loads successfully, and returns an empty
  record list.
- **A missing/unreadable file is a hard failure**, but a clean one: `SalesDataException` (Java)
  / `SalesDataError` (Python) is raised with a clear "file not found" message and the file path,
  not a raw stack trace/traceback. `Main`/`main.py` catch this and print a one-line error instead
  of letting an exception escape.
- **Date range filtering (`getSalesByDateRange` / `get_sales_by_date_range`) is inclusive on
  both ends**: `fromDate <= date <= toDate`. This is called out explicitly because "range" is
  otherwise ambiguous, and is pinned down by boundary tests in both suites (a same-day range, a
  range that just misses the fixture dates by one day, etc.).
- **Top-N ties are broken by salesperson name, ascending**, so `getTopSalespersons`/
  `get_top_salespersons` is fully deterministic even when totals tie exactly.
- Region and category values are normalized to upper case on load (`north` → `NORTH`), and
  region/category filter methods compare case-insensitively, so callers don't need to know the
  on-disk casing convention.

## Running the Java project

```bash
cd challenge-13-sales/java
mvn test                       # run the JUnit 5 suite
mvn -q package -DskipTests \
  && java -cp target/classes com.buildchallenge.sales.Main   # run the demo against the real fixture
```

The demo resolves the CSV path in this order: first CLI arg, then `SALES_CSV_PATH` env var,
then a few relative-path candidates (works whether run from `java/` or the repo root). You can
also pass an explicit path, e.g.:

```bash
java -cp target/classes com.buildchallenge.sales.Main /absolute/path/to/sales.csv
```

Result at time of writing: **25 tests, all passing** (`mvn test`).

## Running the Python project

```bash
cd challenge-13-sales/python
python3 -m pip install pytest    # only needed once, if pytest isn't already installed
python3 -m pytest                # run the pytest suite
python3 main.py                  # run the demo against the real fixture
```

Path resolution mirrors the Java demo (CLI arg, then `SALES_CSV_PATH`, then relative
candidates); you may also do `python3 main.py /absolute/path/to/sales.csv`.

Result at time of writing: **26 tests, all passing** (`pytest`).

No third-party dependencies are required for the Python implementation (pandas is *not* used —
the spec allows but does not require it, and plain comprehensions/`itertools`/`functools`/
`collections` cover every requirement).

## Test coverage notes

Both suites include:

- In-memory fixture tests pinning down exact aggregation/grouping numbers by hand (region
  totals, category averages, monthly trend, region×category cross-tab).
- Top-N tie-breaking (two salespersons with identical totals — result must be alphabetical).
- Empty-region / empty-dataset behavior (no crash, empty map/list).
- Date-range boundary tests: inclusive same-day range, and a range that excludes dates just
  outside the boundary by one day.
- A test that loads the **real fixture** and asserts the actual observed counts: 93 valid, 6
  malformed, 99 total — plus a check that all six expected `TXN900x` ids are the ones flagged.
- A file-not-found test asserting a clean, descriptive exception (not a raw stack trace).
- Malformed-CSV edge cases built from small temp files: empty file, header-only file, and a
  mixed file exercising each of the four "shapes" of malformed row (bad date, bad number, wrong
  column count, currency-formatted number).
