import copy
from email.message import Message
import io
from http.client import IncompleteRead, BadStatusLine
import json
from pathlib import Path
import sys
import unittest
from urllib.error import HTTPError, URLError

sys.path.insert(0, str(Path(__file__).parents[1]/"scripts"))
from server import AdapterError, ApiClient, MAX_BYTES, MetricsAdapter, StdioServer, TOOLS, parse_json

ITEM = {"series_id": "OUTPUT", "year": 2024, "value": "105.25", "unit": "index", "source": "Synthetic fixture"}
ARGS = {"series_id": "OUTPUT", "start_year": 2023, "end_year": 2024}


class Client:
    origin = "https://metrics.example.invalid"
    def __init__(self, body):
        self.body = body
        self.calls = []
    def get(self, route, params):
        self.calls.append((route, params))
        return copy.deepcopy(self.body)


class Response:
    status = 200
    def __init__(self, body, mime="application/json"):
        self.body = body
        self.headers = Message()
        self.headers["Content-Type"] = mime
    def __enter__(self): return self
    def __exit__(self, *_): pass
    def read(self, limit): return self.body[:limit]


class Opener:
    def __init__(self, response): self.response = response
    def open(self, request, timeout):
        self.request, self.timeout = request, timeout
        if isinstance(self.response, Exception): raise self.response
        return self.response


class AdapterTests(unittest.TestCase):
    def adapter(self, items=None, **overrides):
        body = {"items": [copy.deepcopy(ITEM)] if items is None else items, "offset": 0, "total": 1}
        body.update(overrides)
        return MetricsAdapter(Client(body))

    def test_decimal_string_preserved(self):
        item = dict(ITEM, value="105.250000000000000001")
        result = self.adapter([item]).call("metric_observations", ARGS)
        self.assertEqual(result["items"][0]["value"], item["value"])
        self.assertIn("+00:00", result["retrieved_at"])

    def test_missing_preserved(self):
        self.assertIsNone(self.adapter([dict(ITEM, value=None)]).call("metric_observations", ARGS)["items"][0]["value"])

    def test_zero_preserved(self):
        self.assertEqual(self.adapter([dict(ITEM, value="0")]).call("metric_observations", ARGS)["items"][0]["value"], "0")

    def test_catalog_contract(self):
        item = {"series_id": "OUTPUT", "name": "Fictional output", "unit": "index"}
        self.assertEqual(self.adapter([item]).call("metric_catalog", {})["items"], [item])

    def test_next_page(self):
        a = self.adapter(total=2)
        self.assertEqual(a.call("metric_observations", {**ARGS, "limit": 1})["next_offset"], 1)

    def test_empty_out_of_range_page(self):
        self.assertIsNone(self.adapter([], total=1, offset=9).call("metric_catalog", {"offset": 9})["next_offset"])

    def test_invalid_argument_matrix(self):
        for args in [{**ARGS, "limit": True}, {**ARGS, "limit": 51}, {**ARGS, "limit": 0},
                     {**ARGS, "offset": -1}, {**ARGS, "start_year": "2023"},
                     {**ARGS, "start_year": 2025}, {**ARGS, "series_id": "../secret"},
                     {**ARGS, "url": "https://other.invalid"}, {}]:
            with self.subTest(args=args), self.assertRaises(AdapterError):
                self.adapter().call("metric_observations", args)

    def test_invalid_args_do_not_request(self):
        a = self.adapter()
        with self.assertRaises(AdapterError): a.call("metric_catalog", {"url": "x"})
        self.assertEqual(a.client.calls, [])

    def test_wrong_series_rejected(self):
        with self.assertRaisesRegex(AdapterError, "scope"):
            self.adapter([dict(ITEM, series_id="OTHER")]).call("metric_observations", ARGS)

    def test_wrong_year_rejected(self):
        with self.assertRaisesRegex(AdapterError, "scope"):
            self.adapter([dict(ITEM, year=2022)]).call("metric_observations", ARGS)

    def test_invalid_decimal_matrix(self):
        for value in [1.2, True, "NaN", "1e999", "01", "+1", " 1", "1.", "9"*81]:
            with self.subTest(value=value), self.assertRaises(AdapterError):
                self.adapter([dict(ITEM, value=value)]).call("metric_observations", ARGS)

    def test_duplicate_period(self):
        with self.assertRaisesRegex(AdapterError, "duplicate"):
            self.adapter([ITEM, ITEM], total=2).call("metric_observations", ARGS)

    def test_unit_required(self):
        with self.assertRaises(AdapterError):
            self.adapter([dict(ITEM, unit="")]).call("metric_observations", ARGS)

    def test_source_required(self):
        with self.assertRaises(AdapterError):
            self.adapter([dict(ITEM, source="")]).call("metric_observations", ARGS)

    def test_surrogate_and_del_labels_rejected(self):
        for label in ["\ud800", "bad\x7f"]:
            with self.subTest(label=repr(label)), self.assertRaises(AdapterError):
                self.adapter([dict(ITEM, unit=label)]).call("metric_observations", ARGS)

    def test_unknown_shape_rejected(self):
        with self.assertRaises(AdapterError):
            self.adapter(extra="not in contract").call("metric_observations", ARGS)

    def test_pagination_mismatch_rejected(self):
        for overrides in [{"offset": 1}, {"total": True}, {"total": -1}, {"total": 2}, {"total": 100001}]:
            with self.subTest(overrides=overrides), self.assertRaises(AdapterError):
                self.adapter(**overrides).call("metric_observations", ARGS)


