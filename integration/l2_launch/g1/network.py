"""UID egress fences in the exclusively owned network-none namespace only."""

import os
from pathlib import Path
import subprocess


def install():
    assert os.geteuid() == 0 and {p.name for p in Path("/sys/class/net").iterdir()} == {"lo"}
    assert not Path("/var/run/docker.sock").exists()
    allowed = {
        10001: (5432,),
        10002: (5432,),
        10003: (5432, 8765),
        10004: (8766, 8768),
        10006: (8766, 8767),
    }
    for tool in ("iptables", "ip6tables"):
        for uid, ports in allowed.items():
            base = [tool, "-w", "3", "-A", "OUTPUT", "-m", "owner", "--uid-owner", str(uid)]
            if uid != 10002:
                subprocess.run(
                    base + ["-m", "conntrack", "--ctstate", "ESTABLISHED,RELATED", "-j", "ACCEPT"],
                    check=True,
                    capture_output=True,
                )
            if tool == "iptables":
                for port in ports:
                    subprocess.run(
                        base
                        + ["-p", "tcp", "-d", "127.0.0.1", "--dport", str(port), "-j", "ACCEPT"],
                        check=True,
                        capture_output=True,
                    )
            subprocess.run(base + ["-j", "REJECT"], check=True, capture_output=True)
    return {
        "network": "none",
        "interfaces": ["lo"],
        "worker_uid": 10002,
        "worker_only_outbound_tcp_port": 5432,
        "source_target_network": False,
        "host_firewall_modified": False,
    }
