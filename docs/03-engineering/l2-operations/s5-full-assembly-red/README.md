# S5 完整集成的首轮 RED 保留

正常 merge d38fd7263ea0d8ce357de54ef22cda90cdb86b9b 后的源码为 400814c417fc25fea55245da28e50a9ed72afa85；没有 force/rebase，也没有复制未合并 PR141。

- 首次自然 S5 workflow [44284613714](https://github.com/gloweaseco-leo/VRAE/actions/runs/44284613714) 的 Linux3.11/3.13 均为 attempt1 RED。两版各已完成65项检查，随后 supervisor 在 m3_workbench.py:634 的精确 PreparationWorkbench 类型断言退出。首轮两份ZIP已下载并校验CRC，完整原始ZIP保留在私有目录；公开有限回执为 first-ci-receipts.json。该断言没有包含原 S5 Workbench 子类，修复提交 ec35c1685bc7e5a020ef19b6702145ef20467287 仅增加此精确类型。
- Windows s5full-313a 在原私有签名响应文件 read_bytes 遇 PermissionError。该文件稍后可正常读取、ACL允许读取，符合瞬时占用；不能据此证明具体占用者。修复只在 Windows、原100/150秒控制期限内重读同一已生成响应，不重发签名或控制请求，不扩大期限。两个平台分支的原生回归验证仅一次请求，POSIX拒绝行为保留。
- 上述运行均已确认所属资源精确清理，旧匿名卷 UNKNOWN_UNTOUCHED，无global prune。原本地完整RED、私有日志/dump和先前 e914bbf/fc3c1b6 历史原位保留；未重跑或改判历史Job。
- 后续新HEAD的完整同任务结果必须独立记录，不能把这两轮或组件检查拼接为完整PASS。

修复版 ec35c1685bc7e5a020ef19b6702145ef20467287 的 S5 两版完整实操均 attempt1 SUCCESS，但原 C3 real-s2-combination 3.11 Job134737844192 的字体依赖步骤自10:28:56Z至10:46:24Z耗时17分28秒，整机步骤10:47:04Z开始，10:48:45Z触及原20分钟总时限取消。本轮不能称全部自然CI通过；保持原门禁与原结论，无targeted重跑。有限公开Job回执见 ec35-c3-311-cancelled.json。
