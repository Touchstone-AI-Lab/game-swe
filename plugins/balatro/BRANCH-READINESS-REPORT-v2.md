# Balatro 插件分支验收 v2

插件 **0.2.2** 已完成本机受控 `honest` 范围的实现和实际评分入口验收，可供分支代码审阅。
这不是全仓发布门禁全绿：Windows 全仓检查和缺失工具的限制列于下文。
维护者：**Sangyu Pan**。未提交、push、创建 PR 或更改项目规则。

## 实现与参考

参考本地 `origin/feat/palworld` 的 `9f7edfc`（已在 main `a518348` 中）、GMod 插件接口，
以及 adding-a-game、plugin-contract 和 evaluation-host 约束。
[要求映射](BRANCH-REQUIREMENTS-v2.md)逐项区分实现、验证和边界。

- 独立 Python 3.12 插件通过 `rhenium.benchmarks` 注册；核心保持游戏无关。
- 未列入既有对照的提交，必须先审阅源码，再记录与任务、提交、适配器、环境及资产绑定的授权。
  父进程和 sidecar 独立核验；评分使用实际候选字节指纹和引擎观察，不依据 gold/base 标签。
- doctor 只读核验固定依赖、保护基线及同指纹 smoke。真实前后快照证明不写状态；不启动游戏。
- 实际未修改的 `score-exam.ps1` 完成匿名 strict 提交评分；新提交只评分一次。
- 状态目录不得位于题包内。环境/RPC/缺少用例/退出失败保持 incomplete；业务失败单独分类。
- `untrusted` 仍由 core/provider 处理；缺失 provider 时不回退到本地执行。

## 最终真实引擎证据

以下数据来自独立核验后的 [validation-branch-v2.json](validation-branch-v2.json)，
源冻结为 `5effae6c2163fe7ec5b584364c408ca203d42a059e77f55c26afeb2c9e57c855`，适配器为 `a1e680ae3be1e9907bffd92c27cede61c2b8c5fb785b4cf3cd6dc49187ac6d79`。
最终非 editable wheel 的 SHA-256 为 `6ea64d87e44225d5741b7691a7aab624ebe3ac54239a9f09748250fbfe4633ee`。
源冻结 v4 只调整一个模拟引擎单元测试的 Windows 锁依赖隔离；业务断言、真实锁/Job 测试、
产品代码、题目、RPC、评分器及 wheel 均未改变。v2 冻结和修改前测试源码归档保留；
对现有引擎证据重新做只读核验，未为该测试修复重复启动游戏。

**22 个完整流程、58 个独立原生进程、
948 个必需检查结果**，均符合预先声明的正负对照预期。
其中十题 gold/base 各一次，交错串行，每次仍执行原 `full` 全套用例和完整生命周期。
durable-charge 的 gold/base 在本次执行前另有精确源码审阅记录，覆盖多文件及多进程准入。
另有两个仅添加注释、旧名单中不存在的提交字节，分别验证审阅后 gold 通过和 base 完整拒绝。
后两者验证准入，不声称新增语义覆盖、变体或正确实现。

| 任务 | gold 完整通过 | base 完整拒绝 |
| --- | ---: | ---: |
| growth-v2 | 1 | 1 |
| reversible-hand-limit-v1 | 1 | 1 |
| seeded-effect-stream-v1 | 1 | 1 |
| bounded-generator-v2 | 1 | 1 |
| deck-removal-consistency-v2 | 1 | 1 |
| live-joker-adjacency-v2 | 1 | 1 |
| isolated-card-wear-v2 | 1 | 1 |
| durable-charge-v2 | 1 | 1 |
| shop-price-coherence-v2 | 1 | 1 |
| pack-choice-commit-v2 | 1 | 1 |

