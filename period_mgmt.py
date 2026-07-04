"""modules/period_mgmt.py - Quản lý kỳ + danh mục (Admin)."""
import io
import hashlib
import streamlit as st
import pandas as pd
import periods as pm
import ui_config as ui
import auth
from db import log_action


def render(conn, user):
    auth.require_role(["admin"])
    ui.header("⚙️ Quản lý kỳ", "Mở/đóng kỳ, danh mục NVL/TP/BOM, mã mới phát sinh, User")

    tabs = st.tabs(["Kỳ báo cáo", "Mã mới phát sinh", "Danh mục NVL", "Danh mục TP", "BOM", "User", "Lịch sử hoạt động"])

    with tabs[0]:
        _render_periods(conn, user)
    with tabs[1]:
        _render_pending_codes(conn, user)
    with tabs[2]:
        _render_master_table(conn, "dm_nvl", ui.DM_NVL_LABELS, "item_code")
    with tabs[3]:
        _render_master_table(conn, "dm_tp", ui.DM_TP_LABELS, "prod_code")
    with tabs[4]:
        _render_master_table(conn, "bom", ui.BOM_LABELS, None)
    with tabs[5]:
        _render_users(conn)
    with tabs[6]:
        _render_audit_log(conn)


def _render_periods(conn, user):
    df = pm.list_periods(conn)
    st.dataframe(df, use_container_width=True, hide_index=True)

    open_period = pm.get_open_period(conn)
    if open_period:
        ui.info_bar(f"Kỳ đang mở: <b>{open_period}</b>")

    st.markdown("#### Mở kỳ mới")
    carry = st.checkbox("Tự động chuyển tồn cuối kỳ trước → tồn đầu kỳ mới", value=True)
    if st.button("➕ Mở kỳ mới", type="primary"):
        try:
            new_p = pm.open_new_period(conn, user["user_id"], carry_forward=carry)
            log_action(conn, user["user_id"], "open_period", f"Mở kỳ mới: {new_p}")
            st.success(f"✅ Đã mở kỳ mới: {new_p}")
            st.rerun()
        except Exception as e:
            st.error(f"Lỗi: {e}")

    if open_period:
        st.markdown("#### Đóng kỳ hiện tại")
        if st.button("🔒 Đóng kỳ " + open_period):
            pm.close_period(conn, open_period, user["user_id"])
            log_action(conn, user["user_id"], "close_period", f"Đóng kỳ: {open_period}")
            st.success(f"✅ Đã đóng kỳ {open_period}")
            st.rerun()


def _render_pending_codes(conn, user):
    df = pd.read_sql("SELECT * FROM pending_new_codes WHERE status='pending' ORDER BY id DESC", conn)
    if df.empty:
        st.info("Không có mã mới nào đang chờ duyệt.")
        return
    st.dataframe(df, use_container_width=True, hide_index=True)

    for _, row in df.iterrows():
        c1, c2, c3 = st.columns([3, 1, 1])
        c1.write(f"**{row['code']}** ({row['code_type']}) — nguồn: {row['source_sheet']} / kỳ {row['period']}")
        if c2.button("✅ Duyệt", key=f"approve_{row['id']}"):
            table = "dm_nvl" if row["code_type"] == "NVL" else "dm_tp"
            col = "item_code" if row["code_type"] == "NVL" else "prod_code"
            exists = pd.read_sql(f"SELECT 1 FROM {table} WHERE {col}=?", conn, params=(row["code"],))
            if exists.empty:
                if table == "dm_nvl":
                    conn.execute("INSERT INTO dm_nvl(item_code, type_code, spec, unit, don_gia) VALUES (?,?,?,?,0)",
                                 (row["code"], "", "", ""))
                else:
                    conn.execute("INSERT INTO dm_tp(prod_code, type_code, sale_code, spec, unit, remark) VALUES (?,?,?,?,?,?)",
                                 (row["code"], "", row["code"], "", "", ""))
            conn.execute("UPDATE pending_new_codes SET status='approved' WHERE id=?", (row["id"],))
            conn.commit()
            st.rerun()
        if c3.button("🚫 Bỏ qua", key=f"ignore_{row['id']}"):
            conn.execute("UPDATE pending_new_codes SET status='ignored' WHERE id=?", (row["id"],))
            conn.commit()
            st.rerun()


