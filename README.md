# life-archive

个人生活数据归档工具。脚本与定时同步逻辑维护在本仓库；数据可写在本仓（fork）或私有数据仓。

豆瓣和 Bangumi 的标记需先同步到 NeoDB，相关代码见 [viazure/douban-backup](https://github.com/viazure/douban-backup)；本仓库只从 NeoDB 拉取数据。

`vendor/run_page/` 包含 [yihong0618/running_page](https://github.com/yihong0618/running_page) 的部分代码，本仓库仅使用其中的佳明中国、TCX 和 GPX 同步功能。Strava、Nike、Keep 等其他运动平台的同步方式见原仓库。

> [!WARNING]
> `data/` 可能包含个人活动轨迹和生活记录。公开 fork 中同步的数据也会公开；需要隐私时请用下面的「私有数据仓」方式。

下文统一使用 `python`；如果系统只提供 `python3`，请自行替换。

## 两种用法

| 场景 | 做法 |
|---|---|
| 新人 / 愿意公开数据 | Fork 本仓库，在 fork 里配 Secrets，跑 Actions；数据写在 fork 的 `data/` |
| 私有数据 + 公开脚本 | 私有仓只存 `data/` 与密钥；用 git submodule 引用本仓，并设置 `LIFE_DATA_ROOT` 指向私有仓根目录 |

`viazure/life-archive` 本身不收录个人档案；CI 会拒绝跟踪 `data/` 下除 `.gitkeep` 以外的文件。

### 私有数据仓（submodule）

在私有仓根目录：

```console
git submodule add https://github.com/viazure/life-archive.git tools/life-archive
git submodule update --init --recursive
```

本地同步前设置数据根（PowerShell）：

```powershell
$env:LIFE_DATA_ROOT = (Resolve-Path .).Path
python tools/life-archive/scripts/neodb.py
```

未设置 `LIFE_DATA_ROOT` 时，脚本把数据写到代码仓根下的 `data/`（fork 用法）。若代码仓的 `origin` 是 `viazure/life-archive`，且数据根落在这个检出里，写入会被拒绝，避免 submodule 误把档案写进公开检出。

GitHub Actions：checkout 时带 `submodules: true`，设置 `LIFE_DATA_ROOT=${{ github.workspace }}`，再调用：

- `./tools/life-archive/.github/actions/fetch`
- `./tools/life-archive/.github/actions/sync-garmin`

Secrets / Variables 配在私有仓，不要写进本仓。

## 支持的数据源

| 数据源 | 配置项 | 输出 |
|---|---|---|
| NeoDB | `NEODB_TOKEN` | `data/neodb/shelf.json` |
| Last.fm | `LASTFM_API_KEY`、`LASTFM_USER` | `data/lastfm/scrobbles.json`、`top.json`、`loved.json` |
| ListenBrainz | `LISTENBRAINZ_USER` | `data/listenbrainz/listens.json`、`top.json`、`feedback.json`、`listening-activity.json` |
| 佳明中国 | `GARMIN_SECRET_STRING_CN` | `data/workouts/fit/`、`data/workouts/activities.json`、`data/workouts/splits/`、`data/health/daily.json` |
| 本地 TCX / GPX | 无 | `data/workouts/tcx/`、`data/workouts/gpx/`、`data/workouts/activities.json` |

## 消费端

本仓库是**写入侧**：定时同步并提交 `data/`。博客、看板、脚本、AI 等**读取侧**直接消费这些文件，没有查询 API。

1. `git pull` 拉取最新提交即可拿到更新；当天没有新数据时不会产生新提交。
2. 只读 `data/`，忽略 `.cache/`。
3. 路径与字段约定见 [CONSUME.md](CONSUME.md)。摘要优先用 JSON；轨迹明细在 `fit/` / `tcx/` / `gpx/` 原件里。
4. 听歌有两份源：时间线用 ListenBrainz，红心与时段榜用 Last.fm；封面回退规则见 CONSUME.md。

| 想看什么 | 读哪里 |
|---|---|
| 某一天的恢复、负荷和当天训练 | `data/health/daily.json` |
| 全量运动摘要（无轨迹、无地址） | `data/workouts/activities.redacted.json` |
| 书架标记 | `data/neodb/shelf.json` |
| 听歌时间线 | `data/listenbrainz/listens.json` |
| 红心 / 时段榜 | `data/lastfm/loved.json`、`top.json` |

## 快速开始（fork）

1. Fork 本仓库（公开数据）或建私有仓并用 submodule（见上）。
2. 打开 **Actions**；如果出现提示，请启用 workflows。
3. 在 **Settings → Actions → General → Workflow permissions** 中选择 **Read and write permissions**。
4. 按下表配置实际需要的 Secrets 和 Variables。
5. 在 **Actions** 中分别手动运行一次 **fetch** 和 **sync garmin**，确认日志无误。

Token、会话串等敏感信息应存入 **Secrets**，用户名存入 **Variables**，不要直接写进代码。

| 名称 | 类型 | 说明 |
|---|---|---|
| `NEODB_TOKEN` | Secret | [NeoDB 开发者页面](https://neodb.social/developer/) |
| `LASTFM_API_KEY` | Secret | Last.fm API key |
| `LASTFM_USER` | Variable | Last.fm 用户名 |
| `LISTENBRAINZ_USER` | Variable | ListenBrainz 用户名 |
| `GARMIN_SECRET_STRING_CN` | Secret | 佳明中国会话串 |

未配置的数据源会被跳过，不影响其他数据源运行。

生成佳明中国会话串：

```console
python -m pip install -r requirements.txt
python vendor/run_page/get_garmin_secret.py "邮箱" "密码" --is-cn
```

## 本地配置

Linux、macOS 或 Git Bash：

```bash
export NEODB_TOKEN="NeoDB token"
export LASTFM_API_KEY="Last.fm API key"
export LASTFM_USER="your-lastfm-username"
export LISTENBRAINZ_USER="your-listenbrainz-username"
```

Windows PowerShell:

```powershell
$env:NEODB_TOKEN = "NeoDB token"
$env:LASTFM_API_KEY = "Last.fm API key"
$env:LASTFM_USER = "your-lastfm-username"
$env:LISTENBRAINZ_USER = "your-listenbrainz-username"
```

只需设置实际使用的数据源。默认时区为 `Asia/Shanghai`，配置见 `vendor/run_page/config.py`。

## 本地运行

需要 Python 3.12。

创建虚拟环境：

```console
python -m venv .venv
```

激活虚拟环境：

```bash
# Linux / macOS / Git Bash
source .venv/bin/activate
```

```powershell
# Windows PowerShell
.\.venv\Scripts\Activate.ps1
```

安装依赖并运行所需脚本：

```console
python -m pip install -r requirements.txt
python scripts/jsonio.py --self-check
python scripts/neodb.py
python scripts/lastfm.py
python scripts/listenbrainz.py
```

| 脚本 | 说明 |
|---|---|
| `scripts/neodb.py` | 同步书架 |
| `scripts/lastfm.py` | 可用 `--only scrobbles`、`top` 或 `loved` 限定内容 |
| `scripts/listenbrainz.py` | 可用 `--only listens`、`top`、`feedback` 或 `activity` 限定内容 |
| `vendor/run_page/garmin_sync.py` | 使用 `--is-cn --fit` 从佳明中国下载 FIT |
| `scripts/export_activities.py` | 从 FIT / 缓存写出 `activities.json` 和脱敏的 `activities.redacted.json` |
| `vendor/run_page/gen_splits.py` | 从 FIT 生成 `data/workouts/splits/{run_id}.json`（无坐标、无逐秒序列） |
| `scripts/garmin_health.py` | 拉取每日健康指标，写出 `data/health/daily.json` |
| `scripts/health_daily.py` | 把当天训练挂到日档案；`--self-check` 不联网 |

### 佳明中国

```console
python scripts/health_daily.py --self-check
python scripts/garmin_health.py --self-check
python vendor/run_page/garmin_sync.py "会话串" --is-cn --fit
python scripts/export_activities.py
python vendor/run_page/gen_splits.py --fit-only --fit-dir data/workouts/fit --out data/workouts/splits --activities data/workouts/activities.json
python scripts/garmin_health.py "会话串" --is-cn
```

会话串也可以放在环境变量 `GARMIN_SECRET_STRING_CN` 里。日档案按北京时间一天一行，字段见 [CONSUME.md](CONSUME.md)。近 90 天里还没有健康指标的日期会继续补，同时重拉最近 14 天。

本公开仓库不收录任何人的 `data/health/daily.json`。在你自己的仓库里跑同步时，工作流会写入并提交这份文件。运动归档先提交；健康同步失败不会挡住这次运动提交。

### TCX / GPX

文件放到 `data/workouts/tcx/`、`data/workouts/gpx/`：

```console
python vendor/run_page/tcx_sync.py
python vendor/run_page/gpx_sync.py
python scripts/import_lap_summaries.py
python scripts/export_activities.py
```

## 定时任务

| Workflow | 运行时间 |
|---|---|
| `sync-garmin.yml` | 每天 00:00 UTC（北京时间 08:00） |
| `fetch.yml` | 每天 01:00 UTC（北京时间 09:00） |

这两个 workflow 只在 **fork** 或私有数据仓里执行；上游 `viazure/life-archive` 会跳过（公开仓只维护脚本与 composite action）。私有仓也可不启用这两份文件，改为自行调度并调用 `.github/actions/fetch` / `sync-garmin`。

当天没有新数据时不会产生新提交。

## 维护

### 更新 `vendor/run_page/`

```console
python scripts/sync_run_page.py
git diff vendor/run_page
```

默认源目录 `../running_page`，可用 `--source`、`--dry-run`。不会覆盖 `vendor/run_page/config.py`。同步清单含 `gen_splits.py`（从 FIT 生成无 GPS 的分段摘要 JSON）。

### 代码检查

```console
python -m pip install -r requirements-dev.txt
black --check scripts
ruff check scripts
```

## 许可证

`scripts/` 等本仓库自有代码采用 MIT 许可证，见 [LICENSE](LICENSE)。

`vendor/run_page/` 源自 running_page，版权信息见 [NOTICE](vendor/run_page/NOTICE)，许可证见 [LICENSE](vendor/run_page/LICENSE)。
