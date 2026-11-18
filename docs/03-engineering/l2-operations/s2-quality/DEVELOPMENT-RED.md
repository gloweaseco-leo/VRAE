# 开发期 RED 保留与因果修复

这些是新 C3-P0 工具的开发检查，不是 Worker/CI 重试，也未重置旧 A1/MAX3。

1. 第一次离线重放在 `generic_site` 读取 `todo["observation_id"]` 时出现 KeyError。原多 SKU 夹具先访问泵的 RFQ，得到403；原 Collector 按安全边界停止，另一 SKU 未访问。原 `quality.assess_sample` 因而返回“候选存在、无原生观察”的 todo，字段少于已观察记录。
2. 接入该分支后，又发现原未观察 todo 同样不包含 `candidate_rationale`。新工具现从独立作者标签取候选理由；实际 statement 仅取原生观察，缺观察时明确写“未观察”，不从候选理由伪造事实。
3. 多 SKU 夹具的先前 PASS 意图与实际原采集范围不符，改为 UNKNOWN 并保留计划分母；另增无阻断的完整多 SKU 正例，实际捕获两 SKU。原 Collector/SourcePolicy/执行器均未改。
4. 第一次新专项：38/38通过，JUnit保留于开发私有目录。随后补充完整多 SKU、JSON 和最终输出门禁，正式双版本以最终冻结候选为准。
5. 新 CLI 多行 import 的 noqa 位置、验收器未使用 sys 的 lint RED 已在新文件内修正。原源码/旧 CI 未改。

原始工具输出保留在本会话；开发 JUnit 与未压缩首版报告保留于 `integration/l2_ops/.private/s2p0-development/`。没有将开发检查冒称为完整 S2 整机或质量 PASS。

## First natural CI179034b RED

Both native CI jobs exit before collection because our explicit integration/l2_ops input-test path loads its existing PG/signed-runtime conftest. The core lock intentionally has no cryptography. Windows reused venvs contained that unrelated dependency, masking the directory coupling. Both raw ZIP digests, job logs and stage0 logs are preserved in first-ci-red-179034b. There is no hosted JUnit from these two jobs; no tests ran. Fix only relocates our input tests/parser to tests/benchmark and tests/s2_quality, preserving the original conftest, locks, crypto verifier, protected code and all first-attempt statuses.

## Frozen default inventory RED and own-suite isolation

The first RA4B natural CI actually collected2603 cases (0error/failure,25existing environment skips), then the intact DISC inventory guard correctly refused the exact2564 baseline because39 new S2 tests were auto-discovered. Input-test relocation would add4 more, so that interim candidate was never pushed. Own S2 files now use explicit quality_cases.py/input_cases.py selection, matching the existing industry/l2_cases.py pattern. The new dedicated native gate still executes all131 tests, including every new security case. No old inventory/manifest/pyproject/CI test filtering or test skips are introduced.

An extra core-only Linux probe on a read-only Windows bind was stopped with exit137 by the operator after measured100-file reads took907085414ns vs1444131ns on tmpfs. It is an incomplete infrastructure probe, not a native crash or test PASS; raw output/CID/cleanup remain private. Final Linux proof uses an exact source snapshot in a dedicated read-only native volume, without adding dependencies or changing production limits.
