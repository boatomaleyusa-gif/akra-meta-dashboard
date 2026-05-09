from plotly.subplots import make_subplots
import plotly.express as px
import plotly.graph_objects as go


def spend_vs_results_by_day(daily_df):
    fig = make_subplots(specs=[[{"secondary_y": True}]])
    fig.add_trace(
        go.Bar(x=daily_df["date"], y=daily_df["spend"], name="Spend"),
        secondary_y=False,
    )
    fig.add_trace(
        go.Scatter(
            x=daily_df["date"],
            y=daily_df["results"],
            name="Results",
            mode="lines+markers",
        ),
        secondary_y=True,
    )
    fig.update_layout(title="Spend vs Results by Day", hovermode="x unified")
    fig.update_yaxes(title_text="Spend (฿)", secondary_y=False)
    fig.update_yaxes(title_text="Results", secondary_y=True)
    return fig


def cost_per_result_trend(daily_df):
    fig = px.line(
        daily_df,
        x="date",
        y="Cost per Result",
        markers=True,
        title="Cost per Result Trend",
    )
    fig.update_yaxes(title="Cost per Result (฿)")
    return fig


def leads_and_inbox_trend(daily_df):
    fig = px.line(
        daily_df,
        x="date",
        y=["leads", "inbox_messages"],
        markers=True,
        title="Leads and Inbox Messages Trend",
    )
    fig.update_yaxes(title="Count")
    return fig


def campaign_comparison(campaign_df):
    fig = px.bar(
        campaign_df,
        x="campaign",
        y=["results", "leads", "inbox_messages"],
        barmode="group",
        title="Campaign Comparison: Results by Type",
    )
    fig.update_xaxes(title="Campaign")
    fig.update_yaxes(title="Count")
    return fig


def frequency_vs_ctr(campaign_df):
    fig = px.scatter(
        campaign_df,
        x="Frequency",
        y="CTR",
        size="spend",
        color="campaign",
        hover_data=["results", "result_type", "leads", "inbox_messages", "Cost per Result"],
        title="Frequency vs CTR by Campaign",
    )
    fig.update_yaxes(title="CTR (%)")
    return fig


def top_creatives_by_leads(creative_df):
    top_df = creative_df.sort_values("leads", ascending=False).head(5)
    fig = px.bar(
        top_df,
        x="ad",
        y="leads",
        color="campaign",
        title="Top 5 Creatives by Leads",
    )
    fig.update_xaxes(title="Creative")
    fig.update_yaxes(title="Leads")
    return fig


def top_creatives_by_inbox_messages(creative_df):
    top_df = creative_df.sort_values("inbox_messages", ascending=False).head(5)
    fig = px.bar(
        top_df,
        x="ad",
        y="inbox_messages",
        color="campaign",
        title="Top 5 Creatives by Inbox Messages",
    )
    fig.update_xaxes(title="Creative")
    fig.update_yaxes(title="Inbox Messages")
    return fig


def cost_per_lead_by_creative(creative_df):
    chart_df = creative_df[creative_df["leads"] > 0].sort_values("Cost per Lead")
    fig = px.bar(
        chart_df,
        x="ad",
        y="Cost per Lead",
        color="campaign",
        title="Cost per Lead by Creative",
    )
    fig.update_xaxes(title="Creative")
    fig.update_yaxes(title="Cost per Lead (฿)")
    return fig


def creative_ctr_vs_frequency(creative_df):
    fig = px.scatter(
        creative_df,
        x="Frequency",
        y="CTR",
        size="spend",
        color="campaign",
        hover_name="ad",
        hover_data=["leads", "inbox_messages", "Cost per Lead", "Cost per Inbox"],
        title="CTR vs Frequency by Creative",
    )
    fig.update_yaxes(title="CTR (%)")
    return fig
