"""
02_market_eda.py
================
Peterborough Restaurant Google Reviews — Market Exploratory Analysis
Phase 3 / Step 5 of the analytical pipeline.

This script covers all seven sub-steps:
  5A — Population and data coverage
  5B — Market-level rating analysis
  5C — Temporal analysis (volume + trend + seasonality + composition effect)
  5D — Restaurant benchmarking
  5E — Peer-group benchmarking
  5F — Review and engagement behaviour
  5G — Structured-context exploration (coverage-gated)

Two analytical populations are maintained throughout:
  Population A (rating_pop)  — all reviews with valid stars + date + restaurant_id
                                Used for: rating distribution, trends, benchmarking
  Population B (nlp_pop)     — nlp_eligible == 1
                                Used for: review length, text behaviour, NLP inputs

Two weighting schemes are applied wherever meaningful:
  Review-weighted  — each review has equal weight (n-driven)
  Restaurant-weighted — each restaurant has equal weight (structure-driven)

Outputs (written to OUT_DIR):
  Charts/          — PNG exports (Matplotlib, publication quality)
  eda_summary.xlsx — All tabular results, one sheet per sub-step
  02_market_eda.ipynb — Notebook with inline Plotly charts (generated at end)

Design rules enforced throughout:
  - Never rank restaurants below MIN_REVIEWS_RANK without a low-sample flag
  - Never plot a monthly trend point with fewer than MIN_REVIEWS_TREND reviews
  - All confidence intervals are 95% Wilson score (proportions) or t-CI (means)
  - Composition-effect check is always run alongside aggregate trend
  - Context metrics are suppressed when coverage < MIN_CONTEXT_COVERAGE
"""

import os
import json
import warnings
import textwrap
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd
import scipy.stats as stats
import matplotlib
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import seaborn as sns
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots

warnings.filterwarnings("ignore")
matplotlib.use("Agg")

