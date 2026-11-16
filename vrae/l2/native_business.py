"""Chinese procurement presentation over verified C1 rows, never a new evaluator."""
import re

from .report import encoded, sha

FIELDS={'flow':'额定流量','head':'额定扬程','power':'电机功率','voltage':'供电电压',
        'frequency':'供电频率','pressure':'最大工作压力','temperature':'介质温度',
        'material':'阀体材料','bore':'公称通径','connection':'连接方式','medium':'介质',
        'model':'型号','quantity':'数量','destination':'交付目的地',
        'Delivery destination':'交付目的地','motor_electrical':'电机电气比较'}
RULES={'IND-SELECTION':'产品路径与声明型号','IND-SPEC':'型号参数与资料覆盖',
       'IND-DUTY':'配置情景的标量比较','IND-FIT':'工程适配待确认',
       'IND-PROOF':'供应商声明资料核验','IND-RFQ':'产品到询价准备'}
PHASES=[('PRODUCT_DISCOVERY','找到产品','从目录到来源声明的型号，先核对路径及型号范围。',['IND-SELECTION']),
        ('PRODUCT_AND_SPECIFICATION','理解技术规格','核对参数值、单位、资料版本和未覆盖字段。',['IND-SPEC']),
        ('APPLICATION_REVIEW','复核采购工况','比较已配置情景的标量，工程适配始终另行确认。',['IND-DUTY','IND-FIT']),
        ('SUPPLIER_PROOF_CONTEXT','核对供应商资料','区分供应商声明、日期比较与独立认证。',['IND-PROOF']),
        ('CONTACT_AND_RFQ','准备型号询价','整理已有输入和买方待补内容，不实际发送询价。',['IND-RFQ'])]


def label(value):
    return FIELDS.get(value,value)


def describe(a):
    rule=a['observation']['rule_id']
    result=a['observation']['result']
    d=a['details']
    if rule=='IND-SELECTION':
        return ('原生重放已记录目录到此来源声明型号的路径；不代表独立SKU验真或实际可用性测试。'
                if result=='PASS' else '当前未证实完整型号选择路径；保持UNKNOWN，不据此断言全站没有产品入口。')
    if rule=='IND-SPEC':
        observed='；'.join(label(k)+'：'+v['text'] for k,v in d.get('observed_attributes',{}).items())
        gaps=d.get('not_observed',[])+d.get('unusable_values',[])
        return ('配置字段的已记录来源值：'+(observed or 'UNKNOWN')+'。待补或待解释：'
                +('、'.join(label(k) for k in gaps) if gaps else '本配置未列出缺项；数值正确性仍待企业确认')
                +'。未覆盖字段不能解释为网站不存在这些资料。')
    if rule=='IND-DUTY':
        if result=='NOT_APPLICABLE':
            return '本阀门配置不执行电机电气比较；执行器需求未确认，不计为问题。'
        outcome={'PASS':'满足本次配置的标量条件','FAIL_WITH_EVIDENCE':'不满足本次配置的标量条件',
                 'UNKNOWN':'缺少可明确比较的配对数值或情景，保持UNKNOWN'}.get(result,'UNKNOWN')
        return (label(d.get('attribute','未知比较项'))+'：'+outcome+'。保留C1原生比较原文：'
                +a['observation']['statement']+' 工况比较不是已证实的网站故障，也不等于工程不适配。')
    if rule=='IND-FIT':
        return ('工程适配为UNKNOWN。需复核：'+'；'.join(d.get('questions',[]))
                +'。目录数值、独立标量满足或冲突，均不能替代供应商对工作点、介质及安装的工程确认。')
    if rule=='IND-PROOF':
        return ('来源声明的机构：'+str(d.get('declared_issuer') or 'UNKNOWN')+'；编号：'
                +str(d.get('declared_reference') or 'UNKNOWN')+'；日期：'+str(d.get('declared_valid_until') or 'UNKNOWN')
                +'。'+('该声明日期早于来源采集日，需要取得当前资料再核验。' if result=='FAIL_WITH_EVIDENCE'
                        else '本次原生日期比较未形成独立认证结论。')
                +'这不证明真实证书失效、供应商不合格或造假；独立认证为UNKNOWN。')
    if rule=='IND-RFQ':
        missing=d.get('missing_buyer_inputs',[])
        return ('保留的RFQ要求：'+'、'.join(d.get('source_required_labels',[]))
                +'。买方待补：'+('、'.join(label(k) for k in missing) if missing else '当前配置未列出，仍需人工复核')
                +'。'+('已记录产品上下文的联系GET路径。' if d.get('native_contact_observation_ids') else '联系路径覆盖尚待复核。')
                +'买方缺少目的地等资料不是网站缺陷；未发送表单，投递及报价结果为UNKNOWN。')
    return a['observation']['statement']+' 未扩展原生评估范围。'


