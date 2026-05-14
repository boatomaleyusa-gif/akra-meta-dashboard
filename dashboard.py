from datetime import date, timedelta
from datetime import datetime
import hashlib
from html import escape
import io
import logging
from pathlib import Path
import re
import sys
import unicodedata

import pandas as pd
import plotly.express as px
import streamlit as st

APP_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = APP_DIR
DATA_PATH = PROJECT_ROOT / "data" / "sample_ads.csv"
FILE_CACHE_PATH = PROJECT_ROOT / "data" / "cache" / "latest_ads.parquet"
PIPELINE_CACHE_PATH = PROJECT_ROOT / "data" / "cache" / "latest_pipeline.parquet"
if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))

from charts import (
    cost_per_result_trend,
    frequency_vs_ctr,
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

LOGGER = logging.getLogger(__name__)


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
    "MC-PC",
]
PROJECT_FILTER_OPTIONS = PROJECT_NAMES + ["Other"]
PROJECT_MATCH_ORDER = sorted(PROJECT_NAMES, key=len, reverse=True)
PROJECT_ALIASES = {
    "M2-KPEK": "M-KPEK",
}
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
PIPELINE_PROJECT_COLUMN = "โครงการ"
PIPELINE_REQUIRED_COLUMNS = [
    PIPELINE_PROJECT_COLUMN,
    "adset_name",
    "channel",
    "quality",
    "stage",
    "created_date",
]
PIPELINE_CONTACT_COLUMNS = ["total_contacts", "paid_contacts", "organic_contacts"]
ORGANIC_BUCKET_NAME = "Organic / Engage"
ORGANIC_RESULT_TYPE = "Engage"
PIPELINE_ADSET_ABBREVIATIONS = {
    "ib": "inbox",
    "ld": "lead",
    "eng": "engage",
    "msg": "message",
}
ADSET_OBJECTIVE_ALIASES = {
    "ib": "inbox",
    "inbox": "inbox",
    "inboxvdo": "inbox",
    "inboxpic": "inbox",
    "ld": "lead",
    "lead": "lead",
    "leadgen": "lead",
    "leadpage": "lead",
    "eng": "engage",
    "engage": "engage",
}
PIPELINE_COLUMN_ALIASES = {
    PIPELINE_PROJECT_COLUMN: [PIPELINE_PROJECT_COLUMN, "Project", "project"],
    "adset_name": ["AD Set Name", "Adset Name", "Ad Set", "adset_name"],
    "channel": ["ช่องทาง", "Channel", "channel"],
    "quality": ["คุณภาพ", "Quality", "quality"],
    "stage": ["สเตจ", "Stage", "stage"],
    "created_date": ["วันที่สร้าง", "Created Date", "created_date"],
}
PIPELINE_TO_META_PROJECTS = {
    "The Obsidian พุทธมณฑล สาย 1": "OB-PM1",
    "The Obsidian": "OB-PM1",
    "The Matias บรมราชชนนี - ทวีวัฒนา": "MT-BRTW",
    "The Matt สาทร-ท่าพระ": "TM1,2-ST",
    "The Matt Sathorn-Thaphra": "TM1,2-ST",
    "The Miracle เศรษฐกิจ - พระราม 2": "M-SKR2",
    "The Miracle เศรษฐกิจ - คลองครุ - พระราม2": "M-SKR2",
    "The Miracle บางแสน สาย 2": "M-BSS2",
    "The Miracle ประชาอุทิศ 90": "M-PC90",
    "The Miracle กาญจนาภิเษก - เอกชัย": "M-KPEK",
    "The Miracle กาญจนาภิเษก-เอกชัย โครงการ 2": "M-KPEK",
    "The Miracle Plus พระราม2": "MP-R2",
    "The miracle plus พระราม 2": "MP-R2",
    "The Matias กาญจนาภิเษก - เพชรเกษม 69": "MT-KPP69",
    "The Matias ราชพฤกษ์ - แจ้งวัฒนะ": "MT-RPCW",
    "The Matt สุขุมวิท 101/1": "TM-SV101/1",
    "The Matt Sukhumvit 101/1": "TM-SV101/1",
    "The Mirth Lite ราชพฤกษ์ – พระราม 5": "TML-RPR5",
    "The Mirth Lite ราชพฤกษ์ - พระราม 5": "TML-RPR5",
    "The Mirth Lite เพชรเกษม 63": "TML-P63",
    "The Miracle Plus เพชรเกษม 63 โครงการ 2": "TML-P63",
    "The Miracle Plus เพชรเกษม 63 โครงการ 3": "TML-P63",
    "Talaycation หัวหิน-ปราณบุรี": "TLC-KKL",
    "ทะเลสาบขน": "TLC-KKL",
    "The Miracle สุขุมวิท - แพรกษา": "M-SVPS",
    "The Miracle ราชพฤกษ์ 346": "M-RP346",
    "The Miracle Plus ราชบุรี": "MP-R",
    "The Miracle ชุมแพ": "MC-PC",
    "The Miracle Chumphae เดอะ มราเคล ชมแพ": "MC-PC",
}
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
STATE_CACHE_STATUS = "cache_status"
STATE_DATA_SOURCE_WARNING = "data_source_warning"
STATE_REPORT_UPDATED_AT = "report_updated_at"
STATE_SIDEBAR_OPEN = "sidebar_open"
STATE_PIPELINE_DF = "pipeline_df"
STATE_PIPELINE_UPLOAD_SIGNATURE = "pipeline_upload_signature"
STATE_PIPELINE_UPLOAD_MESSAGE = "pipeline_upload_message"
STATE_PIPELINE_METADATA = "pipeline_metadata"
META_CACHE_TTL_SECONDS = 30 * 60


def _format_currency(value):
    if pd.isna(value):
        return "-"
    return f"฿{value:,.2f}"


def _format_baht_number(value):
    if pd.isna(value):
        return "-"
    return f"{value:,.2f}"


def _format_number(value):
    return f"{value:,.0f}"


def _format_percent(value):
    return f"{value:.2f}%"


def _safe_divide(numerator, denominator):
    return safe_divide_value(numerator, denominator)


def _display_separation_note():
    st.caption("Lead and Inbox metrics are separated by Primary Result Type.")


def _blank_non_primary_result_metrics(display_df):
    display_df = display_df.copy()
    if "Primary Result Type" not in display_df.columns:
        return display_df
    lead_rows = display_df["Primary Result Type"] == "Lead"
    inbox_rows = display_df["Primary Result Type"] == "Inbox"
    for column in ["Inbox Messages", "Cost per Inbox"]:
        if column in display_df.columns:
            display_df.loc[lead_rows, column] = pd.NA
    for column in ["Leads", "Cost per Lead"]:
        if column in display_df.columns:
            display_df.loc[inbox_rows, column] = pd.NA
    return display_df


def _primary_result_type(row):
    """Classify dashboard primary result intent before applying shared metric math."""
    campaign_name = str(row.get("campaign", "")).lower()
    result_type = str(row.get("result_type", "")).lower()
    if "inbox" in campaign_name or "messaging" in result_type or "inbox" in result_type:
        return "Inbox"
    if "leadgen" in campaign_name or "lead" in campaign_name or "lead" in result_type:
        return "Lead"
    return "Mixed / Unknown"


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
            _meta_account_cache_key(),
            _date_range_cache_key(use_custom_range, date_from, date_to, preset),
        ]
    )


def _date_range_cache_key(use_custom_range, date_from, date_to, preset):
    if use_custom_range:
        return f"custom:{date_from.isoformat()}:{date_to.isoformat()}"
    return f"preset:{preset}"


@st.cache_data(show_spinner=False, ttl=META_CACHE_TTL_SECONDS)
def _cached_meta_ads_data(
    account_cache_key,
    date_range_cache_key,
    _project_root,
    date_from_text="",
    date_to_text="",
    preset="",
):
    if date_from_text and date_to_text:
        meta_df = load_meta_ads_data(
            Path(_project_root),
            date_from=date_from_text,
            date_to=date_to_text,
        )
    else:
        meta_df = load_meta_ads_data(Path(_project_root), date_preset=preset)
    if meta_df is not None:
        meta_df.attrs["cache_created_at"] = datetime.utcnow().isoformat(timespec="seconds")
    return meta_df


