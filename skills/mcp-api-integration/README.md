# API-to-MCP integration

This example turns a small metrics API into two tools an AI assistant can call: discover series and retrieve annual observations. It shows the work between an API response and a usable tool result: validating scope, preserving units and missing values, and reporting partial pages.

The Python standard-library implementation includes a bounded MCP stdio server. A local demonstration connects it to a synthetic HTTP API. No external account or API key is needed for that demonstration.

| Tool | Output |
| --- | --- |
| `metric_catalog` | One page of series identifiers, names and units. |
| `metric_observations` | One page for a specified series and year range, with source labels and an explicit next-page offset. |

## Run

From this folder, using Python 3.11 or newer:

```sh
python -m unittest discover -s tests -v
python examples/run_demo.py /tmp/mcp-demo.json
```

An additional interoperability check used the MCP Python SDK 1.29.0. To reproduce it in a separate environment:

```sh
python -m pip install -r requirements-sdk.txt
python examples/run_sdk_demo.py /tmp/mcp-sdk-demo.json
```

The SDK initialized the server, discovered both tools, read two pages, preserved a missing value and sent a successful ping after a tool error. [The saved SDK result](examples/sdk-output.json) records that bounded check.

The output path must be new. The demonstration needs permission to open a loopback socket. It starts and closes its own synthetic server; it makes no external provider calls. [The saved result](examples/demo-output.json) preserves the returned decimal strings and a missing observation.

To connect a compatible local MCP client, configure it to launch `python scripts/server.py`. Set `METRICS_API_ORIGIN` to a trusted HTTPS origin implementing [the contract](references/contract.md), and set `METRICS_API_TOKEN` in its environment when required. The default origin is a reserved, non-working example address. `METRICS_ALLOW_LOOPBACK=1` permits plain HTTP only for `127.0.0.1` in local tests.

## What was checked

The unit suite covers input validation, response shape and scope, decimal preservation, pagination, request limits, error redaction and MCP initialization/discovery/calls. The synthetic demonstration exercised the actual subprocess stdio and HTTP path. These checks do not establish compatibility with every MCP client, a live provider, or a hosted deployment.

The server implements a limited MCP 2024-11-05 tool surface. Calls run sequentially. There is no in-flight cancellation, remote MCP transport, client authentication, persistent state or automatic retry. The ten-second socket timeout is not a total execution deadline. Server-reported source labels and a retrieval timestamp are provenance fields, not independent verification of data quality.

Read [SKILL.md](SKILL.md) for the workflow and [the contract](references/contract.md) for supported inputs and limitations. The package is an independently written public demonstration of a broader connector-building workflow. All rights reserved; see [LICENSE](LICENSE).
