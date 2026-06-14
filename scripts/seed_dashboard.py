#!/usr/bin/env python3
"""
首页总览大主页种子数据 → Supabase(candidates / timeline_events)

按政治光谱录入热门+潜在候选人花名册,以及待观察大事记。
candidates 按 name upsert(可重复执行,改这里再跑一次即可覆盖);
timeline_events 按 (event_date, title) 查重插入,不重复。

凭据:.streamlit/secrets.toml 优先,其次环境变量(与 analysis_to_db.py 一致)。
依赖 db/setup.sql 已在 Supabase 建好 candidates / timeline_events 两张表。
"""
from __future__ import annotations

import os
import sys
import pathlib


def load_db():
    secrets_path = pathlib.Path(__file__).parent.parent / ".streamlit" / "secrets.toml"
    url = key = ""
    if secrets_path.exists():
        try:
            import toml
            s = toml.load(str(secrets_path))
            url = s.get("SUPABASE_URL", "")
            key = s.get("SUPABASE_SERVICE_KEY") or s.get("SUPABASE_KEY", "")
        except Exception as e:
            print("⚠️  读取 secrets.toml 失败: %s" % e, file=sys.stderr)
    if not (url and key):
        url = os.environ.get("SUPABASE_URL", "")
        key = os.environ.get("SUPABASE_SERVICE_KEY") or os.environ.get("SUPABASE_KEY", "")
    if not (url and key):
        raise RuntimeError("找不到 Supabase 凭据")
    from supabase import create_client
    return create_client(url, key)


# ── 候选人花名册(sort_order 大在前)──────────────────────────────────────────
CANDIDATES = [
    # 🔴 极左
    {"name": "梅朗雄", "poll_name": "Mélenchon", "party": "LFI 不屈法国",
     "camp": "far-left", "declared": True, "declared_on": "2026-05-03",
     "issues": ["SMIC 1700€", "退休60岁", "媒体反垄断", "第六共和国"],
     "note": "圣但尼集会2.6万人,左翼天然旗手", "sort_order": 100,
     "avatar_url": "https://upload.wikimedia.org/wikipedia/commons/thumb/f/f5/Portrait_officiel_JLM_20-01-2026.jpg/330px-Portrait_officiel_JLM_20-01-2026.jpg"},

    # 🟠 中左
    {"name": "格鲁克斯曼", "poll_name": "Glucksmann", "party": "Place Publique 社民",
     "camp": "center-left", "declared": False, "declared_on": None,
     "issues": ["亲欧亲乌", "主权三绳索", "打败极右"],
     "note": "未宣布,给自己三个月窗口;6/13 集会追平梅朗雄", "sort_order": 90,
     "avatar_url": "https://upload.wikimedia.org/wikipedia/commons/thumb/1/1f/1720448398743_20240708_GLUCKSMANN_Raphael_FR_006.jpg/330px-1720448398743_20240708_GLUCKSMANN_Raphael_FR_006.jpg"},

    # 🟡 中间派 / 中右
    {"name": "菲利普", "poll_name": "Philippe", "party": "Horizons 地平线",
     "camp": "center-right", "declared": True, "declared_on": "2026-03-01",
     "issues": ["三次全民公投", "养老金积累制", "立法权下放"],
     "note": "数字城案缠身,基本盘两月跌6点", "sort_order": 80,
     "avatar_url": "https://upload.wikimedia.org/wikipedia/commons/thumb/a/a3/Edouard_Philippe_3x4_crop.jpg/330px-Edouard_Philippe_3x4_crop.jpg"},
    {"name": "阿塔尔", "poll_name": "Attal", "party": "Renaissance 复兴党",
     "camp": "center-right", "declared": True, "declared_on": "2026-05-22",
     "issues": ["AI教育", "移民配额", "四支柱", "俄乌强硬"],
     "note": "与马克龙无切割,同场遇菲利普跌至9%", "sort_order": 70,
     "avatar_url": "https://upload.wikimedia.org/wikipedia/commons/thumb/c/c4/Gabriel_Attal_2025_%28close_crop%29.jpg/330px-Gabriel_Attal_2025_%28close_crop%29.jpg"},
    {"name": "雷塔约", "poll_name": "Retailleau", "party": "LR 共和党",
     "camp": "center-right", "declared": True, "declared_on": "2026-04-19",
     "issues": ["移民回返条例", "治安强硬"],
     "note": "现任内政部长,以官职行竞选;6/20 首场集会", "sort_order": 60,
     "avatar_url": "https://upload.wikimedia.org/wikipedia/commons/thumb/6/61/Bruno_Retailleau_-_Ministre_de_l%27Int%C3%A9rieur_fran%C3%A7ais_%28cropped%29.jpg/330px-Bruno_Retailleau_-_Ministre_de_l%27Int%C3%A9rieur_fran%C3%A7ais_%28cropped%29.jpg"},
    {"name": "卡斯泰", "poll_name": "Castex", "party": "复兴系(潜在)",
     "camp": "center-right", "declared": False, "declared_on": None,
     "issues": ["接地气技术官僚", "无司法问题"],
     "note": "潜在变量,或11月宣布;若菲利普垮台可接盘", "sort_order": 50,
     "avatar_url": "https://upload.wikimedia.org/wikipedia/commons/thumb/9/99/Castex_Matignon.jpg/330px-Castex_Matignon.jpg"},

    # ⚫ 极右
    {"name": "巴德拉", "poll_name": "Bardella", "party": "RN 国民联盟",
     "camp": "far-right", "declared": True, "declared_on": None,
     "issues": ["增值税降至5.5%", "驱逐外籍罪犯", "福利法国人优先"],
     "note": "稳居第一33%,待7/7勒庞裁决定接棒", "sort_order": 100,
     "avatar_url": "https://upload.wikimedia.org/wikipedia/commons/thumb/1/13/MEP_Jordan_Bardella.jpg/330px-MEP_Jordan_Bardella.jpg"},
    {"name": "勒庞", "poll_name": "Le Pen", "party": "RN 国民联盟(潜在)",
     "camp": "far-right", "declared": False, "declared_on": None,
     "issues": ["移民/认同", "法国人优先"],
     "note": "被判5年禁选,7/7上诉裁决决定能否参选", "sort_order": 90,
     "avatar_url": "https://upload.wikimedia.org/wikipedia/commons/thumb/8/81/Marine_Le_Pen_2025_%28cropped%29.jpg/330px-Marine_Le_Pen_2025_%28cropped%29.jpg"},
]

