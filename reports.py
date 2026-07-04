import streamlit as st
import pandas as pd
import calc_engine as ce
import ui_config as ui
import periods as pm

PRIORITY_ORDER = [
    "NXT NVL",
    "NXT TP",
    "NXT Convert MAT",
    "GAP NK NVL",
    "Remain delivery NVL (lũy kế)",
    "NXT SUB",
    "Convert SUB to MAT",
    "GAP XK TP",
    "Remain delivery TP (lũy kế)",
    "Convert TP to MAT",
]

REPORT_FUNCS = {
    "GAP NK NVL": ce.calc_nvl_gap,
    "Remain delivery NVL (lũy kế)": ce.calc_nvl_remain_delivery,
    "NXT SUB": ce.calc_nxt_sub_wide,
    "Convert SUB to MAT": ce.calc_convert_sub_to_mat,
    "NXT Convert MAT": ce.calc_nxt_convert_mat,
    "GAP XK TP": ce.calc_tp_gap,
    "Remain delivery TP (lũy kế)": ce.calc_tp_remain_delivery,
    "NXT NVL": ce.calc_nxt_nvl,
    "NXT TP": ce.calc_nxt_tp,
    "Convert TP to MAT": ce.calc_convert_tp_to_mat,
}

# Detail (vertical) variants for subcon-level display
DETAIL_FUNCS = {
    "NXT SUB": ce.calc_nxt_sub_detail,
    "NXT Convert MAT": ce.calc_nxt_convert_mat_detail,
}

ALL_SUBCONS = ["CKAD", "CKTL", "CKVB", "CKTN", "CKMT", "CKAL"]


def _add_subtotal(df):
    """Add a subtotal row at the TOP summing all numeric columns."""
    if df.empty:
        return df
    skip_sum = {"period", "no", "stt"}
    num_cols = [c for c in df.select_dtypes(include="number").columns if c not in skip_sum]
    if not num_cols:
        return df
    label_col = next((c for c in ["item_code", "prod_code"] if c in df.columns), df.columns[0])
    sub = {}
    for c in df.columns:
        if c in num_cols:
            sub[c] = df[c].sum()
        elif c == label_col:
            sub[c] = "Tong cong"
        else:
            sub[c] = ""
    return pd.concat([pd.DataFrame([sub]), df], ignore_index=True)


