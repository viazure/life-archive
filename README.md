# life-archive

个人生活数据归档工具。

本仓库维护同步脚本和定时任务。数据可以写在你 fork 出来的公开仓，也可以写在私有数据仓里。

豆瓣和 Bangumi 的标记需先同步到 NeoDB，相关代码见 [viazure/douban-backup](https://github.com/viazure/douban-backup)。本仓库只从 NeoDB 拉取。

`vendor/run_page/` 含 [yihong0618/running_page](https://github.com/yihong0618/running_page) 的部分代码。本仓库只用其中的佳明中国、TCX、GPX 同步。其他运动平台见原仓库。

> [!WARNING]
> `data/` 可能含个人活动轨迹和生活记录。公开 fork 里同步的数据也会公开。需要隐私时，请用下面的「私有数据仓」方式。

## 选择用法

| 场景 | 做法 |
|---|---|
| 公开 fork | Fork 本仓库，在 fork 里配 Secrets，跑 Actions；数据写在 fork 的 `data/` |
| 私有数据仓 | 私有仓只存 `data/` 与密钥；用 git submodule 引用本仓，并设置 `LIFE_DATA_ROOT` 指向私有仓根目录 |

`viazure/life-archive` 本身不收录个人档案。公开仓只维护脚本与 composite action。

## 快速开始（公开 fork）

1. Fork 本仓库。
2. 打开 **Actions**；如有提示，启用 workflows。
3. 在 **Settings → Actions → General → Workflow permissions** 中选择 **Read and write permissions**。
4. 按下表配置实际需要的 Secrets 和 Variables。
5. 在 **Actions** 中分别手动运行一次 **fetch** 和 **sync garmin**，确认日志无误。

Token、会话串等敏感信息放入 **Secrets**。用户名放入 **Variables**。不要写进代码。

| 名称 | 类型 | 说明 |
|---|---|---|
| `NEODB_TOKEN` | Secret | [NeoDB 开发者页面](https://neodb.social/developer/) |
| `LASTFM_API_KEY` | Secret | Last.fm API key |
| `LASTFM_USER` | Variable | Last.fm 用户名 |
| `LISTENBRAINZ_USER` | Variable | ListenBrainz 用户名 |
| `GARMIN_SECRET_STRING_CN` | Secret | 佳明中国会话串 |

未配置的数据源会被跳过，不影响其他数据源。

生成佳明中国会话串：

```console
python -m pip install -r requirements.txt
python vendor/run_page/get_garmin_secret.py "邮箱" "密码" --is-cn
```

下文示例统一写 `python`。若系统只有 `python3`，请自行替换。

## 私有数据仓（submodule）

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

未设置 `LIFE_DATA_ROOT` 时，脚本把数据写到代码仓根下的 `data/`（即 fork 用法）。

GitHub Actions：checkout 时带 `submodules: true`，设置 `LIFE_DATA_ROOT=${{ github.workspace }}`，再调用：

- `./tools/life-archive/.github/actions/fetch`
- `./tools/life-archive/.github/actions/sync-garmin`

Secrets / Variables 配在私有仓，不要写进本仓。

更多防误写与上游跳过说明见文末「附录 / FAQ」。

## 支持的数据源

| 数据源 | 配置项 | 输出 |
|---|---|---|
| NeoDB | `NEODB_TOKEN` | `data/neodb/shelf.json` |
| Last.fm | `LASTFM_API_KEY`、`LASTFM_USER` | `data/lastfm/scrobbles.json`、`top.json`、`loved.json` |
| ListenBrainz | `LISTENBRAINZ_USER` | `data/listenbrainz/listens.json`、`top.json`、`feedback.json`、`listening-activity.json` |
| 佳明中国 | `GARMIN_SECRET_STRING_CN` | `data/workouts/fit/`、`data/workouts/activities.json`、`data/workouts/splits/`、`data/health/daily.json` |
| 本地 TCX / GPX | 无 | `data/workouts/tcx/`、`data/workouts/gpx/`、`data/workouts/activities.json` |

## 本地配置与运行

需要 Python 3.12。

### 环境变量

Linux、macOS 或 Git Bash：

```bash
export NEODB_TOKEN="NeoDB token"
export LASTFM_API_KEY="Last.fm API key"
export LASTFM_USER="your-lastfm-username"
export LISTENBRAINZ_USER="your-listenbrainz-username"
```

Windows PowerShell：

```powershell
$env:NEODB_TOKEN = "NeoDB token"
$env:LASTFM_API_KEY = "Last.fm API key"
$env:LASTFM_USER = "your-lastfm-username"
$env:LISTENBRAINZ_USER = "your-listenbrainz-username"
```

只需设置实际使用的数据源。默认时区为 `Asia/Shanghai`，配置见 `vendor/run_page/config.py`。

### 虚拟环境与依赖

```console
python -m venv .venv
```

```bash
# Linux / macOS / Git Bash
source .venv/bin/activate
```

```powershell
# Windows PowerShell
.\.venv\Scripts\Activate.ps1
```

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

会话串也可以放在环境变量 `GARMIN_SECRET_STRING_CN` 里。日档案按北京时间一天一行，字段见 [CONSUME.md](CONSUME.md)。

运动归档先提交；健康同步失败不会挡住这次运动提交。补洞与重拉策略见附录。

### TCX / GPX

把文件放到 `data/workouts/tcx/`、`data/workouts/gpx/`：

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

这两个 workflow 只在 fork 或私有数据仓里执行。上游 `viazure/life-archive` 会跳过。详见附录。

## 读取数据

定时同步会把结果提交到 `data/`。博客、看板、脚本、AI 等直接读这些文件，没有查询 API。

1. `git pull` 即可拿到更新。
2. 只读 `data/`，忽略 `.cache/`。
3. 路径与字段约定见 [CONSUME.md](CONSUME.md)。完整摘要在 `activities.json`（可含轨迹与地址）；需要公开或分享时用脱敏的 `activities.redacted.json`。轨迹原件在 `fit/` / `tcx/` / `gpx/`。
4. 听歌有两份源：时间线用 ListenBrainz，红心与时段榜用 Last.fm；封面回退规则见 CONSUME.md。

| 想看什么 | 读哪里 |
|---|---|
| 某一天的恢复、负荷和当天训练 | `data/health/daily.json` |
| 全量运动摘要（可含轨迹与地址等敏感字段） | `data/workouts/activities.json` |
| 脱敏运动摘要（无轨迹、无地址，便于公开消费） | `data/workouts/activities.redacted.json` |
| 书架标记 | `data/neodb/shelf.json` |
| 听歌时间线 | `data/listenbrainz/listens.json` |
| 红心 / 时段榜 | `data/lastfm/loved.json`、`top.json` |

## 附录 / FAQ

### 为什么我的写入被拒绝了？

若代码仓的 `origin` 是 `viazure/life-archive`，且数据根落在这个检出里，脚本会拒绝写入。这是为了避免 submodule 误把档案写进公开上游检出。请改用 fork，或设置 `LIFE_DATA_ROOT` 指向私有数据仓根目录。

### 上游会不会提交我的 `data/`？

不会。CI 拒绝跟踪 `data/` 下除 `.gitkeep` 以外的文件。本公开仓库也不收录任何人的 `data/health/daily.json`。在你自己的仓库里跑同步时，工作流会写入并提交这份文件。

### 上游的定时任务会跑吗？

不会。`fetch.yml` 与 `sync-garmin.yml` 在上游 `viazure/life-archive` 会跳过。公开仓只维护脚本与 composite action。

私有仓也可以不启用这两份 workflow 文件，改为自行调度，并调用：

- `.github/actions/fetch`
- `.github/actions/sync-garmin`

（在 submodule 布局下路径为 `./tools/life-archive/.github/actions/...`。）

### 当天没有新数据会怎样？

不会产生新提交。

### 佳明健康数据如何补洞？

近 90 天里还没有健康指标的日期会继续补，同时重拉最近 14 天。

### 系统只有 `python3` 怎么办？

把文档中的 `python` 换成 `python3` 即可。

### 如何更新 `vendor/run_page/`？（维护者）

```console
python scripts/sync_run_page.py
git diff vendor/run_page
```

默认源目录 `../running_page`，可用 `--source`、`--dry-run`。不会覆盖 `vendor/run_page/config.py`。同步清单含 `gen_splits.py`。

### 代码检查

```console
python -m pip install -r requirements-dev.txt
black --check scripts
ruff check scripts
```

### 许可证

`scripts/` 等本仓库自有代码采用 MIT 许可证，见 [LICENSE](LICENSE)。

`vendor/run_page/` 源自 running_page，版权信息见 [NOTICE](vendor/run_page/NOTICE)，许可证见 [LICENSE](vendor/run_page/LICENSE)。
