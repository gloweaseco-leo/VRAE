"""The operator's actual public integration source; never a customer website."""
import http.server
import ssl
from pathlib import Path

PAGES={
 "/":"""<!doctype html><html lang="en"><title>VRAE public controlled industrial sample</title><h1>Controlled sample pump catalog</h1><p>This operator-owned public integration website is not a customer. Published content is deliberately limited.</p><a href="/products">Catalog</a><a href="/contact">Contact</a></html>""",
 "/products":"""<!doctype html><html lang="en"><title>Sample pump TX10</title><h1>TX10 sample catalog</h1><p>Example material: stainless steel. Actual operating pressure, certificates and product test results are not supplied. These unknowns must remain unknown.</p><a href="/contact">Request technical details</a></html>""",
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

def main():
    tls=ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    tls.minimum_version=ssl.TLSVersion.TLSv1_2
    tls.load_cert_chain(str(Path("/tls/source.pem")),str(Path("/tls/source-key.pem")))
    server=http.server.ThreadingHTTPServer(("127.0.0.1",9443),Handler)
    server.socket=tls.wrap_socket(server.socket,server_side=True)
    print('{"phase":"OPERATOR_OWNED_PUBLIC_SOURCE_READY","customer_website":false}',flush=True)
    server.serve_forever()

if __name__=="__main__":
    main()
