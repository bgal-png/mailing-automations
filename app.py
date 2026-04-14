import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from io import StringIO

st.set_page_config(page_title="Email Campaign Reports", layout="wide")
st.title("Email Campaign Reports")

SHOPS = {
    "Čočky-online.cz": {"currency": "CZK", "symbol": "Kč", "locale": "cs"},
    "Ihre-kontaktlinsen.de": {"currency": "EUR", "symbol": "€", "locale": "de"},
    "Lentes-de-contacto.es": {"currency": "EUR", "symbol": "€", "locale": "es"},
    "Leshti.bg": {"currency": "BGN", "symbol": "лв", "locale": "bg"},
    "Mataki.gr": {"currency": "EUR", "symbol": "€", "locale": "el"},
    "Kontaktni.cz": {"currency": "CZK", "symbol": "Kč", "locale": "cs"},
}

EXPECTED_COLUMNS = [
    "Campaign title", "Sent at", "Subject", "Recipients", "Opens",
    "Openrate", "Total opens", "Clicks", "Clickrate", "Total clicks",
    "Unsubscribes", "Bounces", "Spam complaints", "Spam rate",
    "Conversions", "Sales",
]


def parse_csv(uploaded_file):
    """Parse the uploaded CSV file and return a cleaned DataFrame."""
    content = uploaded_file.getvalue().decode("utf-8")
    df = pd.read_csv(StringIO(content), sep=";", quotechar='"')

    if len(df.columns) == 1:
        df = pd.read_csv(StringIO(content), sep=",", quotechar='"')

    if len(df.columns) != 16:
        return None, f"Expected 16 columns but got {len(df.columns)}. Please check the file format."

    df.columns = EXPECTED_COLUMNS

    numeric_cols = [
        "Recipients", "Opens", "Total opens", "Clicks", "Total clicks",
        "Unsubscribes", "Bounces", "Spam complaints", "Conversions", "Sales",
    ]
    for col in numeric_cols:
        df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)

    df["Sent at"] = pd.to_datetime(df["Sent at"], errors="coerce")
    df = df.dropna(subset=["Sent at"]).sort_values("Sent at").reset_index(drop=True)

    # Recalculate all rates from totals — ignore file values
    df["Open Rate (%)"] = (df["Opens"] / df["Recipients"] * 100).round(2)
    df["Click Rate (%)"] = (df["Clicks"] / df["Recipients"] * 100).round(2)
    df["Click-to-Open Rate (%)"] = (
        df["Clicks"] / df["Opens"].replace(0, pd.NA) * 100
    ).round(2).fillna(0)
    df["Unsubscribe Rate (%)"] = (df["Unsubscribes"] / df["Recipients"] * 100).round(3)
    df["Bounce Rate (%)"] = (df["Bounces"] / df["Recipients"] * 100).round(3)
    df["Spam Rate (%)"] = (df["Spam complaints"] / df["Recipients"] * 100).round(4)
    df["Conversion Rate (%)"] = (
        df["Conversions"] / df["Recipients"] * 100
    ).round(3)
    df["Revenue per Email"] = (df["Sales"] / df["Recipients"]).round(2)
    df["Revenue per Click"] = (
        df["Sales"] / df["Clicks"].replace(0, pd.NA)
    ).round(2).fillna(0)
    df["Revenue per Conversion"] = (
        df["Sales"] / df["Conversions"].replace(0, pd.NA)
    ).round(2).fillna(0)

    # Drop the original rate columns we don't trust
    df = df.drop(columns=["Openrate", "Clickrate", "Spam rate"])

    return df, None


def fmt_currency(value, symbol):
    """Format a number with currency symbol."""
    if value >= 1_000_000:
        return f"{value:,.0f} {symbol}"
    elif value >= 1_000:
        return f"{value:,.0f} {symbol}"
    return f"{value:,.2f} {symbol}"


