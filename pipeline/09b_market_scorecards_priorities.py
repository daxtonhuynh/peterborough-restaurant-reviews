# -*- coding: utf-8 -*-
"""
09b_market_scorecards_priorities.py (5 Nov 2026)
  Market analysis   : aspect prevalence, positive/negative rates (bootstrap 95% CI), recent-12-month change, segments
  Scorecards        : 25 restaurants - snapshot, aspect breakdown vs peer group and city, strengths/weaknesses
  Priorities        : Priority = negative rate x severity x rating association x recent growth x peer factor x controllability x confidence
  Action-plan data  : top priorities per restaurant with finding, evidence (incl. example quotes), interpretation, action, KPI, limitation
Outputs (08. Outputs_Analysis/): market_analysis.xlsx, restaurant_scorecards.xlsx, priorities_action_plans.xlsx, dashboard_data.json
"""
import os, sys, json, re
from pathlib import Path
import numpy as np, pandas as pd
BASE = Path(os.environ.get("PTBO_BASE", Path(__file__).resolve().parent.parent)); OUT = BASE / "08. Outputs_Analysis"
sys.path.insert(0, str(Path(__file__).resolve().parent)); from absa_lexicon import SHORT, NAME
F = pd.read_parquet(BASE / "07. Outputs_ABSA/absa_review_features.parquet")
A = pd.read_parquet(BASE / "07. Outputs_ABSA/absa_unit_aspects.parquet")
R = pd.read_parquet(BASE / "02. Outputs_Data Mining/reviews_analysis_ready.parquet")
ame = pd.read_csv(OUT / "rating_driver_ame.csv").set_index("feature")
OPS = ["FOOD","FRESH","PORT","MENU","PRICE","STAFF","SPEED","ACC","AMB","CLEAN","LOC","DELIV","DIET","COMPL"]
ALLA = OPS + ["OVR"]
rng = np.random.default_rng(42)
for d in (F, R): d["published_at"] = pd.to_datetime(d.published_at, utc=True)
END = R.published_at.max(); CUT = END - pd.DateOffset(months=12)
F["recent"] = F.published_at >= CUT; R["recent"] = R.published_at >= CUT

# ------------------------------------------------------------------ market
def boot(x, B=1000):
    x = np.asarray(x, float); i = rng.integers(0, len(x), (B, len(x))); m = x[i].mean(1); return np.percentile(m, [2.5, 97.5])
mk = []
for c in ALLA:
    men, pos, neg = F[f"{c}_mention"], F[f"{c}_pos"], F[f"{c}_neg"]
    net = (pos.sum() - neg.sum()) / max(pos.sum() + neg.sum(), 1)
    lo, hi = boot(neg); rec, old = F[F.recent], F[~F.recent]
    nr, no = rec[f"{c}_neg"].mean(), old[f"{c}_neg"].mean()
    p = (rec[f"{c}_neg"].sum() + old[f"{c}_neg"].sum()) / len(F); se = np.sqrt(p * (1 - p) * (1 / len(rec) + 1 / len(old))) if 0 < p < 1 else np.nan
    mk.append({"aspect": SHORT[c], "code": c, "mention_rate_pct": round(100 * men.mean(), 1), "positive_rate_pct": round(100 * pos.mean(), 1),
               "negative_rate_pct": round(100 * neg.mean(), 2), "neg_rate_95CI": f"{100*lo:.1f}-{100*hi:.1f}",
               "net_sentiment": round(net, 2), "neg_rate_recent12m_pct": round(100 * nr, 2), "neg_rate_before_pct": round(100 * no, 2),
               "change_pp": round(100 * (nr - no), 2), "change_z": round((nr - no) / se, 2) if se else None,
               "AME_low_rating_if_negative_pp": ame.loc[f"{c}_neg", "AME_pp_low_rating"] if f"{c}_neg" in ame.index else None})
mk = pd.DataFrame(mk)
seg = []
for col in ("operational_peer_group", "cuisine_cluster"):
    for g, d in F.groupby(col):
        for c in OPS:
            seg.append({"segment_type": col, "segment": g, "n_text_reviews": len(d), "aspect": SHORT[c],
                        "mention_rate_pct": round(100 * d[f"{c}_mention"].mean(), 1), "negative_rate_pct": round(100 * d[f"{c}_neg"].mean(), 2),
                        "net_sentiment": round((d[f"{c}_pos"].sum() - d[f"{c}_neg"].sum()) / max(d[f"{c}_pos"].sum() + d[f"{c}_neg"].sum(), 1), 2)})
