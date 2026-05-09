from datetime import date, timedelta
from html import escape
from pathlib import Path
import sys

import pandas as pd
import plotly.express as px
import streamlit as st

APP_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = APP_DIR
DATA_PATH = PROJECT_ROOT / "data" / "sample_ads.csv"
if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))

from charts import (
    cost_per_result_trend,
    frequency_vs_ctr,
    leads_and_inbox_trend,
    spend_vs_results_by_day,
    top_creatives_by_inbox_messages,
    top_creatives_by_leads,
)
from meta_client import RATE_LIMIT_MESSAGE, load_meta_ads_data, meta_credentials_cache_key
from metrics import (
    add_metrics,
    apply_primary_result_metrics,
    creative_summary,
    daily_summary,
    safe_divide_value,
)


PRESETS = ["today", "yesterday", "last_7d", "last_14d", "last_30d"]
PROJECT_NAMES = [
    "M-KPEK",
    "M-RP346",
    "M-PC90",
    "M-SVPS",
    "M-SKR2",
    "M-BSS2",
    "TML-RPR5",
    "TML-P63",
    "TM1,2-ST",
    "TM-SV101/1",
    "MP-R",
    "MP-R2",
    "MT-KPP69",
    "MT-RPCW",
    "MT-BRTW",
    "OB-PM1",
    "TLC-KKL",
    "MC-CP",
]
PROJECT_FILTER_OPTIONS = PROJECT_NAMES + ["Other"]
PROJECT_MATCH_ORDER = sorted(PROJECT_NAMES, key=len, reverse=True)
SORT_OPTIONS = [
    "Spend",
    "Results",
    "Inbox Messages",
    "Leads",
    "Cost per Result",
    "Cost per Inbox",
    "Cost per Lead",
    "CTR",
    "CPM",
    "Frequency",
]
SORT_COLUMNS = {
    "Spend": "spend",
    "Results": "results",
    "Inbox Messages": "inbox_messages",
    "Leads": "leads",
    "Cost per Result": "cost_per_result",
    "Cost per Inbox": "cost_per_inbox",
    "Cost per Lead": "cost_per_lead",
    "CTR": "CTR",
    "CPM": "CPM",
    "Frequency": "Frequency",
}
ASCENDING_SORTS = {"Cost per Result", "Cost per Inbox", "Cost per Lead", "CPM", "Frequency"}
STATE_ADS_DF = "ads_df"
STATE_DATE_RANGE_LABEL = "date_range_label"
STATE_SELECTED_PROJECTS = "selected_projects"
STATE_SELECTED_CAMPAIGNS = "selected_campaigns"
STATE_SELECTED_ADSETS = "selected_adsets"
STATE_USE_CUSTOM_RANGE = "use_custom_range"
STATE_DATE_FROM = "date_from"
STATE_DATE_TO = "date_to"
STATE_PRESET = "preset"
STATE_FETCH_REQUEST_KEY = "fetch_request_key"
META_CACHE_TTL_SECONDS = 60 * 60


def _format_currency(value):
    if pd.isna(value):
        return "-"
    return f"฿{value:,.2f}"


def _format_number(value):
    return f"{value:,.0f}"


def _format_percent(value):
    return f"{value:.2f}%"


def _safe_divide(numerator, denominator):
    return safe_divide_value(numerator, denominator)


def _primary_result_type(row):
    """Classify dashboard primary result intent before applying shared metric math."""
    campaign_name = str(row.get("campaign", "")).lower()
    result_type = str(row.get("result_type", "")).lower()
    if "inbox" in campaign_name or "messaging" in result_type or "inbox" in result_type:
        return "Inbox"
    if "leadgen" in campaign_name or "lead" in campaign_name or "lead" in result_type:
        return "Lead"
    return "Mixed"


def _apply_primary_result_logic(df):
    df = df.copy()
    df["primary_result_type"] = df.apply(_primary_result_type, axis=1)
    return apply_primary_result_metrics(df)


def _sync_selection_state(key, options, default_options=None):
    if key not in st.session_state:
        st.session_state[key] = list(default_options if default_options is not None else options)
    st.session_state[key] = [
        value for value in st.session_state[key] if value in options
    ]


def _meta_account_cache_key():
    return meta_credentials_cache_key(PROJECT_ROOT)


def _fetch_request_key(use_custom_range, date_from, date_to, preset):
    return "|".join(
        [
            str(use_custom_range),
            date_from.isoformat(),
            date_to.isoformat(),
            str(preset),
            _meta_account_cache_key(),
        ]
    )


@st.cache_data(show_spinner=False, ttl=META_CACHE_TTL_SECONDS)
def _cached_meta_ads_data(
    project_root,
    use_custom_range,
    date_from_text,
    date_to_text,
    preset,
    account_cache_key,
    breakdown_key,
):
    if use_custom_range:
        return load_meta_ads_data(
            Path(project_root),
            date_from=date_from_text,
            date_to=date_to_text,
        )
    return load_meta_ads_data(Path(project_root), date_preset=preset)


def _styles():
    st.markdown(
        """
        <style>
            .block-container {
                padding-top: 1.2rem;
                padding-bottom: 3rem;
                max-width: 1440px;
            }
            div[data-testid="stAppViewContainer"] {
                background: #f4f7fb;
            }
            .exec-header {
                background: linear-gradient(135deg, #071529 0%, #10213f 100%);
                color: white;
                padding: 28px 32px;
                border-radius: 14px;
                box-shadow: 0 16px 36px rgba(15, 23, 42, 0.22);
                margin-bottom: 22px;
            }
            .brand {
                color: #9fb3d9;
                font-size: 13px;
                font-weight: 800;
                text-transform: uppercase;
                letter-spacing: 0.08em;
                margin-bottom: 8px;
            }
            .exec-header h1 {
                margin: 0;
                font-size: 34px;
                line-height: 1.15;
                letter-spacing: 0;
            }
            .subtitle {
                margin: 8px 0 0;
                color: #dbe7ff;
                font-size: 16px;
            }
            .date-range {
                display: inline-block;
                margin-top: 16px;
                padding: 8px 12px;
                border-radius: 8px;
                background: rgba(255, 255, 255, 0.1);
                color: #f8fafc;
                font-weight: 700;
            }
            .section-title {
                color: #111827;
                font-size: 22px;
                font-weight: 800;
                margin: 26px 0 12px;
            }
            .card-grid {
                display: grid;
                grid-template-columns: repeat(auto-fit, minmax(210px, 1fr));
                gap: 14px;
                margin-bottom: 10px;
            }
            .kpi-card, .decision-card, .note-card {
                background: white;
                border: 1px solid #e6eaf2;
                border-radius: 14px;
                padding: 18px;
                box-shadow: 0 8px 24px rgba(15, 23, 42, 0.08);
            }
            .kpi-card.highlight {
                border-color: #38bdf8;
                box-shadow: 0 10px 26px rgba(14, 165, 233, 0.18);
                background: #f0f9ff;
            }
            .kpi-card.muted {
                background: #f8fafc;
                border-color: #e2e8f0;
                box-shadow: none;
                opacity: 0.62;
            }
            .kpi-card.muted .kpi-value {
                color: #94a3b8;
            }
            .kpi-group {
                color: #64748b;
                font-size: 12px;
                font-weight: 800;
                text-transform: uppercase;
                letter-spacing: 0.06em;
            }
            .kpi-label {
                color: #334155;
                font-size: 14px;
                margin-top: 8px;
            }
            .kpi-value {
                color: #0f172a;
                font-size: 28px;
                font-weight: 850;
                margin-top: 4px;
            }
            .decision-label {
                color: #475569;
                font-size: 13px;
                font-weight: 800;
                text-transform: uppercase;
                letter-spacing: 0.05em;
            }
            .decision-value {
                color: #111827;
                font-size: 20px;
                font-weight: 850;
                margin-top: 8px;
                line-height: 1.25;
            }
            .decision-detail {
                color: #64748b;
                font-size: 13px;
                margin-top: 6px;
            }
            .action-plan-grid {
                display: grid;
                grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
                gap: 14px;
                margin-bottom: 12px;
            }
            .insight-group {
                background: white;
                border: 1px solid #e6eaf2;
                border-radius: 14px;
                padding: 16px;
                box-shadow: 0 8px 24px rgba(15, 23, 42, 0.08);
            }
            .insight-heading {
                color: #0f172a;
                font-size: 16px;
                font-weight: 850;
                margin-bottom: 10px;
            }
            .insight-item {
                border-top: 1px solid #eef2f7;
                padding-top: 10px;
                margin-top: 10px;
            }
            .insight-name {
                color: #111827;
                font-size: 14px;
                font-weight: 800;
                line-height: 1.25;
                margin-top: 8px;
            }
            .insight-copy {
                color: #475569;
                font-size: 13px;
                line-height: 1.4;
                margin-top: 5px;
            }
            .status-badge {
                display: inline-block;
                border-radius: 999px;
                padding: 4px 8px;
                font-size: 11px;
                font-weight: 850;
                letter-spacing: 0.04em;
            }
            .badge-good {
                background: #dcfce7;
                color: #166534;
            }
            .badge-watch {
                background: #fef3c7;
                color: #92400e;
            }
            .badge-risk {
                background: #fee2e2;
                color: #991b1b;
            }
            .badge-action {
                background: #e0f2fe;
                color: #075985;
            }
            .note-card {
                border-left: 5px solid #2563eb;
                color: #1f2937;
                line-height: 1.45;
            }
            .warning {
                border-left-color: #f59e0b;
            }
            .risk {
                border-left-color: #ef4444;
            }
            .ok {
                border-left-color: #10b981;
            }
            div[data-testid="stDataFrame"] {
                border-radius: 12px;
                overflow: hidden;
                box-shadow: 0 8px 24px rgba(15, 23, 42, 0.06);
            }
            .creative-row {
                background: white;
                border: 1px solid #e6eaf2;
                border-radius: 12px;
                padding: 14px 16px;
                margin-bottom: 14px;
                box-shadow: 0 6px 18px rgba(15, 23, 42, 0.06);
                cursor: pointer;
                transition: transform 0.16s ease, box-shadow 0.16s ease, border-color 0.16s ease;
            }
            .creative-row:hover {
                border-color: #bfd0ea;
                box-shadow: 0 12px 28px rgba(15, 23, 42, 0.12);
                transform: translateY(-1px);
            }
            .creative-card {
                display: flex;
                align-items: flex-start;
                gap: 16px;
            }
            .creative-image {
                flex: 0 0 120px;
                display: flex;
                justify-content: flex-start;
            }
            .creative-body {
                flex: 1;
                min-width: 0;
            }
            .creative-title {
                color: #0f172a;
                font-size: 16px;
                font-weight: 850;
                line-height: 1.25;
                margin-bottom: 4px;
                overflow-wrap: anywhere;
            }
            .creative-title a {
                color: #0f172a;
                text-decoration: none;
            }
            .creative-campaign {
                color: #64748b;
                font-size: 13px;
                font-weight: 650;
                line-height: 1.3;
                margin-bottom: 12px;
                overflow-wrap: anywhere;
            }
            .creative-metrics {
                display: grid;
                grid-template-columns: repeat(auto-fit, minmax(125px, 1fr));
                gap: 10px 16px;
            }
            .row-label {
                color: #64748b;
                font-size: 11px;
                font-weight: 800;
                text-transform: uppercase;
                letter-spacing: 0.05em;
            }
            .row-value {
                color: #0f172a;
                font-size: 14px;
                font-weight: 750;
                margin-top: 2px;
                line-height: 1.25;
            }
            .no-preview {
                width: 120px;
                min-height: 90px;
                border-radius: 8px;
                background: #e2e8f0;
                color: #64748b;
                display: flex;
                align-items: center;
                justify-content: center;
                font-size: 12px;
                font-weight: 800;
                text-align: center;
                line-height: 1.2;
                padding: 8px;
            }
        </style>
        """,
        unsafe_allow_html=True,
    )