def render_kpis(df, symbol):
    """Render the top-level KPI metrics."""
    total_campaigns = len(df)
    total_recipients = int(df["Recipients"].sum())
    total_sales = df["Sales"].sum()
    total_conversions = int(df["Conversions"].sum())
    total_opens = int(df["Opens"].sum())
    total_clicks = int(df["Clicks"].sum())
    total_unsubs = int(df["Unsubscribes"].sum())
    total_bounces = int(df["Bounces"].sum())

    avg_open_rate = (total_opens / total_recipients * 100) if total_recipients else 0
    avg_click_rate = (total_clicks / total_recipients * 100) if total_recipients else 0
    avg_conversion_rate = (total_conversions / total_recipients * 100) if total_recipients else 0

    row1 = st.columns(4)
    row1[0].metric("Total Campaigns", f"{total_campaigns}")
    row1[1].metric("Total Emails Sent", f"{total_recipients:,}")
    row1[2].metric("Total Sales", fmt_currency(total_sales, symbol))
    row1[3].metric("Total Conversions", f"{total_conversions:,}")

    row2 = st.columns(4)
    row2[0].metric("Avg Open Rate", f"{avg_open_rate:.2f}%")
    row2[1].metric("Avg Click Rate", f"{avg_click_rate:.2f}%")
    row2[2].metric("Avg Conversion Rate", f"{avg_conversion_rate:.3f}%")
    row2[3].metric("Total Unsubscribes / Bounces", f"{total_unsubs:,} / {total_bounces:,}")


def render_best_worst(df, symbol):
    """Show best and worst performing campaigns."""
    st.subheader("Best & Worst Campaigns")

    col1, col2 = st.columns(2)

    with col1:
        st.markdown("**Best by Sales**")
        best_sales = df.loc[df["Sales"].idxmax()]
        st.success(
            f"**{best_sales['Campaign title']}**  \n"
            f"Sales: {fmt_currency(best_sales['Sales'], symbol)} · "
            f"Conversions: {int(best_sales['Conversions'])} · "
            f"Date: {best_sales['Sent at'].strftime('%Y-%m-%d')}"
        )

        st.markdown("**Best by Open Rate**")
        best_open = df.loc[df["Open Rate (%)"].idxmax()]
        st.success(
            f"**{best_open['Campaign title']}**  \n"
            f"Open Rate: {best_open['Open Rate (%)']:.2f}% · "
            f"Opens: {int(best_open['Opens']):,} / {int(best_open['Recipients']):,} · "
            f"Date: {best_open['Sent at'].strftime('%Y-%m-%d')}"
        )

        st.markdown("**Best by Click Rate**")
        best_click = df.loc[df["Click Rate (%)"].idxmax()]
        st.success(
            f"**{best_click['Campaign title']}**  \n"
            f"Click Rate: {best_click['Click Rate (%)']:.2f}% · "
            f"Clicks: {int(best_click['Clicks']):,} / {int(best_click['Recipients']):,} · "
            f"Date: {best_click['Sent at'].strftime('%Y-%m-%d')}"
        )

    with col2:
        st.markdown("**Worst by Sales**")
        worst_sales = df.loc[df["Sales"].idxmin()]
        st.error(
            f"**{worst_sales['Campaign title']}**  \n"
            f"Sales: {fmt_currency(worst_sales['Sales'], symbol)} · "
            f"Conversions: {int(worst_sales['Conversions'])} · "
            f"Date: {worst_sales['Sent at'].strftime('%Y-%m-%d')}"
        )

        st.markdown("**Worst by Open Rate**")
        worst_open = df.loc[df["Open Rate (%)"].idxmin()]
        st.error(
            f"**{worst_open['Campaign title']}**  \n"
            f"Open Rate: {worst_open['Open Rate (%)']:.2f}% · "
            f"Opens: {int(worst_open['Opens']):,} / {int(worst_open['Recipients']):,} · "
            f"Date: {worst_open['Sent at'].strftime('%Y-%m-%d')}"
        )

        st.markdown("**Worst by Click Rate**")
        worst_click = df.loc[df["Click Rate (%)"].idxmin()]
        st.error(
            f"**{worst_click['Campaign title']}**  \n"
            f"Click Rate: {worst_click['Click Rate (%)']:.2f}% · "
            f"Clicks: {int(worst_click['Clicks']):,} / {int(worst_click['Recipients']):,} · "
            f"Date: {worst_click['Sent at'].strftime('%Y-%m-%d')}"
        )