def render(conn):
    ui.header("📈 Báo cáo", "Toàn bộ báo cáo tính lại real-time từ dữ liệu gốc")

    period = st.session_state.get("global_period", pm.get_open_period(conn))
    if not period or period == "—":
        period = pm.get_open_period(conn)
    if not period:
        all_periods = pm.list_periods(conn)
        if not all_periods.empty:
            period = all_periods["period"].iloc[-1]
        else:
            st.info("Chưa có kỳ nào trong hệ thống. Vào **Quản lý kỳ** để mở kỳ đầu tiên.")
            return

    results, errors = {}, {}
    for name, func in REPORT_FUNCS.items():
        try:
            results[name] = func(conn, period)
        except Exception as e:
            errors[name] = str(e)

    # Compute detail (vertical) variants for display
    detail_results = {}
    for name, func in DETAIL_FUNCS.items():
        try:
            detail_results[name] = func(conn, period)
        except Exception as e:
            pass  # falls back to wide version

    try:
        balance_sheet = ce.calc_balance_sheet(conn, period)
    except Exception as e:
        balance_sheet = pd.DataFrame()
        errors["Balance Sheet"] = str(e)

    if errors:
        with st.expander(f"⚠️ {len(errors)} báo cáo gặp lỗi khi tính toán — bấm để xem chi tiết"):
            for name, msg in errors.items():
                st.error(f"**{name}**: {msg}")

    export_sheets = {}
    for k, v in results.items():
        export_sheets[k] = _add_subtotal(v.copy()) if v is not None else v
    export_sheets["Balance Sheet"] = _add_subtotal(balance_sheet.copy()) if balance_sheet is not None else balance_sheet
    try:
        excel_data = ui.excel_bytes_multi(export_sheets)
        st.download_button(
            "📥 Tải toàn bộ báo cáo (Excel nhiều sheet)",
            data=excel_data,
            file_name=f"BaoCao_CKVina_{period}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            type="primary",
        )
    except Exception as e:
        st.error(f"Không thể tạo file Excel tổng hợp: {e}")

    st.markdown("---")

    sorted_names = [n for n in PRIORITY_ORDER if n in results]
    tab_names = ["Balance Sheet"] + sorted_names
    tabs = st.tabs(tab_names)

    report_errors = {n: e for n, e in errors.items() if n != "Balance Sheet"}

    # Store subcon filter state per report tab
    if "subcon_filter" not in st.session_state:
        st.session_state.subcon_filter = {}

    for tab, name in zip(tabs, tab_names):
        with tab:
            # For subcon detail reports, use vertical version
            df_detail = detail_results.get(name)
            use_detail = df_detail is not None and not df_detail.empty

            if use_detail:
                df = df_detail
            else:
                df = balance_sheet if name == "Balance Sheet" else results.get(name)

            if df is None:
                st.warning(f"Báo cáo này bị lỗi khi tính toán.")
                if name in report_errors:
                    st.error(report_errors[name])
                continue
            if df.empty:
                st.info("Chưa có dữ liệu cho kỳ này.")
                continue

            # Subcon filter for detail reports
            if use_detail and "subcon" in df.columns:
                subcon_list = sorted(df["subcon"].dropna().unique())
                subcon_options = ["Tất cả"] + subcon_list
                key = f"subcon_{name}"
                selected = st.selectbox("Lọc theo Subcon", subcon_options,
                                         key=key)
                if selected != "Tất cả":
                    df = df[df["subcon"] == selected]
                if df.empty:
                    st.info(f"Không có dữ liệu cho subcon {selected}.")
                    continue

            # Filter by Item code
            code_cols = [c for c in ["item_code", "prod_code", "sale_code", "hs_code", "ma_hs"]
                         if c in df.columns]
            if code_cols:
                search_val = st.text_input("Tim theo ma", key=f"item_search_{name}",
                                           placeholder="Nhập mã Item...")
                if search_val:
                    mask = pd.Series(False, index=df.index)
                    for c in code_cols:
                        mask |= df[c].astype(str).str.contains(search_val, case=False, na=False)
                    df = df[mask]
                    if df.empty:
                        st.info(f"Không có dữ liệu mã '{search_val}'.")
                        continue

            # Filter by value range (on numeric columns)
            num_cols = df.select_dtypes(include="number").columns.tolist()
            if len(num_cols) > 0:
                val_col = num_cols[0]
                fcols = st.columns([1, 1, 1, 1])
                with fcols[0]:
                    val_col = st.selectbox("Cot", num_cols, key=f"value_col_{name}", label_visibility="collapsed")
                with fcols[1]:
                    vmin = float(df[val_col].min()) if not df[val_col].empty else 0.0
                    lo = st.number_input("Tu", value=vmin, key=f"vlo_{name}", label_visibility="collapsed")
                with fcols[2]:
                    vmax = float(df[val_col].max()) if not df[val_col].empty else 0.0
                    hi = st.number_input("Den", value=vmax, key=f"vhi_{name}", label_visibility="collapsed")
                if lo != vmin or hi != vmax:
                    df = df[(df[val_col] >= lo) & (df[val_col] <= hi)]
                    if df.empty:
                        st.info(f"Khong co du lieu trong khoang {lo}-{hi}.")
                        continue

            # Add subtotal row
            df = _add_subtotal(df)

            labels = ui.BALANCE_SHEET_LABELS if name == "Balance Sheet" else ui.REPORT_LABELS.get(name, {})
            display_df = ui.label_df(df, labels)

            st.dataframe(
                ui.style_df(display_df),
                use_container_width=True,
                height=420,
                hide_index=True,
            )

            try:
                sheet_bytes = ui.excel_bytes_single(df, sheet_name=name)
                st.download_button(
                    f"📥 Tải '{name}' (Excel)",
                    data=sheet_bytes,
                    file_name=f"{name.replace(' ', '_')}_{period}.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    key=f"dl_{name}",
                )
            except Exception as e:
                st.error(f"Không thể xuất Excel cho '{name}': {e}")
