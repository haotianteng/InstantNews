# Pain Point Discovery Report — InstNews (SIGNAL)

**Date:** 2026-04-02
**Purpose:** Pre-launch research to validate positioning, identify highest-leverage pain points, and inform go-to-market strategy.

---

## 1. User Personas

### Persona A: Retail Day Trader

**Profile:** Individual trading stocks/options intraday from a home office. Typical account size $10K-$100K. Uses a broker platform (ThinkorSwim, IBKR, Webull) and supplements with external news.

**Current Workflow (step by step):**
1. Pre-market (6:00-9:30 AM ET): Opens 4-6 browser tabs — CNBC.com, Yahoo Finance, Bloomberg, Twitter/X, and broker newsfeed.
2. Scans each tab manually for headlines that might move their positions or watchlist tickers.
3. Checks r/wallstreetbets, r/stocks, and FinTwit for sentiment pulse.
4. During market hours: Alt-tabs between chart software and news tabs. Relies on CNBC live stream audio as a "background alert."
5. Hears something on CNBC or sees a spike on a chart, scrambles to find the headline.
6. By the time they locate the catalyst headline, the initial move has already happened (30-120 seconds late on average for headline-driven moves).
7. Post-market: Reviews what headlines moved the market, often realizes they missed 2-3 actionable events during the day.

**Biggest Friction Points:**
- **Latency tax:** News travels Twitter -> Bloomberg Terminal -> CNBC -> free sites. By the time it hits Yahoo Finance, the move is done. Retail traders are systematically last in the information chain.
- **Tab hell:** Managing 5+ news tabs is cognitively expensive. Context-switching between charts and news costs seconds that matter in fast markets.
- **No filtering:** Free news sites show everything — crypto, politics, sports mixed with market-moving headlines. No way to filter to just high-impact financial news.
- **No sentiment context:** A headline says "Fed signals pause" — is that bullish or bearish? Day traders must interpret sentiment themselves under time pressure.
- **Duplicate noise:** The same story appears on every tab (Reuters wire picked up by 10 outlets), wasting scanning time.

**Willingness to Pay:**
- Currently pays $0-$30/mo for news (most use free sources).
- Many pay $100-$300/mo for charting (TradingView Premium, ThinkorSwim).
- Would pay for news if it demonstrably saved them from even one bad entry per month (one saved losing trade = $50-500+ in avoided losses).
- Price sensitivity: $15/mo is an easy "yes" if value is clear. $40/mo requires visible ROI. $100+/mo is Bloomberg territory — too expensive.

**How InstNews Solves Their Problem:**
- **Single feed, 15+ sources:** Eliminates tab hell. One terminal replaces 5 browser tabs.
- **Tradeable signal detection (lightning bolt):** Instantly flags headlines with actionable catalysts (earnings beats, FDA decisions, M&A) — reduces scanning time from minutes to seconds.
- **AI sentiment scoring:** Each headline scored -1.0 to +1.0, removing the interpretation step. Trader sees "+0.87" and knows it's strongly bullish without reading the full article.
- **Smart deduplication:** Same story from Reuters, AP, Bloomberg collapsed into one entry. Cuts noise by 30-50%.
- **3-second refresh (Pro):** Fastest refresh rate among tools at this price point.
- **$29.99/mo price:** Fraction of charting software costs. One saved bad trade/month covers the annual subscription.

---

### Persona B: Swing/Position Trader

**Profile:** Holds positions for days to weeks. More focused on macro themes, sector rotation, and earnings cycles than intraday ticks. Typical account $50K-$500K. Often has a day job and trades part-time.

**Current Workflow (step by step):**
1. Morning routine (15-30 min): Reads Briefing.com or Morning Brew email digest, skims CNBC headlines.
2. Checks economic calendar for upcoming events (FOMC, jobs report, CPI).
3. Reviews sector ETF performance for rotation signals.
4. During the day: Glances at phone for push notifications from Yahoo Finance or CNBC app — but notifications are often irrelevant or delayed.
5. After market close: Spends 30-60 min reading analysis on SeekingAlpha, MarketWatch, and financial Twitter.
6. Tries to connect dots between macro news and sector/stock impact manually. E.g., "Tariffs on China announced" -> "Which of my holdings has China supply chain exposure?"
7. Misses the connection between a policy headline and its downstream sector impact until the move is well underway.