def _load_dashboard_data(use_custom_range, date_from, date_to, preset):
    live_error = None
    try:
        meta_df = _cached_meta_ads_data(
            str(PROJECT_ROOT),
            use_custom_range,
            date_from.isoformat(),
            date_to.isoformat(),
            preset,
            _meta_account_cache_key(),
            "ad",
        )
    except Exception as error:
        live_error = error
        meta_df = None

    if meta_df is None:
        if DATA_PATH.exists():
            meta_df = pd.read_csv(DATA_PATH, parse_dates=["date"])
            meta_df.attrs["date_range_label"] = "Report Date Range: Sample CSV"
            if live_error:
                if RATE_LIMIT_MESSAGE in str(live_error):
                    meta_df.attrs["data_source_warning"] = (
                        f"{RATE_LIMIT_MESSAGE} Showing sample CSV fallback."
                    )
                else:
                    meta_df.attrs["data_source_warning"] = (
                        f"Live Meta Ads data unavailable: {live_error}. Showing sample CSV fallback."
                    )
        else:
            if live_error:
                if RATE_LIMIT_MESSAGE in str(live_error):
                    raise RuntimeError(RATE_LIMIT_MESSAGE) from live_error
                raise RuntimeError(
                    f"Live Meta Ads data unavailable and sample fallback is missing: {live_error}"
                ) from live_error
            raise RuntimeError(
                "Meta credentials were not found. Add META_ACCESS_TOKEN and "
                "META_AD_ACCOUNT_ID or META_AD_ACCOUNT_IDS to Streamlit secrets, "
                "environment variables, or local .env. You can also provide "
                "data/sample_ads.csv for local fallback."
            )

    date_range_label = meta_df.attrs.get("date_range_label", "")
    data_source_warning = meta_df.attrs.get("data_source_warning", "")
    meta_df["date"] = pd.to_datetime(meta_df["date"])
    if "adset" not in meta_df.columns:
        meta_df["adset"] = ""
    meta_df = add_metrics(meta_df)
    meta_df["project"] = meta_df["campaign"].apply(_extract_project)
    meta_df = _apply_primary_result_logic(meta_df)
    meta_df.attrs["date_range_label"] = date_range_label
    if data_source_warning:
        meta_df.attrs["data_source_warning"] = data_source_warning
    return meta_df


def _extract_project(campaign_name):
    campaign_name = str(campaign_name or "").upper()
    for project_name in PROJECT_MATCH_ORDER:
        if project_name.upper() in campaign_name:
            return project_name
    return "Other"


