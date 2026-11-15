"""B5B composition in the existing SSR; never a Worker/report association."""

from urllib.parse import quote
from .views import e, frame, link
from .proposal_views import hidden

RESULT_BLOCK = "BLOCKED_NO_ACCEPTED_LEASE_BOUND_RESULT_PORT"
STATUS_BLOCK = "BLOCKED_NO_ACCEPTED_REVIEWER_TASK_STATUS_PORT"


def boundaries():
    return (
        '<section class="notice" id="b5b-boundaries"><h2>任务与审核边界</h2>'
        "<p>当前仅使用已授权的封存报告，非 Worker 新生成结果。"
        "内部演练不代表真人审批。</p><dl>"
        "<dt>任务 request / run / job 状态</dt><dd>UNKNOWN</dd>"
        '<dt>Reviewer 受信任务读取</dt><dd data-code="'
        + STATUS_BLOCK
        + '">'
        + STATUS_BLOCK
        + "</dd>"
        '<dt>Worker 生成报告与审核分配</dt><dd data-code="'
        + RESULT_BLOCK
        + '">'
        + RESULT_BLOCK
        + "</dd>"
        "</dl><p>APP 状态不授予 Reviewer 权限；封存 404/200 原件不作为 Worker 输出。"
        "TEST_ONLY · NOT APPROVED · 禁止外发</p></section>"
    )


def navigation(task):
    root = "/b5a/tasks/" + quote(task, safe="")
    return (
        boundaries()
        + '<nav aria-label="B5B 私有工作区">'
        + "".join(
            (
                link(root + "/rehearsal", "逐 Claim 内部演练（非审批）", key="b5b-rehearsal"),
                link(root + "/rehearsal/receipt", "按原键核对持久回执", key="b5b-receipt"),
                link(root + "/b5b/private-preview", "当前权限私有预览", key="b5b-preview"),
                link(root + "/b5b/worker-result", "查看生成结果阻断原因", key="b5b-worker-result"),
                link(root + "/b5b/m2", "合成任务审核工作区", key="b5b-m2"),
            )
        )
        + "</nav>"
    )


def blocked():
    return frame("/b5a/", "生成报告链尚未接通", boundaries(), "NOT APPROVED")


def preview(package, task, csrf):
    # B6 verifies and sanitizes these exact bytes; no untrusted HTML or source
    # prose enters the existing SSR document. This is not generated-job output.
    core = package.candidate.document
    task_path = quote(task, safe="")
    content = navigation(task) + (
        '<section class="card" id="b5b-private-preview"><h1>当前权限私有预览</h1>'
        "<p>TEST_ONLY_PRIVATE_PREVIEW · NOT APPROVED · 不可交付</p>"
        '<p>已验证静态发现数：<span data-key="b5b-finding-count">'
        + str(len(core["findings"]))
        + "</span>。"
        "未检查范围 UNKNOWN；零发现不代表批准或全站无问题。</p>"
        '<p>候选内容指纹：<code data-key="b5b-candidate-digest">'
        + e(core["content_digest"])
        + "</code></p>"
        "<p>不包含原文、身份凭据、联系人、可兑换链接或正式批准。</p>"
        + link(
            "/b5a/tasks/" + task_path + "/b5b/private-view",
            "查看原 B6 私有内容",
            key="b5b-private-document",
        )
        + '<form method="post" action="/b5a/tasks/'
        + task_path
        + '/b5b/delivery">'
        + hidden("_csrf", csrf)
        + hidden("operation", "CREATE_GRANT")
        + '<button id="b5b-deny-delivery" type="submit">核验分享拒绝（不创建授权）</button></form></section>'
    )
    return frame("/b5a/", "私有预览 · NOT APPROVED", content, "NOT APPROVED")


def private_view(package, task):
    # The immutable original document stays at /private-document, byte-exact.
    # Its inline style and meta-CSP conflict with the signed SSR's stricter
    # response CSP. Reuse only its verified body in the existing same-origin
    # styled frame; never loosen the original HTTP policy or rewrite B6 bytes.
    original = package.private_html.decode('utf-8')
    if original.count('<main>') != 1 or original.count('</main>') != 1:
        raise ValueError('B5B_ORIGINAL_PRIVATE_DOCUMENT_SHAPE')
    content = original.split('<main>', 1)[1].split('</main>', 1)[0]
    digest = package.candidate.document['private_html_sha256']
    return frame('/b5a/', '原 B6 私有内容 · NOT APPROVED',
        '<section class="card" data-key="b5b-private-content" data-original-sha256="' + e(digest) + '">'
        + content + '</section>'
        + '<p>这是同源样式查看层；原 B6 文档字节及哈希保持不变。</p>'
        + link('/b5a/tasks/' + quote(task, safe='') + '/b5b/private-document',
               '按原哈希读取原 B6 文档字节', key='b5b-original-document'), 'NOT APPROVED')


def denial(receipt):
    return frame(
        "/b5a/",
        "交付已拒绝",
        boundaries() + '<section class="notice" id="b5b-delivery-denied"><h1>交付已拒绝</h1>'
        '<p>未创建 ShareGrant、token、通知或外发记录。</p><p data-code="'
        + e(receipt["reason"])
        + '">'
        + e(receipt["reason"])
        + "</p><p>NOT APPROVED · sent=false · allowed=false</p></section>",
        "NOT APPROVED",
    )
