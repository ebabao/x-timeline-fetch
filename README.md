# X Timeline Fetch

抓取指定 X 账号的**最新时间线**，按 2 小时定时运行，并把去重后的数据以 JSON 提交回仓库。

## 当前可用通道

| 通道 | 接口 | 状态 |
|---|---|---|
| **FxTwitter v2（主）** | `api.fxtwitter.com/2/profile/<handle>/statuses` | ✅ 按时间倒序返回最近 20 条，免登录、免代理，正文/时间/互动齐全 |
| guest GraphQL（备） | `x.com/i/api/graphql/<hash>/UserTweets` | ⚠️ 多数账号只返回 `profile_best_highlights`（历史精选），不能作为最新时间线 |
| syndication SSR（末备） | `syndication.twitter.com/srv/timeline-profile/screen-name/<handle>` | ❌ GitHub Runner 出口 IP 恒定 429 |

早期尝试过代理池、17 个 Nitter 实例、TLS 指纹伪装、headless Chromium、twstalker/sotwe、
Apify/TwitterAPI.io 等路径，均已在 `x_latest_report.md` 中记录结果。真正稳定的是 FxTwitter v2。

## 仓库结构

```
.github/workflows/x_fetch.yml       # 手动触发 + 每 2 小时 cron
.github/scripts/fetch_timelines.py  # 抓取脚本（免登录、免 API key）
accounts.txt                        # 监控名单
data/<handle>.json                  # 累积推文数据（自动提交）
data/_run_summary.json              # 每次运行汇总
```

## 抓取原理

`fetch()` 的降级顺序：

1. **FxTwitter v2**：直接取最新 20 条；上游偶发 404，脚本做 5 次短重试。
2. **guest GraphQL**：v2 连续失败时兜底，但结果可能是历史精选。
3. **syndication SSR**：最后兜底，GitHub IP 通常 429。

每条数据包含：`id / time / user / name / text / reply / like / rt / view / lang / media / url / src`。

## 使用方法

### 自动跑

Actions 已配置 `17 */2 * * *`，每 2 小时自动执行并提交新数据。

### 手动跑

Actions 页面 → `X Timeline Fetch` → `Run workflow`，可临时指定账号与条数。

### 本地直接取最新

```bash
# 默认自动选通道，当前会走 fxtwitter-v2
python3 /workspace/x_scraper.py cnfinancewatch fxtrader baoshu88 --limit 20

# 强制走最新通道
python3 /workspace/x_scraper.py SCMPNews business --channel fx2
```

### 读取仓库已落盘的数据

```bash
python3 /workspace/x_scraper.py cnfinancewatch --repo ebabao/x-timeline-fetch
```

私有仓库需要 `GITHUB_TOKEN` 环境变量。

## 修改监控名单

编辑 `accounts.txt`，每行一个 handle，`#` 后为备注：

```
cnfinancewatch   # 华尔街观察 Xtrader
fxtrader         # 外汇交易员
```

## 注意事项

- 每账号最多保留 **500 条**，避免仓库无限增长。
- 数据按推文 ID 去重，重复运行不会产生新提交。
- 单个账号失败会记录原因，不影响其他账号。
- `@SCMPChinese` 最后更新停留在 2016-09-09，已停更，不是抓取失败。