class HttpTests(unittest.TestCase):
    def test_only_https_by_default(self):
        for origin in ["http://api.example.invalid", "http://127.0.0.1:8000", "file:///tmp/a", "https://user:secret@a.invalid", "https://a.invalid/path", "https://a.invalid?key=secret", "https://a.invalid/#x"]:
            with self.subTest(origin=origin), self.assertRaises(AdapterError): ApiClient(origin)

    def test_loopback_requires_explicit_opt_in(self):
        self.assertEqual(ApiClient("http://127.0.0.1:8080", allow_loopback=True).origin, "http://127.0.0.1:8080")
        with self.assertRaises(AdapterError): ApiClient("http://192.0.2.1", allow_loopback=True)

    def test_header_injection_rejected(self):
        with self.assertRaises(AdapterError): ApiClient("https://api.example.invalid", "key\nInjected: yes")

    def test_request_boundaries(self):
        opener = Opener(Response(b'{"ok": true}'))
        result = ApiClient("https://api.example.invalid", "synthetic-key", opener=opener).get("/v1/series", {"limit": 1})
        self.assertEqual(result, {"ok": True})
        self.assertEqual(opener.request.full_url, "https://api.example.invalid/v1/series?limit=1")
        self.assertEqual(opener.request.get_header("Authorization"), "Bearer synthetic-key")
        self.assertEqual(opener.timeout, 10)

    def test_route_not_arbitrary(self):
        with self.assertRaises(AdapterError): ApiClient("https://api.example.invalid").get("https://other.invalid", {})

    def test_network_error_redacted(self):
        client = ApiClient("https://api.example.invalid", opener=Opener(URLError("secret internal body")))
        with self.assertRaisesRegex(AdapterError, "^upstream_unavailable$"): client.get("/v1/series", {})

    def test_http_error_redacted(self):
        error = HTTPError("https://api.example.invalid", 401, "secret", {}, io.BytesIO(b"secret"))
        client = ApiClient("https://api.example.invalid", opener=Opener(error))
        with self.assertRaisesRegex(AdapterError, "^upstream_http_error$"): client.get("/v1/series", {})

    def test_malformed_http_redacted(self):
        for error in [IncompleteRead(b"private body", 10), BadStatusLine("private header")]:
            client = ApiClient("https://api.example.invalid", opener=Opener(error))
            with self.subTest(error=type(error).__name__), self.assertRaisesRegex(AdapterError, "^upstream_unavailable$"):
                client.get("/v1/series", {})

    def test_non_ascii_token_rejected(self):
        with self.assertRaises(AdapterError): ApiClient("https://api.example.invalid", "secret\u2603")

    def test_timeout_redacted(self):
        client = ApiClient("https://api.example.invalid", opener=Opener(TimeoutError("secret")))
        with self.assertRaisesRegex(AdapterError, "^upstream_unavailable$"): client.get("/v1/series", {})

    def test_oversized_response(self):
        client = ApiClient("https://api.example.invalid", opener=Opener(Response(b"x"*(MAX_BYTES+1))))
        with self.assertRaisesRegex(AdapterError, "too_large"): client.get("/v1/series", {})

    def test_wrong_content_type(self):
        client = ApiClient("https://api.example.invalid", opener=Opener(Response(b"{}", "text/html")))
        with self.assertRaisesRegex(AdapterError, "content_type"): client.get("/v1/series", {})

    def test_strict_json(self):
        for raw in [b'{"x":1,"x":2}', b'{"x":NaN}', b'\xff', b'{"label":"\\ud800"}', b'['*2000]:
            with self.subTest(raw=raw[:20]), self.assertRaises(AdapterError): parse_json(raw)


