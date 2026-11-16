"""Business panel fragment for the existing signed SSR, never a second server."""
import json
from html import escape

from .briefs import validate_document

LABELS = {
    "business_goals": "业务目标", "products_and_target_markets": "产品与目标市场",
    "material_reuse_rights": "素材复用权利", "included_and_excluded_scope": "改造范围及排除项",
    "legacy_urls_and_redirects": "历史 URL 与重定向", "acceptance_criteria": "验收标准",
    "customer_approval": "客户确认", "veyfront_consultation_receipt": "VEYFRONT 咨询受理凭据",
}


def render_current(service, document):
    """Call inside the original SSR response path; live reader remains mandatory."""
    return render_verified(service.read_current(document))


def render_verified(document):
    # This pure renderer does not confer read authority. The SSR must use
    # render_current with its server-held signed reader, never browser JSON.
    validate_document(document)
    e = lambda x: escape(str(x), quote=True)
    pins = "".join(f"<dt>{e(k)}</dt><dd>{e(v)}</dd>" for k, v in document["pins"].items())
    pending = "".join(f"<li>{e(LABELS[c['key']])}：待确认</li>" for c in document["customer_confirmations"])
    consultation = document["consultation"]
    consultation_text = "尚未关联真实咨询" if consultation["reference"] is None else "引用待核验：" + consultation["reference"]
    cost = document["cost_total"]
    cost_text = "费用未知（非零费用声明）" if cost["amount_micros"] is None else f"{cost['amount_micros']} 微单位 {cost['currency']}，估算，未对账"
    activities = "".join(f"<li>{e(a['kind'])}：{e(a['wall_ns'])} ns；{e(a['actor_kind'])}</li>" for a in document["activities"])
    return (
        '<section aria-label="VEYFRONT 内部改造交接"><h2>RebuildBrief · 内部草案</h2>'
        '<p>用于商务准备。客户资料、范围、权利与咨询受理凭据仍待确认；本草案不触发外发或建站。</p>'
        f"<p>引用：{e(document['brief_ref'])}；状态：{e(document['preparation_status'])}</p>"
        f"<h3>报告与任务版本</h3><dl>{pins}</dl>"
        f"<p>审核回执：{e(document['review']['receipt_ref'])}；{e(document['review']['decision'])}</p>"
        f"<h3>改造蓝图</h3><pre>{e(json.dumps(document['blueprint'], ensure_ascii=False, indent=2))}</pre>"
        f"<h3>待客户确认</h3><ul>{pending}</ul>"
        f"<h3>商务承接</h3><p>{e(consultation_text)}；未计入 E2/E3。</p>"
        f"<h3>实际运行与操作记录</h3><ul>{activities}</ul><p>{e(cost_text)}</p>"
        f"<p>交接内容 SHA256：{e(document['content_sha256'])}</p></section>"
    )
