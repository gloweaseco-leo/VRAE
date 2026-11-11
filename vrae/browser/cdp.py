"""Bounded, correlated CDP over private Unix IPC; no browser TCP listener."""
import asyncio
import json

from vrae.collection.errors import CollectionError


class CDP:
    def __init__(self, reader, writer):
        self.reader, self.writer = reader, writer
        self.pending: dict[int, asyncio.Future] = {}
        self.events: asyncio.Queue = asyncio.Queue(maxsize=256)
        self.serial = 0
        self.task = asyncio.create_task(self.receive())

    @classmethod
    async def connect(cls, path='/ipc/cdp.sock'):
        connect = getattr(asyncio, 'open_unix_connection', None)
        if connect is None:
            raise CollectionError('SOURCE_NOT_ALLOWED')
        reader, writer = await connect(path, limit=8_000_000)
        return cls(reader, writer)

    async def receive(self):
        try:
            while True:
                line = await self.reader.readline()
                if not line or len(line) > 8_000_000:
                    raise CollectionError('LIMIT_EXCEEDED')
                message = json.loads(line)
                if 'id' in message:
                    future = self.pending.pop(message['id'], None)
                    if future is not None and not future.done():
                        if 'error' in message:
                            future.set_exception(CollectionError('HTTP_PROTOCOL_ERROR'))
                        else:
                            future.set_result(message.get('result', {}))
                else:
                    self.events.put_nowait(message)
        except (Exception, asyncio.CancelledError):
            for future in self.pending.values():
                if not future.done():
                    future.set_exception(CollectionError('EVIDENCE_INSUFFICIENT'))
            self.pending.clear()
            self.writer.close()

    async def call(self, method, params=None, session=None):
        if len(self.pending) >= 32 or self.task.done():
            raise CollectionError('LIMIT_EXCEEDED')
        self.serial += 1
        message = {'id': self.serial, 'method': method, 'params': params or {}}
        if session is not None:
            message['sessionId'] = session
        future = asyncio.get_running_loop().create_future()
        self.pending[self.serial] = future
        self.writer.write(json.dumps(message).encode() + b'\n')
        await self.writer.drain()
        try:
            return await asyncio.wait_for(future, 5)
        except TimeoutError as exc:
            raise CollectionError('EVIDENCE_INSUFFICIENT') from exc
        finally:
            self.pending.pop(message['id'], None)

    async def close(self):
        self.task.cancel()
        self.writer.close()
        await asyncio.gather(self.task, return_exceptions=True)
