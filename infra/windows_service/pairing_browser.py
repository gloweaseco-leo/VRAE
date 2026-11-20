"""One-time loopback phone-pairing page. Never a public IdP or MFA assertion."""
import argparse
import base64
import hashlib
from html import escape
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
import io
import json
from pathlib import Path
import secrets
import threading
import time
from urllib.parse import quote,parse_qs
import webbrowser
import qrcode
from infra.windows_service.pair_reviewer import action
from infra.windows_service.private_host import put_private
from infra.windows_service.windows_credentials import current_sid


def main():
    p=argparse.ArgumentParser()
    p.add_argument('--operator-image',required=True)
    p.add_argument('--name',default='vrae-windows')
    p.add_argument('--receipt',required=True)
    a=p.parse_args()
    receipt=Path(a.receipt)
    def progress(state,**extra):
        receipt.write_text(json.dumps({'state':state,**extra}),encoding='utf8')
    sid=current_sid()
    pair=action(a.operator_image,a.name,'begin-pair',{'sid':sid})
    label='VRAE Reviewer '+pair['nonce'][-6:]
    uri='otpauth://totp/'+quote('VRAE:'+label,safe='')+'?secret='+pair['seed']+'&issuer=VRAE&algorithm=SHA1&digits=6&period=30'
    png=io.BytesIO()
    qrcode.make(uri).save(png,format='PNG')
    image=base64.b64encode(png.getvalue()).decode()
    capability=secrets.token_urlsafe(32)
    route='/pair/'+capability
    done=threading.Event()
    deadline=time.monotonic()+600
    class Handler(BaseHTTPRequestHandler):
        def log_message(self,*_):
            pass
        def reply(self,status,body):
            raw=body.encode('utf8')
            self.send_response(status)
            self.send_header('Content-Type','text/html; charset=utf-8')
            self.send_header('Content-Length',str(len(raw)))
            self.send_header('Cache-Control','no-store, max-age=0')
            self.send_header('Pragma','no-cache')
            self.send_header('Referrer-Policy','no-referrer')
            self.send_header('X-Content-Type-Options','nosniff')
            self.send_header('Content-Security-Policy',"default-src 'none'; img-src data:; style-src 'unsafe-inline'; form-action 'self'; frame-ancestors 'none'; base-uri 'none'")
            self.end_headers()
            self.wfile.write(raw)
        def valid(self):
            return (self.client_address[0]=='127.0.0.1' and self.path==route
                and self.headers.get('Host')==authority and time.monotonic()<deadline and not done.is_set())
        def do_GET(self):
            if not self.valid():
                return self.reply(404,'Not found')
            progress('QR_PAGE_DELIVERED_TO_LOCAL_BROWSER',account_label=label,loopback_only=True,qr_png_bytes=len(png.getvalue()))
            self.reply(200,'<!doctype html><html lang="zh-CN"><meta charset="utf-8"><title>VRAE 本机手机扫码配对</title>'
                '<style>body{font:18px system-ui;max-width:850px;margin:32px auto;padding:0 20px}img{width:360px;height:360px;image-rendering:pixelated}strong{font-size:24px}button{font-size:20px;padding:14px}p{line-height:1.6}</style>'
                '<h1>VRAE 本机手机扫码配对</h1><p>此页面仅在本机临时提供，不是公网服务。先不要输入 Windows 密码。</p>'
                '<p>手机打开 Microsoft Authenticator，点击 <b>＋ → 其他账户 → 扫描二维码</b>。</p>'
                '<img alt="用手机 Authenticator 扫描此二维码" src="data:image/png;base64,'+image+'">'
                '<p>扫描后手机必须出现这条新记录：<br><strong>'+escape(label)+'</strong></p>'
                '<p>请勿使用旧的 VRAE Windows Reviewer 条目。不要将二维码或验证码发到聊天。</p>'
                '<form method="post"><input type="hidden" name="confirmation" value="'+capability+'">'
                '<button type="submit">手机已显示上述新条目，完成扫码</button></form></html>')
        def do_POST(self):
            origin=self.headers.get('Origin')
            length=self.headers.get('Content-Length','')
            if (not self.valid() or origin!='http://'+authority or not length.isdigit() or not 0<int(length)<256
                or self.headers.get('Content-Type')!='application/x-www-form-urlencoded'):
                return self.reply(403,'Forbidden')
            values=parse_qs(self.rfile.read(int(length)).decode('ascii'))
            if values!={'confirmation':[capability]}:
                return self.reply(403,'Forbidden')
            put_private(a.operator_image,a.name,'pairing-label.json',json.dumps({'sid':sid,
                'seed_sha256':hashlib.sha256(pair['seed'].encode()).hexdigest(),'account_label':label}).encode())
            self.reply(200,'<meta charset="utf-8"><title>VRAE 扫码步骤已确认</title><h1>扫码步骤已确认</h1>'
                '<p>还未完成 MFA 身份注册。后续将另外验证 Windows 账户密码及此新条目的六位码。</p><p>现在可以关闭本页。</p>')
            done.set()
    with ThreadingHTTPServer(('127.0.0.1',0),Handler) as server:
        server.daemon_threads=True
        authority='127.0.0.1:'+str(server.server_port)
        thread=threading.Thread(target=server.serve_forever,daemon=True)
        thread.start()
        progress('WAITING_PHONE_QR_IN_LOCAL_BROWSER',account_label=label,loopback_only=True)
        # The capability URL is never printed, logged, or written into a receipt.
        webbrowser.open('http://'+authority+route,new=1)
        confirmed=done.wait(600)
        server.shutdown()
    progress('PHONE_KEY_ADDED_REQUIRES_WINDOWS_AND_TOTP' if confirmed else 'LOCAL_PAIRING_PAGE_EXPIRED',
             account_label=label,loopback_only=True)


if __name__=='__main__':
    main()
