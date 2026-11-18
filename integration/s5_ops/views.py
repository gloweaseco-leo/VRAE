"""Readable sidecar UI within the original DeepConsole layout and CSS."""

from apps.operator_console.proposal_views import hidden
from apps.operator_console.views import e, link
from vrae.intelligence.s3.offline import TASKS

LABELS = dict(
    zip(TASKS, ("发现产品", "理解规格与工况", "核对供应商证明", "准备询价", "搜索与技术范围"))
)


def render(root, nonce, job, current_hash, historical):
    body = '<section class="card" data-key="s5-offline"><p class="eyebrow">VEYFRONT · 内部离线采购解释</p><h1>同任务采购解释候选</h1>'
    body += "<p>先保留原证据和报告判断，再阅读可选离线解释；它不批准报告、不修改事实，也不代表真正模型质量。</p>"
    body += '<p data-key="s5-state">' + e(job.state if job else "NO_MODEL_READY") + "</p>"
    body += "<p>真实模型费用 UNKNOWN；真实模型调用为 0。Fixture 只做封闭模板选择，不是开放式语义理解。</p>"
    body += '<form method="post" action="' + root + '/s3">' + hidden("_csrf", nonce)
    body += '<label>解释模式<select name="mode"><option value="NO_MODEL">NO_MODEL · 不调用模型</option><option value="FIXTURE">FixtureProvider · 合成解释候选</option></select></label>'
    body += '<button data-key="s5-run">运行本任务解释</button></form>'
    body += link(root + "/s3", "刷新本任务解释状态", key="s5-refresh")
    body += link(root, "原确定性专业报告始终可用", key="s5-original-report")
    body += "<p>摘要与内部模拟接单由已验收 S4 接口接入；当前不虚构 ACK、客户批准或持久接单。</p></section>"
    if job and job.result is not None:
        data = job.result
        attrs = " ".join(
            "data-" + key + '="' + e(data[field]) + '"'
            for key, field in (
                ("mode", "mode"),
                ("status", "status"),
                ("context-ref", "context_ref"),
                ("receipt-ref", "receipt_ref"),
                ("content-hash", "deterministic_report_hash"),
            )
        )
        body += (
            '<section class="card" data-key="s5-result" '
            + attrs
            + "><h2>"
            + e(data["mode"])
            + " · "
            + e(data["status"])
            + "</h2>"
        )
        body += "<p>" + e(data["code"]) + " · 仅为人工审阅候选，不替代原报告、版本或审核。</p>"
        body += "<p>原报告内容 hash " + e(current_hash) + "</p>"
        for task in TASKS:
            body += '<article data-s5-task="' + task + '"><h3>' + e(LABELS[task]) + "</h3>"
            rows = [
                x for x in data["claims"] if x.get("task") == task and x["status"] != "REJECTED"
            ]
            if not rows:
                body += "<p>本模式没有新增本维度的解释；原报告与 UNKNOWN 范围继续保留。</p>"
            for row in rows:
                body += "<p>" + e(row["status"]) + " · " + e(row["text"]) + "</p>"
                body += "<p>还需人工核对；工程适配、证明真实性和实际商业收益未获确认。</p>"
                body += (
                    "<details><summary>同源证据与反证</summary><p>"
                    + e(" / ".join(row["refs"]))
                    + "</p><p>"
                    + e(" / ".join(row["counter_refs"]))
                    + "</p></details>"
                )
            body += "</article>"
        body += (
            '<details><summary>模式、版本、费用与引用</summary><p data-key="s5-receipt">'
            + e(data["receipt_ref"])
            + "</p>"
        )
        body += (
            "<p>"
            + e(data["context_ref"])
            + "</p><p>真实费用："
            + e(data["usage"]["cost_status"])
            + "</p>"
        )
        body += "<p>Fixture 字节费率为合成 ESTIMATED，不能作为真实 token、账单或人工费用。</p></details></section>"
    if historical:
        body += '<section class="card" data-key="s5-history"><h2>历史执行引用</h2><p>会话过期或服务重启后，不把历史引用当当前候选授权；原账本保留且禁止重复分派。</p>'
        for row in historical:
            body += "<p>" + e(row.get("receipt_ref") or row["state"]) + "</p>"
        body += "</section>"
    return body
