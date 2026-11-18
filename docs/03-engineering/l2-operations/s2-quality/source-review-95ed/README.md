# C3 首批来源候选审阅准备（本地交付）

先读 [业务核对入口](BIZ-START.md)，再按需要查看 [完整原文卡](reviewer-zh.md)、[原格式待审JSON](s2-review-input.json)及[来源Packet](s2-packet.json)。

本包固定 accepted main `95ed55321775223e95cf0a1585220951cc692648` 的 C1 Batch1/Batch2。未在 PR123 合入该 main；源快照与 C3 自有审阅层独立记录。342个 accepted Git blob 与5个自有叠加文件分别核验，额外未知文件/符号链接会被拒绝。不是新平台、正式报告、rx、Guard事实或整机P2。

## 业务方如何核对

本批14项代表单元覆盖DISC-03/SEO-02/TECH-01/INFO-02/TRUST-02/TRUST-03。6个离线场景包括有原文的正向样本、不保留HTML、身份地址原文冲突、单位不支持及缺少独立IndustryPins。

受限候选PASS只表示本次保存来源满足所述条件。证书真伪/供应商资格、法律身份、联系送达、工程适用性、Google排名与实时健康均未验证。8项UNKNOWN不得变成网站缺陷或TN。完整Packet保留原始ev-ref、source/snapshot、URL、原始UTF-8字节区间、内容SHA与受限s2p版本。

两位真实独立审核人的身份、日期、裁决、理由均为空；冲突时另需独立第三人及Owner原签名核验。原人类Gold0/26、新32项0/32、本包0/14分开列示；不合并计分，也不输出人类精度百分比。咨询、费率、工时、客户批准、E2/E3继续UNKNOWN。真实人审须Owner安排。

采集时间是原合成夹具的固定录制时间（2026-11-10等），不是本轮运行墙钟，更不是现场网站采集。当前source身份是合成fixture/run-synthetic；没有APP202或真实Worker COMMIT。

## 实际运行 / 未运行

- 实际：新增适配双原生3.11/3.13各10/10，零failure/error/skip；同一源码6个离线来源构造、EvidencePack校验、accepted C1 s2p及独立重放、每条原文字节核对、原unsigned review/intake零人审校验；两个minor最终bundle字节相同。
- 未运行：真实Worker、Chrome、SSR、Controlled人审、Brief、模型、真实外站、正式交付和新CI。原131/528、旧Chrome RED与历史专项未重跑。
- 原静态/CMS/SPA/多SKU/多语言分母与9工业反例仍保留在上一准备版本；本批是代表性来源适配子集，不是全站或全部规则完成。
- 原Gold核验、信任锚、旧26包、Worker30秒、权限双权威、Guard/SQL/RLS/SourcePolicy、旧CI及保护blob零修改。原39/40 RED原因UNKNOWN且不改判；匿名历史卷UNKNOWN_UNTOUCHED。

## 工程复现

本地精确快照位于 `integration/l2_ops/.private/source-review-95ed/gitblob-source`。它由accepted Git blob原始字节生成；不要把Windows git archive的换行转换结果当原始Git blob。

若需重建，先在仓库根执行以下Python（新目录已存在会拒绝）：

```python
from pathlib import Path
import subprocess, io
from integration.l2_ops.s2_quality_source_review import ACCEPTED, OVERLAYS
repo = Path.cwd()
root = repo / "integration/l2_ops/.private/review-rebuild/source"
root.mkdir(parents=True, exist_ok=False)
rows = []
for line in subprocess.check_output(["git", "ls-tree", "-r", ACCEPTED, "--",
        "vrae", "tests", "contracts", "industry-packs",
        "integration/s2_contract", "pyproject.toml"]).decode().splitlines():
    meta, path = line.split("\t")
    rows.append((path, meta.split()[2]))
raw = subprocess.check_output(["git", "cat-file", "--batch"],
    input=("\n".join(ref for _, ref in rows) + "\n").encode())
stream = io.BytesIO(raw)
for path, ref in rows:
    header = stream.readline().decode().split()
    assert header[0] == ref and header[1] == "blob"
    content = stream.read(int(header[2]))
    assert stream.read(1) == b"\n"
    target = root / path
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(content)
for path in OVERLAYS:
    target = root / path
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes((repo / path).read_bytes())
```

然后用既有原生Python执行本地新入口，必须选全新输出目录：

```
python -m integration.l2_ops.s2_quality_source_review --source-root <上述source绝对路径> --repository <仓库绝对路径> --output <全新输出目录>
python -m integration.l2_ops.s2_quality_source_review --source-root <上述source绝对路径> --repository <仓库绝对路径> --verify <输出目录/bundle.json>
```

新增10项验证应从snapshot为cwd/PYTHONPATH，显式使用snapshot的pyproject及--confcutdir，避免父工作区旧PG conftest误加载；只运行 `tests/s2_quality/source_review_cases.py`。本轮真实runner与原始日志保留在私有目录，原生JUnit与哈希见[manifest](manifest.json)。

## 开发RED保留

1. 初次ruff发现新入口unused base64，仅删除新文件无用import。
2. 首次测试收集误载父工作区PG conftest：没有JUnit，不计通过。修复独立测试root/config，没有改旧conftest或跳过原断言。
3. 第二次9项setup RED：严格blob门禁识别git archive在Windows产生换行转换，正确拒绝。保留旧快照/日志/XML，另用cat-file建立精确快照；没有规范化原源码或放宽哈希。
4. 精确快照9项先通过；随后为明确防止未核验额外代码混入，新增边界和第10项反例，最终新源码各10项完整通过。中间成功和最终结果独立保留，不覆盖RED。

本批尚未推送，不是远端CI证据。只有C2 P1和相应因果诊断获Owner FINAL PASS后，才正常同步获准main并用同一真实任务开展S2-P2。Issue129在既有Draft收口后的独立任务中落实；本PR没有删除3.11或修改分层触发。