def _header(date_range_label):
    clean_range = escape(date_range_label.replace("Report Date Range: ", "") or "Not generated")
    st.markdown(
        f"""
        <div class="exec-header">
            <div class="brand">Akra Land  House</div>
            <h1>Real Estate Meta Ads Performance Dashboard</h1>
            <p class="subtitle">Executive summary for campaign decision-making</p>
            <div class="date-range">Selected Date Range: {clean_range}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def _card_grid(cards, card_class="kpi-card"):
    html = '<div class="card-grid">'
    for card in cards:
        group = escape(str(card.get("group", "")))
        label = escape(str(card["label"]))
        value = escape(str(card["value"]))
        detail = escape(str(card.get("detail", "")))
        extra_class = str(card.get("class", "")).strip()
        classes = f"{card_class} {extra_class}".strip()
        html += (
            f'<div class="{classes}">'
            f'<div class="kpi-group">{group}</div>'
            f'<div class="kpi-label">{label}</div>'
            f'<div class="kpi-value">{value}</div>'
            f'<div class="decision-detail">{detail}</div>'
            "</div>"
        )
    html += "</div>"
    st.markdown(html, unsafe_allow_html=True)


def _kpi_cards(filtered_df):
    total_spend = filtered_df["spend"].sum()
    total_results = filtered_df["results"].sum()
    inbox_df = filtered_df[filtered_df["primary_result_type"] == "Inbox"]
    lead_df = filtered_df[filtered_df["primary_result_type"] == "Lead"]
    total_inbox = inbox_df["inbox_messages"].sum()
    total_leads = lead_df["leads"].sum()
    total_impressions = filtered_df["impressions"].sum()
    total_reach = filtered_df["reach"].sum()
    total_clicks = filtered_df["clicks"].sum()
    inbox_spend = inbox_df["spend"].sum()
    lead_spend = lead_df["spend"].sum()
    classified_spend = inbox_spend + lead_spend
    inbox_share = _safe_divide(inbox_spend, classified_spend)
    lead_share = _safe_divide(lead_spend, classified_spend)
    context = "mixed"
    if classified_spend > 0 and inbox_share >= 0.7:
        context = "inbox"
    elif classified_spend > 0 and lead_share >= 0.7:
        context = "lead"

    cost_per_inbox_class = "highlight" if context == "inbox" else "muted" if context == "lead" else ""
    cost_per_lead_class = "highlight" if context == "lead" else "muted" if context == "inbox" else ""
    cost_per_inbox_detail = "Primary efficiency metric" if context == "inbox" else "Not primary for this selection" if context == "lead" else ""
    cost_per_lead_detail = "Primary efficiency metric" if context == "lead" else "Not primary for this selection" if context == "inbox" else ""

    cards = [
        {"group": "Efficiency", "label": "Total Spend", "value": _format_currency(total_spend)},
        {"group": "Lead Generation", "label": "Total Results", "value": _format_number(total_results)},
        {"group": "Messaging", "label": "Inbox Messages", "value": _format_number(total_inbox)},
        {"group": "Lead Generation", "label": "Leads", "value": _format_number(total_leads)},
        {
            "group": "Efficiency",
            "label": "Cost per Result",
            "value": _format_currency(_safe_divide(total_spend, total_results)),
        },
        {
            "group": "Messaging",
            "label": "Cost per Inbox",
            "value": _format_currency(_safe_divide(inbox_spend, total_inbox)),
            "class": cost_per_inbox_class,
            "detail": cost_per_inbox_detail,
        },
        {
            "group": "Lead Generation",
            "label": "Cost per Lead",
            "value": _format_currency(_safe_divide(lead_spend, total_leads)),
            "class": cost_per_lead_class,
            "detail": cost_per_lead_detail,
        },
        {
            "group": "Audience Quality",
            "label": "CTR",
            "value": _format_percent(_safe_divide(total_clicks, total_impressions) * 100),
        },
        {
            "group": "Audience Quality",
            "label": "CPM",
            "value": _format_currency(_safe_divide(total_spend, total_impressions) * 1000),
        },
        {
            "group": "Audience Quality",
            "label": "Frequency",
            "value": f"{_safe_divide(total_impressions, total_reach):.2f}",
        },
    ]
    _card_grid(cards)


def _decision_summary(campaign_df):
    minimum_results = 3
    best_campaign = campaign_df[
        (campaign_df["results"] >= minimum_results) & (campaign_df["cost_per_result"] > 0)
    ].sort_values("cost_per_result", ascending=True).head(1)
    lead_campaigns = campaign_df[
        (campaign_df["primary_result_type"] == "Lead")
        & (campaign_df["leads"] > 0)
        & (campaign_df["cost_per_lead"].notna())
    ]
    inbox_campaigns = campaign_df[
        (campaign_df["primary_result_type"] == "Inbox")
        & (campaign_df["inbox_messages"] > 0)
    ].sort_values("inbox_messages", ascending=False).head(1)

    if lead_campaigns.empty:
        lowest_cpl_card = {
            "label": "Lowest Cost per Lead",
            "value": "No Lead Campaign Selected",
            "detail": "",
        }
    else:
        lowest_cpl = lead_campaigns.sort_values("cost_per_lead", ascending=True).head(1)
        lowest_cpl_card = _decision_card(
            lowest_cpl, "Lowest Cost per Lead", "cost_per_lead", "cost per lead"
        )

    if inbox_campaigns.empty:
        inbox_card = {
            "label": "Highest Inbox Volume",
            "value": "No Inbox Campaign Selected",
            "detail": "",
        }
    else:
        inbox_card = _decision_card(
            inbox_campaigns, "Highest Inbox Volume", "inbox_messages", "inbox messages"
        )

    spend_threshold = campaign_df["spend"].quantile(0.75)
    result_threshold = campaign_df["results"].median()
    cpl_threshold = lead_campaigns["cost_per_lead"].quantile(0.75)
    watch_df = campaign_df[
        ((campaign_df["spend"] >= spend_threshold) & (campaign_df["results"] <= result_threshold))
        | (
            (campaign_df["primary_result_type"] == "Lead")
            & (campaign_df["leads"] > 0)
            & pd.notna(cpl_threshold)
            & (campaign_df["cost_per_lead"] >= cpl_threshold)
        )
    ]

    cards = [
        _decision_card(best_campaign, "Best Campaign", "cost_per_result", "cost per result"),
        lowest_cpl_card,
        inbox_card,
        {
            "label": "Campaigns to Watch",
            "value": _format_number(len(watch_df)),
            "detail": "High cost or low result efficiency flags",
        },
    ]

    st.markdown('<div class="section-title">Executive Decision Summary</div>', unsafe_allow_html=True)
    html = '<div class="card-grid">'
    for card in cards:
        label = escape(str(card["label"]))
        value = escape(str(card["value"]))
        detail = escape(str(card["detail"]))
        html += (
            '<div class="decision-card">'
            f'<div class="decision-label">{label}</div>'
            f'<div class="decision-value">{value}</div>'
            f'<div class="decision-detail">{detail}</div>'
            "</div>"
        )
    html += "</div>"
    st.markdown(html, unsafe_allow_html=True)


def _decision_card(df, label, metric_column, metric_label):
    if df.empty:
        return {"label": label, "value": "No data", "detail": ""}

    row = df.iloc[0]
    value = row["campaign"]
    metric_value = row[metric_column]
    if "cost" in metric_column:
        detail = f"{_format_currency(metric_value)} {metric_label}"
    else:
        detail = f"{_format_number(metric_value)} {metric_label}"
    return {"label": label, "value": value, "detail": detail}


def _executive_action_plan(filtered_df, campaign_df, adset_df, creative_df):
    overall_cpr = _safe_divide(filtered_df["spend"].sum(), filtered_df["results"].sum())
    overall_ctr = _safe_divide(filtered_df["clicks"].sum(), filtered_df["impressions"].sum()) * 100

    groups = [
        (
            "Scale Opportunities",
            _scale_opportunity_insights(campaign_df, adset_df, overall_cpr, overall_ctr),
        ),
        ("Cost Problems", _cost_problem_insights(campaign_df, adset_df, overall_cpr)),
        (
            "Creative Fatigue Risks",
            _fatigue_risk_insights(creative_df, adset_df, overall_ctr),
        ),
        ("Lead Quality Issues", _lead_quality_insights(campaign_df, adset_df)),
    ]

    has_insights = any(insights for _, insights in groups)
    st.markdown('<div class="section-title">Executive Action Plan</div>', unsafe_allow_html=True)
    if not has_insights:
        st.markdown(
            '<div class="note-card ok">No major issue detected for current selection.</div>',
            unsafe_allow_html=True,
        )
        return

    html = '<div class="action-plan-grid">'
    for title, insights in groups:
        html += f'<div class="insight-group"><div class="insight-heading">{escape(title)}</div>'
        if not insights:
            html += '<div class="insight-copy">No major issue detected for current selection.</div>'
        else:
            for insight in insights[:5]:
                html += _insight_item_html(insight)
        html += "</div>"
    html += "</div>"
    st.markdown(html, unsafe_allow_html=True)



def _thai_performance_agency_summary(filtered_df, campaign_df, adset_df, creative_df):
    total_spend = filtered_df["spend"].sum()
    total_results = filtered_df["results"].sum()
    total_inbox = filtered_df.get("inbox_messages", pd.Series(dtype=float)).sum()
    total_leads = filtered_df.get("leads", pd.Series(dtype=float)).sum()

    cost_per_result = _safe_divide(total_spend, total_results)
    overall_ctr = (
        _safe_divide(filtered_df["clicks"].sum(), filtered_df["impressions"].sum()) * 100
    )

    scale_insights = _scale_opportunity_insights(
        campaign_df, adset_df, cost_per_result, overall_ctr
    )
    cost_insights = _cost_problem_insights(campaign_df, adset_df, cost_per_result)
    fatigue_insights = _fatigue_risk_insights(creative_df, adset_df, overall_ctr)
    quality_insights = _lead_quality_insights(campaign_df, adset_df)

    bullets = [
        (
            "สรุปผู้บริหารแบบ Performance Agency: งบรวม "
            f"{_format_currency(total_spend)} สร้างผลลัพธ์รวม "
            f"{_format_number(total_results)} ครั้ง ต้นทุนเฉลี่ยต่อผลลัพธ์อยู่ที่ "
            f"{_format_currency(cost_per_result)} ต้องบริหารงบด้วยตัวเลข ไม่ใช่ความรู้สึก."
        ),
        (
            f"Funnel ยังมีจุดรั่วชัดเจน: Inbox {_format_number(total_inbox)} ครั้ง "
            f"แต่ปิดเป็น Lead ได้ {_format_number(total_leads)} ราย ต้องตรวจคุณภาพแชต "
            "ข้อเสนอ หน้า Landing Page และความเร็วในการ Follow-up ทันที."
        ),
    ]

    if scale_insights:
        scale_targets = " / ".join(
            insight["name"].split(": ", 1)[-1] for insight in scale_insights[:2]
        )
        bullets.append(
            f"ตัวที่ควร Scale ก่อนคือ {scale_targets} เพราะทำต้นทุนดีกว่าค่าเฉลี่ยและ CTR แข็งแรง "
            "ให้เพิ่มงบแบบคุมรอบ ไม่เทงบก้อนใหญ่จนระบบเสียสมดุล."
        )
    else:
        bullets.append(
            "ตอนนี้ยังไม่มี Campaign หรือ Ad Set ที่แข็งแรงพอสำหรับการ Scale แบบมั่นใจ "
            "ให้ล็อกงบไว้ก่อนจนกว่าจะเห็นต้นทุนและ CTR ชนะค่าเฉลี่ยชัดเจน."
        )

    if cost_insights:
        review_targets = " / ".join(
            insight["name"].split(": ", 1)[-1] for insight in cost_insights[:2]
        )
        bullets.append(
            f"ตัวที่ใช้เงินสูงแต่ผลลัพธ์ต่ำต้องถูกรีวิวหรือพักทันที: {review_targets} "
            "อย่าเติมงบเพิ่มจนกว่าจะรู้ว่าปัญหาอยู่ที่ Audience, Offer หรือ Creative."
        )
    else:
        bullets.append(
            "ยังไม่พบกลุ่มใช้เงินสูงแต่ผลลัพธ์ต่ำแบบน่าหยุดทันที แต่ต้องเฝ้าดู Cost per Result ทุกวัน."
        )

    if fatigue_insights:
        fatigue_targets = " / ".join(
            insight["name"].split(": ", 1)[-1] for insight in fatigue_insights[:2]
        )
        bullets.append(
            f"พบสัญญาณ Creative Fatigue ที่ {fatigue_targets}: Frequency สูงแต่ CTR อ่อนลง "
            "ควรรีเฟรช Creative และทดสอบมุมขายใหม่ก่อนประสิทธิภาพตกหนักกว่านี้."
        )

    if quality_insights:
        quality_targets = " / ".join(
            insight["name"].split(": ", 1)[-1] for insight in quality_insights[:2]
        )
        bullets.append(
            f"พบปัญหาคุณภาพ Lead ที่ {quality_targets}: Inbox เยอะแต่ Lead ต่ำ "
            "ต้องแก้จุดคัดกรอง Lead Form, Landing Page และกระบวนการ Follow-up ไม่ใช่เพิ่มงบอย่างเดียว."
        )

    st.markdown("### สรุปผู้บริหารแบบ Performance Agency")
    for bullet in bullets:
        st.markdown(f"- {bullet}")


def _scale_opportunity_insights(campaign_df, adset_df, overall_cpr, overall_ctr):
    insights = []
    for level_name, df, name_column in [
        ("Campaign", campaign_df, "campaign"),
        ("Ad Set", adset_df, "adset"),
    ]:
        if df.empty:
            continue
        candidates = df[
            (df["results"] >= 5)
            & (df["cost_per_result"] > 0)
            & (df["cost_per_result"] < overall_cpr)
            & (df["CTR"] > overall_ctr)
        ].sort_values(["cost_per_result", "results"], ascending=[True, False])
        for _, row in candidates.head(3).iterrows():
            insights.append(
                {
                    "status": "GOOD",
                    "badge": "badge-good",
                    "name": f"{level_name}: {row[name_column]}",
                    "why": (
                        f"Strong efficiency: {_format_currency(row['cost_per_result'])} cost per result "
                        f"with {_format_number(row['results'])} results and {row['CTR']:.2f}% CTR, "
                        "better than the current selection average."
                    ),
                    "action": "Consider increasing budget carefully",
                }
            )
    return insights


def _cost_problem_insights(campaign_df, adset_df, overall_cpr):
    insights = []
    for level_name, df, name_column in [
        ("Campaign", campaign_df, "campaign"),
        ("Ad Set", adset_df, "adset"),
    ]:
        if df.empty:
            continue
        avg_spend = df["spend"].mean()
        avg_results = df["results"].mean()
        candidates = df[
            (df["spend"] > avg_spend)
            & ((df["results"] < avg_results) | (df["cost_per_result"] > overall_cpr))
        ].sort_values(["spend", "cost_per_result"], ascending=[False, False])
        for _, row in candidates.head(3).iterrows():
            insights.append(
                {
                    "status": "ACTION NEEDED",
                    "badge": "badge-action",
                    "name": f"{level_name}: {row[name_column]}",
                    "why": (
                        f"High spend at {_format_currency(row['spend'])} with "
                        f"{_format_number(row['results'])} results and "
                        f"{_format_currency(row['cost_per_result'])} cost per result."
                    ),
                    "action": "Review audience, offer, or creative before adding budget",
                }
            )
    return insights


def _fatigue_risk_insights(creative_df, adset_df, overall_ctr):
    insights = []
    for level_name, df, name_column in [
        ("Creative", creative_df, "ad"),
        ("Ad Set", adset_df, "adset"),
    ]:
        if df.empty:
            continue
        candidates = df[(df["Frequency"] >= 2.5) & (df["CTR"] < overall_ctr)].sort_values(
            ["Frequency", "CTR"], ascending=[False, True]
        )
        for _, row in candidates.head(3).iterrows():
            insights.append(
                {
                    "status": "RISK",
                    "badge": "badge-risk",
                    "name": f"{level_name}: {row[name_column]}",
                    "why": f"Frequency is {row['Frequency']:.2f} while CTR is {row['CTR']:.2f}%, below the current selection average.",
                    "action": "Refresh creative or test new angle",
                }
            )
    return insights


def _lead_quality_insights(campaign_df, adset_df):
    insights = []
    for level_name, df, name_column in [
        ("Campaign", campaign_df, "campaign"),
        ("Ad Set", adset_df, "adset"),
    ]:
        if df.empty:
            continue
        quality_df = df.copy()
        quality_df["lead_to_inbox_rate"] = quality_df.apply(
            lambda row: _safe_divide(row["leads"], row["inbox_messages"]), axis=1
        )
        candidates = quality_df[
            (quality_df["inbox_messages"] >= 10) & (quality_df["lead_to_inbox_rate"] < 0.2)
        ].sort_values(["inbox_messages", "lead_to_inbox_rate"], ascending=[False, True])
        for _, row in candidates.head(3).iterrows():
            insights.append(
                {
                    "status": "WATCH",
                    "badge": "badge-watch",
                    "name": f"{level_name}: {row[name_column]}",
                    "why": (
                        f"{_format_number(row['inbox_messages'])} inbox messages produced "
                        f"{_format_number(row['leads'])} leads."
                    ),
                    "action": "Review landing page, lead form, or sales follow-up quality",
                }
            )
    return insights


def _insight_item_html(insight):
    return (
        '<div class="insight-item">'
        f'<span class="status-badge {escape(insight["badge"])}">{escape(insight["status"])}</span>'
        f'<div class="insight-name">{escape(str(insight["name"]))}</div>'
        f'<div class="insight-copy">{escape(str(insight["why"]))}</div>'
        f'<div class="insight-copy"><strong>Suggested action:</strong> {escape(str(insight["action"]))}</div>'
        "</div>"
    )


def _campaign_table(campaign_df):
    st.markdown('<div class="section-title">Campaign Performance</div>', unsafe_allow_html=True)
    sorted_df = campaign_df.sort_values("spend", ascending=False).copy()

    columns = [
        "campaign",
        "project",
        "primary_result_type",
        "spend",
        "results",
        "inbox_messages",
        "leads",
        "cost_per_result",
        "cost_per_inbox",
        "cost_per_lead",
        "CTR",
        "CPM",
        "Frequency",
    ]
    display_df = sorted_df[columns].copy()
    display_df.loc[display_df["primary_result_type"] == "Inbox", ["leads", "cost_per_lead"]] = pd.NA
    display_df.loc[
        display_df["primary_result_type"] == "Lead", ["inbox_messages", "cost_per_inbox"]
    ] = pd.NA
    display_df = display_df.rename(
        columns={
            "campaign": "Campaign",
            "project": "Project",
            "primary_result_type": "Primary Result Type",
            "spend": "Spend",
            "results": "Results",
            "inbox_messages": "Inbox Messages",
            "leads": "Leads",
            "cost_per_result": "Cost per Result",
            "cost_per_inbox": "Cost per Inbox",
            "cost_per_lead": "Cost per Lead",
        }
    )

    lead_costs = pd.to_numeric(display_df["Cost per Lead"], errors="coerce")
    result_costs = pd.to_numeric(display_df["Cost per Result"], errors="coerce")
    high_cpl = lead_costs[lead_costs.notna()].quantile(0.75)
    best_cpr = result_costs[display_df["Results"] > 0].quantile(0.25)

    def highlight(row):
        styles = [""] * len(row)
        if pd.notna(high_cpl) and pd.notna(row["Cost per Lead"]) and row["Cost per Lead"] >= high_cpl:
            styles = ["background-color: #fff7ed"] * len(row)
        if pd.notna(best_cpr) and row["Results"] > 0 and row["Cost per Result"] <= best_cpr:
            styles = ["background-color: #ecfdf5"] * len(row)
        return styles

    styled = (
        display_df.style.apply(highlight, axis=1)
        .format(
            {
                "Spend": _format_currency,
                "Results": "{:,.0f}",
                "Inbox Messages": lambda value: "-" if pd.isna(value) else f"{value:,.0f}",
                "Leads": lambda value: "-" if pd.isna(value) else f"{value:,.0f}",
                "Cost per Result": _format_currency,
                "Cost per Inbox": _format_currency,
                "Cost per Lead": _format_currency,
                "CTR": "{:.2f}%",
                "CPM": _format_currency,
                "Frequency": "{:.2f}",
            }
        )
    )
    st.dataframe(styled, use_container_width=True, hide_index=True)


def _adset_table(adset_df):
    st.markdown('<div class="section-title">Ad Set Performance</div>', unsafe_allow_html=True)
    columns = [
        "project",
        "campaign",
        "adset",
        "primary_result_type",
        "spend",
        "results",
        "inbox_messages",
        "leads",
        "cost_per_result",
        "cost_per_inbox",
        "cost_per_lead",
        "CTR",
        "CPM",
        "Frequency",
    ]
    display_df = adset_df[columns].rename(
        columns={
            "project": "Project",
            "campaign": "Campaign",
            "adset": "Ad Set",
            "primary_result_type": "Primary Result Type",
            "spend": "Spend",
            "results": "Results",
            "inbox_messages": "Inbox Messages",
            "leads": "Leads",
            "cost_per_result": "Cost per Result",
            "cost_per_inbox": "Cost per Inbox",
            "cost_per_lead": "Cost per Lead",
        }
    )
    styled = display_df.style.format(
        {
            "Spend": _format_currency,
            "Results": "{:,.0f}",
            "Inbox Messages": "{:,.0f}",
            "Leads": "{:,.0f}",
            "Cost per Result": _format_currency,
            "Cost per Inbox": _format_currency,
            "Cost per Lead": _format_currency,
            "CTR": "{:.2f}%",
            "CPM": _format_currency,
            "Frequency": "{:.2f}",
        }
    )
    st.dataframe(styled, use_container_width=True, hide_index=True)


def _top_level_filters(ads_df):
    st.markdown('<div class="section-title">Project Filters</div>', unsafe_allow_html=True)
    available_projects = set(ads_df["project"].dropna().unique().tolist())
    project_options = [project for project in PROJECT_FILTER_OPTIONS if project in available_projects]

    _sync_selection_state(STATE_SELECTED_PROJECTS, project_options)

    button_columns = st.columns(5)
    if button_columns[0].button("All Projects", use_container_width=True):
        st.session_state[STATE_SELECTED_PROJECTS] = project_options
    if button_columns[1].button("Clear Projects", use_container_width=True):
        st.session_state[STATE_SELECTED_PROJECTS] = []
    if button_columns[2].button("Top 10 by Spend", use_container_width=True):
        st.session_state[STATE_SELECTED_PROJECTS] = _top_projects_by_metric(
            ads_df, project_options, "spend"
        )
    if button_columns[3].button("Top 10 by Leads", use_container_width=True):
        st.session_state[STATE_SELECTED_PROJECTS] = _top_projects_by_metric(
            ads_df, project_options, "leads"
        )
    if button_columns[4].button("Top 10 by Inbox Messages", use_container_width=True):
        st.session_state[STATE_SELECTED_PROJECTS] = _top_projects_by_metric(
            ads_df, project_options, "inbox_messages"
        )

    controls = st.columns([0.9, 1.0])
    top_n = controls[0].slider("Top N projects", min_value=1, max_value=50, value=10)
    sort_by = controls[1].selectbox("Sort by", SORT_OPTIONS, index=0)

    project_filtered_df = ads_df.copy()
    if st.session_state[STATE_SELECTED_PROJECTS]:
        project_filtered_df = project_filtered_df[
            project_filtered_df["project"].isin(st.session_state[STATE_SELECTED_PROJECTS])
        ]
    campaign_options = sorted(project_filtered_df["campaign"].dropna().unique().tolist())
    _sync_selection_state(STATE_SELECTED_CAMPAIGNS, campaign_options, default_options=[])

    campaign_filtered_df = project_filtered_df.copy()
    if st.session_state[STATE_SELECTED_CAMPAIGNS]:
        campaign_filtered_df = campaign_filtered_df[
            campaign_filtered_df["campaign"].isin(st.session_state[STATE_SELECTED_CAMPAIGNS])
        ]
    adset_options = sorted(campaign_filtered_df["adset"].dropna().unique().tolist())
    _sync_selection_state(STATE_SELECTED_ADSETS, adset_options)

    adset_buttons = st.columns(5)
    if adset_buttons[0].button("Top 10 Ad Sets by Spend", use_container_width=True):
        st.session_state[STATE_SELECTED_ADSETS] = _top_adsets_by_metric(campaign_filtered_df, "spend")
    if adset_buttons[1].button("Top 10 Ad Sets by Results", use_container_width=True):
        st.session_state[STATE_SELECTED_ADSETS] = _top_adsets_by_metric(campaign_filtered_df, "results")
    if adset_buttons[2].button("Top 10 Ad Sets by Leads", use_container_width=True):
        st.session_state[STATE_SELECTED_ADSETS] = _top_adsets_by_metric(campaign_filtered_df, "leads")
    if adset_buttons[3].button("Top 10 Ad Sets by Inbox Messages", use_container_width=True):
        st.session_state[STATE_SELECTED_ADSETS] = _top_adsets_by_metric(
            campaign_filtered_df, "inbox_messages"
        )
    if adset_buttons[4].button("Lowest Cost per Lead", use_container_width=True):
        st.session_state[STATE_SELECTED_ADSETS] = _top_adsets_by_lowest_cost_per_lead(
            campaign_filtered_df
        )

    with st.expander("Project and campaign selection", expanded=False):
        selected_projects = st.multiselect(
            "Select Project",
            project_options,
            key=STATE_SELECTED_PROJECTS,
        )
        selected_campaigns = st.multiselect(
            "Select Campaign",
            campaign_options,
            key=STATE_SELECTED_CAMPAIGNS,
            help="Optional. Leave blank to include all campaigns in selected projects.",
        )
        selected_adsets = st.multiselect(
            "Select Ad Set",
            adset_options,
            key=STATE_SELECTED_ADSETS,
            help="Defaults to all ad sets matching the selected projects and campaigns.",
        )

    filtered_df = ads_df.copy()
    if selected_projects:
        filtered_df = filtered_df[filtered_df["project"].isin(selected_projects)]
    if selected_campaigns:
        filtered_df = filtered_df[filtered_df["campaign"].isin(selected_campaigns)]
    if selected_adsets:
        filtered_df = filtered_df[filtered_df["adset"].isin(selected_adsets)]

    adset_label = "Ad Set" if len(selected_adsets) == 1 else "Ad Sets"
    st.caption(
        f"{len(selected_projects)} Projects selected | "
        f"{len(selected_campaigns)} Campaigns selected | "
        f"{len(selected_adsets)} {adset_label} selected"
    )

    return filtered_df, top_n, sort_by


def _top_projects_by_metric(ads_df, project_options, metric):
    project_totals = (
        ads_df[ads_df["project"].isin(project_options)]
        .groupby("project", as_index=False)
        .agg(metric_value=(metric, "sum"))
        .sort_values("metric_value", ascending=False)
        .head(10)
    )
    return project_totals["project"].tolist()


def _top_adsets_by_metric(filtered_df, metric):
    if filtered_df.empty:
        return []
    adset_totals = (
        filtered_df.groupby("adset", as_index=False)
        .agg(metric_value=(metric, "sum"))
        .sort_values("metric_value", ascending=False)
        .head(10)
    )
    return adset_totals["adset"].tolist()


def _top_adsets_by_lowest_cost_per_lead(filtered_df):
    if filtered_df.empty:
        return []
    adset_totals = (
        filtered_df.groupby("adset", as_index=False)
        .agg(spend=("spend", "sum"), leads=("leads", "sum"))
    )
    adset_totals["cost_per_lead"] = adset_totals.apply(
        lambda row: _safe_divide(row["spend"], row["leads"]), axis=1
    )
    return (
        adset_totals[adset_totals["leads"] > 0]
        .sort_values("cost_per_lead", ascending=True)
        .head(10)["adset"]
        .tolist()
    )


def _add_weighted_metrics(grouped):
    grouped["cost_per_result"] = grouped.apply(
        lambda row: _safe_divide(row["spend"], row["results"]), axis=1
    )
    grouped["CTR"] = grouped.apply(
        lambda row: _safe_divide(row["clicks"], row["impressions"]) * 100, axis=1
    )
    grouped["CPM"] = grouped.apply(
        lambda row: _safe_divide(row["spend"], row["impressions"]) * 1000, axis=1
    )
    grouped["Frequency"] = grouped.apply(
        lambda row: _safe_divide(row["impressions"], row["reach"]), axis=1
    )
    grouped["Cost per Result"] = grouped["cost_per_result"]
    grouped["Cost per Inbox"] = grouped["cost_per_inbox"]
    grouped["Cost per Lead"] = grouped["cost_per_lead"]
    return grouped


def _dashboard_campaign_summary(filtered_df):
    grouped = (
        filtered_df.groupby(["campaign", "project", "primary_result_type"], as_index=False)
        .agg(
            result_type=("result_type", "first"),
            spend=("spend", "sum"),
            results=("results", "sum"),
            inbox_messages=("inbox_messages", "sum"),
            leads=("leads", "sum"),
            impressions=("impressions", "sum"),
            reach=("reach", "sum"),
            clicks=("clicks", "sum"),
        )
    )
    grouped["cost_per_inbox"] = grouped.apply(
        lambda row: pd.NA
        if row["primary_result_type"] == "Lead"
        else _safe_divide(row["spend"], row["inbox_messages"]),
        axis=1,
    )
    grouped["cost_per_lead"] = grouped.apply(
        lambda row: pd.NA
        if row["primary_result_type"] == "Inbox"
        else _safe_divide(row["spend"], row["leads"]),
        axis=1,
    )
    return _add_weighted_metrics(grouped)


def _dashboard_adset_summary(filtered_df, sort_by):
    grouped = (
        filtered_df.groupby(["project", "campaign", "adset", "primary_result_type"], as_index=False)
        .agg(
            spend=("spend", "sum"),
            results=("results", "sum"),
            inbox_messages=("inbox_messages", "sum"),
            leads=("leads", "sum"),
            impressions=("impressions", "sum"),
            reach=("reach", "sum"),
            clicks=("clicks", "sum"),
        )
    )
    grouped["cost_per_inbox"] = grouped.apply(
        lambda row: _safe_divide(row["spend"], row["inbox_messages"]), axis=1
    )
    grouped["cost_per_lead"] = grouped.apply(
        lambda row: _safe_divide(row["spend"], row["leads"]), axis=1
    )
    grouped = _add_weighted_metrics(grouped)
    return _sort_summary(grouped, sort_by)


def _sort_summary(grouped, sort_by):
    sort_column = SORT_COLUMNS[sort_by]
    ascending = sort_by in ASCENDING_SORTS
    if sort_by == "Cost per Lead":
        denominator_column = "lead_campaign_results" if "lead_campaign_results" in grouped else "leads"
        grouped["_sort_value"] = grouped["cost_per_lead"].where(
            grouped[denominator_column] > 0, float("inf")
        )
        sort_column = "_sort_value"
    elif sort_by == "Cost per Inbox":
        denominator_column = (
            "inbox_campaign_results" if "inbox_campaign_results" in grouped else "inbox_messages"
        )
        grouped["_sort_value"] = grouped["cost_per_inbox"].where(
            grouped[denominator_column] > 0, float("inf")
        )
        sort_column = "_sort_value"
    elif sort_by == "Cost per Result":
        grouped["_sort_value"] = grouped["cost_per_result"].where(
            grouped["results"] > 0, float("inf")
        )
        sort_column = "_sort_value"
    return grouped.sort_values(sort_column, ascending=ascending).drop(
        columns=["_sort_value"], errors="ignore"
    )


def _project_summary(filtered_df, sort_by, top_n):
    rollup_df = filtered_df.copy()
    rollup_df["inbox_campaign_spend"] = rollup_df["spend"].where(
        rollup_df["primary_result_type"] == "Inbox", 0
    )
    rollup_df["inbox_campaign_results"] = rollup_df["inbox_messages"].where(
        rollup_df["primary_result_type"] == "Inbox", 0
    )
    rollup_df["lead_campaign_spend"] = rollup_df["spend"].where(
        rollup_df["primary_result_type"] == "Lead", 0
    )
    rollup_df["lead_campaign_results"] = rollup_df["leads"].where(
        rollup_df["primary_result_type"] == "Lead", 0
    )
    grouped = (
        rollup_df.groupby("project", as_index=False)
        .agg(
            spend=("spend", "sum"),
            results=("results", "sum"),
            inbox_messages=("inbox_messages", "sum"),
            leads=("leads", "sum"),
            inbox_campaign_spend=("inbox_campaign_spend", "sum"),
            inbox_campaign_results=("inbox_campaign_results", "sum"),
            lead_campaign_spend=("lead_campaign_spend", "sum"),
            lead_campaign_results=("lead_campaign_results", "sum"),
            impressions=("impressions", "sum"),
            reach=("reach", "sum"),
            clicks=("clicks", "sum"),
        )
    )
    grouped["cost_per_inbox"] = grouped.apply(
        lambda row: pd.NA
        if row["inbox_campaign_results"] == 0
        else _safe_divide(row["inbox_campaign_spend"], row["inbox_campaign_results"]),
        axis=1,
    )
    grouped["cost_per_lead"] = grouped.apply(
        lambda row: pd.NA
        if row["lead_campaign_results"] == 0
        else _safe_divide(row["lead_campaign_spend"], row["lead_campaign_results"]),
        axis=1,
    )
    grouped = _add_weighted_metrics(grouped)

    sorted_grouped = _sort_summary(grouped, sort_by)
    return sorted_grouped.head(top_n)


def _verify_project_aggregation(project_df):
    if project_df.empty:
        return True
    expected_cpr = project_df.apply(
        lambda row: _safe_divide(row["spend"], row["results"]), axis=1
    )
    expected_cpi = project_df.apply(
        lambda row: pd.NA
        if row["inbox_campaign_results"] == 0
        else _safe_divide(row["inbox_campaign_spend"], row["inbox_campaign_results"]),
        axis=1,
    )
    expected_cpl = project_df.apply(
        lambda row: pd.NA
        if row["lead_campaign_results"] == 0
        else _safe_divide(row["lead_campaign_spend"], row["lead_campaign_results"]),
        axis=1,
    )
    checks = (
        (project_df["cost_per_result"].fillna(-1) == expected_cpr.fillna(-1))
        & (project_df["cost_per_inbox"].fillna(-1) == expected_cpi.fillna(-1))
        & (project_df["cost_per_lead"].fillna(-1) == expected_cpl.fillna(-1))
    )
    return bool(checks.all())


def _aggregation_check(filtered_df):
    inbox_df = filtered_df[filtered_df["primary_result_type"] == "Inbox"]
    lead_df = filtered_df[filtered_df["primary_result_type"] == "Lead"]

    inbox_spend = inbox_df["spend"].sum()
    inbox_results = inbox_df["inbox_messages"].sum()
    lead_spend = lead_df["spend"].sum()
    lead_results = lead_df["leads"].sum()
    total_spend = filtered_df["spend"].sum()
    primary_results = filtered_df["results"].sum()

    st.markdown('<div class="section-title">Aggregation Check</div>', unsafe_allow_html=True)
    _card_grid(
        [
            {
                "group": "Messaging",
                "label": "Inbox Campaign Spend",
                "value": _format_currency(inbox_spend),
            },
            {
                "group": "Messaging",
                "label": "Inbox Campaign Results",
                "value": _format_number(inbox_results),
            },
            {
                "group": "Messaging",
                "label": "Cost per Inbox",
                "value": _format_currency(_safe_divide(inbox_spend, inbox_results)),
            },
            {
                "group": "Lead Generation",
                "label": "Lead Campaign Spend",
                "value": _format_currency(lead_spend),
            },
            {
                "group": "Lead Generation",
                "label": "Lead Campaign Results",
                "value": _format_number(lead_results),
            },
            {
                "group": "Lead Generation",
                "label": "Cost per Lead",
                "value": _format_currency(_safe_divide(lead_spend, lead_results)),
            },
            {"group": "Efficiency", "label": "Total Spend", "value": _format_currency(total_spend)},
            {
                "group": "Efficiency",
                "label": "Primary Results",
                "value": _format_number(primary_results),
            },
            {
                "group": "Efficiency",
                "label": "Cost per Result",
                "value": _format_currency(_safe_divide(total_spend, primary_results)),
            },
        ]
    )


def _project_performance(project_df):
    st.markdown('<div class="section-title">Project Performance</div>', unsafe_allow_html=True)
    if _verify_project_aggregation(project_df):
        st.caption(
            "Project costs are recalculated after grouping: total spend / primary results, inbox campaign spend / inbox campaign results, and lead campaign spend / lead campaign results."
        )
    display_df = project_df[
        [
            "project",
            "spend",
            "results",
            "inbox_messages",
            "leads",
            "cost_per_result",
            "cost_per_inbox",
            "cost_per_lead",
            "CTR",
            "CPM",
            "Frequency",
        ]
    ].rename(
        columns={
            "project": "Project",
            "spend": "Spend",
            "results": "Results",
            "inbox_messages": "Inbox Messages",
            "leads": "Leads",
            "cost_per_result": "Cost per Result",
            "cost_per_inbox": "Cost per Inbox",
            "cost_per_lead": "Cost per Lead",
        }
    )
    styled = display_df.style.format(
        {
            "Spend": _format_currency,
            "Results": "{:,.0f}",
            "Inbox Messages": "{:,.0f}",
            "Leads": "{:,.0f}",
            "Cost per Result": _format_currency,
            "Cost per Inbox": _format_currency,
            "Cost per Lead": _format_currency,
            "CTR": "{:.2f}%",
            "CPM": _format_currency,
            "Frequency": "{:.2f}",
        }
    )
    st.dataframe(styled, use_container_width=True, hide_index=True)

    chart_columns = st.columns(2)
    inbox_df = project_df.sort_values("inbox_messages", ascending=False)
    leads_df = project_df.sort_values("leads", ascending=False)
    cpi_df = project_df[project_df["inbox_campaign_results"] > 0].sort_values(
        "cost_per_inbox", ascending=True
    )
    cpl_df = project_df[project_df["lead_campaign_results"] > 0].sort_values(
        "cost_per_lead", ascending=True
    )

    inbox_fig = px.bar(
        inbox_df,
        x="inbox_messages",
        y="project",
        orientation="h",
        title="Top Projects by Inbox Messages",
    )
    inbox_fig.update_layout(yaxis={"categoryorder": "total ascending"})

    leads_fig = px.bar(
        leads_df,
        x="leads",
        y="project",
        orientation="h",
        title="Top Projects by Leads",
    )
    leads_fig.update_layout(yaxis={"categoryorder": "total ascending"})

    cpi_fig = px.bar(
        cpi_df,
        x="cost_per_inbox",
        y="project",
        orientation="h",
        title="Top Projects by Cost per Inbox",
    )
    cpi_fig.update_xaxes(title="Cost per Inbox (฿)")
    cpi_fig.update_layout(yaxis={"categoryorder": "total descending"})

    cpl_fig = px.bar(
        cpl_df,
        x="cost_per_lead",
        y="project",
        orientation="h",
        title="Top Projects by Cost per Lead",
    )
    cpl_fig.update_xaxes(title="Cost per Lead (฿)")
    cpl_fig.update_layout(yaxis={"categoryorder": "total descending"})

    chart_columns[0].plotly_chart(inbox_fig, use_container_width=True)
    chart_columns[1].plotly_chart(leads_fig, use_container_width=True)
    chart_columns = st.columns(2)
    chart_columns[0].plotly_chart(cpi_fig, use_container_width=True)
    chart_columns[1].plotly_chart(cpl_fig, use_container_width=True)


def _top_campaigns_by_results(campaign_df):
    top_df = campaign_df.sort_values("results", ascending=False).head(10)
    fig = px.bar(
        top_df,
        x="results",
        y="campaign",
        orientation="h",
        color="primary_result_type",
        title="Top 10 Campaigns by Results",
    )
    fig.update_layout(yaxis={"categoryorder": "total ascending"})
    return fig


def _top_campaigns_by_cost_per_lead(campaign_df):
    chart_df = (
        campaign_df[
            (campaign_df["primary_result_type"] == "Lead")
            & (campaign_df["leads"] > 0)
            & (campaign_df["cost_per_lead"].notna())
        ]
        .sort_values("cost_per_lead")
        .head(10)
    )
    fig = px.bar(
        chart_df,
        x="cost_per_lead",
        y="campaign",
        orientation="h",
        color="leads",
        title="Top 10 Campaigns by Cost per Lead",
    )
    fig.update_xaxes(title="Cost per Lead (฿)")
    fig.update_layout(yaxis={"categoryorder": "total descending"})
    return fig


def _creative_cost_efficiency(creative_df):
    chart_df = creative_df[creative_df["results"] > 0].sort_values("Cost per Result").head(15)
    fig = px.bar(
        chart_df,
        x="Cost per Result",
        y="ad",
        orientation="h",
        color="campaign",
        title="Creative Cost Efficiency",
        hover_data=["leads", "inbox_messages", "Cost per Lead", "Cost per Inbox"],
    )
    fig.update_layout(yaxis={"categoryorder": "total descending"})
    return fig


def _creative_fatigue_risk(creative_df):
    fig = px.scatter(
        creative_df,
        x="Frequency",
        y="CTR",
        size="spend",
        color="Cost per Result",
        hover_name="ad",
        hover_data=["campaign", "results", "leads", "inbox_messages"],
        title="Creative Fatigue Risk",
    )
    fig.update_yaxes(title="CTR (%)")
    return fig


def _preview_url(row):
    thumbnail_url = row.get("thumbnail_url", "")
    image_url = row.get("image_url", "")
    if pd.notna(thumbnail_url) and str(thumbnail_url).strip():
        return str(thumbnail_url)
    if pd.notna(image_url) and str(image_url).strip():
        return str(image_url)
    return ""


def _render_preview_image(container, preview_url):
    if preview_url:
        container.image(preview_url, width=120)
    else:
        container.markdown(
            '<div class="no-preview">Preview not available</div>',
            unsafe_allow_html=True,
        )


def _metric_cell(label, value):
    return (
        '<div>'
        f'<div class="row-label">{escape(label)}</div>'
        f'<div class="row-value">{escape(str(value))}</div>'
        '</div>'
    )


def _creative_preview_rows(creative_df):
    st.markdown("#### Creative Performance With Preview")
    preview_df = creative_df.sort_values(["spend", "results"], ascending=False).head(30)

    for _, row in preview_df.iterrows():
        preview_url = _preview_url(row)
        ad_name = escape(str(row["ad"]))
        campaign = escape(str(row["campaign"]))
        preview_link = row.get("creative_preview_url", "")
        if pd.notna(preview_link) and str(preview_link).strip():
            title_html = f'<a href="{escape(str(preview_link))}" target="_blank">{ad_name}</a>'
        else:
            title_html = ad_name

        image_html = (
            f'<img src="{escape(preview_url)}" width="120" style="width:120px;height:auto;border-radius:8px;display:block;">'
            if preview_url
            else '<div class="no-preview">Preview not available</div>'
        )
        metrics_html = "".join(
            [
                _metric_cell("Spend", _format_currency(row["spend"])),
                _metric_cell("Results", _format_number(row["results"])),
                _metric_cell(
                    "Inbox / Leads",
                    f'{_format_number(row["inbox_messages"])} / {_format_number(row["leads"])}',
                ),
                _metric_cell("Cost / Result", _format_currency(row["Cost per Result"])),
            ]
        )
        st.markdown(
            f"""
            <div class="creative-row" role="button" tabindex="0">
                <div class="creative-card">
                    <div class="creative-image">{image_html}</div>
                    <div class="creative-body">
                        <div class="creative-title">{title_html}</div>
                        <div class="creative-campaign">{campaign}</div>
                        <div class="creative-metrics">{metrics_html}</div>
                    </div>
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )


def _creative_gallery(creative_df):
    st.markdown('<div class="section-title">Creative Gallery</div>', unsafe_allow_html=True)
    gallery_df = creative_df.sort_values(["results", "spend"], ascending=False).head(20)

    for start in range(0, len(gallery_df), 4):
        columns = st.columns(4)
        for column, (_, row) in zip(columns, gallery_df.iloc[start : start + 4].iterrows()):
            with column:
                with st.container(border=True):
                    preview_url = _preview_url(row)
                    _render_preview_image(st, preview_url)

                    st.markdown(f"**{row['ad']}**")
                    st.caption(row["campaign"])
                    st.write(f"Spend: {_format_currency(row['spend'])}")
                    st.write(f"Results: {_format_number(row['results'])}")
                    st.write(f"Inbox Messages: {_format_number(row['inbox_messages'])}")
                    st.write(f"Leads: {_format_number(row['leads'])}")
                    st.write(f"Cost per Result: {_format_currency(row['Cost per Result'])}")
                    st.write(f"Cost per Lead: {_format_currency(row['Cost per Lead'])}")


def _charts(daily_df, campaign_df):
    st.markdown('<div class="section-title">Performance Trends</div>', unsafe_allow_html=True)
    rows = [
        [spend_vs_results_by_day(daily_df), cost_per_result_trend(daily_df)],
        [leads_and_inbox_trend(daily_df), _top_campaigns_by_results(campaign_df)],
        [_top_campaigns_by_cost_per_lead(campaign_df), frequency_vs_ctr(campaign_df)],
    ]
    for row in rows:
        columns = st.columns(2)
        for column, figure in zip(columns, row):
            column.plotly_chart(figure, use_container_width=True)


