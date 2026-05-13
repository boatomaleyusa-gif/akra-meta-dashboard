from plotly.subplots import make_subplots
import plotly.express as px
import plotly.graph_objects as go


def _dark_chart(fig):
    fig.update_layout(
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font={"color": "#f8fafc", "family": "Inter, Arial, sans-serif"},
        title={"font": {"color": "#f8fafc", "size": 18}},
        legend={
            "bgcolor": "rgba(17,24,39,0.72)",
            "bordercolor": "#334155",
            "borderwidth": 1,
            "font": {"color": "#cbd5e1"},
        },
        hoverlabel={
            "bgcolor": "#111827",
            "bordercolor": "#334155",
            "font": {"color": "#f8fafc"},
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
    return _dark_chart(fig)


def cost_per_result_trend(daily_df):
    fig = px.line(
        daily_df,
        x="date",
        y="Cost per Result",
        markers=True,
        title="Cost per Result Trend",
    )
    fig.update_yaxes(title="Cost per Result (฿)")
    return _dark_chart(fig)


def leads_and_inbox_trend(daily_df):
    fig = px.line(
        daily_df,
        x="date",
        y=["leads", "inbox_messages"],
        markers=True,
        title="Leads and Inbox Messages Trend",
    )
    fig.update_yaxes(title="Count")
    return _dark_chart(fig)


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
    return _dark_chart(fig)


def frequency_vs_ctr(campaign_df):
    fig = px.scatter(
        campaign_df,
        x="Frequency",
        y="CTR",
        size="spend",
        color="campaign",
        hover_data=["results", "primary_result_type", "Cost per Result"],
        title="Frequency vs CTR by Campaign",
    )
    fig.update_yaxes(title="CTR (%)")
    return _dark_chart(fig)


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
    return _dark_chart(fig)


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
    return _dark_chart(fig)


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
    return _dark_chart(fig)


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
    return _dark_chart(fig)
