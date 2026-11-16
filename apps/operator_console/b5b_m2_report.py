"""Presentation of the public M1 result, never an identity or report authority.

Callers must obtain a fresh authorized result through the accepted reader. These
views do not authorize a save, create an assignment, or preserve an authenticated
session. Original bytes and native approval state remain unchanged.
"""

from dataclasses import dataclass, field
import hashlib
import json

from vrae.application.ra4b_p2.m1.reader import GeneratedReport
from .views import e, dump


@dataclass(frozen=True)
class ReportView:
    payload: GeneratedReport = field(repr=False)

    def __post_init__(self):
        p = self.payload
        if type(p) is not GeneratedReport:
            raise ValueError("M2_GENERATED_REPORT_REQUIRED")
        for key in ("source", "report", "html"):
            if hashlib.sha256(getattr(p, key)).hexdigest() != p.locator.get(key + "_sha256"):
                raise ValueError("M2_RESULT_HASH_MISMATCH")
        d = self.document
        loc = p.locator
        if (
            d["metadata"]["report_id"] != loc["report_id"]
            or type(loc["report_version"]) is not int
            or d["metadata"]["version"] != loc["report_version"]
            or d["metadata"]["report_id"] != "job-" + loc["job_id"]
            or d["scope"]["run_id"] != loc["run_id"]
            or d["approval_status"] != "NOT_APPROVED"
            or d["shareable"] is not False
            or d["semantic_approval"] is not False
            or d["private"] is not True
            or d["metadata"]["mode"] != "SYNTHETIC_PRIVATE_PREVIEW"
            or len(d["issues"]) > 3
            or len(self.issue_ids) != len(set(self.issue_ids))
            or any(i["fact_claim"]["status"] != "SOURCE_FACT_BINDING_VERIFIED"
                   for i in d["issues"])
        ):
            raise ValueError("M2_GENERATED_SCOPE_MISMATCH")

    @property
    def document(self):
        return json.loads(self.payload.report)

    @property
    def source(self):
        return json.loads(self.payload.source)

    @property
    def issue_ids(self):
        return tuple(i["finding"]["finding_id"] for i in self.document["issues"])

    @property
    def pins(self):
        loc = self.payload.locator
        d = self.document
        native = d["native_report_version"]
        return {
            "job_id": loc["job_id"],
            "request_id": loc["request_id"],
            "run_id": loc["run_id"],
            "report_id": loc["report_id"],
            "report_version": loc["report_version"],
            "report_sha256": loc["report_sha256"],
            "source_sha256": loc["source_sha256"],
            "html_sha256": loc["html_sha256"],
            "draft_ref": d["draft_ref"],
            "editorial_content_sha256": d["editorial_content_sha256"],
            "native_content_hash": native["content_hash"] if native else None,
        }


def _issue(issue, number, *, compact=False):
    claim = issue["fact_claim"]
    citation = claim["fact"]["source"]["citation"]
    body = (
        '<article class="m2-issue"><h2>' + str(number) + '. '
        + e(claim["fact"]["rule_id"]) + ' · HTTP '
        + e(issue["target_response"]["http_status"]) + '</h2>'
        '<p class="m2-fact">' + e(claim["text"]) + '</p>'
        '<p class="m2-source">来源：' + e(issue["source_page"]["url"])
        + ' · ' + e(issue["source_page"]["observed_at"]) + '</p>'
        '<p class="m2-source">Evidence：' + e(citation["evidence_ref"])
        + ' · Guard：' + e(claim["status"]) + '</p>'
    )
    for key, label in (("impact", "可能影响"), ("action", "建议动作"), ("recheck", "复验方法")):
        body += '<p><strong>' + label + '（待判断）：</strong>' + e(issue["proposals"][key]["text"]) + '</p>'
    if not compact:
        body += '<details><summary>完整来源、Evidence 与逐项 Guard 绑定</summary>' + dump(issue) + '</details>'
    return body + '</article>'


