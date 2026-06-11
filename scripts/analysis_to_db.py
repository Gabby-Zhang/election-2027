#!/usr/bin/env python3
"""
讨论成果 → Supabase(研判文章 / 预测 / 结案 / 本周速览)

通过 stdin 接收结构化 JSON:
  {
    "brief": "本周形势一段话(可选,覆盖站点速览卡)",
    "analyses": [
      {
        "title": "Attal 民调企稳的三个信号",
        "body_md": "正文,Markdown…",
        "author": "Gabby",
        "date": "2026-06-11",            # 可选,默认今天
        "tags": ["民调", "Attal"],        # 可选
        "evidence": [                      # 可选,证据链
          {"type": "url", "value": "https://…", "note": "Ipsos 5月报告"}
        ]
      }
    ],
    "predictions": [
      {
        "statement": "Attal 会在 9 月前正式宣布参选",
        "author": "Gabby",
        "confidence": 80,
        "deadline": "2026-09-01"          # 可选
      }
    ],
    "resolutions": [                       # 给已有预测结案
      {"id": 3, "status": "correct", "resolution_note": "6月10日官宣"}
    ]
  }

查重:analyses 按 (date, title),predictions 按 (statement, author),重复跳过。
凭据:.streamlit/secrets.toml 优先,其次环境变量。
"""
from __future__ import annotations

import os
import sys
import json
import pathlib
from datetime import date, datetime, timezone


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


def insert_analyses(db, items):
    if not items:
        return 0
    existing = {(r["date"], r["title"])
                for r in (db.table("analysis_posts").select("date,title")
                          .execute().data or [])}
    n = 0
    for it in items:
        d = it.get("date") or date.today().isoformat()
        title = (it.get("title") or "").strip()
        if not title or not it.get("body_md"):
            print("   ⚠️  跳过缺标题/正文的研判", file=sys.stderr)
            continue
        if (d, title) in existing:
            print("   ↩️  已存在,跳过: %s" % title[:50])
            continue
        db.table("analysis_posts").insert({
            "date": d, "title": title, "body_md": it["body_md"],
            "author": it.get("author", "匿名"),
            "tags": it.get("tags") or [],
            "evidence": it.get("evidence") or [],
        }).execute()
        existing.add((d, title))
        n += 1
        print("   ✅ 研判: %s" % title[:60])
    return n


def insert_predictions(db, items):
    if not items:
        return 0
    existing = {(r["statement"], r["author"])
                for r in (db.table("predictions").select("statement,author")
                          .execute().data or [])}
    n = 0
    for it in items:
        stmt = (it.get("statement") or "").strip()
        if not stmt:
            continue
        author = it.get("author", "匿名")
        if (stmt, author) in existing:
            print("   ↩️  已存在,跳过: %s" % stmt[:50])
            continue
        db.table("predictions").insert({
            "statement": stmt, "author": author,
            "confidence": it.get("confidence"),
            "made_on": it.get("made_on") or date.today().isoformat(),
            "deadline": it.get("deadline"),
        }).execute()
        existing.add((stmt, author))
        n += 1
        print("   ✅ 预测: %s" % stmt[:60])
    return n


def resolve_predictions(db, items):
    n = 0
    for it in items or []:
        pid = it.get("id")
        status = it.get("status")
        if not pid or status not in ("correct", "wrong", "partial"):
            print("   ⚠️  结案条目缺 id 或 status 不合法: %s" % it, file=sys.stderr)
            continue
        db.table("predictions").update({
            "status": status,
            "resolution_note": it.get("resolution_note", ""),
            "resolved_on": date.today().isoformat(),
        }).eq("id", pid).execute()
        n += 1
        print("   ⚖️  预测 #%s 结案: %s" % (pid, status))
    return n


def main():
    raw = sys.stdin.read().strip()
    if not raw:
        print("stdin 没有输入", file=sys.stderr)
        sys.exit(1)
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as e:
        print("JSON 不合法: %s" % e, file=sys.stderr)
        sys.exit(1)

    db = load_db()
    a = insert_analyses(db, data.get("analyses"))
    p = insert_predictions(db, data.get("predictions"))
    r = resolve_predictions(db, data.get("resolutions"))

    brief = (data.get("brief") or "").strip()
    if brief:
        db.table("site_config").upsert({
            "key": "weekly_brief", "value": brief,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }, on_conflict="key").execute()
        print("   📌 已更新本周形势速览")

    print("\n✅ 完成 — %d 研判 / %d 预测 / %d 结案%s" % (
        a, p, r, " / 速览已更新" if brief else ""))


if __name__ == "__main__":
    main()
