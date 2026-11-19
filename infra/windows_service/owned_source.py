"""The operator's actual public integration source; never a customer website."""
import http.server
import ssl
from pathlib import Path
from threading import BoundedSemaphore

PAGES={
 "/":"""<!doctype html><html lang="en"><title>VRAE public controlled industrial sample</title><h1>Controlled sample pump catalog</h1><p>This operator-owned public integration website is not a customer. Published content is deliberately limited.</p><a href="/products/tx10">TX10 controlled sample detail</a><a href="/contact">Contact</a></html>""",
 "/products":"""<!doctype html><html lang="en"><title>Sample pump TX10</title><h1>TX10 sample catalog</h1><p>Example material: stainless steel. Actual operating pressure, certificates and product test results are not supplied. These unknowns must remain unknown.</p><a href="/contact">Request technical details</a></html>""",
 "/products/tx10":"""<!doctype html><html lang="en"><head><title>TX10 controlled integration sample</title></head><body><h1>TX10 controlled integration sample</h1><p>This operator-authored public sample is only for real network integration acceptance. It is not a customer website, real supplier qualification or verified product specification.</p><table><tr><th>Product family</th><td>Pump</td></tr><tr><th>Model</th><td>TX10 (integration sample)</td></tr><tr><th>Material</th><td>Stainless steel (illustrative source declaration)</td></tr></table><p>Operating pressure, certificates, engineering fit and real supplier identity are not supplied and must remain unknown.</p><a href="/contact">Controlled contact context</a></body></html>""",
 "/contact":"""<!doctype html><html lang="en"><title>Controlled contact page</title><h1>Operator contact example</h1><p>No real customer contacts or commercial submission. No warranty or third-party certification is asserted.</p></html>""",
}

class Handler(http.server.BaseHTTPRequestHandler):
    protocol_version="HTTP/1.1"
    def log_message(self,*_):
        pass
    def do_GET(self):
        if self.path=="/robots.txt":
            raw=b"User-agent: *\nDisallow: /private\n"
            status,kind=200,"text/plain"
        elif self.path in PAGES:
            raw=PAGES[self.path].encode()
            status,kind=200,"text/html; charset=utf-8"
        elif self.path=="/denied":
            raw=b"Forbidden"
            status,kind=403,"text/plain"
        else:
            raw=b"Not found"
            status,kind=404,"text/plain"
        self.send_response(status)
        self.send_header("Content-Type",kind)
        self.send_header("Content-Length",str(len(raw)))
        self.send_header("Cache-Control","no-store")
        self.end_headers()
        self.wfile.write(raw)


class BoundedTLSServer(http.server.ThreadingHTTPServer):
    daemon_threads=True
    request_queue_size=8

    def __init__(self,address,handler,tls):
        self.tls=tls
        self.slots=BoundedSemaphore(8)
        super().__init__(address,handler)

    def get_request(self):
        raw,address=super().get_request()
        raw.settimeout(6)
        try:
            return self.tls.wrap_socket(raw,server_side=True,do_handshake_on_connect=False),address
        except Exception:
            raw.close()
            raise

    def process_request(self,request,address):
        if not self.slots.acquire(blocking=False):
            request.close()
            return
        try:
            super().process_request(request,address)
        except Exception:
            self.slots.release()
            raise

    def process_request_thread(self,request,address):
        try:
            request.do_handshake()
            super().process_request_thread(request,address)
        except (OSError,ssl.SSLError):
            self.shutdown_request(request)
        finally:
            self.slots.release()


def main():
    tls=ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    tls.minimum_version=ssl.TLSVersion.TLSv1_2
    tls.load_cert_chain(str(Path("/tls/source.pem")),str(Path("/tls/source-key.pem")))
    server=BoundedTLSServer(("127.0.0.1",9443),Handler,tls)
    print('{"phase":"OPERATOR_OWNED_PUBLIC_SOURCE_READY","customer_website":false}',flush=True)
    server.serve_forever()

if __name__=="__main__":
    main()
