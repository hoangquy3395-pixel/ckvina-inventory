"""
Authentication & Authorization Module for Streamlit (CK VINA REPORT)
Author: Senior UI/UX & IT Engineering Team
Description: Giao diện Đăng nhập Premium - Đồng bộ full màu xám toàn phần cho các ô nhập liệu.
"""

import hashlib
import logging
from typing import Optional, Dict, Any, List
import streamlit as st
from db import get_conn, log_action
import pandas as pd
from db import get_conn

# Thiết lập logging chuẩn hệ thống
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")


# ==========================================
# 1. CORE LOGIC & SECURITY (XỬ LÝ HỆ THỐNG)
# ==========================================

def _hash_password(password: str) -> str:
    """Mã hóa mật khẩu bằng thuật toán SHA-256."""
    return hashlib.sha256(password.strip().encode('utf-8')).hexdigest()


def authenticate_user(user_id: str, password: str) -> Optional[Dict[str, Any]]:
    """Xác thực người dùng từ cơ sở dữ liệu bảo mật."""
    if not user_id or not password:
        return None

    conn = None
    try:
        conn = get_conn()
        query = "SELECT user_id, password, role, name FROM users WHERE user_id = ?"
        df = pd.read_sql(query, conn, params=(user_id.strip(),))
        
        if df.empty:
            logging.warning(f"Failed login attempt: User '{user_id}' not found.")
            return None
            
        user_row = df.iloc[0]
        stored_pwd = str(user_row["password"]).strip()
        input_pwd_hashed = _hash_password(password)
        
        if stored_pwd == input_pwd_hashed or stored_pwd == password.strip():
            logging.info(f"User '{user_id}' logged in successfully.")
            try:
                c = get_conn()
                log_action(c, user_id, "login", "Đăng nhập thành công")
                c.close()
            except Exception:
                pass
            return {
                "user_id": user_row["user_id"],
                "role": str(user_row["role"]).upper(),
                "name": user_row["name"]
            }
            
        logging.warning(f"Failed login attempt: Incorrect password for '{user_id}'.")
        return None

    except Exception as e:
        logging.error(f"Database error during authentication: {str(e)}")
        st.error("🚨 Lỗi kết nối cơ sở dữ liệu. Vui lòng liên hệ bộ phận IT.")
        return None
    finally:
        if conn:
            conn.close()


# ==========================================
# 2. MODERN UI/UX STYLING (HỆ THỐNG CSS ĐÃ FIX)
# ==========================================

def _inject_custom_css():
    """Nhúng bộ CSS sửa đổi cấu trúc hiển thị để phủ full màu xám và xóa lỗi khung mờ."""
    st.markdown("""
    <style>
    /* Nền tổng thể sáng sang trọng */
    .stApp {
        background-color: #fcfbf7 !important;
        font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
    }
    
    /* Ẩn header và footer mặc định */
    header[data-testid="stHeader"], footer {
        visibility: hidden !important;
    }

    /* Ẩn thẻ đánh dấu phụ */
    div.card-marker {
        display: none !important;
    }

    /* Tạo duy nhất một Card Đăng nhập đồng nhất bao quanh toàn bộ Column (Độ rộng 600px) */
    div[data-testid="stColumn"]:has(.card-marker) {
        background: #ffffff !important;
        padding: 45px 50px 40px 50px !important;
        border-radius: 24px !important;
        box-shadow: 0 15px 45px rgba(0, 0, 0, 0.05) !important;
        border: 1px solid #efeeed !important;
        max-width: 600px !important;
        margin: 40px auto !important;
    }

    /* Định dạng cụm tiêu đề chính xác */
    .auth-container {
        text-align: center;
        margin-bottom: 2.2rem;
    }
    .auth-title {
        font-size: 2.4rem;
        font-weight: 700;
        color: #1e293b;
        line-height: 1.2;
        margin-bottom: 0.8rem;
        letter-spacing: -0.5px;
    }
    .auth-brand {
        font-size: 1.1rem;
        font-weight: 800;
        color: #0f172a;
        text-transform: uppercase;
        letter-spacing: 0.8px;
        margin-bottom: 0.3rem;
    }
    .auth-subtitle {
        font-size: 0.95rem;
        color: #64748b;
        font-weight: 400;
    }

    /* Cấu hình tiêu đề nhãn input */
    div[data-testid="stTextInput"] label p {
        font-weight: 600 !important;
        font-size: 0.9rem !important;
        color: #4a5058 !important;
    }

    /* FIX TRIỆT TIỂU LỖI: Đồng bộ FULL MÀU XÁM toàn phần cho toàn bộ khung ô nhập liệu */
    div[data-testid="stTextInput"] div[data-baseweb="input"] {
        border-radius: 12px !important;
        border: 1.5px solid #e2e8f0 !important;
        background-color: #f1f5f9 !important; /* Màu xám tinh tế đồng nhất */
        transition: all 0.2s ease !important;
    }
    
    /* Ép tất cả các thẻ con, khoảng trống thừa bên trong ô nhập liệu thành trong suốt */
    div[data-testid="stTextInput"] div[data-baseweb="input"] * {
        background: transparent !important;
    }
    
    /* Hiệu ứng đổi màu viền mượt mà khi người dùng click vào ô nhập liệu */
    div[data-testid="stTextInput"] div[data-baseweb="input"]:focus-within {
        border-color: #00ce5a !important;
        background-color: #ffffff !important; /* Chuyển sang trắng sạch sẽ khi focus */
        box-shadow: 0 0 0 4px rgba(0, 206, 90, 0.12) !important;
    }

    /* Định dạng text bên trong ô nhập liệu */
    div[data-testid="stTextInput"] input {
        border: none !important;
        box-shadow: none !important;
        padding: 14px 16px !important;
        font-size: 1rem !important;
        color: #0f172a !important;
    }
    
    /* Định dạng lại khu vực icon mắt native */
    div[data-testid="stTextInput"] button {
        border: none !important;
        box-shadow: none !important;
        padding-right: 14px !important;
    }

    /* Nút bấm Đăng nhập hình hạt đậu lớn */
    div[data-testid="stButton"] > button[kind="primary"] {
        background: linear-gradient(135deg, #00d25b 0%, #00b84f 100%) !important;
        color: #ffffff !important;
        border: none !important;
        border-radius: 50px !important;
        padding: 0.8rem 1.5rem !important;
        font-size: 1.1rem !important;
        font-weight: 700 !important;
        margin-top: 1.5rem;
        width: 100%;
        box-shadow: 0 6px 20px rgba(0, 184, 79, 0.2);
        transition: all 0.2s ease;
    }
    div[data-testid="stButton"] > button[kind="primary"]:hover {
        transform: translateY(-1px);
        box-shadow: 0 8px 25px rgba(0, 184, 79, 0.3);
    }

    /* Cụm liên kết phía dưới chân trang */
    .auth-links {
        display: flex;
        justify-content: space-between;
        align-items: center;
        margin-top: 2rem;
        padding-top: 1.4rem;
        border-top: 1px solid #f1f1f0;
    }
    .auth-links a {
        color: #2b6cb0;
        text-decoration: none;
        font-weight: 600;
        font-size: 0.88rem;
        white-space: nowrap;
        transition: color 0.15s;
    }
    .auth-links a:hover {
        color: #1a4971;
        text-decoration: underline;
    }

    /* Footer hệ thống */
    .auth-footer {
        text-align: center;
        font-size: 0.78rem;
        color: #cbd5e1;
        line-height: 1.5;
        margin-top: 1.8rem;
    }
    </style>
    """, unsafe_allow_html=True)


