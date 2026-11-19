"""Minimal Docker host operations. No cloud account, DNS or customer scan is created."""

import argparse
import hashlib
import json
import io
import tarfile
import os
from pathlib import Path
import re
import subprocess
import time

LABEL = "vrae.linux_service"
ROOT = Path(__file__).resolve().parents[2]
PG_IMAGE = (ROOT / "infra/ra4a/image.txt").read_text().strip()


def docker(*args, input=None, check=True):
    return subprocess.run(
        ["docker", *map(str, args)], input=input, capture_output=True, check=check
    ).stdout


def inspect(kind, name):
    raw = docker(kind, "inspect", name, check=False)
    items = json.loads(raw) if raw.strip() else []
    return items[0] if items else None


def names(name):
    if not re.fullmatch(r"vrae-[a-z0-9][a-z0-9-]{1,40}", name):
        raise ValueError("VRAE_DEPLOYMENT_NAME_REQUIRED")
    return {
        k: name + "-" + k
        for k in ("pg", "runtime", "data", "ledger", "net", "operator", "relay", "ingress", "ai", "model-net")
    }


def owned(kind, name, owner):
    d = inspect(kind, name)
    if d is None:
        return False
    labels = d.get("Labels", {}) if kind in ("volume", "network") else d["Config"].get("Labels", {})
    if (labels or {}).get(LABEL) != owner:
        raise PermissionError("RESOURCE_OWNERSHIP_MISMATCH")
    return d


def config(path):
    root = Path(path).resolve(strict=True)
    if not root.is_dir() or root.is_symlink():
        raise ValueError("PRIVATE_CONFIG_DIRECTORY_REQUIRED")
    if os.name == "posix" and (root.stat().st_uid != 0 or root.stat().st_mode & 0o077):
        raise PermissionError("ROOT_PRIVATE_CONFIG_REQUIRED")
    d = json.loads((root / "manifest.json").read_bytes())
    if d["contract"] != "vrae.linux-service.v1":
        raise ValueError("SERVICE_CONFIG_REQUIRED")
    if os.name != "posix" and d["source_class"] != "CONTROLLED_NON_CUSTOMER":
        raise PermissionError("CUSTOMER_DEPLOYMENT_REQUIRES_LINUX_ROOT")
    if not re.fullmatch(r"sha256:[0-9a-f]{64}", d["image"]):
        raise ValueError("IMMUTABLE_IMAGE_REQUIRED")
    image = inspect("image", d["image"])
    if image["Config"].get("Labels", {}).get("vrae.source_sha") != d["source_sha"]:
        raise ValueError("IMAGE_SOURCE_MISMATCH")
    for f in root.iterdir():
        if f.is_symlink() or not f.is_file():
            raise ValueError("FLAT_PRIVATE_INPUTS_REQUIRED")
        if os.name == "posix" and (f.stat().st_uid != 0 or f.stat().st_mode & 0o077):
            raise PermissionError("ROOT_PRIVATE_INPUT_REQUIRED")
    return root, d


