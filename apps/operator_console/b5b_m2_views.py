"""M2 presentation preparation; no generated-result authority or persistence."""

from urllib.parse import quote

from .views import e, frame, link
from .b5b_views import RESULT_BLOCK, STATUS_BLOCK


def workspace(task):
    root = '/b5a/tasks/' + quote(task, safe='')
    content = (
        '<section class="card" id="m2-workspace"><h1>合成 L0 → L1 内部审核</h1>'
        '<p>仅合成制造业网站 · NOT APPROVED · 禁止外发</p>'
        '<p>本页没有本次 Worker 生成报告。现有封存演练原件不会冒充新任务输出。</p>'
        '<h2>发起诊断与处理状态</h2>'
        '<p data-code="' + STATUS_BLOCK + '">' + STATUS_BLOCK + '</p>'
        '<p>尚无已验收的签名操作员任务创建／任务映射端口，不能将 APP 凭据交给浏览器或 SSR。</p>'
        '<label for="m2-source">合成源分支</label><select id="m2-source" disabled>'
        '<option>制造业路径 404（有据问题）</option><option>制造业路径 200（证据不足／UNKNOWN）</option></select>'
        '<button type="button" disabled>发起新的 L0 诊断（等待可信端口）</button>'
        '<dl><dt>request / run / job</dt><dd>UNKNOWN</dd><dt>报告版本／内容哈希</dt><dd>UNKNOWN</dd></dl>'
        '<h2>生成报告与逐项审核</h2><p data-code="' + RESULT_BLOCK + '">' + RESULT_BLOCK + '</p>'
        '<p>需要 C1 已合并的当前任务、来源、租约／epoch 与 Reviewer 分配绑定读取。'
        '没有真实生成版本时不创建审核决定、回执或导出。</p>'
        '<fieldset disabled><legend>针对同一生成版本的内部决定</legend>'
        '<label for="m2-decision">决定</label><select id="m2-decision">'
        '<option>内部批准</option><option>拒绝</option><option>修订后重新审核</option></select>'
        '<label for="m2-revision">修订说明</label><textarea id="m2-revision" maxlength="2000"></textarea>'
        '<button type="button">保存版本回执（等待真实报告）</button>'
        '<button type="button">查看／下载中文 A4 内部合成样本（等待真实报告）</button></fieldset>'
        '<p>内部合成审核不是客户正式批准，不产生 ShareGrant、联系人、token 或网络发送。</p>'
        + link(root + '/rehearsal/receipt', '查看原封存演练回执（不是新任务审核）', key='m2-legacy-receipt')
        + '</section>'
    )
    return frame('/b5a/', '合成任务审核 · 等待生成端口', content, 'NOT APPROVED')


def decision_fields(task, version, report_sha256, issue_ids, csrf):
    """Render only; caller must supply trusted port pins, authorize and persist.

    Not mounted while the accepted generated-result/read port is absent. These
    fields are untrusted submissions, never proof of a report or assignment.
    """
    import re
    from .proposal_views import hidden

    if (type(version) is not int or version < 1
            or not isinstance(report_sha256, str) or not re.fullmatch('[a-f0-9]{64}', report_sha256)
            or len(issue_ids) > 3 or len(set(issue_ids)) != len(issue_ids)
            or any(not isinstance(i, str) or not re.fullmatch('[A-Za-z0-9_-]{1,80}', i) for i in issue_ids)):
        raise ValueError('M2_EXACT_REPORT_PINS_REQUIRED')
    out = ('<form method="post" action="/b5a/tasks/' + quote(task, safe='') + '/b5b/generated-review">'
           + hidden('_csrf', csrf) + hidden('report_version', str(version))
           + hidden('report_sha256', report_sha256)
           + '<p>合成内部审核 · 报告原件及证据不被改写 · NOT APPROVED</p>')
    for issue in issue_ids:
        out += ('<fieldset><legend>问题 ' + e(issue) + '</legend><label for="decision-' + e(issue)
                + '">内部决定</label><select id="decision-' + e(issue) + '" name="decision.' + e(issue)
                + '"><option value="">请选择</option><option value="APPROVE_INTERNAL">内部批准</option>'
                '<option value="REJECT_INTERNAL">拒绝</option><option value="REVISE_INTERNAL">修订</option></select>'
                '<label for="revision-' + e(issue) + '">修订说明（不改写源事实）</label><textarea id="revision-'
                + e(issue) + '" name="revision.' + e(issue) + '" maxlength="2000"></textarea></fieldset>')
    return out + '<button type="submit">保存本版本内部决定</button></form>'


def generated_decision_fields(view, csrf):
    """Actual generated-result form, including zero-issue coverage summaries."""
    from .proposal_views import hidden
    out = ('<form method="post" action="/b5a/m2/review">'
           + hidden('_csrf', csrf)
           + hidden('report_version', str(view.pins['report_version']))
           + hidden('report_sha256', view.pins['report_sha256'])
           + '<h2>保存内部合成审核</h2><p>决定不修改报告原件，不构成真实人工批准或外部交付。</p>')
    for key, label in [('', '整份报告')] + [(i, '问题 ' + str(n)) for n, i in enumerate(view.issue_ids, 1)]:
        suffix = '.' + key if key else ''
        out += ('<fieldset><legend>' + e(label) + '</legend><label>内部决定'
                '<select name="decision' + e(suffix) + '" required><option value="">请选择</option>'
                '<option value="APPROVE_INTERNAL">内部批准</option><option value="REJECT_INTERNAL">拒绝</option>'
                '<option value="REVISE_INTERNAL">修订</option></select></label><label>修订说明'
                '<textarea name="revision' + e(suffix) + '" maxlength="2000"></textarea></label></fieldset>')
    return out + '<button type="submit">保存本版本内部回执</button></form>'
