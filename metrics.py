import pandas as pd


def safe_divide(numerator, denominator):
    """Divide two pandas Series and return 0 when the denominator is 0."""
    safe_denominator = denominator.where(denominator != 0)
    return (numerator / safe_denominator).fillna(0)


def safe_divide_value(numerator, denominator):
    """Divide scalar values and return 0 when the denominator is empty or zero."""
    if pd.isna(numerator) or pd.isna(denominator) or denominator == 0:
        return 0
    return numerator / denominator


def add_metric_columns(df):
    """Add standard Meta Ads delivery and cost metrics using one shared formula set."""
    df["CTR"] = safe_divide(df["clicks"], df["impressions"]) * 100
    df["CPC"] = safe_divide(df["spend"], df["clicks"])
    df["CPM"] = safe_divide(df["spend"], df["impressions"]) * 1000
    df["Frequency"] = safe_divide(df["impressions"], df["reach"])
    df["Cost per Result"] = safe_divide(df["spend"], df["results"])
    df["Cost per Inbox"] = safe_divide(df["spend"], df["inbox_messages"])
    df["Cost per Lead"] = safe_divide(df["spend"], df["leads"])
    df["cost_per_result"] = df["Cost per Result"]
    df["cost_per_inbox"] = df["Cost per Inbox"]
    df["cost_per_lead"] = df["Cost per Lead"]
    return df


def apply_primary_result_metrics(df):
    """Recalculate result metrics from explicit primary result type.

    Inbox rows use inbox messages as results and do not show cost per lead.
    Lead rows use leads as results and do not show cost per inbox.
    Mixed rows use inbox messages plus leads and keep both channel costs.
    """
    df = df.copy()
    df["results"] = df.apply(_primary_results, axis=1)
    df["cost_per_result"] = df.apply(
        lambda row: safe_divide_value(row["spend"], row["results"]), axis=1
    )
    df["cost_per_inbox"] = df.apply(_primary_cost_per_inbox, axis=1)
    df["cost_per_lead"] = df.apply(_primary_cost_per_lead, axis=1)
    df["Cost per Result"] = df["cost_per_result"]
    df["Cost per Inbox"] = df["cost_per_inbox"]
    df["Cost per Lead"] = df["cost_per_lead"]
    return df


def add_metrics(df):
    """Add common Meta Ads reporting metrics to a DataFrame."""
    df = df.copy()

    for column in ["inbox_messages", "leads"]:
        if column not in df.columns:
            df[column] = 0
    for column in [
        "ad_id",
        "creative_id",
        "creative_name",
        "thumbnail_url",
        "image_url",
        "object_story_image_hash",
        "creative_preview_url",
        "preview_reason",
        "creative_media_source",
    ]:
        if column not in df.columns:
            df[column] = ""

    if "results" not in df.columns:
        df["results"] = df["leads"] + df["inbox_messages"]
    if "result_type" not in df.columns:
        df["result_type"] = df.apply(_result_type, axis=1)

    return add_metric_columns(df)


def _result_type(row):
    if row["leads"] > 0 and row["inbox_messages"] > 0:
        return "mixed"
    if row["leads"] > 0:
        return "leads"
    if row["inbox_messages"] > 0:
        return "inbox_messages"
    return "none"


def _summary_result_type(row):
    if row["leads"] > 0 and row["inbox_messages"] > 0:
        return "mixed"
    if row["leads"] > 0:
        return "leads"
    if row["inbox_messages"] > 0:
        return "inbox_messages"
    return "none"


def _primary_results(row):
    if row["primary_result_type"] == "Inbox":
        return row["inbox_messages"]
    if row["primary_result_type"] == "Lead":
        return row["leads"]
    return row["inbox_messages"] + row["leads"]


def _primary_cost_per_inbox(row):
    if row["primary_result_type"] == "Lead":
        return pd.NA
    return safe_divide_value(row["spend"], row["inbox_messages"])


def _primary_cost_per_lead(row):
    if row["primary_result_type"] == "Inbox":
        return pd.NA
    return safe_divide_value(row["spend"], row["leads"])


def daily_summary(df):
    """Group ads data by day and calculate metrics for each day."""
    grouped = (
        df.groupby("date", as_index=False)
        .agg(
            spend=("spend", "sum"),
            impressions=("impressions", "sum"),
            reach=("reach", "sum"),
            clicks=("clicks", "sum"),
            inbox_messages=("inbox_messages", "sum"),
            leads=("leads", "sum"),
            results=("results", "sum"),
        )
        .sort_values("date")
    )
    grouped["result_type"] = grouped.apply(_summary_result_type, axis=1)
    return add_metrics(grouped)


def campaign_summary(df):
    """Group ads data by campaign and calculate metrics for each campaign."""
    grouped = (
        df.groupby("campaign", as_index=False)
        .agg(
            spend=("spend", "sum"),
            impressions=("impressions", "sum"),
            reach=("reach", "sum"),
            clicks=("clicks", "sum"),
            inbox_messages=("inbox_messages", "sum"),
            leads=("leads", "sum"),
            results=("results", "sum"),
            ad_id=("ad_id", "first"),
            creative_id=("creative_id", "first"),
            creative_name=("creative_name", "first"),
            thumbnail_url=("thumbnail_url", "first"),
            image_url=("image_url", "first"),
            object_story_image_hash=("object_story_image_hash", "first"),
            creative_preview_url=("creative_preview_url", "first"),
            preview_reason=("preview_reason", "first"),
            creative_media_source=("creative_media_source", "first"),
        )
        .sort_values("spend", ascending=False)
    )
    grouped["result_type"] = grouped.apply(_summary_result_type, axis=1)
    return add_metrics(grouped)


def creative_summary(df):
    """Group ads data by creative and campaign, then calculate creative metrics."""
    group_columns = ["ad", "campaign"]
    if "primary_result_type" in df.columns:
        group_columns.append("primary_result_type")
    grouped = (
        df.groupby(group_columns, as_index=False)
        .agg(
            spend=("spend", "sum"),
            impressions=("impressions", "sum"),
            reach=("reach", "sum"),
            clicks=("clicks", "sum"),
            inbox_messages=("inbox_messages", "sum"),
            leads=("leads", "sum"),
            results=("results", "sum"),
            ad_id=("ad_id", "first"),
            creative_id=("creative_id", "first"),
            creative_name=("creative_name", "first"),
            thumbnail_url=("thumbnail_url", "first"),
            image_url=("image_url", "first"),
            object_story_image_hash=("object_story_image_hash", "first"),
            creative_preview_url=("creative_preview_url", "first"),
            preview_reason=("preview_reason", "first"),
            creative_media_source=("creative_media_source", "first"),
        )
        .sort_values("leads", ascending=False)
    )
    grouped["result_type"] = grouped.apply(_summary_result_type, axis=1)
    return add_metrics(grouped)