def start_runtime(owner, n, root, d):
    net = owned("network", n["net"], owner)
    if bool(net["Internal"]) != (d["network_mode"] == "internal"):
        raise PermissionError("NETWORK_MODE_MISMATCH")
    # Facts supplied by the host operator, not a workload's self-report.
    d.update(network_id=net["Id"], network_internal=bool(net["Internal"]))
    if owned('container', n['ai'], owner):
        docker('stop', '-t', '30', n['ai'])
        docker('rm', n['ai'])
    if d.get('isolated_model_runtime') is True:
        # Fixed private PG wire endpoint, never an exposed or dynamic SQL port.
        pg = owned('container', n['pg'], owner)
        endpoint = {'host': pg['NetworkSettings']['Networks'][n['net']]['IPAddress'], 'port': 15432}
        if root is not None:
            (root / 'ai-pg-endpoint.json').write_text(json.dumps(endpoint))
            (root / 'ai-pg-endpoint.json').chmod(0o600)
    if root is None:
        # Existing ext4 operator material never crosses back into NTFS. This
        # update contains only inspected topology/image metadata, no secret.
        update = {'manifest': d}
        if d.get('isolated_model_runtime') is True:
            update['endpoint'] = endpoint
        docker('run', '--rm', '-i', '--network', 'none', '--read-only', '--cap-drop', 'ALL',
            '--mount', 'type=volume,src=' + n['operator'] + ',dst=/operator', d['image'],
            'python', '-c',
            "import sys,json,os;from pathlib import Path;d=json.load(sys.stdin);"
            "p=Path('/operator/manifest.json');p.write_text(json.dumps(d['manifest']));p.chmod(0o600);"
            "p=Path('/operator/ai-pg-endpoint.json');p.write_text(json.dumps(d['endpoint']));p.chmod(0o600)",
            input=json.dumps(update).encode())
    else:
        (root / "manifest.json").write_text(json.dumps(d))
        (root / "manifest.json").chmod(0o600)
    if not owned("volume", n["operator"], owner):
        docker("volume", "create", "--label", LABEL + "=" + owner, n["operator"])
    archive = io.BytesIO()
    with tarfile.open(fileobj=archive, mode="w:gz") as tar:
        for path in (() if root is None else root.iterdir()):
            info = tarfile.TarInfo(path.name)
            raw = path.read_bytes()
            info.size = len(raw)
            info.mode = 0o600
            tar.addfile(info, io.BytesIO(raw))
    if root is not None:
        stage_operator(d, n, archive.getvalue())
    docker(
        "run", "--rm", "--network", "container:" + n["pg"], "--read-only", "--cap-drop", "ALL",
        "--tmpfs", "/run/vrae-targets:rw,nosuid,nodev,size=2m", "--mount",
        "type=volume,src=" + n["operator"] + ",dst=/operator,readonly", d["image"],
        "python", "-m", "infra.linux_service.initialize",
    )
    old = owned("container", n["runtime"], owner)
    if old:
        docker("stop", "-t", "30", n["runtime"])
        docker("rm", n["runtime"])
    launch_runtime(owner, n, d)


def stage_operator(d, n, archive):
    docker(
        "run",
        "--rm",
        "-i",
        "--network",
        "none",
        "--read-only",
        "--cap-drop",
        "ALL",
        "--mount",
        "type=volume,src=" + n["operator"] + ",dst=/inputs",
        d["image"],
        "python",
        "-c",
        "import sys,tarfile,os;tarfile.open(fileobj=sys.stdin.buffer,mode='r|gz').extractall('/inputs',filter='data');os.chmod('/inputs',0o700)",
        input=archive,
    )


def launch_runtime(owner, n, d):
    docker(
        "run",
        "-d",
        "--name",
        n["runtime"],
        "--label",
        LABEL + "=" + owner,
        "--restart",
        "unless-stopped",
        "--network",
        "container:" + n["pg"],
        "--read-only",
        "--cap-drop",
        "ALL",
        "--cap-add",
        "SETUID",
        "--cap-add",
        "SETGID",
        "--cap-add",
        "CHOWN",
        "--cap-add",
        "NET_ADMIN",
        "--security-opt",
        "no-new-privileges",
        "--pids-limit",
        "160",
        "--memory",
        "768m",
        "--cpus",
        "2",
        "--tmpfs",
        "/tmp:rw,nosuid,nodev,size=64m",
        "--tmpfs",
        "/run/service:rw,nosuid,nodev,size=8m",
        "--tmpfs",
        "/run/vrae-reports:rw,nosuid,nodev,size=2m",
        "--tmpfs",
        "/run/vrae-targets:rw,nosuid,nodev,size=2m",
        "--mount",
        "type=volume,src=" + n["operator"] + ",dst=/operator,readonly",
        "--mount",
        "type=volume,src=" + n["ledger"] + ",dst=/ledger",
        d["image"],
    )


