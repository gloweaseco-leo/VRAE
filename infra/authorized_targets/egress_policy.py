"""Trusted namespace parent installs exact kernel egress before dropping UID.

Call only inside a separately inspected owned namespace. No host-wide invocation,
Docker socket in Worker, or runtime process privilege is provided here.
"""

import ipaddress
import os
from pathlib import Path
import subprocess
from contracts.l2_launch.contract import digest
from vrae.collection.resolver import public_addresses


def install(*, namespace_inode, parent_network_mode, interfaces, destination_ips, nameservers):
    if (
        os.geteuid() != 0
        or os.stat("/proc/self/ns/net").st_ino != namespace_inode
        or sorted(os.listdir("/sys/class/net")) != sorted(interfaces)
        or parent_network_mode not in ("none", "isolated-egress")
        or Path("/var/run/docker.sock").exists()
    ):
        raise PermissionError("ISOLATED_PARENT_REQUIRED")
    public_addresses(destination_ips)
    public_addresses(nameservers)
    rules = [{"ip": "127.0.0.1", "protocol": "tcp", "port": 5432}]
    rules += [{"ip": ip, "protocol": "tcp", "port": 443} for ip in sorted(set(destination_ips))]
    rules += [
        {"ip": ip, "protocol": proto, "port": 53}
        for ip in sorted(set(nameservers))
        for proto in ("udp", "tcp")
    ]
    receipt = {
        "contract": "vrae.namespace-egress-policy.v2",
        "namespace_inode": namespace_inode,
        "worker_uid": 65532,
        "parent_network_mode": parent_network_mode,
        "interfaces": sorted(interfaces),
        "rules": rules,
        "default": "REJECT",
    }
    for tool, version in (("iptables", 4), ("ip6tables", 6)):
        chain = "VRAE_TARGET_V2"
        subprocess.run([tool, "-w", "3", "-N", chain], check=True, capture_output=True)
        for rule in rules:
            if ipaddress.ip_address(rule["ip"]).version == version:
                subprocess.run(
                    [
                        tool,
                        "-w",
                        "3",
                        "-A",
                        chain,
                        "-p",
                        rule["protocol"],
                        "-d",
                        rule["ip"],
                        "--dport",
                        str(rule["port"]),
                        "-j",
                        "ACCEPT",
                    ],
                    check=True,
                    capture_output=True,
                )
        subprocess.run(
            [tool, "-w", "3", "-A", chain, "-j", "REJECT"], check=True, capture_output=True
        )
        subprocess.run(
            [
                tool,
                "-w",
                "3",
                "-I",
                "OUTPUT",
                "1",
                "-m",
                "owner",
                "--uid-owner",
                "65532",
                "-j",
                chain,
            ],
            check=True,
            capture_output=True,
        )
    return {**receipt, "policy_sha256": digest(receipt)}
