#!/usr/bin/env python3
"""
全表备份 — 供 GitHub Actions 每周调用(照抄 sa-archive 模式)。

把所有表导出为 JSON(写入 backup/ 目录),workflow 打包成 artifact 保留 90 天。
民调可以重抓,但预测/研判是手工内容无法重建,这是唯一的灾备。
分页读取(每批 1000 行),不受 PostgREST 单次返回上限影响。
"""
import os
import json
import pathlib
from datetime import datetime, timezone
from supabase import create_client

SUPABASE_URL = os.environ["SUPABASE_URL"]
SUPABASE_KEY = os.environ.get("SUPABASE_SERVICE_KEY") or os.environ["SUPABASE_KEY"]
db = create_client(SUPABASE_URL, SUPABASE_KEY)

TABLES = ["polls", "analysis_posts", "predictions", "site_config"]
PAGE = 1000


def dump_table(name):
    rows = []
    offset = 0
    while True:
        try:
            batch = (db.table(name).select("*")
                     .range(offset, offset + PAGE - 1)
                     .execute().data) or []
        except Exception as e:
            print("⚠️ 跳过 %s: %s" % (name, e))
            return None
        rows.extend(batch)
        if len(batch) < PAGE:
            break
        offset += PAGE
    out = pathlib.Path("backup") / ("%s.json" % name)
    out.write_text(json.dumps(rows, ensure_ascii=False, indent=1, default=str),
                   encoding="utf-8")
    return len(rows)


def main():
    pathlib.Path("backup").mkdir(exist_ok=True)
    summary = {"backed_up_at": datetime.now(timezone.utc).isoformat(), "tables": {}}
    for tbl in TABLES:
        n = dump_table(tbl)
        if n is not None:
            summary["tables"][tbl] = n
            print("✅ %s: %d 行" % (tbl, n))
    pathlib.Path("backup/_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=1), encoding="utf-8")
    print("\n✅ 备份完成:%d 张表,共 %d 行" % (
        len(summary["tables"]), sum(summary["tables"].values())))


if __name__ == "__main__":
    main()
