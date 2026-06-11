"""研判文章:平时讨论沉淀下来的分析,紫色 = 研判内容专属标识。"""
import json
import streamlit as st
from datetime import date

from utils.db import get_analyses, add_analysis
from utils.auth import admin_sidebar

st.set_page_config(page_title="研判文章", page_icon="📝", layout="wide")
admin_sidebar()

st.markdown("""
<style>
.tag { background: #ece4ff; color: #5e35b1; border-radius: 12px;
       padding: 0.1rem 0.6rem; font-size: 0.75rem; margin-right: 0.3rem; }
</style>
""", unsafe_allow_html=True)

st.title("📝 研判文章")
st.caption("🟣 讨论中沉淀的分析与判断 — 与数据页分开,观点归观点,数据归数据")

posts = get_analyses()

# 标签筛选
all_tags = sorted({t for p in posts for t in (p.get("tags") or [])})
sel_tags = st.multiselect("按标签筛选", all_tags) if all_tags else []
if sel_tags:
    posts = [p for p in posts if set(p.get("tags") or []) & set(sel_tags)]

if not posts:
    st.info("还没有研判文章。管理员登录后可在下方添加,或在讨论会话里一句话入库。")

for p in posts:
    tags_html = "".join('<span class="tag">{}</span>'.format(t)
                        for t in (p.get("tags") or []))
    with st.expander("**{}** · {} · {}".format(p["title"], p["date"], p["author"]),
                     expanded=False):
        if tags_html:
            st.markdown(tags_html, unsafe_allow_html=True)
        st.markdown(p["body_md"])
        ev = p.get("evidence") or []
        if isinstance(ev, str):
            try:
                ev = json.loads(ev)
            except ValueError:
                ev = []
        if ev:
            st.markdown("**证据链:**")
            for e in ev:
                if isinstance(e, dict):
                    label = e.get("note") or e.get("value", "")
                    if e.get("type") == "url":
                        st.markdown("- [{}]({})".format(label, e["value"]))
                    else:
                        st.markdown("- {}: {}".format(e.get("type", "ref"), label))
                else:
                    st.markdown("- {}".format(e))

# ── 管理操作 ──────────────────────────────────────────────────────────────────
if st.session_state.get("is_admin"):
    st.divider()
    with st.form("add_post", clear_on_submit=True):
        st.markdown("**➕ 新研判**")
        title = st.text_input("标题")
        body = st.text_area("正文(Markdown)", height=200)
        col1, col2, col3 = st.columns(3)
        author = col1.text_input("作者", value="Gabby")
        tags_str = col2.text_input("标签(逗号分隔)", placeholder="民调, Attal")
        post_date = col3.date_input("日期", value=date.today())
        evidence_str = st.text_area("证据链接(每行一条 URL,可选)", height=80)
        if st.form_submit_button("发布") and title.strip() and body.strip():
            evidence = [{"type": "url", "value": u.strip()}
                        for u in evidence_str.splitlines() if u.strip()]
            add_analysis({
                "title": title.strip(), "body_md": body, "author": author.strip() or "匿名",
                "tags": [t.strip() for t in tags_str.split(",") if t.strip()],
                "date": post_date.isoformat(), "evidence": evidence,
            })
            st.rerun()