def _render_master_table(conn, table, labels, key_col):
    df = pd.read_sql(f"SELECT * FROM {table}", conn)

    edited = ui.data_editor_with_labels(df, labels, num_rows="dynamic",
                                        use_container_width=True, key=f"editor_{table}")

    st.markdown("""
        <style>
        div[data-testid="stFileUploader"] { padding: 0 !important; }
        div[data-testid="stFileUploader"] section { padding: 4px 8px !important; min-height: unset !important; border: 1px dashed #aaa !important; border-radius: 8px !important; }
        div[data-testid="stFileUploader"] section > div:first-child { display: none !important; }
        div[data-testid="stFileUploader"] button { font-size: 0.78rem !important; padding: 2px 12px !important; }
        div[data-testid="stFileUploader"] span { font-size: 0.7rem !important; }
        </style>
    """, unsafe_allow_html=True)

    c1, c2, c3 = st.columns(3)
    with c1:
        tpl = io.BytesIO()
        pd.DataFrame(columns=list(labels.keys())).to_excel(tpl, index=False)
        st.download_button("📥 Template", data=tpl.getvalue(),
                           file_name=f"{table}_template.xlsx",
                           mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                           key=f"tpl_{table}", use_container_width=True)
    with c2:
        uploaded = st.file_uploader("", type=["xlsx", "csv"],
                                    key=f"upload_{table}", label_visibility="collapsed")
    with c3:
        if st.button("💾 Lưu thay đổi", key=f"save_{table}", use_container_width=True):
            edited.to_sql(table, conn, if_exists="replace", index=False)
            conn.commit()
            st.success("✅ Đã lưu.")
            st.rerun()

    if uploaded:
        try:
            if uploaded.name.endswith(".csv"):
                new_df = pd.read_csv(uploaded, dtype=str, encoding="utf-8-sig", sep=None, engine="python")
            else:
                new_df = pd.read_excel(uploaded, dtype=str)
            new_df.columns = [c.strip().lower().replace(" ", "_") for c in new_df.columns]
            new_df = new_df.dropna(how="all")
            if not new_df.empty:
                st.dataframe(new_df, use_container_width=True, height=200, hide_index=True)
                if st.button("💾 Ghi vào danh mục", type="primary", key=f"save_upload_{table}"):
                    new_df.to_sql(table, conn, if_exists="append", index=False)
                    conn.commit()
                    st.success(f"✅ Đã thêm {len(new_df)} dòng.")
                    st.rerun()
        except Exception as e:
            st.error(f"Lỗi: {e}")


def _render_audit_log(conn):
    st.markdown("#### Lịch sử hoạt động")
    search = st.text_input("Tìm kiếm", placeholder="Nhập user, hành động...", key="audit_search")
    df = pd.read_sql("SELECT * FROM audit_log ORDER BY id DESC LIMIT 500", conn)
    if df.empty:
        st.info("Chưa có dữ liệu.")
        return
    if search:
        mask = df.astype(str).apply(lambda x: x.str.contains(search, case=False, na=False)).any(axis=1)
        df = df[mask]
    st.dataframe(df, use_container_width=True, height=500, hide_index=True)


def _render_users(conn):
    df = pd.read_sql("SELECT * FROM users", conn)
    safe_cols = [c for c in df.columns if c != "password"]
    display_labels = {k: v for k, v in ui.USERS_LABELS.items() if k != "password"}

    c_left, c_right = st.columns([3, 2])
    with c_left:
        st.markdown("**Danh sách User**")
        edited = ui.data_editor_with_labels(df[safe_cols], display_labels, num_rows="dynamic",
                                            use_container_width=True, key="editor_users")
        if st.button("💾 Lưu thay đổi User"):
            edited.to_sql("users", conn, if_exists="replace", index=False)
            conn.commit()
            st.success("✅ Đã lưu.")
            st.rerun()

    with c_right:
        st.markdown("**🔑 Đặt/đổi mật khẩu**")
        sel_user = st.selectbox("Chọn User", df["user_id"].tolist() if not df.empty else [],
                                key="pwd_user")
        new_pwd = st.text_input("Mật khẩu mới", type="password", key="pwd_new")
        confirm = st.text_input("Xác nhận mật khẩu", type="password", key="pwd_confirm")
        if st.button("Cập nhật mật khẩu", type="primary"):
            if not new_pwd:
                st.error("Vui lòng nhập mật khẩu.")
            elif new_pwd != confirm:
                st.error("Mật khẩu xác nhận không khớp.")
            else:
                hashed = hashlib.sha256(new_pwd.encode()).hexdigest()
                conn.execute("UPDATE users SET password = ? WHERE user_id = ?", (hashed, sel_user))
                conn.commit()
                st.success(f"✅ Đã cập nhật mật khẩu cho {sel_user}.")
                st.rerun()