def _styles(dark_theme=True):
    if not dark_theme:
        return
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
    st.markdown(
        """
        <style>
            :root {
                --bg: #0b1220;
                --bg-soft: #0f172a;
                --panel: #111827;
                --panel-2: #1e293b;
                --border: #334155;
                --text: #f8fafc;
                --muted: #94a3b8;
                --cyan: #22d3ee;
                --blue: #60a5fa;
                --green: #34d399;
                --orange: #fb923c;
                --shadow: 0 20px 54px rgba(2, 6, 23, 0.42);
            }
            #MainMenu, footer {
                visibility: hidden;
                height: 0;
            }
            header[data-testid="stHeader"] {
                visibility: visible !important;
                height: 2.75rem !important;
                background: transparent !important;
                pointer-events: auto !important;
            }
            /* Force sidebar visible */
            section[data-testid="stSidebar"] {
                display: block !important;
                visibility: visible !important;
                transform: none !important;
                margin-left: 0 !important;
                pointer-events: auto !important;
            }
            /* Show sidebar toggle button */
            button[kind="header"] {
                display: flex !important;
                opacity: 1 !important;
                visibility: visible !important;
                pointer-events: auto !important;
            }
            /* Show collapsed control */
            [data-testid="collapsedControl"] {
                display: flex !important;
                visibility: visible !important;
                opacity: 1 !important;
                pointer-events: auto !important;
            }
            /* Prevent accidental hidden nav */
            section[data-testid="stSidebarNav"] {
                display: block !important;
                visibility: visible !important;
            }
            .stApp, html, body, [data-testid="stAppViewContainer"] {
                background:
                    radial-gradient(circle at 18% 0%, rgba(34, 211, 238, 0.08), transparent 25%),
                    linear-gradient(180deg, var(--bg) 0%, var(--bg-soft) 100%) !important;
                color: var(--text) !important;
                font-family: Inter, "Segoe UI", system-ui, sans-serif !important;
                font-size: 14px;
            }
            html, body, [class*="css"] {
                font-family: "Inter", "Segoe UI", sans-serif !important;
                letter-spacing: 0 !important;
            }
            * {
                box-sizing: border-box;
            }
            h1, h2, h3, h4 {
                line-height: 1.2 !important;
                margin-bottom: 0.4rem !important;
            }
            .material-symbols-rounded,
            .material-symbols-outlined,
            .material-icons,
            span[data-testid="stIconMaterial"],
            i[data-testid="stIconMaterial"] {
                font-family: "Material Symbols Rounded", "Material Symbols Outlined", "Material Icons" !important;
                font-weight: normal !important;
                font-style: normal !important;
                letter-spacing: normal !important;
                line-height: 1 !important;
                text-transform: none !important;
                white-space: nowrap !important;
                word-wrap: normal !important;
                direction: ltr !important;
                -webkit-font-feature-settings: "liga" !important;
                -webkit-font-smoothing: antialiased !important;
                font-feature-settings: "liga" !important;
            }
            .block-container {
                max-width: 1600px;
                padding: 1rem 1.7rem 2.5rem;
            }
            [data-testid="stSidebar"] {
                background: linear-gradient(180deg, #070d19 0%, #0b1120 100%) !important;
                border-right: 1px solid var(--border);
                box-shadow: 18px 0 36px rgba(2, 6, 23, 0.32);
            }
            [data-testid="stSidebar"] [data-testid="stMarkdownContainer"],
            [data-testid="stSidebar"] label,
            [data-testid="stSidebar"] span,
            [data-testid="stSidebar"] p {
                color: var(--muted) !important;
                font-size: 13px !important;
                font-weight: 500 !important;
            }
            [data-testid="stSidebar"] h1,
            [data-testid="stSidebar"] h2,
            [data-testid="stSidebar"] h3 {
                color: var(--text) !important;
                font-size: 18px !important;
                font-weight: 700 !important;
                letter-spacing: 0;
            }
            [data-testid="stSidebar"] [data-baseweb="select"] > div,
            [data-testid="stSidebar"] input,
            [data-testid="stSidebar"] textarea,
            [data-testid="stSidebar"] [data-baseweb="input"] {
                background: var(--panel) !important;
                border-color: var(--border) !important;
                border-radius: 8px !important;
                color: var(--text) !important;
                font-size: 13px !important;
            }
            [data-testid="stFileUploader"] {
                background: rgba(17, 24, 39, 0.88);
                border: 1px dashed #475569;
                border-radius: 8px;
                padding: 12px;
            }
            div.stButton > button,
            [data-testid="stDownloadButton"] button {
                background: linear-gradient(135deg, #1d4ed8, #0891b2) !important;
                border: 1px solid rgba(96, 165, 250, 0.55) !important;
                border-radius: 8px !important;
                color: var(--text) !important;
                font-size: 14px !important;
                font-weight: 600 !important;
                letter-spacing: 0 !important;
                line-height: 1.2 !important;
                min-height: 42px;
                padding: 0.58rem 0.82rem !important;
                box-shadow: 0 12px 30px rgba(14, 165, 233, 0.18);
            }
            .exec-header,
            .kpi-card,
            .decision-card,
            .note-card,
            .insight-group,
            .creative-row,
            div[data-testid="stDataFrame"],
            [data-testid="stPlotlyChart"] {
                background: linear-gradient(180deg, rgba(17, 24, 39, 0.96), rgba(15, 23, 42, 0.98)) !important;
                border: 1px solid var(--border) !important;
                border-radius: 8px !important;
                box-shadow: var(--shadow) !important;
                color: var(--text) !important;
            }
            .exec-header {
                background:
                    radial-gradient(circle at 12% 0%, rgba(34, 211, 238, 0.18), transparent 28%),
                    linear-gradient(135deg, #0f172a 0%, #111827 58%, #0b1120 100%) !important;
                padding: 22px 24px !important;
                margin-bottom: 16px !important;
            }
            .exec-header h1 {
                font-size: 30px !important;
                line-height: 1.15 !important;
                font-weight: 700 !important;
                letter-spacing: 0 !important;
            }
            .subtitle {
                font-size: 14px !important;
                line-height: 1.45 !important;
                font-weight: 500 !important;
            }
            .dashboard-header-row {
                display: flex;
                align-items: center;
                justify-content: space-between;
                gap: 22px;
            }
            .header-badges {
                display: flex;
                flex-wrap: wrap;
                justify-content: flex-end;
                gap: 8px;
                max-width: 760px;
            }
            .header-pill {
                min-height: 36px;
                display: inline-flex;
                align-items: center;
                gap: 7px;
                white-space: nowrap;
                color: var(--muted);
                background: rgba(30, 41, 59, 0.72);
                border: 1px solid var(--border);
                border-radius: 999px;
                padding: 8px 12px;
                font-size: 12px;
                font-weight: 600;
                line-height: 1;
            }
            .header-pill span {
                color: var(--muted);
                font-size: 11px;
                font-weight: 700;
                text-transform: uppercase;
                letter-spacing: 0.06em;
            }
            .header-pill strong {
                color: var(--text);
                font-size: 12px;
                font-weight: 700;
            }
            .data-source-pill {
                border-color: rgba(96, 165, 250, 0.48);
                background: rgba(37, 99, 235, 0.16);
            }
            .data-source-pill strong {
                color: var(--cyan);
            }
            .section-title {
                color: var(--text) !important;
                font-size: 20px;
                font-weight: 700;
                margin: 16px 0 8px;
                padding-left: 12px;
                border-left: 3px solid var(--cyan);
            }
            .table-title-bar {
                margin: 14px 0 0;
                padding: 11px 14px;
                background: linear-gradient(180deg, rgba(17, 24, 39, 0.98), rgba(15, 23, 42, 0.98));
                border: 1px solid var(--border);
                border-bottom: 0;
                border-radius: 8px 8px 0 0;
                color: var(--text);
                font-size: 15px;
                font-weight: 700;
                letter-spacing: 0;
            }
            .table-title-bar + div[data-testid="stDataFrame"] {
                border-top-left-radius: 0 !important;
                border-top-right-radius: 0 !important;
            }
            .brand { color: var(--cyan) !important; }
            .subtitle,
            .date-range,
            .kpi-group,
            .kpi-label,
            .decision-label,
            .decision-detail,
            .insight-copy,
            .creative-campaign,
            .row-label {
                color: var(--muted) !important;
            }
            .date-range {
                background: rgba(30, 41, 59, 0.78) !important;
                border: 1px solid var(--border);
                border-radius: 8px;
            }
            .kpi-card {
                position: relative;
                min-height: 132px;
                padding: 18px 18px !important;
                overflow: hidden;
            }
            .kpi-card::before {
                content: "";
                position: absolute;
                inset: 0 auto 0 0;
                width: 3px;
                background: var(--blue);
            }
            .kpi-card.accent-leads::before { background: var(--cyan); }
            .kpi-card.accent-inbox::before { background: var(--blue); }
            .kpi-card.accent-contacts::before { background: var(--green); }
            .kpi-card.accent-cpl::before { background: var(--orange); }
            .kpi-icon {
                width: 34px;
                height: 34px;
                display: inline-flex;
                align-items: center;
                justify-content: center;
                border-radius: 8px;
                background: rgba(30, 41, 59, 0.9);
                border: 1px solid var(--border);
                color: var(--cyan);
                font-size: 15px;
                font-weight: 700;
            }
            .kpi-topline {
                display: flex;
                justify-content: space-between;
                align-items: center;
                gap: 10px;
            }
            .kpi-value,
            .decision-value,
            .insight-heading,
            .insight-name,
            .creative-title,
            .creative-title a,
            .row-value {
                color: var(--text) !important;
            }
            .kpi-value {
                font-size: 32px;
                line-height: 1.08;
                font-weight: 700;
                letter-spacing: 0;
                margin-top: 8px;
            }
            .kpi-label,
            .kpi-group,
            .decision-label,
            .row-label {
                font-size: 11px !important;
                line-height: 1.2;
                font-weight: 700 !important;
                text-transform: uppercase;
                letter-spacing: 0.06em !important;
            }
            .decision-detail,
            .insight-copy,
            .creative-campaign {
                font-size: 13px !important;
                line-height: 1.45;
                font-weight: 500 !important;
            }
            .decision-value,
            .insight-heading,
            .insight-name,
            .creative-title {
                font-weight: 700 !important;
            }
            .card-grid {
                grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)) !important;
                gap: 14px !important;
                margin-bottom: 12px !important;
            }
            [data-testid="stPlotlyChart"] {
                padding: 10px;
                margin-bottom: 10px;
            }
            .empty-chart-card {
                min-height: 380px;
                display: flex;
                align-items: center;
                justify-content: center;
                text-align: center;
                background: linear-gradient(180deg, rgba(17, 24, 39, 0.96), rgba(15, 23, 42, 0.98));
                border: 1px solid var(--border);
                border-radius: 8px;
                box-shadow: var(--shadow);
                color: var(--muted);
                font-weight: 800;
                padding: 18px;
            }
            .stDataFrame,
            [data-testid="stDataFrame"],
            div[data-testid="stDataFrame"] {
                background: #071226 !important;
                color: #dbe7ff !important;
                overflow: hidden;
            }
            div[data-testid="stDataFrame"] div[role="grid"] {
                background: #071226 !important;
                color: #dbe7ff !important;
                border-color: rgba(120,160,255,0.12) !important;
                font-size: 12.5px !important;
                font-weight: 400 !important;
            }
            div[data-testid="stDataFrame"],
            div[data-testid="stDataFrame"] table,
            div[data-testid="stDataFrame"] [role="grid"],
            div[data-testid="stDataFrame"] [data-testid="stTable"] {
                background: #071226 !important;
                border-color: rgba(120,160,255,0.12) !important;
            }
            div[data-testid="stDataFrame"] [role="columnheader"] {
                background: #0f1c36 !important;
                color: #8fb7ff !important;
                border-color: rgba(120,160,255,0.12) !important;
                border-bottom: 1px solid rgba(120,160,255,0.12) !important;
                position: sticky;
                top: 0;
                z-index: 2;
                font-size: 12px !important;
                font-weight: 650 !important;
            }
            div[data-testid="stDataFrame"] thead,
            div[data-testid="stDataFrame"] thead tr,
            div[data-testid="stDataFrame"] th {
                background: #0f1c36 !important;
                color: #8fb7ff !important;
                border-color: rgba(120,160,255,0.12) !important;
            }
            div[data-testid="stDataFrame"] tbody,
            div[data-testid="stDataFrame"] tbody tr,
            div[data-testid="stDataFrame"] td,
            div[data-testid="stDataFrame"] [role="gridcell"] {
                background: #071226 !important;
                color: #dbe7ff !important;
                border-color: rgba(120,160,255,0.08) !important;
                font-size: 12.5px !important;
                font-weight: 400 !important;
            }
            div[data-testid="stDataFrame"] tbody tr:nth-child(even),
            div[data-testid="stDataFrame"] [role="row"]:nth-child(even) [role="gridcell"] {
                background: #0b1730 !important;
            }
            div[data-testid="stDataFrame"] tbody tr:hover,
            div[data-testid="stDataFrame"] [role="row"]:hover [role="gridcell"] {
                background: #13264a !important;
            }
            div[data-testid="stDataFrame"] [role="row"]:nth-child(even) {
                background: #0b1730 !important;
            }
            div[data-testid="stDataFrame"] [role="row"]:hover {
                background: #13264a !important;
            }
            div[data-testid="stDataFrame"] [role="row"]:nth-child(even) [role="gridcell"],
            div[data-testid="stDataFrame"] [role="row"]:nth-child(even) [role="columnheader"] {
                background: #0b1730 !important;
            }
            div[data-testid="stDataFrame"] [role="row"]:hover [role="gridcell"],
            div[data-testid="stDataFrame"] [role="row"]:hover [role="columnheader"] {
                background: #13264a !important;
            }
            div[data-testid="stDataFrame"] * {
                border-color: rgba(120,160,255,0.12) !important;
            }
            /* Typography and spacing polish */
            div[data-testid="stVerticalBlock"] {
                gap: 0.75rem !important;
            }
            div[data-testid="stHorizontalBlock"] {
                gap: 12px !important;
                align-items: stretch !important;
            }
            [data-testid="column"] {
                min-width: 0 !important;
            }
            [data-testid="stWidgetLabel"],
            [data-testid="stWidgetLabel"] p,
            label,
            .stMarkdown p,
            .stCaptionContainer,
            [data-testid="stCaptionContainer"] {
                font-size: 13px !important;
                line-height: 1.45 !important;
                letter-spacing: 0 !important;
            }
            [data-testid="stWidgetLabel"] p,
            label {
                color: #cbd5e1 !important;
                font-weight: 600 !important;
                margin-bottom: 0.35rem !important;
            }
            div[data-testid="stExpander"] {
                border: 1px solid var(--border) !important;
                border-radius: 8px !important;
                background: rgba(17, 24, 39, 0.54) !important;
                overflow: hidden !important;
            }
            div[data-testid="stExpander"] details,
            div[data-testid="stExpander"] summary {
                color: var(--text) !important;
            }
            div[data-testid="stExpander"] summary {
                min-height: 44px !important;
                display: flex !important;
                align-items: center !important;
                gap: 10px !important;
                padding: 0.72rem 0.9rem !important;
                line-height: 1.25 !important;
                font-size: 14px !important;
                font-weight: 650 !important;
                letter-spacing: 0 !important;
            }
            div[data-testid="stExpander"] summary p {
                margin: 0 !important;
                line-height: 1.25 !important;
            }
            .section-title {
                margin: 18px 0 10px !important;
                font-size: 20px !important;
                line-height: 1.25 !important;
                letter-spacing: 0 !important;
            }
            .table-title-bar {
                min-height: 44px;
                display: flex;
                align-items: center;
                padding: 12px 15px !important;
                line-height: 1.25 !important;
            }
            .kpi-card {
                min-height: 140px !important;
                padding: 20px 20px 18px !important;
                display: flex;
                flex-direction: column;
                justify-content: space-between;
                gap: 8px;
            }
            .kpi-topline {
                min-height: 36px;
            }
            .kpi-label,
            .kpi-group {
                font-size: 11px !important;
                line-height: 1.25 !important;
                letter-spacing: 0.07em !important;
                margin: 0 !important;
            }
            .kpi-value {
                font-size: clamp(28px, 2.2vw, 36px) !important;
                line-height: 1.05 !important;
                margin-top: 6px !important;
                overflow-wrap: anywhere;
            }
            .decision-detail {
                min-height: 18px;
                overflow-wrap: anywhere;
            }
            .card-grid {
                gap: 16px !important;
                margin-bottom: 14px !important;
            }
            [data-testid="stSidebar"] {
                line-height: 1.45 !important;
            }
            [data-testid="stSidebar"] [data-testid="stMarkdownContainer"],
            [data-testid="stSidebar"] label,
            [data-testid="stSidebar"] span,
            [data-testid="stSidebar"] p,
            [data-testid="stSidebar"] small {
                line-height: 1.45 !important;
                letter-spacing: 0 !important;
            }
            [data-testid="stSidebar"] [data-testid="stFileUploader"] {
                padding: 14px !important;
                text-align: center !important;
            }
            [data-testid="stSidebar"] [data-testid="stFileUploader"] section {
                border-color: #475569 !important;
                border-radius: 8px !important;
                padding: 14px !important;
            }
            [data-testid="stSidebar"] [data-testid="stFileUploader"] button {
                margin: 8px auto 0 !important;
                min-height: 38px !important;
            }
            [data-testid="stSidebar"] [data-testid="stFileUploader"] p,
            [data-testid="stSidebar"] [data-testid="stFileUploader"] span {
                font-size: 12.5px !important;
                line-height: 1.45 !important;
                white-space: normal !important;
            }
            .stButton button {
                font-size: 14px !important;
                font-weight: 600 !important;
                letter-spacing: 0 !important;
                line-height: 1.2 !important;
                min-height: 42px !important;
                white-space: normal !important;
                word-break: normal !important;
            }
            div[data-testid="stSlider"],
            div[data-testid="stSelectbox"],
            div[data-testid="stMultiSelect"],
            div[data-testid="stDateInput"] {
                margin-bottom: 0 !important;
            }
            div[data-baseweb="select"] > div,
            div[data-baseweb="input"] > div,
            [data-testid="stDateInput"] input {
                min-height: 42px !important;
                align-items: center !important;
            }
            div[data-testid="stDataFrame"] {
                font-size: 13px !important;
            }
            div[data-testid="stDataFrame"] [role="columnheader"],
            div[data-testid="stDataFrame"] th {
                background: #0f1c36 !important;
                color: #8fb7ff !important;
                font-size: 12.5px !important;
                font-weight: 700 !important;
                line-height: 1.35 !important;
                min-height: 36px !important;
                padding: 9px 10px !important;
            }
            div[data-testid="stDataFrame"] [role="gridcell"],
            div[data-testid="stDataFrame"] td {
                background: #071226 !important;
                color: #dbe7ff !important;
                border-color: rgba(120,160,255,0.08) !important;
                font-size: 12.75px !important;
                line-height: 1.42 !important;
                min-height: 34px !important;
                padding: 8px 10px !important;
                vertical-align: middle !important;
            }
            div[data-testid="stDataFrame"] [role="row"] {
                min-height: 34px !important;
            }
            div[data-testid="stDataFrame"] td:not(:first-child),
            div[data-testid="stDataFrame"] th:not(:first-child) {
                text-align: right !important;
            }
            .badge-good { background: rgba(16, 185, 129, 0.16); color: var(--green); }
            .badge-watch { background: rgba(251, 146, 60, 0.16); color: var(--orange); }
            .badge-risk { background: rgba(248, 113, 113, 0.16); color: #f87171; }
            .badge-action { background: rgba(96, 165, 250, 0.16); color: var(--blue); }
            .note-card { border-left: 4px solid var(--blue) !important; }
            .note-card.warning { border-left-color: var(--orange) !important; }
            .note-card.risk { border-left-color: #f87171 !important; }
            .note-card.ok { border-left-color: var(--green) !important; }
            .no-preview {
                background: var(--panel-2) !important;
                color: var(--muted) !important;
                border: 1px solid var(--border);
                border-radius: 8px !important;
            }
            [data-testid="stAlert"] {
                background: var(--panel) !important;
                color: var(--text) !important;
                border: 1px solid var(--border) !important;
                border-radius: 8px !important;
            }
            @media (max-width: 900px) {
                .dashboard-header-row {
                    flex-direction: column;
                }
                .header-badges {
                    justify-content: flex-start;
                    min-width: 0;
                }
                .block-container {
                    padding-left: 1rem;
                    padding-right: 1rem;
                }
            }
            .st-key-debug_matching_diagnostics {
                opacity: 0.72;
                margin-top: 8px;
            }
            .st-key-debug_matching_diagnostics .section-title {
                color: #94a3b8 !important;
                border-left-color: #475569 !important;
                font-size: 16px !important;
                margin-top: 8px !important;
            }
            .st-key-debug_matching_diagnostics div[data-testid="stExpander"] {
                border-color: rgba(71, 85, 105, 0.58) !important;
                background: rgba(15, 23, 42, 0.42) !important;
                box-shadow: none !important;
            }
            .st-key-debug_matching_diagnostics div[data-testid="stExpander"] summary {
                min-height: 38px !important;
                padding: 0.55rem 0.78rem !important;
                font-size: 12.5px !important;
                color: #94a3b8 !important;
                font-weight: 600 !important;
            }
            .st-key-debug_matching_diagnostics div[data-testid="stExpander"] [data-testid="stCaptionContainer"],
            .st-key-debug_matching_diagnostics div[data-testid="stExpander"] p {
                font-size: 12px !important;
                color: #94a3b8 !important;
            }
            .st-key-debug_matching_diagnostics div[data-testid="stDataFrame"] {
                box-shadow: none !important;
                border-color: rgba(71, 85, 105, 0.48) !important;
            }
            .dark-html-table-wrap {
                width: 100%;
                max-height: 360px;
                overflow: auto;
                background: #071226;
                border: 1px solid rgba(120,160,255,0.12);
                border-radius: 0 0 8px 8px;
                box-shadow: var(--shadow);
            }
            .dark-html-table {
                width: 100%;
                min-width: 980px;
                border-collapse: collapse;
                background: #071226;
                color: #dbe7ff;
                font-size: 12.75px;
                line-height: 1.42;
            }
            .dark-html-table thead th {
                position: sticky;
                top: 0;
                z-index: 2;
                background: #0f1c36;
                color: #8fb7ff;
                border: 1px solid rgba(120,160,255,0.12);
                padding: 9px 10px;
                text-align: left;
                font-weight: 700;
                white-space: nowrap;
            }
            .dark-html-table tbody tr:nth-child(odd) td {
                background: #071226;
            }
            .dark-html-table tbody tr:nth-child(even) td {
                background: #0b1730;
            }
            .dark-html-table tbody tr:hover td {
                background: #13264a;
            }
            .dark-html-table td {
                color: #dbe7ff;
                border: 1px solid rgba(120,160,255,0.12);
                padding: 8px 10px;
                vertical-align: middle;
                white-space: nowrap;
            }
            .dark-html-table td:first-child,
            .dark-html-table th:first-child {
                white-space: normal;
                min-width: 220px;
            }
            .dark-html-table .numeric-cell {
                text-align: right;
                font-variant-numeric: tabular-nums;
            }
        </style>
        """,
        unsafe_allow_html=True,
    )


def _sidebar_visibility_styles(sidebar_open):
    if sidebar_open:
        return
    st.markdown(
        """
        <style>
            section[data-testid="stSidebar"] {
                display: block !important;
                visibility: visible !important;
                width: 0 !important;
                min-width: 0 !important;
                max-width: 0 !important;
                flex: 0 0 0 !important;
                overflow: hidden !important;
                border-right: 0 !important;
                box-shadow: none !important;
            }
            section[data-testid="stSidebar"] > div,
            section[data-testid="stSidebar"] [data-testid="stSidebarContent"] {
                display: none !important;
                visibility: hidden !important;
                width: 0 !important;
                min-width: 0 !important;
                max-width: 0 !important;
                overflow: hidden !important;
            }
            [data-testid="stAppViewContainer"],
            [data-testid="stMain"],
            .main {
                margin-left: 0 !important;
                max-width: 100% !important;
            }
            .block-container {
                max-width: 1600px !important;
                padding-left: 1.7rem !important;
                padding-right: 1.7rem !important;
            }
            button[kind="header"],
            [data-testid="collapsedControl"] {
                display: flex !important;
                opacity: 1 !important;
                visibility: visible !important;
                pointer-events: auto !important;
            }
        </style>
        """,
        unsafe_allow_html=True,
    )


def _render_sidebar_toggle():
    sidebar_open = st.session_state.get(STATE_SIDEBAR_OPEN, True)
    label = "Hide controls" if sidebar_open else "Show controls"
    toggle_columns = st.columns([0.16, 0.84])
    with toggle_columns[0]:
        if st.button(label, key="custom_sidebar_visibility_toggle", use_container_width=True):
            st.session_state[STATE_SIDEBAR_OPEN] = not sidebar_open
            st.rerun()


class _HiddenSidebarSlot:
    def caption(self, *args, **kwargs):
        return None

    def empty(self, *args, **kwargs):
        return None

    def download_button(self, *args, **kwargs):
        return None


