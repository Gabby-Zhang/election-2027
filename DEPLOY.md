# 部署说明(给站主)

一共三步:建表 → 部署 app → 确认定时任务。前两步都是网页上点点点。

## 第 1 步:建 Supabase 表(只做一次)

1. 打开 [Supabase Dashboard](https://supabase.com/dashboard),进你现有的项目(和 sa-archive 同一个)
2. 左侧菜单 **SQL Editor** → **New query**
3. 把仓库里 [`db/setup.sql`](db/setup.sql) 的内容整段粘贴进去,点 **Run**
4. 看到 "Success. No rows returned" 即成功(重复执行也安全)

> 建好后在本机跑一次 `python3 scripts/fetch_polls.py` 灌入历史数据。

## 第 2 步:Streamlit Cloud 新建 app

1. 打开 [share.streamlit.io](https://share.streamlit.io),用 GitHub 账号登录
2. **New app** → 选仓库 `Gabby-Zhang/election-2027`,分支 `main`,主文件 `app.py`
3. 部署前点 **Advanced settings** → **Secrets**,粘贴(值同 sa-archive,可直接抄本机 `.streamlit/secrets.toml`):

```toml
SUPABASE_URL = "https://xacofljzjblwnzcscrbg.supabase.co"
SUPABASE_KEY = "(anon key,同 sa-archive)"
SUPABASE_SERVICE_KEY = "(service key,同 sa-archive)"
ADMIN_PASSWORD = "(本机 .streamlit/secrets.toml 里那个,或自己改一个,告诉朋友们)"
```

4. 点 **Deploy**,等几分钟就有网址了

## 第 3 步:确认 GitHub Actions

仓库 secrets 已经配好(SUPABASE_URL / SUPABASE_KEY / SUPABASE_SERVICE_KEY)。

- 每日 06:30 UTC 自动抓民调;想立即跑一次:仓库页 → **Actions** → 「每日抓取民调」→ **Run workflow**
- 失败会推 ntfy 到 `ss-calendar-update`(和 sa-archive 同一个 topic)
- 每周一自动备份数据库到 artifact(保留 90 天)

## 日常使用

- **登记预测 / 写研判 / 改速览**:网页侧边栏「管理员登录」,输入共享密码
- **从讨论会话一句话入库**:把 [docs/讨论会话接入说明.md](docs/讨论会话接入说明.md) 的内容粘贴到那个会话里