def render_charts(df, symbol):
    """Render all the analytical charts."""
    df_plot = df.copy()
    df_plot["Date"] = df_plot["Sent at"].dt.strftime("%Y-%m-%d")

    # --- Sales over time ---
    st.subheader("Sales Over Time")
    fig_sales = px.bar(
        df_plot, x="Date", y="Sales",
        hover_data=["Campaign title", "Conversions"],
        color_discrete_sequence=["#2E86AB"],
    )
    fig_sales.update_layout(yaxis_title=f"Sales ({symbol})", xaxis_title="Campaign Date")
    st.plotly_chart(fig_sales, use_container_width=True)

    # --- Opens & Clicks over time ---
    st.subheader("Opens & Clicks Over Time")
    fig_oc = go.Figure()
    fig_oc.add_trace(go.Scatter(
        x=df_plot["Date"], y=df_plot["Opens"], name="Unique Opens",
        mode="lines+markers", line=dict(color="#2E86AB"),
        hovertext=df_plot["Campaign title"],
    ))
    fig_oc.add_trace(go.Scatter(
        x=df_plot["Date"], y=df_plot["Clicks"], name="Unique Clicks",
        mode="lines+markers", line=dict(color="#E8451E"),
        hovertext=df_plot["Campaign title"],
    ))
    fig_oc.update_layout(yaxis_title="Count", xaxis_title="Campaign Date")
    st.plotly_chart(fig_oc, use_container_width=True)

    # --- Open Rate & Click Rate ---
    col1, col2 = st.columns(2)
    with col1:
        st.subheader("Open Rate Over Time")
        fig_or = px.line(
            df_plot, x="Date", y="Open Rate (%)",
            hover_data=["Campaign title"],
            markers=True, color_discrete_sequence=["#2E86AB"],
        )
        fig_or.update_layout(yaxis_title="Open Rate (%)")
        st.plotly_chart(fig_or, use_container_width=True)

    with col2:
        st.subheader("Click Rate Over Time")
        fig_cr = px.line(
            df_plot, x="Date", y="Click Rate (%)",
            hover_data=["Campaign title"],
            markers=True, color_discrete_sequence=["#E8451E"],
        )
        fig_cr.update_layout(yaxis_title="Click Rate (%)")
        st.plotly_chart(fig_cr, use_container_width=True)

    # --- Conversions over time ---
    st.subheader("Conversions Over Time")
    fig_conv = px.bar(
        df_plot, x="Date", y="Conversions",
        hover_data=["Campaign title", "Sales"],
        color_discrete_sequence=["#56A764"],
    )
    fig_conv.update_layout(yaxis_title="Conversions", xaxis_title="Campaign Date")
    st.plotly_chart(fig_conv, use_container_width=True)

    # --- Revenue per Email & Revenue per Click ---
    col3, col4 = st.columns(2)
    with col3:
        st.subheader("Revenue per Email Sent")
        fig_rpe = px.bar(
            df_plot, x="Date", y="Revenue per Email",
            hover_data=["Campaign title"],
            color_discrete_sequence=["#A23B72"],
        )
        fig_rpe.update_layout(yaxis_title=f"Revenue per Email ({symbol})")
        st.plotly_chart(fig_rpe, use_container_width=True)

    with col4:
        st.subheader("Revenue per Click")
        fig_rpc = px.bar(
            df_plot, x="Date", y="Revenue per Click",
            hover_data=["Campaign title"],
            color_discrete_sequence=["#F18F01"],
        )
        fig_rpc.update_layout(yaxis_title=f"Revenue per Click ({symbol})")
        st.plotly_chart(fig_rpc, use_container_width=True)

    # --- Unsubscribes & Bounces ---
    st.subheader("Unsubscribes & Bounces Over Time")
    fig_ub = go.Figure()
    fig_ub.add_trace(go.Bar(
        x=df_plot["Date"], y=df_plot["Unsubscribes"], name="Unsubscribes",
        marker_color="#E8451E", hovertext=df_plot["Campaign title"],
    ))
    fig_ub.add_trace(go.Bar(
        x=df_plot["Date"], y=df_plot["Bounces"], name="Bounces",
        marker_color="#FFB627", hovertext=df_plot["Campaign title"],
    ))
    fig_ub.update_layout(barmode="group", yaxis_title="Count", xaxis_title="Campaign Date")
    st.plotly_chart(fig_ub, use_container_width=True)

    # --- Click-to-Open Rate ---
    st.subheader("Click-to-Open Rate Over Time")
    fig_ctor = px.line(
        df_plot, x="Date", y="Click-to-Open Rate (%)",
        hover_data=["Campaign title"],
        markers=True, color_discrete_sequence=["#7B2D8E"],
    )
    fig_ctor.update_layout(yaxis_title="Click-to-Open Rate (%)")
    st.plotly_chart(fig_ctor, use_container_width=True)


