# Adapter contract

## Upstream API

The example API uses a trusted origin, with no path, user information, query or fragment in the configured origin. HTTPS is required except for explicit loopback testing. The client makes GET requests to exactly two routes. Redirects are rejected, including redirects within the same origin. The optional bearer token is ASCII without whitespace or control characters.

| Route | Query parameters |
| --- | --- |
| `/v1/series` | `limit`, `offset` |
| `/v1/observations` | `limit`, `offset`, `series_id`, `start_year`, `end_year` |

Page size is 1–50; offset is 0–100000. A series identifier starts with an uppercase letter and contains at most 40 uppercase letters, digits or underscores. Years are integers from 1900 to 2200, with start no later than end. Booleans are not accepted as integers.

Both routes return exactly `items`, `offset` and `total`. `total` is an integer between zero and 100000; the response offset must equal the request offset. The item count must equal `min(limit, max(0, total-offset))`. An upstream API that returns short non-final pages must be adapted explicitly; this helper rejects them.

Catalog items contain exactly `series_id`, `name` and `unit`. Observation items contain exactly `series_id`, `year`, `value`, `unit` and `source`. Labels must be nonempty strings, at most 160 characters, without control characters. Observation series and years must match the request. Duplicate series within a catalog page or duplicate years within an observation page are rejected. Cross-page consistency and snapshot isolation are not established by a single call.

Observation values are null or decimal strings of at most 80 characters, using an optional minus sign and optional fractional part. Exponents, leading plus signs, whitespace, leading zeroes, NaN and infinity are rejected. The adapter preserves accepted strings; it does not round or perform arithmetic. Units are carried through without conversion. A consumer combining pages must verify that units are consistent.

The response body is capped at 262144 bytes. Content type must be `application/json`. Duplicate JSON keys and nonfinite JSON constants are rejected. HTTP errors, malformed HTTP transport and network errors return sanitized categories. Unexpected changes to the API contract fail rather than silently dropping fields.

The HTTP opener uses the host's standard proxy and TLS configuration. Origin selection and DNS are trusted deployment responsibilities; this is not a network sandbox or general SSRF defense. Tool callers cannot override the origin, route or credentials.

## MCP surface

The server uses newline-delimited JSON-RPC 2.0 over stdin/stdout and announces MCP protocol `2024-11-05`. Supported methods are `initialize`, `ping`, `tools/list` and `tools/call`, plus the `notifications/initialized` notification. Tool calls and discovery require the initialized notification. Unknown notifications are ignored. Tool results contain JSON serialized into MCP text content; `isError` distinguishes failures from successful pages.

The input schemas describe the same bounds enforced by the adapter. Unknown tool names and unsupported methods return protocol errors. Tool argument validation and upstream failures return tool errors. Malformed JSON returns a parse error. An oversized input line ends the process after a parse error. All other calls execute sequentially, with no asynchronous cancellation.

This is a deliberately limited implementation for inspecting the boundary. It does not implement resources, prompts, logging requests, subscriptions, client sampling, roots, resumability or HTTP transport. A client must accept the announced protocol version. Using a maintained MCP SDK is preferable when extending protocol coverage or deploying a remote service.

The [MCP 2024-11-05 specification](https://modelcontextprotocol.io/specification/2024-11-05) documents the protocol. The [stdio transport](https://modelcontextprotocol.io/specification/2024-11-05/basic/transports) and [tools contract](https://modelcontextprotocol.io/specification/2024-11-05/server/tools) are the relevant interoperability references. This package does not reproduce proprietary provider documentation.

## Executed demonstration

The fixture contains two series with three annual observations each. `DEMO_OUTPUT` has values `100.00`, null and `105.25` for 2022–2024. These are invented data. The demo performs MCP initialization, discovers both tools, reads a one-item catalog page, reads the output series over two pages, and confirms that a page-size request of 51 returns a tool error. The saved report omits the ephemeral port and retrieval timestamp so the demonstration result can be reproduced exactly.
