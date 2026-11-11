"""Unprivileged CDP pipe relay. No network client, policy, secrets or Docker access."""
import asyncio
import errno
import json
import os
from pathlib import Path
import subprocess
import time


def event(name, **fields):
    print(json.dumps({'event': name, 'monotonic_ns': time.monotonic_ns(), **fields}), flush=True)

MAX_MESSAGE = 8_000_000
ARGS = ['chromium', '--headless', '--disable-gpu', '--no-first-run',
        '--disable-background-networking', '--disable-component-update',
        '--disable-sync', '--disable-extensions', '--disable-default-apps',
        '--disable-breakpad', '--noerrdialogs', '--disable-dev-shm-usage',
        '--remote-debugging-pipe', '--user-data-dir=/tmp/profile',
        '--force-webrtc-ip-handling-policy=disable_non_proxied_udp', 'about:blank']


async def main():
    print(json.dumps({'argv': ARGS, 'uid': os.getuid(),
        'status': Path('/proc/self/status').read_text(), 'interfaces': os.listdir('/sys/class/net')}), flush=True)
    probe = Path('/ipc/quota-probe')
    try:
        with probe.open('wb', buffering=0) as stream:
            stream.write(b'x' * 2_097_152)
            stream.write(b'x')
    except OSError as exc:
        if exc.errno != errno.ENOSPC:
            raise
        print('IPC_TMPFS_QUOTA_ENFORCED', flush=True)
    else:
        raise RuntimeError('SECURITY_BLOCKED: unbounded IPC filesystem')
    finally:
        probe.unlink(missing_ok=True)
    # Popen runs before the event loop owns these descriptors: reserve FD3/4 in
    # a tiny exec wrapper rather than relying on preexec_fn from multiple threads.
    child_in, parent_out = os.pipe()
    parent_in, child_out = os.pipe()
    wrapper = ('import os,sys; a,b=map(int,sys.argv[1:3]); '
               'x=os.dup(a); y=os.dup(b); os.dup2(x,3); os.dup2(y,4); '
               'os.set_inheritable(3,True); os.set_inheritable(4,True); '
               'os.execvp(sys.argv[3],sys.argv[3:])')
    child = subprocess.Popen(['python', '-c', wrapper, str(child_in), str(child_out), *ARGS],
                             pass_fds=(child_in, child_out), stderr=None, stdout=None)
    os.close(child_in)
    os.close(child_out)
    async def supervise():
        code = await asyncio.to_thread(child.wait)
        event('chromium_reaped', pid=child.pid, exit_code=code)
        print(json.dumps({'chromium_exit': code, 'container_teardown': True}), flush=True)
        # This process is container PID1. Its exit also tears down the PID namespace,
        # including any remaining zygote/renderer descendants after a browser crash.
        event('pid1_exit', pid=os.getpid(), chromium_exit=code)
        os._exit(0 if code == 0 else 1)
    asyncio.create_task(supervise())
    connected = False

    async def handle(reader, writer):
        nonlocal connected
        if connected:
            writer.close()
            return
        connected = True
        async def to_chrome():
            while True:
                line = await reader.readline()
                if not line:
                    event('control_socket_eof')
                    break
                if len(line) > MAX_MESSAGE:
                    raise ValueError('CDP message limit')
                await asyncio.to_thread(os.write, parent_out, line.rstrip(b'\n') + b'\0')
        async def from_chrome():
            pending = b''
            while True:
                data = await asyncio.to_thread(os.read, parent_in, 65536)
                if not data:
                    break
                pending += data
                if len(pending) > MAX_MESSAGE:
                    raise ValueError('CDP output limit')
                while b'\0' in pending:
                    message, pending = pending.split(b'\0', 1)
                    writer.write(message + b'\n')
                    await writer.drain()
        tasks = [asyncio.create_task(to_chrome()), asyncio.create_task(from_chrome())]
        try:
            await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
        finally:
            event('relay_channel_closed')
            if child.poll() is None:
                event('chromium_kill_sent', pid=child.pid)
                child.kill()
            for task in tasks:
                task.cancel()
            writer.close()
            event('control_socket_close_requested')
    server = await asyncio.start_unix_server(handle, '/ipc/cdp.sock', limit=MAX_MESSAGE)
    os.chmod('/ipc/cdp.sock', 0o660)
    async with server:
        await server.serve_forever()

asyncio.run(main())