# ─── Paths ────────────────────────────────────────────────────────────────────
# Workspace root (raw files + numbered output folders): set PTBO_BASE, or it defaults to the repository root.
PROJECT_DIR = os.environ.get("PTBO_BASE", os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
PARQUET = os.path.join(
    PROJECT_DIR,
    "02. Outputs_Data Mining",
    "reviews_analysis_ready.parquet"
)
OUT_DIR     = os.path.join(PROJECT_DIR, "03. Outputs_EDA")
CHART_DIR   = os.path.join(OUT_DIR, "Charts")
os.makedirs(CHART_DIR, exist_ok=True)

# ─── Analysis thresholds (documented, not arbitrary) ─────────────────────────
MIN_REVIEWS_RANK    = 30   # min reviews to include a restaurant in ranked comparisons
MIN_REVIEWS_TREND   = 10   # min reviews per month-point to plot a trend value
MIN_CONTEXT_COV     = 0.15 # min coverage fraction to report a context variable
ROLLING_WINDOW      = 3    # months for rolling average
CI_LEVEL            = 0.95 # confidence interval level
RECENT_MONTHS       = 12   # "recent" window in months

# ─── Colour palette (consistent across all charts) ───────────────────────────
COLORS = {
    "market"  : "#378ADD",
    "rw"      : "#1D9E75",   # review-weighted
    "restw"   : "#7F77DD",   # restaurant-weighted
    "positive": "#1D9E75",
    "neutral" : "#EF9F27",
    "negative": "#D85A30",
    "low_ci"  : "#B5D4F4",
    "peer_palette": px.colors.qualitative.Safe,
    "star_palette": ["#D85A30","#F0997B","#EF9F27","#9FE1CB","#1D9E75"],
}

PEER_ORDER = [
    "Fast Casual & Counter Service",
    "Breakfast, Diner & Family Casual",
    "Casual Full-Service Ethnic Dining",
    "Pub, Burger & Smokehouse Casual",
    "Premium Full-Service & Experience Dining",
]

# ─── Matplotlib style ─────────────────────────────────────────────────────────
plt.rcParams.update({
    "font.family"      : "DejaVu Sans",
    "font.size"        : 10,
    "axes.spines.top"  : False,
    "axes.spines.right": False,
    "axes.grid"        : True,
    "grid.alpha"       : 0.3,
    "grid.linestyle"   : "--",
    "figure.dpi"       : 150,
    "savefig.dpi"      : 150,
    "savefig.bbox"     : "tight",
    "savefig.facecolor": "white",
})

# ─── Helper utilities ─────────────────────────────────────────────────────────

def ci_mean(series, level=CI_LEVEL):
    """95% t-CI for the mean of a numeric series."""
    s = series.dropna()
    if len(s) < 2:
        return (np.nan, np.nan)
    se = stats.sem(s)
    h  = se * stats.t.ppf((1 + level) / 2, df=len(s) - 1)
    return (s.mean() - h, s.mean() + h)

def ci_proportion(k, n, level=CI_LEVEL):
    """95% Wilson score CI for a proportion (k successes out of n trials)."""
    if n == 0:
        return (0.0, 0.0)
    z  = stats.norm.ppf((1 + level) / 2)
    p  = k / n
    denom = 1 + z**2 / n
    centre = (p + z**2 / (2 * n)) / denom
    half   = z * np.sqrt(p * (1 - p) / n + z**2 / (4 * n**2)) / denom
    return (max(0, centre - half), min(1, centre + half))

def star_based_proxy(stars_series):
    """Return (positive_share, mid_share, negative_share) as fractions."""
    n = len(stars_series.dropna())
    if n == 0:
        return 0.0, 0.0, 0.0
    pos = (stars_series >= 4).sum() / n
    mid = (stars_series == 3).sum() / n
    neg = (stars_series <= 2).sum() / n
    return pos, mid, neg

def low_sample_flag(n, threshold=MIN_REVIEWS_RANK):
    return "⚠ low sample" if n < threshold else ""

def save_fig(fig, name, subdir=""):
    path = os.path.join(CHART_DIR, subdir, f"{name}.png")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    fig.savefig(path)
    plt.close(fig)
    return path

def section(title):
    print(f"\n{'═'*70}\n  {title}\n{'═'*70}")


# ════════════════════════════════════════════════════════════════════════════════
# LOAD DATA
# ════════════════════════════════════════════════════════════════════════════════

def load_data():
    print(f"Loading: {PARQUET}")
    df = pd.read_parquet(PARQUET)

    # Ensure datetime
    for col in ["published_at", "scraped_at", "owner_response_at"]:
        if col in df.columns:
            df[col] = pd.to_datetime(df[col], errors="coerce")

    # Derive published_year_month as Period for grouping
    df["pub_ym"] = pd.to_datetime(df["published_at"]).dt.to_period("M")
    df["pub_month_num"] = pd.to_datetime(df["published_at"]).dt.month   # 1–12 for seasonality

    # Population masks
    df["_pop_rating"] = (
        df["rating_analysis_eligible"].fillna(0) == 1
    )
    df["_pop_nlp"] = (
        df["nlp_eligible"].fillna(0) == 1
    )

    print(f"  Total rows       : {len(df):,}")
    print(f"  Population A (rating) : {df['_pop_rating'].sum():,}")
    print(f"  Population B (NLP)    : {df['_pop_nlp'].sum():,}")
    return df


# ════════════════════════════════════════════════════════════════════════════════
# 5A — POPULATION AND DATA COVERAGE
# ════════════════════════════════════════════════════════════════════════════════

def step_5a(df):
    section("5A — Population and Data Coverage")
    results = {}

    # ── 5A.1 Top-level population profile ────────────────────────────────────
    rp = df[df["_pop_rating"]]
    np_ = df[df["_pop_nlp"]]

    date_min = df["published_at"].min()
    date_max = df["published_at"].max()
    date_range_days = (date_max - date_min).days

    profile = {
        "Total reviews in dataset"         : len(df),
        "Rating population (Pop. A)"       : df["_pop_rating"].sum(),
        "NLP / text population (Pop. B)"   : df["_pop_nlp"].sum(),
        "Star-only reviews (no text)"      : int((df["has_text"].fillna(0) == 0).sum()),
        "Suspicious duplicates"            : int(df["suspicious_duplicate_flag"].fillna(0).sum()),
        "Restaurants"                      : df["restaurant_id"].nunique(),
        "Operational peer groups"          : df["operational_peer_group"].nunique(),
        "Earliest review"                  : str(date_min.date()),
        "Latest review"                    : str(date_max.date()),
        "Date range (days)"                : date_range_days,
        "Non-English reviews"              : int((df["is_english"].fillna(1) == 0).sum()),
        "Reviews with owner response"      : int(df["has_owner_response"].fillna(0).sum()),
        "Reviews with detailed ratings"    : int(df["has_detailed_rating"].fillna(0).sum()),
    }
    results["population_profile"] = pd.DataFrame(
        list(profile.items()), columns=["Metric", "Value"]
    )
    for k, v in profile.items():
        print(f"  {k:<45}: {v}")

    # ── 5A.2 Per-restaurant coverage table ───────────────────────────────────
    rest_cov = (
        df.groupby(["restaurant_id", "restaurant_name",
                    "operational_peer_group", "restaurant_report_status"])
        .agg(
            total_reviews        =("review_id",                "count"),
            rating_pop_reviews   =("_pop_rating",             "sum"),
            nlp_pop_reviews      =("_pop_nlp",                "sum"),
            star_only            =("has_text",
                                   lambda x: (x.fillna(0) == 0).sum()),
            suspicious_dups      =("suspicious_duplicate_flag",
                                   lambda x: x.fillna(0).sum()),
            avg_stars_all        =("review_stars",            "mean"),
            collection_coverage  =("collection_coverage",     "first"),
        )
        .round(3)
        .reset_index()
    )
    rest_cov["low_sample_flag"] = rest_cov["total_reviews"].apply(
        lambda n: low_sample_flag(n)
    )
    results["restaurant_coverage"] = rest_cov
    print(f"\n  Per-restaurant coverage table: {len(rest_cov)} restaurants")

    # ── 5A.3 Review concentration ─────────────────────────────────────────────
    vol_sorted = rest_cov.sort_values("total_reviews", ascending=False)
    vol_sorted["cumulative_reviews"] = vol_sorted["total_reviews"].cumsum()
    vol_sorted["cumulative_share"]   = vol_sorted["cumulative_reviews"] / vol_sorted["total_reviews"].sum()
    vol_sorted["review_share"]       = vol_sorted["total_reviews"] / vol_sorted["total_reviews"].sum()
    top5_share = vol_sorted.head(5)["total_reviews"].sum() / vol_sorted["total_reviews"].sum()
    results["concentration"] = vol_sorted[
        ["restaurant_name", "total_reviews", "review_share", "cumulative_share"]
    ]
    print(f"\n  Top-5 restaurant review concentration: {top5_share:.1%}")

    # ── 5A.4 Missing-data coverage ────────────────────────────────────────────
    key_cols = [
        "review_stars", "published_at", "review_text_raw",
        "language_final", "restaurant_id",
        "context_meal_type", "context_wait_time", "context_price_per_person",
        "context_order_type", "context_noise_level",
        "detailed_rating_food", "detailed_rating_service", "detailed_rating_atmosphere",
        "has_owner_response", "is_local_guide", "reviewer_number_of_reviews",
    ]
    missing = []
    for col in key_cols:
        if col in df.columns:
            n_total   = len(df)
            n_present = df[col].notna().sum()
            # For binary flags stored as Int64, also count non-null 0s as present
            missing.append({
                "Column"          : col,
                "N present"       : int(n_present),
                "N missing"       : int(n_total - n_present),
                "Coverage %"      : round(n_present / n_total * 100, 1),
                "Usable for EDA?" : "Yes" if n_present / n_total >= MIN_CONTEXT_COV else "Low coverage",
            })
    results["missing_data"] = pd.DataFrame(missing)
    print(f"\n  Missing-data coverage computed for {len(missing)} columns")

    # ── 5A.5 CHARTS ──────────────────────────────────────────────────────────

    # Chart 5A-1: Population funnel
    fig, ax = plt.subplots(figsize=(7, 4))
    funnel_labels = [
        "All reviews\n(7,073)",
        "Rating pop. A\n(valid stars+date)",
        "Text reviews\n(has_text=1)",
        "NLP pop. B\n(nlp_eligible=1)",
        "Gold annotation\neligible",
    ]
    funnel_vals = [
        len(df),
        int(df["_pop_rating"].sum()),
        int(df["has_text"].fillna(0).sum()),
        int(df["_pop_nlp"].sum()),
        int(df["gold_annotation_eligible"].fillna(0).sum()),
    ]
    colors_funnel = ["#B5D4F4","#85B7EB","#378ADD","#1D9E75","#0F6E56"]
    bars = ax.barh(range(len(funnel_labels)), funnel_vals,
                   color=colors_funnel, height=0.6, edgecolor="white")
    ax.set_yticks(range(len(funnel_labels)))
    ax.set_yticklabels(funnel_labels, fontsize=9)
    ax.invert_yaxis()
    ax.set_xlabel("Number of reviews")
    ax.set_title("Review population funnel", fontweight="bold", pad=10)
    for bar, val in zip(bars, funnel_vals):
        ax.text(bar.get_width() + 30, bar.get_y() + bar.get_height()/2,
                f"{val:,}", va="center", fontsize=9)
    ax.set_xlim(0, max(funnel_vals) * 1.15)
    save_fig(fig, "5A1_population_funnel", "5A")

    # Chart 5A-2: Review volume per restaurant (sorted)
    fig, ax = plt.subplots(figsize=(9, 6))
    vol_plot = vol_sorted.iloc[::-1]  # ascending for horizontal bar
    bar_colors = ["#D85A30" if n < MIN_REVIEWS_RANK else COLORS["market"]
                  for n in vol_plot["total_reviews"]]
    ax.barh(range(len(vol_plot)), vol_plot["total_reviews"],
            color=bar_colors, height=0.7, edgecolor="white")
    ax.set_yticks(range(len(vol_plot)))
    ax.set_yticklabels(
        [n[:30] for n in vol_plot["restaurant_name"]], fontsize=8
    )
    ax.axvline(MIN_REVIEWS_RANK, color="#D85A30", lw=1.2,
               linestyle="--", label=f"Min rank threshold ({MIN_REVIEWS_RANK})")
    ax.set_xlabel("Number of reviews")
    ax.set_title("Review volume per restaurant\n(red = below minimum threshold for ranking)",
                 fontweight="bold", pad=10)
    ax.legend(fontsize=8)
    save_fig(fig, "5A2_volume_per_restaurant", "5A")

    # Chart 5A-3: Cumulative share (Lorenz-style)
    fig, ax = plt.subplots(figsize=(7, 4))
    x = range(1, len(vol_sorted) + 1)
    ax.fill_between(x, vol_sorted["cumulative_share"].values,
                    alpha=0.25, color=COLORS["market"])
    ax.plot(x, vol_sorted["cumulative_share"].values,
            color=COLORS["market"], lw=2)
    ax.axhline(0.5, color="gray", lw=0.8, linestyle="--", label="50% of reviews")
    ax.set_xticks(x)
    ax.set_xticklabels(
        [n[:12] for n in vol_sorted["restaurant_name"]], rotation=45, ha="right", fontsize=7
    )
    ax.set_ylabel("Cumulative share of reviews")
    ax.set_title(f"Review concentration — top 5 restaurants account for {top5_share:.0%}",
                 fontweight="bold", pad=10)
    ax.yaxis.set_major_formatter(mticker.PercentFormatter(1.0))
    ax.legend(fontsize=8)
    save_fig(fig, "5A3_review_concentration", "5A")

    # Chart 5A-4: Coverage heatmap for key fields
    coverage_plot = results["missing_data"].set_index("Column")["Coverage %"]
    fig, ax = plt.subplots(figsize=(8, 5))
    bar_colors_cov = [
        "#1D9E75" if v >= 90 else
        "#EF9F27" if v >= MIN_CONTEXT_COV * 100 else
        "#D85A30"
        for v in coverage_plot.values
    ]
    ax.barh(range(len(coverage_plot)), coverage_plot.values,
            color=bar_colors_cov, height=0.7)
    ax.set_yticks(range(len(coverage_plot)))
    ax.set_yticklabels(coverage_plot.index, fontsize=8)
    ax.set_xlabel("Coverage (%)")
    ax.axvline(MIN_CONTEXT_COV * 100, color="#D85A30", lw=1.2, linestyle="--",
               label=f"Min threshold ({MIN_CONTEXT_COV:.0%})")
    ax.axvline(90, color="#1D9E75", lw=1.2, linestyle="--", label="90% coverage")
    ax.set_title("Field coverage — key analytical columns", fontweight="bold", pad=10)
    ax.legend(fontsize=8)
    save_fig(fig, "5A4_field_coverage", "5A")

    print(f"\n  [5A] Charts saved to {CHART_DIR}/5A/")
    return results


# ════════════════════════════════════════════════════════════════════════════════
# 5B — MARKET-LEVEL RATING ANALYSIS
# ════════════════════════════════════════════════════════════════════════════════

def step_5b(df):
    section("5B — Market-Level Rating Analysis")
    results = {}
    rp = df[df["_pop_rating"]].copy()

    # ── 5B.1 Overall distribution ─────────────────────────────────────────────
    star_counts = rp["review_stars"].value_counts().sort_index()
    star_pct    = (star_counts / star_counts.sum() * 100).round(2)
    pos, mid, neg = star_based_proxy(rp["review_stars"])

    # ── 5B.2 Review-weighted vs restaurant-weighted rating ────────────────────
    rw_mean   = rp["review_stars"].mean()
    rw_median = rp["review_stars"].median()
    rw_std    = rp["review_stars"].std()
    rw_ci     = ci_mean(rp["review_stars"])

    rest_means = rp.groupby("restaurant_id")["review_stars"].mean()
    restw_mean   = rest_means.mean()
    restw_median = rest_means.median()
    restw_std    = rest_means.std()
    restw_ci     = ci_mean(rest_means)

    # ── 5B.3 Polarization ────────────────────────────────────────────────────
    polar_share = star_pct.get(1, 0) + star_pct.get(5, 0)  # % 1-star + % 5-star
    iqr = rp["review_stars"].quantile(0.75) - rp["review_stars"].quantile(0.25)

    # ── 5B.4 Recent vs historical ─────────────────────────────────────────────
    cutoff = rp["published_at"].max() - pd.DateOffset(months=RECENT_MONTHS)
    recent = rp[rp["published_at"] >= cutoff]
    hist   = rp[rp["published_at"] <  cutoff]

    summary = {
        "Review-weighted mean rating"      : round(rw_mean, 3),
        "Review-weighted median"           : round(rw_median, 2),
        "Review-weighted std dev"          : round(rw_std, 3),
        "Review-weighted 95% CI lower"     : round(rw_ci[0], 3),
        "Review-weighted 95% CI upper"     : round(rw_ci[1], 3),
        "Restaurant-weighted mean rating"  : round(restw_mean, 3),
        "Restaurant-weighted median"       : round(restw_median, 2),
        "Restaurant-weighted std dev"      : round(restw_std, 3),
        "Restaurant-weighted 95% CI lower" : round(restw_ci[0], 3),
        "Restaurant-weighted 95% CI upper" : round(restw_ci[1], 3),
        "Positive-rating share (4–5★)"     : round(pos * 100, 1),
        "Mid-rating share (3★)"            : round(mid * 100, 1),
        "Negative-rating share (1–2★)"     : round(neg * 100, 1),
        "Polarization score (1★+5★ share)" : round(polar_share, 1),
        "IQR"                              : round(iqr, 2),
        "All-time reviews in Pop. A"       : len(rp),
        f"Recent {RECENT_MONTHS}M mean"    : round(recent["review_stars"].mean(), 3),
        f"Historical (pre-{RECENT_MONTHS}M) mean": round(hist["review_stars"].mean(), 3) if len(hist) else None,
        f"Rating change (recent vs hist)"  : round(
            recent["review_stars"].mean() - hist["review_stars"].mean(), 3
        ) if len(hist) else None,
    }
    results["market_summary"] = pd.DataFrame(
        list(summary.items()), columns=["Metric", "Value"]
    )
    for k, v in summary.items():
        print(f"  {k:<50}: {v}")

    # ── 5B.5 Positive/negative per-restaurant (with CI) ───────────────────────
    rest_rating_summary = []
    for rid, grp in rp.groupby("restaurant_id"):
        n = len(grp)
        pos_k = (grp["review_stars"] >= 4).sum()
        neg_k = (grp["review_stars"] <= 2).sum()
        pos_ci = ci_proportion(pos_k, n)
        neg_ci = ci_proportion(neg_k, n)
        rest_rating_summary.append({
            "restaurant_id"       : rid,
            "restaurant_name"     : grp["restaurant_name"].iloc[0],
            "operational_peer_group": grp["operational_peer_group"].iloc[0],
            "n_reviews"           : n,
            "mean_stars"          : round(grp["review_stars"].mean(), 3),
            "median_stars"        : grp["review_stars"].median(),
            "std_stars"           : round(grp["review_stars"].std(), 3),
            "positive_share"      : round(pos_k / n * 100, 1),
            "pos_ci_lo"           : round(pos_ci[0] * 100, 1),
            "pos_ci_hi"           : round(pos_ci[1] * 100, 1),
            "negative_share"      : round(neg_k / n * 100, 1),
            "neg_ci_lo"           : round(neg_ci[0] * 100, 1),
            "neg_ci_hi"           : round(neg_ci[1] * 100, 1),
            "low_sample"          : n < MIN_REVIEWS_RANK,
        })
    rest_ratings = pd.DataFrame(rest_rating_summary).sort_values("mean_stars", ascending=False)
    results["restaurant_rating_summary"] = rest_ratings

    # ── 5B.6 CHARTS ──────────────────────────────────────────────────────────

    # Chart 5B-1: Overall star distribution
    fig, axes = plt.subplots(1, 2, figsize=(12, 4))
    ax = axes[0]
    ax.bar(star_counts.index, star_counts.values,
           color=COLORS["star_palette"], edgecolor="white", width=0.7)
    ax.set_xticks([1,2,3,4,5])
    ax.set_xlabel("Star rating")
    ax.set_ylabel("Number of reviews")
    ax.set_title("Star distribution — Population A\n(rating-eligible reviews)",
                 fontweight="bold")
    for x, y, pct in zip(star_counts.index, star_counts.values, star_pct.values):
        ax.text(x, y + 30, f"{pct:.1f}%", ha="center", fontsize=9)

    ax2 = axes[1]
    shares = [pos * 100, mid * 100, neg * 100]
    labels = [f"Positive\n(4–5★)\n{pos:.1%}", f"Mid\n(3★)\n{mid:.1%}", f"Negative\n(1–2★)\n{neg:.1%}"]
    colors_pgn = [COLORS["positive"], COLORS["neutral"], COLORS["negative"]]
    wedges, _ = ax2.pie(shares, colors=colors_pgn, startangle=90,
                        wedgeprops={"edgecolor":"white","linewidth":2})
    ax2.legend(wedges, labels, loc="lower center", fontsize=9,
               bbox_to_anchor=(0.5, -0.15), ncol=3)
    ax2.set_title("Star-based rating proxy\n(positive / mid / negative)",
                  fontweight="bold")
    plt.tight_layout()
    save_fig(fig, "5B1_star_distribution", "5B")

    # Chart 5B-2: Review-weighted vs restaurant-weighted with CI
    fig, ax = plt.subplots(figsize=(6, 4))
    labels_b2 = ["Review-weighted", "Restaurant-weighted"]
    means_b2  = [rw_mean, restw_mean]
    cis_b2    = [rw_ci,   restw_ci]
    colors_b2 = [COLORS["rw"], COLORS["restw"]]
    x_pos = [0, 1]
    for i, (lbl, m, ci, col) in enumerate(zip(labels_b2, means_b2, cis_b2, colors_b2)):
        ax.bar(i, m, color=col, width=0.5, label=lbl, edgecolor="white")
        ax.errorbar(i, m, yerr=[[m - ci[0]], [ci[1] - m]],
                    fmt="none", color="black", capsize=5, lw=1.5)
        ax.text(i, ci[1] + 0.02, f"{m:.3f}", ha="center", fontsize=10, fontweight="bold")
    ax.set_xticks(x_pos)
    ax.set_xticklabels(labels_b2)
    ax.set_ylabel("Mean star rating")
    ax.set_ylim(3.5, 5.1)
    ax.set_title("Review-weighted vs restaurant-weighted mean rating\n(with 95% confidence intervals)",
                 fontweight="bold")
    diff = abs(rw_mean - restw_mean)
    ax.text(0.5, 3.6, f"Difference: {diff:.3f} stars", ha="center", fontsize=9,
            style="italic", color="gray", transform=ax.transData)
    save_fig(fig, "5B2_rw_vs_restw", "5B")

    # Chart 5B-3: Restaurant rating ranked with CI error bars
    rs = rest_ratings.sort_values("mean_stars", ascending=True)
    fig, ax = plt.subplots(figsize=(9, 7))
    bar_colors_r = ["#D85A30" if lsamp else COLORS["market"]
                    for lsamp in rs["low_sample"]]
    y_pos = range(len(rs))
    ax.barh(y_pos, rs["mean_stars"], color=bar_colors_r, height=0.6)
    ax.axvline(rw_mean, color=COLORS["rw"], lw=1.5, linestyle="--",
               label=f"Market avg (RW) {rw_mean:.2f}★")
    ax.axvline(restw_mean, color=COLORS["restw"], lw=1.5, linestyle="--",
               label=f"Market avg (RestW) {restw_mean:.2f}★")
    ax.set_yticks(y_pos)
    ax.set_yticklabels(
        [f"{r} (n={n}{'⚠' if lsamp else ''})"
         for r, n, lsamp in zip(rs["restaurant_name"], rs["n_reviews"], rs["low_sample"])],
        fontsize=8
    )
    ax.set_xlabel("Mean star rating")
    ax.set_xlim(2.5, 5.3)
    ax.set_title("Restaurant ranking by mean rating\n(⚠ = below minimum sample threshold)",
                 fontweight="bold")
    ax.legend(fontsize=8)
    save_fig(fig, "5B3_restaurant_ranking", "5B")

    # Chart 5B-4: Positive/negative share per restaurant (stacked bar)
    rs2 = rest_ratings.sort_values("positive_share", ascending=True)
    fig, ax = plt.subplots(figsize=(9, 7))
    y = range(len(rs2))
    ax.barh(y, rs2["positive_share"], color=COLORS["positive"],
            height=0.6, label="Positive (4–5★)")
    ax.barh(y, rs2["negative_share"],
            left=100 - rs2["negative_share"],
            color=COLORS["negative"], height=0.6, label="Negative (1–2★)")
    ax.set_yticks(y)
    ax.set_yticklabels([r[:28] for r in rs2["restaurant_name"]], fontsize=8)
    ax.set_xlabel("Share of reviews (%)")
    ax.set_title("Positive vs negative rating share per restaurant\n(star-based proxy — not model sentiment)",
                 fontweight="bold")
    ax.legend(fontsize=8)
    save_fig(fig, "5B4_positive_negative_share", "5B")

    print(f"\n  [5B] Charts saved.")
    return results


# ════════════════════════════════════════════════════════════════════════════════
# 5C — TEMPORAL ANALYSIS
# ════════════════════════════════════════════════════════════════════════════════

def step_5c(df):
    section("5C — Temporal Analysis")
    results = {}
    rp = df[df["_pop_rating"]].copy()
    rp["pub_ym_str"] = rp["pub_ym"].astype(str)

    # ── 5C.1 Monthly volume ───────────────────────────────────────────────────
    monthly_vol = (
        rp.groupby("pub_ym_str")
        .agg(n_reviews=("review_id", "count"),
             n_restaurants=("restaurant_id", "nunique"))
        .reset_index()
    )

    # ── 5C.2 Monthly rating (review-weighted) ─────────────────────────────────
    monthly_rw = (
        rp.groupby("pub_ym_str")["review_stars"]
        .agg(mean="mean", n="count")
        .reset_index()
    )
    monthly_rw["plot"] = monthly_rw["n"] >= MIN_REVIEWS_TREND
    monthly_rw["rolling_mean"] = (
        monthly_rw["mean"]
        .rolling(window=ROLLING_WINDOW, min_periods=1)
        .mean()
    )

    # ── 5C.3 Restaurant-weighted monthly rating (composition control) ─────────
    monthly_restw = (
        rp.groupby(["pub_ym_str", "restaurant_id"])["review_stars"].mean()
        .groupby(level=0)
        .mean()
        .reset_index()
        .rename(columns={"review_stars": "restw_mean"})
    )
    monthly_restw["restw_rolling"] = (
        monthly_restw["restw_mean"]
        .rolling(window=ROLLING_WINDOW, min_periods=1)
        .mean()
    )

    monthly = monthly_vol.merge(monthly_rw, on="pub_ym_str", how="left")
    monthly = monthly.merge(monthly_restw, on="pub_ym_str", how="left")
    results["monthly_trend"] = monthly

    # ── 5C.4 Year-over-year ───────────────────────────────────────────────────
    yoy = (
        rp.groupby("review_year")["review_stars"]
        .agg(mean="mean", n="count", std="std")
        .reset_index()
    )
    yoy["ci_lo"] = yoy.apply(lambda r: ci_mean(
        rp[rp["review_year"] == r["review_year"]]["review_stars"])[0], axis=1)
    yoy["ci_hi"] = yoy.apply(lambda r: ci_mean(
        rp[rp["review_year"] == r["review_year"]]["review_stars"])[1], axis=1)
    results["year_over_year"] = yoy

    # ── 5C.5 Seasonality (month-of-year) ─────────────────────────────────────
    seasonal = (
        rp.groupby("pub_month_num")["review_stars"]
        .agg(mean="mean", n="count")
        .reset_index()
    )
    month_names = {1:"Jan",2:"Feb",3:"Mar",4:"Apr",5:"May",6:"Jun",
                   7:"Jul",8:"Aug",9:"Sep",10:"Oct",11:"Nov",12:"Dec"}
    seasonal["month_label"] = seasonal["pub_month_num"].map(month_names)
    results["seasonality"] = seasonal

    # ── 5C.6 CHARTS ──────────────────────────────────────────────────────────

    # Chart 5C-1: Monthly volume
    fig, ax = plt.subplots(figsize=(12, 4))
    x = range(len(monthly))
    ax.bar(x, monthly["n_reviews"], color=COLORS["low_ci"], label="Monthly reviews")
    ax.plot(x, monthly["n_reviews"].rolling(3, min_periods=1).mean(),
            color=COLORS["market"], lw=2, label="3-month rolling avg")
    step_x = max(1, len(monthly) // 12)
    ax.set_xticks(list(range(0, len(monthly), step_x)))
    ax.set_xticklabels(
        monthly["pub_ym_str"].iloc[::step_x].tolist(), rotation=45, ha="right", fontsize=7
    )
    ax.set_ylabel("Number of reviews")
    ax.set_title("Monthly review volume — observed sample (Population A)",
                 fontweight="bold")
    ax.legend(fontsize=8)
    save_fig(fig, "5C1_monthly_volume", "5C")

    # Chart 5C-2: Rating trend — RW vs RestW with rolling
    plotable = monthly[monthly["plot"].fillna(False)].copy()
    fig, ax = plt.subplots(figsize=(12, 4))
    x2 = range(len(plotable))
    ax.plot(x2, plotable["mean"], color=COLORS["rw"], lw=1,
            alpha=0.5, linestyle="--", label="Monthly avg (RW)")
    ax.plot(x2, plotable["rolling_mean"], color=COLORS["rw"], lw=2,
            label=f"{ROLLING_WINDOW}M rolling avg (RW)")
    ax.plot(x2, plotable["restw_mean"], color=COLORS["restw"], lw=1,
            alpha=0.5, linestyle="--", label="Monthly avg (RestW)")
    ax.plot(x2, plotable["restw_rolling"], color=COLORS["restw"], lw=2,
            label=f"{ROLLING_WINDOW}M rolling avg (RestW)")
    step_x2 = max(1, len(plotable) // 10)
    ax.set_xticks(list(range(0, len(plotable), step_x2)))
    ax.set_xticklabels(
        plotable["pub_ym_str"].iloc[::step_x2].tolist(), rotation=45, ha="right", fontsize=7
    )
    ax.set_ylabel("Mean star rating")
    ax.set_ylim(3.0, 5.5)
    ax.set_title(
        "Rating trend — review-weighted vs restaurant-weighted\n"
        f"(points with n<{MIN_REVIEWS_TREND} excluded; divergence = composition effect)",
        fontweight="bold"
    )
    ax.legend(fontsize=8, loc="lower left")
    save_fig(fig, "5C2_rating_trend_rw_vs_restw", "5C")

    # Chart 5C-3: YoY bar with error bars
    fig, ax = plt.subplots(figsize=(8, 4))
    yr_valid = yoy[yoy["n"] >= MIN_REVIEWS_TREND]
    x3 = range(len(yr_valid))
    ax.bar(x3, yr_valid["mean"], color=COLORS["market"], width=0.6)
    ax.errorbar(x3, yr_valid["mean"],
                yerr=[yr_valid["mean"] - yr_valid["ci_lo"],
                      yr_valid["ci_hi"] - yr_valid["mean"]],
                fmt="none", color="black", capsize=5, lw=1.5)
    ax.set_xticks(x3)
    ax.set_xticklabels(yr_valid["review_year"].astype(int), fontsize=9)
    for i, (m, n_) in enumerate(zip(yr_valid["mean"], yr_valid["n"])):
        ax.text(i, m + 0.03, f"{m:.2f}\n(n={n_:,})", ha="center", fontsize=8)
    ax.set_ylabel("Mean star rating")
    ax.set_ylim(3.0, 5.5)
    ax.set_title("Year-over-year mean rating with 95% CI", fontweight="bold")
    save_fig(fig, "5C3_year_over_year", "5C")

    # Chart 5C-4: Seasonality
    fig, ax = plt.subplots(figsize=(9, 4))
    ax.bar(range(len(seasonal)), seasonal["mean"],
           color=COLORS["market"], width=0.7)
    ax.plot(range(len(seasonal)), seasonal["mean"],
            color=COLORS["restw"], lw=2, marker="o", ms=5)
    ax.set_xticks(range(len(seasonal)))
    ax.set_xticklabels(seasonal["month_label"].tolist(), fontsize=9)
    ax.set_ylabel("Mean star rating")
    ax.set_ylim(3.5, 5.2)
    ax2_twin = ax.twinx()
    ax2_twin.bar(range(len(seasonal)), seasonal["n"],
                 color="#D3D1C7", width=0.7, alpha=0.4, label="Review volume")
    ax2_twin.set_ylabel("Review volume", color="#888780")
    ax.set_title("Seasonality — average rating and review volume by month of year",
                 fontweight="bold")
    save_fig(fig, "5C4_seasonality", "5C")

    print(f"\n  [5C] Charts saved.")
    return results


# ════════════════════════════════════════════════════════════════════════════════
# 5D — RESTAURANT BENCHMARKING
# ════════════════════════════════════════════════════════════════════════════════

def step_5d(df):
    section("5D — Restaurant Benchmarking")
    results = {}
    rp = df[df["_pop_rating"]].copy()

    rw_mean   = rp["review_stars"].mean()
    cutoff    = rp["published_at"].max() - pd.DateOffset(months=RECENT_MONTHS)

    bench_rows = []
    for rid, grp in rp.groupby("restaurant_id"):
        n = len(grp)
        recent_grp = grp[grp["published_at"] >= cutoff]
        hist_grp   = grp[grp["published_at"] <  cutoff]
        mean_all   = grp["review_stars"].mean()
        mean_rec   = recent_grp["review_stars"].mean() if len(recent_grp) >= 5 else np.nan
        mean_hist  = hist_grp["review_stars"].mean() if len(hist_grp) >= 5 else np.nan
        ci_lo, ci_hi = ci_mean(grp["review_stars"])
        pos_k = (grp["review_stars"] >= 4).sum()

        # Monthly volatility (std of monthly means)
        monthly_means = grp.groupby(grp["pub_ym"].astype(str))["review_stars"].mean()
        volatility    = monthly_means.std() if len(monthly_means) >= 3 else np.nan

        # Max rating decline (worst consecutive-month drop)
        diffs = monthly_means.diff().dropna()
        max_decline = diffs.min() if len(diffs) else np.nan

        bench_rows.append({
            "restaurant_id"           : rid,
            "restaurant_name"         : grp["restaurant_name"].iloc[0],
            "operational_peer_group"  : grp["operational_peer_group"].iloc[0],
            "cuisine_cluster"         : grp["cuisine_cluster"].iloc[0],
            "n_reviews"               : n,
            "mean_stars_all"          : round(mean_all, 3),
            "ci_lo"                   : round(ci_lo, 3),
            "ci_hi"                   : round(ci_hi, 3),
            "vs_market_mean"          : round(mean_all - rw_mean, 3),
            "mean_stars_recent"       : round(mean_rec, 3) if not np.isnan(mean_rec) else None,
            "mean_stars_historical"   : round(mean_hist, 3) if not np.isnan(mean_hist) else None,
            "rating_change_recent_vs_hist": round(mean_rec - mean_hist, 3)
                                          if not (np.isnan(mean_rec) or np.isnan(mean_hist)) else None,
            "positive_share_pct"      : round(pos_k / n * 100, 1),
            "rating_volatility"       : round(volatility, 3) if not np.isnan(volatility) else None,
            "max_monthly_decline"     : round(max_decline, 3) if not np.isnan(max_decline) else None,
            "low_sample_flag"         : n < MIN_REVIEWS_RANK,
        })

    bench = pd.DataFrame(bench_rows).sort_values("mean_stars_all", ascending=False)
    results["restaurant_benchmark"] = bench

    # ── 5D.1 CHARTS ──────────────────────────────────────────────────────────

    # Chart 5D-1: Rating vs volume scatter (the 2×2 quadrant chart)
    fig, ax = plt.subplots(figsize=(10, 7))
    peer_groups = bench["operational_peer_group"].unique()
    MPL_PEER_PALETTE = ["#1D9E75","#7F77DD","#D85A30","#BA7517","#378ADD","#993556","#3B6D11","#185FA5","#993C1D","#0F6E56"]
    peer_colors = {pg: MPL_PEER_PALETTE[i % len(MPL_PEER_PALETTE)]
                   for i, pg in enumerate(peer_groups)}
    for _, row in bench.iterrows():
        col = peer_colors.get(row["operational_peer_group"], "gray")
        marker = "^" if row["low_sample_flag"] else "o"
        ax.scatter(row["n_reviews"], row["mean_stars_all"],
                   color=col, s=80, marker=marker, zorder=3, alpha=0.9)
        ax.annotate(row["restaurant_name"][:16],
                    (row["n_reviews"], row["mean_stars_all"]),
                    textcoords="offset points", xytext=(5, 3), fontsize=6.5)
    ax.axhline(rw_mean, color=COLORS["rw"], lw=1.2, linestyle="--",
               label=f"Market avg {rw_mean:.2f}★")
    ax.axvline(bench["n_reviews"].median(), color="gray", lw=1, linestyle=":",
               label="Median volume")
    ax.set_xlabel("Number of reviews (volume)")
    ax.set_ylabel("Mean star rating")
    ax.set_title("Rating vs review volume — restaurant benchmarking\n"
                 "(△ = low sample; colour = peer group; quadrants guide interpretation)",
                 fontweight="bold")
    from matplotlib.lines import Line2D
    legend_handles = [
        Line2D([0],[0], marker="o", color="w", markerfacecolor=peer_colors[pg],
               markersize=8, label=pg[:35]) for pg in peer_groups
    ] + [
        Line2D([0],[0], marker="^", color="gray", lw=0, markersize=8,
               label=f"Low sample (<{MIN_REVIEWS_RANK})"),
    ]
    ax.legend(handles=legend_handles, fontsize=7, loc="lower right")

    # Quadrant shading
    med_vol  = bench["n_reviews"].median()
    ax.fill_between([med_vol, bench["n_reviews"].max()*1.1], rw_mean, 5.3,
                    alpha=0.04, color=COLORS["positive"])
    ax.fill_between([0, med_vol], 0, rw_mean, alpha=0.04, color=COLORS["negative"])
    ax.text(bench["n_reviews"].max()*0.55, 5.15, "Strong performers",
            fontsize=7, color=COLORS["positive"], style="italic")
    ax.text(20, rw_mean - 0.25, "Priority improvement",
            fontsize=7, color=COLORS["negative"], style="italic")
    save_fig(fig, "5D1_rating_vs_volume_scatter", "5D")

    # Chart 5D-2: Recent vs historical rating change
    ch = bench.dropna(subset=["rating_change_recent_vs_hist"]).copy()
    ch = ch.sort_values("rating_change_recent_vs_hist")
    fig, ax = plt.subplots(figsize=(9, 6))
    bar_colors_ch = [COLORS["positive"] if v >= 0 else COLORS["negative"]
                     for v in ch["rating_change_recent_vs_hist"]]
    ax.barh(range(len(ch)), ch["rating_change_recent_vs_hist"],
            color=bar_colors_ch, height=0.6)
    ax.axvline(0, color="black", lw=0.8)
    ax.set_yticks(range(len(ch)))
    ax.set_yticklabels([r[:28] for r in ch["restaurant_name"]], fontsize=8)
    ax.set_xlabel(f"Rating change (last {RECENT_MONTHS}M vs prior)")
    ax.set_title(f"Recent vs historical rating — change in mean stars\n"
                 f"(positive = improving; negative = declining)",
                 fontweight="bold")
    save_fig(fig, "5D2_recent_vs_historical", "5D")

    # Chart 5D-3: Volatility
    vol_ch = bench.dropna(subset=["rating_volatility"]).sort_values("rating_volatility")
    fig, ax = plt.subplots(figsize=(9, 6))
    ax.barh(range(len(vol_ch)), vol_ch["rating_volatility"],
            color=COLORS["market"], height=0.6)
    ax.set_yticks(range(len(vol_ch)))
    ax.set_yticklabels([r[:28] for r in vol_ch["restaurant_name"]], fontsize=8)
    ax.set_xlabel("Rating volatility (std dev of monthly means)")
    ax.set_title("Rating stability per restaurant\n(higher = more volatile month-to-month)",
                 fontweight="bold")
    save_fig(fig, "5D3_rating_volatility", "5D")

    print(f"\n  [5D] Charts saved.")
    return results


# ════════════════════════════════════════════════════════════════════════════════
# 5E — PEER-GROUP BENCHMARKING
# ════════════════════════════════════════════════════════════════════════════════

def step_5e(df):
    section("5E — Peer-Group Benchmarking")
    results = {}
    rp = df[df["_pop_rating"]].copy()

    # ── 5E.1 Peer-group aggregate metrics ────────────────────────────────────
    peer_rows = []
    for pg, grp in rp.groupby("operational_peer_group"):
        n_rest = grp["restaurant_id"].nunique()
        n_rev  = len(grp)
        rw_m   = grp["review_stars"].mean()
        rest_m_series = grp.groupby("restaurant_id")["review_stars"].mean()
        rw_ci  = ci_mean(grp["review_stars"])
        restw_m = rest_m_series.mean()
        restw_ci = ci_mean(rest_m_series)
        pos_k  = (grp["review_stars"] >= 4).sum()
        neg_k  = (grp["review_stars"] <= 2).sum()
        peer_rows.append({
            "peer_group"               : pg,
            "n_restaurants"            : n_rest,
            "n_reviews"                : n_rev,
            "rw_mean"                  : round(rw_m, 3),
            "rw_ci_lo"                 : round(rw_ci[0], 3),
            "rw_ci_hi"                 : round(rw_ci[1], 3),
            "restw_mean"               : round(restw_m, 3),
            "restw_ci_lo"              : round(restw_ci[0], 3),
            "restw_ci_hi"              : round(restw_ci[1], 3),
            "median_restaurant_rating" : round(rest_m_series.median(), 3),
            "within_group_std"         : round(rest_m_series.std(), 3),
            "positive_share_pct"       : round(pos_k / n_rev * 100, 1),
            "negative_share_pct"       : round(neg_k / n_rev * 100, 1),
            "caution_flag"             : "⚠ n<3 restaurants" if n_rest < 3 else "",
        })
    peer_df = pd.DataFrame(peer_rows)
    # Order by PEER_ORDER if possible
    pg_order = [p for p in PEER_ORDER if p in peer_df["peer_group"].values]
    peer_df["_order"] = peer_df["peer_group"].apply(
        lambda x: pg_order.index(x) if x in pg_order else 99
    )
    peer_df = peer_df.sort_values("_order").drop(columns="_order")
    results["peer_group_summary"] = peer_df

    # ── 5E.2 CHARTS ──────────────────────────────────────────────────────────

    # Chart 5E-1: Peer-group rating comparison (RW + RestW) with CI
    fig, ax = plt.subplots(figsize=(11, 5))
    x4 = np.arange(len(peer_df))
    width = 0.35
    bars_rw = ax.bar(x4 - width/2, peer_df["rw_mean"],
                     width=width, color=COLORS["rw"], label="Review-weighted")
    bars_restw = ax.bar(x4 + width/2, peer_df["restw_mean"],
                        width=width, color=COLORS["restw"], label="Restaurant-weighted")
    ax.errorbar(x4 - width/2, peer_df["rw_mean"],
                yerr=[peer_df["rw_mean"] - peer_df["rw_ci_lo"],
                      peer_df["rw_ci_hi"] - peer_df["rw_mean"]],
                fmt="none", color="black", capsize=4, lw=1.2)
    ax.errorbar(x4 + width/2, peer_df["restw_mean"],
                yerr=[peer_df["restw_mean"] - peer_df["restw_ci_lo"],
                      peer_df["restw_ci_hi"] - peer_df["restw_mean"]],
                fmt="none", color="black", capsize=4, lw=1.2)
    for i, row in peer_df.iterrows():
        if row["caution_flag"]:
            ax.text(list(peer_df.index).index(i), row["rw_mean"] + 0.1,
                    "⚠", fontsize=10, ha="center", color="#D85A30")
    ax.set_xticks(x4)
    ax.set_xticklabels(
        [textwrap.fill(pg, 20) for pg in peer_df["peer_group"]], fontsize=8
    )
    ax.set_ylabel("Mean star rating")
    ax.set_ylim(3.5, 5.4)
    ax.set_title("Peer-group mean rating — review-weighted vs restaurant-weighted\n"
                 "(with 95% CI; ⚠ = interpret with caution: <3 restaurants)",
                 fontweight="bold")
    ax.legend(fontsize=9)
    save_fig(fig, "5E1_peer_group_comparison", "5E")

    # Chart 5E-2: Positive/negative share by peer group
    fig, ax = plt.subplots(figsize=(10, 5))
    x5 = np.arange(len(peer_df))
    ax.bar(x5, peer_df["positive_share_pct"], color=COLORS["positive"],
           label="Positive (4–5★)", width=0.6)
    ax.bar(x5, peer_df["negative_share_pct"], bottom=100 - peer_df["negative_share_pct"],
           color=COLORS["negative"], label="Negative (1–2★)", width=0.6)
    ax.set_xticks(x5)
    ax.set_xticklabels(
        [textwrap.fill(pg, 20) for pg in peer_df["peer_group"]], fontsize=8
    )
    ax.set_ylabel("Share of reviews (%)")
    ax.set_title("Positive vs negative rating share by peer group",
                 fontweight="bold")
    ax.legend(fontsize=9)
    save_fig(fig, "5E2_peer_positive_negative", "5E")

    # Chart 5E-3: Within-group dispersion boxplot
    fig, ax = plt.subplots(figsize=(11, 5))
    box_data = []
    box_labels = []
    for pg in peer_df["peer_group"]:
        vals = rp[rp["operational_peer_group"] == pg]["review_stars"].dropna()
        box_data.append(vals.tolist())
        box_labels.append(textwrap.fill(pg, 18))
    bp = ax.boxplot(box_data, labels=box_labels, patch_artist=True,
                    medianprops={"color": "white", "lw": 2},
                    flierprops={"marker": ".", "markersize": 3, "alpha": 0.4})
    peer_pal = ["#1D9E75","#7F77DD","#D85A30","#BA7517","#378ADD","#993556","#3B6D11","#185FA5"]
    for i, patch in enumerate(bp["boxes"]):
        patch.set_facecolor(peer_pal[i % len(peer_pal)])
        patch.set_alpha(0.75)
    ax.set_ylabel("Star rating")
    ax.set_title("Rating distribution within each peer group (Population A)",
                 fontweight="bold")
    save_fig(fig, "5E3_peer_group_boxplot", "5E")

    print(f"\n  [5E] Charts saved.")
    return results


# ════════════════════════════════════════════════════════════════════════════════
# 5F — REVIEW AND ENGAGEMENT BEHAVIOUR
# ════════════════════════════════════════════════════════════════════════════════

def step_5f(df):
    section("5F — Review and Engagement Behaviour")
    results = {}

    # ── Population B for text behaviour ──────────────────────────────────────
    np_ = df[df["_pop_nlp"]].copy()
    rp  = df[df["_pop_rating"]].copy()

    # ── 5F.1 Text availability by star rating ────────────────────────────────
    text_avail = (
        rp.groupby("review_stars")
        .agg(
            n_reviews       =("review_id",  "count"),
            has_text_count  =("has_text",   "sum"),
        )
        .reset_index()
    )
    text_avail["text_availability_pct"] = (
        text_avail["has_text_count"] / text_avail["n_reviews"] * 100
    ).round(1)
    results["text_availability"] = text_avail

    # ── 5F.2 Review length by star rating ────────────────────────────────────
    length_by_star = (
        np_.groupby("review_stars")["text_length_words"]
        .describe(percentiles=[0.25, 0.5, 0.75])
        .reset_index()
    )
    results["review_length_by_star"] = length_by_star

    # ── 5F.3 Owner response analysis ─────────────────────────────────────────
    owner_overall = {
        "Overall response rate"              : round(rp["has_owner_response"].mean() * 100, 1),
        "Median response delay (days)"       : int(rp["owner_response_delay_days"].median())
                                               if rp["owner_response_delay_days"].notna().any() else None,
        "Response rate — negative (1–2★)"   : round(rp[rp["review_stars"] <= 2]["has_owner_response"].mean() * 100, 1),
        "Response rate — mid (3★)"          : round(rp[rp["review_stars"] == 3]["has_owner_response"].mean() * 100, 1),
        "Response rate — positive (4–5★)"   : round(rp[rp["review_stars"] >= 4]["has_owner_response"].mean() * 100, 1),
    }
    results["owner_response_summary"] = pd.DataFrame(
        list(owner_overall.items()), columns=["Metric", "Value"]
    )
    for k, v in owner_overall.items():
        print(f"  {k:<50}: {v}")

    owner_by_rest = (
        rp.groupby(["restaurant_id", "restaurant_name"])
        .agg(
            n_reviews       =("review_id",                "count"),
            response_rate   =("has_owner_response",       "mean"),
            median_delay    =("owner_response_delay_days","median"),
        )
        .reset_index()
    )
    owner_by_rest["response_rate_pct"] = (owner_by_rest["response_rate"] * 100).round(1)
    owner_by_rest = owner_by_rest.sort_values("response_rate_pct", ascending=False)
    results["owner_response_by_restaurant"] = owner_by_rest

    # ── 5F.4 Local Guide vs non-Local Guide ──────────────────────────────────
    lg_compare = (
        rp.groupby("is_local_guide")["review_stars"]
        .agg(mean="mean", n="count", std="std")
        .reset_index()
    )
    lg_compare["group"] = lg_compare["is_local_guide"].map({0:"Non-Local Guide", 1:"Local Guide"})
    results["local_guide_comparison"] = lg_compare

    # ── 5F.5 Review length by peer group ─────────────────────────────────────
    length_by_peer = (
        np_.groupby("operational_peer_group")["text_length_words"]
        .agg(median="median", mean="mean", q25=lambda x: x.quantile(0.25),
             q75=lambda x: x.quantile(0.75))
        .reset_index()
    )
    results["review_length_by_peer"] = length_by_peer

    # ── 5F.6 CHARTS ──────────────────────────────────────────────────────────

    # Chart 5F-1: Text availability by star
    fig, ax = plt.subplots(figsize=(7, 4))
    ax.bar(text_avail["review_stars"], text_avail["text_availability_pct"],
           color=COLORS["star_palette"], width=0.7)
    for _, row in text_avail.iterrows():
        ax.text(row["review_stars"], row["text_availability_pct"] + 0.5,
                f"{row['text_availability_pct']:.0f}%\n(n={row['n_reviews']:,})",
                ha="center", fontsize=8)
    ax.set_xticks([1,2,3,4,5])
    ax.set_xlabel("Star rating")
    ax.set_ylabel("Reviews with written text (%)")
    ax.set_ylim(0, 110)
    ax.set_title("Text availability by star rating\n"
                 "(NLP population is biased toward reviewers who write text)",
                 fontweight="bold")
    save_fig(fig, "5F1_text_availability_by_star", "5F")

    # Chart 5F-2: Review length distribution by star (boxplot)
    fig, ax = plt.subplots(figsize=(8, 5))
    box_data_f = []
    star_labels_f = []
    for s in [1, 2, 3, 4, 5]:
        vals = np_[np_["review_stars"] == s]["text_length_words"].dropna()
        box_data_f.append(vals.tolist())
        star_labels_f.append(f"{s}★\n(n={len(vals):,})")
    bp2 = ax.boxplot(box_data_f, labels=star_labels_f, patch_artist=True,
                     medianprops={"color":"white","lw":2},
                     flierprops={"marker":".","markersize":3,"alpha":0.3},
                     showfliers=True)
    for patch, col in zip(bp2["boxes"], COLORS["star_palette"]):
        patch.set_facecolor(col)
        patch.set_alpha(0.8)
    ax.set_ylabel("Review length (words)")
    ax.set_title("Review length distribution by star rating (NLP population)\n"
                 "(longer negative reviews → potential NLP bias toward complaint topics)",
                 fontweight="bold")
    ax.set_ylim(0, ax.get_ylim()[1] * 0.7)
    save_fig(fig, "5F2_review_length_by_star", "5F")

    # Chart 5F-3: Owner response rate by rating group
    resp_by_star = (
        rp.groupby("review_stars")["has_owner_response"]
        .mean().reset_index()
    )
    resp_by_star["pct"] = resp_by_star["has_owner_response"] * 100
    fig, ax = plt.subplots(figsize=(7, 4))
    ax.bar(resp_by_star["review_stars"], resp_by_star["pct"],
           color=COLORS["star_palette"], width=0.7)
    for _, row in resp_by_star.iterrows():
        ax.text(row["review_stars"], row["pct"] + 0.5,
                f"{row['pct']:.1f}%", ha="center", fontsize=9)
    ax.set_xticks([1,2,3,4,5])
    ax.set_xlabel("Star rating")
    ax.set_ylabel("Owner response rate (%)")
    ax.set_title("Owner response rate by star rating\n"
                 "(association only — does not imply causation)",
                 fontweight="bold")
    save_fig(fig, "5F3_owner_response_by_star", "5F")

    # Chart 5F-4: Owner response rate per restaurant
    fig, ax = plt.subplots(figsize=(9, 7))
    orb = owner_by_rest.sort_values("response_rate_pct", ascending=True)
    ax.barh(range(len(orb)), orb["response_rate_pct"],
            color=COLORS["market"], height=0.6)
    ax.set_yticks(range(len(orb)))
    ax.set_yticklabels(
        [f"{r[:25]} (n={n})" for r, n in zip(orb["restaurant_name"], orb["n_reviews"])],
        fontsize=8
    )
    ax.set_xlabel("Owner response rate (%)")
    ax.set_title("Owner response rate per restaurant\n(descending — reputation management proxy)",
                 fontweight="bold")
    save_fig(fig, "5F4_owner_response_per_restaurant", "5F")

    # Chart 5F-5: Local Guide vs non-Local Guide rating
    fig, ax = plt.subplots(figsize=(6, 4))
    lg_valid = lg_compare.dropna(subset=["group"])
    ax.bar(lg_valid["group"], lg_valid["mean"],
           color=[COLORS["market"], COLORS["restw"]], width=0.5)
    for _, row in lg_valid.iterrows():
        ax.text(row["group"], row["mean"] + 0.02,
                f"{row['mean']:.3f}\n(n={int(row['n']):,})", ha="center", fontsize=9)
    ax.set_ylabel("Mean star rating")
    ax.set_ylim(3.5, 5.3)
    ax.set_title("Local Guide vs non-Local Guide — mean star rating\n"
                 "(supplementary; Local Guide = Google programme membership)",
                 fontweight="bold")
    save_fig(fig, "5F5_local_guide_comparison", "5F")

    print(f"\n  [5F] Charts saved.")
    return results


# ════════════════════════════════════════════════════════════════════════════════
# 5G — STRUCTURED CONTEXT EXPLORATION
# ════════════════════════════════════════════════════════════════════════════════

def step_5g(df):
    section("5G — Structured-Context Exploration")
    results = {}
    rp = df[df["_pop_rating"]].copy()
    n_total = len(rp)

    context_configs = [
        ("context_meal_type",        "Meal type",         True),
        ("context_order_type",       "Order type",        True),
        ("context_wait_time",        "Wait time",         True),
        ("context_price_per_person", "Price per person",  True),
        ("context_noise_level",      "Noise level",       True),
        ("context_parking",          "Parking",           False),
        ("context_dietary_restrictions","Dietary restrictions",False),
        ("detailed_rating_food",     "Food detailed rating",    True),
        ("detailed_rating_service",  "Service detailed rating", True),
        ("detailed_rating_atmosphere","Atmosphere rating",       True),
    ]

    for col, label, do_star_breakdown in context_configs:
        if col not in rp.columns:
            continue
        coverage = rp[col].notna().sum() / n_total
        if coverage < MIN_CONTEXT_COV:
            print(f"  [{label}] Coverage {coverage:.1%} < threshold — skipped")
            continue

        print(f"  [{label}] Coverage {coverage:.1%} — analysing")

        if do_star_breakdown:
            is_numeric = pd.api.types.is_numeric_dtype(rp[col])
            if is_numeric:
                # Detailed rating: correlation with overall star
                ctx_data = rp[[col, "review_stars"]].dropna()
                corr = ctx_data.corr().iloc[0, 1]
                agg = (
                    ctx_data.groupby("review_stars")[col]
                    .agg(["mean","median","count"])
                    .reset_index()
                )
                results[f"ctx_{col}"] = agg
                print(f"    Correlation with review_stars: {corr:.3f}")

                fig, ax = plt.subplots(figsize=(7, 4))
                ax.bar(agg["review_stars"], agg["mean"],
                       color=COLORS["star_palette"], width=0.7)
                ax.set_xticks([1,2,3,4,5])
                ax.set_xlabel("Star rating")
                ax.set_ylabel(f"Mean {label}")
                ax.set_title(f"{label} vs overall star rating (r={corr:.2f})\n"
                             f"Coverage: {coverage:.1%}", fontweight="bold")
                save_fig(fig, f"5G_{col}", "5G")

            else:
                # Categorical context: rating distribution per category
                ctx_data = rp[[col, "review_stars"]].dropna()
                cat_means = (
                    ctx_data.groupby(col)["review_stars"]
                    .agg(mean="mean", n="count")
                    .sort_values("mean", ascending=False)
                    .reset_index()
                )
                # Only show categories with enough data
                cat_means = cat_means[cat_means["n"] >= 10]
                if cat_means.empty:
                    continue
                results[f"ctx_{col}"] = cat_means

                fig, ax = plt.subplots(figsize=(8, max(4, len(cat_means) * 0.5)))
                ax.barh(range(len(cat_means)), cat_means["mean"],
                        color=COLORS["market"], height=0.6)
                ax.set_yticks(range(len(cat_means)))
                ax.set_yticklabels(
                    [f"{r} (n={n})" for r, n in zip(cat_means[col], cat_means["n"])],
                    fontsize=8
                )
                ax.set_xlabel("Mean star rating")
                ax.set_title(f"Mean rating by {label}\n"
                             f"Coverage: {coverage:.1%} (min 10 reviews per category)",
                             fontweight="bold")
                save_fig(fig, f"5G_{col}", "5G")

    print(f"\n  [5G] Context charts saved.")
    return results


# ════════════════════════════════════════════════════════════════════════════════
# EXPORT — Excel summary + Plotly notebook cells
# ════════════════════════════════════════════════════════════════════════════════

def export_excel_summary(all_results):
    path = os.path.join(OUT_DIR, "eda_summary.xlsx")
    with pd.ExcelWriter(path, engine="openpyxl") as w:
        for section_key, section_results in all_results.items():
            for tbl_key, tbl in section_results.items():
                if isinstance(tbl, pd.DataFrame) and len(tbl) > 0:
                    sheet = f"{section_key}_{tbl_key}"[:31]
                    tbl.to_excel(w, sheet_name=sheet, index=False)
    print(f"\n  Excel summary saved: {path}")
    return path


def generate_notebook(all_results, df):
    """
    Generate a Jupyter notebook (.ipynb) with:
      - Markdown cells explaining each section
      - Code cells producing Plotly interactive charts
    The notebook is self-contained: it loads the parquet and re-runs all analyses.
    """
    cells = []

    def md(text):
        cells.append({
            "cell_type": "markdown",
            "metadata": {},
            "source": text.strip().splitlines(keepends=True),
        })

    def code(text):
        cells.append({
            "cell_type": "code",
            "execution_count": None,
            "metadata": {},
            "outputs": [],
            "source": text.strip().splitlines(keepends=True),
        })

    md("""# Peterborough Restaurant Reviews — Market EDA
**Phase 3 / Step 5 — Exploratory Analysis**

All charts are interactive (Plotly). Hover for values, click legend to toggle series.

> **Data note**: Results reflect the *observed sample* of Google Reviews collected for 25 Peterborough restaurants. This is not a census of all customers or all reviews. See Section 5A for population definitions and coverage.
""")

    code(f"""import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import scipy.stats as stats

import os as _os
PARQUET = _os.path.join(_os.environ.get("PTBO_BASE", ".."), "02. Outputs_Data Mining", "reviews_analysis_ready.parquet")
RECENT_MONTHS = {RECENT_MONTHS}
MIN_REVIEWS_RANK = {MIN_REVIEWS_RANK}
MIN_REVIEWS_TREND = {MIN_REVIEWS_TREND}
PEER_ORDER = {json.dumps(PEER_ORDER)}

df = pd.read_parquet(PARQUET)
for col in ["published_at","scraped_at","owner_response_at"]:
    if col in df.columns:
        df[col] = pd.to_datetime(df[col], errors="coerce")
df["pub_ym"] = df["published_at"].dt.to_period("M")
df["pub_month_num"] = df["published_at"].dt.month
df["_pop_rating"] = df["rating_analysis_eligible"].fillna(0) == 1
df["_pop_nlp"]    = df["nlp_eligible"].fillna(0) == 1
rp = df[df["_pop_rating"]].copy()
np_ = df[df["_pop_nlp"]].copy()
print(f"Rating pop (A): {{df['_pop_rating'].sum():,}} | NLP pop (B): {{df['_pop_nlp'].sum():,}}")
""")

    md("## 5A — Population and Data Coverage")
    code("""# Population funnel
funnel = dict(
    labels=["All reviews","Rating pop. A","Text reviews","NLP pop. B","Gold eligible"],
    values=[len(df), int(df["_pop_rating"].sum()), int(df["has_text"].fillna(0).sum()),
            int(df["_pop_nlp"].sum()), int(df["gold_annotation_eligible"].fillna(0).sum())]
)
fig = go.Figure(go.Funnel(y=funnel["labels"], x=funnel["values"],
    textinfo="value+percent initial",
    marker=dict(color=["#B5D4F4","#85B7EB","#378ADD","#1D9E75","#0F6E56"])))
fig.update_layout(title="Review population funnel", height=400)
fig.show()
""")

    code("""# Review volume per restaurant
vol = rp.groupby("restaurant_name")["review_id"].count().reset_index()
vol.columns = ["restaurant_name","n_reviews"]
vol = vol.sort_values("n_reviews", ascending=False)
vol["cumshare"] = vol["n_reviews"].cumsum() / vol["n_reviews"].sum()
fig = px.bar(vol, x="restaurant_name", y="n_reviews",
    title="Review volume per restaurant (Population A)",
    color_discrete_sequence=["#378ADD"],
    labels={"n_reviews":"Reviews","restaurant_name":"Restaurant"})
fig.add_hline(y=MIN_REVIEWS_RANK, line_dash="dot", line_color="#D85A30",
              annotation_text=f"Min rank threshold ({MIN_REVIEWS_RANK})")
fig.update_xaxes(tickangle=45)
fig.show()
print(f"Top-5 concentration: {vol.head(5)['n_reviews'].sum()/vol['n_reviews'].sum():.1%}")
""")

    md("## 5B — Market-Level Rating Analysis")
    code("""# Star distribution + RW vs RestW
star_dist = rp["review_stars"].value_counts().sort_index().reset_index()
star_dist.columns = ["stars","count"]
star_dist["pct"] = star_dist["count"] / star_dist["count"].sum() * 100

fig = make_subplots(rows=1, cols=2, subplot_titles=[
    "Star distribution", "Review-weighted vs Restaurant-weighted mean"])
fig.add_trace(go.Bar(x=star_dist["stars"], y=star_dist["count"],
    marker_color=["#D85A30","#F0997B","#EF9F27","#9FE1CB","#1D9E75"],
    text=star_dist["pct"].round(1).astype(str)+"%", textposition="outside",
    name="Count"), row=1, col=1)

rw_m = rp["review_stars"].mean()
restw_m = rp.groupby("restaurant_id")["review_stars"].mean().mean()
fig.add_trace(go.Bar(x=["Review-weighted","Restaurant-weighted"],
    y=[rw_m, restw_m],
    marker_color=["#1D9E75","#7F77DD"],
    text=[f"{rw_m:.3f}", f"{restw_m:.3f}"], textposition="outside",
    name="Mean"), row=1, col=2)
fig.update_layout(title="Market rating overview", height=450, showlegend=False)
fig.show()
print(f"Difference (RW − RestW): {rw_m - restw_m:+.3f} stars")
""")

    md("## 5C — Temporal Analysis")
    code("""# Monthly volume + rating trend
monthly = (
    rp.groupby(rp["pub_ym"].astype(str))
    .agg(n=("review_id","count"), mean_stars=("review_stars","mean"))
    .reset_index().rename(columns={"pub_ym":"ym"})
)
monthly["rolling_mean"] = monthly["mean_stars"].rolling(3, min_periods=1).mean()
monthly["plot"] = monthly["n"] >= MIN_REVIEWS_TREND

fig = make_subplots(rows=2, cols=1, shared_xaxes=True,
    subplot_titles=["Monthly review volume","Monthly mean rating (review-weighted)"])
fig.add_trace(go.Bar(x=monthly["ym"], y=monthly["n"],
    marker_color="#B5D4F4", name="Volume"), row=1, col=1)
plotable = monthly[monthly["plot"]]
fig.add_trace(go.Scatter(x=plotable["ym"], y=plotable["mean_stars"],
    mode="markers+lines", line=dict(dash="dot", color="#378ADD"),
    name="Monthly avg"), row=2, col=1)
fig.add_trace(go.Scatter(x=plotable["ym"], y=plotable["rolling_mean"],
    mode="lines", line=dict(color="#D85A30", width=2.5),
    name="3M rolling avg"), row=2, col=1)
fig.update_layout(height=600, title="Review volume and rating trend")
fig.show()
""")

    md("## 5D — Restaurant Benchmarking")
    code("""# Rating vs volume scatter
bench = rp.groupby(["restaurant_id","restaurant_name","operational_peer_group"]).agg(
    n=("review_id","count"), mean_stars=("review_stars","mean")).reset_index()
bench["low_sample"] = bench["n"] < MIN_REVIEWS_RANK
bench["symbol"] = bench["low_sample"].map({True:"triangle-up", False:"circle"})

fig = px.scatter(bench, x="n", y="mean_stars",
    color="operational_peer_group",
    symbol="symbol",
    text="restaurant_name",
    hover_data={"n":True,"mean_stars":":.3f","low_sample":True},
    title="Rating vs review volume — restaurant benchmarking",
    labels={"n":"Number of reviews","mean_stars":"Mean star rating",
            "operational_peer_group":"Peer group"})
fig.add_hline(y=rp["review_stars"].mean(), line_dash="dash", line_color="gray",
    annotation_text=f"Market avg {rp['review_stars'].mean():.2f}★")
fig.update_traces(textposition="top center", textfont_size=8)
fig.update_layout(height=550)
fig.show()
""")

    md("## 5E — Peer-Group Benchmarking")
    code("""# Peer group rating comparison
peer = rp.groupby("operational_peer_group").agg(
    rw_mean=("review_stars","mean"),
    n=("review_id","count"),
    n_rest=("restaurant_id","nunique")).reset_index()
restw = rp.groupby(["operational_peer_group","restaurant_id"])["review_stars"].mean()\
    .groupby(level=0).mean().reset_index().rename(columns={"review_stars":"restw_mean"})
peer = peer.merge(restw, on="operational_peer_group")

fig = go.Figure()
fig.add_trace(go.Bar(name="Review-weighted", x=peer["operational_peer_group"],
    y=peer["rw_mean"], marker_color="#1D9E75",
    text=peer["rw_mean"].round(3), textposition="outside"))
fig.add_trace(go.Bar(name="Restaurant-weighted", x=peer["operational_peer_group"],
    y=peer["restw_mean"], marker_color="#7F77DD",
    text=peer["restw_mean"].round(3), textposition="outside"))
fig.update_layout(barmode="group", title="Peer-group mean rating — RW vs RestW",
    yaxis=dict(range=[3.5, 5.3]), height=450)
fig.show()
""")

    md("## 5F — Review and Engagement Behaviour")
    code("""# Review length by star + owner response rate
length = np_.groupby("review_stars")["text_length_words"].median().reset_index()
resp   = rp.groupby("review_stars")["has_owner_response"].mean().reset_index()
resp["pct"] = resp["has_owner_response"] * 100

fig = make_subplots(rows=1, cols=2, subplot_titles=[
    "Median review length by star (NLP pop.)",
    "Owner response rate by star (Rating pop.)"])
fig.add_trace(go.Bar(x=length["review_stars"], y=length["text_length_words"],
    marker_color=["#D85A30","#F0997B","#EF9F27","#9FE1CB","#1D9E75"],
    text=length["text_length_words"].round(1), textposition="outside",
    name="Median words"), row=1, col=1)
fig.add_trace(go.Bar(x=resp["review_stars"], y=resp["pct"],
    marker_color=["#D85A30","#F0997B","#EF9F27","#9FE1CB","#1D9E75"],
    text=resp["pct"].round(1).astype(str)+"%", textposition="outside",
    name="Response rate %"), row=1, col=2)
fig.update_layout(height=420, showlegend=False,
    title="Review behaviour and owner engagement")
fig.show()
""")

    md("## 5G — Structured Context (coverage-gated)")
    code("""# Detailed ratings vs overall star
for col, label in [("detailed_rating_food","Food"),
                   ("detailed_rating_service","Service"),
                   ("detailed_rating_atmosphere","Atmosphere")]:
    if col not in rp.columns: continue
    cov = rp[col].notna().mean()
    if cov < 0.15:
        print(f"{label}: coverage {cov:.1%} — skipped")
        continue
    agg = rp.groupby("review_stars")[col].mean().reset_index()
    corr = rp[[col,"review_stars"]].dropna().corr().iloc[0,1]
    fig = px.bar(agg, x="review_stars", y=col,
        title=f"{label} detailed rating by overall star (r={corr:.2f}, coverage={cov:.0%})",
        color_discrete_sequence=["#378ADD"],
        labels={"review_stars":"Star rating", col:f"Mean {label} rating"})
    fig.show()
""")

    nb = {
        "nbformat": 4,
        "nbformat_minor": 5,
        "metadata": {
            "kernelspec": {"display_name":"Python 3","language":"python","name":"python3"},
            "language_info": {"name":"python","version":"3.10.0"},
        },
        "cells": cells,
    }

    nb_path = os.path.join(OUT_DIR, "02_market_eda.ipynb")
    with open(nb_path, "w") as f:
        json.dump(nb, f, indent=1)
    print(f"  Notebook saved: {nb_path}")
    return nb_path


# ════════════════════════════════════════════════════════════════════════════════
# MAIN
# ════════════════════════════════════════════════════════════════════════════════

def main():
    print("=" * 70)
    print("  Peterborough Restaurant Reviews — Market EDA")
    print(f"  Run at: {datetime.now(timezone.utc).isoformat()}")
    print(f"  Thresholds: MIN_REVIEWS_RANK={MIN_REVIEWS_RANK} | "
          f"MIN_REVIEWS_TREND={MIN_REVIEWS_TREND} | "
          f"MIN_CONTEXT_COV={MIN_CONTEXT_COV:.0%} | "
          f"ROLLING_WINDOW={ROLLING_WINDOW}M | RECENT={RECENT_MONTHS}M")
    print("=" * 70)

    df = load_data()
    all_results = {}

    all_results["5A"] = step_5a(df)
    all_results["5B"] = step_5b(df)
    all_results["5C"] = step_5c(df)
    all_results["5D"] = step_5d(df)
    all_results["5E"] = step_5e(df)
    all_results["5F"] = step_5f(df)
    all_results["5G"] = step_5g(df)

    export_excel_summary(all_results)
    generate_notebook(all_results, df)

    print("\n" + "=" * 70)
    print(f"  EDA complete. Outputs in: {OUT_DIR}")
    print(f"  Charts: {CHART_DIR}/")
    print(f"  Summary Excel: {OUT_DIR}/eda_summary.xlsx")
    print(f"  Notebook: {OUT_DIR}/02_market_eda.ipynb")
    print("=" * 70)

    return all_results


if __name__ == "__main__":
    results = main()
