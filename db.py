import sqlite3
import hashlib
import os
import pandas as pd
from datetime import datetime
from typing import Optional

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "ck_app.db")
DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")

SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    user_id TEXT PRIMARY KEY,
    password TEXT NOT NULL,
    role TEXT NOT NULL CHECK(role IN ('admin','pic','boss')),
    name TEXT,
    email TEXT
);

CREATE TABLE IF NOT EXISTS periods (
    period TEXT PRIMARY KEY,
    status TEXT NOT NULL DEFAULT 'open' CHECK(status IN ('open','closed')),
    opened_by TEXT,
    opened_at TEXT,
    closed_by TEXT,
    closed_at TEXT
);

CREATE TABLE IF NOT EXISTS dm_nvl (
    item_code TEXT PRIMARY KEY,
    type_code TEXT,
    spec TEXT,
    unit TEXT,
    don_gia REAL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS dm_tp (
    prod_code TEXT PRIMARY KEY,
    type_code TEXT,
    sale_code TEXT,
    spec TEXT,
    unit TEXT,
    remark TEXT
);

CREATE TABLE IF NOT EXISTS bom (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    prod_code TEXT,
    sale_code TEXT,
    item_code TEXT,
    type TEXT,
    component_desc TEXT,
    dvt TEXT,
    bom_unit REAL,
    time_apply TEXT,
    remark TEXT
);

CREATE TABLE IF NOT EXISTS transaction_list (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    group_name TEXT,
    request_kind TEXT,
    disposition_desc TEXT,
    dien_giai TEXT
);

CREATE TABLE IF NOT EXISTS subcon_list (
    code TEXT PRIMARY KEY,
    group_name TEXT,
    stock_detail TEXT,
    level_subcon INTEGER,
    full_name TEXT
);

CREATE TABLE IF NOT EXISTS pending_new_codes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    code TEXT,
    code_type TEXT,
    source_sheet TEXT,
    period TEXT,
    status TEXT DEFAULT 'pending',
    created_at TEXT
);

CREATE TABLE IF NOT EXISTS end_stock_nvl (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    period TEXT, item_code TEXT, qty_begin REAL, subcon TEXT,
    type TEXT, level_subcon INTEGER, remark TEXT
);

CREATE TABLE IF NOT EXISTS end_stock_tp (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    period TEXT, prod_code TEXT, sale_code TEXT, qty_begin REAL,
    subcon TEXT, level_subcon INTEGER, remark TEXT
);

CREATE TABLE IF NOT EXISTS end_stock_full_sub (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    period TEXT, prod_code TEXT, sale_code TEXT, qty_begin REAL,
    subcon TEXT, level_subcon INTEGER, remark TEXT
);

CREATE TABLE IF NOT EXISTS end_stock_hs_erp (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    period TEXT, item_code TEXT, ending REAL
);

CREATE TABLE IF NOT EXISTS nk_nvl_in_cds (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    period TEXT, so_to_khai TEXT, ngay_tk TEXT, ma_loai_hinh TEXT,
    so_hoa_don TEXT, item_code TEXT, ten_hang TEXT, dvt TEXT, type TEXT,
    qty_input REAL, ngay_giao_hang TEXT, qty_return REAL, remark TEXT
);

CREATE TABLE IF NOT EXISTS nk_nvl_in_actual (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    period TEXT, ngay_nhap_kho TEXT, sub_code TEXT, item_code TEXT,
    type TEXT, qty_actual REAL, qty_return REAL, ghi_chu TEXT
);

CREATE TABLE IF NOT EXISTS subcon_out (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    period TEXT, ngay TEXT, prod_code TEXT, sale_code TEXT, item_code TEXT,
    type TEXT, stock_in TEXT, level_subcon INTEGER, trans_type TEXT,
    qty REAL, remark TEXT
);

CREATE TABLE IF NOT EXISTS subcon_in (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    period TEXT, ngay TEXT, hs_code TEXT, prod_code TEXT, sale_code TEXT,
    item_code TEXT, stock_out TEXT, trans_type TEXT, qty REAL,
    level_subcon INTEGER, remark TEXT
);

