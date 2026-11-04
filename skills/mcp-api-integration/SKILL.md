---
name: mcp-api-integration
description: Build and review a bounded API-to-MCP integration. Use when exposing a read-only data API as tools, defining input contracts, checking pagination or testing a connector without live credentials. Includes a runnable stdio adapter and synthetic HTTP demonstration.
compatibility: Python 3.11 standard library. The demonstration needs loopback sockets; real retrieval needs a configured API matching the documented contract. The included server implements a limited MCP 2024-11-05 stdio tool surface.
---

# API-to-MCP integration

Define the upstream contract before writing the tool. Record which fields identify an observation, what units mean, how missing values are represented and how pagination ends. A successful HTTP response alone does not establish the requested scope or meaning.

## Choose the boundary

Use [the adapter contract](references/contract.md) to distinguish upstream API behavior from MCP transport behavior. The bundled adapter exposes a catalog and annual observations for one series. It is a demonstrator for a specified synthetic metrics API, not a connector for every financial-data provider.

Choose a fixed origin and routes in trusted deployment configuration. Tool arguments should select the data, not arbitrary hosts or URLs. Read credentials from the environment. Do not include keys in examples, source control, tool arguments or error messages. Keep provider authentication separate from client authentication.

## Implement and check

1. Define narrow tool arguments and validate them again at runtime. Reject ambiguous identifiers, invalid periods and unexpected fields before sending a request.
2. Bound the response size and page size. Use timeouts and reject redirects. The helper's socket timeout does not impose an overall wall-clock deadline.
3. Verify the response shape, requested series and period, page offset and item count. Preserve decimal text and null observations. Do not turn missing values into zero or silently fetch a broader scope.
4. Return source information, retrieval time and a next-page offset. One page is not the full dataset. Check units across pages before combining observations.
5. Return a concise failure category. Do not return upstream bodies, exception text or credentials. An upstream failure is a tool error, not an empty successful dataset.
6. Exercise initialization, discovery and tool calls through the actual transport. Test malformed responses and invalid inputs as well as successful calls.

Run from the package directory:

```sh
python -m unittest discover -s tests -v
python examples/run_demo.py /tmp/mcp-demo.json
```

The demo starts a loopback-only synthetic HTTP API and sends MCP messages to a child process over stdio. It checks catalog discovery, two observation pages, a missing value and a rejected page-size request. Read [the executed result](examples/demo-output.json). The optional [SDK demonstration](examples/run_sdk_demo.py) exercises the same boundary through the MCP Python client; its pinned dependency is in [requirements-sdk.txt](requirements-sdk.txt).

## Delivery

Report the tool names, protocol and upstream contract; identify executed tests and untested deployment steps. The included server provides tools only, with newline-delimited JSON-RPC and protocol negotiation to MCP 2024-11-05. It does not offer HTTP MCP transport, OAuth, resources, prompts, subscriptions, cancellation of in-flight calls or concurrent execution.

A host that accepts this protocol may launch `python scripts/server.py` over stdio. A remote service needs a maintained MCP transport implementation and appropriate authentication. Do not expose this stdio adapter as an unauthenticated web service. Recheck discovery and every tool through the intended client before claiming interoperability or deployment success.
