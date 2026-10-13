"""A fake Cerbos Hub that records what a PDP or cerbosctl sends it.

Speaks the Connect unary protocol with binary protobuf bodies over plain HTTP,
which is what the 0.55.0 PDP and cerbosctl send when their endpoints are
overridden. Every request is appended to a JSON-lines log for the checks to
read back. Nothing is ever served successfully except store writes made with a
credential the fake was told to accept.
"""

import argparse
import gzip
import io
import json
import secrets
import threading
import zipfile
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer


def varint(buf, pos):
    shift = result = 0
    while True:
        b = buf[pos]
        pos += 1
        result |= (b & 0x7F) << shift
        if not b & 0x80:
            return result, pos
        shift += 7


def decode(buf):
    """Return {field_number: [value, ...]}; length-delimited values stay bytes."""
    fields, pos = {}, 0
    while pos < len(buf):
        key, pos = varint(buf, pos)
        num, wire = key >> 3, key & 7
        if wire == 0:
            val, pos = varint(buf, pos)
        elif wire == 2:
            n, pos = varint(buf, pos)
            val, pos = buf[pos : pos + n], pos + n
        elif wire == 1:
            val, pos = buf[pos : pos + 8], pos + 8
        elif wire == 5:
            val, pos = buf[pos : pos + 4], pos + 4
        else:
            raise ValueError(f"unsupported wire type {wire}")
        fields.setdefault(num, []).append(val)
    return fields


def enc_varint(n):
    out = bytearray()
    while True:
        b = n & 0x7F
        n >>= 7
        if n:
            out.append(b | 0x80)
        else:
            out.append(b)
            return bytes(out)


def enc_field(num, value):
    if isinstance(value, int):
        return enc_varint(num << 3) + enc_varint(value)
    if isinstance(value, str):
        value = value.encode()
    return enc_varint(num << 3 | 2) + enc_varint(len(value)) + value


def text(fields, num):
    vals = fields.get(num) or [b""]
    return vals[0].decode("utf-8", "replace")


def file_msg(raw):
    f = decode(raw)
    return text(f, 1), (f.get(2) or [b""])[0]


class Hub:
    def __init__(self, log_path, credentials):
        # credentials: {client_id: {"secret": ..., "kind": "store"|"deployment"}}
        self.log_path = log_path
        self.credentials = credentials
        self.tokens = {}
        self.lock = threading.Lock()

    def record(self, entry):
        with self.lock, open(self.log_path, "a") as log:
            log.write(json.dumps(entry, sort_keys=True) + "\n")


def handler_for(hub):
    class Handler(BaseHTTPRequestHandler):
        protocol_version = "HTTP/1.1"

        def log_message(self, *args):
            pass

        def reply(self, status, body=b"", content_type="application/proto"):
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def error(self, status, code, message):
            body = json.dumps({"code": code, "message": message}).encode()
            self.reply(status, body, "application/json")

        def do_GET(self):
            hub.record({"method": "GET", "path": self.path})
            self.reply(404, b"", "text/plain")

        def do_POST(self):
            length = int(self.headers.get("Content-Length") or 0)
            body = self.rfile.read(length)
            if self.headers.get("Content-Encoding", "").lower() == "gzip":
                body = gzip.decompress(body)
            rpc = self.path.rsplit("/", 1)[-1]
            entry = {"method": "POST", "path": self.path, "rpc": rpc}
            try:
                fields = decode(body)
            except (ValueError, IndexError) as error:
                entry["decode_error"] = str(error)
                entry["headers"] = dict(self.headers)
                hub.record(entry)
                return self.error(400, "invalid_argument", "undecodable body")

            if rpc == "IssueAccessToken":
                client_id, client_secret = text(fields, 1), text(fields, 2)
                entry.update(client_id=client_id, client_secret=client_secret)
                cred = hub.credentials.get(client_id)
                if not cred or cred["secret"] != client_secret:
                    entry["result"] = "unauthenticated"
                    hub.record(entry)
                    return self.error(401, "unauthenticated", "invalid credentials")
                token = secrets.token_hex(16)
                hub.tokens[token] = client_id
                entry["result"] = "ok"
                hub.record(entry)
                duration = enc_field(1, 3600)
                return self.reply(200, enc_field(1, token) + enc_field(2, duration))

            auth = self.headers.get("Authorization", "") + self.headers.get(
                "x-cerbos-auth", ""
            )
            client_id = next(
                (cid for tok, cid in hub.tokens.items() if tok in auth), None
            )
            entry["client_id"] = client_id
            entry["store_id"] = text(fields, 1)
            if client_id is None:
                hub.record(entry | {"result": "unauthenticated"})
                return self.error(401, "unauthenticated", "missing token")
            if hub.credentials[client_id]["kind"] != "store":
                hub.record(entry | {"result": "permission_denied"})
                return self.error(
                    403, "permission_denied", "permission denied for store"
                )

            if rpc == "GetCurrentVersion":
                hub.record(entry | {"result": "ok"})
                return self.reply(200, enc_field(1, 7))
            if rpc == "ListFiles":
                hub.record(entry | {"result": "ok"})
                return self.reply(200, enc_field(1, 7))
            if rpc == "ReplaceFiles":
                files = {}
                if 3 in fields:
                    with zipfile.ZipFile(io.BytesIO(fields[3][0])) as archive:
                        for info in archive.infolist():
                            if not info.is_dir():
                                files[info.filename] = archive.read(info).decode(
                                    "utf-8", "replace"
                                )
                for raw in fields.get(5, []):
                    for f in decode(raw).get(1, []):
                        path, contents = file_msg(f)
                        files[path] = contents.decode("utf-8", "replace")
                entry.update(result="ok", files=files)
                hub.record(entry)
                return self.reply(200, enc_field(1, 8))
            if rpc == "ModifyFiles":
                adds, deletes = {}, []
                for raw in fields.get(3, []):
                    op = decode(raw)
                    if 1 in op:
                        path, contents = file_msg(op[1][0])
                        adds[path] = contents.decode("utf-8", "replace")
                    for d in op.get(2, []):
                        deletes.append(d.decode())
                entry.update(result="ok", adds=adds, deletes=deletes)
                hub.record(entry)
                return self.reply(200, enc_field(1, 8))
            hub.record(entry | {"result": "unimplemented"})
            return self.error(501, "unimplemented", f"fake hub does not serve {rpc}")

    return Handler


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, required=True)
    parser.add_argument("--log", required=True)
    parser.add_argument("--credentials", required=True, help="JSON file")
    args = parser.parse_args()
    with open(args.credentials) as f:
        creds = json.load(f)
    hub = Hub(args.log, creds)
    server = ThreadingHTTPServer(("127.0.0.1", args.port), handler_for(hub))
    server.serve_forever()


if __name__ == "__main__":
    main()
