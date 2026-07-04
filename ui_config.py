import streamlit as st
import pandas as pd
import numpy as np
import io
from typing import Optional
from db import sync_to_excel

APP_CSS = """
<style>
    * { font-family: 'Inter', 'Segoe UI', 'Tahoma', sans-serif !important; }
    html, body, [data-testid="stAppViewContainer"] { background: #f4f6fa !important; }
    [data-testid="stHeader"] { background: transparent !important; }
    .block-container { padding-top: 1.4rem !important; max-width: 100% !important; }

    .login-page {
        position: fixed; top: 0; left: 0; right: 0; bottom: 0;
        background:
            radial-gradient(circle at 15% 15%, rgba(26,58,107,0.10), transparent 40%),
            radial-gradient(circle at 85% 85%, rgba(198,40,40,0.06), transparent 40%),
            #eef1f6;
        display: flex; align-items: center; justify-content: center; z-index: 9999;
    }
    .login-card {
        background: #ffffff; border-radius: 18px; padding: 1.9rem 2.1rem 1.6rem;
        width: 336px; max-width: 90vw;
        box-shadow: 0 20px 50px -12px rgba(10,22,40,0.22), 0 2px 8px rgba(10,22,40,0.06);
        border: 2px solid #1a3a6b;
    }
    .login-logo-badge {
        width: 46px; height: 46px; border-radius: 13px; margin: 0 auto 0.8rem;
        background: linear-gradient(135deg, #0a1628 0%, #1a3a6b 60%, #2f5fa8 100%);
        display: flex; align-items: center; justify-content: center;
        color: #fff; font-weight: 800; font-size: 1.1rem; letter-spacing: 0.5px;
        box-shadow: 0 8px 18px rgba(10,22,40,0.25);
    }
    .login-card h2 { text-align: center; color: #0a1628; margin: 0 0 0.1rem 0; font-weight: 800; font-size: 1.2rem; letter-spacing: 0.2px; }
    .login-card .login-sub { text-align: center; color: #8a95a8; margin: 0 0 1.2rem 0; font-size: 0.76rem; }
    .login-card .login-error { background: #fdecea; color: #c62828; padding: 0.5rem 0.8rem; border-radius: 9px; font-size: 0.76rem; margin-bottom: 0.9rem; text-align: center; font-weight: 500; border: 1px solid #f6cccc; }
    .login-card .login-footer { text-align: center; color: #b2bac9; font-size: 0.68rem; margin-top: 1.1rem; }
    .login-forgot { text-align: right; margin: 0.2rem auto 0.2rem; max-width: 280px; }
    .login-forgot a { font-size: 0.72rem; color: #1a3a6b; text-decoration: none; font-weight: 500; }
    .login-forgot a:hover { text-decoration: underline; }

    .login-card [data-testid="stTextInput"] { max-width: 280px !important; margin: 0 auto !important; }
    .login-card [data-testid="stTextInput"] label { font-weight: 600 !important; color: #24324a !important; font-size: 0.78rem !important; }
    .login-card [data-testid="stTextInput"] input { border-radius: 9px !important; border: 1.5px solid #e4e8f0 !important; padding: 0.5rem 0.7rem !important; background: #f9fafc !important; font-size: 0.86rem !important; }
    .login-card [data-testid="stTextInput"] input:focus { border-color: #1a3a6b !important; background: #fff !important; box-shadow: 0 0 0 3px rgba(26,58,107,0.12) !important; }
    .login-card [data-testid="stTextInput"] input::placeholder { color: #b6bdcb !important; }
    .login-card .stButton { max-width: 280px !important; margin: 0 auto !important; }
    .login-card .stButton button { border-radius: 9px !important; padding: 0.55rem 0.8rem !important; font-weight: 700 !important; font-size: 0.84rem !important; letter-spacing: 0.2px; }
    .login-card .stButton button[kind="primary"] { background: linear-gradient(135deg, #0a1628, #1a3a6b) !important; border: none !important; box-shadow: 0 8px 16px rgba(10,22,40,0.25); width: 100%; margin-top: 0.2rem; }
    .login-card .stButton button[kind="primary"]:hover { filter: brightness(1.12); }
    .login-card [data-testid="column"]:nth-of-type(2) .stButton button { padding: 0.45rem 0 !important; background: #f4f6fa !important; color: #5c6579 !important; border: 1.5px solid #e4e8f0 !important; font-weight: 500 !important; width: 100%; box-shadow: none !important; min-width: 40px !important; }
    .login-card [data-testid="column"]:nth-of-type(2) .stButton button:hover { background: #eef1f6 !important; }
    .login-card [data-testid="stCheckbox"] { max-width: 280px !important; margin: 0 auto !important; }
    .login-card [data-testid="stCheckbox"] label p { font-size: 0.76rem !important; color: #5c6579 !important; }

    section[data-testid="stSidebar"] { background: linear-gradient(180deg, #0a1628 0%, #0d2038 100%) !important; min-width: 258px !important; max-width: 258px !important; }
    section[data-testid="stSidebar"] > div { padding: 1rem 0.9rem !important; }
    section[data-testid="stSidebar"] .brand { margin-bottom: 0.9rem; }
    section[data-testid="stSidebar"] .brand .brand-text h1 { color: #fff !important; }
    section[data-testid="stSidebar"] .brand .brand-text p { color: rgba(255,255,255,0.45) !important; }
    section[data-testid="stSidebar"] .brand .badge-logo { box-shadow: 0 6px 14px rgba(0,0,0,0.35); }
    section[data-testid="stSidebar"] .user-chip { background: rgba(255,255,255,0.05); border: 1px solid rgba(255,255,255,0.08); border-radius: 12px; padding: 0.55rem 0.7rem; margin-bottom: 0.6rem; }
    section[data-testid="stSidebar"] .user-chip .avatar { background: rgba(255,255,255,0.12); color: #fff; }
    section[data-testid="stSidebar"] .user-chip .who .name { color: #fff; }
    section[data-testid="stSidebar"] .user-chip .role-badge { color: #ffffff !important; font-size: 0.7rem; opacity: 0.85; }

    /* ── Period chip (Kỳ làm việc) ── */
    section[data-testid="stSidebar"] .period-chip {
        display: flex; align-items: center; gap: 9px;
        background: rgba(255,255,255,0.04);
        border: 1px solid rgba(255,255,255,0.08);
        border-radius: 12px; padding: 0.5rem 0.7rem; margin-bottom: 0.75rem;
    }
    section[data-testid="stSidebar"] .period-chip .period-chip-icon {
        width: 30px; height: 30px; min-width: 30px; border-radius: 9px;
        display: flex; align-items: center; justify-content: center;
        background: linear-gradient(135deg, #1a3a6b, #2f5fa8);
        color: #fff; font-size: 1rem;
    }
    section[data-testid="stSidebar"] .period-chip-label {
        font-size: 0.62rem; font-weight: 700; text-transform: uppercase;
        letter-spacing: 0.6px; color: rgba(255,255,255,0.4); line-height: 1.1;
    }
    section[data-testid="stSidebar"] .period-chip-value {
        font-size: 0.86rem; font-weight: 700; color: #fff; line-height: 1.3;
        display: flex; align-items: center; gap: 6px;
    }
    section[data-testid="stSidebar"] .period-chip-status {
        font-size: 0.62rem; font-weight: 700; padding: 1px 7px; border-radius: 20px;
        text-transform: uppercase; letter-spacing: 0.3px;
    }
    section[data-testid="stSidebar"] .period-chip.period-open .period-chip-status {
        background: rgba(46, 204, 113, 0.18); color: #4ade80;
    }
    section[data-testid="stSidebar"] .period-chip.period-closed .period-chip-status {
        background: rgba(239, 68, 68, 0.18); color: #f87171;
    }
    section[data-testid="stSidebar"] .nav-section { color: rgba(255,255,255,0.32); font-size: 0.66rem; font-weight: 700; text-transform: uppercase; letter-spacing: 1px; margin: 0.9rem 0.2rem 0.35rem; }
    section[data-testid="stSidebar"] .stButton button { background: transparent !important; color: rgba(255,255,255,0.75) !important; border: none !important; text-align: left !important; justify-content: flex-start !important; font-weight: 500 !important; font-size: 0.85rem !important; padding: 0.55rem 0.8rem !important; border-radius: 9px !important; margin-bottom: 2px !important; box-shadow: none !important; }
    section[data-testid="stSidebar"] .stButton button:hover { background: rgba(255,255,255,0.08) !important; color: #fff !important; }
    section[data-testid="stSidebar"] .stButton button[kind="primary"] { background: linear-gradient(135deg, #1a3a6b, #2f5fa8) !important; color: #fff !important; font-weight: 700 !important; box-shadow: 0 4px 12px rgba(0,0,0,0.28) !important; }
    section[data-testid="stSidebar"] hr { border-color: rgba(255,255,255,0.08) !important; }

    /* Sidebar selectbox (kỳ làm việc) — nổi bật trên nền tối */
    section[data-testid="stSidebar"] div[data-testid="stSelectBox"] {
        background: linear-gradient(135deg, rgba(255,255,255,0.12), rgba(255,255,255,0.06)) !important;
        border-radius: 12px !important;
        padding: 8px 12px 4px !important;
        margin-bottom: 6px !important;
        border: 1.5px solid rgba(255,255,255,0.2) !important;
        box-shadow: 0 2px 12px rgba(0,0,0,0.25) !important;
    }
    section[data-testid="stSidebar"] div[data-testid="stSelectBox"] label,
    section[data-testid="stSidebar"] div[data-testid="stSelectBox"] label div,
    section[data-testid="stSidebar"] div[data-testid="stSelectBox"] label p,
    section[data-testid="stSidebar"] div[data-testid="stWidgetLabel"] p {
        color: #ffffff !important;
        font-weight: 800 !important;
        font-size: 0.85rem !important;
        letter-spacing: 0.5px !important;
        text-shadow: 0 1px 4px rgba(0,0,0,0.4) !important;
    }
    section[data-testid="stSidebar"] div[data-testid="stSelectBox"] div[data-baseweb="select"] > div {
        background: rgba(255,255,255,0.2) !important;
        border: 1px solid rgba(255,255,255,0.35) !important;
        color: #fff !important; border-radius: 8px !important;
        font-weight: 700 !important; font-size: 0.9rem !important;
        backdrop-filter: blur(4px) !important;
    }
    section[data-testid="stSidebar"] div[data-testid="stSelectBox"] div[data-baseweb="select"] span {
        color: #ffffff !important; font-weight: 700 !important;
    }
    section[data-testid="stSidebar"] div[data-testid="stSelectBox"] svg {
        fill: #ffffff !important;
    }

    /* Dropdown popup list */
    div[data-baseweb="popover"] ul {
        background: #0d2038 !important; border: 1px solid rgba(255,255,255,0.12) !important;
    }
    div[data-baseweb="popover"] li {
        color: #fff !important;
    }
    div[data-baseweb="popover"] li:hover {
        background: rgba(255,255,255,0.1) !important;
    }

    /* Material Icons font không tải được (offline) -> ẩn raw ligature text */
    [class*="material-symbols"], [class*="material-icons"],
    span[class*="material"], span[class*="Material"],
    [data-testid*="stExpander"] button span,
    [data-testid*="baseButton-header"] span,
    [data-testid*="stSelectBox"] span[class] {
        font-size: 0px !important;
        min-width: 0px !important;
        max-width: 0px !important;
        width: 0px !important;
        height: 0px !important;
        min-height: 0px !important;
        overflow: hidden !important;
        display: inline-block !important;
        color: transparent !important;
        visibility: hidden !important;
    }

    .sidebar-spacer { height: 30vh; }
    section[data-testid="stSidebar"] .logout-row .stButton button { border: 1px solid rgba(255,255,255,0.12) !important; color: rgba(255,255,255,0.6) !important; }
    section[data-testid="stSidebar"] .logout-row .stButton button:hover { background: rgba(198,40,40,0.18) !important; color: #ff8a80 !important; }

    .main-header { background: linear-gradient(135deg, #0a1628, #1a3a6b); padding: 0.7rem 1.6rem 1rem; border-radius: 14px; margin-bottom: 1.1rem; box-shadow: 0 8px 24px rgba(10,22,40,0.14); }
    .main-header h1 { color: white !important; font-size: 1.25rem !important; margin: 0.2rem 0 0 !important; font-weight: 700 !important; }
    .main-header p { color: rgba(255,255,255,0.72); margin: 0.2rem 0 0 0; font-size: 0.8rem; }
    div[data-testid="stMetric"], div[data-testid="metric-container"] { background: white; border: 1px solid #edf0f5; border-radius: 14px; padding: 0.9rem 1.1rem; box-shadow: 0 2px 10px rgba(10,22,40,0.04); }
    div[data-testid="stMetric"] label, div[data-testid="metric-container"] label { color: #1a3a6b !important; font-weight: 600 !important; font-size: 0.75rem !important; }
    div[data-testid="stMetricValue"], div[data-testid="metric-container"] div[data-testid="metric-value"] { color: #0a1628 !important; font-weight: 800 !important; }
    .stTabs [data-baseweb="tab-list"] { gap: 4px; background: #eef1f6; padding: 5px; border-radius: 12px; margin-bottom: 1rem; }
    .stTabs [data-baseweb="tab"] { border-radius: 9px; padding: 0.5rem 1.1rem; font-size: 0.85rem; font-weight: 600; white-space: nowrap; color: #5c6579; }
    .stTabs [aria-selected="true"] { background: #0a1628 !important; color: white !important; font-weight: 700; box-shadow: 0 4px 10px rgba(10,22,40,0.2); }
    div[data-testid="stAppViewContainer"] .main .stButton button { border-radius: 9px; font-weight: 600; font-size: 0.85rem; }
    div[data-testid="stAppViewContainer"] .main .stButton button[kind="primary"] { background: #0a1628; border: none; font-weight: 700; padding: 0.4rem 1.5rem; }
    div[data-testid="stAppViewContainer"] .main .stButton button[kind="primary"]:hover { background: #1a3a6b; }
    div[data-testid="stAppViewContainer"] .main .stButton button[kind="secondary"] { border: 1.5px solid #e4e8f0; background: #fff; color: #24324a; }
    .stDataFrame { border-radius: 10px; border: 1px solid #edf0f5; font-size: 0.82rem; overflow: hidden; }
    .stSubheader, h2, h3 { color: #0a1628 !important; }
    .info-bar { background: #eef3fc; border-left: 4px solid #1a3a6b; padding: 0.55rem 1rem; border-radius: 0 10px 10px 0; font-size: 0.8rem; color: #0a1628; margin: 0.5rem 0; }
    hr { margin: 0.4rem 0 !important; border-color: #edf0f5 !important; }
    div[data-testid="stExpander"] { border: 1px solid #edf0f5; border-radius: 10px; overflow: hidden; }
    .stAlert { border-radius: 10px; font-size: 0.85rem; }
    .upload-zone { border: 2px dashed #1a3a6b; border-radius: 14px; padding: 2rem; text-align: center; background: #f8faff; margin: 1rem 0; }
    .upload-zone p { color: #6b7a99; margin: 0.5rem 0 0; font-size: 0.85rem; }
    .template-btn { display: inline-flex; align-items: center; gap: 6px; background: #eef3fc; border: 1px solid #1a3a6b; color: #0a1628; border-radius: 9px; padding: 0.4rem 1rem; font-size: 0.8rem; font-weight: 600; cursor: pointer; text-decoration: none; }
    .template-btn:hover { background: #d6e4f5; }
</style>
"""

