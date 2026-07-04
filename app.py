import streamlit as st
st.set_page_config(page_title="CK Vina Report", page_icon="📊", layout="wide")

from db import init_db, seed_master_data, get_conn, auto_import_if_changed
import auth
import ui_config as ui
import pandas as pd
import calc_engine as ce
import periods as pm

init_db()
seed_master_data()

# Auto-import from Template/ Excel files if modified
try:
    periods_df = pm.list_periods(get_conn())
    if not periods_df.empty:
        open_period = pm.get_open_period(get_conn()) or periods_df["period"].iloc[-1]
        if auto_import_if_changed(open_period):
            print(f"Auto-imported Template changes for period {open_period}")
except Exception:
    pass  # silent fail on auto-import

# ===== LOGIN GATE (thẻ nhỏ, căn giữa) =====
auth.require_login()
user = st.session_state["user"]
ui.apply_css()

# ===== NAV: chức năng chính nằm bên trái (sidebar) =====
NAV_SECTIONS = [
    (None, [("📊", "Dashboard")]),
    ("Nhập liệu", [
        ("📋", "Tồn đầu kỳ"),
        ("🚚", "NK NVL"),
        ("♻️", "Subcon"),
        ("📨", "XK TP"),
        ("⚠️", "OUT NG"),
    ]),
    ("Quản trị", [("📅", "Quản lý kỳ")]),
    ("Báo cáo", [("📑", "Báo cáo")]),
]

if "page" not in st.session_state or st.session_state["page"] is None:
    st.session_state["page"] = "Dashboard"

# Lấy danh sách kỳ để tạo dropdown ở sidebar
_conn_for_period = get_conn()
_periods_df_all = pm.list_periods(_conn_for_period)
_conn_for_period.close()

with st.sidebar:
    st.markdown(ui.user_chip_html(user), unsafe_allow_html=True)

    st.markdown("""
        <div style="background:linear-gradient(135deg,#2f5fa8,#1a3a6b);
                    border-radius:10px;padding:6px 12px 0px;margin-bottom:2px;
                    border:1px solid rgba(255,255,255,0.25);box-shadow:0 2px 10px rgba(0,0,0,0.3);">
            <label style="color:#fff;font-weight:700;font-size:0.8rem;letter-spacing:0.5px;
                          display:block;margin-bottom:2px;text-shadow:0 1px 3px rgba(0,0,0,0.3);">
                📅 KỲ LÀM VIỆC
            </label>
    """, unsafe_allow_html=True)

    if not _periods_df_all.empty:
        _period_list = _periods_df_all["period"].tolist()
        _open_row = _periods_df_all[_periods_df_all["status"] == "open"]
        _default_p = _open_row.iloc[-1]["period"] if not _open_row.empty else _period_list[-1]
        _default_idx = _period_list.index(_default_p) if _default_p in _period_list else len(_period_list) - 1
        st.selectbox("", _period_list, index=_default_idx, key="global_period", label_visibility="collapsed")
    else:
        st.selectbox("", ["—"], key="global_period", label_visibility="collapsed")

    st.markdown("</div>", unsafe_allow_html=True)

    st.markdown("<hr/>", unsafe_allow_html=True)

    for section_title, items in NAV_SECTIONS:
        if section_title:
            ui.nav_section(section_title)
        for icon, label in items:
            active = st.session_state["page"] == label
            if st.button(label, key=f"nav_{label}", icon=icon,
                         type="primary" if active else "secondary",
                         use_container_width=True):
                st.session_state["page"] = label
                st.rerun()

    ui.sidebar_spacer()
    st.markdown('<div class="logout-row">', unsafe_allow_html=True)
    auth.logout_button()
    st.markdown('</div>', unsafe_allow_html=True)

# ===== NỘI DUNG: hiển thị full chiều rộng bên phải =====
page = st.session_state["page"]
conn = get_conn()

if page == "Dashboard":
    import modules.dashboard as mod
    mod.render(conn)

elif page == "Tồn đầu kỳ":
    import modules.data_entry as mod
    mod.render_ton_dau(conn, user)

elif page == "NK NVL":
    import modules.data_entry as mod
    mod.render_nk_nvl(conn, user)

elif page == "Subcon":
    import modules.data_entry as mod
    mod.render_subcon(conn, user)

elif page == "XK TP":
    import modules.data_entry as mod
    mod.render_xk_tp(conn, user)

elif page == "OUT NG":
    import modules.data_entry as mod
    mod.render_out_ng(conn, user)

elif page == "Quản lý kỳ":
    import modules.period_mgmt as mod
    mod.render(conn, user)

elif page == "Báo cáo":
    import modules.reports as mod
    mod.render(conn)

conn.close()