# Runtime checklist

A prompt describes work; the host supplies capabilities. Check the boundary once, then write for what is actually available.

| Environment | Check before writing |
| --- | --- |
| Text chat | Which material is attached or visible? A path alone is not an attachment. |
| API request | Which model and endpoint execute it? Which controls are documented? Keep configuration separate from the prompt. |
| Text-only worker | Include all needed evidence or specify the input placeholder. Do not require file reads, tool calls or saving outputs. |
| Tool-using agent | Name available operations and required result checks. Preserve existing authorization; don't add repeated permission questions. |
| Unattended task | No reply is available. Define routine assumptions, material blockers and a useful partial result. Never treat missing approval as granted. |

For a file edit, retain preservation requirements and validate the saved file, not merely in-memory data. A recalculation request needs a real calculation engine; reading stored spreadsheet values is different. If the host cannot produce the artifact, say what a capable host must do next.

For extracted values, keep source locators and units attached to each claim. Null should mean an explicitly defined missing state. Conflicting sources need a reported discrepancy or an established precedence rule, not an invented average.

For long jobs, save progress only when storage is exposed. Identify completed work, pending work, decisions and verification results. Do not promise continuation after the host stops unless it supports that behavior.

Exact provider settings change. Verify them when needed using the provider's official documentation. If verification is unavailable, omit the setting rather than importing a control from another provider.
