"""Pure, honest UI boundaries; the original default inventory remains untouched."""

import pytest
from apps.operator_console import b5b_views as v
from apps.operator_console.b5b_http import Application


@pytest.mark.parametrize("task", ["task-404", "task-200", "<script>", "../admin", '" onclick="bad'])
def test_navigation_escapes_untrusted_labels_without_claiming_worker_output(task):
    html = v.navigation(task)
    assert "<script>" not in html and '" onclick="bad' not in html
    assert v.RESULT_BLOCK in html and v.STATUS_BLOCK in html
    assert "UNKNOWN" in html and "NOT APPROVED" in html
    assert "Bearer " not in html and "DONE+report" not in html


@pytest.mark.parametrize(
    "ports", [(None, None), (object(), object()), ({}, {}), (lambda: None, lambda: None)]
)
def test_unaccepted_ports_cannot_supply_trusted_capabilities(ports):
    with pytest.raises(ValueError, match="B5B_ACCEPTED_SHARED_SESSION_PORTS_REQUIRED"):
        Application(*ports)
