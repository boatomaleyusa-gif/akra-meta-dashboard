# Agent Operating Guide

This project is a Streamlit dashboard for Meta Ads reporting and analysis.
The current Python modules are the source of truth:

- `dashboard.py`: Streamlit UI and user workflow.
- `meta_client.py`: Meta Ads API access and account data retrieval.
- `metrics.py`: metric calculations and data normalization.
- `charts.py`: visualization helpers.
- `report_writer.py`: report export and narrative generation.
- `main.py`: command-line or app entrypoint.

## Operating Rules

- Do not change existing Python files unless the user explicitly asks.
- Keep dashboard behavior transparent: every metric should be traceable to Meta Ads source fields or documented calculations.
- Treat Meta Ads credentials, tokens, account IDs, and exported reports as sensitive data.
- Prefer small, reviewable changes with clear ownership by agent role.
- Keep MCP integration work isolated until the MCP architecture is implemented.

## Agent Roles

- Dashboard Agent: owns Streamlit UX, dashboard flow, filters, layout, and user-facing state.
- MCP Agent: owns future tool boundaries, MCP server contracts, schemas, and integration plans.
- Performance Analyst: owns campaign interpretation, metric definitions, reporting logic, and insight quality.
- Safety Agent: owns privacy, credential handling, platform-policy checks, and change review.

## Collaboration Protocol

1. Identify the owning agent before proposing a change.
2. Check whether the change touches UI, API access, metrics, reporting, or safety boundaries.
3. Document assumptions when Meta Ads fields, attribution windows, or date ranges are ambiguous.
4. Escalate to the Safety Agent before adding storage, exports, external calls, or account-level automation.
5. Keep prompts and agent instructions concise and task-specific.

## Project Boundaries

Allowed documentation locations:

- `docs/`
- `agents/`
- `prompts/`
- `AGENTS.md`

Future implementation should preserve clear separation between dashboard presentation, Meta API access, metric computation, chart rendering, and report writing.
