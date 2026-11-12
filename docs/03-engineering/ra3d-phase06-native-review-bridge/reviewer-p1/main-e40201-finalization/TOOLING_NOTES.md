# 本次收口工具记录

第一次 prepare 命令 exit 1：从很深的新证据目录执行 Git show，Windows 的 revision/path 歧义检查触发 `Filename too long`（Git exit 128）。没有生成测试副本，随后首次启动因此报 `MODULE_NOT_FOUND`，同样 exit 1，未执行任何浏览器断言，不计 PASS。

修正仅将 Git 工作目录设为仓库根，未改 Git 配置、冻结 suite、断言或产品界面。新的 suite 只有两项可逆路径替换，源码原样逆变换核对并记录 SHA。
