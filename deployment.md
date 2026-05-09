# Deployment Workflow

## Local Development

1. Install dependencies in your local environment.
2. Create a local `.env` file with Meta Ads credentials. Do not commit `.env`.
3. Run the dashboard locally:

```powershell
streamlit run dashboard.py
```

4. Test changes locally before pushing.

## GitHub Push Flow

Use the helper script:

```bat
update_dashboard.bat
```

The script runs:

```bat
git add .
git commit -m "<your message>"
git push
```

Use a clear commit message, for example:

```text
Fix dashboard cache handling
```

## Streamlit Cloud Auto Redeploy

Streamlit Cloud redeploys automatically when the connected GitHub branch receives a push.

Required Streamlit Cloud settings:

- Main file path: `dashboard.py`
- Python dependencies: managed by your project dependency file if present.
- Secrets: configure Meta Ads credentials in Streamlit Cloud secrets or environment settings, not in Git.

Never commit access tokens, ad account IDs you consider sensitive, app secrets, or `.env` files.

## Rollback Process

1. Find the last known good commit in GitHub.
2. Revert the bad commit locally:

```powershell
git revert <commit_sha>
git push
```

3. Streamlit Cloud will redeploy after the rollback commit is pushed.

For an urgent rollback, use GitHub's revert button on the bad commit or redeploy a known-good commit from Streamlit Cloud if available.

## Troubleshooting

- App does not redeploy: confirm the GitHub branch connected to Streamlit Cloud received the push.
- Missing data: confirm Meta credentials are configured in the deployment environment.
- Local `.env` not found: create `.env` in the project root beside `dashboard.py`.
- Port already in use locally: run Streamlit on another port, for example:

```powershell
streamlit run dashboard.py --server.port 8502
```

- Import errors: install missing dependencies and rerun:

```powershell
python -m py_compile dashboard.py main.py meta_client.py metrics.py charts.py report_writer.py
```

- Live Meta API unavailable: the dashboard can fall back to `data/sample_ads.csv` when that file exists.
