# RA-1A 代码与依赖来源

本轮按 Issue #2 及 Owner 指令独立实现。没有复制/移植 L2M 的 url_fetch.py、discovery.py
或其他源码，没有修改 L2M、VEYFRONT 或 Vey2GE。RA-0F 对 L2M 候选源码的历史审计仅作为
架构风险背景，未把未确认许可的候选源文件纳入 VRAE。无需以 L2M 许可确认阻塞此独立实现。

新增运行依赖：h11 0.16.0（MIT）、dnspython 2.8.0（ISC）；其余解析、TLS、socket、
异步运行使用 Python 标准库。安装元数据许可见 ra1a-evidence/image-source.json。
所有直接/间接运行与开发依赖版本见根目录 requirements-ra1a.lock 和验收 freeze.txt。
锁定版本不是依赖漏洞扫描或发行包内容哈希保证。

协议实现使用成熟库并参考官方 API 文档：

- [Python asyncio streams：已有 socket、TLS/SNI](https://docs.python.org/3/library/asyncio-stream.html)
- [h11 HTTP/1.1 framing API](https://h11.readthedocs.io/en/latest/api.html)
- [dnspython async resolver](https://dnspython.readthedocs.io/en/latest/async-resolver-class.html)

Docker 镜像仅用于开发测试。基础 digest 固定，安装 iproute2、iptables、openssl、util-linux
作为命名空间、防火墙、临时证书和降权工具；不是部署模板或生产基础镜像审批。
所有网站内容、DNS 回复、证书均为测试合成。证书每次实验生成，不使用客户凭据。
