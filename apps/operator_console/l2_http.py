"""L2 routes on the original B5B server, not a second application/server."""
import hashlib
from http.cookies import SimpleCookie
import json
from pathlib import Path
import re
import secrets

from vrae.domain.errors import DomainError
from vrae.l2.identity import Directory
from vrae.l2.ledger import Ledger
from vrae.l2.report import L2Denied, deny
from .b5a_http import FORM, Reply, form
from .interface import Response
from .proposal_views import hidden
from .views import e, link
from . import l2_views as v

PREFIX='/b5a/l2/'


class DeepConsole:
    def __init__(self,directory,ledgers,refresh=lambda:None):
        if type(directory) is not Directory or not ledgers or any(
                type(x) is not Ledger or x.directory is not directory for x in ledgers.values()):
            raise ValueError('L2_PINNED_REVIEW_PORTS_REQUIRED')
        self.directory,self.ledgers,self.refresh=directory,dict(ledgers),refresh
        self.bootstrap_csrf=secrets.token_urlsafe(32)
        self.l1_enabled=False

    def reply(self,title,body,status=200):
        if self.l1_enabled:
            body=link('/b5a/m2/','返回现有 L1 任务',key='l2-back-to-l1')+body
        return Reply(Response(status,v.layout(title,body,self.directory.mode).encode()))

    def sid(self,headers):
        raw=headers.get('Cookie','')
        keys=[x.strip().split('=',1)[0] for x in raw.split(';')] if raw else []
        if len(raw)>2048 or len(keys)!=len(set(keys)) or set(keys)-{
                'b5a_session','b5a_challenge','b5a_m2_session','b5a_m2_challenge','b5a_l2_session'}:
            deny()
        jar=SimpleCookie()
        jar.load(raw)
        if set(jar)!=set(keys) or any(not re.fullmatch('[A-Za-z0-9_-]{43}',x.value) for x in jar.values()):
            deny()
        return jar['b5a_l2_session'].value if 'b5a_l2_session' in jar else ''

    def fields(self,headers,raw,sid,path,expected):
        if headers.get('Content-Type')!=FORM:
            deny()
        fields=form(raw)
        if set(fields)!=set(expected)|{'_csrf'}:
            deny('L2_INVALID_INPUT')
        self.directory.consume(sid,path,fields.pop('_csrf'))
        return fields

    def pins(self,f):
        if not f['version'].isdigit() or len(f['version'])>8:
            deny('L2_STALE_VERSION')
        if any(not re.fullmatch('[a-f0-9]{64}',f[k]) for k in ('content_hash','display_hash')):
            deny('L2_STALE_VERSION')
        return dict(version=int(f['version']),content_hash=f['content_hash'],display_hash=f['display_hash'])

    def current(self,sid,rid,version=None):
        session=self.directory.require(sid,rid)
        ledger=self.ledgers[rid]
        if session.person.role=='READER':
            claim=session.grant_claims.get(rid)
            if claim is None:
                deny('L2_DIRECTED_ACCESS_REQUIRED')
            view=ledger.access(sid,rid,*claim)
            if version is not None and view.version['version']!=version:
                deny('L2_STALE_GRANT')
        else:
            view=ledger.read(sid,rid,version)
        return session,view

    def review_state(self,sid,rid,person,view):
        if person.role=='READER':
            return '已验证受控定向只读访问；不是正式人审或外部客户交付'
        _,decisions,_=self.ledgers[rid].history(sid,rid)
        matching=[x for x in decisions if x['decision']['version']==view.version['version']
                  and x['display_hash']==view.display_hash and x['decision']['content_hash']==view.version['content_hash']]
        if not matching:
            return '尚无本版本决定'
        item=matching[0]
        return (('责任人决定：' if item['formal_human_review'] else '演练决定（非正式人审）：')
                +v.ACTIONS[item['decision']['action']]+' · '+item['reviewer_name']+' · '+item['decision']['decided_at'])

    def handle(self,method,path,headers,raw):
        with self.directory.lock:
            try:
                self.refresh()
                if method not in ('GET','HEAD','POST'):
                    deny()
                route=path.removeprefix(PREFIX)
                if headers.get('Authorization') is not None and (route!='session' or method!='POST'):
                    deny()
                if route=='style.css' and method in ('GET','HEAD'):
                    return Reply(Response(200,Path(__file__).with_name('l2.css').read_bytes(),'text/css; charset=utf-8'))
                sid=self.sid(headers)
                if route=='' and method in ('GET','HEAD'):
                    expired=False
                    if sid:
                        try:
                            self.directory.require(sid)
                        except L2Denied:
                            sid,expired='',True
                    if not sid:
                        body=('<section class="card"><h1>L2 深度诊断与 Rebuild 工作区</h1>'
                            '<p>沿工业采购旅程核对证据、讨论改造方案并记录当前版本的责任人决定。'
                            '读取和操作均需受信签名身份；本页不收集姓名冒认、服务密钥或私钥。</p>'
                            '<form method="post" action="/b5a/l2/challenge">'
                            +hidden('_csrf',self.bootstrap_csrf)+'<button>申请签名登录挑战</button></form>'
                            '<p>独立身份提供方通过 Authorization 头完成登录；受控启动器可代为完成演练签名。</p></section>')
                    else:
                        person=self.directory.require(sid).person
                        body='<section class="card"><h1>我的 L2 深度诊断</h1><p>'+e(person.name)+'</p>'
                        for rid,ledger in self.ledgers.items():
                            meta=ledger.source.read().document['meta']
                            if rid in person.report_ids and meta['tenant_id']==person.tenant_id:
                                body+=link(PREFIX+'r/'+rid,meta['title'],key='l2-open-report')
                        body+='</section>'
                    response=self.reply('L2 工作区',body)
                    if expired:
                        return Reply(response.response,(('Set-Cookie','b5a_l2_session=; Path=/b5a/l2/; Max-Age=0; HttpOnly; SameSite=Strict'),))
                    return response
                if route=='challenge' and method=='POST':
                    if headers.get('Content-Type')!=FORM or form(raw)!={'_csrf':self.bootstrap_csrf}:
                        deny()
                    nonce,csrf=self.directory.challenge()
                    return Reply(Response(200,json.dumps({'nonce':nonce,'csrf':csrf}).encode(),'application/json'))
                if route=='session' and method=='POST':
                    if headers.get('Content-Type')!='application/json' or raw!=b'{}':
                        deny()
                    sid=self.directory.login(headers.get('Authorization',''),headers.get('X-L2-Nonce',''),headers.get('X-L2-CSRF',''))
                    age=max(1,int(self.directory.require(sid).expires-self.directory.now()))
                    return Reply(Response(303,b''),(('Location',PREFIX),
                        ('Set-Cookie',f'b5a_l2_session={sid}; Path={PREFIX}; Max-Age={age}; HttpOnly; SameSite=Strict')))
                match=re.fullmatch(r'r/([A-Za-z0-9_.-]{3,128})(?:/(.*))?',route)
                if match is None or match[1] not in self.ledgers:
                    return self.reply('页面不可用','<h1>没有可用的 L2 页面</h1>',404)
                rid,action=match[1],match[2] or ''
                ledger=self.ledgers[rid]
                person=self.directory.require(sid,rid).person
                root=PREFIX+'r/'+rid
                if action.startswith('claim/'):
                    grant_id=action.removeprefix('claim/')
                    if person.role!='READER' or not re.fullmatch('grant-[a-f0-9]{32}',grant_id):
                        deny()
                    if method=='POST':
                        f=self.fields(headers,raw,sid,path,{'token'})
                        if not re.fullmatch('[A-Za-z0-9_-]{43}',f['token']):
                            deny()
                        digest=hashlib.sha256(f['token'].encode()).hexdigest()
                        ledger.access(sid,rid,grant_id,digest)
                        self.directory.require(sid,rid).grant_claims[rid]=(grant_id,digest)
                        return Reply(Response(303,b''),(('Location',root),))
                    if method not in ('GET','HEAD'):
                        deny()
                    csrf=self.directory.action(sid,path)
                    return self.reply('验证定向访问','<section class="card"><h1>验证指定身份的受控访问</h1>'
                        '<p>仅限本次受控验证的指定接收者；没有对真实客户分享。</p><form method="post" action="'+e(path)+'">'
                        +hidden('_csrf',csrf)+'<label>一次性显示的授权密文<input type="password" name="token" maxlength="43" required autocomplete="off"></label><button data-key="l2-claim">验证并查看报告</button></form></section>')
                if action.startswith('revoke/') and method=='POST':
                    self.fields(headers,raw,sid,path,set())
                    ledger.revoke(sid,rid,action.removeprefix('revoke/'))
                    return Reply(Response(303,b''),(('Location',root+'/access'),))
                if action=='review' and method=='POST':
                    view=ledger.read(sid,rid)
                    keys={r['id'] for r in view.document['findings']+view.document['blueprint']}
                    f=self.fields(headers,raw,sid,path,{'version','content_hash','display_hash','action','reason','attest'}|{'item.'+k for k in keys})
                    receipt=ledger.review(sid,rid,**self.pins(f),action=f['action'],reason=f['reason'],
                        items={k:f['item.'+k] for k in keys},attest=f['attest']=='yes')
                    return Reply(Response(303,b''),(('Location',root+'/decision/'+receipt['decision']['decision_id']),))
                if action.startswith('revise/') and method=='POST':
                    view=ledger.read(sid,rid)
                    originals={b['id']:b['change'] for b in view.document['blueprint']}
                    key=action.removeprefix('revise/')
                    if key not in originals:
                        deny()
                    f=self.fields(headers,raw,sid,path,{'version','content_hash','display_hash','change'})
                    changes={key:f['change']} if f['change']!=originals[key] else {}
                    ledger.revise(sid,rid,**self.pins(f),changes=changes)
                    return Reply(Response(303,b''),(('Location',root+'/blueprint'),))
                if action=='access' and method=='POST':
                    f=self.fields(headers,raw,sid,path,{'version','content_hash','display_hash','recipient'})
                    grant,token=ledger.issue(sid,rid,**self.pins(f),recipient_id=f['recipient'])
                    target=root+'/claim/'+grant['grant_id']
                    body=('<section class="card"><h1>受控定向访问已创建</h1><p>只显示一次；只保存哈希。必须由指定受控接收者签名登录后使用。</p>'
                        '<p data-key="l2-created-grant">'+e(grant['grant_id'])+'</p><p>接收者：'+e(grant['subject_ref'])+'</p>'
                        '<label>授权密文（请妥善保管，不放入网址）<input type="password" readonly data-key="l2-grant-token" value="'+e(token)+'"></label>'
                        +link(target,'受控接收者验证页面',key='l2-claim-link')+link(root+'/access','返回访问管理')+'</section>')
                    return self.reply('受控定向访问',body)
                if method not in ('GET','HEAD'):
                    deny()
                version=None
                if action.startswith('v/'):
                    number=action[2:]
                    if not number.isdigit() or len(number)>8:
                        deny()
                    version=int(number)
                session,view=self.current(sid,rid,version)
                if action in ('report-print','blueprint-print'):
                    state=self.review_state(sid,rid,person,view)
                    self.current(sid,rid,version)
                    return Reply(Response(200,v.export(view,person,action,self.directory.mode,state).encode()))
                if action in ('executive','executive-document'):
                    from .l2_executive_views import render
                    state=self.review_state(sid,rid,person,view)
                    body=render(view,person,state,document=action=='executive-document')
                elif action=='':
                    state=self.review_state(sid,rid,person,view)
                    body=v.report(view,person,review_state=state)
                elif action=='blueprint':
                    csrf={b['id']:self.directory.action(sid,root+'/revise/'+b['id']) for b in view.document['blueprint']} if person.role in ('OWNER','REVIEWER') else None
                    body=v.blueprint(view,person,csrf)
                elif action=='evidence' or action.startswith('evidence/'):
                    key=action.split('/',1)[1] if '/' in action else None
                    if key is not None and key not in {x['id'] for x in view.document['evidence']}:
                        deny()
                    body=v.evidence(view,person,key)
                elif action=='review':
                    if person.role not in ('OWNER','REVIEWER'):
                        deny()
                    body=v.review(view,person,self.directory.action(sid,path),self.directory.mode)
                elif action=='history':
                    versions,decisions,_=ledger.history(sid,rid)
                    body=v.history(view,person,versions,decisions)
                elif action.startswith('v/'):
                    if person.role not in ('OWNER','REVIEWER'):
                        deny()
                    body='<section class="notice"><h1>历史版本 '+str(version)+' · 只读核对</h1><p>旧决定和授权不会自动作用于当前新版本。</p></section>'
                    body+=v.report(view,person)+v.blueprint(view,person)
                elif action.startswith('decision/'):
                    _,items,_=ledger.history(sid,rid)
                    receipt=next((x for x in items if x['decision']['decision_id']==action.split('/',1)[1]),None)
                    if receipt is None:
                        deny()
                    old=ledger.read(sid,rid,receipt['decision']['version'])
                    body=v.receipt(old,person,receipt)
                elif action=='access':
                    if person.role!='OWNER':
                        deny()
                    if self.directory.mode!='CONTROLLED':
                        body='<h1>尚未启用外部客户访问</h1><p>本轮只验证受控身份的定向可撤销访问，不向外部真实客户分享。</p>'
                    else:
                        _,_,grants=ledger.history(sid,rid)
                        recipients=[p for p in self.directory.people.values() if p.role=='READER' and p.active
                            and p.tenant_id==person.tenant_id and rid in p.report_ids]
                        revoke={g['grant_id']:self.directory.action(sid,root+'/revoke/'+g['grant_id']) for g in grants if g['status']=='ACTIVE'}
                        body=v.access(view,person,self.directory.action(sid,path),recipients,grants,revoke)
                else:
                    deny()
                # Revalidate directed access after rendering, not merely login.
                self.current(sid,rid,version)
                return self.reply('L2 深度诊断',body)
            except Exception as exc:
                code=exc.args[0] if isinstance(exc,L2Denied) and exc.args else 'L2_REQUEST_DENIED'
                allowed={'L2_LOGIN_DENIED','L2_STALE_VERSION','L2_STALE_GRANT','L2_REVIEW_REQUIRED',
                    'L2_DIRECTED_ACCESS_REQUIRED','L2_DIRECTED_ACCESS_DENIED','L2_SOURCE_CHANGED',
                    'L2_EVERY_ITEM_REQUIRES_REVIEW','L2_UNRESOLVED_REVIEW_ITEMS','L2_REVIEW_ATTESTATION_REQUIRED',
                    'L2_EXTERNAL_ACCESS_NOT_ENABLED'}
                if code not in allowed:
                    code='L2_REQUEST_DENIED'
                if isinstance(exc,DomainError):
                    code='L2_REQUEST_DENIED'
                status=409 if code in ('L2_STALE_VERSION','L2_STALE_GRANT') else 403
                return self.reply('请求未提供数据','<section class="notice"><h1>请求未提供报告或写入结果</h1><p data-code="'+code+'">'+code+'</p><p>请使用当前签名身份重新核对来源、版本或访问授权。旧决定保留，不自动迁移到新版本。</p>'+link(PREFIX,'返回 L2 工作区')+'</section>',status)
