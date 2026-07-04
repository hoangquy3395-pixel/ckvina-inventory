import sqlite3
import pandas as pd
from typing import Optional


def _read(conn: sqlite3.Connection, table: str, period: Optional[str] = None) -> pd.DataFrame:
    if period:
        return pd.read_sql(f"SELECT * FROM {table} WHERE period = ?", conn, params=(period,))
    return pd.read_sql(f"SELECT * FROM {table}", conn)


def _prev_period(period: str) -> str:
    y, m = map(int, period.split("-"))
    if m == 1:
        return f"{y-1}-12"
    return f"{y}-{m-1:02d}"


def get_master(conn: sqlite3.Connection):
    dm_nvl = _read(conn, "dm_nvl")
    dm_tp = _read(conn, "dm_tp")
    bom = _read(conn, "bom")
    return dm_nvl, dm_tp, bom


def check_new_codes(conn: sqlite3.Connection, period: str) -> pd.DataFrame:
    dm_nvl, dm_tp, _ = get_master(conn)
    known_nvl = set(dm_nvl["item_code"].dropna())
    known_tp = set(dm_tp["prod_code"].dropna())

    warnings = []

    def scan(table: str, col: str, code_type: str, known_set: set):
        df = _read(conn, table, period)
        if df.empty or col not in df.columns:
            return
        codes = df[col].dropna().unique()
        for c in codes:
            if c and c not in known_set:
                warnings.append({"code": c, "code_type": code_type,
                                  "source_sheet": table, "period": period})

    scan("nk_nvl_in_cds", "item_code", "NVL", known_nvl)
    scan("nk_nvl_in_actual", "item_code", "NVL", known_nvl)
    scan("subcon_out", "item_code", "NVL", known_nvl)
    scan("subcon_out", "prod_code", "TP", known_tp)
    scan("subcon_in", "prod_code", "TP", known_tp)
    scan("xk_tp_out_cds", "prod_code", "TP", known_tp)
    scan("out_ng", "item_code", "NVL", known_nvl)
    scan("out_ng", "prod_code", "TP", known_tp)

    if not warnings:
        return pd.DataFrame(columns=["code", "code_type", "source_sheet", "period"])
    return pd.DataFrame(warnings).drop_duplicates()


def calc_nvl_gap(conn: sqlite3.Connection, period: str) -> pd.DataFrame:
    in_cds = _read(conn, "nk_nvl_in_cds", period)
    subcon_out = _read(conn, "subcon_out", period)
    _, _, bom = get_master(conn)

    in_cds_sum = (in_cds.groupby(["item_code", "type"])["qty_input"]
                  .sum().reset_index().rename(columns={"qty_input": "in_cds"})) \
        if not in_cds.empty else pd.DataFrame(columns=["item_code", "type", "in_cds"])

    direct = subcon_out[(subcon_out["trans_type"] == "SUB OUT") &
                         (subcon_out["item_code"].fillna("") != "")] \
        if not subcon_out.empty else pd.DataFrame()
    giao_nvl = (direct.groupby("item_code")["qty"].sum().reset_index()
                .rename(columns={"qty": "giao_nvl"})) if not direct.empty \
        else pd.DataFrame(columns=["item_code", "giao_nvl"])

    full_sub = subcon_out[(subcon_out["trans_type"] == "SUB OUT") &
                           (subcon_out["prod_code"].fillna("") != "") &
                           (subcon_out["item_code"].fillna("") == "")] \
        if not subcon_out.empty else pd.DataFrame()
    if not full_sub.empty and not bom.empty:
        full_sub_x = full_sub.drop(columns=["item_code"], errors="ignore")
        merged = full_sub_x.merge(bom, on="prod_code", how="left")
        merged["mat_qty"] = merged["qty"] * merged["bom_unit"].fillna(0)
        giao_sub_dongbo = (merged.groupby("item_code")["mat_qty"].sum()
                            .reset_index().rename(columns={"mat_qty": "giao_sub_dongbo"}))
    else:
        giao_sub_dongbo = pd.DataFrame(columns=["item_code", "giao_sub_dongbo"])

    out = in_cds_sum.merge(giao_nvl, on="item_code", how="outer") \
                     .merge(giao_sub_dongbo, on="item_code", how="outer")
    out[["in_cds", "giao_nvl", "giao_sub_dongbo"]] = out[
        ["in_cds", "giao_nvl", "giao_sub_dongbo"]].fillna(0)
    out["gap_qty"] = out["in_cds"] - out["giao_nvl"] - out["giao_sub_dongbo"]
    out["period"] = period
    return out[["period", "item_code", "type", "in_cds", "giao_nvl",
                "giao_sub_dongbo", "gap_qty"]]


