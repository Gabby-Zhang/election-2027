#!/usr/bin/env python3
"""
法文维基 2027 总统大选民调 → Supabase polls 表

主源:法文维基 Liste de sondages sur l'élection présidentielle française de 2027
备用校验:英文维基 Opinion polling(只比对最新民调日期,不入库)

页面结构(2026-06 现状):
  - 第一轮:按年份分表(h3 = "Année 2026" 等),多级表头,候选人在第二级;
    同一民调多行 = 不同参选场景(谁代表 EPR、RN 推谁等),
    单元格里可能带候选人替换,如 "33,5 Bardella"、"7 Hollande (PS)"
  - 第二轮:按对决假设分表(h3 = "Hypothèse Attal – Bardella" 等),
    两列候选人,日期含年份

scenario 字段 = 该行全部参选人姓氏拼接(精确、可作唯一键的一部分);
scenario_group = 简化分组(如 "Attal × Bardella"),供页面下拉筛选。

用法:
  python3 scripts/fetch_polls.py            # 抓取并入库
  python3 scripts/fetch_polls.py --dry-run  # 只解析打印,不写库

凭据:.streamlit/secrets.toml 优先,其次环境变量(GitHub Actions)。
退出码:0 正常;1 解析失败;42 入库成功但英文维基比法文新 10 天以上(主源疑似滞后)。
"""
from __future__ import annotations

import io
import re
import os
import sys
import pathlib
import argparse
from datetime import date, timedelta

import requests
import pandas as pd
from bs4 import BeautifulSoup

FR_URL = ("https://fr.wikipedia.org/wiki/"
          "Liste_de_sondages_sur_l%27%C3%A9lection_pr%C3%A9sidentielle_"
          "fran%C3%A7aise_de_2027")
EN_URL = ("https://en.wikipedia.org/wiki/"
          "Opinion_polling_for_the_2027_French_presidential_election")
UA = {"User-Agent": "Mozilla/5.0 (election-2027 tracker; private hobby project)"}

MONTHS_FR = {
    "janvier": 1, "fevrier": 2, "février": 2, "mars": 3, "avril": 4,
    "mai": 5, "juin": 6, "juillet": 7, "aout": 8, "août": 8,
    "septembre": 9, "octobre": 10, "novembre": 11, "decembre": 12, "décembre": 12,
}
MONTHS_EN = {
    "january": 1, "february": 2, "march": 3, "april": 4, "may": 5, "june": 6,
    "july": 7, "august": 8, "september": 9, "october": 10,
    "november": 11, "december": 12,
}


# ── 凭据 ─────────────────────────────────────────────────────────────────────
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
        raise RuntimeError("找不到 Supabase 凭据(secrets.toml 或环境变量)")
    from supabase import create_client
    return create_client(url, key)


# ── 文本清洗 ──────────────────────────────────────────────────────────────────
def clean(s):
    """去维基脚注 [c]/[1],归一化空白与各种横线。"""
    s = str(s)
    s = re.sub(r"\[[^\]]{1,6}\]", "", s)
    s = s.replace(" ", " ").replace(" ", " ").replace(" ", " ")
    s = re.sub(r"[–—‒‑]", "-", s)
    return re.sub(r"\s+", " ", s).strip()


def parse_header_candidate(h):
    """表头 'Attal[c] (RE)' → ('Attal', 'RE');'Candidat RN' → ('Candidat RN', None)"""
    h = clean(h)
    m = re.match(r"^(.+?)\s*\(([^)]+)\)\s*$", h)
    if m:
        return m.group(1).strip(), m.group(2).strip()
    return h, None


# ── 日期解析 ──────────────────────────────────────────────────────────────────
def _parse_side(tok, ref_month, ref_year):
    """'28'、'28 février'、'2 mars 2026' → (day, month, year),缺省继承 ref。"""
    tok = tok.strip().replace("1er", "1")
    m = re.match(r"^(\d{1,2})(?:\s*([a-zà-ÿ]+))?(?:\s*(\d{4}))?$", tok)
    if not m:
        return None
    day = int(m.group(1))
    month = MONTHS_FR.get(m.group(2)) if m.group(2) else ref_month
    year = int(m.group(3)) if m.group(3) else ref_year
    if not (month and year):
        return None
    try:
        return date(year, month, day)
    except ValueError:
        return None


def parse_date_range(text, default_year):
    """'27-28 mai' / '26 - 28 mai 2026' / '28 février - 2 mars 2026' / '3 mai'
    → (fieldwork_start, fieldwork_end);解析失败返回 (None, None)。"""
    t = clean(text).lower()
    t = re.sub(r"^du\s+", "", t).replace(" au ", "-").replace(" et ", "-")
    parts = [p for p in t.split("-") if p.strip()]
    if not parts:
        return None, None
    # 先解析最右侧(信息最全),左侧继承月/年
    right = _parse_side(parts[-1], None, default_year)
    if right is None:
        return None, None
    if len(parts) == 1:
        return right, right
    left = _parse_side(parts[0], right.month, right.year)
    if left is None:
        return right, right
    if left > right:  # 跨年,如 30 décembre - 2 janvier
        try:
            left = left.replace(year=left.year - 1)
        except ValueError:
            return right, right
    return left, right


