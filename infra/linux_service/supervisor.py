"""Root namespace bootstrap; existing API/Worker/REVIEW/AI run as distinct UIDs.

No fixtures, test issuer, customer grant or provider credentials are generated.
"""

import hashlib
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import time
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat
from contracts.l2_launch.contract import canonical, digest
from integration.authorized_targets.source_authority import root_document, verify, TRUST, DEPLOYMENT
from infra.authorized_targets.egress_policy import install

INPUT = Path("/operator")
RUNTIME = Path("/run/service")
ENV = {
    "PATH": "/usr/local/bin:/usr/bin:/bin",
    "PYTHONPATH": "/work",
    "PYTHONUNBUFFERED": "1",
    "PYTHONDONTWRITEBYTECODE": "1",
    "PYTHONUTF8": "1",
    "HOME": "/tmp",
}
SERVICES = {
    "api": (10001, "integration.authorized_targets.http"),
    "worker": (65532, "integration.authorized_targets.worker"),
    "review": (10007, "integration.authorized_targets.report_api"),
    "ai": (10008, "infra.linux_service.ai_loop"),
}


def private(path):
    s = path.lstat()
    if path.is_symlink() or not path.is_file() or s.st_uid != 0 or s.st_mode & 0o077:
        raise PermissionError("ROOT_PRIVATE_INPUT_REQUIRED")
    return path.read_bytes()


def write(path, data, uid=0, mode=0o600):
    path.write_bytes(data)
    path.chmod(mode)
    os.chown(path, uid, uid)


def command(*args, check=True):
    return subprocess.run(args, capture_output=True, check=check)


def clear_chain(tool, chain, uid):
    jump = [tool, "-w", "3", "-D", "OUTPUT", "-m", "owner", "--uid-owner", str(uid), "-j", chain]
    while command(*jump, check=False).returncode == 0:
        pass
    command(tool, "-w", "3", "-F", chain, check=False)
    command(tool, "-w", "3", "-X", chain, check=False)


def fence(uid, ports):
    for tool in ("iptables", "ip6tables"):
        chain = "VRAE_SERVICE_" + str(uid)
        clear_chain(tool, chain, uid)
        command(tool, "-w", "3", "-N", chain)
        if tool == "iptables":
            for port in ports:
                command(
                    tool,
                    "-w",
                    "3",
                    "-A",
                    chain,
                    "-p",
                    "tcp",
                    "-d",
                    "127.0.0.1",
                    "--dport",
                    str(port),
                    "-j",
                    "ACCEPT",
                )
            # Only replies on accepted HTTPS connections; this is not new egress.
            command(
                tool,
                "-w",
                "3",
                "-A",
                chain,
                "-p",
                "tcp",
                "-m",
                "conntrack",
                "--ctstate",
                "ESTABLISHED",
                "-j",
                "ACCEPT",
            )
        command(tool, "-w", "3", "-A", chain, "-j", "REJECT")
        command(
            tool,
            "-w",
            "3",
            "-I",
            "OUTPUT",
            "1",
            "-m",
            "owner",
            "--uid-owner",
            str(uid),
            "-j",
            chain,
        )


def provision(name, uid):
    cfg = json.loads(private(INPUT / (name + ".json")))
    if name == "worker":
        if cfg["workload"] != {"kind": "AUTHORIZED_EGRESS_V2"}:
            raise ValueError("BOUNDED_WORKER_REQUIRED")
        cfg["poll_interval_seconds"] = 0.5
    expected = {"api": None, "review": "REVIEW", "ai": "AI", "worker": None}[name]
    if any(
        b.get("port") != expected or b["kind"] != ("WORKER" if name == "worker" else "APP")
        for b in cfg["bindings"]
    ):
        raise ValueError("SEPARATE_SERVICE_ROLES_REQUIRED")
    directory = RUNTIME / name
    directory.mkdir(mode=0o700)
    for field in ("certificate", "certificate_key"):
        if field in cfg:
            filename = cfg[field]
            if Path(filename).name != filename:
                raise ValueError("PRIVATE_TLS_FILENAME_REQUIRED")
            dst = directory / filename
            write(dst, private(INPUT / filename), uid)
            cfg[field] = str(dst)
    if name in ("api", "review"):
        if cfg["transport"].get("mtls") is not True:
            raise ValueError("MTLS_REQUIRED")
        cfg["transport"]["client_ca"] = "/run/vrae-targets/client-ca.pem"
    if name == "review":
        cfg["ledger_root"] = "/ledger"
    write(directory / "config.json", canonical(cfg), uid)
    os.chown(directory, uid, uid)
    return directory / "config.json"


