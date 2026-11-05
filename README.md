
# FIN 331 Final Project — Team Free Agents

## Project Title

**Do Goldman Sachs Analyst Recommendations Move Stock Prices More Than Morgan Stanley or JPMorgan Recommendations?**

## Research Question

Do analyst upgrades and downgrades issued by Goldman Sachs generate significantly larger stock price reactions than recommendations issued by Morgan Stanley or JPMorgan?

Our project investigates whether the brokerage firm issuing an analyst recommendation influences how financial markets react to rating changes.

Inspired by Womack (1996), we aim to evaluate whether certain investment banks provide analyst recommendations that are associated with greater market reactions.

## Project Motivation

Institutional investors rely on equity research when making investment decisions. However, analyst recommendations from different brokerage firms may not have the same influence on stock prices.

Our goal is to determine whether recommendations from Goldman Sachs, Morgan Stanley, and JPMorgan are associated with different market reactions.

This research could help buy-side investment teams evaluate the informational value of research provided by different brokerage firms.

## Research Hypothesis

**Primary Hypothesis:** Goldman Sachs analyst upgrades and downgrades are associated with larger absolute abnormal stock returns than comparable recommendations from Morgan Stanley or JPMorgan.

**Null Hypothesis:** There is no statistically significant difference in the magnitude of abnormal stock returns associated with recommendations from the three brokerage firms.

We will test these hypotheses using historical analyst recommendations and stock price data.

## Proposed Data Sources

- **Yahoo Finance (yfinance):** Analyst upgrades and downgrades, including broker names, recommendation dates, and rating changes.
- **Historical Stock Prices:** Daily stock prices and returns.
- **Earnings Announcements:** Earnings dates used to identify potentially confounding events.
- **Market Benchmark:** Broad market index returns used to estimate abnormal stock performance.

### Initial Companies

We will begin by testing data availability for:

1. Apple (AAPL)
2. Microsoft (MSFT)
3. Nvidia (NVDA)
4. Amazon (AMZN)
5. Tesla (TSLA)

If sufficient data is available, we plan to expand the analysis to approximately 50 large publicly traded companies.

### Time Period

Our target sample will cover approximately five years of historical analyst recommendations and stock returns, subject to data availability.

## Planned Methodology

We will conduct an event study to measure stock price reactions surrounding analyst upgrades and downgrades.

### Step 1: Data Collection

Collect historical analyst rating changes issued by Goldman Sachs, Morgan Stanley, and JPMorgan.

For each recommendation, we will attempt to identify:

- Company ticker
- Brokerage firm
- Recommendation date
- Previous analyst rating
- New analyst rating
- Upgrade or downgrade classification

### Step 2: Calculate Stock Returns

Collect historical daily stock prices and calculate daily returns around recommendation dates.

We will compare stock returns with a market benchmark to estimate abnormal returns.

### Step 3: Event Study

Calculate:

- **Abnormal Returns (AR):** Stock returns adjusted for expected market performance.
- **Cumulative Abnormal Returns (CAR):** Total abnormal returns over a specified event window.

We will examine stock price reactions before, during, and after analyst recommendation changes.

### Step 4: Broker Comparison

Compare the market reactions associated with recommendations from:

1. Goldman Sachs
2. Morgan Stanley
3. JPMorgan

We will examine average abnormal returns, cumulative abnormal returns, sample sizes, and confidence intervals.

### Step 5: Statistical Analysis

Evaluate whether observed differences across brokers are statistically significant.

We will also examine whether upgrades and downgrades produce different market reactions.

### Step 6: Control for Confounding Events

Identify recommendations issued near company earnings announcements.

We will compare results with and without these events to evaluate whether earnings announcements influence our findings.

## Planned Dashboard

We plan to develop an interactive dashboard using Streamlit.

The dashboard will include:

- **Broker Leaderboard:** Compare Goldman Sachs, Morgan Stanley, and JPMorgan based on average absolute abnormal returns.
- **Upgrade vs. Downgrade Analysis:** Compare market reactions to positive and negative rating changes.
- **Event Study Charts:** Display cumulative abnormal returns surrounding analyst recommendations.
- **Company Filters:** Examine individual stocks and compare results across companies.
- **Confidence Intervals:** Show statistical uncertainty surrounding broker comparisons.
- **Sample Sizes:** Display the number of recommendations analyzed for each broker.

## Minimum Viable Product (MVP)

Our initial project will focus on:

- Analyst recommendations from three major investment banks.
- Approximately 50 large publicly traded companies, subject to data availability.
- Five years of historical data, where available.
- Upgrades and downgrades.
- Abnormal returns and cumulative abnormal returns.
- Comparisons across brokerage firms.

## Potential Extensions

If time permits, we may investigate:

- Whether recommendations that go against analyst consensus generate larger stock price reactions.
- Whether the influence of brokerage firms differs across industries.
- Whether downgrades generate stronger reactions than upgrades.
- Whether recommendations near earnings announcements produce different results.

## Project Structure

The repository will be organized as the project develops.

Planned components include:

- `README.md` — Project overview and methodology.
- `STATUS.md` — Project progress and updates.
- `data/` — Data files used for analysis.
- `notebooks/` — Python notebooks for data collection and research.
- `src/` — Reusable Python functions.
- `app.py` — Streamlit dashboard.
- `requirements.txt` — Required Python packages.

## Current Project Status

**Current Stage:** Research planning and data feasibility testing.

### Next Steps

1. Test analyst recommendation data for the five initial companies.
2. Verify that the three brokerage firms have sufficient historical recommendations.
3. Collect historical stock returns.
4. Calculate preliminary abnormal returns.
5. Develop a small working event-study prototype.
6. Begin building the Streamlit dashboard.
7. Document progress in `STATUS.md`.

## Team Members and Responsibilities

**Team Name:** Free Agents

- **Team Member 1:** To be assigned.
- **Team Member 2:** To be assigned.
- **Team Member 3:** To be assigned.

Responsibilities will include data collection, financial analysis, dashboard development, and documentation.

## Reproducibility

Our GitHub repository will include the code, data source information, dependencies, and instructions needed to reproduce our research.

We aim to ensure that another researcher can run our analysis and verify the results.

## Research Limitations

Important considerations include:

- **Earnings Confounds:** Rating changes issued near earnings announcements may coincide with other market-moving information.
- **Announcement Timing:** Recommendations released before market open or after market close may require different event-date treatment.
- **Small Sample Sizes:** Some brokerage firms may have fewer recommendations than others.
- **Historical Data Availability:** Yahoo Finance may not provide complete recommendation histories.
- **Selection Bias:** Our chosen companies may not represent the broader equity market.
- **Causality:** An observed stock price reaction does not necessarily prove that an analyst recommendation caused the movement.

## References

Womack, K. L. (1996). Do Brokerage Analysts' Recommendations Have Investment Value? *The Journal of Finance*, 51(1), 137–167.
