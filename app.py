"""2027 法国大选追踪站 — 主页:本周形势速览 + 民调聚合趋势图"""
import streamlit as st
import pandas as pd
import plotly.graph_objects as go

from utils.db import load_polls, get_config, set_config
from utils.auth import admin_sidebar

st.set_page_config(page_title="2027 大选观察站", page_icon="🗳️",
                   layout="wide", initial_sidebar_state="expanded")

st.markdown("""
<style>
[data-testid="stDecoration"], [data-testid="stDeployButton"],
[class*="viewerBadge"] { display: none !important; }
.brief-card {
    background: linear-gradient(135deg, #f5f0ff 0%, #ece4ff 100%);
    border-left: 5px solid #7C4DFF;
    border-radius: 10px; padding: 1rem 1.3rem; margin-bottom: 1rem;
}
.brief-card .meta { color: #7C4DFF; font-size: 0.8rem; }
</style>
""", unsafe_allow_html=True)

admin_sidebar()

st.title("🗳️ 2027 法国大选观察站")

# ── 本周形势速览(紫色 = 研判内容)────────────────────────────────────────────
brief, brief_updated = get_config("weekly_brief")
if brief:
    updated_str = ""
    if brief_updated:
        updated_str = " · 更新于 " + str(brief_updated)[:10]
    st.markdown(
        '<div class="brief-card"><div class="meta">📌 本周形势速览{}</div>'
        '<div>{}</div></div>'.format(updated_str, brief),
        unsafe_allow_html=True)

if st.session_state.get("is_admin"):
    with st.expander("✏️ 编辑本周形势速览"):
        new_brief = st.text_area("速览内容(一段话)", value=brief, height=120)
        if st.button("保存速览"):
            set_config("weekly_brief", new_brief.strip())
            st.success("已保存")
            st.rerun()

# ── 民调趋势主图 ──────────────────────────────────────────────────────────────
df = load_polls()
if df.empty:
    st.info("polls 表还没有数据,先跑 `python3 scripts/fetch_polls.py`")
    st.stop()

# 候选人配色:Attal 金色加粗高亮,其余按政治光谱
COLORS = {
    "Attal": "#D4A017", "Philippe": "#4f86c6", "Mélenchon": "#cc2443",
    "Bardella": "#0D378A", "Le Pen": "#27408B", "Retailleau": "#1f6fb2",
    "Glucksmann": "#e57373", "Tondelier": "#2e9e5b", "Roussel": "#dd0000",
    "Zemmour": "#5c4033", "Dupont-Aignan": "#104e8b", "Villepin": "#7ba7cc",
    "Arthaud": "#8b0000", "Hollande": "#f08080", "Ruffin": "#d2452d",
    "Poutou": "#b22222", "Faure": "#f4a0a0",
}
FALLBACK = ["#9e9e9e", "#80a0b0", "#b0a080", "#a080b0"]


def color_of(name):
    return COLORS.get(name, FALLBACK[hash(name) % len(FALLBACK)])


tab1, tab2 = st.tabs(["第一轮", "第二轮对决"])


def trend_chart(sub: pd.DataFrame, window: int):
    """各机构原始数据浅色散点 + 滚动平均线,Attal 金色加粗。"""
    fig = go.Figure()
    # 候选人按最近一期平均分排序,图例好读
    order = (sub.sort_values("poll_date").groupby("candidate")["score"]
             .apply(lambda s: s.tail(5).mean()).sort_values(ascending=False))
    for cand in order.index:
        cdf = sub[sub["candidate"] == cand].sort_values(["poll_date", "id"])
        color = color_of(cand)
        is_attal = cand == "Attal"
        fig.add_trace(go.Scatter(
            x=cdf["poll_date"], y=cdf["score"], mode="markers",
            marker=dict(color=color, size=7 if is_attal else 5,
                        opacity=0.45 if is_attal else 0.25),
            name=cand, legendgroup=cand, showlegend=False,
            customdata=cdf[["source"]],
            hovertemplate="%{x|%Y-%m-%d} · %{y}%<br>%{customdata[0]}<extra>" + cand + "</extra>",
        ))
        roll = cdf["score"].rolling(window, min_periods=3).mean()
        fig.add_trace(go.Scatter(
            x=cdf["poll_date"], y=roll, mode="lines",
            line=dict(color=color, width=4.5 if is_attal else 1.8),
            name=("⭐ " if is_attal else "") + cand, legendgroup=cand,
            hovertemplate="%{x|%Y-%m-%d} · 均线 %{y:.1f}%<extra>" + cand + "</extra>",
        ))
    fig.update_layout(
        height=560, hovermode="closest",
        yaxis=dict(title="意向投票 %", rangemode="tozero"),
        legend=dict(orientation="h", yanchor="bottom", y=1.02),
        margin=dict(l=10, r=10, t=10, b=10),
    )
    return fig


with tab1:
    r1 = df[df["round"] == 1]
    groups = r1["scenario_group"].value_counts()
    # 默认选数据最多的 Attal 场景
    default_idx = 0
    opts = list(groups.index)
    for i, g in enumerate(opts):
        if g.startswith("Attal ×"):
            default_idx = i
            break
    col_a, col_b = st.columns([3, 1])
    with col_a:
        group = st.selectbox(
            "场景(谁参选)", opts, index=default_idx,
            format_func=lambda g: "{}({} 条)".format(g, groups[g]))
    with col_b:
        window = st.slider("滚动平均窗口(期)", 3, 20, 8)
    sub = r1[r1["scenario_group"] == group]
    st.plotly_chart(trend_chart(sub, window), use_container_width=True)
    st.caption("浅色散点 = 各机构原始数据;实线 = 近 {} 期滚动平均。"
               "同一场景分组内可能混有细节略不同的假设(以原始数据页为准)。".format(window))

with tab2:
    r2 = df[df["round"] == 2]
    if r2.empty:
        st.info("暂无第二轮数据")
    else:
        groups2 = r2["scenario_group"].value_counts()
        duel = st.selectbox(
            "对决假设", list(groups2.index),
            format_func=lambda g: "{}({} 条)".format(g, groups2[g]))
        sub2 = r2[r2["scenario_group"] == duel]
        # 最新一期对决大数字
        latest = sub2[sub2["poll_date"] == sub2["poll_date"].max()]
        cols = st.columns(len(latest["candidate"].unique()) or 1)
        for i, (cand, cdf) in enumerate(latest.groupby("candidate")):
            with cols[i % len(cols)]:
                st.metric("{}(最新 {})".format(cand, latest["poll_date"].max().strftime("%Y-%m-%d")),
                          "{:.1f}%".format(cdf["score"].mean()))
        fig2 = trend_chart(sub2, window=5)
        fig2.add_hline(y=50, line_dash="dash", line_color="#999",
                       annotation_text="50%")
        st.plotly_chart(fig2, use_container_width=True)

st.caption("数据来源:法文维基百科民调列表页,每日自动更新 · "
           "[原始页面]({})".format(
               "https://fr.wikipedia.org/wiki/Liste_de_sondages_sur_l%27%C3%A9lection_pr%C3%A9sidentielle_fran%C3%A7aise_de_2027"))