seg = pd.DataFrame(seg)
over = pd.DataFrame([("Reviews collected", len(R)), ("Text reviews analysed (ABSA)", len(F)), ("Restaurants", R.restaurant_id.nunique()),
                     ("Date range", f"{R.published_at.min():%Y-%m} to {END:%Y-%m}"), ("Recent window", f"{CUT:%Y-%m-%d} to {END:%Y-%m-%d}"),
                     ("Mean stars (review-weighted, all reviews)", round(R.review_stars.mean(), 3)),
                     ("Mean stars (restaurant-weighted)", round(R.groupby("restaurant_id").review_stars.mean().mean(), 3)),
                     ("Share 1-2 stars (all reviews)", f"{(R.review_stars <= 2).mean():.1%}"),
                     ("Share 4-5 stars (all reviews)", f"{(R.review_stars >= 4).mean():.1%}"),
                     ("Text reviews with >=1 negative operational aspect", f"{(F.n_neg_aspects > 0).mean():.1%}"),
                     ("Text reviews with mixed experience (pos + neg)", f"{F.mixed_experience.mean():.1%}"),
                     ("Return intention stated (positive / negative)", f"{(F.return_intention > 0).mean():.1%} / {(F.return_intention < 0).mean():.1%}")],
                    columns=["metric", "value"])

# ------------------------------------------------------------------ scorecards
info = R.groupby("restaurant_id").agg(restaurant=("restaurant_name", "first"), peer_group=("operational_peer_group", "first"),
        cuisine=("cuisine_cluster", "first"), price_tier=("price_tier", "first"), brand_type=("brand_type", "first"),
        google_rating=("restaurant_google_rating_at_scrape", "first"), google_review_count=("google_review_count_at_scrape", "first"),
        collection_coverage=("collection_coverage", "first"), n_reviews=("review_id", "size"), mean_stars=("review_stars", "mean"),
        pct_4_5=("review_stars", lambda s: 100 * (s >= 4).mean()), pct_1_2=("review_stars", lambda s: 100 * (s <= 2).mean()),
        owner_response_rate=("has_owner_response", "mean"))
rc = R[R.recent].groupby("restaurant_id").agg(n_recent=("review_id", "size"), stars_recent=("review_stars", "mean"))
ro = R[~R.recent].groupby("restaurant_id").agg(stars_before=("review_stars", "mean"))
info = info.join(rc).join(ro).join(F.groupby("restaurant_id").agg(n_text=("review_id", "size"), ret_pos=("return_intention", lambda s: 100 * (s > 0).mean()),
                                                                   ret_neg=("return_intention", lambda s: 100 * (s < 0).mean())))
info["stars_trend"] = info.stars_recent - info.stars_before
info["peer_mean_stars"] = info.groupby("peer_group").mean_stars.transform("mean")
info["rating_rank_in_peer"] = info.groupby("peer_group").mean_stars.rank(ascending=False).astype(int)
info["peer_size"] = info.groupby("peer_group").mean_stars.transform("size").astype(int)
for c in ["mean_stars","pct_4_5","pct_1_2","stars_recent","stars_before","stars_trend","peer_mean_stars","ret_pos","ret_neg","owner_response_rate"]:
    info[c] = info[c].round(2)
def wilson(k, n, z=1.96):
    if n == 0: return (np.nan, np.nan)
    p = k / n; d = 1 + z * z / n; c = p + z * z / (2 * n); h = z * np.sqrt(p * (1 - p) / n + z * z / (4 * n * n)); return ((c - h) / d, (c + h) / d)
