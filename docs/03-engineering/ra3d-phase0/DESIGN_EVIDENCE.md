# 设计证据与未执行边界

本包只针对 Issue #49 的 Phase0 文档交付进行检查，不导入/运行 RA3C、RA3D 或原审批/分享函数。
所有设计验收用例状态为 NOT_RUN；真人审批 0、grant 0、客户访问 0、真实网站/模型调用 0。
四项 hosted CI 不作为本设计已有实现的证明，本轮不修改或手动重跑 CI。

## 可复核输入

- 已验收 main：`2429be6dc5d7dcb48221ab179f063b93ce4b1956`。
- 未合并 RA3C 候选：`6a7a3d3aa5f4341059b04567157f7fc58d6bf6d2`，PR #47 保持 Draft。
- [REFERENCES.json](REFERENCES.json) 记录 20 个只读 Git 文件的 commit、blob、原 Git 字节 SHA-256。
- [SCENARIO_INPUTS.json](SCENARIO_INPUTS.json) 仅提取原 404/200 草稿及来源位置、状态与 hash，
  并与同 commit 的实际 HTML 字节 SHA 比对；没有调用 build_draft/approve_version/check_share。
- Codex-1 PR #48 属独立业务 QA；本包不修改、不执行其测试，也不以其主干 prerequisite RED 推断产品缺陷。

## 设计检查方法

使用临时命令直接读取 Git 对象和本目录文件，不增加可运行生产/测试脚本：

1. 必需文档存在，Markdown 本地文件链接能解析；参考 Commit/Blob/SHA 与 `git show` 精确相同。
2. 测试目录有唯一 A01–A48 共 48 项，威胁目录 TH01–TH24 共 24 项，三个主场景；全部是待实施设计。
3. 原始 404/200 的 scope/ref/状态、native 有无、引文和 HTML hash 来自原文件而非编造。
4. HTMLParser 检查静态 mock：无 script/iframe/form/input/textarea、无事件属性、无远程资源或链接；
   所有 5 个 button 均 disabled，顶端有 DESIGN ONLY，页脚有 IMPLEMENTATION_NOT_STARTED/CUSTOMER_SHARE_NO_GO。
5. PNG 签名与实际尺寸检查；逐张目视检查。最终截图是本机缓存 Chromium 以 CDP 指定真实
   1280/375 viewport 打开本目录 file 的静态渲染。测得无横向溢出、5 个按钮全部禁用、无脚本/表单，
   文档外部请求为 0；通过 CSP、CDP blocklist、proxy 黑洞/host resolver 限制联网。
   这只检查静态设计文档，不是审核运行时或整体浏览器后台网络的安全验收。未启动服务端。
6. `git diff --cached --name-status` 只能出现本目录新增文件，1400 个基线 index blob/mode 与 main 对比不变；
   PR #47 原工作树的 HEAD/工作状态只读检查，禁止写入。

实际检查记录见 [DESIGN_CHECKS.json](DESIGN_CHECKS.json)，完整原基线文件清单及边界证明见
[SOURCE_PROOF.json](SOURCE_PROOF.json)。这些证明设计包完整性和隔离性，**不证明未来工作流通过**。

## 静态视觉证据

- [非交互 HTML 概念图](mock/reviewer-workbench.html)
- [桌面概念截图，1280×2022](mock/desktop-concept.png)
- [手机概念截图，375×3702](mock/mobile-concept.png)
- [静态文档渲染数据](mock/static-render-check.json)

所有身份、会话、T404、批准后状态均明确是设计占位或未来预期；截图没有真实“审批成功”回执。
原样本的机器来源绑定标签只是固定候选内容，真人决策与外发能力均未实现。
首次 Start-Process 截图尝试退出 13，没有据此报告成功；随后本机 headless file 渲染实际写出上述 PNG，
但 CLI 手机截图被窗口最小宽度裁切，未据此报告手机验收；最终用 CDP 明确设置 viewport 后重新
生成 PNG，核对 DOM 宽度与截图尺寸并目视检查。未增加 no-sandbox 等降低浏览器隔离的开关。

## 后续真实验收

只有在 RA3C 与独立 QA 合并、Owner 另行放行后，才能实现并执行 A01–A48；
身份、原子持久性、并发、撤销、recipient 访问及恢复须在相应受保护运行时独立验证。
Phase0 的自然中文、布局和合同评审不代替业务真实性、Human Gold 或真实客户同意。
