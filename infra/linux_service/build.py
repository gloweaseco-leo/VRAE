"""Build only committed, tracked source; never include private operator inputs."""

import argparse
import io
import subprocess
import tarfile
from infra.linux_service.control import ROOT


def build(base, tag):
    if base.startswith("sha256:"):
        local = "vrae-runtime-base:" + base.removeprefix("sha256:")[:24]
        subprocess.run(["docker", "tag", base, local], check=True)
        base = local
    head = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT).decode().strip()
    if subprocess.check_output(["git", "diff", "HEAD", "--binary"], cwd=ROOT):
        raise ValueError("CLEAN_COMMITTED_SOURCE_REQUIRED")
    paths = (
        subprocess.check_output(["git", "ls-tree", "-r", "--name-only", head], cwd=ROOT)
        .decode()
        .splitlines()
    )
    archive = io.BytesIO()
    with tarfile.open(fileobj=archive, mode="w:gz", compresslevel=1) as tar:
        for name in paths:
            if name.startswith("docs/"):
                continue
            path = ROOT / name
            if not path.is_file():
                continue
            info = tarfile.TarInfo(name)
            raw = path.read_bytes()
            info.size = len(raw)
            info.mode = 0o644
            tar.addfile(info, io.BytesIO(raw))
    subprocess.run(
        [
            "docker",
            "build",
            "--build-arg",
            "RUNTIME_IMAGE=" + base,
            "--build-arg",
            "SOURCE_SHA=" + head,
            "-t",
            tag,
            "-f",
            "infra/linux_service/Dockerfile",
            "-",
        ],
        input=archive.getvalue(),
        check=True,
    )


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--base", default="vrae-g1:313")
    p.add_argument("--tag", required=True)
    a = p.parse_args()
    build(a.base, a.tag)
