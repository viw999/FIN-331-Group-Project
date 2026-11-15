# FIN 331 Final Project Proposal

## Team Free Agents

**Team Members:** Lauren Bower and Victor Weiss

---

## 1. Research Question and Motivation

**Research Question:** Do analyst upgrades and downgrades from Goldman Sachs lead to larger abnormal stock returns than those from Morgan Stanley or JPMorgan?

Goldman Sachs, Morgan Stanley, and JPMorgan are three of the biggest names in finance, but we wanted to see if their analyst recommendations actually have the same influence on stock prices. We were especially interested in Goldman Sachs because of its reputation and whether investors take its recommendations more seriously than those from other major banks.

We thought this would be interesting to study because investors pay attention to what analysts at large financial institutions are saying about stocks. If Goldman Sachs upgrades or downgrades a company, does the stock price react more than it would to a similar recommendation from Morgan Stanley or JPMorgan? We want to see whether the name behind a recommendation really makes a difference.

By comparing stock returns around these recommendations, we hope to find out whether Goldman Sachs has a stronger influence on market reactions or whether the three banks produce relatively similar results. This could be useful for investors and portfolio managers who use analyst research when making investment decisions.

---

## 2. Data

For our project, we're using data from Financial Modeling Prep (FMP) to look at how stock prices react to analyst upgrades and downgrades. We're focusing on 25 large U.S. companies and comparing recommendations from Goldman Sachs, Morgan Stanley, and JPMorgan.

Our dataset begins in January 2010, with the final end date depending on the latest available data when we run the analysis. Each row represents one stock on a specific trading day. We're looking at daily stock prices, returns, analyst rating changes, and S&P 500 returns. Comparing individual stock returns to the overall market will help us see whether a stock moved more than we would normally expect.

### Main Variables

| Variable | What It Tells Us |
|---|---|
| `ticker` | Which stock we're looking at |
| `date` | The trading day |
| `adj_open`, `adj_close` | Adjusted opening and closing stock prices |
| `ret` | Daily stock return |
| `sp500_ret` | Daily S&P 500 return |
| `gs_change` | Whether Goldman Sachs upgraded or downgraded the stock |
| `ms_change` | Whether Morgan Stanley upgraded or downgraded the stock |
| `jpm_change` | Whether JPMorgan upgraded or downgraded the stock |
| `earnings` | Whether the company reported earnings |
| `other_changes` | Rating changes from other banks |

The most important information for our analysis is the date of each recommendation, which bank issued it, and how the stock performed around that date. We also want to account for earnings announcements and recommendations from other banks because those could influence stock prices at the same time.

### Data Collection

We're using `build_dataset.py` to download and organize the data from FMP. The original downloads are stored in `data/raw/`, and the combined dataset is saved in `data/clean/dataset.csv`.

We then use `build_events.py` to identify the upgrades and downgrades we're interested in studying. This lets us focus on how stocks perform around those recommendations instead of looking at every trading day.

Because FMP restricts sharing data under its free plan, each team member generates the dataset locally rather than uploading it to GitHub.

### Sample Data

The final dataset will contain one row per stock per trading day, including prices, returns, rating changes, and earnings information.

**Dataset sample:** [Insert 3–5 actual rows from `data/clean/dataset.csv` after running the pipeline.]

**Sample period:** January 2010 to [confirm final date from dataset].

---

## 3. Methodology

### Event Study Approach

For our analysis, we're using an event study to measure how stock prices react when Goldman Sachs, Morgan Stanley, or JPMorgan issues an upgrade or downgrade.

An event study looks at stock returns around a specific event. In our case, the event is the date when an analyst changes their recommendation. We want to see whether the stock reacts differently depending on which bank made the recommendation.

We'll look at the stock's return on the day of the recommendation and over a three-day period surrounding the event. This will help us capture both the immediate reaction and any price movement right before or after the recommendation.

### Measuring Abnormal Returns

To measure the impact of each recommendation, we'll compare the stock's return to the S&P 500 return on the same day.

We'll calculate abnormal returns using:

**Abnormal Return = Stock Return - S&P 500 Return**

For example, if a stock increases by 3% while the S&P 500 increases by 1%, the abnormal return would be 2%.

This helps us separate the stock's individual performance from movements in the overall market.

We'll also calculate cumulative abnormal returns (CAR) over the three-day event window, which includes the day before the recommendation, the day of the recommendation, and the day after.

**CAR(-1,+1) = AR(-1) + AR(0) + AR(+1)**

This allows us to compare how much stocks move around recommendations from each bank.

### Comparing the Three Banks

Once we calculate abnormal returns, we'll group the results by bank and recommendation type.

We'll compare upgrades separately from downgrades because we expect them to affect stock prices in different directions.

For upgrades, we'll look at whether Goldman Sachs recommendations lead to larger positive abnormal returns.

For downgrades, we'll look at whether Goldman Sachs recommendations lead to larger negative abnormal returns.

We'll calculate average abnormal returns for each bank and use statistical tests to see whether the differences are significant.

