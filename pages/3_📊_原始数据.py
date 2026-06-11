"""原始数据表:可筛选全量民调 + 来源链接 + CSV 下载。"""
import streamlit as st

from utils.db import load_polls
from utils.auth import admin_sidebar

st.set_page_config(page_title="原始数据", page_icon="📊", layout="wide")
admin_sidebar()

st.title("📊 原始民调数据")

df = load_polls()
if df.empty:
    st.info("polls 表还没有数据")
    st.stop()

col1, col2, col3, col4 = st.columns(4)
with col1:
    round_sel = st.selectbox("轮次", ["全部", "第一轮", "第二轮"])
with col2:
    sources = ["全部"] + sorted(df["source"].unique())
    source_sel = st.selectbox("机构", sources)
with col3:
    cands = ["全部"] + sorted(df["candidate"].unique())
    cand_sel = st.selectbox("候选人", cands)
with col4:
    groups = ["全部"] + list(df["scenario_group"].value_counts().index)
    group_sel = st.selectbox("场景分组", groups)

sub = df
if round_sel != "全部":
    sub = sub[sub["round"] == (1 if round_sel == "第一轮" else 2)]
if source_sel != "全部":
    sub = sub[sub["source"] == source_sel]
if cand_sel != "全部":
    sub = sub[sub["candidate"] == cand_sel]
if group_sel != "全部":
    sub = sub[sub["scenario_group"] == group_sel]

date_min, date_max = df["poll_date"].min().date(), df["poll_date"].max().date()
dr = st.slider("日期范围", date_min, date_max, (date_min, date_max))
sub = sub[(sub["poll_date"].dt.date >= dr[0]) & (sub["poll_date"].dt.date <= dr[1])]

st.caption("{} 条记录 · 数据来自[法文维基百科民调列表页]({}),每日自动同步".format(
    len(sub), sub["source_url"].iloc[0] if not sub.empty else "#"))

show = sub.sort_values(["poll_date", "id"], ascending=False)[
    ["poll_date", "source", "round", "candidate", "party", "score",
     "scenario_group", "scenario", "sample_size", "fieldwork_start", "fieldwork_end"]]
st.dataframe(
    show, use_container_width=True, height=560, hide_index=True,
    column_config={
        "poll_date": st.column_config.DateColumn("日期", format="YYYY-MM-DD"),
        "source": "机构", "round": "轮次", "candidate": "候选人", "party": "政党",
        "score": st.column_config.NumberColumn("得分 %", format="%.1f"),
        "scenario_group": "场景分组", "scenario": "精确场景(参选人)",
        "sample_size": "样本量", "fieldwork_start": "调查开始", "fieldwork_end": "调查结束",
    })

st.download_button(
    "⬇️ 下载当前筛选结果 CSV",
    show.to_csv(index=False).encode("utf-8-sig"),
    file_name="polls_2027.csv", mime="text/csv")
