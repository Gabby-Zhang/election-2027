"""Supabase 读写封装。读用 anon key(RLS 只读),写用 service key。"""
import streamlit as st
import pandas as pd
from supabase import create_client, Client

PAGE = 1000  # PostgREST 单次返回上限,全量读取必须分页


@st.cache_resource
def get_supabase() -> Client:
    return create_client(st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_KEY"])


@st.cache_resource
def get_supabase_admin() -> Client:
    """Service Role Key,绕过 RLS,仅供管理员写操作"""
    key = st.secrets.get("SUPABASE_SERVICE_KEY", st.secrets["SUPABASE_KEY"])
    return create_client(st.secrets["SUPABASE_URL"], key)


# ── 民调 ─────────────────────────────────────────────────────────────────────
@st.cache_data(ttl=3600, show_spinner="加载民调数据…")
def load_polls() -> pd.DataFrame:
    """分页拉取全量 polls,返回 DataFrame(poll_date 转为 datetime)。"""
    db = get_supabase()
    rows = []
    offset = 0
    while True:
        batch = (db.table("polls").select("*")
                 .order("poll_date").order("id")
                 .range(offset, offset + PAGE - 1)
                 .execute().data) or []
        rows.extend(batch)
        if len(batch) < PAGE:
            break
        offset += PAGE
    df = pd.DataFrame(rows)
    if not df.empty:
        df["poll_date"] = pd.to_datetime(df["poll_date"])
        df["score"] = pd.to_numeric(df["score"])
    return df


# ── 站点配置(速览等)─────────────────────────────────────────────────────────
def get_config(key, default=""):
    db = get_supabase()
    rows = db.table("site_config").select("value,updated_at").eq("key", key).execute().data
    if rows:
        return rows[0]["value"] or default, rows[0]["updated_at"]
    return default, None


def set_config(key, value):
    from datetime import datetime, timezone
    db = get_supabase_admin()
    db.table("site_config").upsert(
        {"key": key, "value": value,
         "updated_at": datetime.now(timezone.utc).isoformat()},
        on_conflict="key").execute()


# ── 预测 ─────────────────────────────────────────────────────────────────────
def get_predictions():
    db = get_supabase()
    return (db.table("predictions").select("*")
            .order("made_on", desc=True).order("id", desc=True)
            .execute().data) or []


def add_prediction(data: dict):
    return get_supabase_admin().table("predictions").insert(data).execute()


def resolve_prediction(pid, status, note):
    from datetime import date
    return (get_supabase_admin().table("predictions")
            .update({"status": status, "resolution_note": note,
                     "resolved_on": date.today().isoformat()})
            .eq("id", pid).execute())


# ── 研判文章 ──────────────────────────────────────────────────────────────────
def get_analyses(limit=100):
    db = get_supabase()
    return (db.table("analysis_posts").select("*")
            .order("date", desc=True).order("id", desc=True)
            .limit(limit).execute().data) or []


def add_analysis(data: dict):
    return get_supabase_admin().table("analysis_posts").insert(data).execute()
