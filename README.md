# life-archive

个人生活数据归档。定时从各接口拉取记录，写入 `data/` 并提交到自己的 git 仓库。

豆瓣和 Bangumi 的标记先同步到 NeoDB，代码在 [viazure/douban-backup](https://github.com/viazure/douban-backup)。本仓库只拉取 NeoDB。

`vendor/run_page/` 是 [yihong0618/running_page](https://github.com/yihong0618/running_page) 的切片，这里只做佳明中国和本地 TCX / GPX。Strava、Nike、Keep 等其他运动软件的同步见原仓库。

## 现在同步的接口

| 接口 | 凭证 | 写出 |
|---|---|---|
| NeoDB | `NEODB_TOKEN` | `data/neodb/shelf.json` |
| Last.fm | `LASTFM_API_KEY`、`LASTFM_USER` | `data/lastfm/scrobbles.json`、`top.json`、`loved.json` |
| ListenBrainz | `LISTENBRAINZ_USER` | `data/listenbrainz/listens.json`、`top.json`、`feedback.json`、`listening-activity.json` |
| 佳明中国 | `GARMIN_SECRET_STRING_CN` | `data/workouts/fit/`、`activities.json` |
| 本地 TCX / GPX | 无 | `data/workouts/tcx/`、`gpx/`，再导出摘要 |

字段说明见 [CONSUME.md](CONSUME.md)。

## 快速开始

1. Fork 本仓库。
2. 若要自动提交自己的档案，把 fork 设为 **Private**。
3. 打开 **Actions**，如有提示则启用 workflows。
4. **Settings → Actions → General → Workflow permissions** 选 **Read and write permissions**。
5. 只填用到的 Secrets / Variables（见下表）。
6. **Actions → fetch** 和 **sync garmin** 各手动跑一次，确认日志成功。

Token 等敏感信息放到 **Secrets**，用户名放到 **Variables**。不要写进代码。

| 名称 | 类型 | 说明 |
|---|---|---|
| `NEODB_TOKEN` | Secret | [NeoDB 开发者页面](https://neodb.social/developer/) |
| `LASTFM_API_KEY` | Secret | Last.fm API key |
| `LASTFM_USER` | Variable | Last.fm 用户名 |
| `LISTENBRAINZ_USER` | Variable | ListenBrainz 用户名 |
| `GARMIN_SECRET_STRING_CN` | Secret | 佳明中国会话串 |

未配置的接口会跳过，workflow 仍成功退出。

佳明会话串在 [running_page](https://github.com/yihong0618/running_page) 仓库生成：

```powershell
python run_page/get_garmin_secret.py 邮箱 密码 --is-cn
```

## 配置

本地环境变量（PowerShell）：

```powershell
$env:NEODB_TOKEN = "NeoDB token"
$env:LASTFM_API_KEY = "Last.fm API key"
$env:LASTFM_USER = "your-lastfm-username"
$env:LISTENBRAINZ_USER = "your-listenbrainz-username"
```

| 脚本 | 说明 |
|---|---|
| `scripts/neodb.py` | 拉书架 |
| `scripts/lastfm.py` | 可加 `--only scrobbles` / `top` / `loved` |
| `scripts/listenbrainz.py` | 可加 `--only listens` / `top` / `feedback` / `activity` |
| `vendor/run_page/garmin_sync.py` | 默认中国区 `--is-cn`，下载 FIT |
| `scripts/export_activities.py` | 从 FIT / 缓存写出 `activities.json` |

时区默认 `Asia/Shanghai`（见 `vendor/run_page/config.py`）。

### TCX / GPX

文件放到 `data/workouts/tcx/`、`data/workouts/gpx/`：

```powershell
python vendor/run_page/tcx_sync.py
python vendor/run_page/gpx_sync.py
python scripts/import_lap_summaries.py
python scripts/export_activities.py
```

### 定时

| Workflow | 时间 |
|---|---|
| `sync-garmin.yml` | 每天 00:00 UTC |
| `fetch.yml` | 每天 01:00 UTC |

当天没有新数据时不会产生新提交。

### 更新 vendor/run_page/

```powershell
python scripts/sync_run_page.py
git diff vendor/run_page
```

默认源目录 `../running_page`，可用 `--source`、`--dry-run`。不会覆盖 `vendor/run_page/config.py`。

## 本地运行

需要 Python 3.12。

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python scripts/jsonio.py --self-check
python scripts/neodb.py
python scripts/lastfm.py
python scripts/listenbrainz.py
```

佳明：

```powershell
python vendor/run_page/garmin_sync.py "会话串" --is-cn --fit
python scripts/export_activities.py
```

代码检查：

```powershell
pip install -r requirements-dev.txt
black --check scripts
ruff check scripts
```

## 许可证

`scripts/` 等本仓库自有代码为 MIT，见 [LICENSE](LICENSE)。

`vendor/run_page/` 来自 running_page，版权见 [NOTICE](vendor/run_page/NOTICE)，许可见 [LICENSE](vendor/run_page/LICENSE)。
