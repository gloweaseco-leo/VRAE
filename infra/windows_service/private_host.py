"""Ephemeral root operator over an owned Docker Desktop WSL2/ext4 volume.

Only this administrator mounts the engine socket; runtime services never do.
"""
import argparse
import io
import json
import re
import subprocess
import sys
import tarfile

LABEL = "vrae.windows-private"


def docker(*args, data=None):
    return subprocess.run(["docker", *args], input=data, capture_output=True, check=True).stdout


def volume(name):
    if not re.fullmatch(r"vrae-[a-z0-9-]{2,40}", name):
        raise ValueError("OWNED_DEPLOYMENT_NAME_REQUIRED")
    vol = name + "-private"
    result = subprocess.run(["docker", "volume", "inspect", vol], capture_output=True)
    if result.returncode:
        docker("volume", "create", "--label", LABEL + "=" + name, vol)
    info = json.loads(docker("volume", "inspect", vol))[0]
    if info.get("Labels", {}).get(LABEL) != name:
        raise PermissionError("PRIVATE_VOLUME_OWNERSHIP_MISMATCH")
    root = info["Mountpoint"]
    if not root.startswith("/var/lib/docker/volumes/") or not root.endswith("/_data"):
        raise PermissionError("DOCKER_EXT4_VOLUME_REQUIRED")
    return vol, root


def invoke(image, name, *args, data=None):
    vol, root = volume(name)
    return docker("run", "--rm", "-i", "--user", "0", "--network", "none", "--read-only",
                  "--cap-drop", "ALL", "--tmpfs", "/tmp:rw,nosuid,nodev,size=8m",
                  "--mount", "type=bind,src=/var/run/docker.sock,dst=/var/run/docker.sock",
                  "--mount", "type=volume,src=" + vol + ",dst=" + root,
                  "--env", "VRAE_PRIVATE_ROOT=" + root, image, *args, data=data)


def put_private(image, name, filename, value):
    if not re.fullmatch(r"[a-z0-9][a-z0-9.-]{0,80}", filename):
        raise ValueError("FLAT_PRIVATE_FILENAME_REQUIRED")
    script = """
import os,pathlib,sys
root=pathlib.Path(os.environ['VRAE_PRIVATE_ROOT'])
root.chmod(0o700)
if root.stat().st_uid!=0 or root.is_symlink():
    raise PermissionError('PRIVATE_ROOT_REQUIRED')
fd=os.open(root/sys.argv[1],os.O_WRONLY|os.O_CREAT|os.O_TRUNC|os.O_NOFOLLOW,0o600)
with os.fdopen(fd,'wb') as f:
    os.fchmod(f.fileno(),0o600)
    f.write(sys.stdin.buffer.read())
"""
    invoke(image, name, "python", "-B", "-c", script, filename, data=value)


def build_operator(runtime, tag):
    # Official CLI only, pinned to the fetched immutable manifest. No new daemon.
    cli_image = "docker@sha256:851f91d241214e7c6db86513b270d58776379aacc5eb9c4a87e5b47115e3065c"
    context = io.BytesIO()
    content = ("FROM " + cli_image + " AS cli\nARG BASE\nFROM " + runtime +
               "\nCOPY --from=cli /usr/local/bin/docker /usr/local/bin/docker\n").encode()
    with tarfile.open(fileobj=context, mode="w:gz") as tar:
        info = tarfile.TarInfo("Dockerfile")
        info.size, info.mode = len(content), 0o644
        tar.addfile(info, io.BytesIO(content))
    docker("build", "-t", tag, "-", data=context.getvalue())


def main():
    p = argparse.ArgumentParser()
    p.add_argument("action", choices=["build-operator", "put-private", "bootstrap", "up", "status", "stop", "restart", "backup", "rollback"])
    p.add_argument("--image", required=True)
    p.add_argument("--tag")
    p.add_argument("--name", default="vrae-windows")
    p.add_argument("--filename")
    p.add_argument("--hostname")
    p.add_argument("--backup")
    a = p.parse_args()
    if a.action == "build-operator":
        build_operator(a.image, a.tag)
        result = {"operator_image": a.tag}
    elif a.action == "put-private":
        put_private(a.image, a.name, a.filename, sys.stdin.buffer.read())
        result = {"private_input_stored": True}
    elif a.action == "bootstrap":
        result = json.loads(invoke(a.image, a.name, "python", "-B", "-m", "infra.windows_service.bootstrap",
                                   "--hostname", a.hostname, "--image", a.image))
    else:
        _, root = volume(a.name)
        extra = ("--backup", a.backup) if a.backup else ()
        result = json.loads(invoke(a.image, a.name, "python", "-B", "-m", "infra.linux_service.control",
                                   a.action, "--name", a.name, "--config", root, *extra))
    print(json.dumps(result))


if __name__ == "__main__":
    main()

