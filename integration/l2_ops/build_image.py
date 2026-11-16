"""Dependency-only image from accepted Dockerfile and locked digests."""
import argparse
import json
from pathlib import Path
import shutil
import subprocess


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--python", required=True, choices=("3.11", "3.13"))
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[2]
    folder = root / "integration/l2_ops/.private" / ("image-" + args.python.replace(".", ""))
    folder.mkdir(parents=True, exist_ok=True)
    for name in ("requirements-ra1a.lock", "requirements-ra4a.lock", "requirements-ra4b-p1.lock"):
        shutil.copyfile(root / name, folder / name)
    shutil.copyfile(root / "integration/ra4b/Dockerfile", folder / "Dockerfile")
    base = json.loads((root / "integration/ra4b/python-images.json").read_bytes())[args.python]
    subprocess.run(["docker", "build", "--build-arg", "PYTHON_BASE=" + base,
                    "-t", "vrae-ra4b-p1:" + args.python.replace(".", ""), str(folder)], check=True)


if __name__ == "__main__":
    main()