def calc_nvl_remain_delivery(conn: sqlite3.Connection, period: str, _cache: Optional[dict] = None) -> pd.DataFrame:
    _cache = _cache if _cache is not None else {}
    if period in _cache:
        return _cache[period]

    in_cds = _read(conn, "nk_nvl_in_cds", period)
    in_actual = _read(conn, "nk_nvl_in_actual", period)
    gap_df = calc_nvl_gap(conn, period)
    dm_nvl, _, _ = get_master(conn)

    items = set(dm_nvl["item_code"]) | set(gap_df["item_code"].dropna()) \
        | set(in_cds["item_code"].dropna() if not in_cds.empty else [])
    items = sorted(x for x in items if x)

    in_cds_sum = in_cds.groupby("item_code")["qty_input"].sum() if not in_cds.empty else pd.Series(dtype=float)
    actual_sum = in_actual.groupby("item_code")["qty_actual"].sum() if not in_actual.empty else pd.Series(dtype=float)
    delivered = gap_df.set_index("item_code")[["giao_nvl", "giao_sub_dongbo"]].sum(axis=1) \
        if not gap_df.empty else pd.Series(dtype=float)

    prev_periods = pd.read_sql("SELECT period FROM periods WHERE period < ? ORDER BY period DESC LIMIT 1",
                                conn, params=(period,))
    if not prev_periods.empty:
        prev_df = calc_nvl_remain_delivery(conn, prev_periods.iloc[0]["period"], _cache)
        gap_begin = prev_df.set_index("item_code")["gap_end"]
    else:
        gap_begin = pd.Series(dtype=float)

    rows = []
    for it in items:
        gb = float(gap_begin.get(it, 0))
        ic = float(in_cds_sum.get(it, 0))
        actual = float(actual_sum.get(it, 0))
        actual_gap = actual - ic
        qty_in_month = gb + ic + actual_gap
        deliv = float(delivered.get(it, 0))
        gap_end = qty_in_month - deliv
        rows.append({"period": period, "item_code": it, "gap_begin": gb,
                      "in_cds": ic, "actual_gap_qty": actual_gap,
                      "qty_in_month": qty_in_month, "gap_end": gap_end})
    result = pd.DataFrame(rows)
    _cache[period] = result
    return result


def calc_subcon_pivot(conn: sqlite3.Connection, period: str) -> pd.DataFrame:
    begin = _read(conn, "end_stock_full_sub", period)
    out_s = _read(conn, "subcon_out", period)
    inn = _read(conn, "subcon_in", period)

    rows = []
    if not begin.empty:
        g = begin.groupby(["prod_code", "sale_code", "subcon"])["qty_begin"].sum().reset_index()
        for _, r in g.iterrows():
            rows.append({"period": period, "prod_code": r["prod_code"],
                         "sale_code": r["sale_code"], "subcon": r["subcon"],
                         "trans_type": "Begin", "qty": r["qty_begin"]})
    if not out_s.empty:
        fs = out_s[(out_s["trans_type"] == "SUB OUT") & (out_s["prod_code"].fillna("") != "") &
                  (out_s["item_code"].fillna("") == "")]
        if not fs.empty:
            g = fs.groupby(["prod_code", "sale_code", "stock_in"])["qty"].sum().reset_index()
            g = g.rename(columns={"stock_in": "subcon"})
            for _, r in g.iterrows():
                rows.append({"period": period, "prod_code": r["prod_code"],
                             "sale_code": r["sale_code"], "subcon": r["subcon"],
                             "trans_type": "SUB OUT", "qty": r["qty"]})
    if not inn.empty:
        si = inn[(inn["trans_type"] == "SUB IN") & (inn["prod_code"].fillna("") != "")]
        if not si.empty:
            g = si.groupby(["prod_code", "sale_code", "stock_out"])["qty"].sum().reset_index()
            g = g.rename(columns={"stock_out": "subcon"})
            for _, r in g.iterrows():
                rows.append({"period": period, "prod_code": r["prod_code"],
                             "sale_code": r["sale_code"], "subcon": r["subcon"],
                             "trans_type": "SUB IN", "qty": r["qty"]})
    return pd.DataFrame(rows, columns=["period", "prod_code", "sale_code", "subcon", "trans_type", "qty"])


def calc_nxt_sub(conn: sqlite3.Connection, period: str) -> pd.DataFrame:
    pv = calc_subcon_pivot(conn, period)
    if pv.empty:
        return pd.DataFrame(columns=["period", "prod_code", "sale_code", "begin", "sub_out", "sub_in", "ending"])

    wide = pv.pivot_table(index=["prod_code", "sale_code", "subcon"], columns="trans_type",
                           values="qty", aggfunc="sum", fill_value=0).reset_index()
    for c in ["Begin", "SUB OUT", "SUB IN"]:
        if c not in wide.columns:
            wide[c] = 0
    wide["ending"] = wide["Begin"] + wide["SUB IN"] - wide["SUB OUT"]
    wide["period"] = period
    wide = wide.rename(columns={"Begin": "begin", "SUB OUT": "sub_out", "SUB IN": "sub_in"})
    return wide[["period", "prod_code", "sale_code", "subcon", "begin", "sub_out", "sub_in", "ending"]]