# ── Catalyst Events 催化事件(待观察) ────────────────────────────────────────
TIMELINE = [
    {"event_date": "2026-06-13", "title": "格鲁克斯曼 · 奥贝维利耶首场集会",
     "candidate": "格鲁克斯曼", "camp": "center-left", "status": "past",
     "description": "发令枪式集会,Gagner en 2027,民调追平梅朗雄"},
    {"event_date": "2026-06-20", "title": "雷塔约 · 花卉公园首场大集会",
     "candidate": "雷塔约", "camp": "center-right", "status": "upcoming",
     "description": "检验他能否把党内胜利转化为全国动能"},
    {"event_date": "2026-06-25", "title": "菲利普 · 同步1000场公寓会议",
     "candidate": "菲利普", "camp": "center-right", "status": "upcoming",
     "description": "地平线党基层渗透策略,看是否兑现"},
    {"event_date": "2026-07-05", "title": "菲利普 · 阿迪达斯球馆启动大会",
     "candidate": "菲利普", "camp": "center-right", "status": "upcoming",
     "description": "约9000人场馆;若坐不满恐重演佩克雷斯半空场"},
    {"event_date": "2026-07-07", "title": "勒庞上诉裁决 · 决定RN由谁出战",
     "candidate": "勒庞", "camp": "far-right", "status": "upcoming",
     "description": "维持禁选则巴德拉接棒;接下来一个月最具决定性的单一事件"},
]


def seed_candidates(db):
    n = 0
    for c in CANDIDATES:
        db.table("candidates").upsert(c, on_conflict="name").execute()
        n += 1
        print("   ✅ 候选人: %s (%s)" % (c["name"], c["camp"]))
    return n


def seed_timeline(db):
    existing = {(r["event_date"], r["title"])
                for r in (db.table("timeline_events")
                          .select("event_date,title").execute().data or [])}
    n = 0
    for e in TIMELINE:
        if (e["event_date"], e["title"]) in existing:
            print("   ↩️  大事记已存在,跳过: %s" % e["title"])
            continue
        db.table("timeline_events").insert(e).execute()
        existing.add((e["event_date"], e["title"]))
        n += 1
        print("   📅 大事记: %s %s" % (e["event_date"], e["title"]))
    return n


def main():
    db = load_db()
    c = seed_candidates(db)
    t = seed_timeline(db)
    print("\n✅ 完成 — %d 候选人 upsert / %d 大事记新增" % (c, t))


if __name__ == "__main__":
    main()