# ==========================================
# 3. UI RENDERING COMPONENTS
# ==========================================

def render_login():
    """Hiển thị giao diện đăng nhập chuẩn hóa thẩm mỹ."""
    _inject_custom_css()

    # Cấu hình tỉ lệ layout giúp căn chỉnh khối đăng nhập tập trung và rộng rãi hơn
    _, col_center, _ = st.columns([1, 3, 1])

    with col_center:
        # Thẻ marker dùng để CSS định vị toàn bộ cấu trúc cột thành 1 hộp thống nhất
        st.markdown('<div class="card-marker"></div>', unsafe_allow_html=True)
        
        # Nội dung tiêu đề căn giữa hoàn hảo
        st.markdown("""
            <div class="auth-container">
                <div class="auth-title">Hello!<br>Sign in</div>
                <div class="auth-brand"><strong>CK VINA REPORT</strong></div>
                <div class="auth-subtitle">Hệ thống quản trị tồn kho</div>
            </div>
        """, unsafe_allow_html=True)

        # Thông báo lỗi nếu có lỗi đăng nhập trong session
        error_msg = st.session_state.pop("login_error", None)
        if error_msg:
            st.error(f"⚠️ {error_msg}")

        # Trường nhập tài khoản
        uid = st.text_input(
            label="Your email / User ID",
            placeholder="e.g. elon@ckvina.com",
            key="login_uid"
        )

        # Trường nhập mật khẩu (Đã phủ màu xám mịn màng, không còn vết nứt trắng)
        pwd = st.text_input(
            label="Your password",
            type="password",
            placeholder="e.g. iloveckvina123",
            key="login_pwd"
        )

        # Xử lý sự kiện khi ấn nút Sign in
        if st.button("Sign in", type="primary", use_container_width=True):
            if not uid or not pwd:
                st.session_state["login_error"] = "Vui lòng nhập đầy đủ Tên đăng nhập và Mật khẩu."
                st.rerun()
                
            user_data = authenticate_user(uid, pwd)
            if user_data:
                st.session_state["user"] = user_data
                st.rerun()
            else:
                st.session_state["login_error"] = "Tên đăng nhập hoặc Mật khẩu không chính xác."
                st.rerun()

        # Thanh liên kết điều hướng phụ và bản quyền chân trang
        st.markdown("""
            <div class="auth-links">
                <a href="#">Don't have an account?</a>
                <a href="#">Forgot password?</a>
            </div>
            <div class="auth-footer">© CK Vina Internal System<br>All rights reserved</div>
        """, unsafe_allow_html=True)


# ==========================================
# 4. MIDDLEWARE & SESSION EXPORTS
# ==========================================

def require_login() -> Dict[str, Any]:
    """Guard kiểm tra trạng thái đăng nhập của người dùng."""
    user = st.session_state.get("user", None)
    if not user:
        render_login()
        st.stop()
    return user


def logout_button(sidebar: bool = True):
    """Nút đăng xuất hệ thống."""
    target = st.sidebar if sidebar else st
    if target.button("🚪 Đăng xuất", key="global_logout_btn", use_container_width=True):
        try:
            user_id = st.session_state.get("user", {}).get("user_id", "unknown")
            c = get_conn()
            log_action(c, user_id, "logout", "Đăng xuất")
            c.close()
        except Exception:
            pass
        st.session_state.clear()
        st.rerun()


def require_role(allowed_roles: List[str]):
    """Kiểm tra quyền hạn phân quyền (RBAC) trên các trang quản trị."""
    user = require_login()
    user_role = user.get("role", "").upper()
    allowed_roles_upper = [r.upper() for r in allowed_roles]
    
    if user_role not in allowed_roles_upper:
        st.error(f"⛔ Từ chối truy cập: Tài khoản ({user_role}) không đủ quyền hạn.")
        st.stop()