# ── 单元格解析 ────────────────────────────────────────────────────────────────
def parse_cell(cell):
    """得分单元格 → (score, 候选人覆盖, 政党覆盖) 或 None(未参选)。
    形如:14 / 8.5 / '33,5 Bardella' / '7 Hollande (PS)' / '—'"""
    if cell is None or (isinstance(cell, float) and pd.isna(cell)):
        return None
    if isinstance(cell, (int, float)):
        score = float(cell)
        return (score, None, None) if 0 <= score <= 100 else None
    s = clean(cell).replace(",", ".")
    if s in ("", "-", "—", "?", "nan"):
        return None
    m = re.match(r"^(\d{1,2}(?:\.\d+)?)\s*(.*)$", s)
    if not m:
        return None
    score = float(m.group(1))
    if not (0 <= score <= 100):
        return None
    rest = m.group(2).strip()
    if not rest:
        return score, None, None
    m2 = re.match(r"^(.+?)\s*\(([^)]+)\)\s*$", rest)
    if m2:
        return score, m2.group(1).strip(), m2.group(2).strip()
    return score, rest, None


def scenario_group_of(candidates, round_):
    """从该行参选人列表推出简化场景分组,如 'Attal × Bardella'。"""
    names = [c for c, _ in candidates]
    if round_ == 2:
        return " vs ".join(names[:2])
    has_attal = "Attal" in names
    has_philippe = "Philippe" in names
    if has_attal and has_philippe:
        epr = "Attal+Philippe"
    elif has_attal:
        epr = "Attal"
    elif has_philippe:
        epr = "Philippe"
    else:
        epr = "EPR未定"
    if "Bardella" in names:
        rn = "Bardella"
    elif "Le Pen" in names:
        rn = "Le Pen"
    else:
        rn = "RN未定"
    return "%s × %s" % (epr, rn)


# ── 表格解析 ──────────────────────────────────────────────────────────────────
def parse_table(table_html, round_, default_year=None, scenario_fixed=None):
    """解析一张 wikitable,返回 polls 行列表。"""
    try:
        df = pd.read_html(io.StringIO(table_html), decimal=",", thousands=" ")[0]
    except ValueError:
        return []
    # 多级表头取候选人所在层(含人名的那一级)
    if isinstance(df.columns, pd.MultiIndex):
        levels = [df.columns.get_level_values(i) for i in range(df.columns.nlevels)]
        best = max(levels, key=lambda lv: sum(
            1 for v in lv if re.search(r"\(", str(v)) or "Candidat" in str(v)))
        df.columns = [clean(c) for c in best]
    else:
        df.columns = [clean(c) for c in df.columns]

    cols = list(df.columns)
    meta_idx = {}
    for i, c in enumerate(cols):
        lc = c.lower()
        if lc.startswith("sondeur"):
            meta_idx["source"] = i
        elif lc.startswith("date"):
            meta_idx["date"] = i
        elif lc.startswith("échantillon") or lc.startswith("echantillon"):
            meta_idx["sample"] = i
    if "source" not in meta_idx or "date" not in meta_idx:
        return []

    cand_cols = []
    for i, c in enumerate(cols):
        if i in meta_idx.values():
            continue
        if c.lower().startswith(("autre", "abstention", "unnamed", "blanc", "ne se prononce")):
            continue
        name, party = parse_header_candidate(c)
        if name:
            cand_cols.append((i, name, party))

    rows = []
    for _, r in df.iterrows():
        source = clean(r.iloc[meta_idx["source"]])
        if not source or source.lower() in ("nan", "sondeur"):
            continue
        fw_start, fw_end = parse_date_range(r.iloc[meta_idx["date"]], default_year)
        if fw_end is None:
            continue
        sample = None
        if "sample" in meta_idx:
            digits = re.sub(r"\D", "", str(r.iloc[meta_idx["sample"]]))
            if digits and len(digits) <= 6:
                sample = int(digits)

        # 收集该行全部 (候选人, 政党, 得分),colspan 重复的去掉
        cands = []
        seen = set()
        for i, hname, hparty in cand_cols:
            parsed = parse_cell(r.iloc[i])
            if parsed is None:
                continue
            score, oname, oparty = parsed
            name = oname or hname
            party = oparty or hparty
            key = (name, score)
            if key in seen:
                continue  # 跨列合并的同一单元格
            seen.add(key)
            cands.append(((name, party), score))

        if not cands:
            continue
        cand_list = [c for c, _ in cands]
        scenario = scenario_fixed or " / ".join(n for n, _ in cand_list)
        group = scenario_fixed or scenario_group_of(cand_list, round_)
        for (name, party), score in cands:
            rows.append({
                "source": source,
                "poll_date": fw_end.isoformat(),
                "fieldwork_start": fw_start.isoformat() if fw_start else None,
                "fieldwork_end": fw_end.isoformat(),
                "sample_size": sample,
                "candidate": name,
                "party": party,
                "score": score,
                "round": round_,
                "scenario": scenario,
                "scenario_group": group,
                "source_url": FR_URL,
            })
    return rows


