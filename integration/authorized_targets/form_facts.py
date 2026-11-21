"""Static form declarations only: no values, interaction, visibility or delivery."""
import re
from urllib.parse import urljoin, urlsplit

from vrae.collection.manifest import document_hash
from vrae.rules.universal_static import Static, ancestors

LABELS = {
    'NAME': ['name','your name','full name','姓名'],
    'EMAIL': ['email','e-mail','your email','email address','邮箱','电子邮箱'],
    'COMPANY': ['company','company name','公司','公司名称'],
    'PHONE': ['phone','telephone','tel','电话'],
    'COUNTRY': ['country','国家'], 'SUBJECT': ['subject','主题'],
    'MESSAGE': ['message','your message','inquiry','enquiry','content','留言','询盘内容'],
    'PRODUCT': ['product','product name','产品'], 'MODEL': ['model','model number','型号'],
    'QUANTITY': ['quantity','qty','数量'], 'SEARCH': ['search','搜索'],
}


def normalized(text):
    return re.sub(r'[\s*:：]+','',text.casefold())


def inside(node, parent):
    return any(a is parent for a in ancestors(node))


def label_text(node):
    if node['tag'] in ('input', 'textarea', 'select', 'button') or node['excluded']:
        return ''
    return node['direct_text'] + ''.join(label_text(c) for c in node['children'])


class Forms(Static):
    def handle_starttag(self, tag, attrs):
        super().handle_starttag(tag, attrs)
        if tag == 'form':
            node = self.nodes[-1]
            # Static excludes forms for prose extraction. Only this local parser
            # inspects them; keep all original hidden/inert/duplicate checks.
            parent = node['parent']
            node['excluded'] = (bool(parent and parent['excluded']) or len(attrs)!=len(dict(attrs))
                or any(k in node['attrs'] for k in ('hidden','inert'))
                or node['attrs'].get('aria-hidden')=='true'
                or bool(re.search(r'display\s*:\s*none|visibility\s*:\s*hidden',
                                  (node['attrs'].get('style') or ''),re.I)))


def span(parser, node, evidence):
    end = node['end'] if node['end'] is not None else node['start']+len(node['start_tag'])
    if end <= node['start'] or end-node['start']>65536:
        raise ValueError('FORM_SPAN_BOUND')
    return {k:evidence[k] for k in ('evidence_ref','snapshot_ref','locator','content_sha256')} | {
        'byte_start':len(parser.text[:node['start']].encode('utf-8')),
        'byte_end':len(parser.text[:end].encode('utf-8'))}


