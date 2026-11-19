"""Actual controlled noncustomer DNS and TLS origin, no recorded transport."""

import asyncio
import json
from pathlib import Path
import ssl
import dns.message
import dns.rdatatype
import dns.rrset


class DNS(asyncio.DatagramProtocol):
    def __init__(self, hosts):
        self.hosts = hosts
        self.queries = []

    def connection_made(self, transport):
        self.transport = transport

    def datagram_received(self, raw, peer):
        q = dns.message.from_wire(raw)
        question = q.question[0]
        host = str(question.name).rstrip(".")
        self.queries.append([host, question.rdtype])
        answer = dns.message.make_response(q)
        if host in self.hosts and question.rdtype == dns.rdatatype.A:
            answer.answer.append(dns.rrset.from_text(question.name, 0, "IN", "A", "93.184.216.20"))
        self.transport.sendto(answer.to_wire(), peer)


async def serve(config):
    dns = DNS(config["hosts"])
    requests = []
    transport, _ = await asyncio.get_running_loop().create_datagram_endpoint(
        lambda: dns, local_addr=("93.184.216.53", 53)
    )

    async def http(reader, writer):
        try:
            raw = await asyncio.wait_for(reader.readuntil(b"\r\n\r\n"), 2)
            line = raw.split(b"\r\n")[0].decode()
            method, path, _ = line.split(" ")
            host = next(
                x[6:].decode() for x in raw.split(b"\r\n") if x.lower().startswith(b"host: ")
            )
            requests.append([host, method, path])
            if host not in config["hosts"]:
                status = 403
                body = b""
            elif path == "/robots.txt":
                status = 200
                body = b"User-agent: *\nDisallow: /private\n"
            elif path == "/denied":
                status = 403
                body = b"Forbidden"
            else:
                status = 200
                records = {
                    "/products/item": [
                        ("Record type", "Product"),
                        ("Product family", "process water pump"),
                        ("Model", "TX10"),
                        ("Rated flow", "60 m3/h"),
                        ("Rated head", "50 m"),
                        ("Motor power", "5 kW"),
                        ("Supply voltage", "400 V"),
                        ("Supply frequency", "50 Hz"),
                        ("Maximum working pressure", "10 bar"),
                        ("Maximum fluid temperature", "80 degC"),
                        ("Permitted medium", "clean water"),
                    ],
                    "/applications": [
                        ("Record type", "Application"),
                        ("Applicable models", "TX10"),
                        ("Required flow", "50 m3/h"),
                        ("Required head", "30 m"),
                        ("Required pressure", "6 bar"),
                        ("Fluid temperature", "40 degC"),
                        ("Available voltage", "400 V"),
                        ("Available frequency", "50 Hz"),
                        ("Process medium", "clean water"),
                        ("Order quantity", "2"),
                    ],
                    "/proof": [
                        ("Record type", "Supplier proof"),
                        ("Applicable models", "TX10"),
                        ("Certificate issuer", "Controlled noncustomer example"),
                        ("Certificate reference", "CONTROLLED-NOT-A-CERTIFICATE"),
                        ("Certificate valid until", "2030-01-01"),
                    ],
                    "/rfq": [
                        ("Record type", "RFQ guide"),
                        ("Applicable models", "TX10"),
                        ("Required RFQ inputs", "Model, Order quantity, Delivery destination"),
                    ],
                }
                rows = "".join(
                    "<tr><th>" + k + "</th><td>" + v + "</td></tr>"
                    for k, v in records.get(path, [])
                )
                links = (
                    "".join(
                        '<a href="' + p + '">' + p + "</a>"
                        for p in (
                            "/products/item",
                            "/applications",
                            "/proof",
                            "/rfq",
                            "/denied",
                            "/private",
                        )
                    )
                    if path == "/"
                    else ""
                )
                body = (
                    '<!doctype html><html lang="en"><meta charset="utf-8"><title>'
                    + config["hosts"][host]
                    + "</title><main><h1>Controlled noncustomer industrial origin</h1><table>"
                    + rows
                    + "</table>"
                    + links
                    + "</main></html>"
                ).encode()

            writer.write(
                (
                    "HTTP/1.1 "
                    + str(status)
                    + " OK\r\nContent-Type: "
                    + ("text/plain" if path == "/robots.txt" else "text/html")
                    + "\r\nContent-Length: "
                    + str(len(body))
                    + "\r\nConnection: close\r\n\r\n"
                ).encode()
                + (body if method == "GET" else b"")
            )
            await writer.drain()
        except (ValueError, ConnectionError, TimeoutError, asyncio.IncompleteReadError):
            pass
        finally:
            writer.close()

    ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    ctx.load_cert_chain("/tmp/lab/cert.pem", "/tmp/lab/key.pem")
    server = await asyncio.start_server(http, "93.184.216.20", 443, ssl=ctx)
    Path("/tmp/lab/ready").touch()
    try:
        await asyncio.Event().wait()
    finally:
        transport.close()
        server.close()


if __name__ == "__main__":
    import sys

    asyncio.run(serve(json.loads(Path(sys.argv[1]).read_bytes())))
