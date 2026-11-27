# GameCodeBench

[English](README.md) | 简体中文

GameCodeBench 是一个面向编程智能体的游戏工程基准：让智能体为真实游戏修复或编写
mod、插件和脚本，并尽可能用真实的游戏引擎或专用服务器来评分。`rhenium` Hub
负责发现题包、在隔离的答题目录里运行智能体，并为提交评分。每个游戏都是一个独立插件。

> [!NOTE]
> 0.6 版本是研究预览版。所有游戏集成都处于 Experimental 或 In Development 状态，
> 集成后的受控运行时验证仍未完成。仓库不包含任何游戏文件：正版游戏和服务器需要在本地准备。

## 支持的游戏

| 游戏 | 状态 | 提交语言 |
| --- | --- | --- |
| [Don't Starve Together](docs/games/dst.md) | Experimental | Lua |
| [Garry's Mod](docs/games/garrys-mod.md) | Experimental | Lua (GLua) |
| [Palworld](docs/games/palworld.md) | Experimental | Lua (UE4SS)，附 JSON 清单 |
| [Balatro](docs/games/balatro-container-v1.md) | Experimental | Lua，附 JSON mod 元数据 |
| [The Binding of Isaac: Rebirth](docs/games/isaac-rebirth.md) | In Development | Lua |
| [Left 4 Dead 2](docs/games/left-4-dead-2.md) | In Development | SourcePawn、Squirrel |
| [Stardew Valley](docs/games/stardew-valley.md) | In Development | C# |
| [RimWorld](docs/games/rimworld.md) | In Development | C# |
| [Terraria](docs/games/terraria.md) | In Development | C# |
| [Mindustry](docs/games/mindustry.md) | In Development | Java |
| [Minecraft](docs/games/minecraft.md) | In Development | Java |
| [Slay the Spire](docs/games/slay-the-spire.md) | In Development | Java 8 |

各游戏的版本、平台和验证记录见[完整支持矩阵](docs/games/README.md)（英文）。

## 贡献者

| 贡献者 | 游戏 |
| --- | --- |
| Xingzhi Li | Rhenium Hub；Don't Starve Together、Garry's Mod、The Binding of Isaac: Rebirth、Mindustry、Minecraft、Stardew Valley |
| Hui Shen | Don't Starve Together |
| Changyi Yang | Garry's Mod、Slay the Spire |
| Yunta Hsieh | Garry's Mod |
| Xuesong Ye | The Binding of Isaac: Rebirth |
| Zhuhan Bao | The Binding of Isaac: Rebirth、Minecraft |
| Zhuoran | Left 4 Dead 2、Terraria |
| Jiaxuan Luo | Stardew Valley |
| Zhengshen He | RimWorld |
| Yunge | Mindustry |
| Rui Hu | Palworld |
| Guobin Zhang | Palworld |
| Sangyu Pan | Balatro |

## 环境要求

- [Nix](https://nixos.org/download) 和 [devenv](https://devenv.sh/getting-started/)。
  开发 shell 会提供 Python 3.12、Node.js 和全部插件。
- Docker：引擎运行在 Linux x86_64 容器里的游戏需要它。
- 部分游戏还需要正版授权或特定主机配置。Palworld 和 Balatro 通过 `rhenium runtime prepare` 显式准备 Linux 运行环境。
  具体见各游戏的文档页。

## 快速开始

```sh
git clone git@github.com:Touchstone-AI-Lab/game-swe.git
cd game-swe
cp .env.example .env    # 填入模型 API key
devenv shell
```

进入 shell 之后：

```sh
rhenium tasks --game dst                                  # 列出任务
rhenium benchmark dst --provider claude                   # 让智能体做完 DST 的全部任务
rhenium benchmark dst/core/dsmmo-release-regressions      # 只做一道题，默认 provider 为 api
rhenium run dst/core/dsmmo-release-regressions ./my-mod   # 为已有提交评分
hub                                                       # Web UI：http://127.0.0.1:4317
```

- `rhenium benchmark <game>[/<pack>[/<task>]] --provider api|codex|claude` 全程无人值守：
  每道题使用独立的匿名答题目录，智能体完成实现后由平台评分一次，最后输出 JSON 汇总。
  `api`（默认）是 mini-swe-agent，读取 `RHENIUM_MODEL_*` 配置；`codex` 和 `claude`
  是本机安装的 CLI，使用它们自己的登录或 `.env` 里的 key。运行前先准备好该游戏的运行时。
- `benchmark <task> [mini|codex|claude] [strict|practice]` 则以交互方式打开一道题，
  由智能体自己运行评分命令。
- `rhenium run` 使用受信任的 `honest` 模式，它不是运行恶意代码的沙箱。
  评测档位、安全模式和全部命令见 [Running the Hub](docs/usage.md)（英文）。

## 准备游戏运行时

需要引擎的任务要先准备好固定版本的游戏或专用服务器，只需准备一次：

```sh
rhenium runtime list --game dst                      # 查看运行时 key
rhenium auth login container                         # 正版游戏改用 `steam`，
                                                     # 不在 Steam 上的官方服务器用 `official-download`
rhenium runtime prepare dst/dst-dedicated-24700372
```

评分过程不会登录或下载任何东西。缺少运行时时，`full` 评测结果为 incomplete，不会通过。
各游戏的运行时 key 见对应的游戏文档页。

## 仓库结构

```text
src/rhenium/    与游戏无关的 Hub 核心：CLI、API、数据库、智能体运行器
plugins/        每个游戏一个独立发行包
benchmarks/     只读题包：题面、初始代码、评测器
providers/      认证与运行时来源提供方（Steam、容器、本地文件、官方下载）
web/            本地 Web UI（React、Vite）
tools/          出题和实验工具
docs/           文档；docs/games/ 下每个游戏一页
```

## 文档

文档均为英文。

- **使用：** [Running the Hub](docs/usage.md) ·
  [Managed authentication and runtimes](docs/managed-runtimes.md) ·
  [Disposable evaluation hosts](docs/disposable-evaluation-hosts.md) ·
  [Web UI](web/README.md)
- **游戏：** [Supported games](docs/games/README.md) ·
  [Status definitions](docs/statuses.md)
- **扩展：** [Architecture](docs/architecture.md) ·
  [Plugin contract](docs/plugin-contract.md) ·
  [Adding a game](docs/adding-a-game.md) ·
  [Clean-room authoring](tools/authoring/README.md) ·
  [Contributing](CONTRIBUTING.md)

全部页面见[文档索引](docs/index.md)。

## 开发

```sh
check    # ruff、mypy、pytest、web lint/test/build、shellcheck、git diff --check
```

贡献者和编程智能体都需遵守 [AGENTS.md](AGENTS.md)：使用 Conventional Commits，
不改动冻结的 benchmark 资产，交付前跑完全部检查。
