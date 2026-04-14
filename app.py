import re
import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from io import StringIO

st.set_page_config(page_title="Email Campaign Reports", layout="wide", page_icon="<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24'><text y='20' font-size='20'>&#x1f4ca;</text></svg>")

# ── Custom CSS ───────────────────────────────────────────────────────────────

st.markdown("""
<style>
    /* Hide default Streamlit branding */
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}

    /* Header styling */
    .main-header {
        font-size: 2.2rem;
        font-weight: 700;
        color: #1a1a2e;
        padding-bottom: 0.2rem;
        margin-bottom: 0.5rem;
        border-bottom: 3px solid #2E86AB;
    }
    .sub-header {
        font-size: 0.95rem;
        color: #6c757d;
        margin-bottom: 1.5rem;
    }

    /* Metric cards */
    [data-testid="stMetric"] {
        background: linear-gradient(135deg, #f8f9fa 0%, #e9ecef 100%);
        border: 1px solid #dee2e6;
        border-radius: 10px;
        padding: 15px 20px;
        box-shadow: 0 1px 3px rgba(0,0,0,0.06);
    }
    [data-testid="stMetric"] label {
        color: #6c757d !important;
        font-size: 0.8rem !important;
        font-weight: 600 !important;
        text-transform: uppercase;
        letter-spacing: 0.5px;
    }
    [data-testid="stMetric"] [data-testid="stMetricValue"] {
        color: #1a1a2e !important;
        font-weight: 700 !important;
    }

    /* Tab styling */
    .stTabs [data-baseweb="tab-list"] {
        gap: 4px;
        background-color: #f1f3f5;
        border-radius: 10px;
        padding: 4px;
    }
    .stTabs [data-baseweb="tab"] {
        border-radius: 8px;
        font-weight: 600;
        font-size: 0.85rem;
        padding: 8px 16px;
    }
    .stTabs [aria-selected="true"] {
        background-color: #2E86AB !important;
        color: white !important;
    }

    /* Section headers */
    .section-header {
        font-size: 1.15rem;
        font-weight: 700;
        color: #1a1a2e;
        padding: 0.6rem 0 0.3rem 0;
        border-bottom: 2px solid #e9ecef;
        margin-bottom: 1rem;
    }

    /* Upload area */
    [data-testid="stFileUploader"] {
        border: 2px dashed #dee2e6;
        border-radius: 12px;
        padding: 8px;
    }

    /* Radio buttons horizontal */
    .stRadio > div {
        gap: 0.3rem !important;
    }
    .stRadio [data-baseweb="radio"] {
        margin-right: 0 !important;
    }

    /* Divider */
    hr {
        border-color: #e9ecef !important;
        margin: 1.5rem 0 !important;
    }

    /* Alert boxes */
    .stAlert {
        border-radius: 10px !important;
    }

    /* Comparison card */
    .comparison-empty {
        text-align: center;
        padding: 4rem 2rem;
        color: #6c757d;
    }
    .comparison-empty h3 {
        color: #495057;
    }
</style>
""", unsafe_allow_html=True)

# ── Constants ────────────────────────────────────────────────────────────────

SHOPS = {
    "Čočky-online.cz": {"currency": "CZK", "symbol": "Kč"},
    "Ihre-kontaktlinsen.de": {"currency": "EUR", "symbol": "€"},
    "Lentes-de-contacto.es": {"currency": "EUR", "symbol": "€"},
    "Leshti.bg": {"currency": "BGN", "symbol": "лв"},
    "Mataki.gr": {"currency": "EUR", "symbol": "€"},
    "Kontaktni.cz": {"currency": "CZK", "symbol": "Kč"},
}

SHOP_COLORS = {
    "Čočky-online.cz": "#2E86AB",
    "Ihre-kontaktlinsen.de": "#A23B72",
    "Lentes-de-contacto.es": "#F18F01",
    "Leshti.bg": "#56A764",
    "Mataki.gr": "#E8451E",
    "Kontaktni.cz": "#7B2D8E",
}

