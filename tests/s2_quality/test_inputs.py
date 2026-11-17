"""CLI boundary tests explicitly selected by the dedicated P0 native gate."""

import pytest
from tests.benchmark.s2_review import read_json
from tests.benchmark.s2_quality import QualityError


@pytest.mark.parametrize(
    "data,reason",
    [
        (b'{"origin":"UNREVIEWED_TEMPLATE","origin":"EXTERNAL_HUMAN"}', "DUPLICATE_JSON_KEY"),
        (b'{"x":NaN}', "NONFINITE_JSON"),
        (b'{"x":Infinity}', "NONFINITE_JSON"),
    ],
)
def test_conflicting_json_is_not_last_writer_wins(tmp_path, data, reason):
    p = tmp_path / "input.json"
    p.write_bytes(data)
    with pytest.raises(QualityError, match=reason):
        read_json(p)


def test_large_input_bound_before_json_decode(tmp_path):
    p = tmp_path / "input.json"
    p.write_bytes(b" " * 16_000_001)
    with pytest.raises(QualityError, match="SIZE_BOUND"):
        read_json(p)