def _apply_plotly_dark_theme(fig):
    fig.update_layout(
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font={"color": "#f8fafc", "family": 'Inter, "Segoe UI", system-ui, sans-serif', "size": 13},
        title={"font": {"color": "#f8fafc", "size": 18, "family": 'Inter, "Segoe UI", system-ui, sans-serif'}},
        legend={
            "bgcolor": "rgba(17,24,39,0.72)",
            "bordercolor": "#334155",
            "borderwidth": 1,
            "font": {"color": "#cbd5e1", "size": 11},
            "itemsizing": "constant",
        },
        hoverlabel={
            "bgcolor": "#111827",
            "bordercolor": "#334155",
            "font": {"color": "#f8fafc", "size": 12},
        },
        colorway=[
            "#22d3ee",
            "#60a5fa",
            "#34d399",
            "#fb923c",
            "#a78bfa",
            "#f472b6",
            "#f87171",
            "#cbd5e1",
        ],
        margin={"l": 28, "r": 22, "t": 54, "b": 34},
    )
    fig.update_xaxes(
        gridcolor="rgba(51,65,85,0.45)",
        zerolinecolor="rgba(51,65,85,0.65)",
        linecolor="#334155",
        tickfont={"color": "#94a3b8"},
        title_font={"color": "#cbd5e1"},
    )
    fig.update_yaxes(
        gridcolor="rgba(51,65,85,0.45)",
        zerolinecolor="rgba(51,65,85,0.65)",
        linecolor="#334155",
        tickfont={"color": "#94a3b8"},
        title_font={"color": "#cbd5e1"},
    )
    return fig


def _render_plotly_chart(container, fig):
    container.plotly_chart(_apply_plotly_dark_theme(fig), use_container_width=True)


def _load_dashboard_data(use_custom_range, date_from, date_to, preset, raise_rate_limit=False):
    live_error = None
    try:
        meta_df = _cached_meta_ads_data(
            _meta_account_cache_key(),
            _date_range_cache_key(use_custom_range, date_from, date_to, preset),
            str(PROJECT_ROOT),
            date_from.isoformat() if use_custom_range else "",
            date_to.isoformat() if use_custom_range else "",
            "" if use_custom_range else preset,
        )
        if meta_df is not None:
            meta_df.attrs["cache_status"] = _cache_status_from_created_at(
                meta_df.attrs.get("cache_created_at", "")
            )
    except Exception as error:
        live_error = error
        meta_df = None

    if meta_df is None:
        if live_error and RATE_LIMIT_MESSAGE in str(live_error) and raise_rate_limit:
            raise RuntimeError(RATE_LIMIT_MESSAGE) from live_error
        file_cache_df = _load_file_cache()
        if file_cache_df is not None:
            if live_error:
                if RATE_LIMIT_MESSAGE in str(live_error):
                    file_cache_df.attrs["data_source_warning"] = (
                        f"{RATE_LIMIT_MESSAGE} Showing cached file data."
                    )
                else:
                    file_cache_df.attrs["data_source_warning"] = (
                        f"Live Meta Ads data unavailable: {live_error}. Showing cached file data."
                    )
            return file_cache_df
        if DATA_PATH.exists():
            meta_df = pd.read_csv(DATA_PATH, parse_dates=["date"])
            meta_df.attrs["date_range_label"] = "Report Date Range: Sample CSV"
            meta_df.attrs["cache_status"] = "Sample CSV fallback"
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
    report_updated_at = meta_df.attrs.get("report_updated_at") or meta_df.attrs.get(
        "cache_created_at", ""
    )
    data_source_warning = meta_df.attrs.get("data_source_warning", "")
    cache_status = meta_df.attrs.get("cache_status", "")
    meta_df["date"] = pd.to_datetime(meta_df["date"])
    if "adset" not in meta_df.columns:
        meta_df["adset"] = ""
    meta_df = add_metrics(meta_df)
    meta_df["project"] = meta_df.apply(
        lambda row: _extract_project(row["campaign"], row["adset"]), axis=1
    )
    meta_df = _apply_primary_result_logic(meta_df)
    meta_df.attrs["date_range_label"] = date_range_label
    meta_df.attrs["report_updated_at"] = report_updated_at or datetime.utcnow().isoformat(
        timespec="seconds"
    )
    if cache_status:
        meta_df.attrs["cache_status"] = cache_status
    if data_source_warning:
        meta_df.attrs["data_source_warning"] = data_source_warning
    return meta_df


def _load_pipeline_upload(uploaded_file):
    if uploaded_file is None:
        return pd.DataFrame()
    file_name = getattr(uploaded_file, "name", "")
    extension = Path(file_name).suffix.lower()
    if extension not in {".csv", ".xlsx", ".xls"}:
        st.sidebar.warning(
            "Sale Pipeline upload must be a .csv, .xlsx, or .xls file."
        )
        return pd.DataFrame()

    file_bytes = uploaded_file.getvalue()
    legacy_html_export = False
    try:
        if extension == ".csv":
            pipeline_df = pd.read_csv(io.BytesIO(file_bytes))
        elif extension == ".xls":
            try:
                pipeline_df = pd.read_excel(io.BytesIO(file_bytes), engine="xlrd")
            except Exception as excel_error:
                pipeline_df = _read_legacy_html_excel_export(file_bytes, excel_error)
                legacy_html_export = True
        else:
            pipeline_df = pd.read_excel(io.BytesIO(file_bytes), engine="openpyxl")
    except Exception as error:
        st.sidebar.warning(
            f"Sale Pipeline {extension} file could not be parsed. "
            f"Check that it is a valid {extension} file and includes the expected columns. "
            f"Details: {error}"
        )
        return pd.DataFrame()

    pipeline_df.columns = [str(column).strip() for column in pipeline_df.columns]
    pipeline_df = _rename_pipeline_columns(pipeline_df)
    missing_columns = [
        column for column in PIPELINE_REQUIRED_COLUMNS if column not in pipeline_df.columns
    ]
    if missing_columns:
        detected_columns = ", ".join(str(column) for column in pipeline_df.columns)
        st.sidebar.warning(
            "Sale Pipeline file missing required columns: "
            + ", ".join(missing_columns)
            + f". Detected columns: {detected_columns}"
        )
        return pd.DataFrame()

    pipeline_df = pipeline_df[PIPELINE_REQUIRED_COLUMNS].copy()
    pipeline_df["created_date_raw"] = pipeline_df["created_date"]
    pipeline_df["created_date"] = _parse_pipeline_created_dates(pipeline_df["created_date"])
    pipeline_df["pipeline_project"] = pipeline_df[PIPELINE_PROJECT_COLUMN].apply(
        _normalize_pipeline_project_name
    )
    pipeline_df["pipeline_project_key"] = pipeline_df["pipeline_project"].apply(
        _normalize_pipeline_project_key
    )
    pipeline_df["is_organic"] = pipeline_df.apply(_is_organic_pipeline_row, axis=1)
    pipeline_df["pipeline_bucket"] = pipeline_df["is_organic"].apply(
        lambda is_organic: ORGANIC_BUCKET_NAME if is_organic else ""
    )
    pipeline_df["pipeline_result_type"] = pipeline_df["is_organic"].apply(
        lambda is_organic: ORGANIC_RESULT_TYPE if is_organic else ""
    )
    pipeline_df["adset_key"] = pipeline_df["adset_name"].apply(
        _normalize_pipeline_adset_key
    )
    if legacy_html_export:
        st.sidebar.info("Loaded legacy HTML Excel export")
    return pipeline_df


def _pipeline_upload_signature(uploaded_file):
    if uploaded_file is None:
        return ""
    file_name = getattr(uploaded_file, "name", "")
    try:
        file_bytes = uploaded_file.getvalue()
    except Exception:
        file_bytes = b""
    file_size = len(file_bytes)
    checksum = hashlib.md5(file_bytes).hexdigest() if file_bytes else ""
    return f"{file_name}:{file_size}:{checksum}"


def _pipeline_upload_metadata(uploaded_file, pipeline_df, signature):
    return {
        "file_name": getattr(uploaded_file, "name", ""),
        "row_count": int(len(pipeline_df)),
        "parsed_at": datetime.utcnow().isoformat(timespec="seconds"),
        "signature": signature,
        "source": "Uploaded Session",
    }


def _save_pipeline_cache(pipeline_df, metadata=None):
    try:
        PIPELINE_CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
        pipeline_df.to_parquet(PIPELINE_CACHE_PATH, index=False)
    except Exception as error:
        print(f"Pipeline cache save failed: {error.__class__.__name__}", flush=True)


def _load_pipeline_cache():
    if not PIPELINE_CACHE_PATH.exists():
        return None
    try:
        pipeline_df = pd.read_parquet(PIPELINE_CACHE_PATH)
    except Exception as error:
        print(f"Pipeline cache load failed: {error.__class__.__name__}", flush=True)
        return None
    return pipeline_df


def _restore_pipeline_cache_to_session():
    if STATE_PIPELINE_DF in st.session_state:
        return False
    pipeline_df = _load_pipeline_cache()
    if pipeline_df is None:
        return False
    st.session_state[STATE_PIPELINE_DF] = pipeline_df
    st.session_state[STATE_PIPELINE_METADATA] = {
        "file_name": PIPELINE_CACHE_PATH.name,
        "row_count": int(len(pipeline_df)),
        "parsed_at": datetime.utcfromtimestamp(
            PIPELINE_CACHE_PATH.stat().st_mtime
        ).isoformat(timespec="seconds"),
        "signature": f"{PIPELINE_CACHE_PATH.name}:{PIPELINE_CACHE_PATH.stat().st_size}",
        "source": "Cached Pipeline File",
    }
    st.session_state[STATE_PIPELINE_UPLOAD_SIGNATURE] = st.session_state[
        STATE_PIPELINE_METADATA
    ]["signature"]
    return True


def _is_organic_pipeline_row(row):
    channel_text = _normalize_organic_detection_text(row.get("channel", ""))
    adset_text = _normalize_organic_detection_text(row.get("adset_name", ""))
    return (
        "organic" in channel_text
        or adset_text in {"", "-"}
        or "organic" in adset_text
    )


def _normalize_organic_detection_text(value):
    if pd.isna(value):
        return ""
    text = unicodedata.normalize("NFKC", str(value))
    text = text.replace("\u00a0", " ")
    text = text.translate(
        str.maketrans(
            {
                "\u2010": "-",
                "\u2011": "-",
                "\u2012": "-",
                "\u2013": "-",
                "\u2014": "-",
                "\u2212": "-",
                "\ufe58": "-",
                "\ufe63": "-",
                "\uff0d": "-",
            }
        )
    )
    return re.sub(r"\s+", " ", text.strip()).casefold()


def _read_legacy_html_excel_export(file_bytes, excel_error):
    html_bytes = file_bytes.lstrip(b"\xef\xbb\xbf").lstrip()
    lower_html = html_bytes[:512].lower()
    looks_like_html = (
        lower_html.startswith(b"<html")
        or lower_html.startswith(b"<!doctype html")
        or b"<table" in file_bytes.lower()
    )
    if not looks_like_html:
        raise excel_error

    tables = pd.read_html(io.BytesIO(file_bytes))
    if not tables:
        raise ValueError("No HTML tables found in legacy Excel export.") from excel_error
    return tables[0]


def _normalize_pipeline_project_name(value):
    if pd.isna(value):
        return ""
    return " ".join(str(value).split())


def _normalize_pipeline_project_key(value):
    if pd.isna(value):
        return ""
    text = unicodedata.normalize("NFKC", str(value))
    text = text.replace("\u00a0", " ")
    text = text.translate(
        str.maketrans(
            {
                "\u2010": "-",
                "\u2011": "-",
                "\u2012": "-",
                "\u2013": "-",
                "\u2014": "-",
                "\u2212": "-",
                "\ufe58": "-",
                "\ufe63": "-",
                "\uff0d": "-",
                "\u2018": "'",
                "\u2019": "'",
                "\u201c": '"',
                "\u201d": '"',
                "\uff0c": ",",
                "\u3001": ",",
                "\uff0f": "/",
            }
        )
    )
    text = re.sub(r"\s+", " ", text.strip())
    text = re.sub(r"\s*-\s*", "-", text)
    text = re.sub(r"\s*/\s*", "/", text)
    return text.casefold()


def _normalize_match_key(value):
    return _normalize_meta_adset_key(value)


def _normalize_meta_adset_key(value):
    return extract_core_adset_key(value)


def _normalize_pipeline_adset_key(value):
    return extract_core_adset_key(value)


def extract_core_adset_key(name):
    normalized = _normalize_adset_name(name)
    if not normalized:
        return ""

    tokens = _expand_concatenated_adset_tokens(normalized.split())
    objective_index = None
    objective_token = ""
    for index, token in enumerate(tokens):
        objective_token = ADSET_OBJECTIVE_ALIASES.get(token, "")
        if objective_token:
            objective_index = index
            break
    if objective_index is None or objective_index == 0:
        return ""

    group_index = None
    group_token = ""
    for index in range(objective_index + 1, len(tokens)):
        group_match = re.fullmatch(r"g\s*(\d+)", tokens[index])
        if group_match:
            group_index = index
            group_token = f"g{group_match.group(1)}"
            break
    if group_index is None:
        return ""

    project_tokens = tokens[:objective_index]
    core_tokens = [*project_tokens, objective_token, group_token]
    return " ".join(core_tokens)


def extract_core_adset_creative_type(name):
    normalized = _normalize_adset_name(name)
    if not normalized:
        return ""

    tokens = _expand_concatenated_adset_tokens(normalized.split())
    for index, token in enumerate(tokens):
        if not re.fullmatch(r"g\s*\d+", token):
            continue
        creative_index = index + 1
        if creative_index < len(tokens) and tokens[creative_index] in {"vdo", "pic"}:
            return tokens[creative_index]
        return ""
    return ""


def _expand_concatenated_adset_tokens(tokens):
    expanded_tokens = []
    for token in tokens:
        match = re.fullmatch(
            r"(lead|leadgen|leadpage|inbox|inboxvdo|inboxpic)g(\d+)",
            token,
        )
        if match:
            objective = ADSET_OBJECTIVE_ALIASES.get(match.group(1), match.group(1))
            expanded_tokens.extend([objective, f"g{match.group(2)}"])
            continue
        expanded_tokens.append(token)
    return expanded_tokens


def _normalize_adset_name(value, expand_pipeline_abbreviations=False):
    if pd.isna(value):
        return ""
    text = unicodedata.normalize("NFKC", str(value))
    text = text.replace("\u00a0", " ")
    text = text.translate(
        str.maketrans(
            {
                "\u2010": "-",
                "\u2011": "-",
                "\u2012": "-",
                "\u2013": "-",
                "\u2014": "-",
                "\u2212": "-",
                "\ufe58": "-",
                "\ufe63": "-",
                "\uff0d": "-",
                "\uff0f": "/",
            }
        )
    )
    text = re.sub(r"[_\->/]+", " ", text.casefold())
    text = re.sub(r"\s+", " ", text.strip())
    if expand_pipeline_abbreviations:
        text = " ".join(
            PIPELINE_ADSET_ABBREVIATIONS.get(token, token)
            for token in text.split()
        )
    return re.sub(r"\s+", " ", text.strip())


def _remove_safe_adset_date_suffixes(text):
    previous_text = None
    while previous_text != text:
        previous_text = text
        text = re.sub(r"\s+\d{6}\s*$", "", text)
        text = re.sub(r"\s+\d{1,2}[/-]\d{1,2}[/-]\d{2,4}\s*$", "", text)
        text = re.sub(r"\s+\d{4}[/-]\d{1,2}[/-]\d{1,2}\s*$", "", text)
    return text


def _adset_token_key(value):
    normalized = _normalize_meta_adset_key(value)
    signature = _adset_match_signature(normalized)
    if not signature["project"] or not signature["objective"] or not signature["group"]:
        return ""
    return "|".join(
        [
            signature["project"],
            signature["objective"],
            signature["group"],
            signature["creative"] or "any",
        ]
    )


def _adset_match_signature(normalized_text):
    tokens = normalized_text.split()
    return {
        "project": _extract_adset_project_key(normalized_text),
        "objective": _extract_adset_objective_token(tokens),
        "group": _extract_adset_group_token(normalized_text),
        "creative": _extract_adset_creative_token(tokens),
    }


def _adset_base_token_key_from_signature(signature):
    if not signature["project"] or not signature["objective"] or not signature["group"]:
        return ""
    return "|".join([signature["project"], signature["objective"], signature["group"]])


