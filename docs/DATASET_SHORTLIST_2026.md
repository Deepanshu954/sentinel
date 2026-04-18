# Dataset Shortlist (2026) for Sentinel

Goal: higher-quality and higher-quantity sources for realistic traffic/load modeling, while remaining usable on a local MacBook workflow.

## Tier A (Recommended)

1. Wikimedia Pageview Complete
- Source: https://dumps.wikimedia.org/other/analytics/
- Readme: https://dumps.wikimedia.org/other/pageview_complete/readme.html
- Why: per-article time series, very long historical span (2007 to present), uniform formatting.
- License: CC0 (per Wikimedia analytics page).
- Sentinel use: external demand/seasonality patterns and burst windows.

2. Azure Public Dataset (VM + Functions traces)
- Source: https://github.com/Azure/AzurePublicDataset
- Why: production cloud traces, strong scale, modern and research-grade documentation.
- Example scale (repo docs):
  - Azure VM 2019 (V2): ~2.6M VMs, ~1.9B utilization readings.
  - Azure Functions 2019: minute-level invocation traces.
- License: CC-BY-4.0 (data) + MIT (code) per repository.
- Sentinel use: autoscaling signal engineering and capacity/latency lead-time modeling.

3. Google ClusterData2019 (Borg traces)
- Source: https://github.com/google/cluster-data
- Background: https://research.google/blog/yet-more-google-compute-cluster-trace-data/
- Why: one of the strongest public cloud workload benchmarks; data from 8 clusters in May 2019.
- License: CC-BY (repo).
- Sentinel use: workload variability, queue/resource pressure features, scale policy validation.

4. Alibaba Cluster Trace Program
- Source: https://github.com/alibaba/clusterdata
- Why: large-scale production traces across multiple years/scenarios.
- Example datasets in repo docs:
  - v2018: ~4000 machines across 8 days
  - v2026-GenAI: includes request/latency + middleware + infra layers
- Usage note: some downloads require short survey and research-use terms.
- Sentinel use: modern high-scale burst and multi-layer telemetry behavior.

## Tier B (Strong Supplementary)

5. MAWI Working Group Traffic Archive
- Source: https://mawi.wide.ad.jp/mawi/
- Why: daily backbone traces over many years (2006 to 2026 listed on archive page).
- Usage note: research-purpose use only; privacy guidelines apply.
- Sentinel use: realistic network burst/diurnal patterns and anomaly episodes.

6. Internet Traffic Archive (WorldCup98 + historical HTTP traces)
- Source: https://ita.ee.lbl.gov/
- Trace list: https://ita.ee.lbl.gov/html/traces.html
- Why: classic high-volume web workloads (WorldCup98 listed as 1.3B requests).
- Sentinel use: stress-test event-style surges and log parsing/feature extraction robustness.

## Practical Kaggle Add-ons (Local-Friendly)

7. Google 2019 Cluster sample (Kaggle mirror/sample)
- Example: https://www.kaggle.com/datasets/derrickmwiti/google-2019-cluster-sample
- Why: easier local experimentation before full-scale source ingestion.

8. Web Server Access Logs (3.3 GB)
- Source: https://www.kaggle.com/datasets/eliasdabbas/web-server-access-logs
- Why: large web log parsing/testing dataset for gateway-like traffic behavior.

## Recommended Sentinel Integration Order

1. Azure Functions + Azure VM traces (best autoscaling relevance)
2. Google ClusterData2019
3. Wikimedia pageviews (seasonality and external demand)
4. Alibaba v2018 / v2026-GenAI
5. MAWI + ITA as stress and robustness supplements

