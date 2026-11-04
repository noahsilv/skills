# Evidence ledger

Keep a local register of figures and other scalar claims used in financing, diligence and analytical writing. Each claim retains its citations through a deterministic proposal and review process. Accepting a new value preserves the previous record and its review history.

The package is independently authored and self-contained. Python 3.10+ and the
standard library are sufficient. There are no connectors, network calls or
institution-specific rules. All bundled data is synthetic.

## Run the example

From this package directory, use a new destination:

```sh
python examples/run_demo.py /tmp/evidence-ledger-demo
python -m unittest discover -s tests -v
```

The demonstration calls the actual CLI to create a ledger, stage an initial
source claim, record its simulated review, then stage a conflicting revision
and an unknown claim. It generates a final pending snapshot and Markdown report.
It deliberately leaves the conflicting revision unaccepted so the earlier
accepted figure remains visible. Synthetic review records are test data, not
authorization for real work.

Read [the example report](examples/outputs/ledger.md), [the final snapshot](examples/outputs/ledger.json),
and [the staged proposal](examples/outputs/proposal.json). Expected results:
one accepted claim, two pending claims, one unresolved difference, and one
unknown. The helper reports `source_truth: not_checked` throughout.

## Commands

| Command | Result |
|---|---|
| `init --ledger-id ID --out FILE` | New empty ledger |
| `fingerprint FILE` | SHA-256 of a local file, at most 8 MiB |
| `stage --ledger FILE --input UPDATE --out PROPOSAL` | Append-only proposal bound to the base bytes |
| `apply --ledger FILE --proposal FILE --review FILE --out NEXT` | New snapshot with a recorded review |
| `validate --ledger FILE` | Structural result, derived statuses, conflicts and unknowns |
| `report --ledger FILE --out FILE` | Human-readable Markdown claim table |

Prefix each command with `python scripts/ledger.py`. Commands exit 0 for a
completed operation and 2 for rejected input or an execution error. A valid record
may still contain pending claims, conflicts or unknowns; exit 0 is not a finding
that the facts are correct. Output paths must be new.

## Design and scope

Claims and source records are immutable by ID. Repeating identical records is
idempotent; reusing an ID with different contents is rejected. Reviews derive
`pending`, `accepted`, `rejected` and `superseded` status without rewriting claims.
An active accepted claim cannot be replaced unless the next acceptance names it
in `supersedes`. Empty review decisions leave claims pending.

Conflict groups share entity, metric, period and basis. Different values, units,
currencies or qualifier lists within a group require review. There is no automatic
conversion, source ranking or semantic identity matching. The field names and
IDs must be chosen consistently by the operator. See [the contract](references/record-contract.md).

Base and proposal hashes reject stale or modified inputs. Snapshots and exclusive
output creation protect prior files; hashes are not signatures and do not
authenticate an actor or prevent someone manually rewriting an entire history.
The helper reads each input into a bounded snapshot and rechecks the base before
writing. It does not lock other applications or merge concurrent branches.

The source digest is recorded as supplied. `fingerprint` computes it from local
bytes, but `validate` does not open source documents, verify a locator, recalculate
a workbook, authenticate a review reference or judge the truth of a claim. An
accepted value can still conflict with a pending value. Review those conflicts
before relying on the accepted value downstream. No extraction engine, source
archive, document rendering, credit scoring or external publication is included.

The tests exercise the deterministic helper and CLIs. Agent trigger evaluations,
comparative model benchmarks and human source review remain separate activities.
