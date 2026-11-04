#!/usr/bin/env python3
"""A bounded MCP stdio adapter for a small, explicitly specified metrics API."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
import json
from http.client import HTTPException
import os
import re
import sys
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener

PROTOCOL = "2024-11-05"
MAX_BYTES = 262144
TIMEOUT = 10
ID = re.compile(r"[A-Z][A-Z0-9_]{0,39}\Z")


class AdapterError(ValueError):
    """A caller-safe category, with no request body, URL or credential details."""


def parse_json(raw):
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise ValueError("duplicate key")
            result[key] = value
        return result
    try:
        result = json.loads(raw, object_pairs_hook=pairs,
                            parse_constant=lambda _: (_ for _ in ()).throw(ValueError("nonfinite")))
        def utf8(value):
            if isinstance(value, str):
                value.encode("utf-8")
            elif isinstance(value, dict):
                for key, item in value.items():
                    utf8(key)
                    utf8(item)
            elif isinstance(value, list):
                for item in value:
                    utf8(item)
        utf8(result)
        return result
    except (ValueError, UnicodeError, RecursionError) as exc:
        raise AdapterError("invalid_json") from exc


def bounded_int(value, low, high):
    if type(value) is not int or not low <= value <= high:
        raise AdapterError("invalid_arguments")
    return value


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


class ApiClient:
    def __init__(self, origin, token="", allow_loopback=False, opener=None):
        parts = urlsplit(origin)
        loopback = allow_loopback and parts.scheme == "http" and parts.hostname == "127.0.0.1"
        try:
            port = parts.port
        except ValueError as exc:
            raise AdapterError("invalid_configuration") from exc
        if (not parts.hostname or not (parts.scheme == "https" or loopback)
                or parts.username is not None or parts.password is not None
                or parts.path not in ("", "/") or parts.query or parts.fragment
                or any(c.isspace() for c in origin) or (port is not None and port < 1)):
            raise AdapterError("invalid_configuration")
        if not isinstance(token, str) or any(ord(c) < 33 or ord(c) > 126 for c in token):
            raise AdapterError("invalid_configuration")
        self.origin = origin.rstrip("/")
        self.token = token
        self.opener = opener or build_opener(NoRedirect())

    def get(self, route, params):
        if route not in {"/v1/series", "/v1/observations"}:
            raise AdapterError("invalid_route")
        headers = {"Accept": "application/json"}
        if self.token:
            headers["Authorization"] = "Bearer " + self.token
        request = Request(self.origin + route + "?" + urlencode(params), headers=headers)
        try:
            with self.opener.open(request, timeout=TIMEOUT) as response:
                if response.status != 200:
                    raise AdapterError("upstream_http_error")
                if response.headers.get_content_type() != "application/json":
                    raise AdapterError("upstream_content_type")
                raw = response.read(MAX_BYTES + 1)
        except HTTPError as exc:
            exc.close()
            raise AdapterError("upstream_http_error") from exc
        except (URLError, TimeoutError, OSError, HTTPException) as exc:
            raise AdapterError("upstream_unavailable") from exc
        if len(raw) > MAX_BYTES:
            raise AdapterError("upstream_response_too_large")
        return parse_json(raw)


def exact_keys(obj, keys):
    if not isinstance(obj, dict) or set(obj) != set(keys):
        raise AdapterError("invalid_upstream_shape")


def text_field(value):
    try:
        if isinstance(value, str):
            value.encode("utf-8")
    except UnicodeError as exc:
        raise AdapterError("invalid_upstream_shape") from exc
    if not isinstance(value, str) or not value.strip() or len(value) > 160 or any(ord(c) < 32 or ord(c) == 127 for c in value):
        raise AdapterError("invalid_upstream_shape")
    return value


def page(body, limit, offset):
    exact_keys(body, {"items", "offset", "total"})
    if type(body["offset"]) is not int or body["offset"] != offset:
        raise AdapterError("invalid_upstream_pagination")
    total = body["total"]
    if type(total) is not int or not 0 <= total <= 100000:
        raise AdapterError("invalid_upstream_pagination")
    items = body["items"]
    expected = min(limit, max(0, total - offset))
    if not isinstance(items, list) or len(items) != expected:
        raise AdapterError("invalid_upstream_pagination")
    return items, total


class MetricsAdapter:
    def __init__(self, client):
        self.client = client

    def call(self, name, args):
        if not isinstance(args, dict):
            raise AdapterError("invalid_arguments")
        if name not in {"metric_catalog", "metric_observations"}:
            raise AdapterError("unknown_tool")
        allowed = {"limit", "offset"}
        if name == "metric_observations":
            allowed |= {"series_id", "start_year", "end_year"}
        if set(args) - allowed:
            raise AdapterError("invalid_arguments")
        limit = bounded_int(args.get("limit", 20), 1, 50)
        offset = bounded_int(args.get("offset", 0), 0, 100000)
        params = {"limit": limit, "offset": offset}
        if name == "metric_observations":
            identifier = args.get("series_id")
            if not isinstance(identifier, str) or not ID.fullmatch(identifier):
                raise AdapterError("invalid_arguments")
            start = bounded_int(args.get("start_year"), 1900, 2200)
            end = bounded_int(args.get("end_year"), 1900, 2200)
            if end < start:
                raise AdapterError("invalid_arguments")
            params.update(series_id=identifier, start_year=start, end_year=end)
        route = "/v1/series" if name == "metric_catalog" else "/v1/observations"
        body = self.client.get(route, params)
        items, total = page(body, limit, offset)
        seen = set()
        for item in items:
            if name == "metric_catalog":
                exact_keys(item, {"series_id", "name", "unit"})
                identifier = item["series_id"]
                if not isinstance(identifier, str) or not ID.fullmatch(identifier):
                    raise AdapterError("invalid_upstream_shape")
                text_field(item["name"])
                text_field(item["unit"])
                key = identifier
            else:
                exact_keys(item, {"series_id", "year", "value", "unit", "source"})
                if item["series_id"] != params["series_id"]:
                    raise AdapterError("upstream_scope_mismatch")
                year = item["year"]
                if type(year) is not int or not start <= year <= end:
                    raise AdapterError("upstream_scope_mismatch")
                text_field(item["unit"])
                text_field(item["source"])
                value = item["value"]
                if value is not None:
                    if not isinstance(value, str) or len(value) > 80 or not re.fullmatch(r"-?(?:0|[1-9][0-9]*)(?:\.[0-9]+)?", value):
                        raise AdapterError("invalid_upstream_value")
                    try:
                        if not Decimal(value).is_finite():
                            raise AdapterError("invalid_upstream_value")
                    except InvalidOperation as exc:
                        raise AdapterError("invalid_upstream_value") from exc
                key = year
            if key in seen:
                raise AdapterError("duplicate_upstream_item")
            seen.add(key)
        next_offset = offset + len(items) if offset + len(items) < total else None
        return {"items": items, "offset": offset, "total": total, "next_offset": next_offset,
                "retrieved_at": datetime.now(timezone.utc).isoformat(),
                "source_origin": self.client.origin, "live_verification": "not_established_by_adapter"}


PAGE_PROPERTIES = {
    "limit": {"type": "integer", "minimum": 1, "maximum": 50, "default": 20},
    "offset": {"type": "integer", "minimum": 0, "maximum": 100000, "default": 0},
}
TOOLS = [
    {"name": "metric_catalog", "description": "List a bounded page of series names and units from the configured metrics API.",
     "inputSchema": {"type": "object", "properties": PAGE_PROPERTIES, "additionalProperties": False}},
    {"name": "metric_observations", "description": "Read annual observations for one series and year range; null values remain missing. Follow next_offset for more pages.",
     "inputSchema": {"type": "object", "properties": {**PAGE_PROPERTIES,
        "series_id": {"type": "string", "pattern": "^[A-Z][A-Z0-9_]{0,39}$"},
        "start_year": {"type": "integer", "minimum": 1900, "maximum": 2200},
        "end_year": {"type": "integer", "minimum": 1900, "maximum": 2200}},
        "required": ["series_id", "start_year", "end_year"], "additionalProperties": False}},
]


class StdioServer:
    def __init__(self, adapter):
        self.adapter = adapter
        self.initialized = False
        self.ready = False

    @staticmethod
    def error(identifier, code, message):
        return {"jsonrpc": "2.0", "id": identifier, "error": {"code": code, "message": message}}

    def handle(self, request):
        if (not isinstance(request, dict) or request.get("jsonrpc") != "2.0"
                or not isinstance(request.get("method"), str)
                or set(request) - {"jsonrpc", "id", "method", "params"}
                or ("id" in request and type(request["id"]) not in {str, int})):
            return self.error(None, -32600, "Invalid Request")
        method = request["method"]
        if "id" not in request:
            if method == "notifications/initialized" and self.initialized:
                self.ready = True
            return None
        identifier = request["id"]
        params = request.get("params", {})
        if not isinstance(params, dict):
            return self.error(identifier, -32602, "Invalid params")
        if method == "initialize":
            if self.initialized or not isinstance(params.get("protocolVersion"), str) or not isinstance(params.get("capabilities"), dict) or not isinstance(params.get("clientInfo"), dict):
                return self.error(identifier, -32602, "Invalid initialization")
            self.initialized = True
            result = {"protocolVersion": PROTOCOL, "capabilities": {"tools": {"listChanged": False}},
                      "serverInfo": {"name": "portfolio-metrics-adapter", "version": "1.0.0"}}
        elif method == "ping":
            result = {}
        elif not self.ready:
            return self.error(identifier, -32000, "Session not initialized")
        elif method == "tools/list":
            if params:
                return self.error(identifier, -32602, "No tool-list pagination")
            result = {"tools": TOOLS}
        elif method == "tools/call":
            if set(params) - {"name", "arguments"} or not isinstance(params.get("name"), str):
                return self.error(identifier, -32602, "Invalid params")
            if params["name"] not in {t["name"] for t in TOOLS}:
                return self.error(identifier, -32602, "Unknown tool")
            try:
                value = self.adapter.call(params["name"], params.get("arguments", {}))
                result = {"content": [{"type": "text", "text": json.dumps(value, ensure_ascii=False)}], "isError": False}
            except AdapterError as exc:
                result = {"content": [{"type": "text", "text": json.dumps({"error": str(exc)})}], "isError": True}
        else:
            return self.error(identifier, -32601, "Method not found")
        return {"jsonrpc": "2.0", "id": identifier, "result": result}

    def run(self, incoming, outgoing):
        while True:
            raw = incoming.readline(MAX_BYTES + 1)
            if not raw:
                return 0
            if len(raw) > MAX_BYTES:
                response = self.error(None, -32700, "Message too large")
                outgoing.write(json.dumps(response).encode() + b"\n")
                outgoing.flush()
                return 2
            try:
                response = self.handle(parse_json(raw))
            except AdapterError:
                response = self.error(None, -32700, "Parse error")
            if response is not None:
                outgoing.write(json.dumps(response, ensure_ascii=False).encode() + b"\n")
                outgoing.flush()


def main():
    argparse.ArgumentParser(description=__doc__).parse_args()
    try:
        client = ApiClient(os.environ.get("METRICS_API_ORIGIN", "https://metrics.example.invalid"),
                           os.environ.get("METRICS_API_TOKEN", ""),
                           allow_loopback=os.environ.get("METRICS_ALLOW_LOOPBACK") == "1")
    except (AdapterError, ValueError):
        print("Invalid adapter configuration", file=sys.stderr)
        return 2
    return StdioServer(MetricsAdapter(client)).run(sys.stdin.buffer, sys.stdout.buffer)


if __name__ == "__main__":
    raise SystemExit(main())