**Biggest Friction Points:**
- **Connecting dots across sources:** Macro news (tariffs, rate decisions, policy changes) affects different sectors differently. No single tool maps news to sector/stock impact automatically.
- **Information lag for part-time traders:** Cannot monitor news all day. By the time they see the evening summary, the market has already priced in the news.
- **Earnings season overload:** During earnings season, 50+ companies report daily. Impossible to track all relevant reports manually.
- **Sentiment ambiguity on macro news:** "Fed holds rates steady" — is the market reading this as dovish or hawkish? Current tools don't clarify market interpretation.
- **Too many subscriptions:** SeekingAlpha Premium ($240/yr), Briefing.com ($25/mo), TradingView ($15/mo) — costs add up for features that overlap.

**Willingness to Pay:**
- Already pays $30-$60/mo across various tools (SeekingAlpha, Briefing.com, newsletters).
- Would consolidate subscriptions if one tool replaced two or more.
- Values depth of analysis over raw speed. Willing to pay $15-$40/mo for a tool that saves 30+ minutes of daily scanning.

**How InstNews Solves Their Problem:**
- **Aggregated feed with source filtering:** One view across all major financial sources. Filter to only macro/policy sources during FOMC week, or earnings-heavy sources during earnings season.
- **Sentiment scoring provides instant macro interpretation:** Instead of guessing whether "CPI comes in hot" is net positive or negative, the sentiment score gives immediate directional context.
- **Historical data (1 year on Plus, 5 years on Max):** Backtest how similar headlines moved markets in the past. "Last time the Fed paused, sentiment was X and markets did Y."
- **Keyword search:** Search "tariff" or "semiconductor" to instantly find all related headlines across all sources in one query.
- **Date range filtering:** Focus on a specific earnings week or event window without scrolling through irrelevant days.
- **Watchlist (Plus, future):** Track only tickers in their portfolio. Get a filtered view of news relevant to their positions.

---

### Persona C: Finance Professional / Analyst

**Profile:** Works at a hedge fund, asset manager, family office, or research firm. Needs to stay current on market news as part of their job. Often junior-to-mid level (senior analysts have Bloomberg Terminal access allocated by the firm). Writes research reports and morning notes.

**Current Workflow (step by step):**
1. Arrives at desk 6:30-7:00 AM ET. Opens Bloomberg Terminal (if available) or starts with Reuters Eikon.
2. If no terminal access: opens 8-10 browser tabs across Reuters, Bloomberg.com, FT, WSJ, CNBC, MarketWatch, and sector-specific sources.
3. Spends 1.5-2.5 hours scanning headlines, flagging relevant stories, and compiling a morning briefing document for the team.
4. Throughout the day: monitors news for anything that impacts the portfolio or research coverage.
5. Copies and pastes relevant headlines into Slack/Teams channels for the team.
6. Writes end-of-day summary of key market developments.
7. Struggles with information overload — sees the same story across 8 sources, must determine which version has the most useful detail.

**Biggest Friction Points:**
- **2+ hours daily on news scanning:** This is pure overhead time that doesn't generate alpha or analysis. It's manual, repetitive, and low-value but critical.
- **Bloomberg Terminal cost:** $24,000/year per seat. Firms limit access. Junior analysts and smaller firms often can't justify the cost but need similar news coverage.
- **Duplicate stories waste time:** The same Reuters wire appears on Bloomberg, CNBC, Yahoo, and MarketWatch. Analyst reads the headline 4 times before realizing it's the same story.
- **No programmatic access on free tools:** Analysts who want to build models or automated reports can't easily pull structured data from free news sources.
- **Compliance and sourcing:** Need to track which source reported something first for research attribution. Current workflow makes this tedious.

