"""Presentation of the public M1 result, never an identity or report authority.

Callers must obtain a fresh authorized result through the accepted reader. These
views do not authorize a save, create an assignment, or preserve an authenticated
session. Original bytes and native approval state remain unchanged.
"""

from dataclasses import dataclass, field
import hashlib
import json

from vrae.application.ra4b_p2.m1.reader import GeneratedReport
from .views import e, dump, link


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
    title = {"CTA-02": "联系入口未正常打开", "DISC-01": "分类入口未正常打开",
             "DISC-02": "产品入口未正常打开"}.get(claim["fact"]["rule_id"], "入口响应异常，需复核")
    body = (
        '<article class="m2-issue"><h2>' + str(number) + '. '
        + e(title) + ' · HTTP '
        + e(issue["target_response"]["http_status"]) + '</h2>'
        '<h3>观察到什么</h3>'
        '<p class="m2-fact">本次采集时，静态入口 ' + e(citation["raw_href"])
        + ' 的目标返回 HTTP ' + e(issue["target_response"]["http_status"])
        + '。仅代表本次响应记录，不代表当前或整个网站状态。</p>'
        '<p class="m2-source"><strong>证据：</strong>本次采集页面 '
        + e(issue["source_page"]["url"]) + ' 中的入口 '
        + e(citation["raw_href"]) + '，目标返回 HTTP '
        + e(issue["target_response"]["http_status"]) + '。</p>'
    )
    for key, label in (("impact", "可能影响"), ("action", "建议动作"), ("recheck", "复验方法")):
        body += '<p><strong>' + label + '（待判断）：</strong>' + e(issue["proposals"][key]["text"]) + '</p>'
    if not compact:
        body += ('<details class="m2-technical"><summary>技术详情：原始来源、Evidence 与 Guard</summary>'
                 '<p>采集时间：' + e(issue["source_page"]["observed_at"]) + '</p>' + dump(issue) + '</details>')
    return body + '</article>'


def diagnosis_summary(view):
    """Business wording is a projection of the same verified report, not a finding."""
    count = len(view.document["issues"])
    if count:
        return ('<p class="m2-outcome">发现 ' + str(count) + ' 个有据问题，建议先复核入口</p>'
                '<p>下方将观察事实、可能影响和建议分开展示。可能影响尚待判断，'
                '不能据此推断询盘或销售损失。</p>')
    return ('<p class="m2-outcome">证据不足，暂不能判断网站是否存在缺陷</p>'
            '<p>本次静态路径返回 HTTP 200，记录为 0 个有据问题；这不代表网站全面健康，'
            '也不证明表单送达或询盘成功。</p>')


def source_summary(view):
    labels = {"HOME": "首页", "CATEGORY": "分类页", "PRODUCT": "产品页", "CONTACT": "联系页"}
    body = '<section class="m2-sources"><h2>本次查看了哪些页面</h2><ul>'
    for item in view.document["examined_pages"]:
        body += ('<li>' + e(labels.get(item["role"], "静态页面")) + '：' + e(item["url"])
                 + ' · ' + (('HTTP ' + e(item["http_status"])) if item["http_status"] is not None
                            else '无已记录响应，不能判断') + '</li>')
    return body + '</ul><p>仅记录本次静态响应；未验证表单提交、送达或业务效果。</p></section>'


def review_label(decision):
    return {"APPROVE_INTERNAL": "内部审核通过", "REJECT_INTERNAL": "内部审核不通过",
            "REVISE_INTERNAL": "待修订后复核"}.get(decision, "查看内部审核记录")


def receipt_body(view, receipt, command_id):
    """Receipt stays an operation record; the report remains the primary result."""
    body = ('<section class="card m2-success" role="status"><p class="eyebrow">内部审核已保存</p>'
            '<h1>内部审核结果已保存</h1><p class="m2-outcome">' + e(review_label(receipt["decision"])) + '</p>'
            '<p>已保存到这份诊断报告的版本 ' + e(view.pins["report_version"]) + '。'
            '重启后重新登录仍可回读；此页是操作记录，诊断结论请查看报告。</p>'
            + link('/b5a/m2/report', '查看主要诊断报告', key='m2-primary-report')
            + link('/b5a/m2/export/' + command_id, '查看／导出单页诊断成果', key='m2-a4')
            + '</section><section class="card"><h2>本次保存内容</h2><dl>'
            '<dt>内部审核结果</dt><dd>' + e(review_label(receipt["decision"])) + '</dd>'
            '<dt>保存时间</dt><dd>' + e(receipt["recorded_at"]) + '</dd>'
            '<dt>修订说明</dt><dd class="m2-review-note">' + e(receipt["revision"] or '未填写') + '</dd></dl>')
    for number, item in enumerate(receipt["issues"], 1):
        body += ('<p>问题 ' + str(number) + '：' + e(review_label(item["decision"])) + '</p>'
                 '<p class="m2-review-note">' + e(item["revision"] or '未填写逐项说明') + '</p>')
    return (body + '<p>仅为内部合成审核，不是实际人工批准；不改变报告状态，不授权外发。</p>'
            '<details class="m2-technical"><summary>技术详情：原始审核回执 JSON</summary><p>已持久化的原始回执，仅供核对。</p>'
            + dump(receipt) + '</details></section>')


