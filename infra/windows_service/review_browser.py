"""Local review presentation only; original API plus fresh actual MFA makes decisions."""

import argparse
import hashlib
from html import escape
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import secrets
import threading
import time
from urllib.parse import parse_qs
import webbrowser
from infra.windows_service.review_operator import Port
from infra.windows_service.private_host import put_private
from infra.windows_service.windows_credentials import current_sid


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--operator-image", required=True)
    parser.add_argument("--name", default="vrae-windows")
    parser.add_argument("--receipt", required=True)
    a = parser.parse_args()
    port = Port(a.operator_image, a.name)
    drafts = port.private("review-pending.json")
    if len(drafts) != 2 or not all(d.get("source_fact_count", 0) > 0 for d in drafts):
        raise PermissionError("REAL_SOURCE_FACTS_REQUIRED_FOR_THIS_ACCEPTANCE_REVIEW")
    sid_hash = hashlib.sha256(current_sid().encode()).hexdigest()
    receipt = Path(a.receipt)
    capability = secrets.token_urlsafe(32)
    route = "/review/" + capability
    done = threading.Event()
    deadline = time.monotonic() + 1800
    reviews = []
    lock = threading.Lock()

    def progress(state, **extra):
        receipt.write_text(json.dumps({"state": state, **extra}), encoding="utf8")

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *_):
            pass

        def reply(self, status, text):
            raw = text.encode("utf8")
            self.send_response(status)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(raw)))
            self.send_header("Cache-Control", "no-store, max-age=0")
            self.send_header("Referrer-Policy", "no-referrer")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header(
                "Content-Security-Policy",
                "default-src 'none'; style-src 'unsafe-inline'; form-action 'self'; frame-ancestors 'none'; base-uri 'none'",
            )
            self.end_headers()
            self.wfile.write(raw)

        def valid(self):
            return (
                self.client_address[0] == "127.0.0.1"
                and self.path == route
                and self.headers.get("Host") == authority
                and time.monotonic() < deadline
                and not done.is_set()
            )

        def page(self):
            d = drafts[len(reviews)]
            document = d["report"]
            items = d["report"]["findings"] + d["report"]["blueprint"]
            labels = {
                "kind": "类型",
                "native_result": "原始评估结果",
                "statement": "观察与结论",
                "scope": "适用范围",
                "uncertainty": "未确认内容",
                "buyer_impact": "可能影响",
                "priority_basis": "优先级依据",
                "recommendation": "建议",
                "recheck": "复核方式",
                "change": "拟议动作",
                "customer_inputs": "需要提供的输入",
                "acceptance": "验收条件",
                "owner_role": "责任人",
                "dependency": "依赖与限制",
                "service_basis": "服务边界",
                "page": "相关页面",
                "source_fact_refs": "来源事实引用",
                "native_details": "原始比较与反证上下文",
            }
            cards = []
            for item in items:
                content = ""
                for key, label in labels.items():
                    if key not in item:
                        continue
                    value = item[key]
                    value = (
                        value
                        if isinstance(value, str)
                        else json.dumps(value, ensure_ascii=False, indent=2)
                    )
                    content += "<p><b>" + label + "：</b>" + escape(value) + "</p>"
                cards.append(
                    "<article><h3>"
                    + escape(item.get("title", item["id"]))
                    + "</h3>"
                    + content
                    + '<p><label><input required type="checkbox" name="ack" value="'
                    + escape(item["id"], quote=True)
                    + '"> 我已审阅本项及其限制，确认保留 UNKNOWN 与原始引用。</label></p></article>'
                )
            checks = "".join(cards)
            return (
                '<!doctype html><html lang="zh-CN"><meta charset="utf-8"><title>VRAE 自控来源实际报告审核</title>'
                "<style>body{font:17px system-ui;max-width:1150px;margin:24px auto;padding:0 24px}pre{white-space:pre-wrap;overflow-wrap:anywhere;background:#f4f4f4;padding:20px;max-height:65vh;overflow:auto}code{overflow-wrap:anywhere}p{line-height:1.6}textarea{width:95%;font:18px system-ui}article{border:1px solid #ccc;padding:20px;margin:20px 0;border-radius:8px}button{font-size:20px;padding:14px}input[type=checkbox]{width:20px;height:20px}</style>"
                "<h1>实际报告审核 " + str(len(reviews) + 1) + " / " + str(len(drafts)) + "</h1>"
                "<p><b>尚未批准或发布。</b>仅针对已授权的自控公网样例，不是真实客户、真实供应商资格或工程认证。模型未获费用授权，AI 不可用。</p>"
                "<p>受邀主体：<b>"
                + escape(d["subject_ref"])
                + "</b><br>任务："
                + escape(d["audit_ref"])
                + "<br>实际来源事实数："
                + str(d["source_fact_count"])
                + "<br>报告展示哈希：<code>"
                + escape(d["display_hash"])
                + "</code></p>"
                "<h2>实际采集范围与状态</h2><pre>"
                + escape(json.dumps(d["snapshots"], ensure_ascii=False, indent=2))
                + "</pre>"
                "<h2>"
                + escape(document["meta"]["title"])
                + "</h2><p>"
                + escape(document.get("summary", ""))
                + "</p>"
                "<p>" + escape(document.get("buyer", {}).get("assumption", "")) + "</p>"
                "<h2>证据与原文引用</h2><details><summary>展开已保留证据、原文与哈希</summary><pre>"
                + escape(json.dumps(document["evidence"], ensure_ascii=False, indent=2))
                + "</pre></details>"
                "<details><summary>展开原始完整报告（保留全部字段）</summary><pre>"
                + escape(json.dumps(document, ensure_ascii=False, indent=2))
                + "</pre></details>"
                '<form method="post"><input type="hidden" name="confirmation" value="'
                + capability
                + '">'
                '<input type="hidden" name="position" value="' + str(len(reviews)) + '">'
                "<h2>逐项审阅：观察、UNKNOWN、反证与建议</h2>"
                + checks
                + '<p><label><input required type="checkbox" name="attest" value="yes"> 我实际阅读了上述报告，确认来源声明仅为样例，缺失参数和未验证内容继续保持 UNKNOWN，没有被当成已证实的业务事实。</label></p>'
                '<p><label><input required type="checkbox" name="directed_grant" value="yes"> 我同意审核通过后，仅向该任务当前受邀收件人发放短期报告读取授权，供本轮外部验收，并允许之后测试撤销。</label></p>'
                '<p>请填写你的实际审核意见（至少12个字符）：</p><textarea required name="reason" minlength="12" maxlength="2000" rows="4"></textarea>'
                "<p>不同意时不要提交，可关闭本页并告诉开发者需要修改的内容。</p>"
                '<button type="submit">确认本份审阅意见，进入下一步</button></form></html>'
            )

        def do_GET(self):
            with lock:
                if not self.valid():
                    return self.reply(404, "Not found")
                progress(
                    "ACTUAL_DRAFT_DELIVERED_FOR_HUMAN_REVIEW",
                    case=len(reviews) + 1,
                    subject_ref=drafts[len(reviews)]["subject_ref"],
                )
                self.reply(200, self.page())

        def do_POST(self):
            with lock:
                n = self.headers.get("Content-Length", "")
                if (
                    not self.valid()
                    or self.headers.get("Origin") != "http://" + authority
                    or not n.isdigit()
                    or not 0 < int(n) <= 16384
                    or self.headers.get("Content-Type") != "application/x-www-form-urlencoded"
                ):
                    return self.reply(403, "Forbidden")
                body = parse_qs(self.rfile.read(int(n)).decode("utf8"))
                d = drafts[len(reviews)]
                expected = {x["id"] for x in d["report"]["findings"] + d["report"]["blueprint"]}
                reason = body.get("reason", [""])[0].strip()
                if (
                    set(body)
                    != {"confirmation", "position", "ack", "attest", "directed_grant", "reason"}
                    or body["confirmation"] != [capability]
                    or body["position"] != [str(len(reviews))]
                    or body["attest"] != ["yes"]
                    or body["directed_grant"] != ["yes"]
                    or set(body["ack"]) != expected
                    or len(body["ack"]) != len(expected)
                    or not 12 <= len(reason) <= 2000
                ):
                    return self.reply(
                        400,
                        '<meta charset="utf-8"><p>尚未完整逐项确认或缺少实际审核意见。请返回后核对，不会产生批准记录。</p>',
                    )
                reviews.append(
                    {
                        "audit_ref": d["audit_ref"],
                        "display_hash": d["display_hash"],
                        "decision": {
                            "action": "APPROVE",
                            "reason": reason,
                            "items": {i: "ACK" for i in expected},
                            "attest": True,
                        },
                    }
                )
                if len(reviews) < len(drafts):
                    return self.reply(200, self.page())
                put_private(
                    a.operator_image,
                    a.name,
                    "review-actions.json",
                    json.dumps(
                        {
                            "windows_sid_sha256": sid_hash,
                            "grant_current_invited_acceptance_recipients": True,
                            "reviews": reviews,
                        }
                    ).encode(),
                )
                self.reply(
                    200,
                    '<meta charset="utf-8"><title>VRAE 审阅意见已暂存</title><h1>两份审阅意见已暂存</h1><p>尚未签名批准或发布。下一步须用真实 Windows 密码及手机验证码签发本次 Reviewer 身份，再由原报告API核验版本并记录审核与定向授权。</p>',
                )
                progress("HUMAN_REVIEW_STAGED_REQUIRES_FRESH_MFA", review_count=len(reviews))
                done.set()

    with ThreadingHTTPServer(("127.0.0.1", 0), Handler) as server:
        server.daemon_threads = True
        authority = "127.0.0.1:" + str(server.server_port)
        threading.Thread(target=server.serve_forever, daemon=True).start()
        progress("WAITING_ACTUAL_HUMAN_REVIEW", report_count=len(drafts))
        webbrowser.open("http://" + authority + route, new=1)
        confirmed = done.wait(1800)
        server.shutdown()
    if not confirmed:
        progress("HUMAN_REVIEW_PAGE_EXPIRED_NO_APPROVAL")


if __name__ == "__main__":
    main()
