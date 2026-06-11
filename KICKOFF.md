# 2027 法国大选追踪与预测站 — 开工文档

> 本文档是从另一个 Claude 会话交接过来的完整设计方案。读完即可直接开工，无需向用户重新确认已有决策。

## 项目是什么

给站主（Gabby）和几个喜欢讨论法国时政的朋友做的**私人玩乐性质**的大选追踪/预测网站。核心乐趣：
1. 看民调趋势（数据自动更新，不用手动维护）
2. 登记预测并追踪命中率（"我早就说过"的快乐，以及敢于被打脸的战绩文化）
3. 沉淀平时讨论中产生的分析文章

**不是**严肃媒体产品，不追求流量。受众就是几个朋友，中文 UI。

## 与现有项目的关系

站主已有一个 `sa-archive` 项目（Streamlit + Supabase + GitHub Actions，部署在 Streamlit Cloud），本项目**完全独立建新仓库**，但：
- **复用同一个 Supabase 实例**（新建表即可），凭据在 `/Users/junruzhang/Documents/GitHub/sa-archive/.streamlit/secrets.toml`（含 `SUPABASE_URL` / `SUPABASE_KEY` / `SUPABASE_SERVICE_KEY`）
- **照抄 sa-archive 的成熟模式**（建议先读这些文件）：
  - `scripts/playbook_to_db.py` — stdin JSON → 查重 → 入库的脚本模式
  - `scripts/backup_tables.py` — 分页导出备份
  - `.github/workflows/fetch_news.yml` — 定时抓取 + 失败时 ntfy 推送（topic: `ss-calendar-update`）
  - 权限模型：所有表 RLS 开启、anon 只读、写操作一律用 service key
- GitHub 账号 `Gabby-Zhang`，`gh` CLI 已登录，可直接 `gh repo create`

另外站主 6 月 1 日做过民调爬虫实验：`/Users/junruzhang/Documents/Calendar Capture/french_polls/`（sqlite 310 条旧民调 + wikipedia/ifop/elabe/opinionway 四个爬虫雏形 + matplotlib 趋势图），二期可参考其爬虫思路，但代码重写为宜。

## 已确认的设计决策

### 数据管道（民调）

```
法文维基（每日，主源）──┐
英文维基（备用校验）  ──┼─→ Supabase polls 表 → 页面四层呈现
[二期] 机构官网爬虫    ──┤
[二期] 截图人工投喂    ──┘
```

- **主数据源（用户明确指定法文优先）**：
  https://fr.wikipedia.org/wiki/Liste_de_sondages_sur_l%27%C3%A9lection_pr%C3%A9sidentielle_fran%C3%A7aise_de_2027
- 备用：英文版 `Opinion_polling_for_the_2027_French_presidential_election`
- 用 `pandas.read_html` 解析表格；注意维基民调页有多张表：第一轮各场景、第二轮对决（Attal vs Bardella 等）
- `polls` 表结构：`source, poll_date, fieldwork_start, fieldwork_end, candidate, score, round, scenario`，唯一键 `(source, poll_date, candidate, round, scenario)`——**scenario 字段是关键**，2027 民调都是分场景测的（Attal 参选 / Philippe 参选 / 两人都上）
- GitHub Actions 每日抓一次，失败 `curl ntfy.sh/ss-calendar-update` 推送

### 页面呈现（四层，按粉丝会问的问题组织）

1. **聚合趋势主图**："Attal 现在多少？" — 各机构原始数据浅色散点 + 滚动平均线（近 N 期），Attal 金色加粗高亮，场景下拉切换（Plotly）
2. **机构对比**："哪家机构偏心？" — 每家机构相对平均线的偏差表（house effects）【二期】
3. **第二轮对决卡**："他能赢吗？" — Attal vs Bardella 等 head-to-head 大卡片【二期】
4. **原始数据表**："数据哪来的？" — 可筛选全量表 + 来源链接 + CSV 下载

**一期范围 = 管道 + 第 1 层 + 第 4 层。** 先上线再迭代。

### 研判/预测系统（本站的灵魂功能）

- `analysis_posts` 表：`date, title, body_md, tags, author, evidence`（evidence 为 jsonb，存相关新闻 URL/民调 id 的证据链）
- `predictions` 表：`statement, author, confidence(%), made_on, deadline, status(open/correct/wrong/partial), resolution_note`
- **预测看板**：进行中的预测亮黄牌，已结的标 ✓/✗，顶部显示命中率战绩；**落空的预测永不删除**——战绩文化是本站的核心趣味
- **本周形势速览**：手动更新的一段话，紫色卡片置顶
- 视觉原则：研判内容用紫色专属标识，与数据内容分开
- 写 `analysis_to_db.py`（照抄 playbook_to_db.py 模式），并产出一段**可粘贴到站主"2027大选讨论"会话的说明**，让那个会话以后能一句话把讨论成果存进库

### 多人使用

朋友几个人用，从简：管理密码共享（参考 sa-archive 的 `utils/auth.py`，注意其防爆破处理），分析/预测条目带 `author` 字段区分谁说的。不做注册系统。

### 部署

- 新 GitHub 仓库（建议名 `election-2027`，private 或 public 均可，问一下站主）
- Streamlit Cloud 新 app（站主有账号，会自己在网页上点部署，给她写清楚步骤即可）
- `requirements.txt` 锁上界（参考 sa-archive 的写法）

## 建议的开工顺序

1. `git init` + 建 GitHub 仓库
2. 建 Supabase 表（polls / analysis_posts / predictions），RLS 锁好
3. 维基爬虫 + 本地跑通入库
4. Streamlit 页面（趋势图 + 数据表 + 预测看板 + 形势速览）
5. GitHub Actions 每日抓取 + ntfy
6. analysis_to_db.py + 给讨论会话的接入说明
7. 部署说明给站主

## 注意事项

- 本地 Python 是 3.9：不要用 `int | None` 裸注解、f-string 内不要反斜杠（CI/部署端是 3.11+ 没事，但本地要能跑）
- Supabase 单次查询默认上限 1000 行，计数用 `count="exact"`，全量读取要分页
- 站主的另一个项目 sa-archive 是她记录 Séjourné & Attal 的粉丝档案馆——**两个项目气质完全不同，不要互相引流或混内容**；唯一共享的是 Supabase 实例和技术模式