def calc_nxt_sub_wide(conn: sqlite3.Connection, period: str) -> pd.DataFrame:
    sub = calc_nxt_sub(conn, period)
    if sub.empty:
        return pd.DataFrame()

    dm_tp = _read(conn, "dm_tp")
    sub = sub.merge(dm_tp[["prod_code", "spec", "unit"]], on="prod_code", how="left")

    subcons = sorted(sub["subcon"].dropna().unique())
    base_cols = ["period", "prod_code", "sale_code", "spec", "unit", "remark"]

    rows = []
    for (pc, sc), grp in sub.groupby(["prod_code", "sale_code"]):
        row = {"period": period, "prod_code": pc, "sale_code": sc,
               "spec": grp["spec"].iloc[0] if "spec" in grp else "",
               "unit": grp["unit"].iloc[0] if "unit" in grp else "",
               "remark": ""}
        tot_begin = 0.0
        tot_out = 0.0
        tot_in = 0.0
        for scon in subcons:
            m = grp[grp["subcon"] == scon]
            if not m.empty:
                b = float(m["begin"].iloc[0])
                o = float(m["sub_out"].iloc[0])
                i = float(m["sub_in"].iloc[0])
                e = float(m["ending"].iloc[0])
            else:
                b = o = i = e = 0.0
            row[f"begin_{scon}"] = b
            row[f"sub_out_{scon}"] = o
            row[f"sub_in_{scon}"] = i
            row[f"ending_{scon}"] = e
            tot_begin += b
            tot_out += o
            tot_in += i
        row["begin"] = tot_begin
        row["sub_out"] = tot_out
        row["sub_in"] = tot_in
        row["ending"] = tot_begin + tot_in - tot_out
        rows.append(row)

    result = pd.DataFrame(rows)
    col_order = ["period", "prod_code", "sale_code", "spec", "unit",
                 "begin", "sub_out", "sub_in", "ending"]
    for scon in subcons:
        for suff in ["begin", "sub_out", "sub_in", "ending"]:
            col_order.append(f"{suff}_{scon}")
    col_order.append("remark")
    for c in col_order:
        if c not in result.columns:
            result[c] = 0.0
    return result[col_order]


def calc_convert_sub_to_mat(conn: sqlite3.Connection, period: str) -> pd.DataFrame:
    pv = calc_subcon_pivot(conn, period)
    _, _, bom = get_master(conn)
    if pv.empty or bom.empty:
        return pd.DataFrame(columns=["period", "prod_code", "item_code", "subcon",
                                       "trans_type", "fg_qty", "bom_unit", "total_mat_qty"])
    merged = pv.merge(bom, on="prod_code", how="left")
    merged["total_mat_qty"] = merged["qty"] * merged["bom_unit"].fillna(0)
    merged = merged.rename(columns={"qty": "fg_qty"})
    cols = ["period", "prod_code", "item_code", "subcon", "trans_type", "fg_qty",
            "bom_unit", "total_mat_qty"]
    return merged[cols].dropna(subset=["item_code"])