def extract(raw, evidence, final_url):
    if len(raw)>131072:
        raise ValueError('FORM_HTML_BOUND')
    parser = Forms(raw.decode('utf-8',errors='strict'))
    parser.feed(parser.text)
    parser.close()
    if parser.ambiguous:
        raise ValueError('FORM_HTML_AMBIGUOUS')
    nodes=parser.nodes
    forms=[n for n in nodes if n['tag']=='form' and not n['excluded'] and n['end'] is not None]
    nested=[n for n in forms if any(a['tag']=='form' for a in ancestors(n))]
    forms=[n for n in forms if all(n is not c for c in nested) and not any(inside(c,n) for c in nested)]
    result=[]
    for form in forms[:8]:
        members=[n for n in nodes if inside(n,form) and not n['excluded']]
        controls=[n for n in members if n['tag'] in ('input','textarea','select')]
        visible_controls=[n for n in controls if (n['attrs'].get('type') or 'text').lower()
                          not in ('hidden','submit','reset','button','image')]
        bindings=span(parser,form,evidence)
        fields=[]
        for node in visible_controls[:32]:
            attrs=node['attrs']
            kind=(attrs.get('type') or 'text').lower() if node['tag']=='input' else node['tag']
            kind=kind if kind in ('text','email','tel','number','search','password','textarea','select','checkbox','radio','file','url','date') else 'other'
            labels=[]
            identity=attrs.get('id')
            if identity and sum(n['attrs'].get('id')==identity for n in nodes)==1:
                labels=[n for n in members if n['tag']=='label' and n['attrs'].get('for')==identity]
            if not labels:
                for parent in ancestors(node):
                    if parent is form:
                        break
                    if sum(inside(n,parent) for n in visible_controls)!=1:
                        continue
                    labels=([parent] if parent['tag']=='label' else
                        [n for n in members if n['tag']=='label' and inside(n,parent)])
                    if not labels and parent['tag']=='tr':
                        cells=[n for n in parent['children'] if n['tag'] in ('th','td')]
                        labels=[cells[0]] if len(cells)==2 and not inside(node,cells[0]) else []
                    if labels:
                        break
            label=labels[0] if len(labels)==1 and 0<len(label_text(labels[0]).strip())<=120 else None
            semantic=next((k for k,values in LABELS.items() if label and normalized(label_text(label))
                           in {normalized(v) for v in values}),None)
            basis='SOURCE_LABEL' if semantic else 'INPUT_TYPE' if kind in ('email','tel','search','password') else 'UNRESOLVED'
            semantic=semantic or {'email':'EMAIL','tel':'PHONE','search':'SEARCH','password':'ACCOUNT_SECRET'}.get(kind,'UNKNOWN')
            binding=span(parser,node,evidence)
            fields.append({'field_ref':'field-'+document_hash(binding),'kind':semantic,'input_type':kind,
                'label_basis':basis,'required_attribute':'required' in attrs,
                'disabled_attribute':'disabled' in attrs,'readonly_attribute':'readonly' in attrs,
                'binding':binding,'label_binding':span(parser,label,evidence) if label and semantic!='UNKNOWN' else None})
        kinds={f['kind'] for f in fields}
        purpose=('ACCOUNT_CANDIDATE' if 'ACCOUNT_SECRET' in kinds else 'INQUIRY_CANDIDATE'
            if 'MESSAGE' in kinds and kinds & {'EMAIL','NAME','COMPANY','PHONE'} else
            'SEARCH_CANDIDATE' if 'SEARCH' in kinds and kinds<={'SEARCH','UNKNOWN'} else 'UNRESOLVED')
        action=(form['attrs'].get('action') or '')
        target=urlsplit(urljoin(final_url,action))
        base=urlsplit(final_url)
        destination=('UNRESOLVED' if target.scheme not in ('http','https') or target.query or target.fragment
            or target.username or target.password or any(n['attrs'].get('formaction') for n in members)
            else 'SAME_ORIGIN' if (target.scheme,target.netloc)==(base.scheme,base.netloc) else 'EXTERNAL')
        method=(form['attrs'].get('method') or 'get').lower()
        result.append({'form_ref':'form-'+document_hash(bindings),'binding':bindings,'purpose':purpose,
            'method':method.upper() if method in ('get','post') else 'UNKNOWN','action_scope':destination,
            'fields':fields,'hidden_control_count':sum((n['attrs'].get('type') or '').lower()=='hidden' for n in controls),
            'submit_control_observed':any(n['tag']=='button' and (n['attrs'].get('type') or 'submit').lower()=='submit'
                or n['tag']=='input' and (n['attrs'].get('type') or '').lower() in ('submit','image') for n in members),
            'field_coverage':{'total':len(visible_controls),'returned':len(fields),'truncated':len(visible_controls)>32},
            'visibility':'UNKNOWN','product_context_transfer':'UNKNOWN','submission_tested':False,
            'delivery':'UNKNOWN','native_fact_admission':'NONE'})
    return {'forms':result,'coverage':{'total':len(forms),'returned':len(result),'truncated':len(forms)>8},
            'nested_forms_excluded':len(nested),
            'unclosed_forms_excluded':sum(n['tag']=='form' and n['end'] is None for n in nodes)}
