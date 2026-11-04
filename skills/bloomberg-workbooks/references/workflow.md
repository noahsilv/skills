# Formula and refresh workflow

BDP returns a current or static field. A formula matrix can reference an identifier cell and a field cell, for example `=BDP(Securities!$B2,Fields!$B$2)`. Verify both inputs with the installed add-in before relying on a return.

BDH requests history. Use the installed Formula Builder for dates, frequency and overrides rather than adapting a BDP call by analogy. Check that returned observation dates match the requested period. Current values copied onto a dated sheet are not historical observations.

BDS returns bulk data. Reserve its result area, including headings and expansion space, without overwriting unrelated cells. Array and spill behavior depends on Excel and the add-in version. The BDP helper does not validate those layouts.

| Problem | Check |
| --- | --- |
| Function not recognized | Add-in connection and exact generated function prefix. |
| Identifier or field unavailable | Security identity, market sector, field coverage and entitlement. |
| Pending return | Refresh completion before reading or taking a snapshot. |
| Unexpected number | Unit, magnitude, currency, quote side, observation date and field definition. |
| Result-area conflict | Declared output area and actual returned dimensions. |

Use Bloomberg's [API support entry point](https://www.bloomberg.com/professional/support/api-library/) to find current product documentation. Desktop API documentation is not proof that a particular Excel field or override is supported. Field verification belongs in the terminal or installed add-in; do not distribute licensed manuals, account exports or client workbooks with a skill.