EXPECTED_COLUMNS = [
    "Campaign title", "Sent at", "Subject", "Recipients", "Opens",
    "Openrate", "Total opens", "Clicks", "Clickrate", "Total clicks",
    "Unsubscribes", "Bounces", "Spam complaints", "Spam rate",
    "Conversions", "Sales",
]

PLOTLY_LAYOUT = dict(
    font=dict(family="Inter, sans-serif", size=12, color="#495057"),
    plot_bgcolor="rgba(0,0,0,0)",
    paper_bgcolor="rgba(0,0,0,0)",
    margin=dict(l=40, r=20, t=30, b=40),
    xaxis=dict(gridcolor="#e9ecef", gridwidth=1),
    yaxis=dict(gridcolor="#e9ecef", gridwidth=1),
    legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
    hoverlabel=dict(bgcolor="white", font_size=12, bordercolor="#dee2e6"),
)

# ── Session state ────────────────────────────────────────────────────────────

if "shop_data" not in st.session_state:
    st.session_state.shop_data = {}


# ── Data processing ──────────────────────────────────────────────────────────

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

    df["Open Rate (%)"] = (df["Opens"] / df["Recipients"] * 100).round(2)
    df["Click Rate (%)"] = (df["Clicks"] / df["Recipients"] * 100).round(2)
    df["Click-to-Open Rate (%)"] = (
        df["Clicks"] / df["Opens"].replace(0, pd.NA) * 100
    ).fillna(0).round(2)
    df["Unsubscribe Rate (%)"] = (df["Unsubscribes"] / df["Recipients"] * 100).round(3)
    df["Bounce Rate (%)"] = (df["Bounces"] / df["Recipients"] * 100).round(3)
    df["Spam Rate (%)"] = (df["Spam complaints"] / df["Recipients"] * 100).round(4)
    df["Conversion Rate (%)"] = (df["Conversions"] / df["Recipients"] * 100).round(3)
    df["Revenue per Email"] = (df["Sales"] / df["Recipients"]).round(2)
    df["Revenue per Click"] = (
        df["Sales"] / df["Clicks"].replace(0, pd.NA)
    ).fillna(0).round(2)
    df["Revenue per Conversion"] = (
        df["Sales"] / df["Conversions"].replace(0, pd.NA)
    ).fillna(0).round(2)

    df = df.drop(columns=["Openrate", "Clickrate", "Spam rate"])

    return df, None


def base_campaign_name(title):
    """Strip date prefix and suffixes (LC, R, etc.) to get the base campaign name."""
    name = re.sub(r"^\d{6}\s*v?\s*", "", title.strip())
    name = re.sub(r"\s*\(?\s*(LC|R)\s*\)?\s*$", "", name, flags=re.IGNORECASE).strip()
    return name.lower()


def compute_shop_summary(df):
    """Compute summary metrics for a shop DataFrame."""
    total_recipients = int(df["Recipients"].sum())
    total_opens = int(df["Opens"].sum())
    total_clicks = int(df["Clicks"].sum())
    total_conversions = int(df["Conversions"].sum())
    return {
        "Campaigns": df["Campaign title"].apply(base_campaign_name).nunique(),
        "Total Sends": len(df),
        "Total Recipients": total_recipients,
        "Total Sales": df["Sales"].sum(),
        "Total Conversions": total_conversions,
        "Avg Open Rate (%)": round(total_opens / total_recipients * 100, 2) if total_recipients else 0,
        "Avg Click Rate (%)": round(total_clicks / total_recipients * 100, 2) if total_recipients else 0,
        "Avg Conversion Rate (%)": round(total_conversions / total_recipients * 100, 3) if total_recipients else 0,
        "Total Unsubscribes": int(df["Unsubscribes"].sum()),
        "Total Bounces": int(df["Bounces"].sum()),
    }


def fmt_currency(value, symbol):
    """Format a number with currency symbol."""
    return f"{value:,.0f} {symbol}"


def fmt_number(value):
    """Format a large number with commas."""
    return f"{value:,}"


# ── Rendering functions ──────────────────────────────────────────────────────

