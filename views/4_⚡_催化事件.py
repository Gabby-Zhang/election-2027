"""催化事件 Catalyst Events:可能改写选情的关键节点时间线。
待观察(upcoming)按日期升序排在前,已发生(past)按日期降序排在后;可按阵营筛选。
管理员可在站内增删/改状态(沿用首页同一套 add_timeline_event / update_timeline_event)。"""
from datetime import date

import streamlit as st

from utils.db import (get_timeline_events, add_timeline_event,
                      update_timeline_event)
from utils.auth import admin_sidebar

st.set_page_config(page_title="催化事件", page_icon="⚡", layout="wide")
admin_sidebar()

# 阵营配色(与首页一致)
CAMPS = [
    ("far-left",     "🔴 极左",        "#A32D2D", "#FCEBEB", "#791F1F"),
    ("center-left",  "🟠 中左",        "#993556", "#FBEAF0", "#72243E"),
    ("center-right", "🟡 中间派 / 中右", "#534AB7", "#EEEDFE", "#3C3489"),
    ("far-right",    "⚫ 极右",         "#185FA5", "#E6F1FB", "#0C447C"),
]
CAMP_LABEL = {c[0]: c[1] for c in CAMPS}
CAMP_ACCENT = {c[0]: c[2] for c in CAMPS}

st.title("⚡ 催化事件 · Catalyst Events")
st.caption("可能改写选情的关键节点 — 集会、司法裁决、宣布参选;⚪ 待观察在前,已发生按时间倒序")

events = get_timeline_events()

# ── 按阵营筛选 ───────────────────────────────────────────────────────────────
camps_present = [c for c in CAMPS if any(e.get("camp") == c[0] for e in events)]
sel = st.multiselect(
    "按阵营筛选", [c[0] for c in camps_present],
    format_func=lambda x: CAMP_LABEL.get(x, x))
if sel:
    events = [e for e in events if e.get("camp") in sel]


def _event_card(e):
    accent = CAMP_ACCENT.get(e.get("camp"), "#534AB7")
    camp = CAMP_LABEL.get(e.get("camp"), "")
    desc = ('<div style="margin-top:6px;font-size:13px;color:#4b5563;'
            'line-height:1.55;">{}</div>'.format(e["description"])
            ) if e.get("description") else ""
    return (
        '<div style="background:#fff;border:0.5px solid rgba(0,0,0,.12);'
        'border-left:3px solid {accent};border-radius:12px;'
        'padding:11px 14px;margin-bottom:10px;">'
        '<div style="display:flex;justify-content:space-between;align-items:baseline;gap:10px;">'
        '<div style="font-weight:500;font-size:15px;">{title}</div>'
        '<div style="font-size:12px;color:{accent};white-space:nowrap;">{date} · {camp}</div>'
        '</div>{desc}</div>'
    ).format(accent=accent, title=e["title"], date=str(e["event_date"]),
             camp=camp, desc=desc)


upcoming = [e for e in events if e.get("status") == "upcoming"]
past = [e for e in events if e.get("status") != "upcoming"]
upcoming.sort(key=lambda e: str(e["event_date"]))
past.sort(key=lambda e: str(e["event_date"]), reverse=True)

st.markdown("### ⚪ 待观察")
if upcoming:
    st.markdown("".join(_event_card(e) for e in upcoming), unsafe_allow_html=True)
else:
    st.caption("暂无待观察事件")

st.markdown("### ✅ 已发生")
if past:
    st.markdown("".join(_event_card(e) for e in past), unsafe_allow_html=True)
else:
    st.caption("暂无已发生记录")

# ── 管理:增删 / 改状态(仅管理员)───────────────────────────────────────────────
if st.session_state.get("is_admin"):
    with st.expander("⚙️ 管理催化事件"):
        with st.form("add_event_pg", clear_on_submit=True):
            st.markdown("**新增催化事件**")
            ed = st.date_input("日期", value=date.today())
            et = st.text_input("事件标题", placeholder="雷塔约 · 花卉公园首场大集会")
            ecmp = st.selectbox("关联阵营", [c[0] for c in CAMPS],
                                format_func=lambda x: CAMP_LABEL[x])
            est = st.selectbox("状态", ["upcoming", "past"],
                               format_func=lambda x: "待观察" if x == "upcoming" else "已发生")
            edesc = st.text_area("说明(可选)", height=80)
            if st.form_submit_button("添加") and et.strip():
                add_timeline_event({
                    "event_date": ed.isoformat(), "title": et.strip(),
                    "camp": ecmp, "description": edesc.strip() or None,
                    "status": est})
                st.success("已添加"); st.rerun()

        if events:
            st.markdown("**改状态 / 说明**")
            opt = {"{}  {}".format(str(e["event_date"]), e["title"]): e for e in
                   sorted(events, key=lambda e: str(e["event_date"]), reverse=True)}
            pick = st.selectbox("选择事件", list(opt.keys()), key="edit_pick")
            ev = opt[pick]
            new_status = st.selectbox(
                "状态", ["upcoming", "past"],
                index=0 if ev.get("status") == "upcoming" else 1,
                format_func=lambda x: "待观察" if x == "upcoming" else "已发生",
                key="edit_status")
            new_desc = st.text_area("说明", value=ev.get("description") or "",
                                    height=80, key="edit_desc")
            if st.button("保存修改"):
                update_timeline_event(
                    ev["id"], {"status": new_status,
                               "description": new_desc.strip() or None})
                st.success("已更新"); st.rerun()
