"""预测看板:进行中亮黄牌,已结标 ✓/✗,顶部命中率战绩。落空的预测永不删除。"""
import streamlit as st
from datetime import date

from utils.db import get_predictions, add_prediction, resolve_prediction
from utils.auth import admin_sidebar

st.set_page_config(page_title="预测看板", page_icon="🔮", layout="wide")
admin_sidebar()

st.markdown("""
<style>
.pred-card { border-radius: 10px; padding: 0.9rem 1.1rem; margin-bottom: 0.7rem; }
.pred-open    { background: #fffbe6; border-left: 5px solid #e6c200; }
.pred-correct { background: #e8f5e9; border-left: 5px solid #43a047; }
.pred-wrong   { background: #ffebee; border-left: 5px solid #e53935; }
.pred-partial { background: #fff3e0; border-left: 5px solid #fb8c00; }
.pred-card .meta { color: #777; font-size: 0.8rem; margin-top: 0.3rem; }
.pred-card .note { color: #555; font-size: 0.85rem; margin-top: 0.3rem; font-style: italic; }
</style>
""", unsafe_allow_html=True)

st.title("🔮 预测看板")

preds = get_predictions()
resolved = [p for p in preds if p["status"] != "open"]
correct = [p for p in preds if p["status"] == "correct"]
partial = [p for p in preds if p["status"] == "partial"]
open_ = [p for p in preds if p["status"] == "open"]

# ── 战绩 ─────────────────────────────────────────────────────────────────────
c1, c2, c3, c4 = st.columns(4)
c1.metric("进行中", len(open_))
c2.metric("已验证", len(resolved))
c3.metric("命中", "{} ✓".format(len(correct)))
if resolved:
    rate = (len(correct) + 0.5 * len(partial)) / len(resolved) * 100
    c4.metric("命中率", "{:.0f}%".format(rate))
else:
    c4.metric("命中率", "—")

STATUS_META = {
    "open":    ("open",    "🟡 进行中"),
    "correct": ("correct", "✓ 命中"),
    "wrong":   ("wrong",   "✗ 落空"),
    "partial": ("partial", "◐ 部分命中"),
}


def card(p):
    cls, label = STATUS_META[p["status"]]
    meta = "{} · {} · 信心 {}%".format(p["author"], p["made_on"], p["confidence"] or "?")
    if p.get("deadline"):
        meta += " · 截止 {}".format(p["deadline"])
    if p["status"] != "open" and p.get("resolved_on"):
        meta += " · 结案 {}".format(p["resolved_on"])
    note = ""
    if p.get("resolution_note"):
        note = '<div class="note">📝 {}</div>'.format(p["resolution_note"])
    st.markdown(
        '<div class="pred-card pred-{}"><b>{}</b>&nbsp;&nbsp;{}'
        '<div class="meta">{}</div>{}</div>'.format(
            cls, label, p["statement"], meta, note),
        unsafe_allow_html=True)


st.subheader("进行中")
if open_:
    for p in open_:
        card(p)
else:
    st.caption("暂无进行中的预测,敢说就来登记一条")

st.subheader("历史战绩(永久存档)")
if resolved:
    for p in resolved:
        card(p)
else:
    st.caption("还没有已验证的预测")

# ── 管理操作 ──────────────────────────────────────────────────────────────────
if st.session_state.get("is_admin"):
    st.divider()
    col1, col2 = st.columns(2)
    with col1:
        with st.form("add_pred", clear_on_submit=True):
            st.markdown("**➕ 登记新预测**")
            statement = st.text_area("预测内容(一句话,可被验证)")
            author = st.text_input("谁说的", value="Gabby")
            confidence = st.slider("信心 %", 5, 100, 70, step=5)
            deadline = st.date_input("验证截止日(可选)", value=None)
            if st.form_submit_button("登记") and statement.strip():
                add_prediction({
                    "statement": statement.strip(), "author": author.strip() or "匿名",
                    "confidence": confidence, "made_on": date.today().isoformat(),
                    "deadline": deadline.isoformat() if deadline else None,
                })
                st.rerun()
    with col2:
        if open_:
            with st.form("resolve_pred"):
                st.markdown("**⚖️ 结案**")
                target = st.selectbox(
                    "选择预测", open_,
                    format_func=lambda p: "#{} {}".format(p["id"], p["statement"][:40]))
                status = st.radio("结果", ["correct", "wrong", "partial"],
                                  format_func=lambda s: STATUS_META[s][1], horizontal=True)
                note = st.text_input("结案说明(发生了什么)")
                if st.form_submit_button("结案"):
                    resolve_prediction(target["id"], status, note.strip())
                    st.rerun()
