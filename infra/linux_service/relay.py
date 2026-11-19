"""Bounded opaque TCP ingress. TLS terminates only in the existing mTLS APIs.

No keys, tokens, HTTP parser, dynamic destination or Docker socket is present.
"""

import selectors
import socket
import threading

SLOTS = threading.BoundedSemaphore(16)


def transfer(client, port):
    backend = None
    try:
        client.settimeout(10)
        backend = socket.create_connection(("vrae-api", port), timeout=5)
        backend.settimeout(10)
        with selectors.DefaultSelector() as selector:
            selector.register(client, selectors.EVENT_READ, backend)
            selector.register(backend, selectors.EVENT_READ, client)
            while True:
                ready = selector.select(timeout=60)
                if not ready:
                    return
                for key, _ in ready:
                    data = key.fileobj.recv(16384)
                    if not data:
                        return
                    key.data.sendall(data)
    except OSError:
        pass
    finally:
        client.close()
        if backend:
            backend.close()
        SLOTS.release()


def listen(port):
    with socket.socket() as server:
        server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        server.bind(("0.0.0.0", port))
        server.listen(16)
        while True:
            client, _ = server.accept()
            if SLOTS.acquire(blocking=False):
                threading.Thread(target=transfer, args=(client, port), daemon=True).start()
            else:
                client.close()


def main():
    threading.Thread(target=listen, args=(8770,), daemon=True).start()
    print('{"phase":"OPAQUE_TCP_INGRESS_READY","tls_termination":false}', flush=True)
    listen(8769)


if __name__ == "__main__":
    main()