asp = []
city = {c: (F[f"{c}_neg"].mean(), F[f"{c}_pos"].mean(), F[f"{c}_mention"].mean()) for c in ALLA}
for rid, d in F.groupby("restaurant_id"):
    pg = info.at[rid, "peer_group"]; peer = F[(F.operational_peer_group == pg) & (F.restaurant_id != rid)]
    for c in ALLA:
        n = len(d); k_neg, k_pos, k_men = int(d[f"{c}_neg"].sum()), int(d[f"{c}_pos"].sum()), int(d[f"{c}_mention"].sum())
        pn = peer[f"{c}_neg"].mean() if len(peer) else np.nan; pp_ = peer[f"{c}_pos"].mean() if len(peer) else np.nan
        p0 = (k_neg + peer[f"{c}_neg"].sum()) / (n + len(peer)); se = np.sqrt(p0 * (1 - p0) * (1 / n + 1 / max(len(peer), 1))) if 0 < p0 < 1 else np.nan
        lo, hi = wilson(k_neg, n); dr, do = d[d.recent], d[~d.recent]
        asp.append({"restaurant_id": rid, "restaurant": info.at[rid, "restaurant"], "peer_group": pg, "aspect": SHORT[c], "code": c,
                    "n_text_reviews": n, "n_mentions": k_men, "n_positive": k_pos, "n_negative": k_neg,
                    "mention_rate_pct": round(100 * k_men / n, 1), "positive_rate_pct": round(100 * k_pos / n, 1), "negative_rate_pct": round(100 * k_neg / n, 2),
                    "neg_rate_95CI": f"{100*lo:.1f}-{100*hi:.1f}", "net_sentiment": round((k_pos - k_neg) / max(k_pos + k_neg, 1), 2),
                    "peer_negative_rate_pct": round(100 * pn, 2), "peer_positive_rate_pct": round(100 * pp_, 2),
                    "city_negative_rate_pct": round(100 * city[c][0], 2), "city_positive_rate_pct": round(100 * city[c][1], 2),
                    "neg_gap_vs_peer_pp": round(100 * (k_neg / n - pn), 2), "pos_gap_vs_peer_pp": round(100 * (k_pos / n - pp_), 2),
                    "neg_z_vs_peer": round((k_neg / n - pn) / se, 2) if se else None,
                    "neg_rate_recent12m_pct": round(100 * dr[f"{c}_neg"].mean(), 2) if len(dr) else None, "n_text_recent12m": len(dr),
                    "neg_rate_before_pct": round(100 * do[f"{c}_neg"].mean(), 2) if len(do) else None})
asp = pd.DataFrame(asp)
asp["net_percentile_in_city"] = asp.groupby("code").net_sentiment.rank(pct=True).mul(100).round(0)
# strengths / weaknesses
sw = []
for rid, d in asp[asp.code.isin(OPS)].groupby("restaurant_id"):
    st = d[(d.n_positive >= 8) & (d.pos_gap_vs_peer_pp >= 2) & (d.net_sentiment >= 0.6)].sort_values("pos_gap_vs_peer_pp", ascending=False).head(3)
    wk = d[(d.n_negative >= 4) & (d.neg_gap_vs_peer_pp >= 1) & (d.neg_z_vs_peer >= 1.28)].sort_values("neg_z_vs_peer", ascending=False).head(3)
    for _, r in st.iterrows(): sw.append({"restaurant_id": rid, "type": "Strength", "aspect": r.aspect, "evidence": f"Positive in {r.positive_rate_pct:.0f}% of text reviews vs {r.peer_positive_rate_pct:.0f}% in peer group (net {r.net_sentiment:+.2f}, n={r.n_positive})"})
    for _, r in wk.iterrows(): sw.append({"restaurant_id": rid, "type": "Weakness", "aspect": r.aspect, "evidence": f"Negative in {r.negative_rate_pct:.1f}% of text reviews vs {r.peer_negative_rate_pct:.1f}% in peer group (z={r.neg_z_vs_peer:.1f}, n={r.n_negative})"})
sw = pd.DataFrame(sw)