def render_kpis(df, symbol):
    """Render the top-level KPI metrics."""
    s = compute_shop_summary(df)

    row1 = st.columns(5)
    row1[0].metric("Campaigns", s["Campaigns"])
    row1[1].metric("Total Sends", s["Total Sends"])
    row1[2].metric("Total Recipients", fmt_number(s["Total Recipients"]))
    row1[3].metric("Total Sales", fmt_currency(s["Total Sales"], symbol))
    row1[4].metric("Total Conversions", fmt_number(s["Total Conversions"]))

    row2 = st.columns(4)
    row2[0].metric("Avg Open Rate", f"{s['Avg Open Rate (%)']:.2f}%")
    row2[1].metric("Avg Click Rate", f"{s['Avg Click Rate (%)']:.2f}%")
    row2[2].metric("Avg Conversion Rate", f"{s['Avg Conversion Rate (%)']:.3f}%")
    row2[3].metric("Unsubs / Bounces", f"{s['Total Unsubscribes']:,} / {s['Total Bounces']:,}")


def render_best_worst(df, symbol):
    """Show best and worst performing campaigns."""
    st.markdown('<div class="section-header">Best & Worst Campaigns</div>', unsafe_allow_html=True)

    col1, col2 = st.columns(2)

    with col1:
        for label, col, fmt in [
            ("Best by Sales", "Sales", lambda r: f"Sales: {fmt_currency(r['Sales'], symbol)}"),
            ("Best by Open Rate", "Open Rate (%)", lambda r: f"Open Rate: {r['Open Rate (%)']:.2f}%"),
            ("Best by Click Rate", "Click Rate (%)", lambda r: f"Click Rate: {r['Click Rate (%)']:.2f}%"),
        ]:
            row = df.loc[df[col].idxmax()]
            st.success(
                f"**{label}**  \n"
                f"**{row['Campaign title']}**  \n"
                f"{fmt(row)} | {row['Sent at'].strftime('%Y-%m-%d')}"
            )

    with col2:
        for label, col, fmt in [
            ("Worst by Sales", "Sales", lambda r: f"Sales: {fmt_currency(r['Sales'], symbol)}"),
            ("Worst by Open Rate", "Open Rate (%)", lambda r: f"Open Rate: {r['Open Rate (%)']:.2f}%"),
            ("Worst by Click Rate", "Click Rate (%)", lambda r: f"Click Rate: {r['Click Rate (%)']:.2f}%"),
        ]:
            row = df.loc[df[col].idxmin()]
            st.error(
                f"**{label}**  \n"
                f"**{row['Campaign title']}**  \n"
                f"{fmt(row)} | {row['Sent at'].strftime('%Y-%m-%d')}"
            )


def _apply_layout(fig, **overrides):
    """Apply consistent Plotly layout."""
    layout = {**PLOTLY_LAYOUT, **overrides}
    fig.update_layout(**layout)
    return fig