def scrape_french():
    """抓取法文维基整页,返回 polls 行列表。"""
    html = requests.get(FR_URL, headers=UA, timeout=60).text
    soup = BeautifulSoup(html, "html.parser")
    all_rows = []
    for tbl in soup.select("table.wikitable"):
        h2 = h3 = ""
        for prev in tbl.find_all_previous(["h2", "h3"]):
            if prev.name == "h3" and not h3:
                h3 = clean(prev.get_text(" ", strip=True))
            if prev.name == "h2":
                h2 = clean(prev.get_text(" ", strip=True))
                break
        h2l = h2.lower()
        if "premier tour" in h2l:
            m = re.search(r"(20\d\d)", h3)
            year = int(m.group(1)) if m else None
            all_rows += parse_table(str(tbl), 1, default_year=year)
        elif "second tour" in h2l:
            scenario = re.sub(r"^hypothèse\s+", "", h3, flags=re.I).strip()
            scenario = re.sub(r"\s*[–—-]\s*", " vs ", clean(scenario))
            if not scenario:
                continue
            m = re.search(r"(20\d\d)", h3)
            all_rows += parse_table(str(tbl), 2, default_year=None,
                                    scenario_fixed=scenario)
    return all_rows


# ── 英文维基备用校验 ───────────────────────────────────────────────────────────
def latest_english_date():
    """英文页面正则扫日期,返回最新一条民调日期(粗略,仅作滞后预警)。"""
    try:
        html = requests.get(EN_URL, headers=UA, timeout=60).text
    except Exception:
        return None
    text = clean(BeautifulSoup(html, "html.parser").get_text(" "))
    best = None
    pat = r"(\d{1,2})\s+(%s)\s+(20\d\d)" % "|".join(m.capitalize() for m in MONTHS_EN)
    for m in re.finditer(pat, text):
        try:
            d = date(int(m.group(3)), MONTHS_EN[m.group(2).lower()], int(m.group(1)))
        except ValueError:
            continue
        if d <= date.today() and (best is None or d > best):
            best = d
    return best


# ── 入库 ─────────────────────────────────────────────────────────────────────
def upsert_polls(db, rows):
    """批量 upsert,唯一键 (source, poll_date, candidate, round, scenario)。"""
    BATCH = 500
    total = 0
    for i in range(0, len(rows), BATCH):
        batch = rows[i:i + BATCH]
        # 同批内按唯一键去重(同场景同人重复行取最后一条)
        uniq = {}
        for r in batch:
            uniq[(r["source"], r["poll_date"], r["candidate"],
                  r["round"], r["scenario"])] = r
        db.table("polls").upsert(
            list(uniq.values()),
            on_conflict="source,poll_date,candidate,round,scenario",
        ).execute()
        total += len(uniq)
    return total


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true", help="只解析不入库")
    args = ap.parse_args()

    rows = scrape_french()
    n_r1 = sum(1 for r in rows if r["round"] == 1)
    n_r2 = sum(1 for r in rows if r["round"] == 2)
    print("解析到 %d 条得分记录(第一轮 %d / 第二轮 %d)" % (len(rows), n_r1, n_r2))
    if len(rows) < 50:
        print("❌ 解析结果异常偏少,页面结构可能变了", file=sys.stderr)
        sys.exit(1)

    fr_latest = max(r["poll_date"] for r in rows)
    print("法文维基最新民调日期: %s" % fr_latest)

    if args.dry_run:
        import json
        groups = {}
        for r in rows:
            groups[r["scenario_group"]] = groups.get(r["scenario_group"], 0) + 1
        print("\n场景分组统计:")
        for g, n in sorted(groups.items(), key=lambda kv: -kv[1]):
            print("  %4d  %s" % (n, g))
        print("\n样例记录:")
        print(json.dumps(rows[:3], ensure_ascii=False, indent=2))
        return

    db = load_db()
    total = upsert_polls(db, rows)
    print("✅ 已 upsert %d 条记录到 polls 表" % total)

    en_latest = latest_english_date()
    if en_latest:
        print("英文维基最新民调日期(粗略): %s" % en_latest)
        if (en_latest - date.fromisoformat(fr_latest)).days > 10:
            print("⚠️  英文维基比法文新 10 天以上,法文主源可能滞后,请人工检查",
                  file=sys.stderr)
            sys.exit(42)


if __name__ == "__main__":
    main()
