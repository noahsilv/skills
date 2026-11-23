# Cash at the debt payment date

A project earns a cash surplus over four payment periods. How much of that cash must it retain to make each payment under stress?

This harness runs a fixed-rate debt schedule and maps the payments to an operating model by date. It compares policies that retain all cash, distribute every surplus or retain cash up to a limit. The included facility and operating cases are synthetic.

## Run

From the repository root, run the example with Python 3.11 or newer. It uses the standard library.

```sh
python harnesses/debt-liquidity/run.py
```

To inspect the period ledger, keep the results in a new folder.

```sh
python harnesses/debt-liquidity/run.py --out ../liquidity-run
```

The [recorded comparison](expected.md) shows the base case and three operating stresses. In a retained run, `liquidity.json` records the opening cash, operating cash, debt service, funding gap, distribution and closing cash for each period.

## Read the combined stress

Volume falls by 15 percent and fixed costs rise by 15 percent. The first half-year produces USD114,269.86 after debt service. Operating cash falls short at each of the next three payments.

| Half-year | Cash available for debt service (USD) | Debt service due (USD) | Cash retained at period end under the minimum cap (USD) |
| --- | ---: | ---: | ---: |
| First half 2027 | 127,500.00 | 13,230.14 | 62,708.23 |
| Second half 2027 | 158,150.00 | 166,635.62 | 54,222.61 |
| First half 2028 | 190,500.00 | 212,341.10 | 32,381.51 |
| Second half 2028 | 224,550.00 | 256,931.51 | 0.00 |

Distributing the entire first surplus leaves USD62,708.23 to fund over the next three payments. Retaining that amount covers all three and leaves USD51,561.63 available for distribution at the first payment date.

## Check the boundary

Run the tests from the repository root.

```sh
python -m unittest discover -s harnesses/debt-liquidity -p "test_*.py"
```

The tests compare the calculated retention cap with an independent search across 625 short cash-flow paths. One test starts with an immediate deficit and a later surplus. In that case, even full retention requires opening cash or funding at the first payment.

## Change the assumptions

Pass `--terms` and `--operations` to use another pair of inputs. Follow the [debt terms](../../skills/debt-schedule/references/input-contract.md) and the [operating case](../../skills/scenario-analysis/examples/connected-operating-case.json). Currency, precision and payment dates must agree.

The ledger starts with zero cash and settles the reported amounts at period end. It assumes retained cash is available for debt service. A funding gap measures cash needed on that date. The retention cap uses the full modeled path. Intra-period cash timing, contractual distribution tests and the availability of external funding require separate evidence.