def _adset_tokens_compatible(meta_signature, pipeline_signature):
    if _adset_base_token_key_from_signature(meta_signature) != _adset_base_token_key_from_signature(
        pipeline_signature
    ):
        return False
    meta_creative = meta_signature["creative"]
    pipeline_creative = pipeline_signature["creative"]
    return not meta_creative or not pipeline_creative or meta_creative == pipeline_creative


def _extract_adset_group_token(normalized_text):
    group_match = re.search(r"\bg\s*(\d+)\b", normalized_text)
    if not group_match:
        return ""
    return f"g{group_match.group(1)}"


def _extract_adset_objective_token(tokens):
    token_set = set(tokens)
    if token_set & {"inbox", "message", "messages", "messaging"}:
        return "inbox"
    if token_set & {"lead", "leads", "leadgen", "leadpage"}:
        return "lead"
    if token_set & {"engage", "engagement"}:
        return "engage"
    return ""


def _extract_adset_creative_token(tokens):
    token_set = set(tokens)
    if "vdo" in token_set:
        return "vdo"
    if "pic" in token_set:
        return "pic"
    return ""


def _legacy_adset_token_key(value):
    normalized = _normalize_meta_adset_key(value)
    if not normalized:
        return ""
    project_key = _extract_adset_project_key(normalized)
    group_match = re.search(r"\bg\s*(\d+)\b", normalized)
    if not project_key or not group_match:
        return ""
    media_key = _extract_adset_media_key(normalized)
    return "|".join([project_key, group_match.group(1), media_key])


def _adset_fallback_key(value):
    return _adset_token_key(value)


def _extract_adset_project_key(normalized_text):
    compact_text = re.sub(r"[^0-9a-z]+", "", normalized_text)
    aliases = {
        "tmst": "tm12st",
        "tm12st": "tm12st",
        "tmsv1011": "tmsv1011",
        "tm-sv101-1": "tmsv1011",
    }
    for alias, project_key in aliases.items():
        if re.sub(r"[^0-9a-z]+", "", alias) in compact_text:
            return project_key
    for project_name in PROJECT_MATCH_ORDER:
        project_key = re.sub(r"[^0-9a-z]+", "", project_name.casefold())
        if project_key and project_key in compact_text:
            return project_key
    return ""


def _extract_adset_media_key(normalized_text):
    if re.search(
        r"\b(?:ib|inbox|inboxvdo|inboxpic|inboxpage|inbox vdo|inbox pic|inbox page)\b",
        normalized_text,
    ):
        return "inbox"
    if re.search(r"\b(?:lead|leadpage|leadgen|lead page)\b", normalized_text):
        return "lead"
    return "any"


def _parse_pipeline_created_dates(values):
    return values.apply(_parse_pipeline_created_date)


def _parse_pipeline_created_date(value):
    if pd.isna(value):
        return pd.NaT

    if isinstance(value, (datetime, date)):
        return pd.to_datetime(value, errors="coerce")

    if isinstance(value, (int, float)) and not isinstance(value, bool):
        if 20000 <= float(value) <= 80000:
            return pd.to_datetime(value, unit="D", origin="1899-12-30", errors="coerce")
        return pd.to_datetime(value, errors="coerce", dayfirst=True)

    date_text = _normalize_pipeline_date_text(value)
    return pd.to_datetime(date_text, errors="coerce", dayfirst=True)


def _normalize_pipeline_date_text(value):
    text = unicodedata.normalize("NFKC", str(value))
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"\s+", " ", text.replace("\u00a0", " ").strip())

    thai_months = {
        "มกราคม": "01",
        "ม.ค.": "01",
        "มค": "01",
        "กุมภาพันธ์": "02",
        "ก.พ.": "02",
        "กพ": "02",
        "มีนาคม": "03",
        "มี.ค.": "03",
        "มีค": "03",
        "เมษายน": "04",
        "เม.ย.": "04",
        "เมย": "04",
        "พฤษภาคม": "05",
        "พ.ค.": "05",
        "พค": "05",
        "มิถุนายน": "06",
        "มิ.ย.": "06",
        "มิย": "06",
        "กรกฎาคม": "07",
        "ก.ค.": "07",
        "กค": "07",
        "สิงหาคม": "08",
        "ส.ค.": "08",
        "สค": "08",
        "กันยายน": "09",
        "ก.ย.": "09",
        "กย": "09",
        "ตุลาคม": "10",
        "ต.ค.": "10",
        "ตค": "10",
        "พฤศจิกายน": "11",
        "พ.ย.": "11",
        "พย": "11",
        "ธันวาคม": "12",
        "ธ.ค.": "12",
        "ธค": "12",
    }
    for thai_month, month_number in thai_months.items():
        text = text.replace(thai_month, month_number)

    text = re.sub(
        r"\b(25\d{2})\b",
        lambda match: str(int(match.group(1)) - 543),
        text,
    )
    return text


def _filter_pipeline_by_date_range(pipeline_df, date_from, date_to):
    if pipeline_df.empty:
        return pipeline_df.copy()

    filtered_df = pipeline_df.copy()
    parsed_dates = filtered_df["created_date"]
    unparsed_count = int(parsed_dates.isna().sum())
    if unparsed_count:
        st.sidebar.warning(
            f"Sale Pipeline rows with unparsed created_date excluded: {unparsed_count:,}"
        )

    start_date = pd.Timestamp(date_from)
    end_date = pd.Timestamp(date_to) + pd.Timedelta(days=1) - pd.Timedelta(microseconds=1)
    filtered_df = filtered_df[
        parsed_dates.notna()
        & (parsed_dates >= start_date)
        & (parsed_dates <= end_date)
    ].copy()
    return filtered_df


def _rename_pipeline_columns(pipeline_df):
    rename_map = {}
    existing_columns = set(pipeline_df.columns)
    for canonical_column, aliases in PIPELINE_COLUMN_ALIASES.items():
        for alias in aliases:
            alias = alias.strip()
            if alias in existing_columns:
                rename_map[alias] = canonical_column
                break
    return pipeline_df.rename(columns=rename_map)


def _pipeline_project_summary(pipeline_df):
    if pipeline_df.empty:
        return pd.DataFrame(
            columns=[
                "pipeline_project",
                "pipeline_project_key",
                *PIPELINE_CONTACT_COLUMNS,
            ]
        )

    summary_df = pipeline_df.copy()
    if "is_organic" not in summary_df.columns:
        summary_df["is_organic"] = False
    summary_df["is_organic"] = summary_df["is_organic"].fillna(False).astype(bool)
    summary_df["paid_contact"] = (~summary_df["is_organic"]).astype(int)
    summary_df["organic_contact"] = summary_df["is_organic"].astype(int)

    return (
        summary_df.groupby(["pipeline_project", "pipeline_project_key"], as_index=False)
        .agg(
            total_contacts=("pipeline_project", "size"),
            paid_contacts=("paid_contact", "sum"),
            organic_contacts=("organic_contact", "sum"),
        )
    )


def _pipeline_adset_summary(pipeline_df):
    if pipeline_df.empty:
        return pd.DataFrame(
            columns=[
                "adset_name",
                "adset_key",
                "normalized_pipeline_key",
                "pipeline_created_date",
                "pipeline_creative_type",
                "total_contacts",
            ]
        )

    summary_df = pipeline_df.copy()
    if "is_organic" in summary_df.columns:
        summary_df = summary_df[~summary_df["is_organic"].fillna(False).astype(bool)]
    summary_df["adset_name"] = summary_df["adset_name"].fillna("").astype(str).str.strip()
    summary_df = summary_df[summary_df["adset_key"] != ""]
    summary_df["pipeline_created_date"] = pd.to_datetime(
        summary_df["created_date"], errors="coerce"
    ).dt.date
    summary_df["pipeline_creative_type"] = summary_df["adset_name"].apply(
        extract_core_adset_creative_type
    )
    if summary_df.empty:
        return pd.DataFrame(
            columns=[
                "adset_name",
                "adset_key",
                "normalized_pipeline_key",
                "pipeline_created_date",
                "pipeline_creative_type",
                "total_contacts",
            ]
        )

    return (
        summary_df.groupby(
            ["adset_key", "pipeline_created_date", "pipeline_creative_type"],
            as_index=False,
            dropna=False,
        )
        .agg(
            adset_name=("adset_name", "first"),
            normalized_pipeline_key=("adset_key", "first"),
            total_contacts=("adset_key", "size"),
        )
    )


def _join_pipeline_project_data(project_df, pipeline_project_df):
    contact_columns = PIPELINE_CONTACT_COLUMNS
    if pipeline_project_df.empty:
        joined_df = project_df.copy()
        for column in contact_columns:
            joined_df[column] = 0
        return _ensure_project_contact_metrics(joined_df)

    mapped_pipeline_df = _mapped_pipeline_projects(pipeline_project_df)
    mapped_project_df = (
        mapped_pipeline_df.groupby("project", as_index=False)[contact_columns].sum()
    )

    joined_df = project_df.merge(mapped_project_df, on="project", how="left")
    for column in contact_columns:
        joined_df[column] = joined_df[column].fillna(0).astype(int)
    return _ensure_project_contact_metrics(joined_df)


def _ensure_project_contact_metrics(project_df):
    project_df = project_df.copy()
    has_total_contacts = "total_contacts" in project_df.columns
    has_paid_contacts = "paid_contacts" in project_df.columns
    has_organic_contacts = "organic_contacts" in project_df.columns
    if has_total_contacts and not has_paid_contacts and not has_organic_contacts:
        project_df["paid_contacts"] = project_df["total_contacts"]
        project_df["organic_contacts"] = 0
    for column in PIPELINE_CONTACT_COLUMNS:
        if column not in project_df.columns:
            project_df[column] = 0
        project_df[column] = (
            pd.to_numeric(project_df[column], errors="coerce")
            .fillna(0)
            .astype(int)
        )
    project_df["total_contacts"] = (
        project_df["paid_contacts"] + project_df["organic_contacts"]
    ).astype(int)
    project_df["cost_per_contact"] = project_df.apply(
        lambda row: pd.NA
        if row["total_contacts"] == 0
        else _safe_divide(row["spend"], row["total_contacts"]),
        axis=1,
    )
    return project_df


def _join_pipeline_adset_data(adset_df, pipeline_adset_df):
    adset_df = adset_df.copy()
    adset_df = adset_df.drop(
        columns=[
            "total_contacts",
            "cost_per_contact",
            "normalized_meta_key",
            "normalized_pipeline_key",
            "meta_creative_type",
            "pipeline_creative_type",
            "contact_join_key",
            "pipeline_contact_count",
            "duplicated_contact_flag",
            "match_status",
        ],
        errors="ignore",
    )
    if "adset" not in adset_df.columns:
        adset_df["adset"] = ""
    adset_df["adset_key"] = adset_df["adset"].apply(_normalize_meta_adset_key)
    adset_df["normalized_meta_key"] = adset_df["adset_key"]
    adset_df["meta_creative_type"] = adset_df["adset"].apply(
        extract_core_adset_creative_type
    )

    if pipeline_adset_df.empty:
        adset_df["total_contacts"] = 0
        adset_df["normalized_pipeline_key"] = ""
        adset_df["pipeline_creative_type"] = ""
        adset_df["contact_join_key"] = adset_df["adset_key"]
        adset_df["pipeline_contact_count"] = 0
        adset_df["duplicated_contact_flag"] = False
        adset_df["match_status"] = "no_match"
        joined_df = _ensure_adset_contact_metrics(adset_df).drop(
            columns=["adset_key"], errors="ignore"
        )
        joined_df.attrs["pipeline_adset_match_details"] = _empty_adset_match_details()
        return joined_df

    match_df, match_details = _match_pipeline_adsets(adset_df, pipeline_adset_df)
    joined_df = adset_df.merge(match_df, on="adset_key", how="left")
    joined_df["normalized_pipeline_key"] = joined_df["normalized_pipeline_key"].fillna("")
    joined_df["pipeline_creative_type"] = joined_df["pipeline_creative_type"].fillna("")
    joined_df["contact_join_key"] = joined_df["contact_join_key"].fillna(
        joined_df["adset_key"]
    )
    joined_df["pipeline_contact_count"] = (
        pd.to_numeric(joined_df["pipeline_contact_count"], errors="coerce")
        .fillna(0)
        .astype(int)
    )
    joined_df["match_status"] = joined_df["match_status"].fillna("no_match")
    joined_df = _allocate_adset_contacts(joined_df)
    joined_df = _ensure_adset_contact_metrics(joined_df).drop(
        columns=["adset_key"], errors="ignore"
    )
    joined_df.attrs["pipeline_adset_match_details"] = match_details
    return joined_df


def _join_adset_contacts_to_campaign(campaign_df, adset_df):
    campaign_df = campaign_df.copy()
    if adset_df.empty or "total_contacts" not in adset_df.columns:
        campaign_df["total_contacts"] = 0
        campaign_df["cost_per_contact"] = pd.NA
        return campaign_df

    contact_df = adset_df.copy()
    contact_df.loc[
        ~contact_df["primary_result_type"].isin(["Lead", "Inbox"]),
        "total_contacts",
    ] = 0
    contact_df["total_contacts"] = (
        pd.to_numeric(contact_df["total_contacts"], errors="coerce")
        .fillna(0)
        .astype(int)
    )
    contact_df = (
        contact_df.groupby(
            ["campaign", "project", "primary_result_type"],
            as_index=False,
        )
        .agg(total_contacts=("total_contacts", "sum"))
    )
    campaign_df = campaign_df.merge(
        contact_df,
        on=["campaign", "project", "primary_result_type"],
        how="left",
    )
    campaign_df["total_contacts"] = (
        pd.to_numeric(campaign_df["total_contacts"], errors="coerce")
        .fillna(0)
        .astype(int)
    )
    campaign_df["cost_per_contact"] = campaign_df.apply(
        lambda row: pd.NA
        if row["total_contacts"] <= 0
        else _safe_divide(row["spend"], row["total_contacts"]),
        axis=1,
    )
    return campaign_df


def _clear_non_primary_adset_contacts(adset_df):
    adset_df = adset_df.copy()
    if "primary_result_type" not in adset_df.columns:
        return _ensure_adset_contact_metrics(adset_df)

    non_primary_rows = ~adset_df["primary_result_type"].isin(["Lead", "Inbox"])
    if non_primary_rows.any():
        adset_df.loc[non_primary_rows, "total_contacts"] = 0
    return _ensure_adset_contact_metrics(adset_df)


def _join_campaign_contacts_to_project(project_df, campaign_df):
    project_df = project_df.copy()
    if campaign_df.empty or "total_contacts" not in campaign_df.columns:
        project_df["total_contacts"] = 0
        project_df["cost_per_contact"] = pd.NA
        return _ensure_project_contact_metrics(project_df)

    contact_df = campaign_df.copy()
    contact_df.loc[
        ~contact_df["primary_result_type"].isin(["Lead", "Inbox"]),
        "total_contacts",
    ] = 0
    contact_df["total_contacts"] = (
        pd.to_numeric(contact_df["total_contacts"], errors="coerce")
        .fillna(0)
        .astype(int)
    )
    contact_df = (
        contact_df.groupby(["project", "primary_result_type"], as_index=False)
        .agg(total_contacts=("total_contacts", "sum"))
    )

    project_df = project_df.drop(
        columns=["total_contacts", "paid_contacts", "organic_contacts", "cost_per_contact"],
        errors="ignore",
    )
    project_df = project_df.merge(
        contact_df,
        on=["project", "primary_result_type"],
        how="left",
    )
    project_df["total_contacts"] = (
        pd.to_numeric(project_df["total_contacts"], errors="coerce")
        .fillna(0)
        .astype(int)
    )
    project_df = _ensure_project_contact_metrics(project_df)
    _validate_project_campaign_contact_totals(project_df, campaign_df)
    return project_df


def _validate_project_campaign_contact_totals(project_df, campaign_df):
    if project_df.empty or campaign_df.empty or "total_contacts" not in campaign_df.columns:
        return

    project_totals = (
        project_df.groupby("project", as_index=False)
        .agg(project_contacts=("total_contacts", "sum"))
    )
    campaign_totals = campaign_df.copy()
    campaign_totals.loc[
        ~campaign_totals["primary_result_type"].isin(["Lead", "Inbox"]),
        "total_contacts",
    ] = 0
    campaign_totals["total_contacts"] = (
        pd.to_numeric(campaign_totals["total_contacts"], errors="coerce")
        .fillna(0)
        .astype(int)
    )
    campaign_totals = campaign_totals[
        campaign_totals["project"].isin(project_totals["project"])
    ]
    campaign_totals = (
        campaign_totals.groupby("project", as_index=False)
        .agg(campaign_contacts=("total_contacts", "sum"))
    )
    validation_df = project_totals.merge(campaign_totals, on="project", how="outer").fillna(0)
    mismatched_df = validation_df[
        validation_df["project_contacts"].astype(int)
        != validation_df["campaign_contacts"].astype(int)
    ]
    if mismatched_df.empty:
        return

    LOGGER.warning(
        "Project contact totals do not match summed campaign contacts: %s",
        mismatched_df.to_dict("records"),
    )


