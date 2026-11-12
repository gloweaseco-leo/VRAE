"""Bounded Chinese review-copy vocabulary for the supported static CTA failure.

These proposals require their own replayed HUMAN_REVIEW_REQUIRED bindings.
They are never objective findings, promises, approved actions or lead events.
"""
EDITORIAL_VERSION = 'ra3c-zh-editorial-1.0.0'
IMPACT = '采购商从产品页继续寻找联系入口时，可能需要额外绕行。是否影响实际询盘，仍需人工核实。'
ACTION = '建议先确认该联系页面是否仍在使用，再修正产品页链接或恢复对应页面；实施前须人工批准。'
RECHECK = '在获准环境中从同一产品页重新访问该 href，核对目标 HTTP 状态与跳转；表单送达需另行授权验证。'
PROPOSALS = {'impact': ('HYPOTHESIS', IMPACT), 'action': ('RECOMMENDATION', ACTION),
             'recheck': ('RECOMMENDATION', RECHECK)}
LIMITATIONS = [
    '仅限本次保留的静态 HTML、原始标签与已记录 HTTP 响应，不代表全站或实时状态。',
    '产品规格、公司自述仅为网站原文；未核实真实性、法律主体、工厂、证书或资质。',
    '未验证页面实际可见性、表单提交与送达、询盘转化、销售损失或 Google 排名。',
    '未检查部分不代表没有问题；受限、未知及缺失证据不作为缺陷。',
    '合成工业样本；无真实模型调用。Human Gold 0/26 尚未评估，不提供准确率结论。',
    '本页仅供内部复核；NOT_APPROVED，不可客户外发，不产生 E2/E3 或报价承诺。',
]