def calc_nxt_convert_mat(conn: sqlite3.Connection, period: str) -> pd.DataFrame:
    dm_nvl, _, _ = get_master(conn)
    begin_nvl = _read(conn, "end_stock_nvl", period)
    conv = calc_convert_sub_to_mat(conn, period)
    subcon_out_raw = _read(conn, "subcon_out", period)
    out_ng_raw = _read(conn, "out_ng", period)
    end_full_sub = _read(conn, "end_stock_full_sub", period)

    ALL_SUBCONS = ["CKAD", "CKTL", "CKVB", "CKTN", "CKMT", "CKAL"]

    # --- 1. NVL begin per item per subcon ---
    nvl_begin = (begin_nvl.groupby(["item_code", "subcon"])["qty_begin"].sum()
                 if not begin_nvl.empty else pd.Series(dtype=float))

    # --- 2. Convert SUB to MAT per item per subcon ---
    def conv_pick(tt: str):
        if conv.empty:
            return pd.Series(dtype=float)
        d = conv[conv["trans_type"] == tt]
        return d.groupby(["item_code", "subcon"])["total_mat_qty"].sum()

    conv_begin = conv_pick("Begin")
    conv_sub_out = conv_pick("SUB OUT")
    conv_sub_in = conv_pick("SUB IN")
    conv_sub_return = conv_pick("SUB RETURN")

    # --- 3. OUT NVL: direct NVL sent to subcon ---
    out_nvl = pd.Series(dtype=float)
    if not subcon_out_raw.empty:
        d = subcon_out_raw[(subcon_out_raw["item_code"].fillna("") != "") &
                           (subcon_out_raw["trans_type"] == "SUB OUT")]
        if not d.empty:
            out_nvl = d.groupby(["item_code", "stock_in"])["qty"].sum()

    # --- 4. Return NVL: NVL returned via out_ng (SUB RETURN) ---
    return_nvl = pd.Series(dtype=float)
    if not out_ng_raw.empty:
        d = out_ng_raw[(out_ng_raw["item_code"].fillna("") != "") &
                       (out_ng_raw["trans_type"] == "SUB RETURN")]
        if not d.empty:
            return_nvl = d.groupby(["item_code", "stock_out_in"])["qty"].sum()

    # --- 5. Build per-item per-subcon rows ---
    items = sorted(x for x in dm_nvl["item_code"].dropna().unique() if x)

    rows = []
    for item in items:
        row = {"period": period, "item_code": item}
        # Get spec/unit/type from dm_nvl
        spec_row = dm_nvl[dm_nvl["item_code"] == item]
        row["spec"] = spec_row["spec"].iloc[0] if len(spec_row) else ""
        row["unit"] = spec_row["unit"].iloc[0] if len(spec_row) else ""
        row["type"] = spec_row["type_code"].iloc[0] if len(spec_row) else ""

        totals = {k: 0.0 for k in ("begin", "sub_out", "sub_return",
                                    "out_nvl", "return_nvl", "sub_in", "ending")}

        for scon in ALL_SUBCONS:
            b = float(nvl_begin.get((item, scon), 0)) + float(conv_begin.get((item, scon), 0))
            so = float(conv_sub_out.get((item, scon), 0))
            sr = float(conv_sub_return.get((item, scon), 0))
            on = float(out_nvl.get((item, scon), 0))
            rn = float(return_nvl.get((item, scon), 0))
            si = float(conv_sub_in.get((item, scon), 0))
            end = b + so - sr + on - rn - si

            # Add TOTAL to the subcon keyed column
            if scon == "CKAD":
                row[f"begin_{scon}"] = b
                row[f"sub_out_{scon}"] = so
                row[f"sub_return_{scon}"] = sr
                row[f"out_nvl_{scon}"] = on
                row[f"return_nvl_{scon}"] = rn
                row[f"sub_in_{scon}"] = si
                row[f"ending_{scon}"] = end
            else:
                row[f"begin_{scon}"] = b
                row[f"sub_out_{scon}"] = so
                row[f"sub_return_{scon}"] = sr
                row[f"out_nvl_{scon}"] = on
                row[f"return_nvl_{scon}"] = rn
                row[f"sub_in_{scon}"] = si
                row[f"ending_{scon}"] = end

            totals["begin"] += b
            totals["sub_out"] += so
            totals["sub_return"] += sr
            totals["out_nvl"] += on
            totals["return_nvl"] += rn
            totals["sub_in"] += si
            totals["ending"] += end

        row["begin"] = totals["begin"]
        row["sub_out"] = totals["sub_out"]
        row["sub_return"] = totals["sub_return"]
        row["out_nvl"] = totals["out_nvl"]
        row["return_nvl"] = totals["return_nvl"]
        row["sub_in"] = totals["sub_in"]
        row["ending"] = totals["ending"]

        row["remark"] = ""
        rows.append(row)

    result = pd.DataFrame(rows)

    # Ensure all columns exist
    col_order = ["period", "item_code", "spec", "unit", "type",
                 "begin", "sub_out", "sub_return", "out_nvl", "return_nvl", "sub_in", "ending"]
    for scon in ALL_SUBCONS:
        for suff in ["begin", "sub_out", "sub_return", "out_nvl", "return_nvl", "sub_in", "ending"]:
            col_order.append(f"{suff}_{scon}")
    col_order += ["remark"]

    for c in col_order:
        if c not in result.columns:
            result[c] = 0.0

    return result[col_order]


def calc_nxt_sub_detail(conn: sqlite3.Connection, period: str) -> pd.DataFrame:
    sub = calc_nxt_sub(conn, period)
    if sub.empty:
        return sub
    dm_tp = _read(conn, "dm_tp")
    sub = sub.merge(dm_tp[["prod_code", "spec", "unit"]], on="prod_code", how="left")
    return sub[["period", "prod_code", "sale_code", "spec", "unit",
                 "subcon", "begin", "sub_out", "sub_in", "ending"]]


