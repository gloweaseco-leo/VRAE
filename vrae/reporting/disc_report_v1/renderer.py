"""Versioned presentation; reuse the accepted CSS, escaping and evidence renderer."""

import base64
import hashlib
from html import escape
from urllib.parse import urlsplit

from vrae.reporting.renderer import CSS, _t, _link, _evidence
from vrae.reporting.common import fail
from .policy import RENDERER_VERSION


def asset_hash():
    return hashlib.sha256((RENDERER_VERSION + "\n" + CSS).encode()).hexdigest()


def _journey(row, issues, *, _disc=False):
    if _disc:
        issues = [issue for issue in issues if issue["finding"]["buyer_task"] == row["task"]]
    values = {o["result"] for o in row["observations"]}
    if (row["task"] == "INQUIRE" or (_disc and row["task"] == "DISCOVER")) and issues:
        state = "一条已绑定的路径问题" if len(issues) == 1 else "存在已绑定的路径问题"
    elif "ACCESS_BLOCKED" in values:
        state = "部分受限 · 无法完整判断"
    elif "PASS" in values:
        state = "仅静态片段／链路已检查"
    else:
        state = "证据不足 · 尚不能判断"
    return (
        f'<div class="step"><span class="eyebrow">{_t(row["task"])}</span>'
        f"<strong>{_t(row['label'])}</strong><small>{state}</small></div>"
    )


def _issue(issue, index, *, _disc=False):
    claim = issue["fact_claim"]
    status = issue["target_response"]["http_status"]
    href = claim["fact"]["source"]["citation"]["raw_href"]
    heading = f"产品 → 联系路径返回 HTTP {status}"
    tag = "INQUIRE · 静态路径问题"
    description = "记录中的产品页静态链接，指向的联系路径未返回成功页面。"
    if _disc and claim["fact"]["rule_id"] in ("DISC-01", "DISC-02"):
        route = "首页 → 分类" if claim["fact"]["rule_id"] == "DISC-01" else "分类 → 产品"
        heading = f"{route}静态路径返回 HTTP {status}"
        tag = "DISCOVER · 静态 href 响应"
        description = "记录中的这条静态链接，其同包目标响应为404或410；不据此断言浏览器可见性、产品身份或业务损失。"
    proposals = ""
    labels = {
        "impact": "对采购任务的可能影响",
        "action": "VEYFRONT 候选动作",
        "recheck": "如何重新验证",
    }
    pending = {"impact": "假设 · 待复核", "action": "候选 · 待批准", "recheck": "方案 · 待批准"}
    for role, label in labels.items():
        c = issue["proposals"][role]
        proposals += (
            f'<div class="proposal"><div class="label">{label}'
            f'<span class="review-pill">{pending[role]}</span></div>'
            f"<p>{_t(c['text'])}</p>{_link(c, '复核该提议的来源绑定')}</div>"
        )
    return (
        f'<article class="issue" id="issue-{index}" aria-labelledby="issue-title-{index}">'
        f'<div class="issue-head"><span class="number">{index:02d}</span><div>'
        f'<h2 id="issue-title-{index}">{_t(heading)}</h2>'
        f'<span class="tag">{_t(tag)}</span></div></div>'
        '<div class="fact"><div class="label">观察到的事实 · 仅本次采集</div>'
        f'<p class="fact-line">{_t(description)}</p>'
        f'<div class="route"><code><bdi>{_t(href)}</bdi></code><span>→</span>'
        f'<span class="status">HTTP {status}</span></div>'
        f'<small class="muted">源页面：<bdi>{_t(issue["source_page"]["url"], 2048)}</bdi></small><br>'
        f'<small class="muted">采集：{_t(issue["source_page"]["observed_at"])}</small>'
        f'{_link(claim)}</div><div class="proposals">{proposals}</div></article>'
    )


