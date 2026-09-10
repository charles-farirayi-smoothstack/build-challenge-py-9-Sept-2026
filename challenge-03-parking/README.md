# Build Challenge 3: Municipal Parking Permits and Citations

Two independent, standalone implementations of the same spec: a Java (Maven / JUnit 5)
project and a Python (pytest) package. Both implement the same rules, model classes,
and `ParkingAuthority` methods; both ship a runnable demo and a full unit test suite,
including the worked appeal-pause escalation example (citation issued 1 March, appealed
10 March, resolved UPHELD 30 March, penalty applied 11 April).

## Layout

```
challenge-03-parking/
  java/     Maven project (Java 17+, JUnit 5)
  python/   pip-installable package (pytest)
```

## Java

Requires Java 17+ and Maven.

```bash
cd challenge-03-parking/java
mvn test                                        # run the unit tests
mvn -q exec:java -Dexec.mainClass=com.parking.Main   # run the demo
```

`mvn test` runs the 22 JUnit 5 tests in
`src/test/java/com/parking/ParkingAuthorityTest.java`, covering zone/permit legality,
violation priority, permit expiry (including the 29 February rollover), appeals
(including the day-14/day-15 boundary), payments (including overpayment rejection),
and escalation (including the worked appeal-pause example and idempotency).

## Python

Requires Python 3.9+ and `pytest` (`pip install pytest`).

```bash
cd challenge-03-parking/python
pytest                 # run the unit tests
python3 main.py        # run the demo
```

`pytest` runs the 22 tests in `tests/test_authority.py`, mirroring the Java suite
exactly (same scenarios, same worked example, same edge cases).

## What the demo shows

Both `Main`/`main.py` demos:

1. Register 5 vehicles.
2. Issue 4 permits (2 RESIDENT, 2 ACCESSIBLE), including one issued on 29 February 2024
   to show the expiry rollover to 28 February 2025.
3. Evaluate a few clearly legal observations (no citation issued).
4. Evaluate 10 observations that each issue a citation, covering all three violation
   codes (BLOCKING_HYDRANT, NO_PERMIT, EXPIRED_METER).
5. File and resolve two appeals — one UPHELD, one DISMISSED — plus a rejected day-15
   appeal.
6. Make one partial payment and demonstrate a rejected overpayment.
7. Run escalation, showing the 21-day/50% penalty being applied, and run it again on
   the same date to prove it does not double-apply.

## Notable judgment calls (spec is otherwise implemented literally)

- **Both permit types are annual** (issuedOn/expiresOn with the 1-year expiry rule):
  the spec's Permit class only has one issuedOn/expiresOn pair for both permit types,
  and rule 4 ("An annual permit expires one year after...") is stated generally, so
  ACCESSIBLE permits are also annual (just free of charge, per rule 2).
- **CitationStatus includes both `ISSUED` and `UPHELD`** as "active/owing" states:
  rule 8 states appeals move to UPHELD or DISMISSED, and rule 9 says the escalation
  clock "resumes on resolution" — so an UPHELD citation must still be able to escalate
  and be paid. `ISSUED` and `UPHELD` are therefore treated identically by
  `runEscalation`/`payCitation`, differing only in that `UPHELD` records the appeal
  history.
- **Payment order (penalty before base fine)**: since `Citation` tracks a single
  `amountPaid` total (per the given class shape) rather than separate penalty/base-fine
  paid amounts, the "penalty first" ordering does not change the arithmetic of the
  running balance — it's documented in code as the conceptual order applied.
- **Permit validity window**: "on or after issuedOn and strictly before expiresOn" is
  interpreted as comparing the observation's full timestamp against the start of the
  issuedOn day and the start of the expiresOn day (i.e., a permit stops being valid at
  the first moment of its expiresOn date).
