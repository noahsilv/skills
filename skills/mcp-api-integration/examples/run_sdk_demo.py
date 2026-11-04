#!/usr/bin/env python3
"""Check the adapter with the optional MCP Python SDK and a synthetic HTTP API."""
import argparse
import asyncio
import json
import os
from pathlib import Path
import sys
import threading
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from fixture_api import make_server


async def run():
    api = make_server()
    thread = threading.Thread(target=api.serve_forever, daemon=True)
    thread.start()
    try:
        env = dict(os.environ, METRICS_API_ORIGIN=f"http://127.0.0.1:{api.server_port}",
                   METRICS_ALLOW_LOOPBACK="1", METRICS_API_TOKEN="",
                   NO_PROXY="127.0.0.1", no_proxy="127.0.0.1")
        params = StdioServerParameters(command=sys.executable,
            args=[str(Path(__file__).parents[1]/"scripts/server.py")], env=env)
        async with stdio_client(params) as (read, write):
            async with ClientSession(read, write) as session:
                init = await session.initialize()
                tools = await session.list_tools()
                assert len(tools.tools) == 2
                first = await session.call_tool("metric_observations", {
                    "series_id": "DEMO_OUTPUT", "start_year": 2022, "end_year": 2024, "limit": 2})
                data = json.loads(first.content[0].text)
                assert not first.isError and data["next_offset"] == 2 and data["items"][1]["value"] is None
                last = await session.call_tool("metric_observations", {
                    "series_id": "DEMO_OUTPUT", "start_year": 2022, "end_year": 2024, "limit": 2, "offset": 2})
                assert not last.isError and json.loads(last.content[0].text)["next_offset"] is None
                bad = await session.call_tool("metric_catalog", {"limit": 51})
                assert bad.isError
                await session.send_ping()
                return {"client": "MCP Python SDK", "negotiated_protocol": init.protocolVersion,
                        "discovered_tools": [tool.name for tool in tools.tools],
                        "initialization_discovery_pagination_missing_error_recovery": "PASS",
                        "upstream": "synthetic loopback only"}
    finally:
        api.shutdown()
        api.server_close()
        thread.join(timeout=2)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    if args.output.exists():
        parser.error("output already exists")
    args.output.write_text(json.dumps(asyncio.run(run()), indent=2)+"\n")
    print("PASS: official MCP client initialized and invoked the synthetic adapter")