def calc_nxt_convert_mat_detail(conn: sqlite3.Connection, period: str) -> pd.DataFrame:
    dm_nvl, _, _ = get_master(conn)
    begin_nvl = _read(conn, "end_stock_nvl", period)
    conv = calc_convert_sub_to_mat(conn, period)
    subcon_out_raw = _read(conn, "subcon_out", period)
    out_ng_raw = _read(conn, "out_ng", period)
    end_full_sub = _read(conn, "end_stock_full_sub", period)

    ALL_SUBCONS = ["CKAD", "CKTL", "CKVB", "CKTN", "CKMT", "CKAL"]

    # --- NVL begin per item per subcon ---
    nvl_begin = (begin_nvl.groupby(["item_code", "subcon"])["qty_begin"].sum()
                 if not begin_nvl.empty else pd.Series(dtype=float))

    # --- Convert SUB to MAT per item per subcon ---
    def conv_pick(tt: str):
        if conv.empty:
            return pd.Series(dtype=float)
        d = conv[conv["trans_type"] == tt]
        return d.groupby(["item_code", "subcon"])["total_mat_qty"].sum()

    conv_begin = conv_pick("Begin")
    conv_sub_out = conv_pick("SUB OUT")
    conv_sub_in = conv_pick("SUB IN")
    conv_sub_return = conv_pick("SUB RETURN")

    # --- OUT NVL: direct NVL sent to subcon ---
    out_nvl = pd.Series(dtype=float)
    if not subcon_out_raw.empty:
        d = subcon_out_raw[(subcon_out_raw["item_code"].fillna("") != "") &
                           (subcon_out_raw["trans_type"] == "SUB OUT")]
        if not d.empty:
            out_nvl = d.groupby(["item_code", "stock_in"])["qty"].sum()

    # --- Return NVL: NVL returned via out_ng (SUB RETURN) ---
    return_nvl = pd.Series(dtype=float)
    if not out_ng_raw.empty:
        d = out_ng_raw[(out_ng_raw["item_code"].fillna("") != "") &
                       (out_ng_raw["trans_type"] == "SUB RETURN")]
        if not d.empty:
            return_nvl = d.groupby(["item_code", "stock_out_in"])["qty"].sum()

    # --- SUB totals for footer ---
    sub_total_raw = pd.Series(dtype=float)
    sub_nosync = pd.Series(dtype=float)
    if not end_full_sub.empty:
        sub_total_raw = end_full_sub.groupby("prod_code")["qty_begin"].sum()
        _, _, bom = get_master(conn)
        if not bom.empty:
            prods_with_bom = set(bom["prod_code"].dropna())
            nosync = end_full_sub[~end_full_sub["prod_code"].isin(prods_with_bom)]
            sub_nosync = (nosync.groupby("prod_code")["qty_begin"].sum()
                          if not nosync.empty else pd.Series(dtype=float))

    _, _, bom = get_master(conn)

    items = sorted(x for x in dm_nvl["item_code"].dropna().unique() if x)

    rows = []
    for item in items:
        spec_row = dm_nvl[dm_nvl["item_code"] == item]
        spec = spec_row["spec"].iloc[0] if len(spec_row) else ""
        unit = spec_row["unit"].iloc[0] if len(spec_row) else ""
        typ = spec_row["type_code"].iloc[0] if len(spec_row) else ""

        # Footer columns (item-level)
        total_sub_val = sum(float(conv_begin.get((item, s), 0)) for s in ALL_SUBCONS)
        nosync_qty = 0.0
        convert_qty = 0.0
        if not bom.empty:
            bom_items = bom[bom["item_code"] == item]
            for _, br in bom_items.iterrows():
                pc = br["prod_code"]
                nosync_qty += float(sub_nosync.get(pc, 0))
                raw_qty = float(sub_total_raw.get(pc, 0))
                bom_unit = float(br["bom_unit"]) if pd.notna(br.get("bom_unit", 0)) else 0
                convert_qty += raw_qty * bom_unit
        gap_val = total_sub_val - convert_qty
        remark = ""

        for scon in ALL_SUBCONS:
            b = float(nvl_begin.get((item, scon), 0)) + float(conv_begin.get((item, scon), 0))
            so = float(conv_sub_out.get((item, scon), 0))
            sr = float(conv_sub_return.get((item, scon), 0))
            on = float(out_nvl.get((item, scon), 0))
            rn = float(return_nvl.get((item, scon), 0))
            si = float(conv_sub_in.get((item, scon), 0))
            end = b + so - sr + on - rn - si

            rows.append({
                "period": period, "item_code": item, "spec": spec,
                "unit": unit, "type": typ, "subcon": scon,
                "begin": b, "sub_out": so, "sub_return": sr,
                "out_nvl": on, "return_nvl": rn, "sub_in": si,
                "ending": end,
                "total_sub": total_sub_val, "ton_dau_sub_kd": nosync_qty,
                "convert": convert_qty, "gap": gap_val, "remark": remark,
            })

    return pd.DataFrame(rows, columns=[
        "period", "item_code", "spec", "unit", "type", "subcon",
        "begin", "sub_out", "sub_return", "out_nvl", "return_nvl", "sub_in", "ending",
        "total_sub", "ton_dau_sub_kd", "convert", "gap", "remark",
    ])