def report_body(view):
    """Escaped SSR fragment. A public URL is always text, never a fetch/link."""
    d = view.document
    body = '<section class="card m2-diagnosis"><p class="eyebrow">制造业网站 · 合成诊断</p><h1>网站入口诊断报告</h1>'
    body += '<p>本次实际生成 · 版本 ' + e(view.pins["report_version"]) + ' · 仅内部复核 · NOT APPROVED</p>'
    body += diagnosis_summary(view)
    body += link('/b5a/m2/export', '查看单页诊断成果／打印 A4', key='m2-report-a4')
    body += '<p class="m2-scope">范围：仅本次静态页面及已记录的响应，不代表全站或实时状态。</p>'
    if not d["issues"]:
        body += ('<section class="m2-next"><h2>下一步如何复核</h2><p>先由人工核对实际浏览器中的联系路径。'
                 '如需验证表单提交和送达，应另行取得授权；当前报告没有这类证据。</p></section>')
    body += ''.join(_issue(i, n) for n, i in enumerate(d["issues"], 1))
    body += source_summary(view)
    body += '<details class="m2-technical"><summary>技术详情：来源、任务标识与报告版本 / 哈希</summary>' + dump(view.pins) + '</details>'
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
            '<title>网站入口诊断报告 · 合成 A4</title>'
            '<link rel="stylesheet" href="/b5a/m2/style.css"></head><body class="m2-export">'
            '<nav class="m2-export-tools" aria-label="诊断报告操作">'
            + link('/b5a/m2/report', '返回主要诊断报告')
            + '<p>打印／保存 PDF：使用浏览器打印（Ctrl+P），纸张选择 A4。此操作栏及技术详情不打印。</p></nav>'
            '<main class="m2-sheet"><div class="m2-watermark">合成样本 · 内部审核 · 禁止外发</div>'
            '<header><strong>VEYFRONT</strong><h1>网站入口诊断报告</h1>'
            '<p>制造业合成网站 · 本次实际生成 · 版本 ' + e(p["report_version"]) + ' · NOT APPROVED</p></header>'
            + diagnosis_summary(view))
    if d["examined_pages"]:
        body += '<p class="m2-source">本次采集来源：' + e(d["examined_pages"][0]["url"]) + ' · 仅已记录的静态页面</p>'
    if d["issues"]:
        body += ''.join(_issue(i, n, compact=True) for n, i in enumerate(d["issues"], 1))
    else:
        body += ('<section><h2>建议复核</h2><p>人工核对实际浏览器中的联系路径；'
                 '表单提交与送达需另行授权验证。当前不补造问题或业务效果结论。</p></section>')
    body += '<section class="m2-review"><h2>内部审核记录</h2>'
    if receipt is None:
        body += '<p>本页未附审核记录；已有记录请在签名工作台查看。</p>'
    else:
        body += '<p>' + e(review_label(receipt["decision"])) + ' · 已保存至本版本</p>'
        body += '<p>完整审核决定及修订说明请在签名工作台查看。</p>'
    body += ('</section><footer>仅合成网站的静态采集与来源绑定；最多三个有据问题。'
             '内部决定不是实际人工批准，不改变报告 NOT_APPROVED 状态，不产生 ShareGrant 或外部交付。'
             '完整来源、Evidence、Guard 和审核回执请回到签名工作台核对。</footer></main>'
             '<details class="m2-export-technical"><summary>技术详情：本页报告的原始绑定与审核回执（不打印）</summary>'
             + dump(p) + (dump(receipt) if receipt is not None else '') + '</details></body></html>')
    return body
