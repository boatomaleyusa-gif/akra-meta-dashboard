# Agent Architecture

## Purpose

The agent architecture separates product UI work, Meta Ads integration, performance analysis, and safety review so changes remain auditable as MCP tooling is added.

## Current System

```text
User
  -> Streamlit dashboard.py
  -> meta_client.py
  -> metrics.py
  -> charts.py
  -> report_writer.py
```

## Planned MCP System

```text
User
  -> Dashboard Agent
  -> MCP Agent
  -> Meta Ads MCP tools
  -> Performance Analyst
  -> Safety Agent review gates
```

## Agent Responsibilities

### Dashboard Agent

- Defines Streamlit layout, controls, filters, session state, and user flow.
- Converts analysis outputs into clear dashboard sections.
- Avoids embedding API or metric business logic directly in UI code.

### MCP Agent

- Defines MCP tool contracts for Meta Ads reads, diagnostics, and future actions.
- Maintains schemas for accounts, campaigns, ad sets, ads, insights, and errors.
- Keeps tool responses structured and safe for downstream analysis.

### Performance Analyst

- Interprets spend, impressions, clicks, conversions, CPA, ROAS, CTR, CPC, CPM, and frequency.
- Documents metric assumptions and attribution windows.
- Produces concise recommendations with evidence and caveats.

### Safety Agent

- Reviews credential handling, data retention, export behavior, and account safety.
- Blocks unsupported write actions or automation without explicit user confirmation.
- Ensures recommendations do not imply policy-violating targeting or claims.

## Review Gates

- UI-only change: Dashboard Agent review.
- Metric or report change: Performance Analyst review.
- Meta API or MCP contract change: MCP Agent review.
- Credentials, exports, automation, or destructive actions: Safety Agent review.

## Meta MCP Safety Boundary

The current dashboard is read-only. It fetches Meta insights, creative metadata, and creative images for reporting.

Future MCP write actions are blocked unless an explicit approval gate is added:

- `pause_campaign`
- `update_budget`
- `create_campaign`
- `create_adset`
- `create_ad`

Each write action must present exact before/after details and receive explicit user confirmation before any Meta API write call.

## Design Principles

- Keep data fetching, calculation, visualization, and narration separate.
- Prefer explicit schemas over loosely shaped dictionaries.
- Make every recommendation explainable from available metrics.
- Require user confirmation before publishing, pausing, budget changes, or account mutations.