def _match_pipeline_adsets(meta_adset_df, pipeline_adset_df):
    meta_unique_df = (
        meta_adset_df[["adset", "adset_key", "normalized_meta_key", "meta_creative_type"]]
        .drop_duplicates()
        .query("adset_key != ''")
        .copy()
    )
    if "normalized_pipeline_key" not in pipeline_adset_df.columns:
        pipeline_adset_df = pipeline_adset_df.copy()
        pipeline_adset_df["normalized_pipeline_key"] = pipeline_adset_df["adset_key"]
    if "pipeline_creative_type" not in pipeline_adset_df.columns:
        pipeline_adset_df = pipeline_adset_df.copy()
        pipeline_adset_df["pipeline_creative_type"] = pipeline_adset_df[
            "adset_name"
        ].apply(extract_core_adset_creative_type)
    if "pipeline_created_date" not in pipeline_adset_df.columns:
        pipeline_adset_df = pipeline_adset_df.copy()
        pipeline_adset_df["pipeline_created_date"] = pd.NaT
    pipeline_unique_df = (
        pipeline_adset_df[
            [
                "adset_name",
                "adset_key",
                "normalized_pipeline_key",
                "pipeline_created_date",
                "pipeline_creative_type",
                "total_contacts",
            ]
        ]
        .drop_duplicates()
        .query("adset_key != ''")
        .copy()
    )

    exact_df = meta_unique_df.merge(
        pipeline_unique_df,
        on="adset_key",
        how="inner",
    )
    exact_df["pipeline_adset_key"] = exact_df["adset_key"]
    exact_df["match_type"] = "exact normalized"
    exact_df["match_status"] = "matched_exact"
    exact_df["contact_join_key"] = exact_df["adset_key"]
    exact_meta_keys = set(exact_df["adset_key"].tolist())
    exact_pipeline_keys = set(exact_df["adset_key"].tolist())

    token_df = pd.DataFrame()
    ambiguous_token_df = pd.DataFrame()
    matched_df = exact_df.copy()
    matched_pipeline_pool_df = pipeline_unique_df[
        pipeline_unique_df["adset_key"].isin(exact_meta_keys)
    ].copy()
    if matched_pipeline_pool_df.empty:
        contact_df = pd.DataFrame(
            columns=[
                "adset_key",
                "normalized_pipeline_key",
                "pipeline_creative_type",
                "contact_join_key",
                "pipeline_contact_count",
                "match_status",
            ]
        )
    else:
        contact_df = (
            matched_pipeline_pool_df.groupby("adset_key", as_index=False)
            .agg(
                normalized_pipeline_key=(
                    "normalized_pipeline_key",
                    lambda values: " | ".join(
                        sorted({str(value) for value in values if str(value).strip()})
                    ),
                ),
                pipeline_creative_type=(
                    "pipeline_creative_type",
                    lambda values: " | ".join(
                        sorted({str(value) for value in values if str(value).strip()})
                    ),
                ),
                contact_join_key=("adset_key", "first"),
                pipeline_contact_count=("total_contacts", "sum"),
            )
        )
        contact_df["match_status"] = "matched_exact"
    contact_df["pipeline_contact_count"] = pd.to_numeric(
        contact_df["pipeline_contact_count"], errors="coerce"
    ).fillna(0).astype(int)

    matched_meta_keys = set(matched_df["adset_key"].tolist()) if not matched_df.empty else set()
    matched_pipeline_keys = _split_matched_pipeline_keys(matched_df)
    details = {
        "exact": exact_df,
        "token": token_df,
        "fallback": token_df,
        "ambiguous_token": ambiguous_token_df,
        "unmatched_meta": meta_unique_df[
            ~meta_unique_df["adset_key"].isin(matched_meta_keys)
        ].copy(),
        "unmatched_pipeline": pipeline_unique_df[
            ~pipeline_unique_df["adset_key"].isin(matched_pipeline_keys | exact_pipeline_keys)
        ].copy(),
    }
    return contact_df, details


def _allocate_adset_contacts(joined_df):
    joined_df = joined_df.copy()
    joined_df["total_contacts"] = 0
    joined_df["duplicated_contact_flag"] = False

    if joined_df.empty or "contact_join_key" not in joined_df.columns:
        return joined_df

    for join_key, group in joined_df.groupby("contact_join_key", dropna=False):
        if not str(join_key or "").strip():
            continue
        pipeline_contact_count = int(group["pipeline_contact_count"].max())
        if pipeline_contact_count <= 0:
            continue

        row_count = len(group)
        duplicated = row_count > 1
        allocated = _allocate_contacts_by_spend(
            pipeline_contact_count,
            group["spend"],
        )
        joined_df.loc[group.index, "total_contacts"] = allocated
        joined_df.loc[group.index, "duplicated_contact_flag"] = duplicated

    joined_df["total_contacts"] = (
        pd.to_numeric(joined_df["total_contacts"], errors="coerce")
        .fillna(0)
        .astype(int)
    )
    joined_df["duplicated_contact_flag"] = joined_df[
        "duplicated_contact_flag"
    ].fillna(False).astype(bool)
    return joined_df


def _allocate_contacts_by_spend(total_contacts, spend_values):
    spend = pd.to_numeric(spend_values, errors="coerce").fillna(0)
    row_count = len(spend)
    if row_count == 0:
        return []
    if row_count == 1:
        return [int(total_contacts)]

    total_spend = spend.sum()
    if total_spend > 0:
        quotas = spend / total_spend * int(total_contacts)
    else:
        quotas = pd.Series(
            [int(total_contacts) / row_count] * row_count,
            index=spend.index,
        )

    base_allocations = quotas.apply(lambda value: int(value))
    remainder = int(total_contacts) - int(base_allocations.sum())
    if remainder > 0:
        fractional_order = (quotas - base_allocations).sort_values(
            ascending=False,
            kind="mergesort",
        )
        for index in fractional_order.index[:remainder]:
            base_allocations.loc[index] += 1
    return base_allocations.astype(int).tolist()


def _split_matched_pipeline_keys(matched_df):
    if matched_df.empty or "pipeline_adset_key" not in matched_df:
        return set()
    keys = set()
    for value in matched_df["pipeline_adset_key"].dropna().astype(str):
        keys.update(part.strip() for part in value.split(" | ") if part.strip())
    return keys


def _empty_adset_match_details():
    return {
        "exact": pd.DataFrame(),
        "token": pd.DataFrame(),
        "fallback": pd.DataFrame(),
        "ambiguous_token": pd.DataFrame(),
        "unmatched_meta": pd.DataFrame(),
        "unmatched_pipeline": pd.DataFrame(),
    }


def _token_adset_matches(meta_df, pipeline_df):
    columns = [
        "adset",
        "adset_key",
        "normalized_meta_key",
        "adset_name",
        "pipeline_adset_key",
        "normalized_pipeline_key",
        "total_contacts",
        "match_type",
        "match_status",
        "token_key",
    ]
    ambiguous_columns = [
        "token_key",
        "meta_adsets",
        "pipeline_adsets",
        "meta_count",
        "pipeline_count",
        "pipeline_contacts",
    ]
    if meta_df.empty or pipeline_df.empty:
        return pd.DataFrame(columns=columns), pd.DataFrame(columns=ambiguous_columns)

    meta_candidates = meta_df.copy()
    pipeline_candidates = pipeline_df.copy()
    meta_candidates["match_signature"] = meta_candidates["normalized_meta_key"].apply(
        _adset_match_signature
    )
    pipeline_candidates["match_signature"] = pipeline_candidates[
        "normalized_pipeline_key"
    ].apply(_adset_match_signature)
    meta_candidates["token_key"] = meta_candidates["match_signature"].apply(
        _adset_base_token_key_from_signature
    )
    pipeline_candidates["token_key"] = pipeline_candidates["match_signature"].apply(
        _adset_base_token_key_from_signature
    )
    meta_candidates = meta_candidates[meta_candidates["token_key"] != ""].copy()
    pipeline_candidates = pipeline_candidates[pipeline_candidates["token_key"] != ""].copy()
    if meta_candidates.empty or pipeline_candidates.empty:
        return pd.DataFrame(columns=columns), pd.DataFrame(columns=ambiguous_columns)

    accepted_rows = []
    ambiguous_keys = set()
    shared_keys = sorted(set(meta_candidates["token_key"]) & set(pipeline_candidates["token_key"]))
    for token_key in shared_keys:
        meta_group = meta_candidates[meta_candidates["token_key"] == token_key]
        pipeline_group = pipeline_candidates[pipeline_candidates["token_key"] == token_key]
        compatible_pairs = []
        for meta_index, meta_row in meta_group.iterrows():
            for pipeline_index, pipeline_row in pipeline_group.iterrows():
                if _adset_tokens_compatible(
                    meta_row["match_signature"], pipeline_row["match_signature"]
                ):
                    compatible_pairs.append((meta_index, pipeline_index))
        if not compatible_pairs:
            continue

        meta_counts = {}
        pipeline_counts = {}
        for meta_index, pipeline_index in compatible_pairs:
            meta_counts[meta_index] = meta_counts.get(meta_index, 0) + 1
            pipeline_counts[pipeline_index] = pipeline_counts.get(pipeline_index, 0) + 1

        accepted_pipeline_indexes = [
            pipeline_index
            for meta_index, pipeline_index in compatible_pairs
            if pipeline_counts[pipeline_index] == 1
        ]
        if not accepted_pipeline_indexes:
            ambiguous_keys.add(token_key)
            continue
        if any(pipeline_counts[pipeline_index] > 1 for _, pipeline_index in compatible_pairs):
            ambiguous_keys.add(token_key)

        accepted_pipeline_df = pipeline_group.loc[accepted_pipeline_indexes]
        for meta_index, matched_pipeline_df in accepted_pipeline_df.groupby(
            accepted_pipeline_df.index.map(
                {
                    pipeline_index: meta_index
                    for meta_index, pipeline_index in compatible_pairs
                    if pipeline_index in accepted_pipeline_indexes
                }
            )
        ):
            meta_row = meta_group.loc[meta_index]
            accepted_rows.append(
                {
                    "adset": meta_row["adset"],
                    "adset_key": meta_row["adset_key"],
                    "normalized_meta_key": meta_row["normalized_meta_key"],
                    "adset_name": " | ".join(matched_pipeline_df["adset_name"].astype(str)),
                    "pipeline_adset_key": " | ".join(
                        matched_pipeline_df["adset_key"].astype(str)
                    ),
                    "normalized_pipeline_key": " | ".join(
                        matched_pipeline_df["normalized_pipeline_key"].astype(str)
                    ),
                    "total_contacts": int(matched_pipeline_df["total_contacts"].sum()),
                    "match_type": "deterministic token key",
                    "match_status": "matched_token",
                    "token_key": token_key,
                }
            )

    token_df = pd.DataFrame(accepted_rows, columns=columns)

    ambiguous_rows = []
    for token_key in sorted(ambiguous_keys):
        meta_group = meta_candidates[meta_candidates["token_key"] == token_key]
        pipeline_group = pipeline_candidates[pipeline_candidates["token_key"] == token_key]
        ambiguous_rows.append(
            {
                "token_key": token_key,
                "meta_adsets": " | ".join(meta_group["adset"].astype(str).tolist()),
                "pipeline_adsets": " | ".join(pipeline_group["adset_name"].astype(str).tolist()),
                "meta_count": len(meta_group),
                "pipeline_count": len(pipeline_group),
                "pipeline_contacts": int(pipeline_group["total_contacts"].sum()),
            }
        )
    ambiguous_df = pd.DataFrame(ambiguous_rows, columns=ambiguous_columns)
    return token_df[columns], ambiguous_df


def _fallback_adset_matches(meta_df, pipeline_df):
    token_df, _ = _token_adset_matches(meta_df, pipeline_df)
    return token_df.drop(columns=["token_key"], errors="ignore")


def _ensure_adset_contact_metrics(adset_df):
    adset_df = adset_df.copy()
    if "total_contacts" not in adset_df.columns:
        adset_df["total_contacts"] = 0
    adset_df["total_contacts"] = (
        pd.to_numeric(adset_df["total_contacts"], errors="coerce")
        .fillna(0)
        .astype(int)
    )
    adset_df["cost_per_contact"] = adset_df.apply(
        lambda row: pd.NA
        if row["total_contacts"] == 0
        else _safe_divide(row["spend"], row["total_contacts"]),
        axis=1,
    )
    return adset_df


def _scalarize_display_value(value):
    if isinstance(value, (pd.DataFrame, pd.Series, list, tuple, dict, set)):
        return str(value)
    return value


def _scalarize_display_df(display_df):
    display_df = display_df.copy()
    display_df = display_df.loc[:, ~display_df.columns.duplicated()]
    return display_df.map(_scalarize_display_value)


def _display_series(df, column, default=None):
    if column not in df.columns:
        return pd.Series([default] * len(df), index=df.index)
    values = df[column]
    if isinstance(values, pd.DataFrame):
        values = values.iloc[:, 0]
    return values


def _adset_display_df(adset_df):
    source_columns = [
        ("project", "Project"),
        ("campaign", "Campaign"),
        ("adset", "Ad Set"),
        ("primary_result_type", "Primary Result Type"),
        ("spend", "Spend"),
        ("results", "Results"),
        ("inbox_messages", "Inbox Messages"),
        ("leads", "Leads"),
        ("total_contacts", "Contacts"),
        ("cost_per_contact", "Cost per Contact"),
        ("cost_per_result", "Cost per Result"),
        ("cost_per_inbox", "Cost per Inbox"),
        ("cost_per_lead", "Cost per Lead"),
        ("CTR", "CTR"),
        ("CPM", "CPM"),
        ("Frequency", "Frequency"),
    ]
    display_df = pd.DataFrame(index=adset_df.index)
    for source_column, display_column in source_columns:
        display_df[display_column] = _display_series(adset_df, source_column)

    numeric_columns = [
        "Spend",
        "Results",
        "Inbox Messages",
        "Leads",
        "Contacts",
        "Cost per Contact",
        "Cost per Result",
        "Cost per Inbox",
        "Cost per Lead",
        "CTR",
        "CPM",
        "Frequency",
    ]
    for column in numeric_columns:
        display_df[column] = pd.to_numeric(display_df[column], errors="coerce")

    display_df["Contacts"] = display_df["Contacts"].fillna(0).astype(int)
    display_df["Cost per Contact"] = display_df.apply(
        lambda row: pd.NA
        if row["Contacts"] <= 0
        else _safe_divide(row["Spend"], row["Contacts"]),
        axis=1,
    )
    display_df = _blank_non_primary_result_metrics(display_df)
    return _scalarize_display_df(display_df)


def _pipeline_project_mapping_frame():
    rows = [
        {
            "project": meta_project,
            "mapped_pipeline_project": _normalize_pipeline_project_name(pipeline_project),
            "pipeline_project_key": _normalize_pipeline_project_key(pipeline_project),
        }
        for pipeline_project, meta_project in PIPELINE_TO_META_PROJECTS.items()
    ]
    return pd.DataFrame(rows).drop_duplicates(
        subset=["project", "pipeline_project_key"], keep="first"
    )


def _mapped_pipeline_projects(pipeline_project_df):
    contact_columns = PIPELINE_CONTACT_COLUMNS
    if pipeline_project_df.empty:
        return pd.DataFrame(
            columns=[
                "project",
                "mapped_pipeline_project",
                "pipeline_project",
                "pipeline_project_key",
                *contact_columns,
            ]
        )

    mapping_df = _pipeline_project_mapping_frame()
    pipeline_project_df = pipeline_project_df.copy()
    for column in contact_columns:
        if column not in pipeline_project_df.columns:
            pipeline_project_df[column] = 0
    mapped_df = mapping_df.merge(
        pipeline_project_df,
        on="pipeline_project_key",
        how="inner",
    )
    mapped_df[contact_columns] = mapped_df[contact_columns].fillna(0)
    return mapped_df


def _unmatched_pipeline_projects(pipeline_project_df):
    if pipeline_project_df.empty:
        return pipeline_project_df

    mapped_keys = set(_pipeline_project_mapping_frame()["pipeline_project_key"].tolist())
    return pipeline_project_df[
        ~pipeline_project_df["pipeline_project_key"].isin(mapped_keys)
    ].copy()


