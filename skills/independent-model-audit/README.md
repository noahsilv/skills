# Independent model audit

A model can carry the same wrong balance into the next year and still pass a continuity check. It can also use the wrong debt-service figure consistently in a ratio. This example recomputes both from separate inputs before comparing them with the reported outputs.

The demonstration checks principal movements, cash debt service, DSCR and an explicitly supplied covenant. It distinguishes an accurately reported covenant breach from a calculation error, and missing evidence from a passed check.

Start with [the synthetic cases](examples/README.md) or read [the workflow](SKILL.md). The [snapshot contract](references/snapshot-contract.md) specifies the units, periods and mapped values.

## Run the clean case

Run from this package directory with Python 3.11 or newer. The script uses the standard library and writes to a new output directory.

```sh
python scripts/audit_model.py examples/clean.json --out ../model-audit-clean
python -m unittest discover -s tests -p 'test_*.py' -v
```

## Interpret the findings

Review the principal movements and debt-service calculation before interpreting covenant compliance. An accurate ratio can still breach the stated covenant. A missing input leaves the affected check incomplete. The calculation uses a normalized JSON snapshot. Workbook recalculation, source verification and an independent professional audit require separate work.

Copyright and use terms are in [LICENSE](LICENSE).
