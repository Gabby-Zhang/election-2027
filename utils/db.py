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
    """分页拉取全量 polls,返回 DataFrame(poll_date 转为 datetime)。
    表还没建时返回空表,站点照常打开。"""
    db = get_supabase()
    rows = []
    offset = 0
    while True:
        try:
            batch = (db.table("polls").select("*")
                     .order("poll_date").order("id")
                     .range(offset, offset + PAGE - 1)
                     .execute().data) or []
        except Exception:
            break
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
    try:
        rows = db.table("site_config").select("value,updated_at").eq("key", key).execute().data
    except Exception:
        rows = []
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
    try:
        return (db.table("predictions").select("*")
                .order("made_on", desc=True).order("id", desc=True)
                .execute().data) or []
    except Exception:
        return []


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
    try:
        return (db.table("analysis_posts").select("*")
                .order("date", desc=True).order("id", desc=True)
                .limit(limit).execute().data) or []
    except Exception:
        return []


def add_analysis(data: dict):
    return get_supabase_admin().table("analysis_posts").insert(data).execute()


# ── 候选人档案(首页总览)──────────────────────────────────────────────────────
def get_candidates(only_active=True):
    db = get_supabase()
    try:
        q = db.table("candidates").select("*").order("sort_order", desc=True)
        rows = q.execute().data or []
    except Exception:
        return []
    if only_active:
        rows = [r for r in rows if r.get("active", True)]
    return rows


def upsert_candidate(data: dict):
    """按 name 唯一键 upsert,站内表单与 seed 脚本共用。"""
    return (get_supabase_admin().table("candidates")
            .upsert(data, on_conflict="name").execute())


# ── 大事记时间线 ──────────────────────────────────────────────────────────────
def get_timeline_events(status=None):
    db = get_supabase()
    try:
        q = db.table("timeline_events").select("*").order("event_date")
        rows = q.execute().data or []
    except Exception:
        return []
    if status:
        rows = [r for r in rows if r.get("status") == status]
    return rows


def add_timeline_event(data: dict):
    return get_supabase_admin().table("timeline_events").insert(data).execute()


def update_timeline_event(eid, fields: dict):
    return (get_supabase_admin().table("timeline_events")
            .update(fields).eq("id", eid).execute())


# ── 民调换算:每位候选人最新意向票 + 趋势 ─────────────────────────────────────
def candidate_standings(df, poll_names):
    """从 polls DataFrame 给每个 poll_name 算「最新一期均值 + 近一月趋势」。
    第一轮、跨场景平均(粗口径,够首页一目了然用);返回 {poll_name: {pct, trend}}。
    trend ∈ {"up","down","flat",None}。"""
    import pandas as pd
    out = {}
    if df is None or df.empty:
        return {n: {"pct": None, "trend": None} for n in poll_names}
    r1 = df[df["round"] == 1]
    for name in poll_names:
        d = r1[r1["candidate"] == name]
        if d.empty:
            out[name] = {"pct": None, "trend": None}
            continue
        latest = d["poll_date"].max()
        pct = float(d[d["poll_date"] == latest]["score"].mean())
        trend = None
        prior_win = d[(d["poll_date"] < latest - pd.Timedelta(days=20))
                      & (d["poll_date"] >= latest - pd.Timedelta(days=55))]
        if not prior_win.empty:
            prev = float(prior_win["score"].mean())
            if pct - prev >= 0.7:
                trend = "up"
            elif prev - pct >= 0.7:
                trend = "down"
            else:
                trend = "flat"
        out[name] = {"pct": pct, "trend": trend}
    return out