def calc_tp_gap(conn: sqlite3.Connection, period: str) -> pd.DataFrame:
    out_cds = _read(conn, "xk_tp_out_cds", period)
    out_actual = _read(conn, "xk_tp_out_actual", period)
    cds_sum = out_cds.groupby(["prod_code", "sale_code"])["qty_sale"].sum().reset_index() \
        if not out_cds.empty else pd.DataFrame(columns=["prod_code", "sale_code", "qty_sale"])
    act_sum = out_actual.groupby(["prod_code", "sale_code"])["actual_qty"].sum().reset_index() \
        if not out_actual.empty else pd.DataFrame(columns=["prod_code", "sale_code", "actual_qty"])
    merged = cds_sum.merge(act_sum, on=["prod_code", "sale_code"], how="outer").fillna(0)
    merged["gap_qty"] = merged.get("actual_qty", 0) - merged.get("qty_sale", 0)
    merged["period"] = period
    merged = merged.rename(columns={"qty_sale": "cds_qty", "actual_qty": "actual_qty"})
    return merged[["period", "prod_code", "sale_code", "cds_qty", "actual_qty", "gap_qty"]]


def calc_tp_remain_delivery(conn: sqlite3.Connection, period: str, _cache: Optional[dict] = None) -> pd.DataFrame:
    _cache = _cache if _cache is not None else {}
    if period in _cache:
        return _cache[period]

    gap_df = calc_tp_gap(conn, period)
    dm_tp = _read(conn, "dm_tp")
    prods = set(dm_tp["prod_code"]) | set(gap_df["prod_code"].dropna())
    prods = sorted(x for x in prods if x)

    prev_periods = pd.read_sql("SELECT period FROM periods WHERE period < ? ORDER BY period DESC LIMIT 1",
                                conn, params=(period,))
    if not prev_periods.empty:
        prev_df = calc_tp_remain_delivery(conn, prev_periods.iloc[0]["period"], _cache)
        gap_begin = prev_df.set_index("prod_code")["gap_end"]
    else:
        gap_begin = pd.Series(dtype=float)

    gap_idx = gap_df.set_index("prod_code") if not gap_df.empty else pd.DataFrame()

    rows = []
    for p in prods:
        gb = float(gap_begin.get(p, 0))
        cds = float(gap_idx["cds_qty"].get(p, 0)) if not gap_idx.empty else 0
        actual_gap = float(gap_idx["gap_qty"].get(p, 0)) if not gap_idx.empty else 0
        qty_in_month = gb + cds + actual_gap
        gap_end = qty_in_month - cds
        rows.append({"period": period, "prod_code": p, "gap_begin": gb, "out_cds": cds,
                      "actual_gap_qty": actual_gap, "qty_in_month": qty_in_month, "gap_end": gap_end})
    result = pd.DataFrame(rows)
    _cache[period] = result
    return result


def calc_nxt_nvl(conn: sqlite3.Connection, period: str) -> pd.DataFrame:
    dm_nvl, _, _ = get_master(conn)
    begin = _read(conn, "end_stock_nvl", period)
    in_cds = _read(conn, "nk_nvl_in_cds", period)
    out_ng = _read(conn, "out_ng", period)
    remain = calc_nvl_remain_delivery(conn, period)
    gap_df = calc_nvl_gap(conn, period)

    begin_sum = begin.groupby("item_code")["qty_begin"].sum() if not begin.empty else pd.Series(dtype=float)
    in_cds_sum = in_cds.groupby("item_code")["qty_input"].sum() if not in_cds.empty else pd.Series(dtype=float)
    return_hs = in_cds.groupby("item_code")["qty_return"].sum() if not in_cds.empty else pd.Series(dtype=float)
    in_other = out_ng[out_ng["request_kind"] == "IN"].groupby("item_code")["qty"].sum() \
        if not out_ng.empty else pd.Series(dtype=float)
    out_other = out_ng[out_ng["request_kind"] == "OUT"].groupby("item_code")["qty"].sum() \
        if not out_ng.empty else pd.Series(dtype=float)
    gap_actual = remain.set_index("item_code")["actual_gap_qty"] if not remain.empty else pd.Series(dtype=float)
    gap_remain = remain.set_index("item_code")["gap_end"] if not remain.empty else pd.Series(dtype=float)
    out_production = (gap_df.set_index("item_code")[["giao_nvl", "giao_sub_dongbo"]].sum(axis=1)
                       if not gap_df.empty else pd.Series(dtype=float))

    items = set(dm_nvl["item_code"])
    for s in [begin_sum, in_cds_sum, return_hs, in_other, out_other, gap_actual, out_production]:
        items |= set(s.index)
    items = sorted(x for x in items if x)

    rows = []
    for it in items:
        b = float(begin_sum.get(it, 0))
        ic = float(in_cds_sum.get(it, 0))
        gap = float(gap_actual.get(it, 0))
        rin = float(in_other.get(it, 0))
        rout = float(out_other.get(it, 0))
        ret = float(return_hs.get(it, 0))
        out_prod = float(out_production.get(it, 0))
        ending = b + ic + gap + rin - rout - ret - out_prod
        rows.append({"period": period, "item_code": it, "begin_mat": b, "in_cds": ic,
                      "gap_actual_delivery": gap, "out_production": out_prod,
                      "return_mat_to_hs": ret,
                      "in_other": rin, "out_other": rout, "ending_logic": ending,
                      "gap_remain_delivery": float(gap_remain.get(it, 0))})
    return pd.DataFrame(rows)