# ------------------------------------------------------------------ priorities
CTRL = {"ACC":1.0,"CLEAN":1.0,"STAFF":1.0,"COMPL":1.0,"SPEED":0.9,"FRESH":0.9,"PORT":0.9,"DELIV":0.8,"DIET":0.8,"FOOD":0.8,"MENU":0.7,"PRICE":0.6,"AMB":0.5,"LOC":0.2}
low_share_city = {c: ((F[f"{c}_neg"] == 1) & (F.review_stars <= 2)).sum() / max(F[f"{c}_neg"].sum(), 1) for c in OPS}
pr = []
for _, r in asp[asp.code.isin(OPS)].iterrows():
    if r.n_negative < 4: continue
    d = F[F.restaurant_id == r.restaurant_id]; c = r.code
    k_low = int(((d[f"{c}_neg"] == 1) & (d.review_stars <= 2)).sum())
    sev = (k_low + 5 * low_share_city[c]) / (r.n_negative + 5)                       # share of the aspect's complaints in 1-2 star reviews, shrunk to city
    assoc = max(ame.loc[f"{c}_neg", "AME_pp_low_rating"], 0.5) / 10 if f"{c}_neg" in ame.index else 0.05
    rec, old = r.neg_rate_recent12m_pct, r.neg_rate_before_pct
    growth = float(np.clip(((rec if pd.notna(rec) and r.n_text_recent12m >= 10 else old) + 1) / ((old if pd.notna(old) else rec) + 1), 0.67, 1.5))
    peerf = float(np.clip((r.negative_rate_pct + 0.5) / (r.peer_negative_rate_pct + 0.5), 0.5, 2.0))
    conf = r.n_negative / (r.n_negative + 5)
    score = (r.negative_rate_pct / 100) * sev * assoc * growth * peerf * CTRL[c] * conf
    pr.append({**r[["restaurant_id","restaurant","peer_group","aspect","code","n_text_reviews","n_negative","negative_rate_pct","peer_negative_rate_pct",
                    "city_negative_rate_pct","neg_z_vs_peer","neg_rate_recent12m_pct","neg_rate_before_pct","n_text_recent12m"]].to_dict(),
               "severity_share_in_1_2_star": round(sev, 2), "rating_association_AME_pp": round(assoc * 10, 1), "recent_growth_factor": round(growth, 2),
               "peer_factor": round(peerf, 2), "controllability": CTRL[c], "confidence": round(conf, 2), "priority_score_raw": score})
pr = pd.DataFrame(pr)
pr["priority_index"] = (100 * pr.priority_score_raw / pr.priority_score_raw.max()).round(1)
pr["rank_in_restaurant"] = pr.groupby("restaurant_id").priority_score_raw.rank(ascending=False, method="first").astype(int)

# ------------------------------------------------------------------ action-plan text
PB_PATH = Path(__file__).resolve().parent.parent / "config" / "action_playbook.json"
PB = json.load(open(PB_PATH if PB_PATH.exists() else OUT / "action_playbook.json"))
def quotes(rid, c, k=2):
    q = A[(A.restaurant_id == rid) & (A.aspect == c) & (A.sentiment == "Negative") & (A.source == "lexicon")].copy()
    q["nw"] = q.unit_text.str.split().str.len(); q = q[(q.nw >= 5) & (q.nw <= 30)]
    q = q.merge(F[["review_id","published_at"]], on="review_id").sort_values("published_at", ascending=False)
    return [f"“{t.strip()}” ({p:%b %Y})" for t, p in zip(q.unit_text.head(k), q.published_at.head(k))]
plans = []
for rid, d in pr.groupby("restaurant_id"):
    ranked = d.sort_values("priority_score_raw", ascending=False)
    above = ranked[ranked.negative_rate_pct >= ranked.peer_negative_rate_pct].head(5)      # priorities: at or above peer complaint rate
    top = above.assign(plan_type="Priority") if len(above) else ranked.head(1).assign(plan_type="Watch (below peer rate)")
    top = top.assign(rank_in_restaurant=range(1, len(top) + 1))
    cov = info.at[rid, "collection_coverage"]
    for _, r in top.iterrows():
        c = r.code; pb = PB[c]
        trend = ("rising" if r.neg_rate_recent12m_pct is not None and pd.notna(r.neg_rate_before_pct) and r.n_text_recent12m >= 10 and r.neg_rate_recent12m_pct > r.neg_rate_before_pct + 1
                 else "falling" if r.neg_rate_recent12m_pct is not None and pd.notna(r.neg_rate_before_pct) and r.n_text_recent12m >= 10 and r.neg_rate_recent12m_pct < r.neg_rate_before_pct - 1 else "stable / too few recent reviews")
        rel = "above" if r.negative_rate_pct > r.peer_negative_rate_pct + 0.5 else "below" if r.negative_rate_pct < r.peer_negative_rate_pct - 0.5 else "in line with"
        finding = (f"{SHORT[c]} complaints appear in {r.negative_rate_pct:.1f}% of {r.restaurant}'s text reviews ({int(r.n_negative)} of {int(r.n_text_reviews)}), "
                   f"{rel} the {r.peer_group} peer group ({r.peer_negative_rate_pct:.1f}%); recent trend: {trend}.")
        ev = (f"{r.severity_share_in_1_2_star:.0%} of these complaints sit in 1-2 star reviews (shrunk estimate). Across Peterborough, a negative {SHORT[c].lower()} mention is "
              f"associated with +{r.rating_association_AME_pp:.1f} pp probability of a 1-2 star rating. Recent 12 months: {r.neg_rate_recent12m_pct if pd.notna(r.neg_rate_recent12m_pct) else 'n/a'}% "
              f"(n={int(r.n_text_recent12m)} text reviews) vs {r.neg_rate_before_pct if pd.notna(r.neg_rate_before_pct) else 'n/a'}% before.")
        lim = (f"Based on {int(r.n_negative)} negative mentions; collected reviews cover {cov:.0%} of the restaurant's Google reviews. Aspect labels come from a weak-supervision "
               f"model validated on 200 silver-labelled sentences (aspect F1 ~0.77, sentiment accuracy ~0.80). Association, not proof of cause; no internal operating data was used.")
        conf = "High" if r.n_negative >= 15 and r.neg_z_vs_peer >= 1.64 else "Medium" if r.n_negative >= 8 else "Low"
        plans.append({"restaurant_id": rid, "restaurant": r.restaurant, "priority_rank": int(r.rank_in_restaurant), "plan_type": r.plan_type, "aspect": SHORT[c], "priority_index": r.priority_index,
                      "confidence": conf, "finding": finding, "evidence": ev, "example_quotes": " | ".join(quotes(rid, c)),
                      "interpretation": pb["interpretation"], "recommended_action": pb["action"], "kpi": pb["kpi"], "limitation": lim})
