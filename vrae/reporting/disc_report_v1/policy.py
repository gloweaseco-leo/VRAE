"""Closed, cautious DISC editorial proposals; never objective assertions."""

from vrae.reporting.editorial import PROPOSALS as CTA_PROPOSALS

VERSION = "ra3c-disc-1.0.0"
RENDERER_VERSION = "ra3c-disc-html-1.0.0"
EDITORIAL_VERSION = "ra3c-disc-editorial-1.0.0"
PROOF_KINDS = {
    "CTA-02": "CAPTURED_CTA_HTTP_FAILURE",
    "DISC-01": "CAPTURED_DISC_HTTP_FAILURE",
    "DISC-02": "CAPTURED_DISC_HTTP_FAILURE",
}
DISC_PROPOSALS = {
    "DISC-01": {
        "impact": (
            "HYPOTHESIS",
            "这条静态首页入口可能妨碍访客继续查找分类；实际可见性、点击行为和业务影响仍需人工核实。",
        ),
        "action": (
            "RECOMMENDATION",
            "建议人工核对这条首页分类入口及其目标地址，再决定是否调整链接或目标页面。",
        ),
        "recheck": (
            "RECOMMENDATION",
            "建议在重新获准的范围内复查同一静态入口与目标响应，并由人工检查实际浏览器路径。",
        ),
    },
    "DISC-02": {
        "impact": (
            "HYPOTHESIS",
            "这条静态分类到产品路径可能中断资料查找；产品身份、实际操作和业务影响仍需人工核实。",
        ),
        "action": (
            "RECOMMENDATION",
            "建议人工核对这条分类到产品的链接及其目标地址，再决定是否修正入口或产品页面。",
        ),
        "recheck": (
            "RECOMMENDATION",
            "建议在重新获准的范围内复查同一分类链接与目标响应，并由人工核对产品上下文。",
        ),
    },
}


def proposals_for(rule_id):
    return CTA_PROPOSALS if rule_id == "CTA-02" else DISC_PROPOSALS[rule_id]