def render_document(d, *, _disc=True):
    if (
        d["private"] is not True
        or d["shareable"] is not False
        or d["approval_status"] != "NOT_APPROVED"
        or d["semantic_approval"] is not False
    ):
        fail("REPORT_RENDER_STATE")
    issues = d["issues"]
    title = "先让产品页的联系路径走通。" if issues else "先看已检查范围，再作判断。"
    intro = (
        "本次静态捕获发现了可回查的联系路径问题。建议先核实并修复这条具体路径，"
        "再讨论更广泛的采购体验改进。"
        if issues
        else "本次没有形成可报告的客观问题。请结合下方已检查范围与证据限制理解结果；"
        "这不等于全站健康，也不代表询盘流程已经完成验证。"
    )
    if _disc and any(i["fact_claim"]["fact"]["rule_id"] in ("DISC-01", "DISC-02") for i in issues):
        title = "先核实这些静态产品发现路径。"
        intro = (
            "本次保留的静态链接与同包目标响应支持以下具体发现。"
            "它们不代表浏览器可见性、产品身份、搜索表现或商业影响已被验证。"
        )
    issue_html = "".join(_issue(issue, i, _disc=_disc) for i, issue in enumerate(issues, 1))
    if not issues:
        issue_html = (
            '<section class="empty"><div class="label">PRIVATE COVERAGE SUMMARY</div>'
            "<h2>0 项可报告问题</h2><p>没有以未知、受限或缺失证据补造问题；本次仅保留覆盖与原文摘要，"
            "不据此确认全站没有问题。</p></section>"
        )
    positives = ""
    labels = {
        "INFO-01": "产品原文 · 不核实规格真实性",
        "TRUST-01": "企业自述 · 非实体／证书核验",
        "SEO-01": "原始标题 · 非 Google 表现",
    }
    for claim in d["positive_source_claims"]:
        cite = claim["fact"]["source"]["citation"]
        positives += (
            f'<div class="source-fact"><div class="label">{labels[claim["fact"]["rule_id"]]}</div>'
            f"<blockquote>“{_t(cite.get('text', claim['fact']['source']['quote']))}”</blockquote>"
            f"{_link(claim, '核对原文')}</div>"
        )
    if not positives:
        positives = "<p>没有纳入本页的已绑定正向原文；不据此判断企业或产品质量。</p>"
    rows = ""
    for page in d["examined_pages"]:
        status = str(page["http_status"]) if page["http_status"] is not None else "UNKNOWN"
        if page["status"] == "ACCESS_BLOCKED":
            status += " · 受限"
        elif page["status"] != "FETCHED":
            status += " · 无法判断" if page["http_status"] not in (404, 410) else " · 响应已记录"
        url = urlsplit(page["url"])
        recorded_path = url.path + ("?" + url.query if url.query else "")
        rows += f"<tr><td><bdi>{_t(recorded_path, 2048)}</bdi></td><td>{_t(status)}</td></tr>"
    limits = "".join(f"<li>{_t(t)}</li>" for t in d["limitations"][:4])
    claims = (
        [i["fact_claim"] for i in issues]
        + [c for i in issues for c in i["proposals"].values()]
        + d["positive_source_claims"]
    )
    evidence = "".join(_evidence(c, d) for c in claims)
    csp_hash = base64.b64encode(hashlib.sha256(CSS.encode("utf-8")).digest()).decode("ascii")
    csp = (
        f"default-src 'none'; style-src 'sha256-{csp_hash}'; script-src 'none'; connect-src 'none'; "
        "img-src 'none'; font-src 'none'; object-src 'none'; base-uri 'none'; form-action 'none'; frame-src 'none'"
    )
    more = ""
    if d["omitted_eligible_issues"] or d["unsupported_rule_findings"]:
        more = (
            f'<p class="muted">另有 {_t(d["omitted_eligible_issues"])} 个可报告路径未列入本页；'
            f"{_t(d['unsupported_rule_findings'])} 条其他规则发现尚未具备本页的逐条支持。</p>"
        )
    html = f'''<!doctype html>
<html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<meta http-equiv="Content-Security-Policy" content="{escape(csp, quote=True)}"><meta name="referrer" content="no-referrer">
<title>VEYFRONT｜私有 L1 诊断草稿｜{_t(d["site_host"])}</title><style>{CSS}</style></head>
<body><a class="skip-link" href="#main-content">跳至诊断内容</a>
<div class="private-bar" role="note"><strong>合成工业样本 · 私有预览</strong><span>NOT APPROVED · 未经人工批准 · 不可客户外发</span></div>
<main class="sheet{" coverage-mode" if not issues else " multi-issue" if len(issues) > 1 else ""}" id="report"><header class="masthead"><div><div class="brand">VEYFRONT</div><div class="brand-sub">REBUILD ADVISORY / BUYER EXPERIENCE</div></div>
<div class="edition"><strong>{"L1 网站初步诊断" if issues else "L1 检查范围摘要"}</strong>内部审阅稿 · v{_t(d["metadata"]["version"])}<br>无真实模型调用</div></header>
<section class="hero"><div><p class="eyebrow">从海外采购商的下一步出发</p><h1>{title}</h1><p class="intro">{intro}</p></div>
<div class="count"><strong>{len(issues):02d}</strong><span>项有证据支持的本页问题<br><span class="muted">不评分 · 不补造问题</span></span></div></section>
<div class="site-line"><span>实际采集站点 <strong><bdi>{_t(d["site_host"])}</bdi></strong></span><span>记录页面 {len(d["examined_pages"])} 个</span><span>草稿时间 {_t(d["metadata"]["created_at"])}</span></div>
<nav class="journey" aria-label="海外采购任务与本次静态检查范围">{"".join(_journey(r, issues, _disc=_disc) for r in d["buyer_journey"])}</nav>
<div class="body-grid" id="main-content"><section aria-label="诊断问题与人工复核提议"><div class="section-title"><h2>{"本次值得先讨论的具体问题" if issues else "本次检查结果"}</h2><span class="eyebrow">EVIDENCE FIRST</span></div>{issue_html}{more}</section>
<aside aria-label="采集范围与来源限制"><section class="side-block"><h2>已检查范围</h2><p>页首域名下的静态记录路径；路径角色不等于语义身份。</p><table class="scope-table"><thead><tr><th scope="col">记录的路径</th><th scope="col">捕获状态</th></tr></thead><tbody>{rows}</tbody></table></section>
<section class="side-block"><h2>已绑定的正向原文</h2><p>这些是来源片段，不作为缺陷，也不作为真实性或效果背书。</p>{positives}</section></aside></div>
<div class="closing-grid"><section class="limits-inline"><h2>未检查／无法判断</h2><ul>{limits}</ul></section>
<section class="next"><p class="eyebrow">下一步 · 仅内部提议</p><h2>先核实范围，再明确改造动作。</h2><p>内容与链接调整可作为 Rebuild 的候选讨论范围。平台、数据库、迁移及业务资料需单独评审；不构成报价或交付承诺。</p><button type="button" disabled aria-disabled="true">建议与 VEYFRONT 讨论下一步（未启用）</button></section></div>
<footer class="footer"><div><strong>PRIVATE / NOT_APPROVED / NO CUSTOMER SHARE</strong><br>所有假设、动作及复核方法均待人工审阅；本页不产生咨询收据或合格商机。<br>© VEYFRONT · 合成离线审阅样本 · 未检查部分不代表无问题。Human Gold 0/26，未评估准确率。</div>
<div class="hashes">编辑内容清单 SHA-256<br><code>{_t(d["editorial_content_sha256"])}</code><br>页面完整字节哈希见配套 draft.json；两者均不是批准凭据。</div></footer></main>{evidence}</body></html>'''
    return html.encode("utf-8")