def project(data, evidence):
    rows=[]
    for a in data['assessments']:
        native=a['finding']
        rule=a['observation']['rule_id']
        result=a['observation']['result']
        refs=list(a['source_fact_refs'])
        # Presentation samples only. All facts and all references remain below.
        chosen=sorted(refs,key=lambda k:(not bool(re.search(r'\d',evidence[k]['quote'])),k))[:2]
        priority='P2' if result=='FAIL_WITH_EVIDENCE' else 'UNRANKED'
        name=a['model'] or '型号未确认'
        rows.append({'id':native['finding_id'],'observation_id':native['observation_id'],
            'native_finding':native,'native_observation':a['observation'],
            'native_reason':a['reason'],'native_rule_id':rule,'native_result':result,
            'native_details':a['details'],'source_fact_refs':refs,
            'guard_bridge':a['guard_bridge'],'native_impact':a['possible_buyer_impact'],
            'native_recommendations':a['recommendations'],
            'kind':native['kind'],'task':native['buyer_task'],'severity':native['severity'],
            'priority':priority,'title':name+' · '+RULES.get(rule,rule),
            'statement':describe(a),'evidence_ids':refs if native['kind']!='UNKNOWN' else [],
            'context_evidence_ids':refs if native['kind']=='UNKNOWN' else [],'display_evidence_ids':chosen,
            'scope':'本次原生保留页面、来源声明型号及当前行业配置；原生结果：'+result+'。不是全站/实时网站断言。',
            'buyer_impact':{'IND-SELECTION':'可供采购人员沿已记录路径识别候选产品，型号身份和实际操作体验仍需核对。',
                'IND-SPEC':'可能需要补充有版本的技术资料才能做可比较的型号清单，其他未观察资料仍可能存在。',
                'IND-DUTY':'采购人员需要先解释配置情景与来源值的关系，再向企业工程师确认，不能据此认定产品不可用。',
                'IND-FIT':'选型决定依赖企业/供应商工程复核，不是网站改版即可解决。',
                'IND-PROOF':'采购人员可能需要当前且可独立核验的供应商资料，来源声明本身不能完成采购认证。',
                'IND-RFQ':'资料整理有助于开展询价讨论，但缺买方输入不代表网站坏掉，实际报价延误未被观察。'}.get(rule,'影响待人工复核。'),
            'priority_basis':'P2仅表示优先复核已记录比较或声明，不是缺陷严重性或损失分数。' if priority=='P2'
                             else '已观察基线、未适用与UNKNOWN均不计为已证实缺陷，不虚构排序。',
            'uncertainty':'工程适配、资料真实性、未覆盖页面、后台投递与业务成效未获独立确认；C1影响与建议仍HUMAN_REVIEW_REQUIRED。',
            'recommendation':{'IND-SELECTION':'保留已观察路径，走查真实型号到资料/询价的连续上下文，不预设需要重建目录。',
                'IND-SPEC':'请企业工程师确认字段、单位、条件和技术资料版本；在确认后整理型号资料卡。',
                'IND-DUTY':'把来源值、情景值、单位和限制交给工程师复核，必要时由供应商提出替代选型。',
                'IND-FIT':'补齐供应商工程确认，再决定哪些条件适合对外表达，工程结论不由本系统代签。',
                'IND-PROOF':'获取当前适用型号的证明资料，核验机构、范围、编号与有效期，再更新展示。',
                'IND-RFQ':'补齐买方输入并保留型号/工况来源，人工复核后在另行授权的环境验证接收。'}.get(rule,'先补充证据。'),
            'recheck':'按原引用重放同一字节及原生观察；企业提供新材料时用新pack/run和新报告版本复验，不改写本次来源。'})
    journey=[]
    for key,title,goal,rules in PHASES:
        selected=[r for r in rows if r['native_rule_id'] in rules]
        journey.append({'task':key,'label':title,'goal':goal,'assessment':'记录'+str(len(selected))+'项原生评估；PASS、配置比较冲突、NOT_APPLICABLE和UNKNOWN分别保留，不汇总成网站缺陷分数。',
                        'finding_ids':[r['id'] for r in selected]})
    packages=[]

    def add(title,selected,change,inputs,acceptance,owner,fit='STANDARD_CANDIDATE'):
        refs=sorted({ref for r in selected for ref in r['source_fact_refs']})
        if not refs:
            return  # No source basis => no invented page improvement.
        urls=sorted({evidence[k]['url'] for k in refs})
        packages.append({'id':'blueprint-'+sha(encoded([title,[r['id'] for r in selected]]))[:24],
            'title':title,'phase':'先核对资料与责任，再决定页面修改',
            'page':'；'.join(urls),'finding_ids':[r['id'] for r in selected],
            'evidence_ids':refs,'source_fact_refs':refs,
            'evidence_refs':sorted({evidence[k]['native_citation']['evidence_ref'] for k in refs}),
            'observation_ids':[r['observation_id'] for r in selected],
            'change':change,'customer_inputs':inputs,'acceptance':acceptance,
            'owner_role':owner,'dependency':'依赖企业确认材料与真实流程走查；原版本保留，不自动更新网站或发送询价。',
            'service_fit':fit,'service_basis':('标准信息组织/页面模板候选，按合同确认；无报价、工期或工程服务承诺。'
                if fit=='STANDARD_CANDIDATE' else '工程确认不在标准网站Rebuild范围；由企业工程师/供应商负责，不能当作自动加购服务。'),
            'semantic_status':'HUMAN_REVIEW_REQUIRED'})

    models=sorted({a['model'] for a in data['assessments'] if a['model'] is not None})
    for model in models:
        native_ids={a['finding']['finding_id'] for a in data['assessments'] if a['model']==model}
        group=[r for r in rows if r['id'] in native_ids]
        specs=[r for r in group if r['native_rule_id']=='IND-SPEC']
        add(model+' · 整理有版本的型号技术资料卡',specs,
            '基于已记录字段保留原始值/单位/条件及资料版本。把未观察或无法解释的字段标为待确认；企业提供新资料后再决定页面或下载索引如何调整，不声称原站没有资料。',
            ['企业工程师确认参数、单位、工况与适用型号。','提供可使用的技术资料、版本日期与资料责任人。'],
            ['逐项核对展示值与获确认的资料版本一致。','未确认字段仍UNKNOWN；新资料以新版本报告复验。'],
            '企业产品工程师确认；网站内容负责人组织资料')
        application=[r for r in group if r['native_rule_id'] in ('IND-DUTY','IND-FIT')]
        add(model+' · 工况与工程复核清单',application,
            '把本次配置情景、来源参数、原生比较及适配UNKNOWN交给工程师。记录介质、工作点、接口及安装限制的确认或替代方案；未确认前不发布“适用/不适用”结论。',
            ['买方确认目标工况与实际介质/安装条件。','供应商提供签名或可核查的工程复核资料；不由网站团队代签。'],
            ['工程责任人说明每项冲突/未知如何处理。','另行确认的结论才进入产品说明，不把单个标量等同整体适配。'],
            '企业/供应商工程责任人；买方补充工况',fit='CUSTOM_ASSESSMENT')
        rfq=[r for r in group if r['native_rule_id']=='IND-RFQ']
        add(model+' · 询价准备与产品上下文复核',rfq,
            '在现有已观察GET路径基础上整理型号、工况、数量与来源，明确买方待补项。先走查现有联系流程是否携带这些信息，再决定是否调整表单或资料卡，不从缺目的地推断网站缺陷。',
            ['买方补齐RFQ缺少的交付目的地等输入。','企业销售确认型号/工况接收字段与资料用途；任何真实发送须另获授权。'],
            ['复核准备包逐字段可追溯至本次来源或明确买方输入。','无授权不发送；实际接收结果保持UNKNOWN，授权验证时记录接收责任人与结果。'],
            '买方补信息；企业销售与网站负责人核对上下文')
    # The same proof record used for two models is one shared work package.
    proofs: dict[tuple,list]={}
    for r in rows:
        if r['native_rule_id']=='IND-PROOF':
            proofs.setdefault(tuple(r['source_fact_refs']),[]).append(r)
    for selected in proofs.values():
        add('共享供应商声明资料 · 取得当前版本再独立核验',selected,
            '保留来源声明及覆盖型号，向企业取得当前资料。核对机构、编号、范围与日期后才决定更新哪个资料区；共享记录只做一份工作包，不重复算成多个供应商故障。',
            ['企业提供当前证明资料和允许展示范围。','采购/合规责任人独立核验机构、编号、范围与日期。'],
            ['每个展示声明可追溯至获确认的资料版本。','没有独立核验时认证状态仍UNKNOWN，旧声明日期不当作真实认证失效。'],
            '企业资质资料责任人；采购方独立核验')
    conflicts=sum(a['reason']=='EXPLICIT_SOURCE_SCALAR_CONFLICT' for a in data['assessments'])
    return rows,journey,packages,models,conflicts