def _creative_section(creative_df):
    st.markdown('<div class="section-title">Creative Performance</div>', unsafe_allow_html=True)
    _creative_preview_rows(creative_df)

    columns = [
        "ad",
        "campaign",
        "creative_id",
        "creative_name",
        "spend",
        "results",
        "inbox_messages",
        "leads",
        "CTR",
        "CPC",
        "Cost per Result",
        "Cost per Inbox",
        "Cost per Lead",
        "Frequency",
    ]
    st.dataframe(creative_df[columns], use_container_width=True, hide_index=True)

    rows = [
        [top_creatives_by_leads(creative_df), top_creatives_by_inbox_messages(creative_df)],
        [_creative_cost_efficiency(creative_df), _creative_fatigue_risk(creative_df)],
    ]
    for row in rows:
        chart_columns = st.columns(2)
        for column, figure in zip(chart_columns, row):
            column.plotly_chart(figure, use_container_width=True)
    _creative_gallery(creative_df)


def _management_notes(campaign_df):
    st.markdown('<div class="section-title">Management Notes</div>', unsafe_allow_html=True)
    notes = []

    lead_campaigns = campaign_df[
        (campaign_df["primary_result_type"] == "Lead") & (campaign_df["leads"] > 0)
    ]
    if not lead_campaigns.empty:
        avg_cpl = _safe_divide(lead_campaigns["spend"].sum(), lead_campaigns["leads"].sum())
        high_cpl = lead_campaigns[lead_campaigns["cost_per_lead"] > avg_cpl * 1.25]
        if not high_cpl.empty:
            notes.append(
                (
                    "warning",
                    f"{len(high_cpl)} campaign(s) are above the blended cost per lead benchmark. Review targeting, offer strength, and lead form quality.",
                )
            )

    high_frequency = campaign_df["Frequency"].quantile(0.75)
    low_ctr = campaign_df["CTR"].quantile(0.25)
    fatigue_df = campaign_df[(campaign_df["Frequency"] >= high_frequency) & (campaign_df["CTR"] <= low_ctr)]
    if not fatigue_df.empty:
        notes.append(
            (
                "risk",
                f"{len(fatigue_df)} campaign(s) show fatigue risk from high frequency and low CTR. Refresh creatives or widen audiences.",
            )
        )

    inbox_campaigns = campaign_df[campaign_df["primary_result_type"] == "Inbox"]
    inbox_threshold = inbox_campaigns["inbox_messages"].quantile(0.75)
    lead_threshold = campaign_df["leads"].quantile(0.25)
    quality_df = campaign_df[
        (campaign_df["primary_result_type"] == "Inbox")
        & (campaign_df["inbox_messages"] >= inbox_threshold)
        & (campaign_df["leads"] <= lead_threshold)
    ]
    if not quality_df.empty:
        notes.append(
            (
                "warning",
                f"{len(quality_df)} campaign(s) have high inbox volume but low lead output. Review message intent and qualification flow.",
            )
        )

    spend_threshold = campaign_df["spend"].quantile(0.75)
    result_threshold = campaign_df["results"].quantile(0.25)
    budget_df = campaign_df[
        (campaign_df["spend"] >= spend_threshold) & (campaign_df["results"] <= result_threshold)
    ]
    if not budget_df.empty:
        notes.append(
            (
                "risk",
                f"{len(budget_df)} high-spend campaign(s) are producing low results. Consider budget reallocation.",
            )
        )

    if not notes:
        notes.append(("ok", "No major efficiency, fatigue, or lead quality issues were flagged for this range."))

    html = '<div class="card-grid">'
    for note_class, text in notes:
        html += f'<div class="note-card {escape(note_class)}">{escape(text)}</div>'
    html += "</div>"
    st.markdown(html, unsafe_allow_html=True)


