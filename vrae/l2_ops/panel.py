"""Business panel fragment for the existing signed SSR, never a second server."""
import json
from html import escape
from decimal import Decimal

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


def _blueprint_summary(blueprint):
    """Present supplied proposals, without inventing a recommendation or scope."""
    rows = blueprint.get("items")
    if not isinstance(rows, list) or not rows:
        return "<p>尚无可呈现的改造条目；请核对上游蓝图，不能据此承诺改造范围。</p>"
    cards = []
    labels = {"proposal": "建议改造", "finding_ref": "关联发现", "priority": "优先级",
              "acceptance_criteria": "验证标准", "evidence_refs": "证据引用"}
    for index, row in enumerate(rows, 1):
        if not isinstance(row, dict):
            continue
        fields = []
        for key, label in labels.items():
            if key in row:
                value = row[key]
                if isinstance(value, (dict, list)):
                    value = json.dumps(value, ensure_ascii=False)
                fields.append(f"<dt>{label}</dt><dd>{escape(str(value), quote=True)}</dd>")
        if fields:
            cards.append(f"<article><h4>改造条目 {index}</h4><dl>{''.join(fields)}</dl></article>")
    return "".join(cards) or "<p>上游蓝图结构待适配，完整原文保留在核验详情。</p>"


def render_verified(document):
    # Pure rendering confers no read authority. SSR must call render_current.
    validate_document(document)

    def e(value):
        return escape(str(value), quote=True)

    pins = "".join(f"<dt>{e(k)}</dt><dd>{e(v)}</dd>" for k, v in document["pins"].items())
    pending = "".join(f"<li>{e(LABELS[c['key']])}：待确认</li>" for c in document["customer_confirmations"])
    consultation = document["consultation"]
    consultation_text = "尚未关联真实咨询" if consultation["reference"] is None else "引用待核验：" + consultation["reference"]
    cost = document["cost_total"]
    cost_text = "费用未知（不表示费用为零）" if cost["amount_micros"] is None else (
        f"{Decimal(cost['amount_micros']) / Decimal(1_000_000):f} {cost['currency']}，估算，未对账")
    kinds = {"DIAGNOSIS_RUNTIME": "诊断运行", "REVIEW_ACTIVITY": "审核操作", "SALES_PREPARATION": "商务准备"}
    actors = {"SYSTEM": "系统运行", "AUTOMATED_DEMO": "自动演示操作", "HUMAN_ATTESTED": "人工操作（具声明引用）"}
    activities = "".join(
        f"<li>{e(kinds[a['kind']])}：{Decimal(a['wall_ns']) / Decimal(1_000_000_000):.3f} 秒；"
        f"{e(actors[a['actor_kind']])}</li>" for a in document["activities"])
    if not activities:
        activities = "<li>尚无运行或人工工时记录；人工成本未知。</li>"
    status = {"INTERNAL_REVIEW_RECORDED": "已记录内部审核", "REJECTED": "内部审核拒绝", "REVISION_REQUIRED": "待修订"}
    decisions = {"APPROVE_INTERNAL": "内部批准", "REJECT_INTERNAL": "内部拒绝", "REVISE_INTERNAL": "要求修订"}
    return (
        '<section aria-label="VEYFRONT 内部改造交接"><h2>RebuildBrief · 内部草案</h2>'
        '<p>用于商务准备。客户资料、范围、权利与咨询受理凭据仍待确认；本草案不触发外发或建站。</p>'
        f"<p>引用：{e(document['brief_ref'])}；状态：{e(status[document['preparation_status']])}</p>"
        f"<p>报告：{e(document['pins']['report_ref'])}，版本 {e(document['pins']['report_version'])}</p>"
        f"<p>审核回执：{e(document['review']['receipt_ref'])}；{e(decisions[document['review']['decision']])}</p>"
        f"<h3>改造蓝图 · 商务准备</h3>{_blueprint_summary(document['blueprint'])}"
        '<p>上述建议来自当前审核版本；客户尚未确认目标、范围和素材权利。</p>'
        f"<h3>待客户确认</h3><ul>{pending}</ul>"
        f"<h3>商务承接</h3><p>{e(consultation_text)}；未计入 E2/E3。</p>"
        f"<h3>实际运行与操作记录</h3><ul>{activities}</ul><p>{e(cost_text)}</p>"
        f"<details><summary>核验详情：任务、版本和蓝图原文</summary><dl>{pins}</dl>"
        f"<pre>{e(json.dumps(document['blueprint'], ensure_ascii=False, indent=2))}</pre>"
        f"<p>交接内容 SHA256：{e(document['content_sha256'])}</p></details></section>"
    )
