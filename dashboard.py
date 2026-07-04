"""modules/dashboard.py - Tổng quan tồn kho & cảnh báo GAP"""
import streamlit as st
import pandas as pd
import calc_engine as ce
import ui_config as ui
import periods as pm

try:
    import plotly.express as px
    HAS_PLOTLY = True
except Exception:
    HAS_PLOTLY = False


def _sale_cds_qty(conn, period):
    df = pd.read_sql("SELECT SUM(qty_sale) as total FROM xk_tp_out_cds WHERE period = ?", conn, params=(period,))
    return df.iloc[0]["total"] if not df.empty and df.iloc[0]["total"] else 0


def _tp_without_bom(conn):
    dm_tp = pd.read_sql("SELECT prod_code, spec, unit FROM dm_tp", conn)
    bom = pd.read_sql("SELECT DISTINCT prod_code FROM bom", conn)
    if bom.empty:
        return dm_tp
    has_bom = set(bom["prod_code"].dropna())
    return dm_tp[~dm_tp["prod_code"].isin(has_bom)]


def render(conn):
    period = st.session_state.get("global_period", pm.get_open_period(conn))
    if not period or period == "—":
        st.info("Chưa có kỳ nào được mở. Vào **Quản lý kỳ** để mở kỳ đầu tiên.")
        return

    ui.header("Dashboard", "Tổng quan tồn kho & cảnh báo GAP")

    try:
        bs = ce.calc_balance_sheet(conn, period)
    except Exception as e:
        st.error(f"Không thể tính Balance Sheet: {e}")
        bs = pd.DataFrame()

    try:
        new_codes = ce.check_new_codes(conn, period)
    except Exception:
        new_codes = pd.DataFrame()

    sale_cds = _sale_cds_qty(conn, period)
    gap_items = int((bs["gap_hs_ck"].abs() > 0).sum()) if not bs.empty and "gap_hs_ck" in bs else 0
    gap_amount = bs["gap_amount_estimate"].sum() if not bs.empty and "gap_amount_estimate" in bs else 0
    new_nvl = len(new_codes[new_codes["code_type"] == "NVL"]) if not new_codes.empty else 0
    new_tp = len(new_codes[new_codes["code_type"] == "TP"]) if not new_codes.empty else 0

    tp_no_bom = _tp_without_bom(conn)

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Sale CDS trong tháng", f"{sale_cds:,}")
    c2.metric("Item GAP HS-CK", gap_items)
    c3.metric("Giá trị GAP ước tính", f"{gap_amount:,.0f}")
    c4.metric("Mã mới chưa khai báo", new_nvl + new_tp,
              help=f"NVL: {new_nvl} mã, TP: {new_tp} mã")

    has_new = not new_codes.empty
    has_no_bom = not tp_no_bom.empty
    if has_new or has_no_bom:
        label = f"Mã mới phát sinh chưa có trong danh mục (NVL:{new_nvl}/TP:{new_tp})"
        details_content = ""
        if has_new:
            details_content += new_codes.to_html(index=False, classes="dataframe")
        if has_no_bom:
            details_content += f"<p><b>TP chưa có BOM ({len(tp_no_bom)} mã)</b></p>"
            details_content += tp_no_bom.to_html(index=False, classes="dataframe")
        st.markdown(f"""
            <details style="margin-bottom:1rem;">
                <summary style="cursor:pointer;font-weight:600;color:#0a1628;font-size:0.9rem;
                                background:#f0f2f6;border-radius:8px;padding:6px 12px;
                                border:1px solid #dce0e8;">
                    {label}
                </summary>
                <div style="padding:8px 4px;">
                {details_content}
                </div>
            </details>
        """, unsafe_allow_html=True)

    if bs.empty:
        st.info("Chưa có đủ dữ liệu để hiển thị biểu đồ.")
        return

    if not HAS_PLOTLY:
        st.dataframe(bs.reindex(bs["gap_hs_ck"].abs().sort_values(ascending=False).index).head(10),
                     use_container_width=True)
        return

    if "gap_hs_ck" in bs.columns:
        top_gap = bs.reindex(bs["gap_hs_ck"].abs().sort_values(ascending=False).index).head(10)
        if not top_gap.empty and top_gap["gap_hs_ck"].abs().sum() > 0:
            st.subheader("Top 10 mã GAP HS-CK lớn nhất")
            fig = px.bar(top_gap, x="item_code", y="gap_hs_ck", color="gap_hs_ck",
                         color_continuous_scale=["#c62828", "#eef3fc", "#1a3a6b"])
            fig.update_layout(margin=dict(l=10, r=10, t=10, b=10), height=360)
            st.plotly_chart(fig, use_container_width=True)

    # Giá trị GAP ước tính qua các tháng
    all_periods = pm.list_periods(conn)
    if not all_periods.empty and not bs.empty and "gap_amount_estimate" in bs.columns:
        gap_by_month = []
        for p in all_periods["period"]:
            try:
                bs_p = ce.calc_balance_sheet(conn, p)
                if not bs_p.empty:
                    gap_by_month.append({"period": p, "gap_amount": bs_p["gap_amount_estimate"].sum()})
            except Exception:
                pass
        if gap_by_month:
            df_gap = pd.DataFrame(gap_by_month)
            st.subheader("Giá trị GAP ước tính qua các tháng")
            fig2 = px.bar(df_gap, x="period", y="gap_amount",
                          color="gap_amount",
                          color_continuous_scale=["#1a3a6b", "#eef3fc", "#c62828"])
            fig2.update_layout(margin=dict(l=10, r=10, t=10, b=10), height=360,
                               xaxis_title="", yaxis_title="Giá trị GAP")
            st.plotly_chart(fig2, use_container_width=True)
