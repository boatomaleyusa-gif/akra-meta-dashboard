from pathlib import Path
import sys

import pandas as pd

from charts import (
    campaign_comparison,
    cost_per_lead_by_creative,
    cost_per_result_trend,
    creative_ctr_vs_frequency,
    frequency_vs_ctr,
    leads_and_inbox_trend,
    spend_vs_results_by_day,
    top_creatives_by_inbox_messages,
    top_creatives_by_leads,
)
from meta_client import load_meta_ads_data
from metrics import add_metrics, campaign_summary, creative_summary, daily_summary
from report_writer import write_html_report


PROJECT_ROOT = Path(__file__).resolve().parent
DATA_PATH = PROJECT_ROOT / "data" / "sample_ads.csv"
REPORT_PATH = PROJECT_ROOT / "reports" / "meta_ads_report.html"


def load_ads_data(csv_path):
    df = pd.read_csv(csv_path, parse_dates=["date"])
    df = add_metrics(df)
    df.attrs["date_range_label"] = "Report Date Range: Sample CSV"
    return df


def load_report_data():
    live_error = None
    try:
        meta_df = load_meta_ads_data(PROJECT_ROOT)
    except Exception as error:
        live_error = error
        meta_df = None
    if meta_df is not None:
        date_range_label = meta_df.attrs.get("date_range_label", "")
        meta_df["date"] = pd.to_datetime(meta_df["date"])
        meta_df = add_metrics(meta_df)
        meta_df.attrs["date_range_label"] = date_range_label
        return meta_df
    if not DATA_PATH.exists():
        if live_error:
            raise RuntimeError(
                f"Live Meta Ads data unavailable and data/sample_ads.csv is missing: {live_error}"
            ) from live_error
        raise RuntimeError(
            "Meta credentials were not found and data/sample_ads.csv is missing."
        )
    df = load_ads_data(DATA_PATH)
    if live_error:
        print(f"WARNING: Live Meta Ads data unavailable; using sample CSV fallback. {live_error}", flush=True)
    return df


def main():
    try:
        ads_df = load_report_data()
    except Exception as error:
        print(f"ERROR: {error}", flush=True)
        sys.exit(1)

    daily_df = daily_summary(ads_df)
    campaign_df = campaign_summary(ads_df)
    creative_df = creative_summary(ads_df)
    date_range_label = ads_df.attrs.get("date_range_label", "")

    figures = [
        spend_vs_results_by_day(daily_df),
        cost_per_result_trend(daily_df),
        leads_and_inbox_trend(daily_df),
        campaign_comparison(campaign_df),
        frequency_vs_ctr(campaign_df),
    ]

    creative_figures = [
        top_creatives_by_leads(creative_df),
        top_creatives_by_inbox_messages(creative_df),
        cost_per_lead_by_creative(creative_df),
        creative_ctr_vs_frequency(creative_df),
    ]

    write_html_report(
        REPORT_PATH,
        daily_df,
        campaign_df,
        creative_df,
        figures,
        creative_figures,
        date_range_label,
    )
    print(f"Report created: {REPORT_PATH}", flush=True)


if __name__ == "__main__":
    main()
