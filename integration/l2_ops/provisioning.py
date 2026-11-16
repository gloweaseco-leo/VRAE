"""Trusted synthetic input configuration, never a DB privilege change."""
import re

from .catalog import SOURCE_REF


def extend_app_sources(config, binding):
    if (type(binding) is not dict or set(binding) != {"sha256", "policy_id", "policy_version"}
        or type(binding["sha256"]) is not str or not re.fullmatch("[a-f0-9]{64}", binding["sha256"])
        or binding["policy_id"] != "pol-001" or type(binding["policy_version"]) is not int
        or binding["policy_version"] != 1 or config["kind"] != "APP"
        or config["tenant"] != "tenant-test" or config["role"] != "ra4b_test_a_app"
        or set(config["sources"]) != {"accepted-404", "accepted-200"}):
        raise ValueError("L2_TEST_ONLY_PROVISIONING_DENIED")
    config["sources"][SOURCE_REF] = dict(binding)


def main():
    import json
    import os
    from pathlib import Path
    import stat
    import sys

    from vrae.application.ra4b.store import validate_binding

    assert os.geteuid() == 10001 and os.environ.get("VRAE_RA4B_TEST_ONLY") == "1"
    path = Path(sys.argv[1])
    assert path == Path("/tmp/b4-app/config.json")
    for item, mode in ((path.parent, 0o700), (path, 0o600)):
        info = item.lstat()
        assert info.st_uid == 10001 and stat.S_IMODE(info.st_mode) == mode and not stat.S_ISLNK(info.st_mode)
    original = json.loads(path.read_bytes())
    updated = json.load(sys.stdin)
    binding = updated["sources"][SOURCE_REF]
    expected = json.loads(json.dumps(original))
    extend_app_sources(expected, binding)
    assert updated == expected
    validate_binding(updated)
    path.write_text(json.dumps(updated))


if __name__ == "__main__":
    main()