def render_charts(df, symbol, shop_key):
    """Render all the analytical charts."""
    df_plot = df.copy()
    df_plot["Date"] = df_plot["Sent at"].dt.strftime("%Y-%m-%d")
    c1 = "#2E86AB"
    c2 = "#E8451E"

    # --- Sales ---
    st.markdown('<div class="section-header">Sales Over Time</div>', unsafe_allow_html=True)
    fig = px.bar(df_plot, x="Date", y="Sales", hover_data=["Campaign title", "Conversions"],
                 color_discrete_sequence=[c1])
    _apply_layout(fig, yaxis_title=f"Sales ({symbol})")
    st.plotly_chart(fig, use_container_width=True, key=f"{shop_key}_sales")

    # --- Opens & Clicks ---
    st.markdown('<div class="section-header">Opens & Clicks Over Time</div>', unsafe_allow_html=True)
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=df_plot["Date"], y=df_plot["Opens"], name="Unique Opens",
                             mode="lines+markers", line=dict(color=c1, width=2), hovertext=df_plot["Campaign title"]))
    fig.add_trace(go.Scatter(x=df_plot["Date"], y=df_plot["Clicks"], name="Unique Clicks",
                             mode="lines+markers", line=dict(color=c2, width=2), hovertext=df_plot["Campaign title"]))
    _apply_layout(fig, yaxis_title="Count")
    st.plotly_chart(fig, use_container_width=True, key=f"{shop_key}_oc")

    # --- Rates side by side ---
    col1, col2 = st.columns(2)
    with col1:
        st.markdown('<div class="section-header">Open Rate</div>', unsafe_allow_html=True)
        fig = px.line(df_plot, x="Date", y="Open Rate (%)", hover_data=["Campaign title"],
                      markers=True, color_discrete_sequence=[c1])
        _apply_layout(fig, yaxis_title="Open Rate (%)")
        st.plotly_chart(fig, use_container_width=True, key=f"{shop_key}_or")
    with col2:
        st.markdown('<div class="section-header">Click Rate</div>', unsafe_allow_html=True)
        fig = px.line(df_plot, x="Date", y="Click Rate (%)", hover_data=["Campaign title"],
                      markers=True, color_discrete_sequence=[c2])
        _apply_layout(fig, yaxis_title="Click Rate (%)")
        st.plotly_chart(fig, use_container_width=True, key=f"{shop_key}_cr")

    # --- Conversions ---
    st.markdown('<div class="section-header">Conversions Over Time</div>', unsafe_allow_html=True)
    fig = px.bar(df_plot, x="Date", y="Conversions", hover_data=["Campaign title", "Sales"],
                 color_discrete_sequence=["#56A764"])
    _apply_layout(fig, yaxis_title="Conversions")
    st.plotly_chart(fig, use_container_width=True, key=f"{shop_key}_conv")

    # --- Revenue metrics side by side ---
    col3, col4 = st.columns(2)
    with col3:
        st.markdown('<div class="section-header">Revenue per Email</div>', unsafe_allow_html=True)
        fig = px.bar(df_plot, x="Date", y="Revenue per Email", hover_data=["Campaign title"],
                     color_discrete_sequence=["#A23B72"])
        _apply_layout(fig, yaxis_title=f"Rev / Email ({symbol})")
        st.plotly_chart(fig, use_container_width=True, key=f"{shop_key}_rpe")
    with col4:
        st.markdown('<div class="section-header">Revenue per Click</div>', unsafe_allow_html=True)
        fig = px.bar(df_plot, x="Date", y="Revenue per Click", hover_data=["Campaign title"],
                     color_discrete_sequence=["#F18F01"])
        _apply_layout(fig, yaxis_title=f"Rev / Click ({symbol})")
        st.plotly_chart(fig, use_container_width=True, key=f"{shop_key}_rpc")

    # --- Unsubscribes & Bounces ---
    st.markdown('<div class="section-header">Unsubscribes & Bounces</div>', unsafe_allow_html=True)
    fig = go.Figure()
    fig.add_trace(go.Bar(x=df_plot["Date"], y=df_plot["Unsubscribes"], name="Unsubscribes",
                         marker_color=c2, hovertext=df_plot["Campaign title"]))
    fig.add_trace(go.Bar(x=df_plot["Date"], y=df_plot["Bounces"], name="Bounces",
                         marker_color="#FFB627", hovertext=df_plot["Campaign title"]))
    _apply_layout(fig, barmode="group", yaxis_title="Count")
    st.plotly_chart(fig, use_container_width=True, key=f"{shop_key}_ub")

    # --- Click-to-Open Rate ---
    st.markdown('<div class="section-header">Click-to-Open Rate</div>', unsafe_allow_html=True)
    fig = px.line(df_plot, x="Date", y="Click-to-Open Rate (%)", hover_data=["Campaign title"],
                  markers=True, color_discrete_sequence=["#7B2D8E"])
    _apply_layout(fig, yaxis_title="CTOR (%)")
    st.plotly_chart(fig, use_container_width=True, key=f"{shop_key}_ctor")


