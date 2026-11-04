# Connected synthetic debt and scenario example

This optional wrapper executed the supplied debt script, matched every period's date bounds, currency and units, then replaced explicit zero debt-service placeholders in a synthetic operating case. It ran the scenario engine on that derived file. Both core tools also run independently.

| Period | Start | End | Mapped debt service |
|---|---|---|---:|
| H1_2027 | 2027-01-01 | 2027-07-01 | 13230.14 |
| H2_2027 | 2027-07-01 | 2028-01-01 | 166635.62 |
| H1_2028 | 2028-01-01 | 2028-07-01 | 212341.10 |
| H2_2028 | 2028-07-01 | 2029-01-01 | 256931.51 |

| Case | CFADS total | Debt service total | Cash after service | Minimum period DSCR |
|---|---:|---:|---:|---:|
| base | 1016000.00 | 649138.37 | 366861.63 | 1.226008 |
| volume_down | 756500.00 | 649138.37 | 107361.63 | 0.930014 |
| fixed_cost_up | 960200.00 | 649138.37 | 311061.63 | 1.169962 |
| combined | 700700.00 | 649138.37 | 51561.63 | 0.873968 |

Operating stresses leave contractual debt payments unchanged. A rate or amortization change would require another debt run and a new mapped debt-service array. No covenant threshold is applied.

## Evidence hashes

- debt_input_sha256: `f02070ef25970ea7e050f7af00fe4f9c388710c0b36da6461fc840a5a40e9d33`
- debt_script_sha256: `49a1639b7bd5703373d845e9fa681747b22ac9455471225645a01a2599457869`
- debt_report_sha256: `9731d27a74356ffa982c9622afe0440e2d04d211071c7e10cc018452b8da715e`
- scenario_template_sha256: `e47083846302cab62a64ed1f8c5380825b664df1037abf34297a3f0cc4f1ee39`
- derived_scenario_input_sha256: `f095f56fef44c77717a9d376511923016470387c15ca3d166a632443a813f86f`
- scenario_script_sha256: `5ea0212fbd16fb7896f933aba00ae2e83daff2e6b3ef1f5bd7ab26ab25d63cf4`
- scenario_report_sha256: `239e4be356e9ece0b73803d887c1595a0f171c8c944bc47ebd59ad169b707e2a`

See debt/report.md, scenario/report.md and handoff.json for the calculations and exact mapping.