def report_body(view):
    """Escaped SSR fragment. A public URL is always text, never a fetch/link."""
    d = view.document
    body = '<section class="card"><h1>本次 Worker 生成的 L1 内部审阅稿</h1>'
    body += '<p>合成制造业网站 · NOT APPROVED · 不可外发</p>'
    body += '<p>' + str(len(d["issues"])) + ' 个有据问题 · 实际生成版本 ' + e(view.pins["report_version"]) + '</p>'
    if not d["issues"]:
        body += ('<p class="neutral">证据不足，不能据此判断网站缺陷或网站全面健康。'
                 'HTTP 200 仅是静态响应，不证明表单送达或询盘成功。</p>')
    body += ''.join(_issue(i, n) for n, i in enumerate(d["issues"], 1))
    body += '<details open><summary>来源与实际报告版本 / 哈希</summary>' + dump(view.pins) + '</details>'
    body += '<details><summary>本次静态页面与覆盖范围</summary>' + dump(d["examined_pages"]) + dump(d["recorded_coverage"]) + '</details>'
    body += '<details><summary>其他静态线索的 Evidence 绑定（不等于问题或资质真实）</summary>' + dump(d['positive_source_claims']) + '</details>'
    body += '<details><summary>原生 Guard 与完整证据保留情况</summary>'
    body += dump([b["guard"] for b in view.source["guard_inputs"]])
    body += dump(view.payload.editorial_selection) + '</details></section>'
    return body


def a4(view, *, receipt=None):
    """Print/export projection; does not modify or relabel original M1 HTML.

    Receipt must already have been authorized and read back by the service. No
    receipt is fabricated for an unreviewed report. Full bytes remain in M1.
    """
    p, d = view.pins, view.document
    if receipt is not None:
        if any(receipt["report"][k] != p[k] for k in ("job_id", "report_id", "report_version", "report_sha256")):
            raise ValueError("M2_RECEIPT_REPORT_MISMATCH")
        if receipt.get("scope") != "SYNTHETIC_INTERNAL_REVIEW_ONLY":
            raise ValueError("M2_INTERNAL_RECEIPT_REQUIRED")
    body = ('<!doctype html><html lang="zh-CN"><head><meta charset="utf-8">'
            '<meta name="viewport" content="width=device-width,initial-scale=1">'
            '<title>合成 L1 内部审阅稿 · A4</title>'
            '<link rel="stylesheet" href="/b5a/m2/style.css"></head><body class="m2-export">'
            '<main class="m2-sheet"><div class="m2-watermark">合成样本 · 内部审核 · 禁止外发</div>'
            '<header><strong>VEYFRONT</strong><h1>制造业网站 L1 内部审阅稿</h1>'
            '<p>本次 Worker 生成 · 版本 ' + e(p["report_version"]) + ' · NOT APPROVED</p></header>')
    if d["issues"]:
        body += ''.join(_issue(i, n, compact=True) for n, i in enumerate(d["issues"], 1))
    else:
        body += ('<section><h2>0 个有据问题 · 证据不足</h2><p>本次静态路径返回 HTTP 200；'
                 '不能据此判断网站缺陷、网站健康、表单送达或询盘成功。</p></section>')
    body += '<section class="m2-pins"><h2>实际生成结果绑定</h2><dl>'
    for key, label in (("job_id", "任务"), ("report_id", "报告"), ("report_sha256", "报告文件 SHA-256"),
                       ("native_content_hash", "原生内容哈希"), ("source_sha256", "来源 SHA-256")):
        body += '<dt>' + label + '</dt><dd>' + e(p[key] if p[key] is not None else '无：本版为覆盖摘要') + '</dd>'
    body += '</dl></section><section class="m2-review"><h2>内部合成审核</h2>'
    if receipt is None:
        body += '<p>尚无已持久化审核回执。</p>'
    else:
        body += '<p>回执 ' + e(receipt["receipt_id"]) + ' · ' + e(receipt["decision"]) + '</p>'
        revision = receipt['revision']
        body += '<p>修订说明：' + e((revision[:180] + '…（完整说明见持久回执）') if len(revision) > 180 else (revision or '无')) + '</p>'
    body += ('</section><footer>仅合成网站的静态采集与来源绑定；最多三个有据问题。'
             '内部决定不是实际人工批准，不改变报告 NOT_APPROVED 状态，不产生 ShareGrant 或外部交付。'
             '完整来源、Evidence、Guard 和审核回执请回到签名工作台核对。</footer></main></body></html>')
    return body
