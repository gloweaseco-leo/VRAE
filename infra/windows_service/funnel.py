"""Windows raw TCP Funnel operations; TLS always terminates in VRAE."""
import argparse
import json
from pathlib import Path
import re
import socket
import subprocess
from infra.windows_service.host import put_private

TAILSCALE = Path("C:/Program Files/Tailscale/tailscale.exe")


def invoke(*args):
    return subprocess.run([str(TAILSCALE), *args], capture_output=True, check=True).stdout


def identity():
    state = json.loads(invoke("status", "--json"))
    hostname = state.get("Self", {}).get("DNSName", "").rstrip(".").lower()
    if state.get("BackendState") != "Running" or not state.get("Self", {}).get("Online"):
        raise PermissionError("TAILSCALE_REAL_ACCOUNT_LOGIN_REQUIRED")
    if not re.fullmatch(r"[a-z0-9-]+(?:\.[a-z0-9-]+)+\.ts\.net", hostname):
        raise PermissionError("ACTUAL_TAILSCALE_FQDN_REQUIRED")
    return hostname


def settings():
    return json.loads(invoke("funnel", "status", "--json"))


def expose(hostname, api_port, review_port):
    old = settings()
    expected = {"443": "127.0.0.1:" + str(api_port), "8443": "127.0.0.1:" + str(review_port)}
    for port, target in expected.items():
        current = old.get("TCP", {}).get(port)
        if current and current != {"TCPForward": target}:
            raise PermissionError("EXISTING_FUNNEL_LISTENER_CONFLICT")
        with socket.create_connection(("127.0.0.1", int(target.split(":")[1])), timeout=5):
            pass
    changed = []
    try:
        for port, target in expected.items():
            if port not in old.get("TCP", {}):
                invoke("funnel", "--bg", "--yes", "--tcp=" + port, "tcp://" + target)
                changed.append(port)
        actual = settings()
        for port, target in expected.items():
            if actual.get("TCP", {}).get(port) != {"TCPForward": target}:
                raise PermissionError("RAW_TCP_PASSTHROUGH_NOT_ACTIVE")
            if actual.get("AllowFunnel", {}).get(hostname + ":" + port) is not True:
                raise PermissionError("PUBLIC_FUNNEL_NOT_ACTIVE")
    except Exception:
        # Roll back only ports created by this operation, never reset other services.
        for port in changed:
            invoke("funnel", "--tcp=" + port, "off")
        raise
    return {"diagnosis": "https://" + hostname, "reports": "https://" + hostname + ":8443",
            "transport": "RAW_TCP_END_TO_END_MTLS", "external_acceptance": "NOT_YET_VERIFIED"}


def main():
    p = argparse.ArgumentParser()
    p.add_argument("action", choices=["status", "install-cert", "up", "down"])
    p.add_argument("--api-port", type=int, default=28769)
    p.add_argument("--review-port", type=int, default=28770)
    p.add_argument("--distro", default="VRAE-Local")
    p.add_argument("--config", default="/etc/vrae-service")
    p.add_argument("--operator-image")
    p.add_argument("--name", default="vrae-windows")
    a = p.parse_args()
    if a.action == "status":
        state = json.loads(invoke("status", "--json"))
        print(json.dumps({"version": state.get("Version"), "state": state.get("BackendState"),
                          "hostname": state.get("Self", {}).get("DNSName", "").rstrip(".") or None}))
        return
    hostname = identity()
    if a.action == "install-cert":
        # Capture both PEMs in memory and send straight to ext4 through stdin.
        # No private certificate material is written to NTFS or printed.
        raw = invoke("cert", "--cert-file=-", "--key-file=-", hostname)
        certificates = re.findall(rb"-----BEGIN CERTIFICATE-----.*?-----END CERTIFICATE-----", raw, re.S)
        keys = re.findall(rb"-----BEGIN (?:EC |RSA |)PRIVATE KEY-----.*?-----END (?:EC |RSA |)PRIVATE KEY-----", raw, re.S)
        if not certificates or len(keys) != 1:
            raise ValueError("TAILSCALE_CERTIFICATE_OUTPUT_REQUIRED")
        if a.operator_image:
            from infra.windows_service.private_host import put_private as store
            store(a.operator_image, a.name, "server.pem", b"\n".join(certificates) + b"\n")
            store(a.operator_image, a.name, "server-key.pem", keys[0] + b"\n")
        else:
            put_private(a.distro, a.config, "server.pem", b"\n".join(certificates) + b"\n")
            put_private(a.distro, a.config, "server-key.pem", keys[0] + b"\n")
        result = {"hostname": hostname, "private_key_location": "WSL2_EXT4_ROOT_ONLY"}
    elif a.action == "up":
        if any(type(n) is not int or not 1024 <= n <= 65535 for n in (a.api_port,a.review_port)) or a.api_port == a.review_port:
            raise ValueError("DISTINCT_LOOPBACK_PORTS_REQUIRED")
        result = expose(hostname, a.api_port, a.review_port)
    else:
        old = settings()
        for port, local in (("443",a.api_port),("8443",a.review_port)):
            if old.get("TCP", {}).get(port) == {"TCPForward": "127.0.0.1:" + str(local)}:
                invoke("funnel", "--tcp=" + port, "off")
        result = {"owned_funnel_ports_stopped": True}
    print(json.dumps(result))


if __name__ == "__main__":
    main()