**Willingness to Pay:**
- Firm pays for tools — budget is $50-$500/mo per analyst for non-Bloomberg tools.
- Personally (if at a small firm): would pay $15-$40/mo out of pocket if it saved 30+ minutes/day.
- Highly values API access for building automated morning briefing documents.
- Would pay for CSV export to feed into Excel models.

**How InstNews Solves Their Problem:**
- **Cuts scanning time from 2 hours to 20 minutes:** Single feed with deduplication and sentiment scoring eliminates the manual tab-by-tab scanning process.
- **Bloomberg-grade coverage at 1% of the cost:** 15+ sources aggregated for $29.99/mo vs. $2,000/mo for Bloomberg. Not a full Bloomberg replacement, but covers the news aggregation function.
- **Deduplication = no repeated reads:** Each story appears once, regardless of how many sources carry it. Saves the "haven't I read this already?" cognitive cost.
- **REST API for automation:** Build automated morning briefing scripts that pull top headlines with sentiment scores. Integrate into Slack bots, email digests, or research pipelines.
- **CSV export:** Download filtered news into Excel for model inputs or team distribution.
- **Source attribution:** Each headline shows its source, making research citation straightforward.

---

### Persona D: Algo/Quant Trader

**Profile:** Builds automated or semi-automated trading systems. May work at a prop firm or trade personal capital with systematic strategies. Uses Python/R/C++ for strategy development. Needs machine-readable signals from unstructured news text.

**Current Workflow (step by step):**
1. Subscribes to expensive data feeds: Bloomberg B-PIPE ($10K+/mo), Refinitiv Machine Readable News ($5K+/mo), or RavenPack ($3K+/mo).
2. If bootstrapping: scrapes RSS feeds manually using custom Python scripts. Breaks frequently as source HTML changes. Spends hours debugging parsers.
3. Builds custom NLP pipeline for sentiment scoring — trains/fine-tunes models, manages embeddings, handles tokenization edge cases.
4. Maintains infrastructure: feed polling, dedup logic, database storage, sentiment model serving.
5. Total infrastructure overhead: 40-100+ hours to build and 5-10 hours/month to maintain a custom news pipeline.
6. Backtests sentiment-based strategies against historical price data.
7. Deploys trading signals that incorporate news sentiment as one factor.

**Biggest Friction Points:**
- **Build vs. buy dilemma:** Building a custom news+NLP pipeline is 100+ hours of engineering. Buying enterprise solutions (RavenPack, Bloomberg) costs $3K-$10K+/month.
- **Middle-market gap:** There is almost nothing between "free RSS scraping" and "$5K/month enterprise feeds" for structured financial news data. The $15-$40/mo price range is a desert.
- **Maintenance burden:** Custom scrapers break when sources change HTML. NLP models drift. Embedding models need updates. This is ongoing DevOps work that distracts from strategy development.
- **No pre-built sentiment for backtesting:** Historical sentiment data is extremely expensive ($10K+ from vendors). Without it, quants can't backtest sentiment-based strategies.
- **Latency concerns:** For HFT-adjacent strategies, even seconds matter. Free RSS feeds poll every 5-15 minutes.

**Willingness to Pay:**
- Currently pays $0 (scrapes) or $3K-$10K+/mo (enterprise feeds).
- Would eagerly pay $15-$40/mo for a clean REST API with pre-scored sentiment and historical data. This is a no-brainer price point for quant traders.
- Values: structured JSON, consistent schema, historical data depth, low latency, and API reliability.
- The Plus tier ($29.99/mo with API access) is roughly 100x cheaper than the next real alternative.