def bootstrap():
    if os.geteuid() != 0 or Path("/var/run/docker.sock").exists():
        raise PermissionError("NAMESPACE_PARENT_REQUIRED")
    RUNTIME.mkdir(mode=0o700, exist_ok=True)
    # Traversal only; each individual service directory remains private.
    RUNTIME.chmod(0o711)
    TRUST.parent.mkdir(mode=0o755, exist_ok=True)
    write(TRUST, private(INPUT / "trust.json"), mode=0o444)
    grant = verify(
        json.loads(private(INPUT / "deployment-intent.json")),
        "DEPLOYMENT_OWNER",
        json.loads(private(INPUT / "manifest.json"))["source_class"],
    )
    if (
        grant["contract"] != "vrae.linux-service-intent.v1"
        or grant["deployment_go"] != "GRANTED"
        or grant["source_network_fee_go"] != "GRANTED"
        or grant["model_fee_go"] != "NOT_GRANTED"
    ):
        raise PermissionError("EXPLICIT_DEPLOYMENT_INTENT_REQUIRED")
    cfg = json.loads(private(INPUT / "manifest.json"))
    if cfg["source_sha"] != Path("/work/infra/linux_service/source-sha").read_text().strip():
        raise PermissionError("DEPLOYMENT_SOURCE_MISMATCH")
    for filename in ("source-ca.pem", "client-ca.pem"):
        write(TRUST.parent / filename, private(INPUT / filename), mode=0o444)
    key = Ed25519PrivateKey.from_private_bytes(
        bytes.fromhex(private(INPUT / "deployment-key").decode().strip())
    )
    envelope = json.loads(private(INPUT / "deployment-intent.json"))
    registered = root_document(TRUST)["keys"][envelope["key_id"]]
    if key.public_key().public_bytes(Encoding.Raw, PublicFormat.Raw).hex() != registered["public"]:
        raise PermissionError("DEPLOYMENT_KEY_MISMATCH")
    for tool in ("iptables", "ip6tables"):
        clear_chain(tool, "VRAE_TARGET_V2", 65532)
    inode = os.stat("/proc/self/ns/net").st_ino
    policy = install(
        namespace_inode=inode,
        parent_network_mode=cfg["network_mode"],
        interfaces=sorted(os.listdir("/sys/class/net")),
        destination_ips=grant["destination_ips"],
        nameservers=grant["nameservers"],
        network_internal=cfg.get("network_internal", False),
    )
    document = {k: v for k, v in grant.items() if k not in ("destination_ips",)}
    document.update(
        contract="vrae.bounded-egress-deployment.v2",
        namespace_inode=inode,
        interfaces=sorted(os.listdir("/sys/class/net")),
        parent_network_mode=cfg["network_mode"],
        network_internal=cfg.get("network_internal", False),
        network_id=cfg.get("network_id"),
        cafile="/run/vrae-targets/source-ca.pem",
        ca_sha256=hashlib.sha256(private(INPUT / "source-ca.pem")).hexdigest(),
        firewall_policy_sha256=policy.pop("policy_sha256"),
        firewall_policy=policy,
        permitted_destination_ips=grant["destination_ips"],
    )
    signed = {
        "key_id": envelope["key_id"],
        "document": document,
        "signature": key.sign(canonical(document)).hex(),
    }
    write(DEPLOYMENT, canonical(signed), mode=0o444)
    for name, (uid, _) in SERVICES.items():
        if name != "worker":
            fence(uid, [5432])
    ledger = Path("/ledger")
    if ledger.stat().st_uid == 0:
        ledger.chmod(0o700)
        os.chown(ledger, 10007, 10007)
    elif ledger.stat().st_uid != 10007 or ledger.stat().st_mode & 0o077:
        raise PermissionError("PRIVATE_LEDGER_REQUIRED")
    configs = {name: provision(name, uid) for name, (uid, _) in SERVICES.items()}
    if cfg.get("controlled_fixture"):
        if (
            cfg["source_class"] != "CONTROLLED_NON_CUSTOMER"
            or cfg.get("network_internal") is not True
        ):
            raise PermissionError("CONTROLLED_FIXTURE_ONLY")
        SERVICES["controlled-source"] = (0, "infra.linux_service.local_site")
        configs["controlled-source"] = INPUT / "site.json"
    return configs, digest(signed)


def main():
    configs, proof = bootstrap()
    stop = False
    children = {}
    failures = {name: 0 for name in SERVICES}

    def halt(*_):
        nonlocal stop
        stop = True

    signal.signal(signal.SIGTERM, halt)
    signal.signal(signal.SIGINT, halt)
    try:
        while not stop:
            for name, (uid, module) in SERVICES.items():
                child = children.get(name)
                if child is None or child.poll() is not None:
                    if child is not None:
                        failures[name] += 1
                        if failures[name] > 5:
                            raise RuntimeError("SERVICE_RESTART_BUDGET_EXHAUSTED")
                    children[name] = subprocess.Popen(
                        [sys.executable, "-m", module, "--config", str(configs[name])],
                        user=uid,
                        group=uid,
                        extra_groups=[],
                        env=ENV,
                        stdin=subprocess.DEVNULL,
                    )
            Path("/run/service/ready.json").write_bytes(
                canonical(
                    {
                        "phase": "SUPERVISED",
                        "deployment_sha256": proof,
                        "children": {n: p.pid for n, p in children.items()},
                        "model_dispatch_enabled": False,
                    }
                )
            )
            time.sleep(1)
    finally:
        for name, child in children.items():
            if child.poll() is None:
                uid = SERVICES[name][0]
                subprocess.run(
                    [
                        sys.executable,
                        "-c",
                        "import os,sys,signal;os.kill(int(sys.argv[1]),signal.SIGTERM)",
                        str(child.pid),
                    ],
                    user=uid,
                    group=uid,
                    extra_groups=[],
                    env=ENV,
                    check=False,
                )
        for child in children.values():
            try:
                child.wait(timeout=10)
            except subprocess.TimeoutExpired:
                uid = next(SERVICES[n][0] for n, c in children.items() if c is child)
                subprocess.run(
                    [
                        sys.executable,
                        "-c",
                        "import os,sys,signal;os.kill(int(sys.argv[1]),signal.SIGKILL)",
                        str(child.pid),
                    ],
                    user=uid,
                    group=uid,
                    extra_groups=[],
                    env=ENV,
                    check=False,
                )


if __name__ == "__main__":
    main()