def _pipeline_projects_debug(pipeline_project_df):
    if pipeline_project_df.empty:
        return

    mapped_df = _mapped_pipeline_projects(pipeline_project_df)
    unmatched_df = _unmatched_pipeline_projects(pipeline_project_df)

    if not mapped_df.empty:
        with st.expander("Mapped Sale Pipeline Project Counts", expanded=False):
            st.caption(
                "These Sale Pipeline project names are mapped to Meta project codes before Project Performance contact counts are joined."
            )
            display_df = mapped_df[
                [
                    "project",
                    "pipeline_project",
                    "total_contacts",
                ]
            ].rename(
                columns={
                    "project": "Meta Project",
                    "pipeline_project": "Sale Pipeline Project",
                    "total_contacts": "Contacts",
                }
            )
            _render_dark_dataframe(display_df, use_container_width=True, hide_index=True)

    if unmatched_df.empty:
        return

    with st.expander("Unmatched Sale Pipeline Projects", expanded=False):
        st.caption(
            "These Sale Pipeline project names were uploaded but are not mapped to a Meta project code."
        )
        display_df = unmatched_df.rename(
            columns={
                "pipeline_project": "Sale Pipeline Project",
                "total_contacts": "Contacts",
            }
        )
        _render_dark_dataframe(display_df, use_container_width=True, hide_index=True)


def _pipeline_adsets_debug(pipeline_adset_df, adset_df):
    match_details = adset_df.attrs.get("pipeline_adset_match_details", {})
    if not match_details and pipeline_adset_df.empty and adset_df.empty:
        return

    exact_df = match_details.get("exact", pd.DataFrame())
    token_df = match_details.get("token", match_details.get("fallback", pd.DataFrame()))
    ambiguous_token_df = match_details.get("ambiguous_token", pd.DataFrame())
    unmatched_meta_df = match_details.get("unmatched_meta", pd.DataFrame())
    unmatched_pipeline_df = match_details.get("unmatched_pipeline", pd.DataFrame())

    if not exact_df.empty:
        with st.expander("Ad Set Matches: Exact Normalized Name", expanded=False):
            display_df = exact_df[
                [
                    "adset",
                    "adset_name",
                    "normalized_meta_key",
                    "normalized_pipeline_key",
                    "meta_creative_type",
                    "pipeline_creative_type",
                    "match_status",
                    "total_contacts",
                ]
            ].rename(
                columns={
                    "adset": "Meta Ad Set",
                    "adset_name": "Sale Pipeline Ad Set",
                    "total_contacts": "Contacts",
                }
            )
            _render_dark_dataframe(display_df, use_container_width=True, hide_index=True)

    if not token_df.empty:
        with st.expander("Ad Set Matches: Unique Token Key", expanded=False):
            st.caption(
                "Token matches are accepted only when exactly one unmatched Meta ad set and one unmatched Sale Pipeline ad set share project code, result type, and group token."
            )
            token_columns = [
                "adset",
                "adset_name",
                "normalized_meta_key",
                "normalized_pipeline_key",
                "meta_creative_type",
                "pipeline_creative_type",
                "match_status",
                "total_contacts",
            ]
            if "token_key" in token_df.columns:
                token_columns.append("token_key")
            display_df = token_df[token_columns].rename(
                columns={
                    "adset": "Meta Ad Set",
                    "adset_name": "Sale Pipeline Ad Set",
                    "total_contacts": "Contacts",
                    "token_key": "Token Key",
                }
            )
            _render_dark_dataframe(display_df, use_container_width=True, hide_index=True)

    if not ambiguous_token_df.empty:
        with st.expander("Ad Set Matches: Ambiguous Token Keys", expanded=False):
            st.caption(
                "These token keys matched multiple Meta or Sale Pipeline ad sets, so no automatic contact match was applied."
            )
            display_df = ambiguous_token_df.rename(
                columns={
                    "token_key": "Token Key",
                    "meta_adsets": "Meta Ad Sets",
                    "pipeline_adsets": "Sale Pipeline Ad Sets",
                    "meta_count": "Meta Count",
                    "pipeline_count": "Pipeline Count",
                    "pipeline_contacts": "Pipeline Contacts",
                }
            )
            _render_dark_dataframe(display_df, use_container_width=True, hide_index=True)

    if not unmatched_pipeline_df.empty:
        with st.expander("Ad Set Matches: Unmatched Sale Pipeline Ad Sets", expanded=False):
            st.caption(
                "These Sale Pipeline ad set names were uploaded but did not match a selected Meta ad set."
            )
            display_df = unmatched_pipeline_df[["adset_name", "total_contacts"]].rename(
                columns={
                    "adset_name": "Sale Pipeline Ad Set",
                    "total_contacts": "Contacts",
                }
            )
            if "normalized_pipeline_key" in unmatched_pipeline_df.columns:
                display_df["normalized_pipeline_key"] = unmatched_pipeline_df[
                    "normalized_pipeline_key"
                ]
            if "pipeline_creative_type" in unmatched_pipeline_df.columns:
                display_df["pipeline_creative_type"] = unmatched_pipeline_df[
                    "pipeline_creative_type"
                ]
            _render_dark_dataframe(display_df, use_container_width=True, hide_index=True)

    if not unmatched_meta_df.empty:
        with st.expander("Ad Set Matches: Unmatched Meta Ad Sets", expanded=False):
            st.caption(
                "These selected Meta ad set names did not match any date-filtered Sale Pipeline ad set."
            )
            display_columns = ["adset"]
            if "normalized_meta_key" in unmatched_meta_df.columns:
                display_columns.append("normalized_meta_key")
            if "meta_creative_type" in unmatched_meta_df.columns:
                display_columns.append("meta_creative_type")
            display_df = unmatched_meta_df[display_columns].rename(
                columns={
                    "adset": "Meta Ad Set",
                }
            )
            _render_dark_dataframe(display_df, use_container_width=True, hide_index=True)


def _cache_status_from_created_at(cache_created_at):
    try:
        created_at = datetime.fromisoformat(cache_created_at)
    except (TypeError, ValueError):
        return "Meta cache active"
    age_seconds = (datetime.utcnow() - created_at).total_seconds()
    if age_seconds > 5:
        return "Streamlit cache hit"
    return "Live Meta fetch"


def _save_file_cache(ads_df):
    try:
        FILE_CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
        ads_df.to_parquet(FILE_CACHE_PATH, index=False)
    except Exception as error:
        print(f"File cache save failed: {error.__class__.__name__}", flush=True)


def _load_file_cache():
    if not FILE_CACHE_PATH.exists():
        return None
    try:
        cached_df = pd.read_parquet(FILE_CACHE_PATH)
    except Exception as error:
        print(f"File cache load failed: {error.__class__.__name__}", flush=True)
        return None
    cached_df.attrs["date_range_label"] = "Report Date Range: Cached File"
    cached_df.attrs["report_updated_at"] = datetime.utcfromtimestamp(
        FILE_CACHE_PATH.stat().st_mtime
    ).isoformat(timespec="seconds")
    cached_df.attrs["cache_status"] = "CACHED FILE DATA"
    return cached_df


def _restore_file_cache_to_session():
    cached_df = _load_file_cache()
    if cached_df is None:
        return False
    st.session_state[STATE_ADS_DF] = cached_df
    st.session_state[STATE_DATE_RANGE_LABEL] = cached_df.attrs.get("date_range_label", "")
    st.session_state[STATE_FETCH_REQUEST_KEY] = ""
    st.session_state[STATE_CACHE_STATUS] = "CACHED FILE DATA"
    st.session_state[STATE_DATA_SOURCE_WARNING] = cached_df.attrs.get("data_source_warning", "")
    st.session_state[STATE_REPORT_UPDATED_AT] = cached_df.attrs.get("report_updated_at", "")
    return True


def _should_save_file_cache(ads_df):
    cache_status = ads_df.attrs.get("cache_status", "")
    date_range_label = ads_df.attrs.get("date_range_label", "")
    if cache_status == "CACHED FILE DATA":
        return False
    if date_range_label == "Report Date Range: Sample CSV":
        return False
    return True


def _render_sidebar_data_controls(
    status_slot,
    updated_slot,
    csv_slot,
    ttl_slot,
    ads_df=None,
    filtered_df=None,
    report_updated_at="",
):
    status = st.session_state.get(STATE_CACHE_STATUS, "No cached report")
    if status == "CACHED FILE DATA":
        data_source = "CACHED FILE DATA"
    elif STATE_ADS_DF in st.session_state:
        data_source = "LIVE DATA"
    else:
        data_source = "No report loaded"
    status_slot.caption(f"Data source: {data_source}")
    updated_slot.caption(f"Last updated: {report_updated_at} UTC" if report_updated_at else "Last updated: -")
    if ads_df is not None:
        csv_df = filtered_df if filtered_df is not None and not filtered_df.empty else ads_df
        csv_slot.download_button(
            "Download current CSV",
            data=csv_df.to_csv(index=False).encode("utf-8-sig"),
            file_name="current-meta-ads.csv",
            mime="text/csv",
            use_container_width=True,
        )
    else:
        csv_slot.empty()
    ttl_slot.caption(f"Meta cache TTL: {META_CACHE_TTL_SECONDS // 60} minutes")


def _extract_project(campaign_name, adset_name=""):
    for source_name in (campaign_name, adset_name):
        source_name = str(source_name or "").upper()
        for alias, project_name in PROJECT_ALIASES.items():
            if alias.upper() in source_name:
                return project_name
        for project_name in PROJECT_MATCH_ORDER:
            if project_name.upper() in source_name:
                return project_name
    return "Other"