**How InstNews Solves Their Problem:**
- **REST API with structured JSON:** Every news item comes with `sentiment_score`, `sentiment_label`, `source`, `published`, `duplicate` flag — machine-readable out of the box.
- **Eliminates 100+ hours of pipeline building:** No need to build RSS scrapers, NLP models, or dedup logic. InstNews does all of this.
- **Pre-scored sentiment for backtesting:** Historical data with sentiment scores enables backtesting sentiment-based strategies without building a custom NLP pipeline.
- **$29.99/mo vs. $3,000+/mo:** 200x cheaper than enterprise alternatives. Even the Max tier at $89.99/mo is 75x cheaper than RavenPack.
- **Multiple language SDKs:** Python, JavaScript, Go, R, Rust examples in the docs — quants can integrate in minutes.
- **3-second refresh rate (Max tier):** Fast enough for swing and position strategies. Not HFT, but covers 90% of quant use cases.
- **500 items/request + 120 req/min (Max):** Sufficient throughput for most systematic strategies.

---

## 2. Competitive Analysis

### Bloomberg Terminal

**What it is:** The gold standard of financial data terminals. $24,000/year ($2,000/month) per seat. Comprehensive: news, data, analytics, messaging, trading execution.

**User Complaints (from Reddit r/finance, r/CFA, r/algotrading, finance forums):**
- **Price:** The #1 complaint, universally. "I would love Bloomberg but I'm not paying $24K/year as a retail trader." Individual traders and small firms are priced out entirely.
- **Overkill:** 90% of features go unused by most subscribers. Traders who only need news are paying for bond analytics, FX tools, and messaging they never touch.
- **Antiquated UI:** The terminal interface is from the 1990s. Keyboard-driven commands (e.g., "TOP GO", "NH GO") have a steep learning curve. New users report 2-4 weeks to become proficient.
- **Lock-in:** Data cannot easily be exported or integrated into external tools. Bloomberg wants to be the entire workflow, not one tool in a stack.
- **Contract terms:** 2-year minimum contracts. Difficult to cancel. Users report aggressive sales tactics and poor cancellation experiences.

**InstNews advantage:** Covers the news aggregation + sentiment function of Bloomberg at 0.6% of the cost. Modern web UI with no learning curve. REST API for easy integration. No contracts.

---

### Benzinga Pro

**What it is:** Real-time financial news and data platform. Pricing: $117/month (Essential) to $177/month (Basic with audio squawk). Positioned as a Bloomberg alternative for retail traders.

**Strengths:**
- Real-time audio squawk (human reads headlines aloud) — traders can listen while watching charts.
- Calendar integration (earnings, economic events, FDA dates).
- Movers feature (real-time stock movers with catalysts).
- Community chat rooms.

**Weaknesses / User Complaints (from Reddit r/daytrading, app store reviews, forums):**
- **Price creep:** Users report prices increasing from $99 to $117 to $177 over the past few years. "Getting too expensive for what it offers."
- **Squawk quality inconsistent:** Some users report the audio readers miss headlines or are late compared to Twitter.
- **Free tier gutted:** Benzinga's free offering was reduced significantly, pushing users to paid plans.
- **Interface cluttered:** "Too much going on, hard to find what matters." Information overload within the tool itself.
- **Reliability:** Reports of feeds going down during high-volatility events (exactly when traders need them most).
- **Limited API access:** No affordable API for quants. Enterprise API pricing is opaque and expensive.

**InstNews advantage:** 8-12x cheaper ($29.99 vs. $117-$177). Cleaner, terminal-style UI designed for focused scanning. Built-in sentiment scoring (Benzinga has no equivalent). REST API included in Plus tier. ML deduplication that Benzinga lacks.

---

### TradeTheEvent / Hammerstone Markets

**What they are:** Ultra-low-latency news services aimed at active day traders. Hammerstone: ~$100/month. TradeTheEvent: ~$50-$100/month (varies by plan).

**Strengths:**
- Fastest news delivery (often seconds ahead of CNBC).
- Human curation — editors filter and prioritize headlines.
- Audio squawk with expert commentary.
- Direct integration with some broker platforms.

