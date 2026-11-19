"""Infrastructure-only native API process. No source collector or generic HTTP proxy."""
import http.client
import ipaddress
import json
import re
import socket
import ssl
import sys

MAX = 131072


def main():
    envelope = json.loads(sys.stdin.buffer.read(65537))
    workspace, key = envelope['workspace'], envelope['key']
    if (not re.fullmatch(r'[a-z0-9][a-z0-9-]{0,62}', workspace)
            or type(key) is not str or not 16 <= len(key) <= 256
            or not re.fullmatch(r'[A-Za-z0-9._~+/-]+=*', key)
            or type(envelope['timeout_ms']) is not int
            or not 1 <= envelope['timeout_ms'] <= 30000):
        return 1
    host = workspace + '.cn-beijing.maas.aliyuncs.com'
    body = json.dumps(envelope['body'], separators=(',', ':')).encode()
    if len(body) > 48000 or envelope['body']['model'] != 'qwen3.7-plus-2026-05-26':
        return 1
    addresses = {str(item[4][0]) for item in socket.getaddrinfo(host, 443, type=socket.SOCK_STREAM)}
    if not addresses:
        return 1
    for value in addresses:
        ip = ipaddress.ip_address(value)
        if (not ip.is_global or ip.is_multicast or ip.is_unspecified
                or isinstance(ip, ipaddress.IPv6Address) and (
                    ip.ipv4_mapped is not None or ip.sixtofour is not None
                    or ip.teredo is not None or ip in ipaddress.ip_network('64:ff9b::/96')
                    or ip in ipaddress.ip_network('64:ff9b:1::/48'))):
            return 1
    pinned = sorted(addresses)[0]

    class Pinned(http.client.HTTPSConnection):
        def connect(self):
            raw = socket.create_connection((pinned, 443), timeout=self.timeout)
            try:
                if ipaddress.ip_address(raw.getpeername()[0]) != ipaddress.ip_address(pinned):
                    raise ValueError()
                self.sock = ssl.create_default_context().wrap_socket(raw, server_hostname=host)
            except BaseException:
                raw.close()
                raise

    connection = Pinned(host, timeout=envelope['timeout_ms'] / 1000)
    try:
        connection.request('POST', '/compatible-mode/v1/chat/completions', body=body,
                           headers={'Content-Type': 'application/json', 'Authorization': 'Bearer ' + key})
        response = connection.getresponse()
        # No redirects, retries, tool execution, cookies, proxies or remote error logging.
        content = response.read(MAX + 1) if response.status == 200 else b''
        if len(content) > MAX:
            return 1
        sys.stdout.write(json.dumps({'status': response.status, 'body': content.decode('utf-8')}))
        return 0
    finally:
        connection.close()


if __name__ == '__main__':
    try:
        sys.exit(main())
    except Exception:
        sys.exit(1)