ROLE_LABELS: dict = {"admin": "Quản trị", "pic": "Nhân viên", "boss": "Ban giám đốc"}
ROLE_CLASS: dict = {"admin": "role-admin", "pic": "role-pic", "boss": "role-boss"}


def apply_css():
    st.markdown(APP_CSS, unsafe_allow_html=True)


def header(title: str, subtitle: str = None):
    brand = '<div style="font-size:0.75rem;font-weight:700;color:#8a95a8;letter-spacing:1px;margin-bottom:2px;">CK VINA REPORT</div>'
    html = f'<div class="main-header">{brand}<h1 style="margin-top:0;">{title}</h1>'
    if subtitle:
        html += f'<p>{subtitle}</p>'
    html += '</div>'
    st.markdown(html, unsafe_allow_html=True)


def info_bar(text: str):
    st.markdown(f'<div class="info-bar">{text}</div>', unsafe_allow_html=True)


def brand_html(subtitle: str = "Báo cáo tồn kho tự động") -> str:
    return (
        '<div class="brand">'
        '<div class="badge-logo">CK</div>'
        '<div class="brand-text"><h1>CK VINA REPORT</h1>'
        f'<p>{subtitle}</p></div></div>'
    )


def user_chip_html(user: dict) -> str:
    name = user.get("name") or user.get("user_id", "")
    initials = "".join([p[0] for p in name.split()][:2]).upper() or "U"
    role = user.get("role", "")
    role_label = ROLE_LABELS.get(role, role.upper())
    role_class = ROLE_CLASS.get(role, "role-admin")
    return (
        '<div class="user-chip">'
        f'<div class="avatar">{initials}</div>'
        f'<div class="who"><div class="name">{name}</div>'
        f'<span class="role-badge {role_class}">{role_label}</span></div>'
        '</div>'
    )