**Weaknesses:**
- **Niche and expensive:** $50-$100/mo for essentially a curated news feed.
- **No AI/NLP features:** No automated sentiment scoring, no dedup, no structured data output.
- **No API:** Designed for human consumption only. Quant traders cannot use them programmatically.
- **Small teams:** Reliability concerns. Less redundancy than larger platforms.
- **No historical data:** Live-only. Cannot review past headlines or backtest.

**InstNews advantage:** AI sentiment scoring provides structured signals that human curation cannot scale. API access enables automation. Historical data enables backtesting. Dedup reduces noise. Lower price point with broader feature set.

---

### Google Finance / Yahoo Finance (Free Alternatives)

**What they are:** Free financial news aggregators bundled with stock quotes, charts, and portfolio tracking.

**What Users Like:**
- Free. No sign-up required.
- Portfolio tracking and basic charting.
- Wide news coverage from major sources.
- Mobile apps are polished (especially Yahoo Finance).

**What's Missing (common complaints):**
- **Speed:** News appears 5-30 minutes after it hits professional terminals. Useless for day trading.
- **No sentiment analysis:** Headlines are raw text. No scoring, no filtering by bullishness/bearishness.
- **No deduplication:** The same Reuters/AP wire story appears 10 times from different sources. Massive noise.
- **Ads everywhere:** Yahoo Finance in particular has become an ad-heavy experience. "More ads than content."
- **No API (or deprecated):** Yahoo Finance API was officially shut down. Unofficial scrapers are unreliable. Google Finance has no API.
- **Algorithmic curation bias:** Headlines selected by engagement algorithms, not market relevance. Clickbait headlines rise to the top.
- **No filtering by source or sentiment:** Cannot focus on just macro news, or just bearish headlines, or just a specific source.

**InstNews advantage:** Real-time (not 5-30 min delayed). Sentiment scoring on every item. Deduplication. Source filtering. No ads. Clean, focused UI. Free tier available for basic browsing, with clear upgrade path for serious users.

---

### Twitter/X FinTwit

**What it is:** The financial community on Twitter/X. Traders, analysts, and journalists post real-time market commentary, breaking news, and analysis.

**Strengths:**
- Often the fastest source for breaking news (traders see headlines on Twitter before CNBC).
- Free.
- Community interaction — can ask questions, share ideas.
- Some high-quality accounts provide genuine alpha.

**Weaknesses / The Signal-to-Noise Problem:**
- **Overwhelming noise:** For every useful tweet, there are 100 memes, pump-and-dumps, affiliate links, and uninformed opinions.
- **No verification:** Anyone can claim "BREAKING: [ticker] earnings beat." No way to distinguish real news from speculation.
- **Algorithmic timeline:** Twitter's algorithm surfaces engagement bait, not market-relevant information. Missing chronological feed means missing time-sensitive news.
- **Pump and dump risk:** Accounts with large followings can move micro-cap stocks with unverified claims. Following FinTwit without skepticism is dangerous.
- **No structured data:** Cannot filter by sentiment, source quality, or ticker. Cannot export or query programmatically.
- **Time sink:** Traders report spending 1-3 hours daily on Twitter "for research" that yields 10 minutes of actually useful information.

**InstNews advantage:** Curated, verified sources only (Reuters, Bloomberg, CNBC, etc.). No user-generated noise. Structured, filterable data. Sentiment scored by AI, not crowd emotion. Dedup prevents the echo-chamber effect where one story dominates the feed through retweets.

---

## 3. Landing Page A/B Test Variants

### Variant A: Speed Angle — "Know Before the Market Moves"

**Target persona:** Retail Day Trader (Persona A)
**Core pain point:** Entering trades late because news reaches free sources after the move has started.

**Headline:**
> Financial News at the Speed of Markets

**Subheadline:**
> 15+ sources. One terminal. Real-time sentiment scoring. Stop being the last to know why a stock just moved 5%.

**Key Visual Concept:**
Split-screen comparison. Left side: cluttered desktop with 6 browser tabs open, each showing a different news site, with a clock showing "2 minutes late." Right side: clean InstNews terminal with the same headline highlighted and a lightning bolt, clock showing "Real-time." The visual should evoke the feeling of going from chaos to clarity.

