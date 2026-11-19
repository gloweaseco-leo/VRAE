#!/bin/sh
set -eu
cd "$(dirname "$0")/../.."
export PYVER="${PYVER:-3.13}"
SLUG="${SLUG:-313}"
BASE=$(python3 -c 'import json,os; print(json.load(open("integration/ra4b/python-images.json"))[os.environ.get("PYVER","3.13")])')
docker build --build-arg "PYTHON_BASE=$BASE" -t "vrae-ra4b-p1:$SLUG" -f integration/ra4b/Dockerfile .
docker build --build-arg "DEPENDENCY_IMAGE=vrae-ra4b-p1:$SLUG" -t "vrae-g1:$SLUG" infra/l2_g1
python3 -m infra.linux_service.build --base "vrae-g1:$SLUG" --tag "${1:-vrae-service:release}"
