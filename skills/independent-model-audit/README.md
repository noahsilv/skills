# Independent model audit

A model can carry the same wrong balance into the next year and still pass a continuity check. It can also use the wrong debt-service figure consistently in a ratio. This example recomputes both from separate inputs before comparing them with the reported outputs.

The demonstration checks principal movements, cash debt service, DSCR and an explicitly supplied covenant. It distinguishes an accurately reported covenant breach from a calculation error, and missing evidence from a passed check.

Start with [the synthetic cases](examples/README.md) or read [the workflow](SKILL.md). The [snapshot contract](references/snapshot-contract.md) specifies the units, periods and mapped values.

```sh
python scripts/audit_model.py examples/clean.json --out /tmp/model-audit-clean
python -m unittest discover -s tests -p 'test_*.py' -v
```

The script checks a normalized JSON snapshot. It does not read or recalculate Excel files. Its separate arithmetic is useful audit evidence within the declared scope; it does not establish source accuracy or an independent professional audit.

Python 3.11 or newer, standard library only. All rights reserved; see [LICENSE](LICENSE).
