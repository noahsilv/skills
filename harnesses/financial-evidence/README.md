# Trace a borrowing reclassification

A synthetic issuer reclassifies USD5 million of other current liabilities as current borrowings. It reports the same total liabilities and cash. Which financing figures need to be revised?

This harness follows a disclosed amount through statement normalization and two closing-date financing cases. It locates the quoted source line and recomputes each covered amount from its inputs. Each trace records a file hash and a location within the file.

## Run the revision

From the repository root, run the walkthrough with Python 3.11 or newer. It uses the standard library.

```sh
python harnesses/financial-evidence/run.py demo
```

| Selected figure (USD millions) | Original disclosure | Revised disclosure |
| --- | ---: | ---: |
| Current borrowings | 90 | 95 |
| Opening net debt | 300 | 305 |
| Closing net debt after refinancing | 302 | 307 |
| Increase in net debt from refinancing | 2 | 2 |
| Closing net debt after capital spending | 402 | 407 |
| Increase in net debt from capital spending | 102 | 102 |

The correction raises both opening and closing net debt by USD5 million. Its effect cancels when the bridge subtracts opening net debt from closing net debt. The calculation still depends on the corrected amount. Closing cash has no dependency on the reclassified opening borrowing balance in these cases.

## Follow one figure

Save a new run, then trace closing net debt back to the disclosure and the transaction terms.

```sh
python harnesses/financial-evidence/run.py demo --out ../financial-trace
python harnesses/financial-evidence/run.py trace ../financial-trace/revised refinance.closing.net_debt
```

The result includes the borrowing line on physical text page two. The disclosure reports 95,000 in USD thousands. The statement records USD95 million. Each calculated value lists its immediate inputs and their coefficients.

The following command traces the source line forward into the closing results.

```sh
python harnesses/financial-evidence/run.py impact ../financial-trace/original ../financial-trace/revised reported.debt_current
```

The comparison returns each dependent figure, its old and new values and the changed input amounts upstream. This distinguishes a calculation that needs review from a value that moves. The [recorded result](expected.json) gives six representative figures.

## Verify a saved trace

```sh
python harnesses/financial-evidence/run.py verify ../financial-trace/revised
python -m unittest discover -s harnesses/financial-evidence -p "test_*.py"
```

Verification rereads the disclosure, statement input and result, opening position, transaction assumptions and closing report. It checks the quoted lines and the conversion from thousands to millions, then reconstructs the graph. Editing a saved source or a closing figure can invalidate the trace.

## Scope

The graph covers five disclosed cash and debt balances and the specified financing flows. The underlying [statement analysis](../../skills/financial-statement-analysis/README.md) and [financing bridge](../../skills/financing-pro-forma/README.md) perform the financial calculations. The trace uses explicit relationships for this fixture. Verifying an actual filing or interpreting an accounting change requires separate source review.
