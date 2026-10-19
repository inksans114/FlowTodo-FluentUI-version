"""Opt-in, token-paired HTTPS camera frames on a single private LAN interface.

Only the newest JPEG is retained in memory. No camera image is written to disk.
"""
from __future__ import annotations

import hmac
import html
import ipaddress
import json
import secrets
import ssl
import threading
import time
from datetime import datetime, timedelta, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

PAGE = Path(__file__).resolve().parent / "supervision-web/phone.html"
MAX_FRAME = 350_000
LAN_NETWORKS = tuple(ipaddress.ip_network(network) for network in ("10.0.0.0/8", "172.16.0.0/12", "192.168.0.0/16"))


def private_host(host, allow_loopback=False):
    address = ipaddress.ip_address(host)
    if address.version != 4 or not (any(address in network for network in LAN_NETWORKS) or (allow_loopback and address.is_loopback)):
        raise ValueError("请选择电脑的局域网 IPv4 地址。")
    return str(address)


def certificates(directory, host):
    from cryptography import x509
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import rsa
    from cryptography.x509.oid import ExtendedKeyUsageOID, NameOID
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    root_file, root_key_file = directory / "local-ca.cer", directory / "local-ca-key.pem"
    now = datetime.now(timezone.utc)
    root = key = None
    try:
        root = x509.load_der_x509_certificate(root_file.read_bytes())
        key = serialization.load_pem_private_key(root_key_file.read_bytes(), password=None)
        if root.not_valid_after_utc < now + timedelta(days=8):
            root = key = None
    except (OSError, ValueError):
        pass
    if root is None:
        key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "FlowTodo Local Camera " + secrets.token_hex(4))])
        root = (x509.CertificateBuilder().subject_name(name).issuer_name(name).public_key(key.public_key())
                .serial_number(x509.random_serial_number()).not_valid_before(now - timedelta(minutes=5))
                .not_valid_after(now + timedelta(days=365)).add_extension(x509.BasicConstraints(ca=True, path_length=0), critical=True)
                .add_extension(x509.KeyUsage(False, False, False, False, False, True, True, False, False), critical=True)
                .sign(key, hashes.SHA256()))
        root_file.write_bytes(root.public_bytes(serialization.Encoding.DER))
        root_key_file.write_bytes(key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption()))
    leaf_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    leaf = (x509.CertificateBuilder().subject_name(x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "FlowTodo Camera")]))
            .issuer_name(root.subject).public_key(leaf_key.public_key()).serial_number(x509.random_serial_number())
            .not_valid_before(now - timedelta(minutes=5)).not_valid_after(now + timedelta(days=7))
            .add_extension(x509.SubjectAlternativeName([x509.IPAddress(ipaddress.ip_address(host))]), critical=False)
            .add_extension(x509.BasicConstraints(ca=False, path_length=None), critical=True)
            .add_extension(x509.ExtendedKeyUsage([ExtendedKeyUsageOID.SERVER_AUTH]), critical=False)
            .add_extension(x509.KeyUsage(True, False, True, False, False, False, False, False, False), critical=True)
            .sign(key, hashes.SHA256()))
    certificate, private_key = directory / "server.pem", directory / "server-key.pem"
    certificate.write_bytes(leaf.public_bytes(serialization.Encoding.PEM) + root.public_bytes(serialization.Encoding.PEM))
    private_key.write_bytes(leaf_key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption()))
    return certificate, private_key, root_file, root.fingerprint(hashes.SHA256()).hex()


