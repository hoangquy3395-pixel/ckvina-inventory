import sqlite3
import pandas as pd
from datetime import datetime
from typing import Optional
import calc_engine as ce


def list_periods(conn: sqlite3.Connection) -> pd.DataFrame:
    return pd.read_sql("SELECT * FROM periods ORDER BY period", conn)


def get_open_period(conn: sqlite3.Connection) -> Optional[str]:
    df = pd.read_sql("SELECT * FROM periods WHERE status='open' ORDER BY period DESC LIMIT 1", conn)
    return df.iloc[0]["period"] if not df.empty else None


def next_period_code(period: str) -> str:
    y, m = map(int, period.split("-"))
    if m == 12:
        return f"{y+1}-01"
    return f"{y}-{m+1:02d}"


def open_new_period(conn: sqlite3.Connection, admin_id: str, carry_forward: bool = True) -> str:
    cur_period = get_open_period(conn)
    if cur_period is None:
        latest = pd.read_sql("SELECT MAX(period) as p FROM periods", conn).iloc[0]["p"]
        if latest is None:
            raise ValueError("Chưa có kỳ nào trong hệ thống.")
        cur_period = latest

    new_period = next_period_code(cur_period)
    existing = pd.read_sql("SELECT * FROM periods WHERE period=?", conn, params=(new_period,))
    if not existing.empty:
        raise ValueError(f"Kỳ {new_period} đã tồn tại.")

    conn.execute("UPDATE periods SET status='closed', closed_by=?, closed_at=? WHERE period=? AND status='open'",
                 (admin_id, datetime.now().isoformat(), cur_period))

    conn.execute(
        "INSERT INTO periods(period, status, opened_by, opened_at) VALUES (?,?,?,?)",
        (new_period, "open", admin_id, datetime.now().isoformat()))

    if carry_forward:
        _carry_forward(conn, cur_period, new_period)

    conn.commit()
    return new_period


def _carry_forward(conn: sqlite3.Connection, from_period: str, to_period: str):
    nxt = ce.calc_nxt_nvl(conn, from_period)
    if not nxt.empty:
        rows = nxt[["item_code", "ending_logic"]].rename(columns={"ending_logic": "qty_begin"})
        rows["period"] = to_period
        rows["subcon"] = "CKAD"
        rows["type"] = ""
        rows["level_subcon"] = 1
        rows["remark"] = "Auto carry-forward"
        rows.to_sql("end_stock_nvl", conn, if_exists="append", index=False)

    nxt_tp = ce.calc_nxt_tp(conn, from_period)
    if not nxt_tp.empty:
        rows = nxt_tp[["prod_code", "ending_logic"]].rename(columns={"ending_logic": "qty_begin"})
        rows["period"] = to_period
        rows["sale_code"] = rows["prod_code"]
        rows["subcon"] = "CKAD"
        rows["level_subcon"] = 1
        rows["remark"] = "Auto carry-forward"
        rows.to_sql("end_stock_tp", conn, if_exists="append", index=False)

    ns = ce.calc_nxt_sub(conn, from_period)
    if not ns.empty:
        rows = ns.rename(columns={"ending": "qty_begin"})
        rows["period"] = to_period
        rows["remark"] = "Auto carry-forward"
        rows = rows[["period", "prod_code", "sale_code", "qty_begin", "subcon", "remark"]]
        rows["level_subcon"] = rows["subcon"].map(
            {r["stock_detail"]: r["level_subcon"] for _, r in
             pd.read_sql("SELECT stock_detail, level_subcon FROM subcon_list", conn).iterrows()
             if r["level_subcon"] is not None}).fillna(1).astype(int)
        rows.to_sql("end_stock_full_sub", conn, if_exists="append", index=False)


def close_period(conn: sqlite3.Connection, period: str, admin_id: str):
    conn.execute("UPDATE periods SET status='closed', closed_by=?, closed_at=? WHERE period=?",
                 (admin_id, datetime.now().isoformat(), period))
    conn.commit()


def reopen_period(conn: sqlite3.Connection, period: str, admin_id: str):
    conn.execute("UPDATE periods SET status='open' WHERE period=?", (period,))
    conn.commit()
