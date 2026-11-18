# R0证据范围与复验

源清单：[inputs.json](inputs.json)。VRAE基线 `89a5115e3b8c4ab782bc140d3d278ffc83e7cc7a`，39份冻结源的Git blob及SHA256（完整原V1目录、原intake/Brief、审核/角色/状态/来源策略/Guard入口）逐份核对。另检查相对基线的全部差分只在新增contracts/l2_launch、l2-launch文档、相应tests及新增专项CI文件内；不能用抽样hash掩盖其它冻结修改。

VF main `348ba4a6a9e885431e769e008dd4b7c157405104` 及leads route只经GitHub源码读取，SHA256 `31aa3ff9cd016e1019e39b1ceb2c6e33649fe3bef4bdb1e4e4a785ac47cfa2d7`。CI离线复验此检查记录，不请求VF网站/API，不声称复核VF实际存储服务。

本地原生Python3.11/3.13各 **351 PASS**：其中新R0 consumer **79**，其余为原V1合同/领域/RA0F相关回归。Ruff通过。22个JSON示例可从固定合成种子/时钟重建，schema和实际对象逐项一致。旧Windows默认GBK读取原中文源文件的失败XML保留在忽略的本地.runtime；最终显式UTF-8复验，没有修改旧测试或跳过检查。

纳入Owner VF-B补充要求后，本地最终原生Python3.11/3.13各 **433 PASS**：consumer共161（基础79、VF-B82），原V1合同/领域/RA0F回归272。Ruff通过；39个JSON示例精确重建。VF PR36文档和presentation源码只读SHA见inputs.json；[一页VF-B兼容矩阵](VF-B-COMPATIBILITY.md)对应六项行为与负例。上述351/22保留为前一阶段记录，不能替代最新HEAD的433/39自然CI。新evidence要求至少160个consumer且至少80个VF-B用例，无skip/failure/error。

`.runtime/evidence*.json` 记录实际source_sha、clean/working-tree区别、Python、JUnit SHA、实际文件SHA和fixture计数。开发工作树结果标WORKING_TREE_UNCOMMITTED；提交本身不把旧结果变成新HEAD验收。自然CI必须checkout本HEAD并重新运行；最终Job/工件/digest核验以Draft PR描述为准，不复用其它HEAD全绿。

可复验内容：

首轮自然CI [44358578073](https://github.com/gloweaseco-leo/VRAE/actions/runs/44358578073) 对应 `4dbe44c8655edffcf05519260854addc12e1d726`，两版本均RED。3.11日志为312 PASS、39个setup ERROR：干净runner缺少`.runtime`父目录；随后冻结源校验因浅克隆不含基线提交而失败。修复仅为专项CI预建目录及完整拉取历史，保留原失败，不重跑旧HEAD；新HEAD结果以其自然CI为准。

- 202真实本地fixture提交、队列未派发、重开journal同run、同key异body/同audit异key冲突、存储503及限流429。
- 缺许可/撤销/过期/错租户/错scope/坏签名/错audience与跨请求重放；L2桥接未实现时明确不可用。
- 双语A/B、source/citation和观察分母、无采证UNKNOWN、未审/旧版/错误收方token及撤销/过期拒绝、Owner签名不能扩张SourcePolicy。
- 原check_share及精确视图hash/当前grant绑定；重复grant、过期及持久撤销；用户撤回与迟到ACK拒绝。
- VF独立SQLite fixture先保存/回读后签receipt，失败不出收据，确认丢失保留WAITING_ACK；相同event/同意图重放幂等，错tenant/版本/hash/假ok/假key拒绝；独立资格确认仍不计E2/E3。

没有声称：真实客户数据、人身份/正式人审、真实ShareGrant、VF真实收据、PG/Worker/Chrome整机、内核网络隔离、真实网站/Provider/邮件、云资源、上线或G0已冻结。socket/DNS禁止hook是本consumer harness的边界，不替代R1的容器与出网安全验证。

原PR141的M2_CAUSE_UNKNOWN/PR141_HOLD及旧RA4B/PR124/127 RED完整保留，不在本分支修饰或重试。这里的合同fixture成功不能替代旧作业，也不替代#145 UAT。