def render_data_table(df, symbol, shop_key):
    """Render the full campaign data table."""
    st.markdown('<div class="section-header">Campaign Data</div>', unsafe_allow_html=True)
    display_cols = [
        "Campaign title", "Sent at", "Subject", "Recipients",
        "Opens", "Open Rate (%)", "Clicks", "Click Rate (%)",
        "Click-to-Open Rate (%)", "Conversions", "Conversion Rate (%)",
        "Sales", "Revenue per Email", "Revenue per Click",
        "Unsubscribes", "Unsubscribe Rate (%)", "Bounces", "Bounce Rate (%)",
        "Spam complaints", "Spam Rate (%)",
    ]
    st.dataframe(
        df[display_cols], use_container_width=True, hide_index=True,
        key=f"{shop_key}_datatable",
        column_config={
            "Sent at": st.column_config.DatetimeColumn(format="YYYY-MM-DD HH:mm"),
            "Sales": st.column_config.NumberColumn(format=f"%.0f {symbol}"),
            "Revenue per Email": st.column_config.NumberColumn(format=f"%.2f {symbol}"),
            "Revenue per Click": st.column_config.NumberColumn(format=f"%.2f {symbol}"),
        },
    )


def render_monthly_summary(df, symbol, shop_key):
    """Render a monthly aggregation summary."""
    st.markdown('<div class="section-header">Monthly Summary</div>', unsafe_allow_html=True)
    df_m = df.copy()
    df_m["Month"] = df_m["Sent at"].dt.to_period("M").astype(str)

    monthly = df_m.groupby("Month").agg(
        Sends=("Campaign title", "count"),
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
    monthly["Conv. Rate (%)"] = (monthly["Total_Conversions"] / monthly["Total_Recipients"] * 100).round(3)

    st.dataframe(
        monthly, use_container_width=True, hide_index=True,
        key=f"{shop_key}_monthly",
        column_config={
            "Total_Sales": st.column_config.NumberColumn("Sales", format=f"%.0f {symbol}"),
            "Total_Recipients": st.column_config.NumberColumn("Recipients", format="%d"),
            "Total_Opens": st.column_config.NumberColumn("Opens", format="%d"),
            "Total_Clicks": st.column_config.NumberColumn("Clicks", format="%d"),
            "Total_Conversions": st.column_config.NumberColumn("Conversions", format="%d"),
            "Total_Unsubscribes": st.column_config.NumberColumn("Unsubs", format="%d"),
            "Total_Bounces": st.column_config.NumberColumn("Bounces", format="%d"),
        },
    )

    fig = px.bar(monthly, x="Month", y="Total_Sales", text="Sends",
                 color_discrete_sequence=["#2E86AB"],
                 labels={"Total_Sales": f"Sales ({symbol})", "Sends": "Sends"})
    fig.update_traces(textposition="outside")
    _apply_layout(fig, yaxis_title=f"Sales ({symbol})")
    st.plotly_chart(fig, use_container_width=True, key=f"{shop_key}_monthly_chart")


# ── Comparison tab ───────────────────────────────────────────────────────────

def render_comparison():
    """Render the cross-shop comparison tab."""
    loaded = {name: data for name, data in st.session_state.shop_data.items() if data is not None}

    if len(loaded) < 2:
        st.markdown(
            '<div class="comparison-empty">'
            "<h3>Upload data in at least 2 shop tabs to compare</h3>"
            "<p>Go to the individual shop tabs and upload CSV reports. "
            "They will appear here automatically for side-by-side comparison.</p>"
            "</div>",
            unsafe_allow_html=True,
        )
        if len(loaded) == 1:
            name = list(loaded.keys())[0]
            st.info(f"**{name}** is loaded. Upload at least one more shop to unlock comparisons.")
        return

    shop_names = list(loaded.keys())
    colors = [SHOP_COLORS[n] for n in shop_names]

    # --- Summary table ---
    st.markdown('<div class="section-header">Key Metrics Comparison</div>', unsafe_allow_html=True)
    rows = []
    for name in shop_names:
        s = compute_shop_summary(loaded[name])
        symbol = SHOPS[name]["symbol"]
        rows.append({
            "Shop": name,
            "Currency": SHOPS[name]["currency"],
            "Campaigns": s["Campaigns"],
            "Sends": s["Total Sends"],
            "Recipients": s["Total Recipients"],
            "Sales": s["Total Sales"],
            "Conversions": s["Total Conversions"],
            "Open Rate (%)": s["Avg Open Rate (%)"],
            "Click Rate (%)": s["Avg Click Rate (%)"],
            "Conv. Rate (%)": s["Avg Conversion Rate (%)"],
            "Unsubscribes": s["Total Unsubscribes"],
        })
    summary_df = pd.DataFrame(rows)
    st.dataframe(summary_df, use_container_width=True, hide_index=True, key="cmp_summary")

    # --- Rate comparisons (bar charts) ---
    st.markdown('<div class="section-header">Rate Comparison</div>', unsafe_allow_html=True)
    col1, col2, col3 = st.columns(3)

    for col, metric, title in [
        (col1, "Open Rate (%)", "Avg Open Rate"),
        (col2, "Click Rate (%)", "Avg Click Rate"),
        (col3, "Conv. Rate (%)", "Avg Conversion Rate"),
    ]:
        with col:
            fig = go.Figure(go.Bar(
                x=summary_df["Shop"], y=summary_df[metric],
                marker_color=colors,
                text=summary_df[metric].apply(lambda v: f"{v:.2f}%"),
                textposition="outside",
            ))
            _apply_layout(fig, yaxis_title="%", title=dict(text=title, font=dict(size=14)))
            fig.update_layout(height=350)
            st.plotly_chart(fig, use_container_width=True, key=f"cmp_{metric}")

    # --- Sends & Conversions ---
    st.markdown('<div class="section-header">Volume Comparison</div>', unsafe_allow_html=True)
    col4, col5 = st.columns(2)

    with col4:
        fig = go.Figure(go.Bar(
            x=summary_df["Shop"], y=summary_df["Sends"],
            marker_color=colors,
            text=summary_df["Sends"], textposition="outside",
        ))
        _apply_layout(fig, yaxis_title="Sends", title=dict(text="Total Sends", font=dict(size=14)))
        fig.update_layout(height=350)
        st.plotly_chart(fig, use_container_width=True, key="cmp_sends")

    with col5:
        fig = go.Figure(go.Bar(
            x=summary_df["Shop"], y=summary_df["Conversions"],
            marker_color=colors,
            text=summary_df["Conversions"], textposition="outside",
        ))
        _apply_layout(fig, yaxis_title="Conversions", title=dict(text="Total Conversions", font=dict(size=14)))
        fig.update_layout(height=350)
        st.plotly_chart(fig, use_container_width=True, key="cmp_conversions")

    # --- Monthly open rate trends overlaid ---
    st.markdown('<div class="section-header">Monthly Open Rate Trend</div>', unsafe_allow_html=True)
    fig = go.Figure()
    for name in shop_names:
        df_m = loaded[name].copy()
        df_m["Month"] = df_m["Sent at"].dt.to_period("M").astype(str)
        monthly = df_m.groupby("Month").agg(
            Opens=("Opens", "sum"), Recipients=("Recipients", "sum")
        ).reset_index()
        monthly["Open Rate (%)"] = (monthly["Opens"] / monthly["Recipients"] * 100).round(2)
        fig.add_trace(go.Scatter(
            x=monthly["Month"], y=monthly["Open Rate (%)"], name=name,
            mode="lines+markers", line=dict(color=SHOP_COLORS[name], width=2),
        ))
    _apply_layout(fig, yaxis_title="Open Rate (%)")
    st.plotly_chart(fig, use_container_width=True, key="cmp_monthly_or")

    # --- Monthly click rate trends overlaid ---
    st.markdown('<div class="section-header">Monthly Click Rate Trend</div>', unsafe_allow_html=True)
    fig = go.Figure()
    for name in shop_names:
        df_m = loaded[name].copy()
        df_m["Month"] = df_m["Sent at"].dt.to_period("M").astype(str)
        monthly = df_m.groupby("Month").agg(
            Clicks=("Clicks", "sum"), Recipients=("Recipients", "sum")
        ).reset_index()
        monthly["Click Rate (%)"] = (monthly["Clicks"] / monthly["Recipients"] * 100).round(2)
        fig.add_trace(go.Scatter(
            x=monthly["Month"], y=monthly["Click Rate (%)"], name=name,
            mode="lines+markers", line=dict(color=SHOP_COLORS[name], width=2),
        ))
    _apply_layout(fig, yaxis_title="Click Rate (%)")
    st.plotly_chart(fig, use_container_width=True, key="cmp_monthly_cr")

    # --- Monthly sales per shop (grouped bar, same-currency shops together) ---
    st.markdown('<div class="section-header">Monthly Sales by Shop</div>', unsafe_allow_html=True)
    currencies_used = sorted(set(SHOPS[n]["currency"] for n in shop_names))

    for curr in currencies_used:
        curr_shops = [n for n in shop_names if SHOPS[n]["currency"] == curr]
        if not curr_shops:
            continue
        symbol = SHOPS[curr_shops[0]]["symbol"]
        st.caption(f"**{curr}** shops")
        fig = go.Figure()
        for name in curr_shops:
            df_m = loaded[name].copy()
            df_m["Month"] = df_m["Sent at"].dt.to_period("M").astype(str)
            monthly = df_m.groupby("Month").agg(Sales=("Sales", "sum")).reset_index()
            fig.add_trace(go.Bar(
                x=monthly["Month"], y=monthly["Sales"], name=name,
                marker_color=SHOP_COLORS[name],
            ))
        _apply_layout(fig, barmode="group", yaxis_title=f"Sales ({symbol})")
        st.plotly_chart(fig, use_container_width=True, key=f"cmp_sales_{curr}")


# ── Main layout ──────────────────────────────────────────────────────────────

st.markdown('<div class="main-header">Email Campaign Reports</div>', unsafe_allow_html=True)
st.markdown('<div class="sub-header">Upload CSV exports from your email platform to analyze campaign performance across shops.</div>', unsafe_allow_html=True)

tab_names = ["Cross-Shop Comparison"] + list(SHOPS.keys())
all_tabs = st.tabs(tab_names)

# --- Comparison tab ---
with all_tabs[0]:
    render_comparison()

# --- Individual shop tabs ---
for tab, (shop_name, shop_cfg) in zip(all_tabs[1:], SHOPS.items()):
    with tab:
        symbol = shop_cfg["symbol"]
        shop_key = shop_name.replace(".", "_").replace("-", "_").replace(" ", "_")

        uploaded = st.file_uploader(
            f"Upload CSV report for **{shop_name}**",
            type=["csv"],
            key=f"upload_{shop_name}",
        )

        if uploaded is not None:
            df_all, error = parse_csv(uploaded)
            if error:
                st.error(error)
            else:
                # Store in session state for comparison tab
                st.session_state.shop_data[shop_name] = df_all

                years = sorted(df_all["Sent at"].dt.year.unique())
                year_options = ["All"] + [str(y) for y in years]
                selected_year = st.radio(
                    "Filter by year",
                    year_options,
                    horizontal=True,
                    key=f"year_{shop_name}",
                )

                if selected_year == "All":
                    df = df_all
                else:
                    df = df_all[df_all["Sent at"].dt.year == int(selected_year)].reset_index(drop=True)

                date_range = f"{df['Sent at'].min().strftime('%b %Y')} — {df['Sent at'].max().strftime('%b %Y')}"
                st.caption(
                    f"Showing **{len(df)}** sends"
                    + (f" for **{selected_year}**" if selected_year != "All" else "")
                    + f" | {date_range}"
                )

                render_kpis(df, symbol)
                st.divider()
                render_best_worst(df, symbol)
                st.divider()
                render_charts(df, symbol, shop_key)
                st.divider()
                render_monthly_summary(df, symbol, shop_key)
                st.divider()
                render_data_table(df, symbol, shop_key)
        else:
            st.session_state.shop_data.pop(shop_name, None)
            st.markdown(
                f'<div class="comparison-empty">'
                f"<h3>No data for {shop_name}</h3>"
                f"<p>Upload a CSV export from your email platform to see campaign analytics.</p>"
                f"</div>",
                unsafe_allow_html=True,
            )