def activate_model(owner, image):
    """Upgrade this SAME running service from existing Linux-private materials.

    No source renewal, key/fee grant fabrication, PG replacement or NTFS secret
    export. The operator stages the independently signed model grant beforehand.
    """
    n = names(owner)
    for kind, key in (('container', 'pg'), ('container', 'runtime'),
                      ('volume', 'operator'), ('volume', 'ledger')):
        if not owned(kind, n[key], owner):
            raise PermissionError('EXISTING_DEPLOYMENT_REQUIRED')
    if type(image) is not str or not re.fullmatch(r'sha256:[0-9a-f]{64}', image):
        raise ValueError('IMMUTABLE_IMAGE_REQUIRED')
    item = inspect('image', image)
    if item is None:
        raise ValueError('IMMUTABLE_IMAGE_REQUIRED')
    sha = item['Config']['Labels'].get('vrae.source_sha')
    if not re.fullmatch(r'[0-9a-f]{40}', sha or ''):
        raise ValueError('IMAGE_SOURCE_MISMATCH')
    d = json.loads(docker('exec', n['runtime'], 'cat', '/operator/manifest.json'))
    d.update(previous={'image': d['image'], 'source_sha': d['source_sha']},
             image=image, source_sha=sha, isolated_model_runtime=True)
    start_runtime(owner, n, None, d)
    start_ai(owner, n, d)
    return {'source_sha': sha, 'same_pg': n['pg'], 'same_ledger': n['ledger'],
            'ai_container': n['ai'], 'model_go_attested': False}


def up(owner, path):
    root, d = config(path)
    n = names(owner)
    if not owned("network", n["net"], owner):
        docker(
            "network",
            "create",
            *(["--internal"] if d["network_mode"] == "internal" else []),
            "--label",
            LABEL + "=" + owner,
            n["net"],
        )
    for key in ("data", "ledger"):
        if not owned("volume", n[key], owner):
            docker("volume", "create", "--label", LABEL + "=" + owner, n[key])
    pg = owned("container", n["pg"], owner)
    if pg and pg["HostConfig"].get("PortBindings"):
        # Migrate an earlier direct-publish container without touching its data.
        if owned("container", n["runtime"], owner):
            docker("stop", "-t", "30", n["runtime"])
        docker("stop", "-t", "30", n["pg"])
        docker("rm", n["pg"])
    if not owned("container", n["pg"], owner):
        # Publish only explicit operator-selected addresses; PG5432 is never mapped.
        ports = d.get("publish", [])
        for value in ports:
            if not re.fullmatch(r"(?:[0-9]{1,3}\.){3}[0-9]{1,3}:[0-9]{1,5}:(8769|8770)", value):
                raise ValueError("EXPLICIT_IPV4_API_PUBLISH_REQUIRED")
        docker(
            "run",
            "-d",
            "--name",
            n["pg"],
            "--label",
            LABEL + "=" + owner,
            "--restart",
            "unless-stopped",
            "--network",
            n["net"],
            "--network-alias",
            "vrae-api",
            "--env",
            "POSTGRES_DB=vrae_ra4a_p1",
            "--env",
            "POSTGRES_PASSWORD_FILE=/run/pg-password",
            "--mount",
            "type=bind,src=" + str(root / "pg-password") + ",dst=/run/pg-password,readonly",
            "--mount",
            "type=volume,src=" + n["data"] + ",dst=/var/lib/postgresql/data",
            PG_IMAGE,
            "postgres",
            "-c",
            "listen_addresses=127.0.0.1",
        )
    else:
        docker("start", n["pg"])
    wait_pg(n)
    start_runtime(owner, n, root, d)
    if d.get('isolated_model_runtime') is True:
        start_ai(owner, n, d)
    if d.get("publish"):
        start_ingress(owner, n, d)
    return n