def _header(date_range_label, status="Ready", updated_at=""):
    clean_range = escape(date_range_label.replace("Report Date Range: ", "") or "Not generated")
    clean_status = escape(status or "Ready")
    clean_updated = escape(updated_at or "-")
    st.markdown(
        f"""
        <div class="exec-header">
            <div class="dashboard-header-row">
                <div>
                    <div class="brand">AKRA LAND ANALYTICS</div>
                    <h1>Meta Ads Performance Dashboard</h1>
                    <p class="subtitle">Pipeline-aware performance view for budget, contact, and creative decisions.</p>
                </div>
                <div class="header-badges">
                    <div class="header-pill"><span>Date Range</span><strong>{clean_range}</strong></div>
                    <div class="header-pill data-source-pill"><span>Data Source</span><strong>{clean_status}</strong></div>
                    <div class="header-pill"><span>Updated At</span><strong>{clean_updated}</strong></div>
                </div>
            </div>
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
        accent_class = _card_accent_class(label)
        icon = escape(str(card.get("icon", _card_icon(label))))
        classes = f"{card_class} {extra_class} {accent_class}".strip()
        html += (
            f'<div class="{classes}">'
            '<div class="kpi-topline">'
            f'<div class="kpi-group">{group}</div>'
            f'<div class="kpi-icon">{icon}</div>'
            "</div>"
            f'<div class="kpi-label">{label}</div>'
            f'<div class="kpi-value">{value}</div>'
            f'<div class="decision-detail">{detail}</div>'
            "</div>"
        )
    html += "</div>"
    st.markdown(html, unsafe_allow_html=True)


def _card_accent_class(label):
    label_text = label.casefold()
    if "cost per lead" in label_text or "cpl" in label_text:
        return "accent-cpl"
    if "lead" in label_text:
        return "accent-leads"
    if "inbox" in label_text:
        return "accent-inbox"
    if "contact" in label_text:
        return "accent-contacts"
    return ""


def _card_icon(label):
    label_text = label.casefold()
    if "lead" in label_text:
        return "L"
    if "inbox" in label_text:
        return "M"
    if "contact" in label_text:
        return "C"
    if "cost" in label_text:
        return "฿"
    if "spend" in label_text:
        return "฿"
    if "ctr" in label_text:
        return "%"
    return "•"


def _kpi_cards(filtered_df, campaign_df=None):
    total_spend = filtered_df["spend"].sum()
    total_results = filtered_df["results"].sum()
    inbox_df = filtered_df[filtered_df["primary_result_type"] == "Inbox"]
    lead_df = filtered_df[filtered_df["primary_result_type"] == "Lead"]
    total_inbox = inbox_df["inbox_messages"].sum()
    total_leads = lead_df["leads"].sum()
    total_contacts = 0
    if campaign_df is not None and "total_contacts" in campaign_df.columns:
        total_contacts = pd.to_numeric(
            campaign_df["total_contacts"], errors="coerce"
        ).fillna(0).sum()

    cards = [
        {
            "group": "Efficiency",
            "label": "Total Spend",
            "value": _format_currency(total_spend),
            "icon": "฿",
        },
        {
            "group": "Delivery",
            "label": "Results",
            "value": _format_number(total_results),
            "icon": "R",
        },
        {
            "group": "Messaging",
            "label": "Inbox Messages",
            "value": _format_number(total_inbox),
            "icon": "M",
        },
        {
            "group": "Lead Gen",
            "label": "Leads",
            "value": _format_number(total_leads),
            "icon": "L",
        },
        {
            "group": "Pipeline",
            "label": "Contacts",
            "value": _format_number(total_contacts),
            "icon": "C",
        },
        {
            "group": "Pipeline",
            "label": "Cost per Contact",
            "value": _format_currency(_safe_divide(total_spend, total_contacts)),
            "icon": "฿",
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



def _thai_performance_agency_summary_bullets(filtered_df, campaign_df, adset_df, creative_df):
    total_spend = filtered_df["spend"].sum()
    total_results = filtered_df["results"].sum()
    inbox_df = filtered_df[filtered_df["primary_result_type"] == "Inbox"]
    lead_df = filtered_df[filtered_df["primary_result_type"] == "Lead"]
    total_inbox = inbox_df.get("inbox_messages", pd.Series(dtype=float)).sum()
    total_leads = lead_df.get("leads", pd.Series(dtype=float)).sum()
    inbox_spend = inbox_df["spend"].sum()
    lead_spend = lead_df["spend"].sum()

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
            "สรุป Performance: งบรวม "
            f"{_format_currency(total_spend)} สร้างผลลัพธ์รวม "
            f"{_format_number(total_results)} ครั้ง ต้นทุนเฉลี่ยต่อผลลัพธ์อยู่ที่ "
            f"{_format_currency(cost_per_result)} ต้องบริหารงบด้วยตัวเลข ไม่ใช่ความรู้สึก."
        ),
        (
            "Lead และ Inbox ถูกแยกตาม Primary Result Type: "
            f"Lead campaigns ใช้งบ {_format_currency(lead_spend)} ได้ Lead {_format_number(total_leads)} ราย "
            f"ที่ {_format_currency(_safe_divide(lead_spend, total_leads))} ต่อ Lead."
        ),
        (
            f"Inbox campaigns ใช้งบ {_format_currency(inbox_spend)} ได้ Inbox "
            f"{_format_number(total_inbox)} ครั้ง ที่ {_format_currency(_safe_divide(inbox_spend, total_inbox))} ต่อ Inbox "
            "ไม่เอา Lead และ Inbox มาปนกันในการตัดสินประสิทธิภาพ."
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

    return bullets


def _thai_performance_agency_summary(filtered_df, campaign_df, adset_df, creative_df):
    bullets = _thai_performance_agency_summary_bullets(
        filtered_df, campaign_df, adset_df, creative_df
    )
    st.markdown("### สรุป Performance")
    _display_separation_note()
    for bullet in bullets:
        st.markdown(f"- {bullet}")
    return bullets


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


def _table_section_title(title):
    st.markdown(
        f"""
        <div class="table-title-bar">
            <div>{escape(title)}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def _dark_table_row_styles(row):
    row_bg = "#0b1730" if row.name % 2 else "#071226"
    return [
        (
            f"background-color: {row_bg}; "
            "color: #dbe7ff; "
            "border: 1px solid rgba(120,160,255,0.12); "
            "padding: 8px 10px;"
        )
        for _ in row
    ]


def _dark_table_header_styles():
    return [
        {
            "selector": "thead th",
            "props": [
                ("background-color", "#0f1c36"),
                ("color", "#8fb7ff"),
                ("border", "1px solid rgba(120,160,255,0.12)"),
                ("padding", "9px 10px"),
                ("font-weight", "700"),
                ("text-align", "left"),
            ],
        },
        {
            "selector": "tbody td",
            "props": [
                ("background-color", "#071226"),
                ("color", "#dbe7ff"),
                ("border", "1px solid rgba(120,160,255,0.12)"),
                ("padding", "8px 10px"),
            ],
        },
        {
            "selector": "tbody tr:hover td",
            "props": [
                ("background-color", "#13264a"),
                ("color", "#dbe7ff"),
            ],
        },
        {
            "selector": "table",
            "props": [
                ("background-color", "#071226"),
                ("border-collapse", "collapse"),
                ("border", "1px solid rgba(120,160,255,0.12)"),
            ],
        },
    ]


def _apply_dark_table_style(styler):
    return styler.apply(_dark_table_row_styles, axis=1).set_table_styles(
        _dark_table_header_styles(),
        overwrite=False,
    )


def _render_dark_dataframe(display_df, **kwargs):
    styled = _apply_dark_table_style(display_df.reset_index(drop=True).style)
    st.dataframe(styled, **kwargs)


def _performance_table_formatters():
    return {
        "Spend": _format_currency,
        "Results": "{:,.0f}",
        "Inbox Messages": lambda value: "-" if pd.isna(value) else f"{value:,.0f}",
        "Leads": lambda value: "-" if pd.isna(value) else f"{value:,.0f}",
        "Contacts": "{:,.0f}",
        "Cost per Contact": _format_currency,
        "Cost per Result": _format_currency,
        "Cost per Inbox": _format_currency,
        "Cost per Lead": _format_currency,
        "CTR": "{:.2f}%",
        "CPM": _format_currency,
        "Frequency": "{:.2f}",
    }


def _format_html_table_value(value, formatter=None):
    if formatter is None:
        return "-" if pd.isna(value) else str(value)
    if callable(formatter):
        return str(formatter(value))
    if pd.isna(value):
        return "-"
    return formatter.format(value)


def _render_dark_html_table(display_df, formatters=None, numeric_columns=None):
    formatters = formatters or {}
    numeric_columns = set(numeric_columns or [])
    display_df = display_df.reset_index(drop=True)
    header_html = "".join(
        f"<th>{escape(str(column))}</th>" for column in display_df.columns
    )
    row_html = []
    for _, row in display_df.iterrows():
        cells = []
        for column, value in row.items():
            cell_class = ' class="numeric-cell"' if column in numeric_columns else ""
            formatted_value = _format_html_table_value(value, formatters.get(column))
            cells.append(f"<td{cell_class}>{escape(formatted_value)}</td>")
        row_html.append(f"<tr>{''.join(cells)}</tr>")

    st.markdown(
        f"""
        <div class="dark-html-table-wrap">
            <table class="dark-html-table">
                <thead><tr>{header_html}</tr></thead>
                <tbody>{''.join(row_html)}</tbody>
            </table>
        </div>
        """,
        unsafe_allow_html=True,
    )


def _campaign_table(campaign_df):
    _table_section_title("Campaign Performance")
    _display_separation_note()
    sorted_df = campaign_df.sort_values("spend", ascending=False).copy()

    columns = [
        "campaign",
        "project",
        "primary_result_type",
        "spend",
        "results",
        "inbox_messages",
        "leads",
        "total_contacts",
        "cost_per_contact",
        "cost_per_result",
        "cost_per_inbox",
        "cost_per_lead",
        "CTR",
        "CPM",
        "Frequency",
    ]
    display_df = sorted_df[columns].copy().reset_index(drop=True)
    display_df = display_df.rename(
        columns={
            "campaign": "Campaign",
            "project": "Project",
            "primary_result_type": "Primary Result Type",
            "spend": "Spend",
            "results": "Results",
            "inbox_messages": "Inbox Messages",
            "leads": "Leads",
            "total_contacts": "Contacts",
            "cost_per_contact": "Cost per Contact",
            "cost_per_result": "Cost per Result",
            "cost_per_inbox": "Cost per Inbox",
            "cost_per_lead": "Cost per Lead",
        }
    )
    display_df = _blank_non_primary_result_metrics(display_df)

    _render_dark_html_table(
        display_df,
        formatters=_performance_table_formatters(),
        numeric_columns=[
            "Spend",
            "Results",
            "Inbox Messages",
            "Leads",
            "Contacts",
            "Cost per Contact",
            "Cost per Result",
            "Cost per Inbox",
            "Cost per Lead",
            "CTR",
            "CPM",
            "Frequency",
        ],
    )


def _adset_table(adset_df):
    _table_section_title("Ad Set Performance")
    st.caption("Only primary result metrics are shown in this table.")
    _display_separation_note()
    adset_df = _ensure_adset_contact_metrics(adset_df)
    display_df = _adset_display_df(adset_df).reset_index(drop=True)
    _render_dark_html_table(
        display_df,
        formatters=_performance_table_formatters(),
        numeric_columns=[
            "Spend",
            "Results",
            "Inbox Messages",
            "Leads",
            "Contacts",
            "Cost per Contact",
            "Cost per Result",
            "Cost per Inbox",
            "Cost per Lead",
            "CTR",
            "CPM",
            "Frequency",
        ],
    )


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
    grouped["results"] = grouped.apply(
        lambda row: row["leads"]
        if row["primary_result_type"] == "Lead"
        else row["inbox_messages"]
        if row["primary_result_type"] == "Inbox"
        else row["results"],
        axis=1,
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
        rollup_df.groupby(["project", "primary_result_type"], as_index=False)
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
    grouped["results"] = grouped.apply(
        lambda row: row["leads"]
        if row["primary_result_type"] == "Lead"
        else row["inbox_messages"]
        if row["primary_result_type"] == "Inbox"
        else row["results"],
        axis=1,
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


def _dashboard_top_chart_row(daily_df, project_df):
    st.markdown('<div class="section-title">Overview Trends</div>', unsafe_allow_html=True)
    trend_fig = spend_vs_results_by_day(daily_df)
    trend_fig.update_layout(height=420)
    _render_plotly_chart(st, trend_fig)

    project_contacts_df = _project_contact_chart_df(project_df)
    if project_contacts_df.empty or project_contacts_df["contacts"].sum() <= 0:
        chart_columns = st.columns(2)
        _empty_chart_card(chart_columns[0])
        _empty_chart_card(chart_columns[1])
        return

    st.markdown('<div class="section-title">Pipeline Contact Efficiency</div>', unsafe_allow_html=True)
    chart_columns = st.columns(2)

    contacts_fig = px.bar(
        project_contacts_df.sort_values("contacts", ascending=False).head(10),
        x="contacts",
        y="project",
        orientation="h",
        color="contacts",
        title="Contacts by Project",
        color_continuous_scale=["#1e293b", "#34d399"],
    )
    contacts_fig.update_layout(yaxis={"categoryorder": "total ascending"}, height=380)
    contacts_fig.update_xaxes(title="Contacts")
    contacts_fig.update_yaxes(title="")

    cpc_df = project_contacts_df[project_contacts_df["contacts"] > 0].copy()
    cpc_df = cpc_df.sort_values("cost_per_contact", ascending=True).head(10)
    cpc_df["cost_per_contact_plot"] = (
        pd.to_numeric(cpc_df["cost_per_contact"], errors="coerce").round(2)
    )
    cpc_df["cost_per_contact_display"] = cpc_df["cost_per_contact_plot"].apply(
        _format_baht_number
    )
    cpc_fig = px.bar(
        cpc_df,
        x="cost_per_contact_plot",
        y="project",
        orientation="h",
        title="Cost per Contact by Project",
        custom_data=["cost_per_contact_display", "contacts"],
    )
    cpc_fig.update_layout(
        yaxis={"categoryorder": "total descending"},
        height=380,
        showlegend=False,
    )
    cpc_fig.update_traces(
        marker_color="#22d3ee",
        hovertemplate=(
            "<b>%{y}</b><br>"
            "Cost / Contact: ฿%{customdata[0]}<br>"
            "Contacts: %{customdata[1]:,.0f}<extra></extra>"
        )
    )
    cpc_fig.update_xaxes(title="Cost / Contact", tickformat=",.2f")
    cpc_fig.update_yaxes(title="")

    _render_plotly_chart(chart_columns[0], contacts_fig)
    _render_plotly_chart(chart_columns[1], cpc_fig)


def _empty_chart_card(container):
    container.markdown(
        '<div class="empty-chart-card">Upload pipeline data to view contact charts.</div>',
        unsafe_allow_html=True,
    )


def _project_contact_chart_df(project_df):
    if project_df.empty or "total_contacts" not in project_df.columns:
        return pd.DataFrame(columns=["project", "spend", "contacts", "cost_per_contact"])

    chart_df = project_df.copy()
    chart_df = chart_df[chart_df["primary_result_type"].isin(["Lead", "Inbox"])]
    chart_df["total_contacts"] = pd.to_numeric(
        chart_df["total_contacts"], errors="coerce"
    ).fillna(0)
    chart_df = (
        chart_df.groupby("project", as_index=False)
        .agg(
            spend=("spend", "sum"),
            contacts=("total_contacts", "sum"),
        )
    )
    chart_df["cost_per_contact"] = chart_df.apply(
        lambda row: pd.NA
        if row["contacts"] <= 0
        else _safe_divide(row["spend"], row["contacts"]),
        axis=1,
    )
    return chart_df


def _project_performance(project_df):
    _table_section_title("Project Performance")
    _display_separation_note()
    project_df = _ensure_project_contact_metrics(project_df)
    if _verify_project_aggregation(project_df):
        st.caption(
            "Project costs are recalculated after grouping: total spend / primary results, inbox campaign spend / inbox campaign results, and lead campaign spend / lead campaign results."
        )
    display_df = project_df[
        [
            "project",
            "primary_result_type",
            "spend",
            "results",
            "inbox_messages",
            "leads",
            "total_contacts",
            "cost_per_contact",
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
            "primary_result_type": "Primary Result Type",
            "spend": "Spend",
            "results": "Results",
            "inbox_messages": "Inbox Messages",
            "leads": "Leads",
            "total_contacts": "Contacts",
            "cost_per_contact": "Cost per Contact",
            "cost_per_result": "Cost per Result",
            "cost_per_inbox": "Cost per Inbox",
            "cost_per_lead": "Cost per Lead",
        }
    )
    display_df = display_df.reset_index(drop=True)
    display_df = _blank_non_primary_result_metrics(display_df)
    _render_dark_html_table(
        display_df,
        formatters=_performance_table_formatters(),
        numeric_columns=[
            "Spend",
            "Results",
            "Inbox Messages",
            "Leads",
            "Contacts",
            "Cost per Contact",
            "Cost per Result",
            "Cost per Inbox",
            "Cost per Lead",
            "CTR",
            "CPM",
            "Frequency",
        ],
    )

    chart_columns = st.columns(2)
    inbox_df = project_df[project_df["primary_result_type"] == "Inbox"].sort_values(
        "inbox_messages", ascending=False
    )
    leads_df = project_df[project_df["primary_result_type"] == "Lead"].sort_values(
        "leads", ascending=False
    )
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

    _render_plotly_chart(chart_columns[0], inbox_fig)
    _render_plotly_chart(chart_columns[1], leads_fig)
    chart_columns = st.columns(2)
    _render_plotly_chart(chart_columns[0], cpi_fig)
    _render_plotly_chart(chart_columns[1], cpl_fig)


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


def _top_inbox_campaigns_by_cost_per_inbox(campaign_df):
    chart_df = (
        campaign_df[
            (campaign_df["primary_result_type"] == "Inbox")
            & (campaign_df["inbox_messages"] > 0)
            & (campaign_df["cost_per_inbox"].notna())
        ]
        .sort_values("cost_per_inbox")
        .head(10)
    )
    fig = px.bar(
        chart_df,
        x="cost_per_inbox",
        y="campaign",
        orientation="h",
        color="inbox_messages",
        title="Top 10 Inbox Campaigns by Cost per Inbox",
    )
    fig.update_xaxes(title="Cost per Inbox (฿)")
    fig.update_layout(yaxis={"categoryorder": "total descending"})
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
        hover_data=["primary_result_type", "results", "Cost per Result"],
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
        hover_data=["campaign", "primary_result_type", "results"],
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


def _preview_unavailable_label(row):
    reason = str(row.get("preview_reason", "") or "").strip()
    if reason and reason not in {"no_usable_media_returned", "image_hash_pending"}:
        return f"Preview not available: {reason}"
    return "Preview not available"


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
            else f'<div class="no-preview">{escape(_preview_unavailable_label(row))}</div>'
        )
        metrics_html = "".join(
            [
                _metric_cell("Spend", _format_currency(row["spend"])),
                _metric_cell("Results", _format_number(row["results"])),
                _metric_cell(str(row.get("primary_result_type", "Primary")), _format_number(row["results"])),
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
                    if row.get("primary_result_type") == "Lead":
                        st.write(f"Leads: {_format_number(row['leads'])}")
                    elif row.get("primary_result_type") == "Inbox":
                        st.write(f"Inbox Messages: {_format_number(row['inbox_messages'])}")
                    st.write(f"Cost per Result: {_format_currency(row['Cost per Result'])}")
                    if row.get("primary_result_type") == "Lead":
                        st.write(f"Cost per Lead: {_format_currency(row['Cost per Lead'])}")
                    elif row.get("primary_result_type") == "Inbox":
                        st.write(f"Cost per Inbox: {_format_currency(row['Cost per Inbox'])}")


def _charts(lead_daily_df, inbox_daily_df, campaign_df):
    st.markdown('<div class="section-title">Performance Trends</div>', unsafe_allow_html=True)
    _display_separation_note()
    lead_campaign_df = campaign_df[campaign_df["primary_result_type"] == "Lead"]
    inbox_campaign_df = campaign_df[campaign_df["primary_result_type"] == "Inbox"]
    rows = [
        [spend_vs_results_by_day(lead_daily_df), cost_per_result_trend(lead_daily_df)],
        [_top_campaigns_by_results(lead_campaign_df), _top_campaigns_by_cost_per_lead(lead_campaign_df)],
        [spend_vs_results_by_day(inbox_daily_df), cost_per_result_trend(inbox_daily_df)],
        [_top_campaigns_by_results(inbox_campaign_df), _top_inbox_campaigns_by_cost_per_inbox(inbox_campaign_df)],
        [frequency_vs_ctr(lead_campaign_df), frequency_vs_ctr(inbox_campaign_df)],
    ]
    for row in rows:
        columns = st.columns(2)
        for column, figure in zip(columns, row):
            _render_plotly_chart(column, figure)


def _creative_section(creative_df):
    st.markdown('<div class="section-title">Creative Performance</div>', unsafe_allow_html=True)
    _display_separation_note()
    _creative_preview_rows(creative_df)

    columns = [
        "ad",
        "campaign",
        "primary_result_type",
        "creative_id",
        "creative_name",
        "creative_media_source",
        "preview_reason",
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
    display_df = creative_df[columns].rename(columns={"primary_result_type": "Primary Result Type"})
    display_df = _blank_non_primary_result_metrics(
        display_df.rename(
            columns={
                "inbox_messages": "Inbox Messages",
                "leads": "Leads",
                "Cost per Inbox": "Cost per Inbox",
                "Cost per Lead": "Cost per Lead",
            }
        )
    )
    _render_dark_dataframe(display_df, use_container_width=True, hide_index=True)

    lead_creative_df = creative_df[creative_df["primary_result_type"] == "Lead"]
    inbox_creative_df = creative_df[creative_df["primary_result_type"] == "Inbox"]
    rows = [
        [top_creatives_by_leads(lead_creative_df), top_creatives_by_inbox_messages(inbox_creative_df)],
        [_creative_cost_efficiency(lead_creative_df), _creative_fatigue_risk(inbox_creative_df)],
    ]
    for row in rows:
        chart_columns = st.columns(2)
        for column, figure in zip(chart_columns, row):
            _render_plotly_chart(column, figure)
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


def _unmapped_campaigns_debug(ads_df):
    with st.expander("Unmapped Campaigns (Other)", expanded=False):
        other_df = ads_df[ads_df["project"] == "Other"]
        if other_df.empty:
            st.caption("No campaigns or ad sets are currently mapped to Other.")
            return

        debug_df = (
            other_df.groupby(["campaign", "adset"], as_index=False)
            .agg(
                spend=("spend", "sum"),
                leads=("leads", "sum"),
                inbox_messages=("inbox_messages", "sum"),
            )
            .sort_values("spend", ascending=False)
            .rename(
                columns={
                    "campaign": "campaign_name",
                    "adset": "adset_name",
                }
            )
        )
        _render_dark_dataframe(
            debug_df[["campaign_name", "adset_name", "spend", "leads", "inbox_messages"]],
            use_container_width=True,
            hide_index=True,
        )


def _debug_matching_diagnostics(ads_df, pipeline_project_df, pipeline_adset_df, adset_df):
    st.markdown("---")
    with st.container(key="debug_matching_diagnostics"):
        st.markdown(
            '<div class="section-title">Debug & Matching Diagnostics</div>',
            unsafe_allow_html=True,
        )
        _unmapped_campaigns_debug(ads_df)
        _pipeline_projects_debug(pipeline_project_df)
        _pipeline_adsets_debug(pipeline_adset_df, adset_df)


def _pipeline_joined_rows(adset_df):
    if adset_df.empty or "total_contacts" not in adset_df.columns:
        return 0
    contacts = pd.to_numeric(adset_df["total_contacts"], errors="coerce").fillna(0)
    return int((contacts > 0).sum())


def _matched_adsets_count(adset_df):
    if adset_df.empty:
        return 0
    match_details = adset_df.attrs.get("pipeline_adset_match_details", {})
    exact_df = match_details.get("exact", pd.DataFrame())
    token_df = match_details.get("token", match_details.get("fallback", pd.DataFrame()))
    matched_names = []
    for match_df in [exact_df, token_df]:
        if not match_df.empty and "adset" in match_df.columns:
            matched_names.extend(match_df["adset"].dropna().astype(str).tolist())
    if matched_names:
        return len(set(matched_names))
    return _pipeline_joined_rows(adset_df)


def _pipeline_join_warning_reason(has_pipeline_session, has_meta_report, pipeline_df, pipeline_filtered_df, pipeline_adset_df, adset_df):
    if not has_pipeline_session:
        return "no pipeline_df in session"
    if not has_meta_report:
        return "no Meta report loaded"
    if not pipeline_df.empty and pipeline_filtered_df.empty:
        return "no selected date overlap"
    match_details = adset_df.attrs.get("pipeline_adset_match_details", {}) if not adset_df.empty else {}
    exact_df = match_details.get("exact", pd.DataFrame())
    token_df = match_details.get("token", match_details.get("fallback", pd.DataFrame()))
    has_matches = (
        not exact_df.empty
        or not token_df.empty
        or _pipeline_joined_rows(adset_df) > 0
    )
    if not pipeline_adset_df.empty and not has_matches:
        return "no matching adset keys"
    return "no matching adset keys"


def _render_pipeline_sidebar_status(
    pipeline_df,
    pipeline_filtered_df,
    has_meta_report,
    adset_df=None,
    pipeline_adset_df=None,
):
    has_pipeline_session = STATE_PIPELINE_DF in st.session_state
    pipeline_metadata = st.session_state.get(STATE_PIPELINE_METADATA, {})
    pipeline_uploaded = bool(has_pipeline_session and not pipeline_df.empty)
    pipeline_source = pipeline_metadata.get("source") if pipeline_uploaded else "Not Loaded"
    st.sidebar.caption(f"Pipeline source: {pipeline_source}")
    if pipeline_metadata.get("file_name"):
        st.sidebar.caption(f"Pipeline file: {pipeline_metadata['file_name']}")
    st.sidebar.caption(f"Pipeline uploaded: {'yes' if pipeline_uploaded else 'no'}")
    st.sidebar.caption(f"Pipeline rows uploaded: {len(pipeline_df):,}")
    st.sidebar.caption(f"Pipeline rows in selected date range: {len(pipeline_filtered_df):,}")
    joined_rows = _pipeline_joined_rows(adset_df) if adset_df is not None else 0
    matched_adsets = _matched_adsets_count(adset_df) if adset_df is not None else 0
    pipeline_joined = has_meta_report and pipeline_uploaded and joined_rows > 0
    st.sidebar.caption(f"Pipeline joined: {'yes' if pipeline_joined else 'no'}")
    st.sidebar.caption(f"Matched adsets count: {matched_adsets:,}")
    if not has_pipeline_session or pipeline_joined:
        return
    reason = _pipeline_join_warning_reason(
        has_pipeline_session,
        has_meta_report,
        pipeline_df,
        pipeline_filtered_df,
        pipeline_adset_df if pipeline_adset_df is not None else pd.DataFrame(),
        adset_df if adset_df is not None else pd.DataFrame(),
    )
    st.sidebar.warning(f"Pipeline joined rows = 0: {reason}.")


def main():
    st.set_page_config(page_title="Real Estate Meta Ads Dashboard", layout="wide")
    st.session_state.setdefault(STATE_SIDEBAR_OPEN, True)
    st.session_state.setdefault("dark_analytics_theme", True)
    dark_theme = st.session_state.get("dark_analytics_theme", True)
    _styles(dark_theme)
    _sidebar_visibility_styles(st.session_state[STATE_SIDEBAR_OPEN])
    _render_sidebar_toggle()

    today = date.today()
    default_from = today - timedelta(days=6)
    st.session_state.setdefault(STATE_USE_CUSTOM_RANGE, True)
    st.session_state.setdefault(STATE_DATE_FROM, default_from)
    st.session_state.setdefault(STATE_DATE_TO, today)
    st.session_state.setdefault(STATE_PRESET, PRESETS[2])

    use_custom_range = st.session_state[STATE_USE_CUSTOM_RANGE]
    date_from = st.session_state[STATE_DATE_FROM]
    date_to = st.session_state[STATE_DATE_TO]
    preset = st.session_state[STATE_PRESET]
    pipeline_upload = st.session_state.get("sale_pipeline_leads_csv")
    generate = False
    hidden_slot = _HiddenSidebarSlot()
    cache_status_slot = hidden_slot
    last_updated_slot = hidden_slot
    csv_download_slot = hidden_slot
    cache_ttl_slot = hidden_slot

    if st.session_state[STATE_SIDEBAR_OPEN]:
        with st.sidebar:
            st.header("Report Controls")
            dark_theme = st.toggle("Dark analytics theme", key="dark_analytics_theme")
            use_custom_range = st.checkbox(
                "Use custom date range", key=STATE_USE_CUSTOM_RANGE
            )
            date_from = st.date_input("META_DATE_FROM", key=STATE_DATE_FROM)
            date_to = st.date_input("META_DATE_TO", key=STATE_DATE_TO)
            preset = st.selectbox("META_DATE_PRESET", PRESETS, key=STATE_PRESET)
            pipeline_upload = st.file_uploader(
                "Upload Sale Pipeline Leads CSV/XLS/XLSX",
                type=["csv", "xlsx", "xls"],
                key="sale_pipeline_leads_csv",
            )
            if st.button("Clear cached Meta data", use_container_width=True, key="clear_cached_meta_data"):
                _cached_meta_ads_data.clear()
                st.session_state.pop(STATE_ADS_DF, None)
                st.session_state.pop(STATE_DATE_RANGE_LABEL, None)
                st.session_state.pop(STATE_FETCH_REQUEST_KEY, None)
                st.session_state.pop(STATE_DATA_SOURCE_WARNING, None)
                st.session_state.pop(STATE_REPORT_UPDATED_AT, None)
                st.session_state[STATE_CACHE_STATUS] = "Cache cleared"
                st.success("Meta data cache cleared. Click Generate Report to fetch again.")
            if st.button("Clear cached pipeline data", use_container_width=True, key="clear_cached_pipeline_data"):
                st.session_state.pop(STATE_PIPELINE_DF, None)
                st.session_state.pop(STATE_PIPELINE_UPLOAD_SIGNATURE, None)
                st.session_state.pop(STATE_PIPELINE_UPLOAD_MESSAGE, None)
                st.session_state.pop(STATE_PIPELINE_METADATA, None)
                try:
                    PIPELINE_CACHE_PATH.unlink(missing_ok=True)
                except Exception as error:
                    st.warning(f"Pipeline cache could not be cleared: {error}")
                else:
                    st.success("Pipeline cache cleared.")
            generate = st.button(
                "Generate Report", type="primary", use_container_width=True, key="generate_report"
            )
            cache_status_slot = st.empty()
            last_updated_slot = st.empty()
            csv_download_slot = st.empty()
            cache_ttl_slot = st.empty()
            _render_sidebar_data_controls(
                cache_status_slot,
                last_updated_slot,
                csv_download_slot,
                cache_ttl_slot,
            )

    restored_file_cache = False
    if not generate and STATE_ADS_DF not in st.session_state:
        restored_file_cache = _restore_file_cache_to_session()
    _restore_pipeline_cache_to_session()

    pipeline_upload_present = pipeline_upload is not None
    pipeline_upload_signature = _pipeline_upload_signature(pipeline_upload)
    previous_pipeline_upload_signature = st.session_state.get(
        STATE_PIPELINE_UPLOAD_SIGNATURE,
        "",
    )
    if pipeline_upload_present:
        if (
            pipeline_upload_signature == previous_pipeline_upload_signature
            and STATE_PIPELINE_DF in st.session_state
        ):
            pipeline_df = st.session_state[STATE_PIPELINE_DF]
        else:
            pipeline_df = _load_pipeline_upload(pipeline_upload)
            if not pipeline_df.empty:
                st.session_state[STATE_PIPELINE_DF] = pipeline_df
                st.session_state[STATE_PIPELINE_UPLOAD_SIGNATURE] = pipeline_upload_signature
                st.session_state[STATE_PIPELINE_METADATA] = _pipeline_upload_metadata(
                    pipeline_upload,
                    pipeline_df,
                    pipeline_upload_signature,
                )
                _save_pipeline_cache(
                    pipeline_df,
                    st.session_state[STATE_PIPELINE_METADATA],
                )
                if STATE_ADS_DF in st.session_state:
                    st.session_state[STATE_PIPELINE_UPLOAD_MESSAGE] = (
                        "Pipeline data loaded and joined with current report."
                    )
                else:
                    st.session_state[STATE_PIPELINE_UPLOAD_MESSAGE] = (
                        "Pipeline loaded. Click Generate Report to join with Meta data."
                    )
    else:
        pipeline_df = st.session_state.get(
            STATE_PIPELINE_DF,
            pd.DataFrame(columns=PIPELINE_REQUIRED_COLUMNS),
        )
    pipeline_filtered_df = _filter_pipeline_by_date_range(
        pipeline_df, date_from, date_to
    )
    pipeline_upload_message = st.session_state.get(STATE_PIPELINE_UPLOAD_MESSAGE, "")
    if pipeline_upload_message:
        if pipeline_upload_message == "Pipeline data loaded and joined with current report.":
            st.sidebar.success(pipeline_upload_message)
        else:
            st.sidebar.info(pipeline_upload_message)

    initial_label = (
        f"{date_from.strftime('%B')} {date_from.day}, {date_from.year} - "
        f"{date_to.strftime('%B')} {date_to.day}, {date_to.year}"
        if use_custom_range
        else preset
    )
    if restored_file_cache:
        initial_label = st.session_state.get(STATE_DATE_RANGE_LABEL, initial_label)

    if not generate:
        if STATE_ADS_DF not in st.session_state:
            _header(initial_label, status="Awaiting report", updated_at="-")
            if pipeline_upload_present or not pipeline_df.empty:
                _render_pipeline_sidebar_status(
                    pipeline_df,
                    pipeline_filtered_df,
                    has_meta_report=False,
                )
                st.info("Pipeline loaded. Click Generate Report to join with Meta data.")
            else:
                st.info("Choose a date range or preset, then click Generate Report.")
            return

    if generate and use_custom_range and date_from > date_to:
        _header(initial_label, status="Invalid date range", updated_at="-")
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
                st.session_state[STATE_CACHE_STATUS] = "Session cache hit"
                st.session_state[STATE_REPORT_UPDATED_AT] = ads_df.attrs.get(
                    "report_updated_at",
                    st.session_state.get(STATE_REPORT_UPDATED_AT, ""),
                )
                if _should_save_file_cache(ads_df):
                    _save_file_cache(ads_df)
            else:
                with st.spinner("Fetching Meta Ads insights..."):
                    ads_df = _load_dashboard_data(
                        use_custom_range,
                        date_from,
                        date_to,
                        preset,
                        raise_rate_limit=STATE_ADS_DF in st.session_state,
                    )
                st.session_state[STATE_ADS_DF] = ads_df
                st.session_state[STATE_DATE_RANGE_LABEL] = ads_df.attrs.get(
                    "date_range_label", initial_label
                )
                st.session_state[STATE_FETCH_REQUEST_KEY] = fetch_request_key
                st.session_state[STATE_CACHE_STATUS] = ads_df.attrs.get(
                    "cache_status", "Meta cache active"
                )
                st.session_state[STATE_DATA_SOURCE_WARNING] = ads_df.attrs.get(
                    "data_source_warning", ""
                )
                st.session_state[STATE_REPORT_UPDATED_AT] = ads_df.attrs.get(
                    "report_updated_at", ""
                )
                if _should_save_file_cache(ads_df):
                    _save_file_cache(ads_df)
                if ads_df.attrs.get("data_source_warning"):
                    st.warning(ads_df.attrs["data_source_warning"])
        except Exception as error:
            if RATE_LIMIT_MESSAGE in str(error):
                if STATE_ADS_DF in st.session_state:
                    ads_df = st.session_state[STATE_ADS_DF]
                    if st.session_state.get(STATE_CACHE_STATUS) != "CACHED FILE DATA":
                        st.session_state[STATE_CACHE_STATUS] = (
                            "Serving cached data after rate limit"
                        )
                    st.warning(f"{RATE_LIMIT_MESSAGE} Showing cached data.")
                else:
                    st.error(RATE_LIMIT_MESSAGE)
                    return
            else:
                st.error(f"Data loading error: {error}")
                return
    else:
        ads_df = st.session_state[STATE_ADS_DF]
        ads_df.attrs["date_range_label"] = st.session_state.get(STATE_DATE_RANGE_LABEL, "")
        ads_df.attrs["report_updated_at"] = st.session_state.get(STATE_REPORT_UPDATED_AT, "")

    if ads_df.empty:
        _header(
            ads_df.attrs.get("date_range_label", initial_label),
            status=st.session_state.get(STATE_CACHE_STATUS, "No data"),
            updated_at=ads_df.attrs.get(
                "report_updated_at", st.session_state.get(STATE_REPORT_UPDATED_AT, "")
            ),
        )
        _render_sidebar_data_controls(
            cache_status_slot,
            last_updated_slot,
            csv_download_slot,
            cache_ttl_slot,
            ads_df=ads_df,
            report_updated_at=ads_df.attrs.get(
                "report_updated_at", st.session_state.get(STATE_REPORT_UPDATED_AT, "")
            ),
        )
        st.warning("Meta returned no rows for this range.")
        return

    filtered_df, top_n, sort_by = _top_level_filters(ads_df)
    report_updated_at = ads_df.attrs.get(
        "report_updated_at", st.session_state.get(STATE_REPORT_UPDATED_AT, "")
    )
    _render_sidebar_data_controls(
        cache_status_slot,
        last_updated_slot,
        csv_download_slot,
        cache_ttl_slot,
        ads_df=ads_df,
        filtered_df=filtered_df,
        report_updated_at=report_updated_at,
    )
    if filtered_df.empty:
        _header(
            ads_df.attrs.get("date_range_label", initial_label),
            status=st.session_state.get(STATE_CACHE_STATUS, "Filtered"),
            updated_at=report_updated_at,
        )
        st.warning("No rows match current filters.")
        return

    project_df = _project_summary(filtered_df, sort_by, top_n)
    pipeline_adset_df = _pipeline_adset_summary(pipeline_filtered_df)
    pipeline_project_df = pd.DataFrame()
    lead_filtered_df = filtered_df[filtered_df["primary_result_type"] == "Lead"]
    inbox_filtered_df = filtered_df[filtered_df["primary_result_type"] == "Inbox"]
    lead_daily_df = daily_summary(lead_filtered_df)
    inbox_daily_df = daily_summary(inbox_filtered_df)
    campaign_df = _dashboard_campaign_summary(filtered_df).sort_values("spend", ascending=False)
    adset_df = _dashboard_adset_summary(filtered_df, sort_by)
    adset_df = _join_pipeline_adset_data(adset_df, pipeline_adset_df)
    adset_df = _clear_non_primary_adset_contacts(adset_df)
    campaign_df = _join_adset_contacts_to_campaign(campaign_df, adset_df)
    project_df = _join_campaign_contacts_to_project(project_df, campaign_df)
    _render_pipeline_sidebar_status(
        pipeline_df,
        pipeline_filtered_df,
        has_meta_report=True,
        adset_df=adset_df,
        pipeline_adset_df=pipeline_adset_df,
    )
    creative_df = creative_summary(filtered_df)
    all_daily_df = daily_summary(filtered_df)

    _header(
        ads_df.attrs.get("date_range_label", initial_label),
        status=st.session_state.get(STATE_CACHE_STATUS, "Ready"),
        updated_at=report_updated_at,
    )
    _kpi_cards(filtered_df, campaign_df)
    _dashboard_top_chart_row(all_daily_df, project_df)
    _project_performance(project_df)
    _campaign_table(campaign_df)
    _adset_table(adset_df)
    _decision_summary(campaign_df)
    _executive_action_plan(filtered_df, campaign_df, adset_df, creative_df)
    _thai_performance_agency_summary(filtered_df, campaign_df, adset_df, creative_df)
    _aggregation_check(filtered_df)
    _management_notes(campaign_df)
    _charts(lead_daily_df, inbox_daily_df, campaign_df)
    _creative_section(creative_df)
    _debug_matching_diagnostics(
        ads_df,
        pipeline_project_df,
        pipeline_adset_df,
        adset_df,
    )


if __name__ == "__main__":
    main()
