"""Internal preparation over the existing PG Brief; no commercial state writes."""
from html import escape


def cost_books(document):
    # Original runtime combines collection/C1/C2; never invent a model split.
    kinds = [('COLLECTION_BROWSER_COMPUTE', '采集／浏览器／计算', 'DIAGNOSIS_RUNTIME'),
             ('MODEL_VENDOR', '模型／供应商', None),
             ('HUMAN_REVIEW', '人工审核', 'REVIEW_ACTIVITY'),
             ('BUSINESS_OUTREACH', '商务触达', 'SALES_PREPARATION')]
    books = []
    for key, label, kind in kinds:
        rows = [r for r in document['activities'] if r['kind'] == kind and
                (key != 'HUMAN_REVIEW' or r['actor_kind'] == 'HUMAN_ATTESTED')]
        # Internal sales preparation != real outreach, and runtime != collection invoice.
        books.append({'book': key, 'label': label, 'cost_status': 'UNKNOWN', 'amount_micros': None,
                      'measurement_status': 'MEASURED' if rows else 'UNKNOWN',
                      'wall_ns': sum(r['wall_ns'] for r in rows) if rows else None,
                      'allocation_status': 'UNRECONCILED' if rows else 'UNKNOWN',
                      'source_refs': [r['operation_ref'] for r in rows]})
    return books


def render(document, row, root, nonce, *, stored):
    def e(x):
        return escape(str(x), quote=True)
    body = '<section class="card"><h2>VF 内部接单准备</h2><p>仅使用当前版本内部 Brief。服务目录 SERVICE_CATALOG_PENDING；标准候选／定制评估尚未映射已确认服务目录版本。工程确认、资质与素材权利由企业责任人提供。</p>'
    body += '<p>未连接 VF CRM；不发送询盘，不自动报价。客户确认、E2/E3、正式人审、外发及素材授权均未成立。</p>'
    state = row['state'] if row else 'NOT_SUBMITTED'
    body += '<p data-key="vf-intake-state">有界合成回执：' + e(state) + '</p>'
    body += '<p>独立收方签名 ACK 只确认内部模拟接收。刷新／重复提交不生成 ACK；退回、失败、重试和撤销保留当前版本边界。此演练状态仅在进程内保存，重启后需重新准备；原 PG Brief 不变。</p>'
    if row:
        body += '<p>尝试 ' + str(row['attempt']) + '；Brief SHA256 ' + e(row['brief_sha256']) + '；收方回执 SHA256 ' + e(row['receiver_receipt_sha256'] or 'UNKNOWN') + '</p>'
    if stored:
        actions = [('submit', '准备合成内部接单（等待收方）')] if not row else []
        if row and row['state'] in ('REJECTED', 'RETRYABLE_FAILED'):
            actions.append(('retry', '修订准备后重试本版本'))
        if row and row['state'] != 'REVOKED':
            actions.append(('revoke', '撤销本次合成接单'))
        for action, label in actions:
            body += '<form method="post" action="' + e(root+'/'+action) + '"><input type="hidden" name="_csrf" value="' + e(nonce[action]) + '"><button data-key="vf-'+action+'">'+label+'</button></form>'
    else:
        body += '<p>先用下方原按钮保存并从 PostgreSQL 回读内部 Brief，再准备模拟接单。</p>'
    body += '<h3>四本费用账</h3><p>MEASURED 是实际计量；ESTIMATED 是有依据的估算；UNKNOWN 不表示 0；UNRECONCILED 表示尚未分摊／对账。下列时长不代表实际人工服务或客户触达。</p><ul>'
    for book in cost_books(document):
        duration = str(book['wall_ns']) + ' ns' if book['wall_ns'] is not None else 'UNKNOWN'
        body += '<li data-cost-book="'+book['book']+'">'+book['label']+'：费用 '+book['cost_status']+'（金额 null）；时长 '+duration+' · '+book['measurement_status']+'；分摊 '+book['allocation_status']+'</li>'
    return body + '</ul><p>E3 分母未确认；单位合格商机成本 null。</p></section>'