def start_ai(owner, n, d):
    # Only the relocated AI loop has a routable namespace. The original PG/
    # Worker namespace stays on its inspected internal network without change.
    if not owned('network', n['model-net'], owner):
        docker('network', 'create', '--label', LABEL + '=' + owner, n['model-net'])
    quota_owner = d.get('model_quota_owner', owner)
    quota_names = names(quota_owner)
    quota_volume = quota_names['ledger']
    owned('volume', quota_volume, quota_owner)
    if quota_owner != owner and d.get('model_quota_shared') is not True:
        raise PermissionError('EXPLICIT_SHARED_QUOTA_REQUIRED')
    quota_mount = 'type=volume,src=' + quota_volume + ',dst=/model-ledger'
    if quota_owner == owner:
        quota_mount += ',volume-subpath=qwen'
    docker('create', '--name', n['ai'], '--label', LABEL + '=' + owner,
        '--restart', 'unless-stopped', '--network', n['model-net'], '--read-only',
        '--cap-drop', 'ALL', '--cap-add', 'SETUID', '--cap-add', 'SETGID',
        '--cap-add', 'CHOWN', '--cap-add', 'NET_ADMIN', '--security-opt', 'no-new-privileges',
        '--pids-limit', '80', '--memory', '512m', '--cpus', '2',
        '--tmpfs', '/tmp:rw,nosuid,nodev,size=32m',
        '--tmpfs', '/run/service:rw,nosuid,nodev,size=8m',
        '--tmpfs', '/run/vrae-targets:rw,nosuid,nodev,size=2m',
        '--mount', 'type=volume,src=' + n['operator'] + ',dst=/operator,readonly',
        '--mount', quota_mount,
        d['image'], 'python', '-m', 'infra.linux_service.ai_bootstrap')
    docker('network', 'connect', n['net'], n['ai'])
    docker('start', n['ai'])


def start_ingress(owner, n, d):
    if not owned("network", n["ingress"], owner):
        docker("network", "create", "--label", LABEL + "=" + owner, n["ingress"])
    if owned("container", n["relay"], owner):
        docker("stop", "-t", "10", n["relay"])
        docker("rm", n["relay"])
    docker(
        "run",
        "-d",
        "--name",
        n["relay"],
        "--label",
        LABEL + "=" + owner,
        "--restart",
        "unless-stopped",
        "--network",
        n["ingress"],
        *[x for p in d["publish"] for x in ("--publish", p)],
        "--read-only",
        "--cap-drop",
        "ALL",
        "--security-opt",
        "no-new-privileges",
        "--user",
        "10009:10009",
        "--pids-limit",
        "64",
        "--memory",
        "64m",
        "--cpus",
        "0.5",
        d["image"],
        "python",
        "-m",
        "infra.linux_service.relay",
    )
    docker("network", "connect", n["net"], n["relay"])


def wait_pg(n):
    end = time.monotonic() + 60
    while time.monotonic() < end:
        if b"accepting connections" in docker(
            "exec", n["pg"], "pg_isready", "-U", "postgres", "-d", "vrae_ra4a_p1", check=False
        ):
            return
        time.sleep(0.5)
    raise RuntimeError("PG_START_TIMEOUT")


def stop(owner):
    n = names(owner)
    for key in ("ai", "relay", "runtime", "pg"):
        if owned("container", n[key], owner):
            docker("stop", "-t", "30", n[key])


def restart(owner, path):
    # Recreate the runtime after PG restart to join its current net namespace.
    stop(owner)
    return up(owner, path)


def upgrade(owner, path, image):
    root, d = config(path)
    if not re.fullmatch(r"sha256:[0-9a-f]{64}", image):
        raise ValueError("IMMUTABLE_IMAGE_REQUIRED")
    item = inspect("image", image)
    previous = {"image": d["image"], "source_sha": d["source_sha"]}
    d.update(image=image, source_sha=item["Config"]["Labels"]["vrae.source_sha"], previous=previous)
    (root / "manifest.json").write_text(json.dumps(d))
    (root / "manifest.json").chmod(0o600)
    # On readiness failure the operator retains explicit rollback coordinates.
    return restart(owner, root)


def rollback(owner, path):
    root, d = config(path)
    previous = d["previous"]
    return upgrade(owner, root, previous["image"])


def volume_archive(volume, image):
    mount = "type=volume,src=" + volume + ",dst=/snapshot,readonly"
    uid = (
        docker(
            "run",
            "--rm",
            "--network",
            "none",
            "--read-only",
            "--cap-drop",
            "ALL",
            "--mount",
            mount,
            image,
            "python",
            "-c",
            "import os;d=os.stat('/snapshot');print(str(d.st_uid)+':'+str(d.st_gid))",
        )
        .decode()
        .strip()
    )
    return docker(
        "run",
        "--rm",
        "--network",
        "none",
        "--read-only",
        "--cap-drop",
        "ALL",
        "--user",
        uid,
        "--mount",
        mount,
        image,
        "python",
        "-c",
        "import sys,tarfile;t=tarfile.open(fileobj=sys.stdout.buffer,mode='w|gz');t.add('/snapshot',arcname='.');t.close()",
    )