def main():
    st.set_page_config(page_title="Real Estate Meta Ads Dashboard", layout="wide")
    _styles()

    today = date.today()
    default_from = today - timedelta(days=6)

    with st.sidebar:
        st.header("Report Controls")
        use_custom_range = st.checkbox(
            "Use custom date range", value=True, key=STATE_USE_CUSTOM_RANGE
        )
        date_from = st.date_input("META_DATE_FROM", value=default_from, key=STATE_DATE_FROM)
        date_to = st.date_input("META_DATE_TO", value=today, key=STATE_DATE_TO)
        preset = st.selectbox("META_DATE_PRESET", PRESETS, index=2, key=STATE_PRESET)
        if st.button("Clear cached Meta data", use_container_width=True, key="clear_cached_meta_data"):
            _cached_meta_ads_data.clear()
            st.session_state.pop(STATE_ADS_DF, None)
            st.session_state.pop(STATE_DATE_RANGE_LABEL, None)
            st.session_state.pop(STATE_FETCH_REQUEST_KEY, None)
            st.success("Meta data cache cleared. Click Generate Report to fetch again.")
        generate = st.button(
            "Generate Report", type="primary", use_container_width=True, key="generate_report"
        )

    initial_label = (
        f"{date_from.strftime('%B')} {date_from.day}, {date_from.year} - "
        f"{date_to.strftime('%B')} {date_to.day}, {date_to.year}"
        if use_custom_range
        else preset
    )
    _header(initial_label)

    if not generate:
        if STATE_ADS_DF not in st.session_state:
            st.info("Choose a date range or preset, then click Generate Report.")
            return

    if generate and use_custom_range and date_from > date_to:
        st.error("META_DATE_FROM must be before or equal to META_DATE_TO.")
        return

    if generate:
        try:
            fetch_request_key = _fetch_request_key(use_custom_range, date_from, date_to, preset)
            if (
                st.session_state.get(STATE_FETCH_REQUEST_KEY) == fetch_request_key
                and STATE_ADS_DF in st.session_state
            ):
                ads_df = st.session_state[STATE_ADS_DF]
            else:
                with st.spinner("Fetching Meta Ads insights..."):
                    ads_df = _load_dashboard_data(use_custom_range, date_from, date_to, preset)
                st.session_state[STATE_ADS_DF] = ads_df
                st.session_state[STATE_DATE_RANGE_LABEL] = ads_df.attrs.get(
                    "date_range_label", initial_label
                )
                st.session_state[STATE_FETCH_REQUEST_KEY] = fetch_request_key
                if ads_df.attrs.get("data_source_warning"):
                    st.warning(ads_df.attrs["data_source_warning"])
        except Exception as error:
            if RATE_LIMIT_MESSAGE in str(error):
                st.error(RATE_LIMIT_MESSAGE)
            else:
                st.error(f"Data loading error: {error}")
            return
    else:
        ads_df = st.session_state[STATE_ADS_DF]
        ads_df.attrs["date_range_label"] = st.session_state.get(STATE_DATE_RANGE_LABEL, "")

    if ads_df.empty:
        st.warning("Meta returned no rows for this range.")
        return

    filtered_df, top_n, sort_by = _top_level_filters(ads_df)
    if filtered_df.empty:
        st.warning("No rows match the selected project or campaign filters.")
        return

    project_df = _project_summary(filtered_df, sort_by, top_n)
    daily_df = daily_summary(filtered_df)
    campaign_df = _dashboard_campaign_summary(filtered_df).sort_values("spend", ascending=False)
    adset_df = _dashboard_adset_summary(filtered_df, sort_by)
    creative_df = creative_summary(filtered_df)

    _decision_summary(campaign_df)
    _executive_action_plan(filtered_df, campaign_df, adset_df, creative_df)
    st.markdown('<div class="section-title">Executive KPI Overview</div>', unsafe_allow_html=True)
    _kpi_cards(filtered_df)
    _thai_performance_agency_summary(filtered_df, campaign_df, adset_df, creative_df)
    _aggregation_check(filtered_df)
    _project_performance(project_df)
    _management_notes(campaign_df)
    _campaign_table(campaign_df)
    _adset_table(adset_df)
    _charts(daily_df, campaign_df)
    _creative_section(creative_df)


if __name__ == "__main__":
    main()