def render_data_table(df, symbol):
    """Render the full campaign data table."""
    st.subheader("Campaign Data Table")
    display_cols = [
        "Campaign title", "Sent at", "Subject", "Recipients",
        "Opens", "Open Rate (%)", "Clicks", "Click Rate (%)",
        "Click-to-Open Rate (%)", "Conversions", "Conversion Rate (%)",
        "Sales", "Revenue per Email", "Revenue per Click",
        "Unsubscribes", "Unsubscribe Rate (%)", "Bounces", "Bounce Rate (%)",
        "Spam complaints", "Spam Rate (%)",
    ]
    st.dataframe(
        df[display_cols],
        use_container_width=True,
        hide_index=True,
        column_config={
            "Sent at": st.column_config.DatetimeColumn(format="YYYY-MM-DD HH:mm"),
            "Sales": st.column_config.NumberColumn(format=f"%.0f {symbol}"),
            "Revenue per Email": st.column_config.NumberColumn(format=f"%.2f {symbol}"),
            "Revenue per Click": st.column_config.NumberColumn(format=f"%.2f {symbol}"),
        },
    )


def render_monthly_summary(df, symbol):
    """Render a monthly aggregation summary."""
    st.subheader("Monthly Summary")
    df_monthly = df.copy()
    df_monthly["Month"] = df_monthly["Sent at"].dt.to_period("M").astype(str)

    monthly = df_monthly.groupby("Month").agg(
        Campaigns=("Campaign title", "count"),
        Total_Recipients=("Recipients", "sum"),
        Total_Opens=("Opens", "sum"),
        Total_Clicks=("Clicks", "sum"),
        Total_Sales=("Sales", "sum"),
        Total_Conversions=("Conversions", "sum"),
        Total_Unsubscribes=("Unsubscribes", "sum"),
        Total_Bounces=("Bounces", "sum"),
    ).reset_index()

    monthly["Open Rate (%)"] = (monthly["Total_Opens"] / monthly["Total_Recipients"] * 100).round(2)
    monthly["Click Rate (%)"] = (monthly["Total_Clicks"] / monthly["Total_Recipients"] * 100).round(2)
    monthly["Conversion Rate (%)"] = (monthly["Total_Conversions"] / monthly["Total_Recipients"] * 100).round(3)

    st.dataframe(
        monthly,
        use_container_width=True,
        hide_index=True,
        column_config={
            "Total_Sales": st.column_config.NumberColumn("Total Sales", format=f"%.0f {symbol}"),
            "Total_Recipients": st.column_config.NumberColumn("Emails Sent", format="%d"),
            "Total_Opens": st.column_config.NumberColumn("Opens", format="%d"),
            "Total_Clicks": st.column_config.NumberColumn("Clicks", format="%d"),
            "Total_Conversions": st.column_config.NumberColumn("Conversions", format="%d"),
            "Total_Unsubscribes": st.column_config.NumberColumn("Unsubscribes", format="%d"),
            "Total_Bounces": st.column_config.NumberColumn("Bounces", format="%d"),
        },
    )

    # Monthly sales bar chart
    fig_monthly = px.bar(
        monthly, x="Month", y="Total_Sales",
        text="Campaigns",
        color_discrete_sequence=["#2E86AB"],
        labels={"Total_Sales": f"Sales ({symbol})", "Campaigns": "# Campaigns"},
    )
    fig_monthly.update_traces(textposition="outside")
    fig_monthly.update_layout(yaxis_title=f"Total Sales ({symbol})")
    st.plotly_chart(fig_monthly, use_container_width=True)


# ── Main layout ──────────────────────────────────────────────────────────────

tabs = st.tabs(list(SHOPS.keys()))

for tab, (shop_name, shop_cfg) in zip(tabs, SHOPS.items()):
    with tab:
        symbol = shop_cfg["symbol"]
        uploaded = st.file_uploader(
            f"Upload CSV report for **{shop_name}**",
            type=["csv"],
            key=f"upload_{shop_name}",
        )

        if uploaded is not None:
            df, error = parse_csv(uploaded)
            if error:
                st.error(error)
            else:
                st.success(f"Loaded **{len(df)}** campaigns from **{uploaded.name}**")
                render_kpis(df, symbol)
                st.divider()
                render_best_worst(df, symbol)
                st.divider()
                render_charts(df, symbol)
                st.divider()
                render_monthly_summary(df, symbol)
                st.divider()
                render_data_table(df, symbol)
        else:
            st.info(f"Upload a CSV export from your email platform for **{shop_name}** to see campaign analytics.")
