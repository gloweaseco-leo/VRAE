"""Operate the accepted Linux service inside a private WSL2 ext4 installation."""
import argparse
import json
from pathlib import Path
import re
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]


def wsl(distro, *args, data=None):
    return subprocess.run(
        ["wsl.exe", "-d", distro, "-u", "root", "--", *args],
        input=data, capture_output=True, check=True,
    ).stdout


def private_path(value):
    if not re.fullmatch(r"/etc/vrae-[a-z0-9-]+", value):
        raise ValueError("ROOT_EXT4_CONFIG_PATH_REQUIRED")
    return value


def put_private(distro, directory, filename, value):
    private_path(directory)
    if not re.fullmatch(r"[a-z0-9][a-z0-9.-]{0,80}", filename):
        raise ValueError("FLAT_PRIVATE_FILENAME_REQUIRED")
    program = """
import os, pathlib, sys
root=pathlib.Path(sys.argv[1])
root.mkdir(mode=0o700, parents=True, exist_ok=True)
if root.is_symlink() or root.stat().st_uid != 0 or root.stat().st_mode & 0o077:
    raise PermissionError('ROOT_PRIVATE_EXT4_DIRECTORY_REQUIRED')
if os.statvfs(root).f_flag & os.ST_RDONLY:
    raise PermissionError('WRITABLE_EXT4_REQUIRED')
# Reject Windows drvfs/9p/CIFS mounts, including a bind mount hiding under /etc.
import subprocess
kind=subprocess.check_output(['stat','-f','-c','%T',str(root)]).decode().strip()
if kind not in ('ext2/ext3','ext4'):
    raise PermissionError('EXT4_REQUIRED')
p=root/sys.argv[2]
fd=os.open(p,os.O_WRONLY|os.O_CREAT|os.O_TRUNC|os.O_NOFOLLOW,0o600)
with os.fdopen(fd,'wb') as f:
    os.fchmod(f.fileno(),0o600)
    f.write(sys.stdin.buffer.read())
"""
    wsl(distro, "python3", "-c", program, directory, filename, data=value)


def sync_source(distro):
    raw = subprocess.check_output(
        ["git", "-c", "core.autocrlf=false", "archive", "--format=tar", "HEAD"], cwd=ROOT,
    )
    program = """
import io,os,pathlib,sys,tarfile
root=pathlib.Path('/opt/vrae')
root.mkdir(mode=0o755,parents=True,exist_ok=True)
if root.is_symlink() or root.stat().st_uid!=0:
    raise PermissionError('ROOT_SOURCE_REQUIRED')
with tarfile.open(fileobj=io.BytesIO(sys.stdin.buffer.read())) as archive:
    archive.extractall(root,filter='data')
"""
    wsl(distro, "python3", "-c", program, data=raw)


def control(distro, action, name, config, extra=()):
    private_path(config)
    return wsl(
        distro, "env", "PYTHONPATH=/opt/vrae", "python3", "-B", "-m",
        "infra.linux_service.control", action, "--name", name, "--config", config, *extra,
    )


def main():
    p = argparse.ArgumentParser()
    p.add_argument("action", choices=["sync-source", "put-private", "up", "status", "stop", "restart", "backup", "restore", "rollback"])
    p.add_argument("--distro", default="VRAE-Local")
    p.add_argument("--name", default="vrae-windows")
    p.add_argument("--config", default="/etc/vrae-service")
    p.add_argument("--filename")
    p.add_argument("--backup")
    a = p.parse_args()
    if a.action == "sync-source":
        sync_source(a.distro)
        result = {"source_synced": True}
    elif a.action == "put-private":
        put_private(a.distro, a.config, a.filename, sys.stdin.buffer.read())
        result = {"private_input_stored": True}
    else:
        extra = ("--backup", a.backup) if a.backup else ()
        result = json.loads(control(a.distro, a.action, a.name, a.config, extra))
    print(json.dumps(result))


if __name__ == "__main__":
    main()
