"""Author a reproducible fictitious pump-maker dossier; never fetch a site.

All pages and commercial context below are invented test materials. The report
describes only these bytes. No real manufacturer, customer or certification.
"""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DEST = ROOT/'fixtures/l2/pump-maker-v1'
AT = '2026-11-15T12:00:00Z'


def raw(d):
    return json.dumps(d,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode()


def main():
    pages = {
        'home': ('/',200,'text/html','<html lang="en"><h1>Harbor Pump — synthetic sample</h1><nav><a href="/pumps">Pumps</a><a href="/about">About</a></nav><p>Industrial fluid transfer equipment</p></html>'),
        'catalog': ('/pumps',200,'text/html','<html><h1>Pumps</h1><article><a href="/pumps/mp25">MP25 Centrifugal Pump</a><p>Capacity 5-100; Head 20-60</p></article><article><a href="/pumps/mp40">MP40 Centrifugal Pump</a><p>Capacity 20-180; Head 30-80</p></article></html>'),
        'product': ('/pumps/mp25',200,'text/html','<html><head><link rel="canonical" href="https://harbor-pump.invalid/"></head><body><h1>MP25 Centrifugal Pump</h1><dl><dt>Capacity</dt><dd>5-100</dd><dt>Head</dt><dd>20-60</dd><dt>Material</dt><dd>Stainless steel</dd></dl><a href="/files/mp25-curve.pdf">Performance curve</a><a href="/contact-old">Request MP25 quotation</a><a href="/rfq">General inquiry</a></body></html>'),
        'curve': ('/files/mp25-curve.pdf',200,'text/html','<html><h1>Document coming soon</h1><p>This is an HTML placeholder, not a performance-curve PDF.</p></html>'),
        'contact': ('/contact-old',404,'text/html','<html><h1>404 — Page not found</h1></html>'),
        'rfq': ('/rfq',200,'text/html','<html><h1>Contact us</h1><form method="post" action="/send"><input name="name"><input name="email"><textarea name="message"></textarea><button>Send</button></form></html>'),
        'about': ('/about',200,'text/html','<html><h1>About Harbor Pump</h1><p>Quality products for global partners.</p><p>ISO 9001 certified</p><p>Contact: sales@harbor-pump.invalid</p></html>'),
    }
    snapshots, evidence, objects = [], [], {}
    for key,(path,status,mime,body) in pages.items():
        content = body.encode()
        name='snapshots/'+key+'.html'
        objects[name]=content
        snapshots.append({'id':'snapshot-'+key,'url':'https://harbor-pump.invalid'+path,
            'captured_at':AT,'http_status':status,'content_type':mime,'body_file':name,
            'sha256':hashlib.sha256(content).hexdigest(),'access_mode':'SYNTHETIC_OFFLINE'})
    def ev(key,page,quote,locator):
        content=objects['snapshots/'+page+'.html']
        start=content.index(quote.encode())
        evidence.append({'id':key,'snapshot_id':'snapshot-'+page,'quote':quote,
            'locator':locator,'byte_start':start,'byte_end':start+len(quote.encode()),
            'sha256':hashlib.sha256(quote.encode()).hexdigest()})
    ev('ev-nav','home','<a href="/pumps">Pumps</a>','nav a[href="/pumps"]')
    ev('ev-catalog','catalog','<p>Capacity 5-100; Head 20-60</p>','article:first-of-type p')
    ev('ev-spec','product','<dt>Capacity</dt><dd>5-100</dd><dt>Head</dt><dd>20-60</dd><dt>Material</dt><dd>Stainless steel</dd>','dl')
    ev('ev-curve-link','product','<a href="/files/mp25-curve.pdf">Performance curve</a>','a[href="/files/mp25-curve.pdf"]')
    ev('ev-curve-body','curve','<h1>Document coming soon</h1>','h1')
    ev('ev-rfq-link','product','<a href="/contact-old">Request MP25 quotation</a>','a[href="/contact-old"]')
    ev('ev-contact404','contact','<h1>404 — Page not found</h1>','h1')
    ev('ev-form','rfq','<input name="name"><input name="email"><textarea name="message"></textarea>','form controls')
    ev('ev-cert','about','<p>ISO 9001 certified</p>','p:nth-of-type(2)')
    ev('ev-canonical','product','<link rel="canonical" href="https://harbor-pump.invalid/">','head link[rel="canonical"]')
    pack={'schema_version':'1.0','tenant_id':'tenant-example','industry_id':'industrial_pumps',
        'version':'1.0.0','methodology_version':'1.1',
        'buyer_tasks':['DISCOVER','UNDERSTAND','TRUST','INQUIRE','SEARCH_TECHNICAL'],
        'applicable_rule_ids':['DISC-01','DISC-02','INFO-01','INFO-02','TRUST-02','CTA-02','SEO-01'],
        'critical_attributes':['流量及单位','扬程及单位','运行点/转速/性能曲线','介质与温度范围','过流件材质/密封','接口尺寸及标准','电源/频率/电机要求'],
        'false_positive_risks':['页面参数存在不等于适配或真实性已核实','保留页面中未见不等于全站不存在','证书宣传不等于资质认证','入口响应不等于表单送达','不得由未知后台推断真实损失']}
    findings=[]
    def finding(key,task,kind,priority,title,statement,refs,scope,impact,basis,uncertainty,recommendation,recheck,severity='MEDIUM'):
        findings.append({'id':key,'task':task,'kind':kind,'priority':priority,'severity':None if kind=='UNKNOWN' else severity,
            'title':title,'statement':statement,'evidence_ids':refs,'scope':scope,'buyer_impact':impact,
            'priority_basis':basis,'uncertainty':uncertainty,'recommendation':recommendation,'recheck':recheck})
    finding('f-rfq404','INQUIRE','OBSERVATION','P1','MP25 的专用询价入口返回 404',
        '保留的 MP25 产品页“Request MP25 quotation”指向 /contact-old；该目标在本次离线记录中返回 404。',
        ['ev-rfq-link','ev-contact404'],'仅 MP25 页面上的这个入口和已记录目标响应；未发送表单。',
        '可能使已选中 MP25 的采购员在准备询价时中断或额外寻找联系方法；实际点击率、送达和损失均未测。',
        '优先处理有明确来源的任务终点阻碍，修复可独立验收；不依据猜测的营收损失排序。',
        '不能认定全部联系渠道不可用；/rfq 另有响应，服务器收件状态 UNKNOWN。',
        '确认有效询价入口后替换产品页链接，保留型号和来源页上下文；上线前由业务责任人确认收件渠道。',
        '在获准环境从 MP25 实际点击入口，检查响应与最终地址、型号传递；表单提交和收件另行授权验证。','HIGH')
    finding('f-curve','UNDERSTAND','OBSERVATION','P1','性能曲线下载实际返回 HTML 占位页',
        '产品页将 /files/mp25-curve.pdf 标为 Performance curve；该记录为 HTTP 200、text/html，正文是 Document coming soon。',
        ['ev-curve-link','ev-curve-body'],'仅这一个曲线文件入口；没有推断其他资料都不存在。',
        '采购工程师可能无法从此入口取得用于核对工作点的曲线，技术比较可能需要往返索取资料。',
        '影响技术选型所需信息，并且“文件已准备好”与实际响应不一致，有直接可复验的修复对象。',
        '型号适配性、真实曲线、效率/NPSH 数据和客户运行工况均 UNKNOWN，不能代替工程选型。',
        '由工程责任人提供带型号、版本、单位、转速和测试条件的真实曲线；未提供前将按钮标为“索取技术资料”，不要补造 PDF。',
        '核对文件 MIME、打开/下载、型号、版本和单位；由企业工程师确认曲线来源和适用工况。','HIGH')
    finding('f-spec','UNDERSTAND','OBSERVATION','P2','已保留参数表的单位与材质等级不足以直接比较',
        'MP25 参数表写 Capacity 5-100、Head 20-60、Material Stainless steel；在该表内未标注单位、材质等级和对应运行条件。',
        ['ev-spec'],'只描述保留的这个参数表；不认定全站或纸质资料均无参数。',
        '海外采购员可能无法与统一单位的采购规格逐项比对，需要先向企业确认数值含义与材质。',
        '行业包将单位、运行点和过流件材质列为技术比较所需信息；属补齐内容结构，不能由网页判断参数真假。',
        '流量单位、扬程单位、316L/304 等等级、介质适用性尚未确认；不得从 Stainless steel 自动推断。',
        '按行业字段整理参数模板，记录参数值、单位、测试条件及资料版本；未知字段展示“请咨询确认”，由工程师签核。',
        '抽查代表型号的网页、PDF 和销售规格表的一致性；用企业确认的一个采购工况逐字段演练比较。')
    finding('f-discovery','DISCOVER','HYPOTHESIS','P2','型号列表的初筛负担需要复核',
        '保留的分类页展示 MP25/MP40 名称及 Capacity、Head 文本；这些卡片未展示应用、介质或材质字段。',
        ['ev-catalog','ev-nav'],'仅当前分类卡片；未实测动态筛选或站内搜索，不认定不存在。',
        '首次来访、尚不知道型号的采购员可能难以从应用或技术要求缩小范围；是否形成阻碍须实际走查。',
        '排在明确下载/联系阻碍之后；影响为假设，先用实际选型任务验证，而非直接认定必须做复杂筛选器。',
        '动态筛选、站内搜索、销售最常用选型逻辑及客户产品分组 UNKNOWN。',
        '先确认客户常见选型维度，再把应用入口、关键对比字段和详情链接放入标准分类模板；复杂联动选型器另行评估。',
        '让业务/技术人员用两个明确采购场景从首页找到候选产品，记录路径、误解和需要补问的信息。')
    finding('f-trust','TRUST','OBSERVATION','P2','认证声明尚不足以完成主体核对',
        '保留的 About 页包含 ISO 9001 certified 宣传文字；此记录未包含证书主体、编号、范围或有效期资料。',
        ['ev-cert'],'这是已观察到的宣传声明，不是证书认证或“没有资质”的结论。',
        '采购员可能仍需索取可核对的企业主体和证明资料；并不据此判断企业不可信。',
        '信任资料直接关系供应商初步核对，但应先补资料而不是通过设计或图标制造可信度。',
        '企业法律主体、证书真实性、认证范围/期限与商标关系 UNKNOWN。',
        '用经许可且由企业确认的主体信息、证书摘录和适用范围建立信任资料页；敏感资料可保留为按需提供。',
        '由企业责任人核对主体和资料有效期，走查到询价前能否找到核验说明；独立资质认证不包含在建站交付中。')
    finding('f-context','INQUIRE','HYPOTHESIS','P2','通用询价页是否保留产品上下文尚待验证',
        '当前 /rfq 表单快照只显示 name、email、message 三个字段；静态结构中未显示型号字段。',
        ['ev-form'],'未运行服务端或脚本，也未测试真实投递；不能断言后台没有自动附加型号。',
        '若后端未补齐上下文，销售可能需要再次询问型号、工况与需求数量；这是条件性风险。',
        '不作为已证实投递失败；与产品模板及询价内容一起验证，避免只美化按钮。',
        '实际请求载荷、后台接收、反垃圾和 CRM 映射均 UNKNOWN。',
        '先确认现有载荷；在授权后验证型号/来源页、流量扬程、介质温度、数量和交期等字段，减少不必要必填项。',
        '在批准的测试收件箱中验证前端载荷、服务端记录、通知和型号上下文；提交行为需单独授权。')
    finding('f-canonical','SEARCH_TECHNICAL','OBSERVATION','P3','产品页 canonical 指向首页，需要确认发布意图',
        '保留的 MP25 HTML canonical 指向 https://harbor-pump.invalid/，与当前产品路径不同。',
        ['ev-canonical'],'仅此页标签；未查询搜索引擎收录、排名或 Search Console。',
        '若产品页应独立承载技术内容，规范化配置可能影响搜索发现的表达；实际索引和排名效果未知。',
        '先核对站点发布环境和规范化策略，再评估；不把单一标签等同于 SEO 损失。',
        '是否测试环境、是否有等价产品页、真实索引及流量均 UNKNOWN。',
        '确认可索引页面清单、规范 URL 和迁移映射；在常规模板中统一 title/canonical，历史 URL 大规模迁移单独评估。',
        '复查获准发布页面的响应、canonical、robots/sitemap 和跳转；真实索引与流量需另行取得有权数据。','LOW')
    for key,task,title,reason,needed in [
        ('u-engineering','UNDERSTAND','真实工况与工程选型','后台/真实技术资料未提供，不影响其他公开页面分析。','目标介质、温度、运行点、供电、接口标准、材质与密封确认；工程责任人核准。'),
        ('u-delivery','INQUIRE','表单提交与实际送达','没有执行真实提交；200 页面响应不能证明送达。','获准测试收件箱、服务端受理记录、通知与失败处理的测试许可。'),
        ('u-identity','TRUST','企业主体与证明真伪','网页自述不能充当外部权威认证。','有权提供的主体/证书信息及核验方式、可公开范围。'),
        ('u-analytics','SEARCH_TECHNICAL','真实访问、索引与询盘表现','没有私有分析、CRM 或 Search Console 数据。','由有权人员提供聚合基线；指标口径、时间范围及隐私边界。')]:
        finding(key,task,'UNKNOWN','UNRANKED',title,reason,[],reason,'未知项不计为缺陷，也不编造经营损失。','不对证据空白排序为严重问题；按依赖决定何时补证。',reason,needed,'只在资料与操作获得适当许可后复核；保留原证据和版本。')
    blueprint=[]
    def bp(key,title,refs,page,change,inputs,fit,why,acceptance,dependency,owner,phase):
        blueprint.append({'id':key,'title':title,'finding_ids':refs,'page':page,'change':change,
            'customer_inputs':inputs,'service_fit':fit,'service_basis':why,'acceptance':acceptance,
            'dependency':dependency,'owner_role':owner,'phase':phase})
    standard='依据已验收 V1.1 纲领的常规网站 Rebuild 范围作候选分类；最终页面数、模板、内容量及合同须由 VEYFRONT 确认，不是报价承诺。'
    bp('bp-rfq','先恢复可用的产品询价路径',['f-rfq404','f-context'],'MP25 产品模板 + Contact/RFQ',
       '把失效专用入口替换为业务确认的有效路径；询价区同时显示型号与来源页，并说明需提供的工况。先复用现有收件流程，不擅自更换 CRM。',
       ['有效收件渠道与业务责任人','型号/来源上下文的现有处理方式','获准测试收件箱及提交测试许可'],
       'STANDARD_CANDIDATE',standard,
       ['从产品页进入获准询价页，不再返回404','型号/来源在获准的载荷及接收记录中一致','未获提交许可时只验收导航，投递结论保持UNKNOWN'],
       '业务确认入口；投递验证依赖 u-delivery','客户销售负责人 + VEYFRONT 网站实施','先修复已证实阻碍')
    bp('bp-spec','建立可复用的工业参数与技术资料模板',['f-spec','f-curve'],'产品详情 + 技术下载区',
       '结构化展示流量/扬程单位、转速、材质、介质/温度和接口；技术下载按型号与版本管理，资料未齐时提供真实的索取入口。不能由网页文字生成工程参数。',
       ['工程确认的代表型号参数及单位','有权使用且版本明确的曲线/规格PDF','型号与文档关联表及维护责任人'],
       'STANDARD_CANDIDATE',standard,
       ['代表型号网页与工程确认规格表逐字段一致','曲线入口下载正确文件并明确型号/版本/单位','未知字段不补造，明确索取资料方式'],
       'u-engineering 资料确认；先从一个模板与两款产品试点','客户工程负责人 + 内容编辑','修复技术资料与内容结构')
    bp('bp-catalog','先用买家任务组织分类和应用入口',['f-discovery','f-spec'],'首页导航 + 产品分类 + 应用入口',
       '根据企业确认的主要应用与技术筛选维度，先做清楚的分类、应用索引与对比字段；让不知道型号的人也能进入代表产品。无需先开发复杂智能选型器。',
       ['主推产品与真实目标应用','适合公开的应用边界和排除条件','采购员最常问的筛选问题'],
       'STANDARD_CANDIDATE',standard,
       ['业务/工程人员按两个指定任务能找到候选产品','分类卡片的字段与详情一致','记录仍需询问的信息，不宣称获得转化率提升'],
       '分类维度待业务确认；不阻止先修复失效入口','客户产品负责人 + 信息架构设计','再整理采购旅程')
    bp('bp-proof','把可信资料变成可核对的说明',['f-trust'],'About + Proof/Quality + Contact',
       '以企业核准的主体、能力说明、证书范围和适用产品建立资料索引；未获准公开的资料明确按需提供，不用模板徽章代替证明。',
       ['可核对的企业名称与关系说明','资料权利与公开范围','证书主体/范围/有效期及更新责任人'],
       'STANDARD_CANDIDATE',standard,
       ['每条公开证明都有企业确认的资料与责任人','网页措辞不超出证书或案例范围','需要私下提供的资料有明确索取方式'],
       'u-identity；无资料时保留UNKNOWN，不写虚构证书','客户合规/管理责任人 + 内容编辑','资料核对后发布')
    bp('bp-urls','确定规范 URL 与有限迁移清单',['f-canonical'],'产品页面模板 + 旧 URL 清单',
       '确认每类页面的发布/索引意图，为试点产品确定规范URL和必要跳转；准备旧网址对照表与上线回归清单。当前不承诺保排名。',
       ['现有URL清单与发布环境说明','优先保留页面与历史入口','有权提供的聚合搜索数据（可选，缺失则UNKNOWN）'],
       'STANDARD_CANDIDATE',standard,
       ['试点页面响应、canonical、robots/sitemap与发布意图一致','约定的旧入口可到达对应新页','索引/流量改善另凭真实数据复盘'],
       '客户确认发布意图；大规模多站迁移不在此候选范围','网站技术负责人 + VEYFRONT 实施','发布前回归')
    bp('bp-custom','复杂选型、系统对接与大规模迁移单独评估',['f-discovery','f-context','f-canonical'],'可选系统能力，不是已确认必需改造',
       '若常规模板不能满足真实业务，再评估联动选型/计算、PIM/ERP/CRM 双向对接、多语言多站点和大规模历史数据迁移；先做接口与数据盘点，再单独评估合同、费用和风险。',
       ['明确的业务流程与必要性','数据量/接口/权限/维护要求','客户确认的预算与交付约束'],
       'CUSTOM_ASSESSMENT','V1.1 纲领明确复杂平台/数据库、多站点与大规模迁移需单独评审；不能因发现网页问题就默认这些功能都必须购买。',
       ['形成独立需求与接口/数据责任清单','以客户确认的场景决定是否开发','未评估前不报固定价、不承诺工期或自动交付'],
       '先验证标准模板；没有证据证明所有定制项都必要','客户系统负责人 + VEYFRONT 方案负责人','可选独立评估')
    journey=[]
    goals={
        'DISCOVER':('从应用与技术要求找到候选泵','首页→分类→MP25 路径有静态记录，但实际初筛可用性需要任务走查。',['f-discovery']),
        'UNDERSTAND':('判断资料是否足以交给工程师核对','曲线入口为HTML占位页；已保留参数表缺少比较所需的单位/条件说明。',['f-curve','f-spec','u-engineering']),
        'TRUST':('核对供应商主体和可引用的证明','只看到了认证宣传，主体与证书资料需企业补充，不能据此判断不可信。',['f-trust','u-identity']),
        'INQUIRE':('带型号和工况发起可处理的询价','专用询价入口404；通用表单的上下文和投递仍未知。',['f-rfq404','f-context','u-delivery']),
        'SEARCH_TECHNICAL':('确认技术页面的可访问与规范化基础','记录了canonical差异，但未取得真实索引、流量或询盘表现。',['f-canonical','u-analytics'])}
    for task,(goal,state,ids) in goals.items():
        journey.append({'task':task,'goal':goal,'assessment':state,'finding_ids':ids})
    d={'contract':'vrae.l2.deep-result.v1',
       'meta':{'tenant_id':'tenant-example','report_id':'l2-pump-maker','run_id':'l2-offline-pump-run-1',
           'version':1,'title':'工业泵网站 L2 深度诊断与 Rebuild 蓝图','created_by':'offline-editor',
           'created_at':AT,'source_mode':'SYNTHETIC_OFFLINE','source_policy_ref':'offline-fixture-policy-v1'},
       'producer':{'name':'Codex2 offline deep-result adapter sample','version':'l2-offline-1.0.0',
           'assurance':'OFFLINE_AUTHORED_SOURCE_BOUND_NOT_NATIVE_GUARD'},
       'industry_pack':pack,'industry_pack_sha256':hashlib.sha256(raw(pack)).hexdigest(),
       'snapshots':snapshots,'evidence':evidence,'findings':findings,'journey':journey,'blueprint':blueprint,
       'buyer':{'label':'示例采购任务：海外设备集成商的工业泵初步筛选',
           'scenario':'采购人员从用途与工况开始寻找候选型号，收集规格和曲线交由工程师复核，核对供应商资料，再携带型号、数量与交期发起询价。',
           'assumption':'这是用于检验网站信息结构的示例任务，不是企业已确认的目标市场、真实客户需求或工程选型结果。',
           'questions':['是否找到与介质/工况相符的候选产品？','流量、扬程、材质和条件能否统一比较？','技术资料属于哪个型号、版本与适用范围？','企业主体和证明能否核对？','询价能否带上产品与工况，并在许可后验证接收？']},
       'summary':'本样本最直接的两处阻碍是 MP25 专用询价入口404、曲线下载返回HTML占位页。先修复这些可复验入口，再补齐工程确认的参数与资料。分类初筛、询价上下文属待复核风险；后台、资质与经营数据未知，不阻止其余分析。',
       'service_catalog':{'version':'v1.1-charter-provisional-1','basis':'docs/00-product/PRODUCT_CHARTER_V1.1.md §4 + §5',
           'standard_label':'标准 Rebuild 候选（按合同确认）','custom_label':'需定制评估',
           'verification':'尚未取得逐项已批准商业服务清单；不能将候选范围当成已报价、已签约或正式交付承诺。',
           'price':'UNKNOWN','schedule':'UNKNOWN'},
       'limitations':['全部来源均为明确标注的合成离线页面；不是对真实企业的采集或评价。',
           '只对保存的页面、响应和字节证据负责；未测试真实站点、脚本行为、登录后台或表单投递。',
           '影响与优先级是用于讨论的专业判断，未测转化、损失额、流量、真实排名或E2/E3。',
           '标准服务仅候选分类；素材复制权、正式业务范围、报价、工期与验收责任需企业和VEYFRONT确认。',
           '此蓝图不是已获客户授权的 RebuildBrief，不向L2M发送素材、不自动建站或发布。']}
    objects['result.json']=json.dumps(d,ensure_ascii=False,indent=2).encode()+b'\n'
    for name,content in objects.items():
        path=DEST/name
        path.parent.mkdir(parents=True,exist_ok=True)
        if path.exists() and path.read_bytes()!=content:
            raise ValueError('SAMPLE_SOURCE_IS_IMMUTABLE_CREATE_NEW_VERSION')
        path.write_bytes(content)
    print(json.dumps({'fixture':str(DEST.relative_to(ROOT)),'bundle_sha256':hashlib.sha256(objects['result.json']).hexdigest(),
        'snapshots':len(snapshots),'evidence':len(evidence),'findings':len(findings),'blueprint':len(blueprint)}))


if __name__=='__main__':
    main()
