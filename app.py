"""导航入口:用 st.navigation 显式定义侧边栏。
首页标题固定为「2027法国大选观察站」(无 emoji);其余三页沿用文件名推断的图标+名称。
各页面各自调用 set_page_config,故此处只做路由。"""
import streamlit as st

pages = [
    st.Page("home.py", title="2027法国大选观察站", default=True),
    st.Page("views/1_🔮_预测看板.py"),
    st.Page("views/2_📝_研判文章.py"),
    st.Page("views/3_📊_原始数据.py"),
]

st.navigation(pages).run()
