# 读取归档数据

面向消费端（博客、看板、脚本、AI 等）。本仓库只负责同步并提交文件；没有查询 API，也没有单独的鉴权层。

同步之后，数据在 `data/` 目录里。更新后会出现新的 git 提交，`git pull` 即可。忽略 `.cache/`（本地/CI 缓存，不作为归档契约）。

读取约定：

1. 以路径和 JSON 字段为准；未知字段应忽略，不要因多出字段而失败。
2. 摘要优先读 JSON；需要轨迹点、逐秒心率时再打开 `fit/` / `tcx/` / `gpx/` 原件。
3. 展示用中文名称、单位换算、筛选与分组由读取方自己处理。

## 文件

| 路径 | 内容 |
|---|---|
| `data/health/daily.json` | 每日健康指标和当天训练。字段与设备无关 |
| `data/workouts/activities.json` | 全部活动的摘要，JSON 数组（含轨迹与地址） |
| `data/workouts/activities.ai.json` | 脱敏运动摘要：无轨迹、无地址。全量活动看这份 |
| `data/workouts/fit/` | FIT 原件。文件名是佳明 activity id，例如 `438269511.fit` |
| `data/workouts/tcx/` | TCX 原件 |
| `data/workouts/gpx/` | GPX 原件 |
| `data/neodb/shelf.json` | 书架标记 |
| `data/lastfm/scrobbles.json` | 听歌记录 |
| `data/lastfm/loved.json` | 红心歌曲 |
| `data/lastfm/top.json` | 各时段的艺人、专辑、歌曲排行 |
| `data/listenbrainz/listens.json` | ListenBrainz 收听记录 |
| `data/listenbrainz/top.json` | ListenBrainz 各时段艺人、专辑组、曲目排行 |
| `data/listenbrainz/feedback.json` | ListenBrainz 喜欢 / 不喜欢反馈 |
| `data/listenbrainz/listening-activity.json` | ListenBrainz 按年听歌量 |

## 听歌双源

| 用途 | 用哪份 |
|---|---|
| 听了什么、何时听 | `data/listenbrainz/listens.json` |
| 红心、时段榜（现有展示） | `data/lastfm/loved.json`、`top.json` |
| 封面 | 先 Last.fm `image`；没有则用 ListenBrainz 的 Cover Art Archive 字段（见下） |

封面回退：取 listen 的 `track_metadata.mbid_mapping.caa_release_mbid`，拼

`https://coverartarchive.org/release/{caa_release_mbid}/front-250`

需要更大图可用 `front-500`。没有 `caa_release_mbid` 时用占位图。

佳明活动和每日健康大约 00:00 UTC 更新，书架和听歌大约 01:00 UTC 更新。当天没有新数据时仓库不会产生新提交。

## 活动摘要

`data/workouts/activities.json` 是 JSON 数组，每个元素是一次活动。

```json
{
  "run_id": 1710000000000,
  "source": "garmin",
  "type": "running",
  "subtype": "generic",
  "name": "",
  "start_date": "2024-03-10 02:00:00",
  "start_date_local": "2024-03-10 10:00:00",
  "distance": 5200.0,
  "moving_time": "0:32:10",
  "average_speed": 2.69,
  "average_heartrate": 148,
  "elevation_gain": 20.0,
  "summary_polyline": "encoded-polyline",
  "location_country": "",
  "streak": 1
}
```

| 字段 | 含义 |
|---|---|
| `run_id` | 这条摘要的 ID，由开始时间生成。它不是 FIT 文件名 |
| `source` | `garmin`、`tcx` 或 `gpx`，表示这条记录来自哪种文件 |
| `type` | 运动类型 |
| `subtype` | 运动子类型。可以是空字符串 |
| `name` | 标题。可以是空字符串 |
| `start_date` | UTC 时间，`YYYY-MM-DD HH:MM:SS` |
| `start_date_local` | 北京时间，同一格式 |
| `distance` | 距离，单位米。可以是 `0` |
| `moving_time` | 时长，`H:MM:SS` 或带小数秒，例如 `0:27:14`、`0:58:00.962000`。展示时通常对时/分/秒向下取整 |
| `average_speed` | 平均速度，单位米/秒 |
| `average_heartrate` | 平均心率。可以是 `null` |
| `elevation_gain` | 累计爬升，单位米 |
| `summary_polyline` | 轨迹，Google encoded polyline。没有轨迹时是空字符串 |
| `location_country` | 国家或地区。可以是空字符串 |
| `streak` | 连续天数。可以不使用 |

`source` 为 `garmin`、`tcx` 或 `gpx` 时，`type` 和 `subtype` 都用佳明 FIT 运动名，全部小写。下表是常见组合，不是完整枚举。读取方按字面使用这三个字段即可，不必只认表内取值。

