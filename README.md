# X Timeline Fetch

用 GitHub Actions 定时抓取 X 账号时间线，并以 JSON 形式累积提交回来。

## 为什么需要它

本机（或任何处于相同网络环境的机器）对 X 系列域名存在 **IP 层出口封锁**：
TCP 能建连，但 TLS 握手必超时。已排除的反爬手段：

| 尝试过的方法 | 结果 |
|---|---|
| 换 TLS 指纹（curl_cffi / chrome124 伪装） | ❌ 握手超时 |
| headless Chromium 直连 | ❌ 返回 0 字节 |
| `pbs/cdn/syndication.twimg.com`、`t.co` | ❌ 整段丢包 |
| 17 个 Nitter 公共实例 | ❌ 实例本身多已关站 |
| 代理池 + guest GraphQL | ⚠️ 偶发可用，但代理寿命以分钟计 |

而 **GitHub Runner 在美国机房，直连 x.com 正常**，所以由它负责「抓」，
本地只用 `api.github.com` 读结果 —— 该域名在任何网络下都可达。

## 仓库结构

```
.github/workflows/x_fetch.yml      # workflow：手动触发 + 每 2 小时 cron
.github/scripts/fetch_timelines.py # 抓取脚本（免登录、免 API key）
accounts.txt                       # 监控名单
data/<handle>.json                 # 累积的推文数据（自动提交）
data/_run_summary.json             # 每次运行的汇总
```

## 抓取原理

双通道自动降级，均**无需登录、无需 API key**：

1. **guest GraphQL**（主）—— X 前端自用协议，即 Nitter / twscrape 的同源实现。
   字段最全（原文、时间、赞/评/转/阅、作者），支持游标翻页。
2. **syndication SSR**（备）—— `syndication.twitter.com/srv/timeline-profile/screen-name/<h>`，
   给 X widget 用的免鉴权接口，返回内嵌 `__NEXT_DATA__` 的 HTML。

## 使用方法

### 自动跑

Actions 已配置 cron（`17 */2 * * *`），每 2 小时自动执行一次并把新数据提交回仓库。

### 手动跑

Actions 页面 → `X Timeline Fetch` → `Run workflow`，可临时覆盖账号与条数。

### 本地读取

```bash
# 读单个/多个账号（公开仓库）
python3 x_scraper.py SCMPChinese business --channel gh --repo <owner>/<repo>

# 私有仓库需要 token
GITHUB_TOKEN=xxx python3 x_scraper.py SCMPChinese --repo <owner>/<repo>
```

## 修改监控名单

编辑 `accounts.txt`，每行一个 handle，`#` 后面写备注（不参与解析）：

```
SCMPChinese           # 南早中文網
business              # Bloomberg
```

## 注意事项

- **首次运行前**：Settings → Actions → General → Workflow permissions 选
  `Read and write permissions`，否则自动提交会失败。
- 每账号数据最多保留 **500 条**，避免仓库体积无限增长。
- 数据会累积去重，重复运行不会产生新提交（工作流会显示「无新数据，跳过提交」）。
- 单个分母账号被 X 限流时会记录失败原因，不影响其他账号。
