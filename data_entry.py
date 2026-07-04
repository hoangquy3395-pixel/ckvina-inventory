"""modules/data_entry.py - Nhập liệu theo từng nghiệp vụ (PIC), theo kỳ đang mở."""
import streamlit as st
import pandas as pd
import calc_engine as ce
import ui_config as ui
import periods as pm
import auth


# Cột (không gồm id/period - period được gán tự động theo kỳ đang mở)
COLS = {
    "end_stock_nvl": ["item_code", "qty_begin", "subcon", "type", "level_subcon", "remark"],
    "end_stock_tp": ["prod_code", "sale_code", "qty_begin", "subcon", "level_subcon", "remark"],
    "end_stock_full_sub": ["prod_code", "sale_code", "qty_begin", "subcon", "level_subcon", "remark"],
    "nk_nvl_in_cds": ["so_to_khai", "ngay_tk", "ma_loai_hinh", "so_hoa_don", "item_code",
                      "ten_hang", "dvt", "type", "qty_input", "ngay_giao_hang", "qty_return", "remark"],
    "nk_nvl_in_actual": ["ngay_nhap_kho", "sub_code", "item_code", "type", "qty_actual",
                         "qty_return", "ghi_chu"],
    "subcon_out": ["ngay", "prod_code", "sale_code", "item_code", "type", "stock_in",
                   "level_subcon", "trans_type", "qty", "remark"],
    "subcon_in": ["ngay", "hs_code", "prod_code", "sale_code", "item_code", "stock_out",
                  "trans_type", "qty", "level_subcon", "remark"],
    "xk_tp_out_cds": ["so_to_khai", "ngay_tk", "ma_loai_hinh", "so_hoa_don", "hs_code",
                      "prod_code", "sale_code", "dvt", "qty_sale", "ngay_giao_hang",
                      "qty_return", "remark"],
    "xk_tp_out_actual": ["ngay_nhap_kho", "ma_hs", "prod_code", "sale_code", "actual_qty", "ghi_chu"],
    "out_ng": ["ngay", "hs_code", "prod_code", "sale_code", "item_code", "stock_out_in",
               "request_kind", "trans_type", "qty", "remark"],
}


def _select_period(conn):
    """Lấy kỳ làm việc từ sidebar (global_period)."""
    all_periods = pm.list_periods(conn)
    if all_periods.empty:
        st.warning("⚠️ Chưa có kỳ nào trong hệ thống. Vào **Quản lý kỳ** để mở kỳ đầu tiên.")
        st.stop()
    period = st.session_state.get("global_period")
    if period not in all_periods["period"].values:
        period = all_periods["period"].iloc[-1]
    return period


def _new_code_warning(conn, period):
    try:
        warn = ce.check_new_codes(conn, period)
    except Exception:
        return
    if not warn.empty:
        with st.expander(f"⚠️ {len(warn)} mã phát sinh chưa có trong danh mục — cần Admin duyệt", expanded=False):
            st.dataframe(warn, use_container_width=True, hide_index=True)


def render_ton_dau(conn, user):
    auth.require_role(["admin", "pic"])
    period = _select_period(conn)
    ui.header("📦 Tồn đầu kỳ")

    t1, t2, t3 = st.tabs(["NVL", "TP", "FULL SUB"])
    with t1:
        ui.render_upload_sheet("end_stock_nvl", COLS["end_stock_nvl"], period, conn, user,
                               "Tồn đầu kỳ NVL", "Tồn đầu kỳ nguyên vật liệu")
    with t2:
        ui.render_upload_sheet("end_stock_tp", COLS["end_stock_tp"], period, conn, user,
                               "Tồn đầu kỳ TP", "Tồn đầu kỳ thành phẩm")
    with t3:
        ui.render_upload_sheet("end_stock_full_sub", COLS["end_stock_full_sub"], period, conn, user,
                               "Tồn đầu kỳ FULL SUB", "Tồn đầu kỳ gia công đồng bộ (Full Subcon)")


def render_nk_nvl(conn, user):
    auth.require_role(["admin", "pic"])
    period = _select_period(conn)
    ui.header("📥 NK NVL")
    _new_code_warning(conn, period)

    t1, t2 = st.tabs(["Tờ khai (CDS)", "Thực tế nhập kho"])
    with t1:
        ui.render_upload_sheet("nk_nvl_in_cds", COLS["nk_nvl_in_cds"], period, conn, user,
                               "NK NVL - Tờ khai", "Nhập khẩu NVL theo tờ khai hải quan")
    with t2:
        ui.render_upload_sheet("nk_nvl_in_actual", COLS["nk_nvl_in_actual"], period, conn, user,
                               "NK NVL - Thực tế", "Nhập kho NVL thực tế")


def render_subcon(conn, user):
    auth.require_role(["admin", "pic"])
    period = _select_period(conn)
    ui.header("🔄 Subcon")
    _new_code_warning(conn, period)

    t1, t2 = st.tabs(["Xuất Subcon (OUT)", "Nhập Subcon (IN)"])
    with t1:
        ui.render_upload_sheet("subcon_out", COLS["subcon_out"], period, conn, user,
                               "Subcon OUT", "Giao NVL/bán thành phẩm cho gia công")
    with t2:
        ui.render_upload_sheet("subcon_in", COLS["subcon_in"], period, conn, user,
                               "Subcon IN", "Nhận lại thành phẩm/bán thành phẩm từ gia công")


def render_xk_tp(conn, user):
    auth.require_role(["admin", "pic"])
    period = _select_period(conn)
    ui.header("📤 XK TP")
    _new_code_warning(conn, period)

    t1, t2 = st.tabs(["Tờ khai (CDS)", "Thực tế xuất kho"])
    with t1:
        ui.render_upload_sheet("xk_tp_out_cds", COLS["xk_tp_out_cds"], period, conn, user,
                               "XK TP - Tờ khai", "Xuất khẩu thành phẩm theo tờ khai hải quan")
    with t2:
        ui.render_upload_sheet("xk_tp_out_actual", COLS["xk_tp_out_actual"], period, conn, user,
                               "XK TP - Thực tế", "Xuất kho thành phẩm thực tế")


def render_out_ng(conn, user):
    auth.require_role(["admin", "pic"])
    period = _select_period(conn)
    ui.header("⚠️ OUT NG")
    _new_code_warning(conn, period)

    ui.render_upload_sheet("out_ng", COLS["out_ng"], period, conn, user,
                           "OUT NG", "Xuất/nhập khác: hàng lỗi (NG), phế liệu, điều chỉnh, thay thế")