| `type` | `subtype` |
|---|---|
| `running` | `generic` |
| `running` | `treadmill` |
| `hiking` | `generic` |
| `walking` | `generic` |
| `cycling` | `generic` |
| `cycling` | `indoor_cycling` |
| `swimming` | `lap_swimming` |
| `training` | `strength_training` |
| `training` | `breathing` |
| `training` | `jump_rope` |
| `training` | `yoga` |
| `training` | `generic` |
| `fitness_equipment` | `pilates` |
| `fitness_equipment` | `stair_climbing` |
| `hiit` | `generic` |
| `skateboarding` | `generic` |

筛选、分组和中文名称由读取方自己决定，直接使用上面的三个字段。`summary_polyline` 为空就没有地图线。`distance` 为 `0` 时，时长看 `moving_time`。

轨迹点、逐秒心率等明细在原件里：佳明用 `data/workouts/fit/` 下的文件名对应佳明 activity id；其余用 `tcx/` 和 `gpx/` 里的文件。摘要里的 `run_id` 不能用来找这些文件名。

### AI 分析用脱敏摘要

看某一天的恢复、负荷和当天练了什么，读 `data/health/daily.json`。要全量活动列表时再读 `data/workouts/activities.ai.json`。不要把 `activities.json` 或 `fit/` / `tcx/` / `gpx/` 原件交给外部模型。

`activities.ai.json` 也是 JSON 数组，与完整摘要同一批活动、同一排序。保留上表中的训练与身体指标（含 `average_heartrate`、距离、时长、速度、爬升、本地开始时间等），不含 `summary_polyline` 和 `location_country`。字段名、单位与上表相同。由 `scripts/export_activities.py` 与完整摘要一同写出。

## 每日健康

`data/health/daily.json` 是消费契约。健康指标和当天训练已经在同一行里，字段名是本仓库自己的，不随设备接口变化。这份日档案只在私有仓库，公开归档不包含它。

```json
{
  "source": "health.daily",
  "items": []
}
```

`items` 按 `date` 升序，一天一行。日期是北京时间，`YYYY-MM-DD`。有健康指标或有训练的日期都会留下。只有训练、还没有健康数据的日子，健康字段是 `null`。

`metrics_source` 说明这行健康指标从哪来。目前是 `garmin`。以后换成别的设备，新数据仍用下面这些字段，旧行保持原来的 `metrics_source`。读取方忽略不认识的取值即可。

没有上报的值是 `null`。`sleep`、`hrv`、`training` 这三个对象一直在，里面的字段可以是 `null`。

| 字段 | 含义 |
|---|---|
| `date` | 北京时间日期 |
| `metrics_source` | 健康指标来源。可以是 `null` |
| `steps` | 步数 |
| `distance_m` | 当日距离，米 |
| `active_calories` | 活动消耗，千卡 |
| `total_calories` | 总消耗，千卡 |
| `intensity_minutes` | 强度分钟。中等强度按 1 计，剧烈强度按 2 计 |
| `resting_hr` | 静息心率 |
| `min_hr` | 最低心率 |
| `max_hr` | 最高心率 |
| `avg_stress` | 平均压力 |
| `body_battery_high` | 当日 Body Battery 最高 |
| `body_battery_low` | 当日 Body Battery 最低 |
| `body_battery_charged` | 当日 Body Battery 充电量 |
| `body_battery_drained` | 当日 Body Battery 消耗量 |

`sleep`：

| 字段 | 含义 |
|---|---|
| `start_local` | 入睡，北京时间，`YYYY-MM-DD HH:MM:SS` |
| `end_local` | 醒来，同一格式 |
| `duration_s` | 睡眠秒数 |
| `deep_s` | 深睡秒数 |
| `light_s` | 浅睡秒数 |
| `rem_s` | REM 秒数 |
| `awake_s` | 清醒秒数 |
| `awake_count` | 醒来次数 |
| `score` | 睡眠分 |
| `qualifier` | 睡眠分档，例如 `GOOD` |
| `avg_spo2` | 睡眠平均血氧 |
| `avg_respiration` | 睡眠平均呼吸 |
| `avg_stress` | 睡眠中平均压力 |
| `need_min` | 睡眠需求，分钟 |
| `body_battery_change` | 过夜 Body Battery 变化 |
| `skin_temp_c` | 皮温相对个人基线的偏差，摄氏度 |

`hrv`：

