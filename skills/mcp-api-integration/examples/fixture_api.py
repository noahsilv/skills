"""Local synthetic upstream for the runnable demonstration; never a public service."""
import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlsplit

SERIES = [
    {"series_id": "DEMO_OUTPUT", "name": "Fictional annual output", "unit": "index, 2022=100"},
    {"series_id": "DEMO_RATE", "name": "Fictional financing rate", "unit": "percent"},
]
VALUES = {"DEMO_OUTPUT": [(2022, "100.00"), (2023, None), (2024, "105.25")],
          "DEMO_RATE": [(2022, "3.50"), (2023, "4.25"), (2024, "4.00")]}


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        url = urlsplit(self.path)
        query = parse_qs(url.query)
        try:
            limit = int(query["limit"][0])
            offset = int(query["offset"][0])
            if not 1 <= limit <= 50 or offset < 0:
                raise ValueError()
            if url.path == "/v1/series":
                rows = SERIES
            elif url.path == "/v1/observations":
                identifier = query["series_id"][0]
                start = int(query["start_year"][0])
                end = int(query["end_year"][0])
                unit = next(row["unit"] for row in SERIES if row["series_id"] == identifier)
                rows = [{"series_id": identifier, "year": year, "value": value, "unit": unit,
                         "source": "Synthetic portfolio fixture"}
                        for year, value in VALUES[identifier] if start <= year <= end]
            else:
                raise ValueError()
            payload = json.dumps({"items": rows[offset:offset+limit], "total": len(rows), "offset": offset}).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)
        except (KeyError, ValueError, StopIteration):
            self.send_error(400)

    def log_message(self, *_args):
        pass


def make_server():
    return ThreadingHTTPServer(("127.0.0.1", 0), Handler)