plans = pd.DataFrame(plans)

# ------------------------------------------------------------------ write
with pd.ExcelWriter(OUT / "market_analysis.xlsx") as w:
    over.to_excel(w, sheet_name="Overview", index=False); mk.drop(columns="code").to_excel(w, sheet_name="Aspects (market)", index=False)
    seg.to_excel(w, sheet_name="Segments", index=False)
with pd.ExcelWriter(OUT / "restaurant_scorecards.xlsx") as w:
    info.reset_index().to_excel(w, sheet_name="Snapshot", index=False); asp.drop(columns="code").to_excel(w, sheet_name="Aspect breakdown", index=False)
    sw.merge(info[["restaurant"]], left_on="restaurant_id", right_index=True).to_excel(w, sheet_name="Strengths & weaknesses", index=False)
with pd.ExcelWriter(OUT / "priorities_action_plans.xlsx") as w:
    pd.DataFrame({"note": ["Priority = negative rate x severity (share of complaints in 1-2 star reviews, shrunk) x rating association (market AME) x recent growth x peer factor x controllability x confidence.",
                           "Controllability weights are analyst assumptions (ACC/CLEAN/STAFF/COMPL 1.0 ... LOC 0.2). Priority index is scaled so the highest item in Peterborough = 100.",
                           "Recommendations are evidence-based hypotheses from public reviews, not conclusions about internal operations."]}).to_excel(w, sheet_name="README", index=False)
    plans.to_excel(w, sheet_name="Action plans", index=False); pr.drop(columns="priority_score_raw").sort_values(["restaurant","rank_in_restaurant"]).to_excel(w, sheet_name="All priority scores", index=False)
# dashboard data
mon = R.assign(m=R.published_at.dt.strftime("%Y-%m")).groupby(["restaurant_id", "m"]).agg(n=("review_id", "size"), s=("review_stars", "mean")).reset_index()
dash = {"meta": {"end": f"{END:%Y-%m-%d}", "recent_from": f"{CUT:%Y-%m-%d}", "n_reviews": int(len(R)), "n_text": int(len(F))},
        "overview": over.to_dict("records"), "market": mk.to_dict("records"), "segments": seg.to_dict("records"),
        "restaurants": info.reset_index().to_dict("records"), "aspects": asp.to_dict("records"), "sw": sw.to_dict("records"),
        "plans": plans.to_dict("records"), "drivers": pd.read_csv(OUT / "rating_driver_ame.csv").to_dict("records"),
        "monthly": mon.to_dict("records")}
json.dump(dash, open(OUT / "dashboard_data.json", "w"), default=lambda o: None if (isinstance(o, float) and np.isnan(o)) else (o.item() if hasattr(o, "item") else str(o)))
print(over.to_string(index=False)); print(mk[["aspect","mention_rate_pct","positive_rate_pct","negative_rate_pct","net_sentiment","change_pp","change_z"]].to_string(index=False))
print("plans:", len(plans), "restaurants with plans:", plans.restaurant_id.nunique(), "| per restaurant:", plans.groupby("restaurant_id").size().describe()[["min","max"]].to_dict())
print(plans.groupby("aspect").size().sort_values(ascending=False).to_string())
