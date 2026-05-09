from pathlib import Path

import plotly.io as pio

from metrics import safe_divide_value


def _format_currency(value):
    return f"${value:,.2f}"


def _format_number(value):
    return f"{value:,.0f}"


def _format_percent(value):
    return f"{value:.2f}%"


def _safe_divide(numerator, denominator):
    return safe_divide_value(numerator, denominator)


def _format_list(values):
    if not values:
        return "None flagged"
    return ", ".join(values)


def _creative_insights(creative_df):
    if creative_df.empty:
        return {
            "Best creative by leads": "No creative data",
            "High inbox but low lead creatives": "None flagged",
            "High cost creatives": "None flagged",
            "Possible fatigue creatives": "None flagged",
        }

    best_lead_row = creative_df.sort_values("leads", ascending=False).iloc[0]
    inbox_threshold = creative_df["inbox_messages"].median()
    lead_threshold = creative_df["leads"].median()
    cost_threshold = creative_df.loc[creative_df["leads"] > 0, "Cost per Lead"].median()
    frequency_threshold = creative_df["Frequency"].median()
    ctr_threshold = creative_df["CTR"].median()

    high_inbox_low_leads = creative_df[
        (creative_df["inbox_messages"] > inbox_threshold)
        & (creative_df["leads"] < lead_threshold)
    ]["ad"].tolist()
    high_cost = creative_df[
        (creative_df["leads"] > 0) & (creative_df["Cost per Lead"] > cost_threshold)
    ]["ad"].tolist()
    possible_fatigue = creative_df[
        (creative_df["Frequency"] > frequency_threshold) & (creative_df["CTR"] < ctr_threshold)
    ]["ad"].tolist()

    return {
        "Best creative by leads": (
            f"{best_lead_row['ad']} ({_format_number(best_lead_row['leads'])} leads)"
        ),
        "High inbox but low lead creatives": _format_list(high_inbox_low_leads),
        "High cost creatives": _format_list(high_cost),
        "Possible fatigue creatives": _format_list(possible_fatigue),
    }


