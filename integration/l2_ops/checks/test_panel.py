import pytest

from vrae.l2_ops.briefs import BriefService
from vrae.l2_ops.panel import render_current
from vrae.l2_ops.sources import OperationsDenied


def test_existing_ssr_business_fragment_escapes_and_rechecks(bundle, reader):
    service = BriefService(reader)
    document = service.prepare(bundle, brief_ref='<script>alert(1)</script>', consultation_ref='" onclick="evil()')
    html = render_current(service, document)
    assert '<script>' not in html and '&lt;script&gt;' in html
    assert '尚未关联真实咨询' not in html and '引用待核验' in html
    assert '费用未知' in html and '未计入 E2/E3' in html
    assert '<form' not in html and '<a href=' not in html
    assert '材料与公差' in html
    reader.allowed = False
    with pytest.raises(OperationsDenied, match='REVOKED'):
        render_current(service, document)


def test_business_proposal_precedes_folded_raw_json(bundle, reader):
    service = BriefService(reader)
    html = render_current(service, service.prepare(bundle, brief_ref="readable-brief"))
    assert html.index("改造条目 1") < html.index("<details>") < html.index("<pre>")
    assert "客户确认后补充材料与公差。" in html
    assert "客户尚未确认目标" in html and "人工成本未知" in html
    assert "已记录内部审核" in html
