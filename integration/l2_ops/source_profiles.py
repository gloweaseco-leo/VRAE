"""Closed server-provisioned source versions; no browser upload or URL input."""
from pathlib import Path

from vrae.l2_ops.ingest import load_source
from vrae.l2_ops.native_input import load_native

PROFILES = {
    "industrial-v1": ("l2-industrial-native-v1", "native-offline_synthetic.json", "industrial-native",
        "ep-735db2c276030e018f21ba7124fb61db6d46f3e922eca1b99df254512064582e", "l2-industrial-capture-v1"),
    "industrial-p40-v3": ("l2-industrial-p40-v3", "native-p40-worker.json", "industrial-p40-worker",
        "ep-6d856d7718027b0895d3b450c34f7d27838f898df7c7ea369a6b060d6a2d4b60", "l2-p40-worker-capture-v3"),
}
SOURCE_REFS = frozenset(row[0] for row in PROFILES.values())


def selected(name):
    ref, file, item, pack, run = PROFILES[name]
    bundle = load_source(Path(__file__).parent / "fixtures" / file)
    return ref, bundle, load_native(bundle, item, expected_pack_ref=pack, expected_capture_run_id=run)