We'll also use a regression to examine whether the bank issuing the recommendation is associated with the size of the stock-price reaction.

Our main goal is to determine whether Goldman Sachs recommendations are associated with stronger market reactions, rather than assuming its reputation automatically gives it more influence.

---

## 4. Potential Limitations and Robustness Checks

There are a few limitations we need to consider when interpreting our results.

### Earnings Announcements

One issue is that companies sometimes release earnings around the same time an analyst changes a recommendation.

If a stock moves significantly after an earnings announcement, we wouldn't necessarily know whether the movement was caused by the earnings news or the analyst recommendation.

To address this, we'll identify recommendations that occur close to earnings announcements and exclude them from our main analysis.

### Other Analyst Recommendations

Another issue is that multiple banks might change their recommendations for the same stock around the same time.

If Goldman Sachs upgrades a company and another bank issues an upgrade that day, it becomes harder to determine which recommendation influenced the stock price.

We'll flag these overlapping recommendations and compare our results with and without them.

### Data Limitations

Our data comes from Financial Modeling Prep, which may have missing information, duplicate recommendations, or incorrect dates.

We'll use the data-cleaning steps in our Python scripts to identify and handle these issues.

We also recognize that our analysis only covers 25 large stocks, so the results may not apply to every company in the market.

Finally, even if we find that Goldman Sachs recommendations are associated with larger stock-price reactions, we can't prove that its reputation alone caused the difference. Other factors, such as the information contained in the recommendation or the companies being covered, could also matter.

---

## 5. Expected Results and Hypothesis

Our main hypothesis is that Goldman Sachs recommendations will be associated with larger abnormal stock returns than similar recommendations from Morgan Stanley or JPMorgan.

We think this could happen because Goldman Sachs has a strong reputation in investment banking and equity research. Investors may place more weight on its recommendations, which could lead to larger price reactions.

For upgrades, we would expect Goldman Sachs to have larger positive abnormal returns. For downgrades, we would expect larger negative abnormal returns.

However, it's also possible that the three banks will produce similar results because they're all well-established financial institutions.

We won't know whether our hypothesis is supported until we complete the analysis and compare the results.

---

## 6. Dashboard and Presentation Plan

We plan to use Streamlit to create an interactive dashboard that makes our findings easier to understand.

The dashboard will focus on comparing the market reactions to recommendations from Goldman Sachs, Morgan Stanley, and JPMorgan.

### Planned Dashboard Features

**1. Bank Comparison**

A chart comparing average abnormal returns across the three banks. This will help us see whether one bank's recommendations are associated with larger stock-price movements.

**2. Upgrades vs. Downgrades**

A comparison showing how stocks react to positive and negative recommendation changes.

**3. Event Study Chart**

A graph showing average abnormal returns around the recommendation date. This will help us visualize when stock prices react and whether the effects continue after the event.

**4. Statistical Results**

A table showing average abnormal returns, confidence intervals, and statistical tests comparing the banks.

**5. Interactive Filters**

If possible, we'll include filters that allow users to select a bank, recommendation type, or individual stock.

### Intended Audience

Our dashboard is intended for investors, portfolio managers, and students interested in how analyst research affects financial markets.

The goal is to make the results understandable without requiring someone to read through all the underlying Python code or statistical output.

We think the dashboard could be useful for investors who want to understand whether recommendations from certain financial institutions are associated with stronger stock-price reactions.

---

## 7. Project Workflow

Our team is using Python and GitHub to organize the project.

The analysis is divided into four main steps:

| Step | Script | Purpose |
|---|---|---|
| 1 | `build_dataset.py` | Download and organize stock and analyst data |
| 2 | `build_events.py` | Identify upgrades, downgrades, and event windows |
| 3 | `analyze_events.py` | Calculate results and compare the banks |
| 4 | `make_report.py` | Generate tables, figures, and a written summary |

We can run the full analysis using:

`python run_all.py`

After the analysis is complete, we'll use the generated tables and figures to help build our Streamlit dashboard.

Keeping the data analysis and dashboard separate should make it easier to update the results if we make changes to the dataset or methodology.

---

## 8. References

Financial Modeling Prep. (n.d.). *Financial market data and APIs*. https://financialmodelingprep.com/

Streamlit. (n.d.). *Streamlit documentation*. https://docs.streamlit.io/

Womack, K. L. (1996). Do brokerage analysts' recommendations have investment value? *The Journal of Finance, 51*(1), 137–167. https://doi.org/10.1111/j.1540-6261.1996.tb05205.x

---

## 9. Conclusion

Overall, our project focuses on whether the financial institution behind an analyst recommendation influences how the stock market reacts.

We're particularly interested in Goldman Sachs because of its reputation and whether that translates into larger abnormal returns compared to Morgan Stanley and JPMorgan.

By using stock-price data, an event study, and statistical comparisons, we hope to better understand how much influence analyst recommendations have on investors.

Our goal is to present the findings in a way that's easy to understand and shows whether the differences between the three banks are meaningful.