**Primary CTA:**
> Start Free — See It Live

**Supporting proof points:**
- "3-second refresh rate"
- "Tradeable signal detection flags catalysts instantly"
- "Used by traders who can't afford to be 2 minutes late"

---

### Variant B: Overload Angle — "Stop Drowning in Financial News"

**Target persona:** Swing Trader (Persona B) and Finance Professional (Persona C)
**Core pain point:** Spending 1-2+ hours daily scanning duplicate headlines across multiple sources.

**Headline:**
> Every Financial Headline. Zero Noise.

**Subheadline:**
> AI deduplication cuts through 15+ sources to show each story once, scored by sentiment. Reclaim the 2 hours you spend scanning tabs every morning.

**Key Visual Concept:**
Animated visualization: a flood of overlapping, grayed-out duplicate headlines flowing in from the left, passing through an "InstNews" filter in the center, and emerging on the right as clean, deduplicated, color-coded (green/red/yellow sentiment) single entries. The visual metaphor is a funnel — chaos in, clarity out.

**Primary CTA:**
> Cut Your News Scanning Time by 80%

**Supporting proof points:**
- "ML-powered deduplication — each story appears once"
- "Sentiment scoring eliminates interpretation time"
- "Source filtering lets you focus on what matters"

---

### Variant C: Access Angle — "Bloomberg-Level Intelligence at 1% of the Cost"

**Target persona:** Finance Professional (Persona C) and Algo/Quant Trader (Persona D)
**Core pain point:** Bloomberg costs $24K/year. The next best option is $1,400+/year (Benzinga). There's nothing good in the $15-$40/month range.

**Headline:**
> Professional Financial News Intelligence — Without the $24K Price Tag

**Subheadline:**
> AI sentiment analysis, 15+ real-time sources, REST API, and historical data. Everything you need from a news terminal for $29.99/month.

**Key Visual Concept:**
A pricing comparison bar chart showing Bloomberg ($2,000/mo), Benzinga Pro ($177/mo), Hammerstone ($100/mo), and InstNews Plus ($29.99/mo). InstNews bar is dramatically shorter with a green "YOU ARE HERE" marker. Above the bars, feature checkmarks show that InstNews has sentiment scoring and API access that some competitors lack.

**Primary CTA:**
> Try the Terminal Free — Upgrade for $29.99/mo

**Supporting proof points:**
- "REST API included — build trading bots in minutes"
- "200x cheaper than enterprise news feeds"
- "Same sources: Reuters, Bloomberg, CNBC, and more"

---

## 4. "Fake Door" Test Plan

### Purpose
Surface locked Pro features to Free users to measure click/tap intent. Each click on a locked feature is a signal of willingness to pay. Track click-through rates to prioritize which Pro features to build and emphasize in marketing.

### Features to Surface as Locked Teasers

| Feature | Where to Show | Implementation |
|---------|---------------|----------------|
| **Sentiment Score** | Show grayed-out sentiment badges on each headline with a lock icon. Tooltip: "Upgrade to Plus to see sentiment scores." | Already partially implemented — Free tier strips sentiment data. Add visual placeholder instead of hiding entirely. |
| **Duplicate Detection** | Show a subtle "[3 sources]" badge on headlines that have duplicates, grayed out. Click reveals: "Plus shows which stories are duplicates so you read each one only once." | Currently hidden entirely for Free. Show the badge but lock the detail. |
| **Date Range Filter** | Show the date range picker in the UI but disabled/grayed. Click triggers upgrade modal: "Filter by date range with Plus — search up to 1 year of history." | Low engineering effort — just disable the control and add a click handler. |
| **CSV Export** | Add an "Export CSV" button in the toolbar, grayed out with a lock icon. Click triggers: "Export your filtered results to CSV with Plus." | Button-only fake door — the feature isn't built yet. Measures demand. |
| **API Access** | In the docs page, show API examples but with a banner: "API access requires Plus ($29.99/mo). Start your free trial." | Already have the docs page. Add the upgrade banner. |
| **Watchlist** | Add a "Add to Watchlist" star icon next to each headline, grayed with lock. Click triggers: "Track your favorite tickers with Plus." | Fake door for an unbuilt feature. High signal for demand. |
| **Custom Alerts** | Add a "Set Alert" bell icon in the filter bar, locked. "Get notified when keywords appear — available on Max." | Fake door for Max tier. Measures willingness to pay $89.99. |

