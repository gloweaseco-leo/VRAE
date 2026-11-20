"""Source TLS regression only; never substituted for public acceptance."""
import http.client
import socket
import ssl
import threading
from infra.windows_service.owned_source import BoundedTLSServer,Handler,PAGES
from integration.authorized_targets.checks.api_tls import create
from vrae.collection.discovery import page_role
from vrae.rules.product_facts import _parse


def test_incomplete_tls_client_does_not_block_next_source_request(tmp_path):
    pki=create(tmp_path/"pki")
    context=ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    context.load_cert_chain(pki["facade"]["certificate"],pki["facade"]["key"])
    server=BoundedTLSServer(("127.0.0.1",0),Handler,context)
    thread=threading.Thread(target=server.serve_forever,daemon=True)
    thread.start()
    stalled=socket.create_connection(server.server_address,timeout=1)
    client=ssl.create_default_context(cafile=pki["ca"])
    connection=http.client.HTTPSConnection("127.0.0.1",server.server_port,context=client,timeout=2)
    try:
        connection.request("GET","/products/tx10")
        response=connection.getresponse()
        assert response.status==200
        assert response.read()==PAGES["/products/tx10"].encode()
        assert response.getheader("Cache-Control")=="no-store"
    finally:
        connection.close()
        stalled.close()
        server.shutdown()
        server.server_close()


def test_real_source_detail_is_supported_without_relaxing_original_parser():
    assert page_role("https://controlled.example.com/products/tx10")=="PRODUCT"
    name,fields=_parse(PAGES["/products/tx10"].encode())
    assert name["text"] and {label["text"] for label,value in fields}=={"Record type","Product family","Model","Material"}
