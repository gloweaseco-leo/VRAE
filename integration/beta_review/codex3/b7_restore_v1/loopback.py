"""Loopback byte transport into a network-none PG; PostgreSQL owns all auth.

No SQL parsing, credentials, role substitution or protocol emulation. Each client
gets a distinct docker-exec busybox nc -> actual PostgreSQL TCP connection.
"""
import socket
import subprocess
import threading


class Loopback:
    def __init__(self, container):
        self.container = container
        self.listener = socket.socket()
        self.listener.bind(('127.0.0.1', 0))
        self.listener.listen(16)
        self.listener.settimeout(.2)
        self.port = self.listener.getsockname()[1]
        self.closing = threading.Event()
        self.lock = threading.Lock()
        self.clients = {}
        self.threads = []
        self.server = threading.Thread(target=self.accept, daemon=True)
        self.server.start()

    def accept(self):
        while not self.closing.is_set():
            try:
                sock, peer = self.listener.accept()
            except socket.timeout:
                continue
            except OSError:
                if self.closing.is_set():
                    return
                raise
            assert peer[0] == '127.0.0.1'
            thread = threading.Thread(target=self.forward, args=(sock,), daemon=True)
            self.threads.append(thread)
            thread.start()

    def forward(self, sock):
        process = subprocess.Popen(['docker', 'exec', '-i', self.container,
            'busybox', 'nc', '127.0.0.1', '5432'], stdin=subprocess.PIPE,
            stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, bufsize=0)
        with self.lock:
            self.clients[sock] = process
        def upstream():
            try:
                while not self.closing.is_set():
                    raw = sock.recv(65536)
                    if not raw:
                        break
                    view = memoryview(raw)
                    while view:
                        sent = process.stdin.write(view)
                        if not sent:
                            return
                        view = view[sent:]
            except (OSError, ValueError):
                pass  # Peer shutdown; PG/psycopg owns protocol error reporting.
            finally:
                try:
                    process.stdin.close()
                except (OSError, ValueError):
                    pass
        sender = threading.Thread(target=upstream, daemon=True)
        sender.start()
        try:
            while not self.closing.is_set():
                raw = process.stdout.read(65536)
                if not raw:
                    break
                sock.sendall(raw)
        except (OSError, ValueError):
            pass
        finally:
            try:
                sock.shutdown(socket.SHUT_RDWR)
            except OSError:
                pass
            sock.close()
            if process.poll() is None:
                process.terminate()  # Only this supervisor's docker-exec client.
            process.wait(timeout=5)
            process.stdout.close()
            sender.join(timeout=5)
            with self.lock:
                self.clients.pop(sock, None)

    def close(self):
        self.closing.set()
        self.listener.close()
        self.server.join(timeout=5)
        with self.lock:
            clients = list(self.clients.items())
        for sock, process in clients:
            try:
                sock.shutdown(socket.SHUT_RDWR)
            except OSError:
                pass
            if process.poll() is None:
                process.terminate()
        for thread in self.threads:
            thread.join(timeout=5)
        assert not self.server.is_alive() and all(not t.is_alive() for t in self.threads), 'LOOPBACK_THREADS_NOT_CLOSED'
