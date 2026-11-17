# 工业 L2 内部操作入口（S0 / TEST_ONLY）

本入口沿用原 PG16、APP202/API、独立 Worker 和唯一签名 SSR。工业 P40/V25
来自本地受控的八页合成证据，不访问真实企业站点。后台只在已合入 Owner
验收的 PR114 main `a9604f570528e599a0b8215a8957208d76e47b89` 后准入。
S0 的范围是 A01–A04；不代表全部五维规则、真实 AI、真人审批或客户交付。
[本轮执行依据](../l2-v1.1/S0_L2_E2E_EXECUTION.md)。

## 启动与打开原工作台

使用已经安装仓库锁定依赖的 Python 3.11 或 3.13，Docker 和本机 Chrome
须可用。在仓库根目录执行（每个隔离环境使用新的 run 名，不删除旧证据）：

```powershell
python scripts/beta_internal.py app doctor
python scripts/beta_internal.py l2 app-start --run operator-p40-01 --minor 3.11
python scripts/beta_internal.py l2 app-status --run operator-p40-01
# 状态为 M3_READY 后：
python scripts/beta_internal.py l2 app-open --run operator-p40-01
```

`app-open` 打开可亲自操作的 Chrome，并保持本地私有签名辅助进程运行。
M2 任务登录与 L2 审阅登录各自使用原签名挑战；辅助进程只签本环境观测到
的短期新挑战，不把私钥放进 SSR、URL 或页面，也不自动审核或批准。
已有 `python scripts/beta_internal.py app open --run ...` 入口继续兼容。

## 从新任务到内部商务 Brief

1. 在“我的合成任务”选择工业泵阀 P40/V25 深度诊断，提交新任务。
   页面先显示 APP202／等待 Worker；刷新状态至 DONE。DONE 不是报告完成。
2. 点击“签名核对本任务并生成／恢复深度报告”，再点击“生成／恢复本任务
   深度报告”。原签名 Reader 核对该任务的真实 Worker 包后，才进入原生
   工业诊断。工作台中的 L2 挑战也由同一个本地辅助进程完成。
3. 打开本次报告，阅读采购任务、证据、比较结论和 UNKNOWN，再阅读 Rebuild
   蓝图中的措施、责任、依赖、待企业确认资料与验收方法。技术哈希在折叠详情。
4. 在“责任人审核”逐项选择认可、拒绝或请求修订，填写理由并确认核对声明，
   保存当前版本回执。这是合成身份的 Controlled 演练，不构成正式人审。
   修改蓝图会产生新版本，原版本和原决定保留，新版本须重新审核。
5. 返回当前报告，打开“内部商务 RebuildBrief”。先核对预览，再保存。
   只有显示“已从 PostgreSQL 回读持久交接”才是实际保存。当前任务和当前
   审阅权限都必须有效；旧版、过期、撤权和冲突不能变成当前交接。
6. 从报告的打印入口查看／保存完整中文 A4 报告和蓝图。当前标准合成输入
   实际生成 22 页报告、7 页蓝图；数量来自真实规则输出，不靠静态样例替代。

原 M1 和 C2 期限均保持不变。请先完整阅读，再重新签名恢复原任务后填写审核；
准备好理由并逐项操作，勿把长期阅读时间当作仍持有提交权限。阅读期间如遇过期拒绝，请回到同一任务重新签名，
再“恢复”该任务的报告；不要创建新任务来替代旧版本，也不要打印拒绝页。
原任务、EvidencePack、诊断、报告版本与审核回执会再次核对。报告和 Brief
可跨本环境真实 PG／服务重启回读；储存的哈希本身不授予权限。

## 商务使用范围

Brief 提供本次报告引用、版本、Rebuild 蓝图、责任／依赖、待客户确认资料和
实际系统诊断运行记录。没有可核实凭据时，咨询保持 UNLINKED，费率／费用
保持 UNKNOWN，客户批准及 E2/E3 不成立。自动化不计为已核实人工工时。
不触达真实客户，不写 Vey2GE，不调用 L2M，不创建通用 CRM，不外发或部署。

## 验收、重启与停止

普通人工操作使用上面的 `app-open`。完整自动验收另建隔离环境：

```powershell
python scripts/beta_internal.py l2 app-verify --run <fresh-test-run>
```

该命令通过实际 Chrome 创建新任务，保存受控回执／Brief，执行明确标注的
故障注入、版本修订、撤权、真实 PG 和服务重启等检查。不要在有未完成
人工操作的环境里混跑。跨 SQLite 与专用 PG 的存储不是一个原子事务；
故障期间可以保留显式 pending 字节，但不作为当前 Brief 展示。
[跨存储设计、真实 RED 和运行证明](RUNTIME-WIRING.md)。

本地双版本包门禁（另行选择全新 alphanumeric label）：

```powershell
python integration/l2_ops/verify.py --label <new-label> --python311 <native311.exe> --python313 <native313.exe> --pg-image postgres@sha256:721873c34ceb9f8d8fc265984940dc982404c105f19ad51be9fdc5970a6080ea
```

人工操作完成后关闭 Chrome，再停止本环境：

```powershell
python scripts/beta_internal.py l2 app-stop --run operator-p40-01
python scripts/beta_internal.py l2 app-status --run operator-p40-01
```

这是临时合成沙箱，自动运行上限仍为 30 分钟。完整停止会清理本次精确所有权
资源，不是生产数据保存服务；所需内部演练结果应在停止前保存，并按本轮
证据规则私有封存。旧 dump、历史 RED 和未识别匿名卷不被全局清理。

三种来源能力的原生离线核验仍保留：`l2 source-check`、`l2 native-check`。
PUBLIC_READONLY_CAPTURE／CLIENT_PROVIDED 表示已提供资料的访问声明，不能
把材料标签当作实际外网运行许可。旧输入、旧 CI 和历史失败保持各自原 SHA
和限定范围，不以新结果改写。