所有评分原生进程正常退出、无强制清理、保护数据不变。最终依赖和导入闭包审计通过。
smoke `20260921-103036-9912de95` 单独统计；开发 pilot 和旧 v1 的 74 流程/208 进程不计入本批次。
最终适配器的 doctor 在匹配 smoke 前拒绝就绪、之后就绪，两次均只读；新状态重新绑定并完成自己的 smoke。
实际准备/启动/测试/退出耗时及目录大小见 [metrics-branch-v2.json](metrics-branch-v2.json)。

## 检查、失败与未执行项

- 最终源码下相关回归 **192 项通过**，含 6 项范围调度/计数拒绝检查。
  相同未变 wheel 的早期安装验证为 80 项通过；保留原证据，不累加为最终测试数量。
- 全仓 Ruff 通过；全仓按 Linux 平台配置的 Mypy 通过（189 源文件），这不是 Linux 引擎运行证据。
  插件自有源码和脚本分别在 Windows/Linux 类型配置下通过。
- Web lint、1 项测试、生产构建通过；core wheel 包含 Web 产物，插件 wheel 只含适配器源码。
  首次宿主 npm.ps1 返回 `Unknown command pm`，改用现有 node.exe/npm-cli.js 后完成；没有安装或升级工具。
- 七个既有 Bash 入口语法检查通过；未改变共享 shell 或评分入口。
- Windows 全仓 Mypy：45 个错误，均在 10 个未修改的 POSIX 相关文件。
  全 pytest：7 个 authoring 收集错误，原因是 Windows 缺失 `fcntl`；全套未执行。
- `devenv`、ShellCheck 不可用，ShellCheck 未运行。没有删除检查或为报告变绿修改别的游戏。
- 开发期首个 wrapper pilot 在启动游戏前因最小环境缺少 PATHEXT 失败，0 个原生评分进程。
  有界查询证明显式 `.EXE` 可解析已安装 CLI；仅修正自编操作者环境。失败目录保留，新匿名 pilot 完整通过。
- 用户授权按影响范围收缩维护验证，理由与升级条件见 [范围修订](BRANCH-REGRESSION-SCOPE-v3.md)。
  原 60 流程调度在两组 growth 完整退出后停止，标记保留，原计划没有伪造 complete。
  后续新状态执行其余九题；同一冻结 wheel 下的原两组有效记录经独立核验纳入这 22 组。
- 本批次未重跑第二/三轮、十个定向 mutation 和四个替代正确实现；逐题列在
  [regression-scope-branch-v2.json](regression-scope-branch-v2.json)，
  不将旧指纹结果写成最终版本的新证据。

## 交付与边界

[重放命令](REPLAY-branch-scope-v3.md)、[运行/源码清单](runtime-manifest-branch-v2.json)、
[最终检查摘要](branch-checks-v4.json)、[保护核验](preservation-branch-v2.json)。
私有原始证据位于 `.test-state/brv2-final/`（两组有效前缀）及 `.test-state/brv2-scope3/`，
仅操作者使用；公开题包不含 gold、私测、日志、存档或游戏内容。
原有 501 个 PoC 冻结源码、76 个暂存文件及旧 v1 证据保持不变，SWE-Game 原仓库仍只读且干净。

支持级别仍为 **Experimental / controlled local honest**。外部 Python 3.13.12 控制工具与许可 Windows
桌面安装是已准备的宿主前提；未实现跨宿主 bootstrap、managed acquisition、Harbor、Linux/macOS 引擎、
通用空白 MENU load 或不可信代码沙箱。绑定 v1 不自动迁移：0.2.2 使用新 v2 状态和匹配 smoke；
旧报告、wheel 与源快照可按原命令重放。

`engine_validated_count=10`，`packaged_count=10`，`calibrated_count=0`；
`formal_integration_status=not_implemented`。难度仍为作者预估 3E/4M/3H，未运行模型实验。
没有生成第十一题。分支审阅可据此评估实现，不能将本报告当成 Stable、全局规则豁免或正式不可信主机验收。
