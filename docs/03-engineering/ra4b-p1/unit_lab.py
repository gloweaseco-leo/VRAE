"""Full suite in an isolated Linux Python minor with a secret-free source copy."""

import json
from pathlib import Path
import shutil
import sys
import subprocess
import uuid

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(HERE))


def main(label):
    from runtime_lab import command, source_tar
    out = HERE / label
    out.mkdir(exist_ok=False)
    private = HERE / ".runtime" / label
    private.mkdir(parents=True, exist_ok=False)
    context = private / "build"
    context.mkdir()
    for name in ("requirements-ra1a.lock", "requirements-ra4a.lock", "requirements-ra4b-p1.lock"):
        shutil.copyfile(ROOT / name, context / name)
    shutil.copyfile(ROOT / "integration/ra4b/Dockerfile", context / "Dockerfile")
    version = f"{sys.version_info.major}.{sys.version_info.minor}"
    image = "vrae-ra4b-p1:" + version.replace(".", "")
    base = json.loads((ROOT / "integration/ra4b/python-images.json").read_bytes())[version]
    command(["docker", "build", "--build-arg", "PYTHON_BASE=" + base, "-t", image, str(context)], out / "build", timeout=900)
    archive = private / "source.tar.gz"
    manifest = source_tar(archive)
    (out / "source.json").write_text(json.dumps(manifest, indent=2))
    ident = "vrae-ra4b-unit-" + uuid.uuid4().hex[:12]
    volume = ident + "-source"
    command(["docker", "volume", "create", "--label", "vrae.ra4b.unit=TEST_ONLY", volume], out / "volume-create")
    try:
        command(["docker", "run", "--rm", "-i", "--name", ident, "--label", "vrae.ra4b.unit=TEST_ONLY", "--network", "none", "--read-only", "--cap-drop", "ALL",
             "--security-opt", "no-new-privileges", "--memory", "2g", "--cpus", "2", "--pids-limit", "128",
             "--tmpfs", "/tmp:rw,nosuid,nodev,size=512m", "--mount", "type=volume,src=" + volume + ",dst=/work",
             "--mount", "type=bind,src=" + str(out.resolve()) + ",dst=/evidence", image,
             "python", "-c", "import sys,tarfile,runpy; tarfile.open(fileobj=sys.stdin.buffer,mode='r|gz').extractall('/work',filter='data'); runpy.run_path('/work/integration/ra4b/unit_check.py',run_name='__main__')"],
             out / "supervisor", data=archive.read_bytes(), timeout=3600)
    finally:
        check = subprocess.run(["docker", "inspect", "--format", '{{index .Config.Labels "vrae.ra4b.unit"}}', ident], capture_output=True, timeout=20)
        if check.returncode == 0:
            assert check.stdout.strip() == b"TEST_ONLY"
            command(["docker", "rm", "-f", ident], out / "container-remove")
        owned = subprocess.check_output(["docker", "volume", "inspect", "--format", '{{index .Labels "vrae.ra4b.unit"}}', volume]).strip()
        assert owned == b"TEST_ONLY"
        command(["docker", "volume", "rm", volume], out / "volume-remove")
        absent = subprocess.run(["docker", "volume", "inspect", volume], capture_output=True, timeout=20)
        assert absent.returncode and volume.encode() in absent.stderr and b"no such volume" in absent.stderr.lower()
        (out / "teardown.json").write_text(json.dumps({"owned_volume_removed": True, "volume": volume, "container": ident}))


if __name__ == "__main__":
    main(sys.argv[1])
