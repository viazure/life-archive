# life-archive

个人生活数据归档工具。通过 GitHub Actions 定时从各数据源拉取记录，写入 `data/` 并提交到你自己的仓库。

豆瓣和 Bangumi 的标记需先同步到 NeoDB，相关代码见 [viazure/douban-backup](https://github.com/viazure/douban-backup)；本仓库只从 NeoDB 拉取数据。

`vendor/run_page/` 包含 [yihong0618/running_page](https://github.com/yihong0618/running_page) 的部分代码，本仓库仅使用其中的佳明中国、TCX 和 GPX 同步功能。Strava、Nike、Keep 等其他运动平台的同步方式见原仓库。

> [!WARNING]
> `data/` 可能包含个人活动轨迹和生活记录。公开 fork 中同步的数据也会公开；如需保护隐私，请改用私有仓库。

下文统一使用 `python`；如果系统只提供 `python3`，请自行替换。

## 支持的数据源

| 数据源 | 配置项 | 输出 |
|---|---|---|
| NeoDB | `NEODB_TOKEN` | `data/neodb/shelf.json` |
| Last.fm | `LASTFM_API_KEY`、`LASTFM_USER` | `data/lastfm/scrobbles.json`、`top.json`、`loved.json` |
| ListenBrainz | `LISTENBRAINZ_USER` | `data/listenbrainz/listens.json`、`top.json`、`feedback.json`、`listening-activity.json` |
| 佳明中国 | `GARMIN_SECRET_STRING_CN` | `data/workouts/fit/`、`data/workouts/activities.json`、`data/health/daily.json` |
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
| 全量运动摘要 | `data/workouts/activities.ai.json`（无轨迹、无地址） |
| 书架标记 | `data/neodb/shelf.json` |
| 听歌时间线 | `data/listenbrainz/listens.json` |
| 红心 / 时段榜 | `data/lastfm/loved.json`、`top.json` |

## 快速开始

1. 如果愿意公开自己的数据，可直接 fork 本仓库；如需保护隐私，请将代码复制到新建的私有仓库。
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
| `scripts/export_activities.py` | 从 FIT / 缓存写出 `activities.json` 和脱敏的 `activities.ai.json` |
| `scripts/garmin_health.py` | 拉取每日健康指标，写出 `data/health/daily.json` |
| `scripts/health_daily.py` | 把当天训练挂到日档案；`--self-check` 不联网 |

### 佳明中国

```console
python scripts/health_daily.py --self-check
python scripts/garmin_health.py --self-check
python vendor/run_page/garmin_sync.py "会话串" --is-cn --fit
python scripts/export_activities.py
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

当天没有新数据时不会产生新提交。

## 维护

### 更新 `vendor/run_page/`

```console
python scripts/sync_run_page.py
git diff vendor/run_page
```

默认源目录 `../running_page`，可用 `--source`、`--dry-run`。不会覆盖 `vendor/run_page/config.py`。

### 代码检查

```console
python -m pip install -r requirements-dev.txt
black --check scripts
ruff check scripts
```

## 许可证

`scripts/` 等本仓库自有代码采用 MIT 许可证，见 [LICENSE](LICENSE)。

`vendor/run_page/` 源自 running_page，版权信息见 [NOTICE](vendor/run_page/NOTICE)，许可证见 [LICENSE](vendor/run_page/LICENSE)。