CREATE TABLE IF NOT EXISTS xk_tp_out_cds (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    period TEXT, so_to_khai TEXT, ngay_tk TEXT, ma_loai_hinh TEXT,
    so_hoa_don TEXT, hs_code TEXT, prod_code TEXT, sale_code TEXT,
    dvt TEXT, qty_sale REAL, ngay_giao_hang TEXT, qty_return REAL, remark TEXT
);

CREATE TABLE IF NOT EXISTS xk_tp_out_actual (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    period TEXT, ngay_nhap_kho TEXT, ma_hs TEXT, prod_code TEXT,
    sale_code TEXT, actual_qty REAL, ghi_chu TEXT
);

CREATE TABLE IF NOT EXISTS out_ng (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    period TEXT, ngay TEXT, hs_code TEXT, prod_code TEXT, sale_code TEXT,
    item_code TEXT, stock_out_in TEXT, request_kind TEXT, trans_type TEXT,
    qty REAL, remark TEXT
);

CREATE TABLE IF NOT EXISTS audit_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ts TEXT, user_id TEXT, action TEXT, detail TEXT
);
"""


def _hash_pwd(pwd: str) -> str:
    return hashlib.sha256(pwd.encode()).hexdigest()


def get_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.execute("PRAGMA foreign_keys = ON")
    conn.row_factory = sqlite3.Row
    return conn


def log_action(conn, user_id: str, action: str, detail: str = ""):
    conn.execute(
        "INSERT INTO audit_log(ts, user_id, action, detail) VALUES (datetime('now', 'localtime'), ?, ?, ?)",
        (user_id, action, detail))
    conn.commit()


def init_db():
    conn = get_conn()
    conn.executescript(SCHEMA)
    conn.commit()
    conn.close()


def _table_empty(conn: sqlite3.Connection, table: str) -> bool:
    cur = conn.execute(f"SELECT COUNT(*) FROM {table}")
    return cur.fetchone()[0] == 0


def _load_csv(name: str) -> Optional[pd.DataFrame]:
    path = os.path.join(DATA_DIR, name)
    if not os.path.exists(path):
        return None
    encodings = ["utf-8", "cp1252", "latin-1", "utf-8-sig"]
    for enc in encodings:
        try:
            return pd.read_csv(path, dtype=str, encoding=enc)
        except (UnicodeDecodeError, UnicodeError):
            continue
    return pd.read_csv(path, dtype=str, encoding="cp1252")


def seed_master_data():
    conn = get_conn()

    if _table_empty(conn, "users"):
        df = _load_csv("users.csv")
        if df is not None:
            df.columns = ["user_id", "password", "role", "name", "email"]
            df["role"] = df["role"].str.lower()
            df["password"] = df["password"].apply(_hash_pwd)
            df.to_sql("users", conn, if_exists="append", index=False)

    if _table_empty(conn, "dm_nvl"):
        df = _load_csv("dm_nvl.csv")
        if df is not None:
            df = df.rename(columns={
                "No.": "no", "Type code": "type_code", "Item code": "item_code",
                "Spec": "spec", "Unit": "unit", "Đơn giá TK": "don_gia"})
            df = df[["item_code", "type_code", "spec", "unit", "don_gia"]]
            df["don_gia"] = pd.to_numeric(df["don_gia"], errors="coerce").fillna(0)
            df = df.dropna(subset=["item_code"]).drop_duplicates("item_code")
            df.to_sql("dm_nvl", conn, if_exists="append", index=False)

    if _table_empty(conn, "dm_tp"):
        df = _load_csv("dm_tp.csv")
        if df is not None:
            df = df.rename(columns={
                "Type code": "type_code", "Prod code": "prod_code",
                "Sale code": "sale_code", "Spec": "spec", "Unit": "unit",
                "Remark": "remark"})
            df = df[["prod_code", "type_code", "sale_code", "spec", "unit", "remark"]]
            df = df.dropna(subset=["prod_code"]).drop_duplicates("prod_code")
            df.to_sql("dm_tp", conn, if_exists="append", index=False)

    if _table_empty(conn, "bom"):
        df = _load_csv("bom.csv")
        if df is not None:
            df = df.rename(columns={
                "Prod code": "prod_code", "Sale code": "sale_code",
                "Mã NVL": "item_code", "Type": "type",
                "Component Desc.": "component_desc", "ĐVT": "dvt",
                "BOM unit": "bom_unit", "Time Apply": "time_apply",
                "Remark": "remark"})
            df["bom_unit"] = pd.to_numeric(df["bom_unit"], errors="coerce").fillna(0)
            df = df[["prod_code", "sale_code", "item_code", "type", "component_desc",
                      "dvt", "bom_unit", "time_apply", "remark"]]
            df.to_sql("bom", conn, if_exists="append", index=False)

    if _table_empty(conn, "transaction_list"):
        df = _load_csv("transaction_list.csv")
        if df is not None:
            df = df.rename(columns={
                "Group": "group_name", "REQUEST_KIND": "request_kind",
                "DISPOSITION_DESC": "disposition_desc", "Diễn giải": "dien_giai"})
            df.to_sql("transaction_list", conn, if_exists="append", index=False)

    if _table_empty(conn, "subcon_list"):
        df = _load_csv("subcon_list.csv")
        if df is not None:
            rename_map = {"Group": "group_name", "CODE": "code",
                "STOCK DETAIL": "stock_detail", "Level subcon": "level_subcon",
                "Tên đầy đủ": "full_name", "Thong tin subcon": "full_name"}
            rename_map = {k: v for k, v in rename_map.items() if k in df.columns}
            df = df.rename(columns=rename_map)
            keep_cols = [c for c in ["code", "group_name", "stock_detail", "level_subcon", "full_name"] if c in df.columns]
            df = df[keep_cols]
            if "code" in df.columns:
                df = df.dropna(subset=["code"]).drop_duplicates("code")
            df.to_sql("subcon_list", conn, if_exists="append", index=False)

    if _table_empty(conn, "periods"):
        conn.execute(
            "INSERT INTO periods(period, status, opened_by, opened_at) VALUES (?,?,?,?)",
            ("2026-04", "open", "QUY", datetime.now().isoformat()))

    table_map = {
        "end_stock_nvl.csv": ("end_stock_nvl", {
            "Period": "period", "Item code": "item_code", "QTY begin": "qty_begin",
            "SUBCON": "subcon", "Type": "type", "Level subcon": "level_subcon",
            "Remark": "remark"}),
        "end_stock_tp.csv": ("end_stock_tp", {
            "Period": "period", "Prod code": "prod_code", "Sale code": "sale_code",
            "QTY begin": "qty_begin", "SUBCON": "subcon",
            "Level subcon": "level_subcon", "Remark": "remark"}),
        "end_stock_full_sub.csv": ("end_stock_full_sub", {
            "Period": "period", "PROD CODE": "prod_code", "SALE CODE": "sale_code",
            "QTY begin": "qty_begin", "SUBCON": "subcon",
            "Level subcon": "level_subcon", "Remark": "remark"}),
        "nk_nvl_in_cds.csv": ("nk_nvl_in_cds", {
            "Period": "period", "Số tờ khai": "so_to_khai", "Ngày TK": "ngay_tk",
            "Mã loại hình": "ma_loai_hinh", "Số hóa đơn": "so_hoa_don",
            "Mã NVL": "item_code", "Tên hàng": "ten_hang", "ĐVT": "dvt",
            "Type": "type", "QTY INPUT": "qty_input", "Ngày giao hàng": "ngay_giao_hang",
            "QTY RETURN": "qty_return", "Remark": "remark"}),
        "nk_nvl_in_actual.csv": ("nk_nvl_in_actual", {
            "Period": "period", "Ngày nhập kho": "ngay_nhap_kho", "SUB code": "sub_code",
            "Item code": "item_code", "Type": "type", "QTY ACTUAL": "qty_actual",
            "QTY RETURN": "qty_return", "Ghi chú": "ghi_chu"}),
        "subcon_out.csv": ("subcon_out", {
            "Period": "period", "Ngày tháng": "ngay", "Prod code": "prod_code",
            "Sale code": "sale_code", "Item code": "item_code", "TYPE": "type",
            "STOCK IN": "stock_in", "Level subcon": "level_subcon",
            "Transaction type": "trans_type", "QTY": "qty", "Remark": "remark"}),
        "subcon_in.csv": ("subcon_in", {
            "Period": "period", "Ngày tháng": "ngay", "HS code": "hs_code",
            "Prod code": "prod_code", "Sale code": "sale_code",
            "Item code": "item_code", "STOCK OUT": "stock_out",
            "Transaction type": "trans_type", "QTY": "qty",
            "Level subcon": "level_subcon", "Remark": "remark"}),
        "xk_tp_out_cds.csv": ("xk_tp_out_cds", {
            "Period": "period", "Số tờ khai": "so_to_khai", "Ngày TK": "ngay_tk",
            "Mã loại hình": "ma_loai_hinh", "Số hóa đơn": "so_hoa_don",
            "HS code": "hs_code", "Prod code": "prod_code", "Sale code": "sale_code",
            "ĐVT": "dvt", "QTY SALE": "qty_sale", "Ngày giao hàng": "ngay_giao_hang",
            "QTY RETURN": "qty_return", "Remark": "remark"}),
        "xk_tp_out_actual.csv": ("xk_tp_out_actual", {
            "Period": "period", "Ngày nhập kho": "ngay_nhap_kho", "Mã HS": "ma_hs",
            "Prod code": "prod_code", "Sale code": "sale_code",
            "ACTUAL QTY": "actual_qty", "Ghi chú": "ghi_chu"}),
        "out_ng.csv": ("out_ng", {
            "Period": "period", "Ngày tháng": "ngay", "HS code": "hs_code",
            "Prod code": "prod_code", "Sale code": "sale_code",
            "Item code": "item_code", "STOCK OUT - IN": "stock_out_in",
            "REQUEST_KIND": "request_kind", "Transaction type": "trans_type",
            "QTY": "qty", "Remark": "remark"}),
        "end_stock_hs_erp.csv": ("end_stock_hs_erp", {
            "Period": "period", "Item": "item_code", "Ending": "ending"}),
    }

    for csv_name, (table, colmap) in table_map.items():
        if not _table_empty(conn, table):
            continue
        df = _load_csv(csv_name)
        if df is None:
            continue
        keep = [c for c in colmap if c in df.columns]
        df = df[keep].rename(columns=colmap)
        num_cols = [c for c in df.columns if c in (
            "qty_begin", "qty_input", "qty_return", "qty_actual", "qty", "qty_sale",
            "actual_qty", "level_subcon", "ending")]
        for c in num_cols:
            df[c] = pd.to_numeric(df[c], errors="coerce").fillna(0)
        df.to_sql(table, conn, if_exists="append", index=False)

    conn.commit()
    conn.close()


# ── Template Excel import ──────────────────────────────────────────

TEMPLATE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "Report")

# (file, sheet) → (table, column_map, is_master)
SHEET_TABLE_MAP = {
    # Master data
    ("1.1 Danh muc.xlsx", "DM NVL"): ("dm_nvl", {
        "Type code": "type_code", "Item code": "item_code",
        "Spec": "spec", "Unit": "unit", "Đơn giá TK": "don_gia"}, True),
    ("1.1 Danh muc.xlsx", "DM TP"): ("dm_tp", {
        "Type code": "type_code", "Prod code": "prod_code",
        "Sale code": "sale_code", "Spec": "spec", "Unit": "unit",
        "Remark": "remark"}, True),
    ("1.1 Danh muc.xlsx", "BOM"): ("bom", {
        "Prod code": "prod_code", "Sale code": "sale_code",
        "Mã NVL": "item_code", "Type": "type",
        "Component Desc.": "component_desc", "ĐVT": "dvt",
        "BOM unit": "bom_unit", "Time Apply": "time_apply",
        "Remark": "remark"}, True),
    ("1.1 Danh muc.xlsx", "Transaction list"): ("transaction_list", {
        "Group": "group_name", "REQUEST_KIND": "request_kind",
        "DISPOSITION_DESC": "disposition_desc", "Diễn giải": "dien_giai"}, True),
    ("1.1 Danh muc.xlsx", "Subcon list"): ("subcon_list", {
        "Group": "group_name", "CODE": "code", "STOCK DETAIL": "stock_detail",
        "Level subcon": "level_subcon", "Tên đầy đủ": "full_name"}, True),
    ("CK_User.xlsx", "UserAccess"): ("users", {
        "UserID": "user_id", "Password": "password", "Role": "role",
        "Name": "name", "Email": "email"}, True),
    # Period transaction data (is_master=False)
    ("1.2 END_STOCK.xlsx", "NVL"): ("end_stock_nvl", {
        "Period": "period", "Item code": "item_code", "QTY begin": "qty_begin",
        "SUBCON": "subcon", "Type": "type", "Level subcon": "level_subcon",
        "Remark": "remark"}, False),
    ("1.2 END_STOCK.xlsx", "TP"): ("end_stock_tp", {
        "Period": "period", "Prod code": "prod_code", "Sale code": "sale_code",
        "QTY begin": "qty_begin", "SUBCON": "subcon",
        "Level subcon": "level_subcon", "Remark": "remark"}, False),
    ("1.2 END_STOCK.xlsx", "FULL SUB"): ("end_stock_full_sub", {
        "Period": "period", "PROD CODE": "prod_code", "SALE CODE": "sale_code",
        "QTY begin": "qty_begin", "SUBCON": "subcon",
        "Level subcon": "level_subcon", "Remark": "remark"}, False),
    ("1.2 END_STOCK.xlsx", "HS-ERP"): ("end_stock_hs_erp", {
        "Period": "period", "Item": "item_code", "Ending": "ending"}, False),
    ("2.1 NK NVL.xlsx", "IN CDS"): ("nk_nvl_in_cds", {
        "Period": "period", "Số tờ khai": "so_to_khai", "Ngày TK": "ngay_tk",
        "Mã loại hình": "ma_loai_hinh", "Số hóa đơn": "so_hoa_don",
        "Mã NVL": "item_code", "Tên hàng": "ten_hang", "ĐVT": "dvt",
        "Type": "type", "QTY INPUT": "qty_input", "Ngày giao hàng": "ngay_giao_hang",
        "QTY RETURN": "qty_return", "Remark": "remark"}, False),
    ("2.1 NK NVL.xlsx", "IN Actual"): ("nk_nvl_in_actual", {
        "Period": "period", "Ngày nhập kho": "ngay_nhap_kho",
        "SUB code": "sub_code", "Item code": "item_code", "Type": "type",
        "QTY ACTUAL": "qty_actual", "QTY RETURN": "qty_return",
        "Ghi chú": "ghi_chu"}, False),
    ("2.2 SUBCON IN-OUT.xlsx", "OUT"): ("subcon_out", {
        "Period": "period", "Ngày tháng": "ngay", "Prod code": "prod_code",
        "Sale code": "sale_code", "Item code": "item_code", "TYPE": "type",
        "STOCK IN": "stock_in", "Level subcon": "level_subcon",
        "Transaction type": "trans_type", "QTY": "qty", "Remark": "remark"}, False),
    ("2.2 SUBCON IN-OUT.xlsx", "IN"): ("subcon_in", {
        "Period": "period", "Ngày tháng": "ngay", "HS code": "hs_code",
        "Prod code": "prod_code", "Sale code": "sale_code",
        "Item code": "item_code", "STOCK OUT": "stock_out",
        "Transaction type": "trans_type", "QTY": "qty",
        "Level subcon": "level_subcon", "Remark": "remark"}, False),
    ("2.3 XK TP.xlsx", "OUT CDS"): ("xk_tp_out_cds", {
        "Period": "period", "Số tờ khai": "so_to_khai", "Ngày TK": "ngay_tk",
        "Mã loại hình": "ma_loai_hinh", "Số hóa đơn": "so_hoa_don",
        "HS code": "hs_code", "Prod code": "prod_code", "Sale code": "sale_code",
        "ĐVT": "dvt", "QTY SALE": "qty_sale", "Ngày giao hàng": "ngay_giao_hang",
        "QTY RETURN": "qty_return", "Remark": "remark"}, False),
    ("2.3 XK TP.xlsx", "OUT ACTUAL"): ("xk_tp_out_actual", {
        "Period": "period", "Ngày nhập kho": "ngay_nhap_kho", "Mã HS": "ma_hs",
        "Prod code": "prod_code", "Sale code": "sale_code",
        "ACTUAL QTY": "actual_qty", "Ghi chú": "ghi_chu"}, False),
    ("2.4 OUT NG.xlsx", "OUT NG"): ("out_ng", {
        "Period": "period", "Ngày tháng": "ngay", "HS code": "hs_code",
        "Prod code": "prod_code", "Sale code": "sale_code",
        "Item code": "item_code", "STOCK OUT - IN": "stock_out_in",
        "REQUEST_KIND": "request_kind", "Transaction type": "trans_type",
        "QTY": "qty", "Remark": "remark"}, False),
}


def import_from_template(conn, period: str, progress_callback=None) -> dict:
    """Đọc tất cả file Excel trong Template/, import vào DB.
    Returns dict {table: rows_imported}.
    """
    if not os.path.isdir(TEMPLATE_DIR):
        return {"error": f"Không tìm thấy thư mục {TEMPLATE_DIR}"}

    results = {}
    total = len(SHEET_TABLE_MAP)
    for i, ((fname, sheet_name), (table, colmap, is_master)) in enumerate(SHEET_TABLE_MAP.items()):
        path = os.path.join(TEMPLATE_DIR, fname)
        if not os.path.exists(path):
            results[f"{fname}/{sheet_name}"] = "file not found"
            continue

        try:
            df = pd.read_excel(path, sheet_name=sheet_name, dtype=str)
        except Exception as e:
            results[f"{fname}/{sheet_name}"] = f"read error: {e}"
            continue

        if df.empty:
            results[f"{fname}/{sheet_name}"] = 0
            continue

        df = df.dropna(how="all")
        # Map columns
        rename = {k: v for k, v in colmap.items() if k in df.columns}
        if not rename:
            results[f"{fname}/{sheet_name}"] = "no matching columns"
            continue
        df = df[list(rename.keys())].rename(columns=rename)

        # Coerce numeric columns
        table_cols = [c["name"] for c in conn.execute(f"PRAGMA table_info({table})").fetchall()]
        num_cols = {"qty_begin", "qty_input", "qty_return", "qty_actual", "qty",
                     "qty_sale", "actual_qty", "level_subcon", "ending", "don_gia", "bom_unit"}
        for c in df.columns:
            if c in num_cols or c in table_cols and any(x in c for x in ("qty", "level", "don", "bom", "ending", "actual")):
                df[c] = pd.to_numeric(df[c], errors="coerce").fillna(0)

        if is_master:
            conn.execute(f"DELETE FROM {table}")
            df.to_sql(table, conn, if_exists="append", index=False)
        else:
            conn.execute(f"DELETE FROM {table} WHERE period = ?", (period,))
            # Ensure period column
            if "period" in df.columns and period not in df["period"].values:
                pass  # keep as-is
            df.to_sql(table, conn, if_exists="append", index=False)

        results[f"{fname}/{sheet_name}"] = len(df)

        if progress_callback:
            progress_callback((i + 1) / total, f"{fname} › {sheet_name}: {len(df)} rows")

    conn.commit()
    return results


def sync_to_excel(table: str, period: str):
    """Sau khi upload data trên web, ghi ngược vào file Excel trong Template/."""
    # Tìm (file, sheet) tương ứng với table
    match = None
    for (fname, sheet_name), (tbl, colmap, is_master) in SHEET_TABLE_MAP.items():
        if tbl == table:
            match = (fname, sheet_name, colmap, is_master)
            break
    if not match:
        return  # không có mapping (bảng không cần sync)

    fname, sheet_name, colmap, is_master = match
    path = os.path.join(TEMPLATE_DIR, fname)
    os.makedirs(TEMPLATE_DIR, exist_ok=True)

    # Đọc dữ liệu từ DB
    conn = get_conn()
    if is_master:
        df = pd.read_sql(f"SELECT * FROM {table}", conn)
    else:
        df = pd.read_sql(f"SELECT * FROM {table} WHERE period = ?", conn, params=(period,))
    conn.close()

    if df.empty:
        return

    # Bỏ cột id
    if "id" in df.columns:
        df = df.drop(columns=["id"])

    # Reverse column mapping: DB → Excel
    reverse_map = {v: k for k, v in colmap.items()}
    df = df.rename(columns=reverse_map)
    # Chỉ giữ cột có trong mapping
    keep_cols = [reverse_map.get(c, c) for c in df.columns if c in reverse_map.values() or c not in colmap.values()]
    mapped_cols = {c: reverse_map[c] for c in df.columns if c in reverse_map}
    df = df[list(mapped_cols.keys())].rename(columns=reverse_map) if mapped_cols else df

    # Đọc/ghi Excel
    if os.path.exists(path):
        try:
            existing = pd.read_excel(path, sheet_name=None, dtype=str)
        except Exception:
            existing = {}
    else:
        existing = {}

    # Cập nhật sheet
    with pd.ExcelWriter(path, engine="openpyxl", mode="a" if os.path.exists(path) else "w",
                        if_sheet_exists="replace") as writer:
        # Ghi lại tất cả sheet cũ + cập nhật sheet hiện tại
        for sh_name, sh_df in existing.items():
            if sh_name == sheet_name:
                continue  # sẽ ghi đè sau
            sh_df.to_excel(writer, sheet_name=sh_name, index=False)
        df.to_excel(writer, sheet_name=sheet_name, index=False)


LAST_IMPORT_FILE = os.path.join(TEMPLATE_DIR, ".last_import")


def _template_max_mtime() -> float:
    """Lấy thời gian sửa đổi lớn nhất của các file Excel trong Template."""
    max_mtime = 0.0
    for (fname, _), _ in SHEET_TABLE_MAP.items():
        path = os.path.join(TEMPLATE_DIR, fname)
        if os.path.exists(path):
            mtime = os.path.getmtime(path)
            if mtime > max_mtime:
                max_mtime = mtime
    return max_mtime


def auto_import_if_changed(period: str) -> bool:
    """Tự động import từ Template nếu file Excel mới hơn lần import cuối.
    Returns True nếu có import mới.
    """
    if not os.path.isdir(TEMPLATE_DIR):
        return False

    max_mtime = _template_max_mtime()
    if max_mtime == 0:
        return False

    stored = 0.0
    if os.path.exists(LAST_IMPORT_FILE):
        with open(LAST_IMPORT_FILE) as f:
            try:
                stored = float(f.read().strip())
            except ValueError:
                stored = 0.0

    if max_mtime <= stored:
        return False  # không có thay đổi

    # Import
    conn = get_conn()
    try:
        log_action(conn, "system", "auto_import", f"Tự động import kỳ {period}")
    except Exception:
        pass
    import_from_template(conn, period)
    conn.close()

    # Ghi timestamp mới
    with open(LAST_IMPORT_FILE, "w") as f:
        f.write(str(max_mtime))

    return True


if __name__ == "__main__":
    init_db()
    seed_master_data()
    print(f"DB initialized at {DB_PATH}")
