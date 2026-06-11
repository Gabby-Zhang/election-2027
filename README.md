# 🗳️ 2027 法国大选观察站

给站主和朋友们的私人玩乐项目:看民调趋势、登记预测、沉淀讨论分析。中文 UI。

## 页面

| 页面 | 内容 |
|---|---|
| 🗳️ 主页 | 本周形势速览(紫色卡片)+ 民调聚合趋势图(第一轮场景切换 / 第二轮对决) |
| 🔮 预测看板 | 进行中的预测亮黄牌,已结标 ✓/✗,顶部命中率战绩;落空的预测永不删除 |
| 📝 研判文章 | 平时讨论沉淀的分析,带标签和证据链 |
| 📊 原始数据 | 可筛选全量民调表 + CSV 下载 |

## 数据管道

```
法文维基(每日,主源)──┐
英文维基(滞后预警)  ──┴─→ Supabase polls 表 → 页面呈现
```

- 主源:[法文维基民调列表页](https://fr.wikipedia.org/wiki/Liste_de_sondages_sur_l%27%C3%A9lection_pr%C3%A9sidentielle_fran%C3%A7aise_de_2027)
- GitHub Actions 每日 06:30 UTC 抓取([fetch_polls.yml](.github/workflows/fetch_polls.yml)),失败推 ntfy(topic `ss-calendar-update`)
- 每周一自动备份全部表为 artifact([backup.yml](.github/workflows/backup.yml))

## 本地开发

```bash
pip install -r requirements.txt
# .streamlit/secrets.toml 需包含:
#   SUPABASE_URL / SUPABASE_KEY / SUPABASE_SERVICE_KEY / ADMIN_PASSWORD

python3 scripts/fetch_polls.py --dry-run   # 只解析不入库
python3 scripts/fetch_polls.py             # 抓取入库
streamlit run app.py
```

## 脚本

- `scripts/fetch_polls.py` — 维基民调爬虫 + 入库(scenario 精确场景 / scenario_group 简化分组)
- `scripts/analysis_to_db.py` — stdin JSON → 研判/预测/结案/速览入库,见 [docs/讨论会话接入说明.md](docs/讨论会话接入说明.md)
- `scripts/backup_tables.py` — 分页导出全部表
- `db/setup.sql` — 建表 + RLS(在 Supabase SQL Editor 执行一次)

## 权限模型

所有表 RLS 开启,anon key 只读;写操作(站内管理表单、脚本)一律走 service key。
站内管理操作用共享密码(`ADMIN_PASSWORD`),条目带 `author` 字段区分谁说的。

部署步骤见 [DEPLOY.md](DEPLOY.md)。
