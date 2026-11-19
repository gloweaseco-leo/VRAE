"""Private Unix nonce broker. The original M1/review private keys stay at UID0."""

import json
import os
import socket
import struct
from threading import Thread, BoundedSemaphore
import time

from vrae.application.ra4b_p2.m1.consumer import TaskHandle


def ask(path, operation, task, nonce):
    value = {"operation": operation, "task": task.__dict__, "nonce": nonce}
    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as client:
        client.settimeout(5)
        client.connect(path)
        client.sendall(json.dumps(value).encode() + b"\n")
        stream = client.makefile("rb")
        raw = stream.readline(32769)
    result = json.loads(raw)
    if set(result) != {"bearer"}:
        raise ValueError("G1_CONTROLLED_BROKER_DENIED")
    return result["bearer"]


class NonceBroker:
    def __init__(self, path, original_client, m1_issuer, review_issuer, read_task):
        assert os.geteuid() == 0
        self.path, self.client, self.m1, self.review = (
            path,
            original_client,
            m1_issuer,
            review_issuer,
        )
        self.read_task = read_task
        self.slots = BoundedSemaphore(4)
        self.socket = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self.socket.bind(path)
        os.chmod(path, 0o600)
        os.chown(path, 10003, 10003)
        self.socket.listen(4)

    def serve(self):
        while True:
            connection, _ = self.socket.accept()
            if not self.slots.acquire(blocking=False):
                connection.close()
                continue
            Thread(target=self.bounded_one, args=(connection,), daemon=True).start()

    def bounded_one(self, connection):
        try:
            self.one(connection)
        finally:
            self.slots.release()

    def one(self, connection):
        with connection:
            connection.settimeout(5)
            try:
                _, uid, _ = struct.unpack(
                    "3i", connection.getsockopt(socket.SOL_SOCKET, socket.SO_PEERCRED, 12)
                )
                assert uid == 10003
                value = json.loads(connection.makefile("rb").readline(32769))
                assert (
                    set(value) == {"operation", "task", "nonce"}
                    and type(value["nonce"]) is str
                    and 16 <= len(value["nonce"]) <= 256
                )
                task = TaskHandle(**value["task"])
                assert task.tenant_id == "tenant-test" and task.source_ref.startswith(
                    "g1-recorded-"
                )
                # Review is issued while current_worker holds original PG
                # authority locks. A second APP status call would invert that
                # lock order. The trusted root reader checks original rows with
                # plain SELECT; the caller must keep current_worker open.
                if value["operation"] == "m1":
                    self.client.status(task)
                elif value["operation"] == "review":
                    self.read_task(task)
                else:
                    raise ValueError("OPERATION")
                now = int(time.time())
                if value["operation"] == "m1":
                    token = self.m1.token(
                        {"iat": now, "nbf": now, "exp": now + 120, "nonce": value["nonce"]}
                    )
                elif value["operation"] == "review":
                    token = self.review.token("g1-controlled-reviewer", value["nonce"])
                else:
                    raise ValueError("OPERATION")
                result = {"bearer": token}
            except Exception:
                import traceback

                traceback.print_exc()
                result = {"error": "G1_CONTROLLED_BROKER_DENIED"}
            connection.sendall(json.dumps(result).encode() + b"\n")