def backup(owner, path, destination):
    root, d = config(path)
    n = names(owner)
    out = Path(destination).resolve()
    out.mkdir(mode=0o700, parents=True, exist_ok=False)
    stop(owner)
    try:
        for key in ("data", "ledger"):
            owned("volume", n[key], owner)
            raw = volume_archive(n[key], d["image"])
            target = out / (key + ".tar.gz")
            target.write_bytes(raw)
            target.chmod(0o600)
        receipt = {
            "contract": "vrae.cold-backup.v1",
            "owner": owner,
            "source_sha": d["source_sha"],
            "image": d["image"],
            "quiescent": True,
            "files": {f.name: hashlib.sha256(f.read_bytes()).hexdigest() for f in out.iterdir()},
        }
        (out / "backup.json").write_text(json.dumps(receipt, indent=2))
        (out / "backup.json").chmod(0o600)
    finally:
        up(owner, root)
    return receipt


def restore(owner, path, source):
    root, d = config(path)
    n = names(owner)
    src = Path(source).resolve(strict=True)
    receipt = json.loads((src / "backup.json").read_bytes())
    # Never overwrite existing data or a differently owned resource.
    if any(
        inspect(kind, n[key])
        for kind, key in [
            ("volume", "data"),
            ("volume", "ledger"),
            ("container", "pg"),
            ("container", "runtime"),
        ]
    ):
        raise PermissionError("RESTORE_REQUIRES_NEW_DEPLOYMENT")
    for key in ("data", "ledger"):
        raw = (src / (key + ".tar.gz")).read_bytes()
        if hashlib.sha256(raw).hexdigest() != receipt["files"][key + ".tar.gz"]:
            raise ValueError("BACKUP_HASH_MISMATCH")
    for key in ("data", "ledger"):
        docker("volume", "create", "--label", LABEL + "=" + owner, n[key])
        raw = (src / (key + ".tar.gz")).read_bytes()
        docker(
            "run",
            "--rm",
            "-i",
            "--network",
            "none",
            "--read-only",
            "--cap-drop",
            "ALL",
            "--cap-add",
            "CHOWN",
            "--cap-add",
            "FOWNER",
            "--mount",
            "type=volume,src=" + n[key] + ",dst=/restore",
            d["image"],
            "python",
            "-c",
            "import sys,tarfile;tarfile.open(fileobj=sys.stdin.buffer,mode='r|gz').extractall('/restore',filter=lambda m,p:tarfile.data_filter(m,p).replace(uid=m.uid,gid=m.gid,mode=m.mode&0o777))",
            input=raw,
        )
    return up(owner, root)


def main():
    p = argparse.ArgumentParser()
    p.add_argument(
        "action",
        choices=["up", "stop", "restart", "upgrade", "rollback", "backup", "restore", "status", "activate-model"],
    )
    p.add_argument("--name", required=True)
    p.add_argument("--config")
    p.add_argument("--image")
    p.add_argument("--backup")
    a = p.parse_args()
    if a.action == 'activate-model':
        result = activate_model(a.name, a.image)
    elif a.action == "up":
        result = up(a.name, a.config)
    elif a.action == "stop":
        result = stop(a.name)
    elif a.action == "restart":
        result = restart(a.name, a.config)
    elif a.action == "upgrade":
        result = upgrade(a.name, a.config, a.image)
    elif a.action == "rollback":
        result = rollback(a.name, a.config)
    elif a.action == "backup":
        result = backup(a.name, a.config, a.backup)
    elif a.action == "restore":
        result = restore(a.name, a.config, a.backup)
    else:
        n = names(a.name)
        result = {
            k: bool(owned("container", n[k], a.name))
            and bool(owned("container", n[k], a.name)["State"]["Running"])
            for k in ("pg", "runtime")
        }
    print(json.dumps({"action": a.action, "result": result}))


if __name__ == "__main__":
    main()
