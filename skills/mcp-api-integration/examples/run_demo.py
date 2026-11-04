#!/usr/bin/env python3
"""Exercise the actual stdio server against a loopback-only synthetic HTTP API."""
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
import threading
from fixture_api import make_server


def run():
    api = make_server()
    worker = threading.Thread(target=api.serve_forever, daemon=True)
    worker.start()
    requests = [
        {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {"protocolVersion": "2024-11-05", "capabilities": {}, "clientInfo": {"name": "synthetic-demo", "version": "1.0"}}},
        {"jsonrpc": "2.0", "method": "notifications/initialized"},
        {"jsonrpc": "2.0", "id": 2, "method": "tools/list"},
        {"jsonrpc": "2.0", "id": 3, "method": "tools/call", "params": {"name": "metric_catalog", "arguments": {"limit": 1}}},
        {"jsonrpc": "2.0", "id": 4, "method": "tools/call", "params": {"name": "metric_observations", "arguments": {"series_id": "DEMO_OUTPUT", "start_year": 2022, "end_year": 2024, "limit": 2}}},
        {"jsonrpc": "2.0", "id": 5, "method": "tools/call", "params": {"name": "metric_observations", "arguments": {"series_id": "DEMO_OUTPUT", "start_year": 2022, "end_year": 2024, "limit": 2, "offset": 2}}},
        {"jsonrpc": "2.0", "id": 6, "method": "tools/call", "params": {"name": "metric_catalog", "arguments": {"limit": 51}}},
    ]
    env = dict(os.environ, METRICS_API_ORIGIN=f"http://127.0.0.1:{api.server_port}",
               METRICS_ALLOW_LOOPBACK="1", METRICS_API_TOKEN="", NO_PROXY="127.0.0.1", no_proxy="127.0.0.1")
    try:
        proc = subprocess.run([sys.executable, str(Path(__file__).parents[1]/"scripts/server.py")],
                              input="".join(json.dumps(r)+"\n" for r in requests),
                              text=True, capture_output=True, env=env, timeout=15)
    finally:
        api.shutdown()
        api.server_close()
        worker.join(timeout=2)
    if proc.returncode or proc.stderr:
        raise RuntimeError("stdio demonstration failed")
    responses = [json.loads(line) for line in proc.stdout.splitlines()]
    assert [r["id"] for r in responses] == [1, 2, 3, 4, 5, 6]
    assert responses[0]["result"]["protocolVersion"] == "2024-11-05"
    assert len(responses[1]["result"]["tools"]) == 2
    catalog = json.loads(responses[2]["result"]["content"][0]["text"])
    first = json.loads(responses[3]["result"]["content"][0]["text"])
    last = json.loads(responses[4]["result"]["content"][0]["text"])
    assert catalog["next_offset"] == 1
    assert first["next_offset"] == 2 and last["next_offset"] is None
    assert [r["value"] for r in first["items"]+last["items"]] == ["100.00", None, "105.25"]
    assert responses[5]["result"]["isError"] is True
    return {"fixture": "synthetic localhost API; no live provider was queried",
            "transport": "newline-delimited MCP JSON-RPC over subprocess stdio",
            "protocol": "2024-11-05", "discovered_tools": [t["name"] for t in responses[1]["result"]["tools"]],
            "catalog_page_count": len(catalog["items"]), "catalog_next_offset": catalog["next_offset"],
            "observations": first["items"]+last["items"], "pagination_complete": last["next_offset"] is None,
            "oversized_page_request": json.loads(responses[5]["result"]["content"][0]["text"])}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    if args.output.exists():
        parser.error("output already exists")
    result = run()
    args.output.write_text(json.dumps(result, indent=2)+"\n")
    print("PASS: MCP stdio initialization, discovery, HTTP pagination, missing value and rejected request")
