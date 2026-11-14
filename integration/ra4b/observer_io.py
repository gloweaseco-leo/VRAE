"""External, bounded binary observation. Never imported by a workload."""
import hashlib
import http.client
import io
import ctypes
from ctypes import wintypes


class ObserverDropped(RuntimeError):
    """Observation is incomplete; this says nothing about native success."""


def exact(stream, size, *, eof_allowed=False):
    held = bytearray()
    while len(held) < size:
        chunk = stream.read(size - len(held))
        if not chunk:
            if not held and eof_allowed:
                return None
            raise ObserverDropped('TRUNCATED_STREAM')
        held.extend(chunk)
    return bytes(held)


def write_all(stream, raw):
    view = memoryview(raw)
    while view:
        count = stream.write(view)
        if count is None or count <= 0:
            raise ObserverDropped('SHORT_WRITE')
        view = view[count:]


def drain(stream, destination, *, limit=64_000_000):
    digest, count = hashlib.sha256(), 0
    try:
        while True:
            raw = stream.read(65536)
            if not raw:
                return {'eof': True, 'bytes': count, 'sha256': digest.hexdigest(), 'observer_dropped': False}
            count += len(raw)
            if count > limit:
                raise ObserverDropped('OBSERVATION_LIMIT')
            write_all(destination, raw)
            digest.update(raw)
    finally:
        destination.flush()
        stream.close()


def demux(stream, stdout, stderr, *, limit=64_000_000, frame_callback=None):
    """Docker stdcopy framing, preserving byte order separately per stream."""
    total, frames = 0, 0
    counts = {1: 0, 2: 0}
    digests = {1: hashlib.sha256(), 2: hashlib.sha256()}
    while True:
        header = exact(stream, 8, eof_allowed=True)
        if header is None:
            stdout.flush()
            stderr.flush()
            return {'eof': True, 'frames': frames, 'bytes': total, 'observer_dropped': False,
                    'streams': {str(k): {'bytes': counts[k], 'sha256': digests[k].hexdigest()} for k in counts}}
        if header[0] not in (1, 2) or header[1:4] != b'\0\0\0':
            raise ObserverDropped('INVALID_STREAM_HEADER')
        size = int.from_bytes(header[4:], 'big')
        if size > 16_000_000 or total + size > limit:
            raise ObserverDropped('OBSERVATION_LIMIT')
        raw = exact(stream, size)
        target = stdout if header[0] == 1 else stderr
        write_all(target, raw)
        target.flush()
        counts[header[0]] += len(raw)
        digests[header[0]].update(raw)
        total += size
        frames += 1
        if frame_callback:
            frame_callback({'ordinal': frames, 'stream': header[0], 'bytes': size,
                            'payload_sha256': hashlib.sha256(raw).hexdigest()})


class WindowsPipe(io.RawIOBase):
    """Use byte-mode ReadFile: CRT pipe reads can turn EOF into EINVAL."""
    def __init__(self, path):
        super().__init__()
        kernel = ctypes.WinDLL('kernel32', use_last_error=True)
        kernel.CreateFileW.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD, wintypes.LPVOID,
                                      wintypes.DWORD, wintypes.DWORD, wintypes.HANDLE]
        kernel.CreateFileW.restype = wintypes.HANDLE
        kernel.ReadFile.argtypes = [wintypes.HANDLE, wintypes.LPVOID, wintypes.DWORD, ctypes.POINTER(wintypes.DWORD), wintypes.LPVOID]
        kernel.WriteFile.argtypes = kernel.ReadFile.argtypes
        kernel.CloseHandle.argtypes = [wintypes.HANDLE]
        kernel.SetNamedPipeHandleState.argtypes = [wintypes.HANDLE, ctypes.POINTER(wintypes.DWORD), wintypes.LPVOID, wintypes.LPVOID]
        self.kernel = kernel
        self.handle = kernel.CreateFileW(path.replace('/', '\\'), 0xC0000000, 0, None, 3, 0, None)
        if self.handle == wintypes.HANDLE(-1).value:
            raise ctypes.WinError(ctypes.get_last_error())
        mode = wintypes.DWORD(0)
        if not kernel.SetNamedPipeHandleState(self.handle, ctypes.byref(mode), None, None):
            error = ctypes.get_last_error()
            kernel.CloseHandle(self.handle)
            raise ctypes.WinError(error)

    def readable(self):
        return True

    def writable(self):
        return True

    def readinto(self, target):
        if not target:
            return 0
        buffer = (ctypes.c_ubyte * len(target)).from_buffer(target)
        count = wintypes.DWORD()
        okay = self.kernel.ReadFile(self.handle, buffer, len(target), ctypes.byref(count), None)
        if not okay:
            error = ctypes.get_last_error()
            if error in (109, 232, 233):
                return 0
            if error != 234 or not count.value:
                raise ctypes.WinError(error)
        return count.value

    def write(self, raw):
        buffer = ctypes.create_string_buffer(bytes(raw))
        count = wintypes.DWORD()
        if not self.kernel.WriteFile(self.handle, buffer, len(raw), ctypes.byref(count), None):
            raise ctypes.WinError(ctypes.get_last_error())
        return count.value

    def close(self):
        if not self.closed:
            try:
                super().close()
            finally:
                self.kernel.CloseHandle(self.handle)


class NamedPipeHTTP:
    """Buffered HTTP over an exact local pipe, no network or Docker exec."""
    def __init__(self, path='//./pipe/docker_engine'):
        self.raw = WindowsPipe(path)
        self.reader = io.BufferedReader(self.raw, buffer_size=65536)
        self.response = None

    def makefile(self, *args):
        return self.reader

    def request(self, path):
        write_all(self.raw, ('GET ' + path + ' HTTP/1.1\r\nHost: docker\r\nConnection: close\r\n\r\n').encode())
        self.response = http.client.HTTPResponse(self)
        self.response.begin()
        return self.response

    def close(self):
        if self.response is not None:
            self.response.close()
        self.reader.close()
        self.raw.close()
