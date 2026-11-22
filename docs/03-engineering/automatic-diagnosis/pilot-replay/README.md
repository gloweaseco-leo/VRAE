# 试点重放

`scripts/pilot_replay.py` 只读审计工件或仓库内合成夹具。它不发请求，不调用模型，不改 `select_next` 的默认参数。

默认输出哈希而不是原文。`--include-public-quotes` 才写入通过长度和联系方式检查的短引用，并留下审计行。原始 HTML、邮箱、电话和表单值不会写入导出文件。

旧版本重放与历史回执不一致时进程退出码为 2。云端没有 beherohome 工件，测试使用 `tests/fixtures/pilot/synthetic-audit.json`。