| 字段 | 含义 |
|---|---|
| `last_night_avg` | 昨夜 HRV 均值 |
| `last_night_5min_high` | 昨夜 5 分钟最高 |
| `weekly_avg` | 7 日均值 |
| `status` | 状态，例如 `BALANCED` |
| `baseline_low_upper` | 偏低区间的上沿 |
| `baseline_balanced_low` | 平衡区间下沿 |
| `baseline_balanced_upper` | 平衡区间上沿 |

`training`：

| 字段 | 含义 |
|---|---|
| `readiness` | 训练准备度分数 |
| `recovery_hours` | 恢复时间，小时 |
| `status` | 训练状态 |
| `vo2_max` | VO2 max |

`workouts` 是当天训练的短投影，按 `start_date_local` 的日期挂上，含 `tcx` / `gpx`，不限于佳明。字段与活动摘要里对应的列相同：`run_id`、`source`、`type`、`subtype`、`name`、`start_date_local`、`distance`、`moving_time`、`average_speed`、`average_heartrate`、`elevation_gain`。没有轨迹和地址。

全量活动、以后新增的活动字段，以及轨迹，仍以 `activities.ai.json` / `activities.json` 和原始文件为准。`workouts` 只回答「这一天练了什么」。活动导出之后会重新挂一遍。

## 书架和听歌

### `data/neodb/shelf.json`

```json
{
  "source": "neodb.shelf",
  "items": []
}
```

`items` 的每个元素是一条书架标记。NeoDB 合并重复目录后，旧 uuid 会跳到正式条目；档案按正式 uuid 各留一条，状态优先 `complete`，其次 `progress`，再次 `wishlist`。

常用字段：

| 字段 | 含义 |
|---|---|
| `category` | `book`、`movie`、`tv`、`music`、`game`、`podcast`、`performance` |
| `shelf_type` | `wishlist`、`progress`、`complete` |
| `created_time` | 标记时间，ISO 8601 |
| `rating_grade` | 评分 |
| `comment_text` | 短评 |
| `tags` | 标签 |
| `item` | 作品对象，含标题、封面等 |

### `data/lastfm/scrobbles.json`

```json
{
  "source": "lastfm.scrobbles",
  "user": "用户名",
  "items": []
}
```

`items` 的每个元素是一条听歌记录。歌名在 `name`。艺人名在 `artist["#text"]`，艺人 MBID 在 `artist.mbid`。专辑名在 `album["#text"]`。播放时间在 `date.uts`，是 Unix 秒数字符串。

### `data/lastfm/loved.json`

```json
{
  "source": "lastfm.loved",
  "user": "用户名",
  "items": []
}
```

`items` 的每个元素是一首红心歌曲。歌名在 `name`。艺人名在 `artist.name`。红心时间在 `date.uts`，是 Unix 秒数字符串。

### `data/lastfm/top.json`

```json
{
  "source": "lastfm.top",
  "user": "用户名",
  "artists": {},
  "albums": {},
  "tracks": {}
}
```

`artists`、`albums`、`tracks` 下面各有这些时段：

`overall`、`7day`、`1month`、`3month`、`6month`、`12month`

每个时段的值是一个数组，元素是 Last.fm 返回的艺人、专辑或歌曲对象。

### `data/listenbrainz/listens.json`

```json
{
  "source": "listenbrainz.listens",
  "user": "用户名",
  "items": []
}
```

`items` 的每个元素是一条收听记录。时间在 `listened_at`，是 Unix 秒。艺人名在 `track_metadata.artist_name`，歌名在 `track_metadata.track_name`。专辑封面相关字段在 `track_metadata.mbid_mapping`：`caa_release_mbid`、`caa_id`。

### `data/listenbrainz/top.json`

```json
{
  "source": "listenbrainz.top",
  "user": "用户名",
  "artists": {},
  "release_groups": {},
  "recordings": {}
}
```

`artists`、`release_groups`、`recordings` 下面各有这些时段：

`this_week`、`this_month`、`this_year`、`week`、`month`、`year`、`all_time`

每个时段的值是一个数组，元素是 ListenBrainz stats 返回的对象。某时段接口不可用时该数组为空。

### `data/listenbrainz/feedback.json`

```json
{
  "source": "listenbrainz.feedback",
  "user": "用户名",
  "items": []
}
```

`items` 的每个元素是一条反馈。`score` 为 `1` 表示喜欢，为 `-1` 表示不喜欢。时间在 `created`，是 Unix 秒。曲目标识在 `recording_mbid` 或 `recording_msid`。

### `data/listenbrainz/listening-activity.json`

```json
{
  "source": "listenbrainz.listening-activity",
  "user": "用户名",
  "range": "all_time",
  "listening_activity": []
}
```

`listening_activity` 的每个元素是一个时间桶。年份在 `time_range`，听歌次数在 `listen_count`，起止 Unix 秒在 `from_ts` / `to_ts`。