class ProtocolTests(unittest.TestCase):
    def server(self): return StdioServer(MetricsAdapter(Client({"items": [], "total": 0, "offset": 0})))
    def initialize(self, server):
        result = server.handle({"jsonrpc":"2.0", "id":1, "method":"initialize", "params":{"protocolVersion":"2025-06-18", "capabilities":{}, "clientInfo":{"name":"test", "version":"1"}}})
        server.handle({"jsonrpc":"2.0", "method":"notifications/initialized"})
        return result

    def test_protocol_negotiation(self):
        self.assertEqual(self.initialize(self.server())["result"]["protocolVersion"], "2024-11-05")

    def test_calls_before_initialization(self):
        self.assertEqual(self.server().handle({"jsonrpc":"2.0","id":2,"method":"tools/list"})["error"]["code"], -32000)

    def test_tool_discovery(self):
        server=self.server();self.initialize(server)
        self.assertEqual(server.handle({"jsonrpc":"2.0","id":2,"method":"tools/list"})["result"]["tools"], TOOLS)

    def test_invalid_arguments_return_tool_error(self):
        server=self.server();self.initialize(server)
        result=server.handle({"jsonrpc":"2.0","id":2,"method":"tools/call","params":{"name":"metric_catalog","arguments":{"limit":99}}})
        self.assertTrue(result["result"]["isError"])

    def test_unknown_tool_is_protocol_error(self):
        server=self.server();self.initialize(server)
        self.assertEqual(server.handle({"jsonrpc":"2.0","id":2,"method":"tools/call","params":{"name":"shell"}})["error"]["code"],-32602)

    def test_unknown_method(self):
        server=self.server();self.initialize(server)
        self.assertEqual(server.handle({"jsonrpc":"2.0","id":2,"method":"other"})["error"]["code"], -32601)

    def test_notifications_have_no_response(self):
        self.assertIsNone(self.server().handle({"jsonrpc":"2.0","method":"notifications/cancelled","params":{"requestId":1}}))

    def test_invalid_request_matrix(self):
        for request in [[], {"jsonrpc":"1.0","id":1,"method":"ping"}, {"jsonrpc":"2.0","id":True,"method":"ping"}, {"jsonrpc":"2.0","id":None,"method":"ping"}]:
            with self.subTest(request=request): self.assertEqual(self.server().handle(request)["error"]["code"],-32600)

    def test_parse_error_and_ping_stdio(self):
        out=io.BytesIO();code=self.server().run(io.BytesIO(b'no json\n{"jsonrpc":"2.0","id":4,"method":"ping"}\n'),out)
        rows=[json.loads(x) for x in out.getvalue().splitlines()]
        self.assertEqual(code,0);self.assertEqual(rows[0]["error"]["code"],-32700);self.assertEqual(rows[1]["result"],{})

    def test_surrogate_request_does_not_kill_stdio(self):
        incoming = json.dumps({"jsonrpc":"2.0", "id":"\ud800", "method":"ping"}).encode()+b"\n"
        incoming += b'{"jsonrpc":"2.0","id":4,"method":"ping"}\n'
        out=io.BytesIO();self.server().run(io.BytesIO(incoming),out)
        rows=[json.loads(x) for x in out.getvalue().splitlines()]
        self.assertEqual(rows[0]["error"]["code"], -32700)
        self.assertEqual(rows[1]["result"], {})

    def test_surrogate_upstream_returns_error_and_continues(self):
        a=MetricsAdapter(Client({"items":[{"series_id":"DEMO", "name":"\ud800", "unit":"index"}],"offset":0,"total":1}))
        server=StdioServer(a);self.initialize(server)
        incoming=json.dumps({"jsonrpc":"2.0","id":2,"method":"tools/call","params":{"name":"metric_catalog"}}).encode()+b"\n"
        incoming+=b'{"jsonrpc":"2.0","id":3,"method":"ping"}\n'
        out=io.BytesIO();server.run(io.BytesIO(incoming),out)
        rows=[json.loads(x) for x in out.getvalue().splitlines()]
        self.assertTrue(rows[0]["result"]["isError"]);self.assertEqual(rows[1]["result"],{})

    def test_oversized_message_stops(self):
        out=io.BytesIO();code=self.server().run(io.BytesIO(b'x'*(MAX_BYTES+1)),out)
        self.assertEqual(code,2);self.assertEqual(json.loads(out.getvalue())["error"]["code"],-32700)

    def test_broken_http_does_not_kill_stdio(self):
        client=ApiClient("https://api.example.invalid",opener=Opener(IncompleteRead(b"private",10)))
        server=StdioServer(MetricsAdapter(client));self.initialize(server)
        incoming=json.dumps({"jsonrpc":"2.0","id":2,"method":"tools/call","params":{"name":"metric_catalog"}}).encode()+b"\n"
        incoming+=b'{"jsonrpc":"2.0","id":3,"method":"ping"}\n'
        out=io.BytesIO();server.run(io.BytesIO(incoming),out)
        rows=[json.loads(x) for x in out.getvalue().splitlines()]
        self.assertTrue(rows[0]["result"]["isError"]);self.assertEqual(rows[1]["result"],{})
        self.assertNotIn("private",out.getvalue().decode())

    def test_no_token_in_tool_error(self):
        client=ApiClient("https://api.example.invalid","synthetic-secret",opener=Opener(URLError("synthetic-secret")))
        server=StdioServer(MetricsAdapter(client));self.initialize(server)
        result=server.handle({"jsonrpc":"2.0","id":2,"method":"tools/call","params":{"name":"metric_catalog"}})
        self.assertNotIn("synthetic-secret",json.dumps(result));self.assertTrue(result["result"]["isError"])


if __name__ == "__main__": unittest.main()
