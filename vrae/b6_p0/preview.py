"""One bounded sanitized private page; no source prose, contacts, links or script."""

from dataclasses import dataclass
from html import escape
from .contracts import Candidate, canonical, deny, sha


def render(core):
    count = len(core["findings"])
    headline = (f"已验证的静态范围内有 {count} 项证据发现，等待人工核对。" if count
                else "未形成可报告问题；零发现不代表已批准或全站没有问题。")
    basis = sha(canonical({k: v for k, v in core.items()
                           if k not in {"private_html_sha256", "content_digest"}}))
    text = f'''<!doctype html><html lang="zh-CN"><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<meta http-equiv="Content-Security-Policy" content="default-src 'none'; style-src 'unsafe-inline'; base-uri 'none'; form-action 'none'">
<title>私有交接候选 · NOT APPROVED</title><style>
@page{{size:A4;margin:14mm}}*{{box-sizing:border-box}}body{{margin:0;background:#f5f5ef;color:#193536;font:16px/1.7 sans-serif}}
main{{max-width:820px;margin:auto;padding:28px}}.bar{{background:#193536;color:white;padding:12px;font-size:13px}}
section{{padding:18px;border:1px solid #c8d4ce;margin:16px 0;background:white}}h1{{font-size:26px;line-height:1.4}}
h2{{font-size:18px}}code{{overflow-wrap:anywhere;font-size:12px}}small{{font-size:13px}}@media print{{body{{background:white}}main{{padding:0}}}}
</style><div class="bar">PRIVATE PREVIEW · NOT APPROVED · 仅内部核对，不可向客户发送</div>
<main><h1>私有交接预检候选</h1><p>{escape(headline)}</p>
<section><h2>权限仍未满足</h2><p>本页不是审核决定、分享授权或访问凭证。真实人员审批、Owner 收件人同意与法律依据均未证明。</p>
<p>无公开链接、无可兑换 token、无客户通知、无 VEYFRONT 外发。</p></section>
<section><h2>已检查范围与未知项</h2><p>仅反映已验证的合成捕获字节与引用区间；未检查范围仍为 UNKNOWN。不能推导采购影响、ROI、排名或 E2/E3 业务结果。</p>
<p>本页不包含原始正文、完整 Guard、联系人、登录材料或外部链接。</p></section>
<section><h2>核对指纹</h2><small>候选内容基准 SHA256</small><br><code>{basis}</code>
<p><small>原始资料与完整核对信息仅留在受控 Reviewer 环境。</small></p></section>
<footer>TEST_ONLY_PRIVATE_PREVIEW · 非自然人签署 · NOT APPROVED · 禁止交付</footer></main></html>'''
    return text.encode("utf-8")


@dataclass(frozen=True)
class PrivatePackage:
    candidate: Candidate
    private_html: bytes

    def __post_init__(self):
        if type(self.candidate) is not Candidate or type(self.private_html) is not bytes:
            deny()
        d = self.candidate.document
        if (sha(self.private_html) != d["private_html_sha256"]
                or self.private_html != render(d)):
            deny("B6_SOURCE_BINDING_DENIED")
