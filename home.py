"""2027 法国大选追踪站 — 主页:候选人总览大主页 + 本周速览 + 民调趋势图"""
from datetime import date

import streamlit as st
import pandas as pd
import plotly.graph_objects as go

from utils.db import (load_polls, get_config, set_config,
                      get_candidates, get_timeline_events, candidate_standings,
                      upsert_candidate, add_timeline_event)
from utils.auth import admin_sidebar

st.set_page_config(page_title="2027法国大选观察站",
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

st.title("2027法国大选观察站")

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

df = load_polls()

# ══ 候选人总览大主页 ══════════════════════════════════════════════════════════
# 按政治光谱分阵营:每个阵营一个配色,卡片 = 候选人(民调实时算 + 招牌议题)
CAMPS = [
    ("far-left",     "🔴 极左",        "#A32D2D", "#FCEBEB", "#791F1F"),
    ("center-left",  "🟠 中左",        "#993556", "#FBEAF0", "#72243E"),
    ("center-right", "🟡 中间派 / 中右", "#534AB7", "#EEEDFE", "#3C3489"),
    ("far-right",    "⚫ 极右",         "#185FA5", "#E6F1FB", "#0C447C"),
]
CAMP_ACCENT = {c[0]: c[2] for c in CAMPS}

cands = get_candidates(only_active=True)
if cands:
    standings = candidate_standings(df, [c.get("poll_name") for c in cands
                                         if c.get("poll_name")])

    def _trend_html(t):
        if t == "up":
            return '<span style="color:#1d9e75;">↑</span>'
        if t == "down":
            return '<span style="color:#e24b4a;">↓</span>'
        if t == "flat":
            return '<span style="color:#9e9e9e;">→</span>'
        return ""

    def _card(c, fill, ink):
        s = standings.get(c.get("poll_name"), {"pct": None, "trend": None})
        pct = "—" if s["pct"] is None else "{:.0f}%".format(s["pct"])
        if c.get("declared"):
            status = "已宣布" + ((" " + str(c["declared_on"])[:7]) if c.get("declared_on") else "")
        else:
            status = "潜在" if "潜在" in (c.get("party") or "") else "未宣布"
        chips = "".join(
            '<span style="font-size:11px;background:{};color:{};padding:2px 8px;'
            'border-radius:8px;">{}</span>'.format(fill, ink, i)
            for i in (c.get("issues") or []))
        note = ('<div style="margin-top:7px;font-size:11.5px;color:#6b7280;'
                'line-height:1.4;">▸ {}</div>'.format(c["note"])) if c.get("note") else ""
        bio = ('<div style="margin-top:7px;font-size:12px;color:#4b5563;'
               'line-height:1.5;">{}</div>'.format(c["bio"])) if c.get("bio") else ""
        if c.get("avatar_url"):
            avatar = ('<img src="{}" alt="{}" style="width:38px;height:38px;'
                      'border-radius:50%;object-fit:cover;object-position:top;'
                      'border:0.5px solid rgba(0,0,0,.12);flex:none;">'
                      ).format(c["avatar_url"], c["name"])
        else:
            avatar = ('<div style="width:38px;height:38px;border-radius:50%;'
                      'background:{fill};color:{ink};display:flex;align-items:center;'
                      'justify-content:center;font-size:15px;font-weight:500;flex:none;">'
                      '{ch}</div>').format(fill=fill, ink=ink, ch=c["name"][:1])
        return (
            '<div style="flex:1 1 220px;min-width:210px;background:#fff;'
            'border:0.5px solid rgba(0,0,0,.12);border-left:3px solid {accent};'
            'border-radius:12px;padding:11px 13px;">'
            '<div style="display:flex;justify-content:space-between;align-items:flex-start;gap:8px;">'
            '<div style="display:flex;gap:9px;align-items:center;min-width:0;">{avatar}'
            '<div style="min-width:0;"><div style="font-weight:500;font-size:15px;">{name}</div>'
            '<div style="font-size:12px;color:#6b7280;">{party} · {status}</div></div></div>'
            '<div style="text-align:right;white-space:nowrap;">'
            '<div style="font-size:22px;font-weight:500;line-height:1;">{pct} {trend}</div></div>'
            '</div>'
            '{bio}'
            '<div style="margin-top:8px;display:flex;flex-wrap:wrap;gap:5px;">{chips}</div>'
            '{note}</div>'
        ).format(accent=CAMP_ACCENT[c["camp"]], avatar=avatar, name=c["name"],
                 party=c.get("party") or "", status=status, pct=pct,
                 trend=_trend_html(s["trend"]), bio=bio, chips=chips, note=note)

    st.markdown("### 候选人总览")
    st.caption("按政治光谱排列 · 民调实时算自原始数据 · 细读见「📝 研判文章」按阵营筛选")
    for code, label, accent, fill, ink in CAMPS:
        group = [c for c in cands if c["camp"] == code]
        if not group:
            continue
        st.markdown(
            '<div style="display:flex;align-items:center;gap:8px;margin:14px 0 8px;">'
            '<span style="font-size:14px;font-weight:500;color:{ink};">{label}</span></div>'
            '<div style="display:flex;flex-wrap:wrap;gap:10px;">{cards}</div>'.format(
                ink=ink, label=label,
                cards="".join(_card(c, fill, ink) for c in group)),
            unsafe_allow_html=True)

    # ── 待观察大事记 ──────────────────────────────────────────────────────────
    upcoming = get_timeline_events(status="upcoming")
    if upcoming:
        rows = "".join(
            '<div style="display:flex;gap:12px;align-items:center;padding:3px 0;">'
            '<span style="font-size:12px;font-weight:500;min-width:60px;color:{color};">{date}</span>'
            '<span style="font-size:13px;">{title}</span></div>'.format(
                color=CAMP_ACCENT.get(e.get("camp"), "#534AB7"),
                date=str(e["event_date"])[5:], title=e["title"])
            for e in upcoming)
        st.markdown(
            '<div style="margin-top:18px;border-top:0.5px solid rgba(0,0,0,.12);padding-top:12px;">'
            '<div style="font-size:14px;font-weight:500;margin-bottom:8px;">⚡ Catalyst Events · 催化事件</div>'
            '{}</div>'.format(rows), unsafe_allow_html=True)

# ── 管理:候选人 / 大事记(仅管理员)─────────────────────────────────────────────
if st.session_state.get("is_admin"):
    with st.expander("⚙️ 管理候选人 / Catalyst Events"):
        cc, ce = st.columns(2)
        with cc.form("add_cand", clear_on_submit=True):
            st.markdown("**候选人(按名字 upsert)**")
            cn = st.text_input("显示名", placeholder="梅朗雄")
            pn = st.text_input("民调姓氏(=polls.candidate)", placeholder="Mélenchon")
            pty = st.text_input("党派", placeholder="LFI 不屈法国")
            cmp = st.selectbox("阵营", [c[0] for c in CAMPS],
                               format_func=lambda x: dict((c[0], c[1]) for c in CAMPS)[x])
            decl = st.checkbox("已宣布参选")
            bo = st.text_input("一句话简介(身份/政绩)", placeholder="马克龙首任总理(2017–2020)…")
            iss = st.text_input("招牌议题(逗号分隔)", placeholder="退休60岁, 媒体反垄断")
            nt = st.text_input("一行当前动态点评")
            av = st.text_input("头像 URL(可选)", placeholder="https://…jpg;留空则首字圆")
            so = st.number_input("排序(大在前)", value=50, step=10)
            if st.form_submit_button("保存候选人") and cn.strip():
                upsert_candidate({
                    "name": cn.strip(), "poll_name": pn.strip() or None,
                    "party": pty.strip() or None, "camp": cmp, "declared": decl,
                    "bio": bo.strip() or None,
                    "issues": [t.strip() for t in iss.split(",") if t.strip()],
                    "note": nt.strip() or None, "avatar_url": av.strip() or None,
                    "sort_order": int(so), "active": True})
                st.success("已保存"); st.rerun()
        with ce.form("add_event", clear_on_submit=True):
            st.markdown("**Catalyst Event**")
            ed = st.date_input("日期", value=date.today())
            et = st.text_input("事件标题", placeholder="雷塔约 · 花卉公园首场大集会")
            ecmp = st.selectbox("关联阵营", [c[0] for c in CAMPS],
                                format_func=lambda x: dict((c[0], c[1]) for c in CAMPS)[x],
                                key="ev_camp")
            edesc = st.text_input("说明(可选)")
            if st.form_submit_button("添加 Catalyst Event") and et.strip():
                add_timeline_event({
                    "event_date": ed.isoformat(), "title": et.strip(),
                    "camp": ecmp, "description": edesc.strip() or None,
                    "status": "upcoming"})
                st.success("已添加"); st.rerun()

# ══ 民调趋势主图 ══════════════════════════════════════════════════════════════
st.markdown("### 民调趋势")
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
    st.plotly_chart(trend_chart(sub, window), width="stretch")
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
        st.plotly_chart(fig2, width="stretch")

st.caption("数据来源:法文维基百科民调列表页,每日自动更新 · "
           "[原始页面]({})".format(
               "https://fr.wikipedia.org/wiki/Liste_de_sondages_sur_l%27%C3%A9lection_pr%C3%A9sidentielle_fran%C3%A7aise_de_2027"))
