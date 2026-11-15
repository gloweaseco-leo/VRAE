"""The accepted SSR frame/composer, with an explicit non-approval test action."""

import re

from .proposal_views import composer, hidden
from .views import e, frame, link, dump

NOTICE = (
    '<section class="notice" data-key="b5p0-boundary"><h2>内部演练 · NOT APPROVED · 非审批</h2>'
    "<p>仅模拟候选判断，没有法律或业务效力。不会批准报告、形成自然人审核决定或对外分享。</p></section>"
)


def internal_footer(body):
    old = "<footer>只读应用层 · SYNTHETIC_TEST_ONLY · 不保存核对结果，不产生审批或分享。<br>"
    if body.count(old) != 1:
        raise ValueError("B5P0_SSR_FOOTER_CONTRACT_CHANGED")
    return body.replace(
        old,
        "<footer>内部演练工作区 · SYNTHETIC_TEST_ONLY · 仅保存内部演练记录；非审批、非自然人签署、不对外分享。<br>",
        1,
    )


def page(prefix, task, dossier, path, ticket, csrf):
    body = composer(prefix, task, dossier)
    changes = {
        "/proposal-preview#validation-result": "/rehearsal",
        "仅测试交互合同，不进行业务审批": "仅保存内部演练，不进行业务审批",
        "所有选择只在本次页面请求内验证。不会保存、提交决定或留下真实人工确认；关闭后重新进入从未提交状态开始。": "本页仅保存内部演练记录。实际审核、真实人工签署及分享仍被禁止；重试只核验同一回执。",
        "3 · 预览验证，不提交审核": "3 · 保存内部演练，不提交审核",
        "仅验证并预览提议 · 不保存": "保存内部演练记录（非审批）",
        'id="preview-proposal"': 'id="save-rehearsal"',
        "逐条核对，再预览处置提议": "逐条核对，保存内部演练记录",
    }
    for before, after in changes.items():
        if body.count(before) != 1:
            raise ValueError("B5P0_SSR_COMPOSITION_CONTRACT_CHANGED")
        body = body.replace(before, after, 1)
    body = re.sub(
        r'(<form id="proposal-form"[^>]*>)',
        lambda m: m[1] + hidden("_ticket", ticket) + hidden("_csrf", csrf),
        body,
        count=1,
    )
    return internal_footer(
        body.replace('<main id="main" tabindex="-1">', '<main id="main" tabindex="-1">' + NOTICE, 1)
    )


def receipt(prefix, task, document, digest, mapping):
    # The immutable raw receipt is verified server-side; capabilities, internal
    # key and synthetic identity binding never leave the trusted boundary.
    visible = {
        k: v for k, v in document.items() if k not in {"idempotency_key", "subject", "db_actor"}
    }
    content = (
        NOTICE + '<section class="card" id="rehearsal-receipt" role="status">'
        "<h1>已保存内部演练记录（非审批）</h1><p>这是已提交的 TEST_ONLY 历史记录，NOT APPROVED。"
        "不是自然人签署，不具备法律或业务效力，不允许客户访问或分享。</p>"
        '<dl><dt>原始回执 SHA256</dt><dd data-key="receipt-sha">' + e(digest) + "</dd>"
        "<dt>合成身份审计映射指纹</dt><dd>"
        + e(mapping)
        + "</dd></dl>"
        + dump(visible)
        + "</section>"
        + link(
            prefix + "tasks/" + task + "/rehearsal", "重新核对同一内部记录", key="rehearsal-form"
        )
    )
    return internal_footer(
        frame(prefix, "TEST_ONLY 内部演练回执", content, "内部演练 · NOT APPROVED")
    )


def error(prefix, code):
    messages = {
        "B5P0_UNKNOWN_COMMIT": "提交结果未知。只能用重新认证后的原键查询；不能换键创建记录。",
        "B5P0_CONFLICT": "该提议与原内部记录冲突，未创建新记录。",
    }
    return internal_footer(
        frame(
            prefix,
            "内部演练未完成",
            NOTICE
            + '<section class="notice"><h1>本次操作已拒绝</h1><p>'
            + e(messages.get(code, "当前身份、权限、证据或表单已失效，请重新认证并读取。"))
            + '</p><p data-code="'
            + e(code)
            + '">'
            + e(code)
            + "</p></section>",
            "NOT APPROVED",
        )
    )
