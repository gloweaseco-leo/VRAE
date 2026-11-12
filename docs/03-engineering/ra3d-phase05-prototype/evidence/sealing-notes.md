# 证据封存工具过程记录

第一次 `seal-evidence.mjs` 从子目录调用 `git ls-tree -r`，错误地取得相对路径范围，输出 mainFilesPreserved=1。该数值与已知 main 1416 文件不符，未用于交付证明。已改为 `--full-tree`，增加固定 1416 个文件断言，逐一比较 mode/type/blob；再次执行实际输出 1416。

源码首次提交前 sourceFilesMatchHead=false 是预期：当时 HEAD 是原 main，六份原型输入尚未提交。交付 manifest 必须指向已提交且六份输入匹配的代码 SHA，不以原 main 自称原型源码提交。

`git add` 最初提示 LF/CRLF 自动转换。为保留原始浏览器日志和合成来源的精确字节，在唯一授权的新目录新增 `.gitattributes` (`* -text`)，仅对此目录关闭文本换行转换，再重新暂存所有本目录文件。既有仓库 attributes 与生产文件均未改。

一次 `node -e` PowerShell 字符串命令解析失败，退出 1，未写入文件。原始错误摘要：`SyntaxError: Invalid or unexpected token` / `Expected ',', got '<eof>'`。后续使用 apply_patch 明确修改 HTTP 记录读取与零问题确认框 id。最终浏览器输入快照包含修正后的精确源码，没有将该失败计为通过。

浏览器各轮的 ERROR、原始截图、断言、stderr 与网络/CDP 日志均保留。临时 `profile-*` 为工具运行数据且不属于 UI 状态，被 `.gitignore` 排除。没有删除或修改已有 main 工件。