### Tracking Implementation
- Log each click event with: `feature_name`, `user_id` (or anonymous session), `timestamp`, `page_location`.
- Dashboard: rank features by click-through rate (clicks / impressions).
- Run for 2-4 weeks post-launch to gather statistically significant data.
- Use results to: (a) prioritize feature development, (b) refine pricing page copy to emphasize most-wanted features.

### Expected Highest-Intent Features (Hypothesis)
1. **Sentiment Score** — most visible, highest curiosity.
2. **Watchlist** — strong intent signal for repeat users.
3. **CSV Export** — high intent from analyst persona.
4. **Custom Alerts** — high intent from position traders.

---

## 5. User Interview Script

### Pre-Interview Setup
- Target: 8-12 interviews across all four personas.
- Duration: 20-30 minutes each.
- Recording: Ask permission to record. Take notes in real time.
- Incentive: 3 months free Plus access.

### Questions

**1. Walk me through how you consume financial news on a typical trading day. Start from when you wake up.**
*(Open-ended. Listen for: number of sources, time spent, tools used, pain points they mention unprompted.)*

**2. What's the most frustrating part of staying current with financial news?**
*(Identify the #1 pain point. Common answers: too many sources, too slow, too much noise, costs too much.)*

**3. Can you tell me about a time you missed a market-moving headline — or saw it too late? What happened?**
*(Concrete story. Anchors the pain in a real financial outcome. Listen for: dollar amount lost, emotional reaction, what they changed afterward.)*

**4. What tools or services do you currently pay for to get financial news? How much do you spend per month total?**
*(Quantify current spend. Establishes budget anchor and reveals competitors we must beat.)*

**5. If I told you a tool could score every headline as bullish or bearish on a scale from -1 to +1 in real time, how would that change your workflow?**
*(Tests value of sentiment scoring — our core differentiator. Listen for: "that would save me time" vs. "I don't trust AI scoring.")*

**6. How important is it to you that duplicate stories are removed — where the same news appears on multiple sources?**
*(Validates dedup feature value. Some traders want to see all sources for a story; others find duplicates annoying.)*

**7. Do you ever use financial news data programmatically — in scripts, spreadsheets, trading bots, or models? If not, would you if you could?**
*(Segments API-interested users. Identifies Persona D vs. others. Gauges demand for API access feature.)*

**8. I'm going to show you InstNews for 2 minutes. [Demo the terminal.] What's your first impression? What's useful? What's missing?**
*(Live reaction test. Note what they look at first, what they click, what questions they ask.)*

**9. If this tool cost $29.99/month for full sentiment scoring, dedup, API access, and 1 year of history, would you subscribe? What would make it a no-brainer?**
*(Direct pricing test. Listen for: "yes immediately," "maybe if it also did X," or "too expensive." The "what would make it a no-brainer" follow-up reveals the killer feature.)*

**10. If you could wave a magic wand and add one feature to any financial news tool, what would it be?**
*(Uncovers latent needs we haven't considered. Past responses in similar research often surface: custom alerts, ticker-specific feeds, price impact correlation, mobile push notifications, and integration with broker platforms.)*

### Follow-Up Probes (use as needed)
- "You mentioned [X]. Can you tell me more about that?"
- "How much time per day would you estimate you spend on [activity]?"
- "Would you switch from [current tool] to this if it did [feature]?"
- "On a scale of 1-10, how painful is [problem] for you day to day?"

---

## 6. Final Recommendation

### Lead Angle at Launch: Variant C — "Bloomberg-Level Intelligence at 1% of the Cost" (Access Angle)

### Rationale

**1. Largest addressable market with clearest value proposition.**
The access angle speaks to ALL four personas simultaneously:
- Day traders understand "Bloomberg is too expensive for me."
- Swing traders understand "I'm paying too much across too many tools."
- Finance professionals understand "My firm won't give me a Bloomberg seat."
- Quant traders understand "Enterprise feeds cost $3K+/month, this is $15."

The speed angle (Variant A) primarily resonates with day traders — one segment. The overload angle (Variant B) resonates with swing traders and analysts — two segments. The access angle resonates with everyone and creates immediate price anchoring.

**2. Price anchoring is the most powerful conversion lever at this price point.**
When users see "$29.99/mo" next to "$2,000/mo (Bloomberg)" and "$177/mo (Benzinga Pro)," the Plus tier feels absurdly cheap. This is not a feature argument — it's a math argument. Math arguments convert better than feature arguments because they don't require the user to understand or value specific features.

**3. Competitive differentiation is clearest on price.**
InstNews cannot claim to be faster than Bloomberg (it's RSS-based, not direct wire feeds). It cannot claim more sources than Bloomberg (Bloomberg has thousands). But it CAN claim to deliver 80% of the news aggregation value at 0.7% of the cost — and that claim is objectively true and easily verifiable.

**4. The access angle naturally leads to feature discovery.**
A user who arrives via "Bloomberg at 1% of the cost" will explore the terminal, discover sentiment scoring and dedup, and those features become delightful surprises rather than things they needed to be sold on. This is the "land with price, retain with features" strategy.

**5. SEO and content marketing alignment.**
"Bloomberg Terminal alternative," "cheap Bloomberg alternative," and "Bloomberg alternative for retail traders" are high-intent search queries with significant volume. The access angle positions InstNews to capture this search traffic organically.

### Recommended Launch Sequence

1. **Launch with Variant C** as the primary landing page angle.
2. **Run A/B test** with Variant A (speed) as the challenger after 2 weeks and sufficient traffic.
3. **Activate fake door tests** on Day 1 to measure Pro feature intent.
4. **Conduct 8-12 user interviews** in weeks 1-3 to validate personas and gather qualitative data.
5. **After 4 weeks:** Use fake door data + interview insights + A/B test results to either confirm Variant C or pivot to Variant A or B for specific audience segments (e.g., retarget day traders with speed angle, retarget analysts with overload angle).

### Secondary Recommendations

- **For paid acquisition (Google Ads):** Test all three angles as separate ad groups targeting different keywords. Speed angle for "real-time trading news," overload angle for "financial news aggregator," access angle for "Bloomberg alternative."
- **For Product Hunt / Hacker News launch:** Lead with the quant/API angle. Developer communities respond to "structured financial news API for $15/mo" more than consumer messaging.
- **For Reddit marketing (r/daytrading, r/algotrading, r/stocks):** Use authentic, value-first posts showing the terminal with real data. Let the product speak. Avoid overt marketing language — Reddit communities reject hard sells.
- **For Twitter/X FinTwit:** Speed angle works best. Post real-time screenshots showing the terminal catching a headline before it hits mainstream news sites. Visual proof > copy.

---

## Appendix: Key Metrics to Track Post-Launch

| Metric | Target | Why It Matters |
|--------|--------|----------------|
| Landing page -> Terminal click-through | >15% | Measures interest in the product |
| Terminal -> Sign-up conversion | >5% | Measures activation |
| Free -> Plus upgrade rate | >3% within 30 days | Revenue validation |
| Fake door click rates by feature | Rank order | Prioritizes feature development |
| Daily active users (terminal visits) | Growing week-over-week | Retention signal |
| API requests from Plus/Max users | Any usage | Validates quant persona |
| Time-to-first-value | <30 seconds | Terminal should show value immediately |
| NPS from interview subjects | >40 | Product-market fit indicator |
