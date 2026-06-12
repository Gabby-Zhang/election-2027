# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 项目是什么

给站主(Gabby)和几个朋友的**私人玩乐性质** 2027 法国大选追踪/预测站,中文 UI,部署在 Streamlit Cloud。三件事:看民调趋势、登记预测并追踪命中率(落空的预测**永不删除**,战绩文化是核心趣味)、沉淀讨论分析。设计方案在本地 `KICKOFF.md`(已 gitignore,不在仓库里)。

与 `~/Documents/GitHub/sa-archive` **共用同一个 Supabase 实例**和技术模式,但两个项目气质完全不同,不互相引流、不混内容。

## 常用命令

```bash
python3 scripts/fetch_polls.py --dry-run   # 解析维基民调,打印场景统计,不写库
python3 scripts/fetch_polls.py             # 抓取并 upsert 入库
streamlit run app.py                       # 本地起站

# 讨论成果入库(stdin JSON,格式见 docs/讨论会话接入说明.md)
python3 scripts/analysis_to_db.py <<'JSON'
{"predictions": [{"statement": "...", "author": "Gabby", "confidence": 80}]}
JSON
```

没有正式测试套件;验证页面用 Streamlit AppTest(改完页面后跑):

```python
from streamlit.testing.v1 import AppTest
import toml
at = AppTest.from_file("app.py", default_timeout=120)
for k, v in toml.load(".streamlit/secrets.toml").items():
    at.secrets[k] = v
at.run()
assert not at.exception
```

注意 AppTest 的 `selectbox.select()` 要传**原始值**(如 `"Attal × Bardella"`),不是 format_func 之后的显示文本。

## 架构

```
法文维基民调页(主源,每日 GitHub Actions)──→ Supabase polls 表 ──→ Streamlit 四页面
英文维基(仅滞后预警,不入库)                    analysis_posts / predictions / site_config
```

- **app.py** 主页:`site_config.weekly_brief` 紫色速览卡 + Plotly 趋势图(散点=原始数据,线=滚动均线,Attal 金色加粗)
- **pages/** 预测看板(命中率战绩)、研判文章(紫色=研判内容的视觉约定)、原始数据表(CSV 下载)
- **utils/db.py** 全部读写封装;读函数全部容错(表不存在返回空,站点照常打开)
- **scripts/analysis_to_db.py**:「2027大选讨论」会话经它一句话入库,接口约定在 `docs/讨论会话接入说明.md`,改 JSON 格式两边要同步

### scenario 与 scenario_group(最关键的概念)

2027 民调都是分场景测的(谁代表 EPR 参选、RN 推谁)。同一份民调在维基表里占多行,每行一个参选假设:

- `scenario` = 该行**全部参选人姓氏拼接**(精确,唯一键 `(source, poll_date, candidate, round, scenario)` 的一部分,防止同一民调不同假设互相覆盖)
- `scenario_group` = 简化分组(如 `"Attal × Bardella"`),页面下拉用;第二轮直接用对决名(如 `"Attal vs Bardella"`)

### 权限模型

所有表 RLS 开启,anon key 只读;写操作(管理表单、脚本)一律 service key。站内管理共享密码 `ADMIN_PASSWORD`,条目用 `author` 字段区分谁说的。建表/改表只能在 Supabase Dashboard SQL Editor 手动执行 `db/setup.sql`(本机无 psql/CLI,DDL 无法自动化;setup.sql 可安全重复执行)。

## 维基解析的坑(改 fetch_polls.py 前必读)

- **法语小数是逗号**:`pd.read_html` 必须传 `decimal=","`,否则 "13,5" 变 135
- **单元格带候选人替换**:如 `"33,5 Bardella"`(RN 推 Bardella)、`"7 Hollande (PS)"`,`parse_cell` 同时返回得分和候选人覆盖
- **第一轮年份在 h3 标题里**("Année 2026"),日期单元格只有 "27-28 mai";第二轮日期自带年份,场景名来自 h3("Hypothèse Attal – Bardella")
- **跨列合并单元格**会被 read_html 复制到每列,按 (候选人, 得分) 去重
- 解析少于 50 条视为页面结构变化,退出码 1 → Actions 推 ntfy(topic `ss-calendar-update`,与 sa-archive 共用)
- 改过滤/解析逻辑先 `--dry-run` 对比改动前后的场景统计再上线

## 环境约束

- **本地 Python 3.9**:不要裸用 `int | None` 注解(文件顶部加 `from __future__ import annotations`),f-string 里不要反斜杠;CI 和 Streamlit Cloud 是 3.11/3.12
- **Supabase 单次查询上限 1000 行**:全量读取分页(见 `utils/db.py` 的 `load_polls`),计数用 `count="exact"`
- 凭据读取顺序:`.streamlit/secrets.toml`(gitignore,本地)→ 环境变量(GitHub Actions secrets 同名)
- Streamlit Cloud 部署选 Python 3.12,别用 3.14(依赖轮子可能装不上);`requirements.txt` 锁上界防自动升级翻车

## 定时任务(GitHub Actions)

- `fetch_polls.yml` 每日 06:30 UTC 抓民调;失败推 ntfy
- `backup.yml` 每周一备份四张表为 artifact(保留 90 天)——预测/研判是手工内容,这是唯一灾备