class PhoneStreamServer:
    def __init__(self, host, directory, *, allow_loopback=False):
        self.host = private_host(host, allow_loopback)
        self.token = secrets.token_urlsafe(32)
        self.lock = threading.Lock()
        self.latest = None
        self.running = False
        self.closed = False
        self.last_seen = 0
        self.last_frame = 0
        self.last_probe = self.last_page = 0
        self.client = ""
        cert, key, self.ca, self.fingerprint = certificates(directory, self.host)
        owner = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *_args):
                pass  # Never log URLs containing pairing secrets.

            def setup(self):
                super().setup()
                self.connection.settimeout(4)

            def allowed(self):
                supplied = self.headers.get("X-FlowTodo-Token", "") or parse_qs(urlsplit(self.path).query).get("token", [""])[0]
                origin = self.headers.get("Origin", "")
                return not owner.closed and hmac.compare_digest(supplied, owner.token) and (not origin or origin == owner.origin)

            def reply(self, code, body=b"", content="application/json"):
                self.send_response(code)
                self.send_header("Content-Type", content)
                self.send_header("Content-Length", str(len(body)))
                if content == "application/x-x509-ca-cert":
                    self.send_header("Content-Disposition", 'attachment; filename="FlowTodo-LocalCamera.cer"')
                self.send_header("Cache-Control", "no-store")
                self.send_header("Referrer-Policy", "no-referrer")
                self.send_header("X-Content-Type-Options", "nosniff")
                self.send_header("Permissions-Policy", "camera=(self), microphone=()")
                self.send_header("Content-Security-Policy", "default-src 'none'; script-src 'unsafe-inline'; style-src 'unsafe-inline'; connect-src 'self'; media-src 'self' blob:; img-src 'self' blob: data:; frame-ancestors 'none'")
                self.end_headers()
                try:
                    self.wfile.write(body)
                except (OSError, ssl.SSLError):
                    pass

            def do_GET(self):
                path = urlsplit(self.path).path
                if path == "/" and not owner.closed:
                    # The page itself contains no secret or camera data. Render
                    # a useful message even after refresh or an expired pairing.
                    with owner.lock:
                        owner.last_page = time.monotonic()
                    self.reply(200, PAGE.read_bytes(), "text/html; charset=utf-8")
                    return
                if not self.allowed():
                    self.reply(403)
                    return
                if path == "/status":
                    with owner.lock:
                        owner.last_seen = time.monotonic()
                        status = {"running": owner.running, "fingerprint": owner.fingerprint}
                    self.reply(200, json.dumps(status).encode())
                elif path == "/certificate":
                    self.reply(200, owner.ca.read_bytes(), "application/x-x509-ca-cert")
                else:
                    self.reply(404)

            def do_POST(self):
                if not self.allowed():
                    self.reply(403)
                    return
                if urlsplit(self.path).path != "/frame":
                    self.reply(404)
                    return
                try:
                    size = int(self.headers.get("Content-Length", "0"))
                except ValueError:
                    size = 0
                if not 4 <= size <= MAX_FRAME or self.headers.get("Content-Type") != "image/jpeg":
                    self.reply(413)
                    return
                with owner.lock:
                    rejection = 409 if not owner.running or (owner.client and owner.client != self.client_address[0]) else 429 if time.monotonic() - owner.last_frame < .4 else 0
                if rejection:
                    self.reply(rejection)
                    return
                try:
                    data = self.rfile.read(size)
                except OSError:
                    self.reply(408)
                    return
                if len(data) != size or not data.startswith(b"\xff\xd8") or not data.endswith(b"\xff\xd9"):
                    self.reply(400)
                    return
                with owner.lock:
                    accepted = owner.running and not owner.closed and (not owner.client or owner.client == self.client_address[0])
                    if accepted:
                        owner.client = self.client_address[0]
                        owner.last_frame = owner.last_seen = time.monotonic()
                        owner.latest = (data, owner.last_frame)
                if not accepted:
                    self.reply(409)
                    return
                self.reply(202)

        self.http = ThreadingHTTPServer((self.host, 0), Handler)
        self.http.daemon_threads = True
        context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        context.minimum_version = ssl.TLSVersion.TLSv1_2
        context.load_cert_chain(str(cert), str(key))
        self.http.socket = context.wrap_socket(self.http.socket, server_side=True, do_handshake_on_connect=False)
        self.origin = f"https://{self.host}:{self.http.server_port}"
        self.url = self.origin + "/#token=" + self.token
        self.thread = threading.Thread(target=self.http.serve_forever, kwargs={"poll_interval": .1}, daemon=True)
        self.thread.start()
        # Plain HTTP only diagnoses reachability and delivers the public CA.
        # It never accepts frames or exposes the pairing token. A blank TLS
        # page can otherwise prevent users from reaching certificate help.
        class CheckHandler(BaseHTTPRequestHandler):
            def log_message(self, *_args):
                pass

            def setup(self):
                super().setup()
                self.connection.settimeout(4)

            def do_GET(self):
                path = urlsplit(self.path).path
                if owner.closed or path not in ("/", "/check", "/certificate"):
                    self.send_error(404)
                    return
                with owner.lock:
                    owner.last_probe = time.monotonic()
                if path == "/certificate":
                    body, content = owner.ca.read_bytes(), "application/x-x509-ca-cert"
                else:
                    body = ("<!doctype html><html lang='zh-CN'><meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1'>"
                        "<title>FlowTodo 连接检查</title><style>body{font:16px system-ui;background:#13251f;color:#e5ece8;max-width:560px;margin:40px auto;padding:24px;line-height:1.8}a{color:#c7dbba}code{overflow-wrap:anywhere}</style>"
                        "<h1>手机已经连到电脑了</h1><p>局域网地址和这个检查端口可访问。如果摄像头页面仍然打不开，继续检查 HTTPS 端口和证书。</p>"
                        "<p>安卓 Edge：如果出现证书提示，核对地址后继续访问。若仍不允许摄像头，可下载并安装这台电脑的本地 CA 证书（系统设置中搜索“安装证书”，选择 CA 证书）。安装前，必须核对下方指纹与电脑显示的一致。</p>"
                        "<p><a href='/certificate'>下载本地 CA 证书</a></p><p>SHA-256：<code>" + html.escape(owner.fingerprint) + "</code></p>"
                        "<p>安装后关闭旧页面，再扫描电脑的“摄像头连接”二维码。此检查页不会打开镜头，也不会接收画面。</p></html>").encode("utf-8")
                    content = "text/html; charset=utf-8"
                self.send_response(200)
                self.send_header("Content-Type", content)
                self.send_header("Content-Length", str(len(body)))
                self.send_header("Cache-Control", "no-store")
                self.send_header("X-Content-Type-Options", "nosniff")
                self.send_header("Content-Security-Policy", "default-src 'none'; style-src 'unsafe-inline'; frame-ancestors 'none'")
                if path == "/certificate":
                    self.send_header("Content-Disposition", 'attachment; filename="FlowTodo-LocalCamera.cer"')
                self.end_headers()
                try:
                    self.wfile.write(body)
                except OSError:
                    pass

            def do_POST(self):
                self.send_error(403, "Camera frames require the paired HTTPS endpoint")

        try:
            self.check_http = ThreadingHTTPServer((self.host, 0), CheckHandler)
            self.check_http.daemon_threads = True
        except Exception:
            self.close()
            raise
        self.check_url = f"http://{self.host}:{self.check_http.server_port}/check"
        self.check_thread = threading.Thread(target=self.check_http.serve_forever, kwargs={"poll_interval": .1}, daemon=True)
        self.check_thread.start()

    def set_running(self, running):
        with self.lock:
            self.running = bool(running) and not self.closed
            if not self.running:
                self.latest = None

    def take_frame(self):
        with self.lock:
            frame, self.latest = self.latest, None
            return frame

    def close(self):
        with self.lock:
            self.closed = True
            self.running = False
            self.latest = None
            self.token = ""
        self.http.shutdown()
        self.http.server_close()
        self.thread.join(timeout=1)
        if hasattr(self, "check_thread"):
            self.check_http.shutdown()
            self.check_http.server_close()
            self.check_thread.join(timeout=1)
