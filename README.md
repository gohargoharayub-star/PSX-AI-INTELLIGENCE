# PSX AI INTELLIGENCE

A public, independently built Pakistan Stock Exchange research dashboard. This project is an original implementation; it does not copy proprietary source code from other websites.

## Status

Initial project setup. Market values shown in the demo are illustrative only and are not live PSX quotes or investment recommendations.

## Run locally

Open `index.html` in a browser. No build step or paid service is required.

## Publish with GitHub Pages

In the repository, open **Settings → Pages**. Under **Build and deployment**, choose **Deploy from a branch**, select **main** and **/(root)**, then Save. GitHub will provide the public Pages URL after deployment.

## Data and risk

This first version uses clearly labelled sample data. Connect only data sources you are permitted to use; confirm licensing and redistribution rights before publishing live prices. Technical signals are educational tools, not guaranteed outcomes.


## Automatic daily PSX signals

An independent PSX 20/80 V4 signal engine and weekday GitHub Actions workflow are included.

- Workflow: `.github/workflows/daily-signals.yml` (16:45 Pakistan time, Monday–Friday)
- Engine: `scripts/generate_signals.py`
- Published dashboard feed: `data/signals.json`
- Setup guide: `docs/DAILY_SIGNALS_SETUP.md`

**Activation required:** configure a licensed/authorized OHLCV CSV provider using the GitHub Actions secrets documented in the setup guide. Until then, the dashboard deliberately shows DATA PENDING and produces no stock calls. Do not set the license confirmation secret to true unless the provider permits automated use and public display.