def calc_nxt_tp(conn: sqlite3.Connection, period: str) -> pd.DataFrame:
    dm_tp = _read(conn, "dm_tp")
    begin = _read(conn, "end_stock_tp", period)
    subcon_in = _read(conn, "subcon_in", period)
    out_cds = _read(conn, "xk_tp_out_cds", period)
    out_ng = _read(conn, "out_ng", period)
    remain = calc_tp_remain_delivery(conn, period)

    begin_sum = begin.groupby("prod_code")["qty_begin"].sum() if not begin.empty else pd.Series(dtype=float)
    prod_qty = subcon_in[subcon_in["trans_type"] == "SUB IN"].groupby("prod_code")["qty"].sum() \
        if not subcon_in.empty else pd.Series(dtype=float)
    sale_cds = out_cds.groupby("prod_code")["qty_sale"].sum() if not out_cds.empty else pd.Series(dtype=float)
    sale_return = out_cds.groupby("prod_code")["qty_return"].sum() if not out_cds.empty else pd.Series(dtype=float)
    out_other = out_ng[(out_ng["request_kind"] == "OUT") & (out_ng["prod_code"].fillna("") != "")] \
        .groupby("prod_code")["qty"].sum() if not out_ng.empty else pd.Series(dtype=float)
    in_other = out_ng[(out_ng["request_kind"] == "IN") & (out_ng["prod_code"].fillna("") != "")] \
        .groupby("prod_code")["qty"].sum() if not out_ng.empty else pd.Series(dtype=float)
    gap_actual = remain.set_index("prod_code")["actual_gap_qty"] if not remain.empty else pd.Series(dtype=float)
    gap_remain = remain.set_index("prod_code")["gap_end"] if not remain.empty else pd.Series(dtype=float)

    prods = set(dm_tp["prod_code"])
    for s in [begin_sum, prod_qty, sale_cds, gap_actual]:
        prods |= set(s.index)
    prods = sorted(x for x in prods if x)

    rows = []
    for p in prods:
        b = float(begin_sum.get(p, 0))
        prodq = float(prod_qty.get(p, 0)) + float(in_other.get(p, 0))
        sale = float(sale_cds.get(p, 0))
        gap = float(gap_actual.get(p, 0))
        ret = float(sale_return.get(p, 0))
        scrap = float(out_other.get(p, 0))
        ending = b + prodq + gap - sale - ret - scrap
        rows.append({"period": period, "prod_code": p, "begin_fg": b, "prod_qty": prodq,
                      "sale_to_hs_cds": sale, "gap_sale_actual": gap, "sale_return": ret,
                      "out_other_scrap": scrap, "ending_logic": ending,
                      "gap_delivery_remain": float(gap_remain.get(p, 0))})
    return pd.DataFrame(rows)


def calc_convert_tp_to_mat(conn: sqlite3.Connection, period: str) -> pd.DataFrame:
    nxt_tp = calc_nxt_tp(conn, period)
    _, _, bom = get_master(conn)
    if nxt_tp.empty or bom.empty:
        return pd.DataFrame(columns=["period", "prod_code", "item_code", "trans_type", "qty",
                                       "bom_unit", "total_mat_qty"])
    long_rows = []
    col_map = {"begin_fg": "Begin", "sale_to_hs_cds": "Sale to HS CDS",
               "gap_sale_actual": "GAP SALE ACTUAL", "sale_return": "Sale return",
               "out_other_scrap": "Out other (Scrap, ADJ)", "ending_logic": "Ending logic",
               "gap_delivery_remain": "Gap delivery remain"}
    for _, r in nxt_tp.iterrows():
        for col, label in col_map.items():
            long_rows.append({"prod_code": r["prod_code"], "trans_type": label, "qty": r[col]})
    long_df = pd.DataFrame(long_rows)
    merged = long_df.merge(bom, on="prod_code", how="left")
    merged["total_mat_qty"] = merged["qty"] * merged["bom_unit"].fillna(0)
    merged["period"] = period
    return merged[["period", "prod_code", "item_code", "trans_type", "qty",
                    "bom_unit", "total_mat_qty"]].dropna(subset=["item_code"])