def period_chip_html(period: str, status: str = "open") -> str:
    """Chip nhỏ hiển thị Kỳ làm việc hiện tại ở sidebar (bên trái)."""
    is_open = str(status).lower() == "open"
    status_class = "period-open" if is_open else "period-closed"
    status_label = "Đang mở" if is_open else "Đã khóa"
    return (
        f'<div class="period-chip {status_class}">'
        '<div class="period-chip-icon">📅</div>'
        '<div>'
        '<div class="period-chip-label">Kỳ làm việc</div>'
        f'<div class="period-chip-value">{period}'
        f'<span class="period-chip-status">{status_label}</span></div>'
        '</div>'
        '</div>'
    )


def nav_section(title: str):
    st.markdown(f'<div class="nav-section">{title}</div>', unsafe_allow_html=True)


def sidebar_spacer():
    st.markdown('<div class="sidebar-spacer"></div>', unsafe_allow_html=True)


def _clean_for_excel(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    num_cols = df.select_dtypes(include=["float", "int"]).columns
    for c in num_cols:
        df[c] = df[c].replace([np.inf, -np.inf], 0).fillna(0)
    obj_cols = df.select_dtypes(include=["object"]).columns
    for c in obj_cols:
        df[c] = df[c].fillna("")
    return df


def _safe_sheet_name(name: str, used: set) -> str:
    invalid = ':\\/?*[]'
    clean = "".join(c for c in str(name) if c not in invalid).strip() or "Sheet"
    clean = clean[:31]
    base, i = clean, 1
    while clean in used:
        suffix = f"_{i}"
        clean = base[: 31 - len(suffix)] + suffix
        i += 1
    used.add(clean)
    return clean


def excel_bytes_multi(sheets: dict) -> bytes:
    buf = io.BytesIO()
    used = set()
    with pd.ExcelWriter(buf, engine="openpyxl") as writer:
        for name, df in sheets.items():
            if df is None or df.empty:
                continue
            safe_name = _safe_sheet_name(name, used)
            _clean_for_excel(df).to_excel(writer, sheet_name=safe_name, index=False)
    return buf.getvalue()


def excel_bytes_single(df: pd.DataFrame, sheet_name: str = "Sheet1") -> bytes:
    return excel_bytes_multi({sheet_name: df})


def _merge(base: dict, extra: dict) -> dict:
    d = base.copy()
    d.update(extra)
    return d


_BASE = {"period": "Kỳ", "id": "ID", "remark": "Ghi chú", "ghi_chu": "Ghi chú",
         "ngay": "Ngày", "type": "Loại", "qty": "SL", "trans_type": "Loại GD",
         "level_subcon": "Cấp SUB", "subcon": "Subcon", "dvt": "ĐVT", "spec": "Quy cách", "unit": "ĐVT"}

SHEET_COLUMNS = {
    "end_stock_nvl": _merge(_BASE, {"item_code": "Mã NVL", "qty_begin": "Tồn đầu"}),
    "end_stock_tp": _merge(_BASE, {"prod_code": "Mã TP", "sale_code": "Mã bán", "qty_begin": "Tồn đầu"}),
    "end_stock_full_sub": _merge(_BASE, {"prod_code": "Mã TP", "sale_code": "Mã bán", "qty_begin": "Tồn đầu"}),
    "nk_nvl_in_cds": _merge(_BASE, {"so_to_khai": "Số tờ khai", "ngay_tk": "Ngày TK", "ma_loai_hinh": "Mã loại hình",
        "so_hoa_don": "Số hóa đơn", "item_code": "Mã NVL", "ten_hang": "Tên hàng",
        "qty_input": "SL nhập", "ngay_giao_hang": "Ngày giao hàng", "qty_return": "SL trả lại"}),
    "nk_nvl_in_actual": _merge(_BASE, {"ngay_nhap_kho": "Ngày nhập kho", "sub_code": "Mã SUB",
        "item_code": "Mã NVL", "qty_actual": "SL thực tế", "qty_return": "SL trả lại"}),
    "subcon_out": _merge(_BASE, {"prod_code": "Mã TP", "sale_code": "Mã bán", "item_code": "Mã NVL", "stock_in": "Kho nhập"}),
    "subcon_in": _merge(_BASE, {"hs_code": "Mã HS", "prod_code": "Mã TP", "sale_code": "Mã bán", "item_code": "Mã NVL", "stock_out": "Kho xuất"}),
    "xk_tp_out_cds": _merge(_BASE, {"so_to_khai": "Số tờ khai", "ngay_tk": "Ngày TK", "ma_loai_hinh": "Mã loại hình",
        "so_hoa_don": "Số hóa đơn", "hs_code": "Mã HS", "prod_code": "Mã TP", "sale_code": "Mã bán",
        "qty_sale": "SL bán", "ngay_giao_hang": "Ngày giao hàng", "qty_return": "SL trả lại"}),
    "xk_tp_out_actual": _merge(_BASE, {"ngay_nhap_kho": "Ngày nhập kho", "ma_hs": "Mã HS",
        "prod_code": "Mã TP", "sale_code": "Mã bán", "actual_qty": "SL thực tế"}),
    "out_ng": _merge(_BASE, {"hs_code": "Mã HS", "prod_code": "Mã TP", "sale_code": "Mã bán",
        "item_code": "Mã NVL", "stock_out_in": "Kho X/N", "request_kind": "Loại yêu cầu"}),
}

DM_NVL_LABELS = {"item_code": "Mã NVL", "type_code": "Mã loại", "spec": "Quy cách", "unit": "ĐVT", "don_gia": "Đơn giá TK"}
DM_TP_LABELS = {"prod_code": "Mã TP", "type_code": "Mã loại", "sale_code": "Mã bán", "spec": "Quy cách", "unit": "ĐVT", "remark": "Ghi chú"}
BOM_LABELS = {"prod_code": "Mã TP", "sale_code": "Mã bán", "item_code": "Mã NVL", "type": "Loại",
    "component_desc": "Diễn giải", "dvt": "ĐVT", "bom_unit": "Định mức", "time_apply": "Thời gian", "remark": "Ghi chú"}
USERS_LABELS = {"user_id": "User ID", "password": "Mật khẩu", "role": "Vai trò", "name": "Họ tên", "email": "Email"}
BALANCE_SHEET_LABELS = {
    "no": "STT", "item_code": "Mã NVL", "spec": "Quy cách", "unit": "ĐVT", "type": "Loại",
    "begin_mat": "① Tồn đầu MAT", "begin_fg": "② Tồn đầu FG", "in_po": "③ NK NVL (tờ khai)",
    "gap_in_actual": "④ GAP NK thực tế", "in_replace_adj": "⑤ NK khác (thay thế/ĐC)",
    "out_scrap_adj_replace": "⑥ XK khác (phế liệu/ĐC)", "out_return": "⑦ Trả lại HS",
    "out_sale_fg_hs_cds": "⑧ XK TP (tờ khai)", "gap_sale_actual": "⑨ GAP XK thực tế",
    "sale_return": "⑩ Hàng bán trả lại", "scrap_fg": "⑪ Phế phẩm FG",
    "gap_in_po_remain": "⑫ GAP NK tồn lũy kế", "gap_sale_fg_remain": "⑬ GAP XK tồn lũy kế",
    "ending_logic": "⑭ Tồn cuối (logic)", "ending_mat": "⑮ Tồn cuối MAT",
    "ending_fg": "⑯ Tồn cuối FG", "gap_actual_logic": "⑰ GAP thực tế - logic",
    "ending_hs_erp": "⑱ Tồn cuối HS ERP", "ending_actual_hs": "⑲ Tồn cuối thực tế HS",
    "gap_hs_ck": "⑳ GAP HS - CK", "don_gia_tk": "Đơn giá TK", "gap_amount_estimate": "Giá trị GAP ước tính",
}
REPORT_LABELS = {
    "GAP NK NVL": {"item_code": "Mã NVL", "type": "Loại", "in_cds": "NK tờ khai",
        "giao_nvl": "Giao NVL trực tiếp", "giao_sub_dongbo": "Giao SUB đồng bộ", "gap_qty": "GAP (SL)"},
    "Remain delivery NVL (lũy kế)": {"item_code": "Mã NVL", "gap_begin": "GAP đầu kỳ", "in_cds": "NK tờ khai",
        "actual_gap_qty": "GAP NK thực tế", "qty_in_month": "Tổng NK trong kỳ", "gap_end": "GAP cuối kỳ"},
    "NXT SUB": {"prod_code": "Mã TP", "sale_code": "Mã bán", "spec": "Quy cách", "unit": "ĐVT",
        "subcon": "Subcon", "begin": "ĐK", "sub_out": "Xuất", "sub_in": "Nhập", "ending": "CK"},
    "Convert SUB to MAT": {"prod_code": "Mã TP", "item_code": "Mã NVL", "trans_type": "Loại GD",
        "fg_qty": "SL TP", "bom_unit": "Định mức BOM", "total_mat_qty": "Tổng NVL quy đổi"},
    "GAP XK TP": {"prod_code": "Mã TP", "sale_code": "Mã bán", "cds_qty": "XK tờ khai",
        "actual_qty": "XK thực tế", "gap_qty": "GAP (SL)"},
    "Remain delivery TP (lũy kế)": {"prod_code": "Mã TP", "gap_begin": "GAP đầu kỳ", "out_cds": "XK tờ khai",
        "actual_gap_qty": "GAP XK thực tế", "qty_in_month": "Tổng XK trong kỳ", "gap_end": "GAP cuối kỳ"},
    "NXT NVL": {"item_code": "Mã NVL", "begin_mat": "Tồn đầu MAT", "in_cds": "NK tờ khai",
        "gap_actual_delivery": "GAP giao hàng thực tế", "out_production": "XSX (giao SUB)",
        "return_mat_to_hs": "Trả NVL cho HS", "in_other": "Nhập khác", "out_other": "Xuất khác",
        "ending_logic": "Tồn cuối (logic)", "gap_remain_delivery": "GAP giao hàng tồn"},
    "NXT TP": {"prod_code": "Mã TP", "begin_fg": "Tồn đầu FG", "prod_qty": "SL sản xuất",
        "sale_to_hs_cds": "Bán HS (tờ khai)", "gap_sale_actual": "GAP bán thực tế",
        "sale_return": "Hàng bán trả lại", "out_other_scrap": "XK khác / phế phẩm",
        "ending_logic": "Tồn cuối (logic)", "gap_delivery_remain": "GAP giao hàng tồn"},
    "Convert TP to MAT": {"prod_code": "Mã TP", "item_code": "Mã NVL", "trans_type": "Loại GD",
        "qty": "SL TP", "bom_unit": "Định mức BOM", "total_mat_qty": "Tổng NVL quy đổi"},
    "NXT Convert MAT": {
        "period": "Kỳ", "item_code": "Mã NVL", "spec": "Quy cách", "unit": "ĐVT", "type": "Loại",
        "subcon": "Subcon",
        "begin": "ĐK", "sub_out": "SUB OUT", "sub_return": "SUB RETURN",
        "out_nvl": "OUT NVL", "return_nvl": "Return NVL", "sub_in": "SUB IN",
        "ending": "CK", "remark": "Ghi chú"},
}


def label_df(df: pd.DataFrame, mapping: dict) -> pd.DataFrame:
    rename = {k: v for k, v in mapping.items() if k in df.columns}
    return df.rename(columns=rename)


def data_editor_with_labels(df: pd.DataFrame, labels: dict, overrides: dict = None, **kwargs):
    col_cfg = {col: label for col, label in labels.items() if col in df.columns}
    if overrides:
        col_cfg.update(overrides)
    return st.data_editor(df, column_config=col_cfg, **kwargs)


def download_template(cols: list, fill_values: dict = None) -> bytes:
    buf = io.BytesIO()
    df = pd.DataFrame(columns=cols)
    if fill_values:
        for col, val in fill_values.items():
            if col in df.columns:
                df[col] = val
    with pd.ExcelWriter(buf, engine="openpyxl") as w:
        df.to_excel(w, index=False)
    return buf.getvalue()


def validate_upload(df: pd.DataFrame, required_cols: list, table_name: str) -> list:
    errors = []
    df_cols = [c.strip().lower().replace(" ", "_") for c in df.columns]
    for col in required_cols:
        if col not in df_cols:
            errors.append(f"Thiếu cột bắt buộc: '{col}'")
    return errors


def render_upload_sheet(table: str, cols: list, period: str, conn, user: dict, sheet_label: str, desc: str):
    st.markdown(f"**{desc}**")
    info_bar(f"Kỳ hiện tại: {period} | Sheet: {table}")

    col_tpl, col_up = st.columns([1, 2])
    with col_tpl:
        tpl_cols = (["Period"] + cols) if "Period" not in cols else cols
        tpl_fill = {"Period": period} if "Period" not in cols else {}
        template_bytes = download_template(tpl_cols, fill_values=tpl_fill)
        st.download_button("📥 Tải template Excel", data=template_bytes,
                           file_name=f"{table}_template.xlsx",
                           mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                           key=f"tpl_{table}")

    uploaded = st.file_uploader("📤 Chọn file dữ liệu (Excel hoặc CSV)", type=["xlsx", "csv"],
                                 key=f"upload_{table}")
    if uploaded:
        try:
            if uploaded.name.endswith(".csv"):
                new_df = pd.read_csv(uploaded, dtype=str, encoding="utf-8-sig", sep=None, engine="python")
            else:
                new_df = pd.read_excel(uploaded, dtype=str)
            new_df.columns = [c.strip().lower().replace(" ", "_") for c in new_df.columns]
            new_df = new_df.dropna(how="all")

            val_errors = validate_upload(new_df, cols, table)
            if not val_errors:
                st.success(f"✅ Đã đọc {len(new_df)} dòng từ file.")
                st.dataframe(new_df, use_container_width=True, height=300, hide_index=True)

                if st.button("💾 Lưu vào cơ sở dữ liệu", type="primary", key=f"save_upload_{table}"):
                    new_df["period"] = period
                    conn.execute(f"DELETE FROM {table} WHERE period = ?", (period,))
                    new_df.to_sql(table, conn, if_exists="append", index=False)
                    conn.execute(
                        "INSERT INTO audit_log(ts, user_id, action, detail) VALUES (datetime('now'), ?, ?, ?)",
                        (user["user_id"], "upload_data", f"{table} / {period} / {len(new_df)} rows"))
                    conn.commit()
                    st.success(f"✅ Đã lưu {len(new_df)} dòng vào **{sheet_label}**.")
                    sync_to_excel(table, period)
                    st.rerun()
            else:
                for e in val_errors:
                    st.error(f"❌ {e}")
        except Exception as e:
            st.error(f"Lỗi đọc file: {e}")

    st.markdown("---")
    st.markdown("**📋 Dữ liệu hiện tại trong DB**")
    existing = pd.read_sql(f"SELECT * FROM {table} WHERE period = ?", conn, params=(period,))
    if existing.empty:
        st.info("Chưa có dữ liệu.")
    else:
        search_cols = [c for c in ["item_code", "prod_code", "sale_code"] if c in existing.columns]
        if search_cols:
            search = st.text_input("🔍 Tìm kiếm theo mã", key=f"search_{table}", placeholder="Nhập mã Item...")
            if search:
                mask = pd.Series(False, index=existing.index)
                for col in search_cols:
                    mask |= existing[col].astype(str).str.contains(search, case=False, na=False)
                existing = existing[mask]
        st.dataframe(existing, use_container_width=True, height=350, hide_index=True)
        try:
            excel_data = excel_bytes_single(existing, sheet_name=sheet_label)
            st.download_button(
                "📥 Tải dữ liệu hiện tại (Excel)",
                data=excel_data,
                file_name=f"{table}_{period}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                key=f"dl_existing_{table}",
            )
        except Exception as e:
            st.error(f"Không thể tạo Excel: {e}")


# ===== Style helpers for reports =====

GAP_KEYWORDS = ("gap", "chênh lệch", "GAP")


def _is_gap_col(col: str) -> bool:
    col_lower = col.lower()
    return any(kw in col_lower for kw in ("gap", "chênh", "giao", "sub_dongbo"))


def _is_ending_col(col: str) -> bool:
    return col.lower().startswith("ending") or col.lower().startswith("end")


def style_df(df: pd.DataFrame, num_format: str = "{:,.0f}"):
    styled = df.copy()
    numeric_cols = styled.select_dtypes(include=[np.number]).columns
    gap_cols = [c for c in numeric_cols if _is_gap_col(c)]
    all_neg_cols = [c for c in numeric_cols if _is_gap_col(c) or _is_ending_col(c)]

    def _color_neg(val):
        if pd.isna(val):
            return ""
        try:
            v = float(val)
        except (ValueError, TypeError):
            return ""
        if v < 0:
            return "color: #d32f2f; font-weight: 600;"
        return ""

    def _bold_total_row(row):
        if any("Tong" in str(v) for v in row.values):
            return ["font-weight: 700; background: #eef3fc;" for _ in row]
        return ["" for _ in row]

    styled = styled.style \
        .format({c: num_format for c in numeric_cols}, na_rep="0") \
        .map(_color_neg, subset=all_neg_cols) \
        .apply(_bold_total_row, axis=1)

    return styled


def label_subcon_columns(df: pd.DataFrame, subcon_prefixes: dict = None) -> pd.DataFrame:
    subcon_suffixes = ("begin", "sub_out", "sub_in", "ending",
                       "sub_return", "out_nvl", "return_nvl")
    rename = {}
    for c in df.columns:
        parts = c.split("_", 1)
        if len(parts) == 2 and parts[0] in subcon_suffixes:
            metric, scon = parts
            subcon_labels = {"begin": "ĐK", "sub_out": "SUB OUT", "sub_return": "SUB RETURN",
                             "out_nvl": "OUT NVL", "return_nvl": "Return NVL",
                             "sub_in": "SUB IN", "ending": "CK"}
            label = subcon_labels.get(metric, metric)
            rename[c] = f"{scon}_{label}"
    if not rename:
        return df
    return df.rename(columns=rename)