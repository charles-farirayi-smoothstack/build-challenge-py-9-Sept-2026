# Challenge 7: Marina Berth Reservation and Billing

Two standalone implementations of the same spec: fit vessels to berths, prevent
overlapping reservations, and invoice stays with seasonal, power, and overstay
pricing.

- `java/` — Maven project, Java 17+, JUnit 5
- `python/` — plain package, pytest

Both implementations share identical business rules and produce the same demo
output (6 berths / 2 docks, 4 vessels, 6 reservations covering a peak-boundary
stay, an overstay, an overlap rejection, and a vessel that fits nothing).

## Java

From `challenge-07-marina/java/`:

```bash
# Run the test suite
mvn test

# Run the demo (prints berths, vessels, reservations, and itemized invoices)
mvn -q compile exec:java
```

`mvn package` also produces a runnable jar at `target/marina.jar` with `marina.Main`
as its main class (`java -jar target/marina.jar`).

## Python

Requires only `pytest` (`pip install pytest` if not already installed).

From `challenge-07-marina/python/`:

```bash
# Run the test suite
pytest

# Run the demo
python3 main.py
```

`pytest.ini` sets `pythonpath = .` so the `marina` package is importable without
installing it — `pytest` and `python3 main.py` both work directly from this
directory with no extra setup.

## Notes on the trickier rules

- **Seasonal pricing is per night, not per reservation.** Each calendar night in
  a stay is priced individually: 1.5x the base rate if that night falls in
  June/July/August, otherwise the plain base rate. A stay spanning the peak
  boundary (e.g. 30 May to 2 June) is billed at mixed rates on a single
  invoice — this is the worked example in the spec (`$336.00`, not `3 x $96`).
- **Half-open reservation ranges.** `[arrival, departure)` — a departure on day
  N and an arrival on day N for a different reservation do not conflict; an
  overlap of even a single shared night is rejected.
- **Overstay billing never reduces the bill.** The reserved nights are always
  charged in full. Only if `actualDeparture` is strictly after the reserved
  `departureDate` are extra "overstay" lines added, one per overstayed night,
  each at 2x that night's base rate, plus a normal-rate power surcharge line
  for that night if power was requested. Departing early charges the full
  reserved-night total with no overstay lines and no discount.
- **Per-line rounding.** Every line (base-rate, power-surcharge, overstay) is
  rounded to 2 decimal places half-up individually, and the invoice total is
  the sum of those already-rounded lines — not a rounding of an unrounded
  running total.