def calc_balance_sheet(conn: sqlite3.Connection, period: str) -> pd.DataFrame:
    dm_nvl = _read(conn, "dm_nvl")
    nxt_nvl = calc_nxt_nvl(conn, period)
    conv = calc_convert_tp_to_mat(conn, period)
    hs_erp = _read(conn, "end_stock_hs_erp", period)

    def pick(trans_type: str):
        if conv.empty:
            return pd.Series(dtype=float)
        d = conv[conv["trans_type"] == trans_type]
        return d.groupby("item_code")["total_mat_qty"].sum()

    begin_fg = pick("Begin")
    sale_fg = pick("Sale to HS CDS")
    gap_sale_actual = pick("GAP SALE ACTUAL")
    sale_return = pick("Sale return")
    scrap_fg = pick("Out other (Scrap, ADJ)")
    ending_fg = pick("Ending logic")
    gap_fg_remain = pick("Gap delivery remain")

    hs_ending = hs_erp.groupby("item_code")["ending"].sum() if not hs_erp.empty else pd.Series(dtype=float)

    nxt_nvl_idx = nxt_nvl.set_index("item_code") if not nxt_nvl.empty else pd.DataFrame()

    items = set(dm_nvl["item_code"])
    rows = []
    for i, it in enumerate(sorted(items), start=1):
        begin_mat = float(nxt_nvl_idx["begin_mat"].get(it, 0)) if not nxt_nvl_idx.empty else 0
        in_po = float(nxt_nvl_idx["in_cds"].get(it, 0)) if not nxt_nvl_idx.empty else 0
        gap_in_actual = float(nxt_nvl_idx["gap_actual_delivery"].get(it, 0)) if not nxt_nvl_idx.empty else 0
        out_return = float(nxt_nvl_idx["return_mat_to_hs"].get(it, 0)) if not nxt_nvl_idx.empty else 0
        in_replace_adj = float(nxt_nvl_idx["in_other"].get(it, 0)) if not nxt_nvl_idx.empty else 0
        out_scrap_adj = float(nxt_nvl_idx["out_other"].get(it, 0)) if not nxt_nvl_idx.empty else 0
        ending_mat = float(nxt_nvl_idx["ending_logic"].get(it, 0)) if not nxt_nvl_idx.empty else 0
        gap_in_po_remain = float(nxt_nvl_idx["gap_remain_delivery"].get(it, 0)) if not nxt_nvl_idx.empty else 0

        b_fg = float(begin_fg.get(it, 0))
        s_fg = float(sale_fg.get(it, 0))
        g_sale = float(gap_sale_actual.get(it, 0))
        s_ret = float(sale_return.get(it, 0))
        scrap = float(scrap_fg.get(it, 0))
        e_fg = float(ending_fg.get(it, 0))
        g_fg_remain = float(gap_fg_remain.get(it, 0))

        ending_logic = begin_mat + b_fg + in_po + gap_in_actual + in_replace_adj \
            - out_scrap_adj - out_return - s_fg - s_ret - scrap
        gap_actual_logic = ending_mat + e_fg - ending_logic

        ending_hs_erp = float(hs_ending.get(it, 0))
        ending_actual_hs = ending_hs_erp + gap_in_po_remain - g_fg_remain
        gap_hs_ck = ending_actual_hs - (ending_mat + e_fg)

        don_gia_row = dm_nvl.loc[dm_nvl["item_code"] == it, "don_gia"]
        don_gia = float(don_gia_row.iloc[0]) if len(don_gia_row) and pd.notna(don_gia_row.iloc[0]) else 0
        gap_amount = gap_hs_ck * don_gia

        spec_row = dm_nvl[dm_nvl["item_code"] == it]
        spec = spec_row["spec"].iloc[0] if len(spec_row) else ""
        unit = spec_row["unit"].iloc[0] if len(spec_row) else ""
        typ = spec_row["type_code"].iloc[0] if len(spec_row) else ""

        rows.append({
            "period": period, "no": i, "item_code": it, "spec": spec, "unit": unit, "type": typ,
            "begin_mat": begin_mat, "begin_fg": b_fg, "in_po": in_po, "gap_in_actual": gap_in_actual,
            "in_replace_adj": in_replace_adj, "out_scrap_adj_replace": out_scrap_adj,
            "out_return": out_return, "out_sale_fg_hs_cds": s_fg, "gap_sale_actual": g_sale,
            "sale_return": s_ret, "scrap_fg": scrap, "gap_in_po_remain": gap_in_po_remain,
            "gap_sale_fg_remain": g_fg_remain, "ending_logic": ending_logic,
            "ending_mat": ending_mat, "ending_fg": e_fg, "gap_actual_logic": gap_actual_logic,
            "ending_hs_erp": ending_hs_erp, "ending_actual_hs": ending_actual_hs,
            "gap_hs_ck": gap_hs_ck, "don_gia_tk": don_gia, "gap_amount_estimate": gap_amount,
        })
    return pd.DataFrame(rows)
