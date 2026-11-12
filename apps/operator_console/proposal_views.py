"""Chinese proposal composer, existing SSR frame, no browser storage or scripts."""

from urllib.parse import urlencode

from .views import e, dump, link, frame, target_url, review_url

ACCEPT_LABELS = {
    "ACK_LITERAL_FACT": "仅确认字面来源 · 不证明资质或经营事实",
    "ACCEPT_AS_HYPOTHESIS": "仅作为假设保留 · 不升级为已证实事实",
    "ACCEPT_AS_PROPOSED_ACTION": "仅作为建议行动保留 · 尚未批准执行",
    "CHANGE_REQUESTED": "提议退回此项修改",
    "REJECTED": "提议拒绝此项",
}
SECTION_LABELS = {
    "coverage.v1": "已检查范围",
    "limitations.v1": "未覆盖内容与局限",
    "full_preview.v1": "完整报告内容",
    "business_boundaries.v1": "商务与使用边界",
}


def hidden(name, value):
    return f'<input type="hidden" name="{e(name)}" value="{e(value)}">'


def composer(prefix, task, dossier, command=None, outcome=None):
    if command and outcome == "D_UNTRUSTED_TEXT":
        command = dict(command, reason="[输入不符合文本约束，原始原因未显示]")
    v = dossier["review_target"]
    t = v["target"]
    is_review = t["kind"] == "L1_NATIVE"
    query = urlencode(
        {"version": task["report_version"], "draft": t["draft_ref"], "target": v["target_digest"]}
    )
    source_base = prefix + "tasks/" + task["task_id"] + "/evidence/"
    actions = (
        [
            ("APPROVE_CANDIDATE", "候选接受提议 · 仅模拟验证"),
            ("REQUEST_CHANGES", "退回修改提议 · 需定位到 Claim"),
            ("REJECT", "拒绝提议 · 需定位到 Claim"),
        ]
        if is_review
        else [("SIMULATED_INTERNAL_SCOPE_ACK", "仅模拟内部范围确认")]
    )
    content = (
        '<p class="eyebrow">TEST_ONLY / PROPOSAL COMPOSER</p><h1>逐条核对，再预览处置提议</h1>'
        '<section class="notice"><h2>仅测试交互合同，不进行业务审批</h2>'
        "<p>所有选择只在本次页面请求内验证。不会保存、提交决定或留下真实人工确认；关闭后重新进入从未提交状态开始。</p>"
        "<p><strong>PRIVATE_NOT_APPROVED · NO_AUTH / NO_APPROVAL / NO_SHARE / NO_CLIENT</strong></p></section>"
    )
    if not is_review:
        content += (
            '<section class="card"><h2>在已检查的范围内未发现可确认问题</h2>'
            "<p>200 · 0 条问题 · native H0 = null / ReportVersion = null。只能核对范围；不证明网站合格、转化成功或审核通过。</p></section>"
        )
    if outcome is not None:
        ok = outcome == "CONTRACT_VALID_ONLY"
        content += (
            '<section class="notice" id="validation-result" tabindex="-1" role="status">'
            "<h2>"
            + ("提议格式与绑定检查完成 · 未产生决定" if ok else "提议未满足合同 · 未产生决定")
            + "</h2>"
            f'<p data-outcome="{e(outcome)}">{e(outcome)}</p>'
            "<p>这是自动化合同验证预览，不是真人验收，不代表报告已批准。没有审批回执、保存记录或分享授权。</p>"
            f"<p>检查目标 <code>{e(v['target_digest'])}</code> · 版本 {e(t['report_version'])}</p>"
            + link(
                target_url(prefix, task, dossier).replace("/target?", "/proposal?"),
                "开始新的未提交提议",
                key="new-proposal",
            )
            + "</section>"
        )
    content += (
        f'<form id="proposal-form" method="post" autocomplete="off" action="{e(prefix)}tasks/{e(task["task_id"])}/proposal-preview#validation-result">'
        + hidden("version", t["report_version"])
        + hidden("draft", t["draft_ref"])
        + hidden("target", v["target_digest"])
        + '<section class="card"><h2>1 · 核对每一条 Claim</h2>'
        "<p>先查看原文与机器状态，再主动选择。网站自述只证明该文字存在；影响、建议与复验保持 HUMAN_REVIEW_REQUIRED。</p>"
    )
    for i, claim in enumerate(t["claims"]):
        ev = next(ev for ev in dossier["evidence"] if ev["pointer"] == claim["document_pointer"])
        index = dossier["evidence"].index(ev)
        selected = command["dispositions"][i]["disposition"] if command else ""
        choices = [claim["allowed_acceptance"]] + (
            ["CHANGE_REQUESTED", "REJECTED"] if is_review else []
        )
        options = '<option value="">请选择本项处置提议</option>'
        for choice in choices:
            options += (
                f'<option value="{e(choice)}"'
                + (" selected" if selected == choice else "")
                + f">{e(ACCEPT_LABELS[choice])}</option>"
            )
        role = (
            "观察事实"
            if claim["document_pointer"].endswith("fact_claim")
            else {"impact": "可能影响 · 假设", "action": "建议动作", "recheck": "复验方法"}.get(
                claim["document_pointer"].split("/")[-1], "网站字面自述 · 不代表真实性核实"
            )
        )
        content += (
            f'<fieldset class="claim-card" id="claim-{i}"><legend>{i + 1} · {e(role)}</legend>'
            f'<p>{e(ev["claim"]["text"])}</p><p class="machine-status">机器状态：{e(claim["machine_status"])}</p>'
            f'<blockquote>{e(ev["quote"])}</blockquote><p class="source-meta"><bdi>{e(ev["citation"]["url"])}</bdi><br>'
            f"UTF-8 [{claim['byte_start']}, {claim['byte_end']})</p>"
            + link(
                source_base + str(index) + "?" + query,
                "回查本项精确原始来源",
                key="proposal-source",
            )
            + hidden("guard." + str(i), claim["guard_ref"])
            + hidden("binding." + str(i), claim["binding_ref"])
            + hidden("pointer." + str(i), claim["pointer"])
            + f'<label for="disposition-{i}">本项处置提议<select id="disposition-{i}" name="disposition.{i}" required>{options}</select></label>'
            "<details><summary>原始 Claim 身份与来源绑定</summary>"
            + dump(claim)
            + "</details></fieldset>"
        )
    content += '</section><section class="card"><h2>2 · 阅读并确认本次核对范围</h2>'
    sections = {
        "coverage.v1": "<p>固定合成采集，仅静态路径与页面文字，不访问原网站。</p>"
        + dump(v["recorded_coverage"])
        + dump(v["examined_pages"]),
        "limitations.v1": dump(v["limitations"]),
        "full_preview.v1": "<p>逐条内容见上方；以下保留完整原生报告结构。请同时查看原生报告展示。</p>"
        + link(review_url(prefix, task), "回到原生报告完整展示", key="proposal-full-preview")
        + "<details><summary>完整原生报告 / Guard / 哈希</summary>"
        + dump(dossier["document"])
        + "</details>",
        "business_boundaries.v1": "<p>不核实企业资质、认证、流量、Google 排名、收入、销售损失、投递或询盘效果。不得对外分享。</p>"
        + "<ul>"
        + "".join("<li>" + e(c) + "</li>" for c in v["missing_conditions"])
        + "</ul>",
    }
    for section in t["required_sections"]:
        acknowledged = command and any(s["section_id"] == section for s in command["sections"])
        content += (
            f'<div class="ack-section" id="{e(section)}"><h3>{e(SECTION_LABELS[section])}</h3>'
            + sections[section]
            + f'<label class="check"><input type="checkbox" name="section.{e(section)}" value="{e(v["target_digest"])}"'
            + (" checked" if acknowledged else "")
            + f" required><span>仅确认已核对「{e(SECTION_LABELS[section])}」· 非真实人工签署</span></label></div>"
        )
    action_value = command.get("action", "SIMULATED_INTERNAL_SCOPE_ACK") if command else ""
    options = '<option value="">请选择整体提议</option>'
    for value, label in actions:
        options += (
            f'<option value="{value}"'
            + (" selected" if action_value == value else "")
            + f">{e(label)}</option>"
        )
    content += (
        '</section><section class="card"><h2>3 · 预览验证，不提交审核</h2>'
        f'<label>整体提议<select name="action" id="proposal-action" required>{options}</select></label>'
        '<label for="proposal-reason">原因（退回修改或拒绝必填，且须在上方定位对应 Claim）</label>'
        f'<textarea id="proposal-reason" name="reason" maxlength="2000" rows="4" placeholder="例如：第 2 项影响假设需要补充采购商路径研究。">{e(command["reason"] or "") if command else ""}</textarea>'
        '<p class="source-meta">最多 2000 字；不接受控制字符或方向覆盖符。请勿输入个人资料或密钥。</p>'
        '<button id="preview-proposal" type="submit">仅验证并预览提议 · 不保存</button></section></form>'
        "<details><summary>本次精确目标与完整来源 / 版本 / Guard 绑定</summary>"
        + dump(v)
        + "</details>"
    )
    if command:
        content += (
            '<details id="checked-command"><summary>本次实际检查的 Claim / Section / Action 合同</summary>'
            + dump(command)
            + "</details>"
        )
    content += link(
        target_url(prefix, task, dossier), "返回精确核对对象", key="proposal-back-target"
    )
    return frame(prefix, "TEST_ONLY 逐 Claim 提议", content, "离线提议预览")
