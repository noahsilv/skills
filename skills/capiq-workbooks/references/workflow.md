# Provider workflow

| Need | Function family to inspect | Evidence required |
| --- | --- | --- |
| Scalar company value | SPG or existing legacy CIQ | Installed add-in formula, entity, field and period. |
| History | SPGRANGEV or the generated legacy range function | Dates, frequency, order, argument positions and return shape. |
| Security or other data table | SPGTable | Data set, security-level identifier, required parameter rows and return area. |
| Screen | SPGScreen | Exact generated query and refresh behavior. |

These are function families, not universal argument signatures. Preserve the complete generated formula. Do not infer that a screen's CUSIP filter means a scalar function accepts a CUSIP directly. Resolve an identifier for the actual data set and query route.

For financials, retain period definitions and magnitude alongside values. Formatting does not convert thousands into millions or percent points into fractions. For market data, keep observation dates and quote sides. A field label is not a returned observation.

When a formula fails, separate unsupported identifiers, arguments, entitlement, connection state and result-area collisions. Obtain a working control instead of repeatedly guessing. A successful control verifies only the observed query and returns; it does not establish coverage for an expanded universe.

Official entry points:

- [MI Office documentation](https://spglobal.my.site.com/s/article/MI-Office-HomePage)
- [Formula Builder](https://spglobal.my.site.com/s/article/Formula-Builder-on-MI-Office)
- [Field lists](https://spglobal.my.site.com/s/article/MI-Office-Field-Lists)

These pages may require licensed access. They are navigation links, not evidence that their content was accessed during this portfolio build. Do not redistribute licensed documentation, field catalogs or account exports in a public package.