def write_html_report(
    output_path,
    daily_df,
    campaign_df,
    creative_df,
    figures,
    creative_figures,
    date_range_label="",
):
    """Write a simple HTML report with summary numbers, tables, and charts."""
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    total_spend = daily_df["spend"].sum()
    total_results = daily_df["results"].sum()
    total_inbox_messages = daily_df["inbox_messages"].sum()
    total_leads = daily_df["leads"].sum()

    totals = {
        "Spend": _format_currency(total_spend),
        "Results": _format_number(total_results),
        "Inbox Messages": _format_number(total_inbox_messages),
        "Leads": _format_number(total_leads),
        "Cost per Result": _format_currency(_safe_divide(total_spend, total_results)),
        "Cost per Inbox": _format_currency(_safe_divide(total_spend, total_inbox_messages)),
        "Cost per Lead": _format_currency(_safe_divide(total_spend, total_leads)),
    }

    all_figures = figures + creative_figures
    chart_html = []
    for index, fig in enumerate(all_figures):
        chart_html.append(
            pio.to_html(
                fig,
                full_html=False,
                include_plotlyjs="cdn" if index == 0 else False,
            )
        )

    standard_chart_html = chart_html[: len(figures)]
    creative_chart_html = chart_html[len(figures) :]

    campaign_table = campaign_df[
        [
            "campaign",
            "spend",
            "results",
            "result_type",
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
            "campaign": "campaign",
            "spend": "spend",
            "results": "results",
            "result_type": "result_type",
            "inbox_messages": "inbox_messages",
            "leads": "leads",
            "cost_per_result": "cost_per_result",
            "cost_per_inbox": "cost_per_inbox",
            "cost_per_lead": "cost_per_lead",
        }
    )
    campaign_table = campaign_table.copy()
    for column in ["spend", "cost_per_result", "cost_per_inbox", "cost_per_lead"]:
        campaign_table[column] = campaign_table[column].apply(_format_currency)
    for column in ["results", "inbox_messages", "leads"]:
        campaign_table[column] = campaign_table[column].apply(_format_number)
    campaign_table["CTR"] = campaign_table["CTR"].apply(_format_percent)
    campaign_table["CPM"] = campaign_table["CPM"].apply(_format_currency)
    campaign_table["Frequency"] = campaign_table["Frequency"].map("{:.2f}".format)

    creative_table = creative_df[
        [
            "ad",
            "campaign",
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
    ].rename(
        columns={
            "ad": "Ad Name",
            "campaign": "Campaign",
            "spend": "Spend",
            "results": "Results",
            "inbox_messages": "Inbox Messages",
            "leads": "Leads",
        }
    )

    currency_columns = ["Spend", "CPC", "Cost per Result", "Cost per Inbox", "Cost per Lead"]
    number_columns = ["Results", "Inbox Messages", "Leads"]
    creative_table = creative_table.copy()
    for column in currency_columns:
        creative_table[column] = creative_table[column].apply(_format_currency)
    for column in number_columns:
        creative_table[column] = creative_table[column].apply(_format_number)
    creative_table["CTR"] = creative_table["CTR"].apply(_format_percent)
    creative_table["Frequency"] = creative_table["Frequency"].map("{:.2f}".format)

    insights = _creative_insights(creative_df)
    insight_items = "\n".join(
        f"""
        <div class="insight">
            <div class="label">{label}</div>
            <div class="insight-value">{value}</div>
        </div>
        """
        for label, value in insights.items()
    )

    summary_cards = "\n".join(
        f"""
        <div class="card">
            <div class="label">{label}</div>
            <div class="value">{value}</div>
        </div>
        """
        for label, value in totals.items()
    )

    html = f"""
<!doctype html>
<html lang="en">
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>Meta Ads Sample Report</title>
    <style>
        body {{
            margin: 0;
            font-family: Arial, sans-serif;
            background: #f5f7fb;
            color: #1f2937;
        }}
        header {{
            background: #0f172a;
            color: white;
            padding: 28px 36px;
        }}
        main {{
            max-width: 1180px;
            margin: 0 auto;
            padding: 28px;
        }}
        h1, h2 {{
            margin: 0 0 12px;
        }}
        .subtle {{
            color: #cbd5e1;
            margin: 0;
        }}
        .date-range {{
            color: #e2e8f0;
            margin: 8px 0 0;
            font-weight: 700;
        }}
        .cards {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
            gap: 16px;
            margin-bottom: 28px;
        }}
        .card, .section {{
            background: white;
            border: 1px solid #e5e7eb;
            border-radius: 8px;
            box-shadow: 0 1px 3px rgba(15, 23, 42, 0.08);
        }}
        .card {{
            padding: 18px;
        }}
        .label {{
            color: #64748b;
            font-size: 14px;
        }}
        .value {{
            font-size: 26px;
            font-weight: 700;
            margin-top: 6px;
        }}
        .insights {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(240px, 1fr));
            gap: 14px;
        }}
        .insight {{
            border: 1px solid #e5e7eb;
            border-radius: 8px;
            padding: 14px;
            background: #f8fafc;
        }}
        .insight-value {{
            font-weight: 700;
            margin-top: 6px;
            line-height: 1.4;
        }}
        .section {{
            padding: 20px;
            margin-bottom: 24px;
            overflow-x: auto;
        }}
        table {{
            border-collapse: collapse;
            width: 100%;
            font-size: 14px;
        }}
        th, td {{
            border-bottom: 1px solid #e5e7eb;
            padding: 10px;
            text-align: left;
        }}
        th {{
            background: #f8fafc;
        }}
    </style>
</head>
<body>
    <header>
        <h1>Meta Ads Sample Report</h1>
        <p class="subtle">Real estate lead generation performance from Meta Ads insights.</p>
        <p class="date-range">{date_range_label}</p>
    </header>
    <main>
        <section class="cards">
            {summary_cards}
        </section>
        <section class="section">
            <h2>Campaign Summary</h2>
            {campaign_table.to_html(index=False)}
        </section>
        {''.join(f'<section class="section">{chart}</section>' for chart in standard_chart_html)}
        <section class="section">
            <h2>Creative Performance</h2>
            {creative_table.to_html(index=False, escape=False)}
        </section>
        {''.join(f'<section class="section">{chart}</section>' for chart in creative_chart_html)}
        <section class="section">
            <h2>Creative Insights</h2>
            <div class="insights">
                {insight_items}
            </div>
        </section>
    </main>
</body>
</html>
"""
    output_path.write_text(html, encoding="utf-8")
