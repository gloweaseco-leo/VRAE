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
