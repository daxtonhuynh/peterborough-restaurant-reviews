# -*- coding: utf-8 -*-
"""
08_absa_inference.py (5 Nov 2026) - runs the chosen ABSA configuration (07) on all 17,191 ABSA units and builds
review-level business variables.
Outputs (07. Outputs_ABSA/):
  absa_unit_aspects.parquet     one row per (unit, aspect): sentiment, rule/VADER score, classifier probability, cue word
  absa_review_features.parquet  one row per text review: per-aspect mention / positive / negative, counts, mixed,
                                return intention, food-safety flag, service channel + review metadata
  food_safety_review_queue.xlsx units flagged as customer-reported food-safety concerns -> MANUAL REVIEW, internal only
  inference_qc.xlsx             coverage, NA share, convergent validity vs Google sub-ratings
"""
import os, sys, json, re
from pathlib import Path
import numpy as np, pandas as pd
sys.path.insert(0, str(Path(__file__).resolve().parent))
from absa_lexicon import *
BASE = Path(os.environ.get("PTBO_BASE", Path(__file__).resolve().parent.parent)); OUT = BASE / "07. Outputs_ABSA"
cfg = json.load(open(OUT / "models/chosen_config.json")); THR = cfg["threshold"]
U = pd.read_parquet(OUT / "_units_with_probs.parquet")
R = pd.read_parquet(BASE / "02. Outputs_Data Mining/reviews_analysis_ready.parquet")
pcols = [c for c in U.columns if c.startswith("p_")]

rows = []
for r in U.itertuples(index=False):
    text = r.unit_text; t = CANT_WAIT.sub(" cantwait ", text)
    hits = {c: m for c in CODES if (m := LEX_RX[c].search(t))}
    asp = {c: (m.start(), m.group(0), "lexicon") for c, m in hits.items()}
    for pc in pcols:
        c = pc[2:]; p = getattr(r, pc)
        if p >= THR and c not in asp: asp[c] = (None, None, "classifier")
    for c, (pos, cue, src) in asp.items():
        lab, sc = aspect_sent(text, c, pos, "rules")
        rows.append((r.unit_id, r.sentence_id, r.review_id, c, lab, round(float(sc), 3),
                     round(float(getattr(r, "p_" + c)), 3) if ("p_" + c) in pcols else None, cue, src))
A = pd.DataFrame(rows, columns=["unit_id","sentence_id","review_id","aspect","sentiment","score","clf_prob","cue","source"])
U["food_safety_flag"] = U.unit_text.apply(lambda x: int(bool(SAFETY_YES.search(x)) and not SAFETY_NO.search(x)))
U["return_intention"] = U.unit_text.apply(lambda x: (-1 if RETURN_NEG.search(x) else 1) if RETURN_POS.search(CANT_WAIT.sub(" ", x)) else 0)
U["has_aspect"] = U.unit_id.isin(A.unit_id)
A = A.merge(U[["unit_id","unit_text","restaurant_id"]], on="unit_id")
A.to_parquet(OUT / "absa_unit_aspects.parquet", index=False)

# ---- review level
txt = R[R.nlp_eligible == 1].copy()
def channel(row):
    o = "" if pd.isna(row.context_order_type) else str(row.context_order_type).lower()
    if "deliver" in o: return "delivery"
    if "take" in o or "pick" in o: return "takeout"
    if "dine" in o: return "dine_in"
    for ch, rx in CHANNEL:
        if rx.search(str(row.review_text_for_nlp)): return ch
    return "unknown"
txt["service_channel"] = txt.apply(channel, axis=1)
piv = A.assign(pos=(A.sentiment == "Positive").astype(int), neg=(A.sentiment == "Negative").astype(int), men=1)
g = piv.groupby(["review_id","aspect"])[["men","pos","neg"]].sum().unstack(fill_value=0)
feat = pd.DataFrame(index=txt.review_id)
for c in CODES:
    m = g["men"][c] if c in g["men"] else pd.Series(dtype=float); p = g["pos"][c] if c in g["pos"] else pd.Series(dtype=float); n = g["neg"][c] if c in g["neg"] else pd.Series(dtype=float)
    feat[f"{c}_mention"] = (m.reindex(feat.index).fillna(0) > 0).astype(int)
    pp, nn = p.reindex(feat.index).fillna(0), n.reindex(feat.index).fillna(0)
    feat[f"{c}_pos"] = ((pp > 0) & (pp >= nn)).astype(int)        # review-level polarity of the aspect: majority, ties -> positive only if no more negatives
    feat[f"{c}_neg"] = ((nn > 0) & (nn >= pp)).astype(int)
    feat[f"{c}_net"] = np.sign(pp - nn).astype(int)
OPS = [c for c in CODES if c not in ("OVR","OTHER")]
feat["n_neg_aspects"] = feat[[f"{c}_neg" for c in OPS]].sum(1); feat["n_pos_aspects"] = feat[[f"{c}_pos" for c in OPS]].sum(1)
feat["mixed_experience"] = ((feat.n_neg_aspects > 0) & (feat.n_pos_aspects > 0)).astype(int)
ur = U.groupby("review_id").agg(food_safety_flag=("food_safety_flag","max"), ret_min=("return_intention","min"), ret_max=("return_intention","max"),
                                n_units=("unit_id","size"), n_units_no_aspect=("has_aspect", lambda s: int((~s).sum())))
ur["return_intention"] = np.where(ur.ret_min < 0, -1, np.where(ur.ret_max > 0, 1, 0))
feat = feat.join(ur[["food_safety_flag","return_intention","n_units","n_units_no_aspect"]])
meta = ["review_id","restaurant_id","restaurant_name","review_stars","published_at","review_year","operational_peer_group","cuisine_cluster",
        "price_tier","brand_type","text_length_words","has_owner_response","detailed_rating_food","detailed_rating_service",
        "detailed_rating_atmosphere","is_local_guide","service_channel"]
F = txt[meta].merge(feat.reset_index(), on="review_id", how="left")
F.to_parquet(OUT / "absa_review_features.parquet", index=False)

# ---- safety queue + QC
q = U[U.food_safety_flag == 1][["unit_id","review_id","restaurant_id","restaurant_name","review_stars","published_at","unit_text"]]
q = q.assign(manual_review_status="", reviewer_notes="")
with pd.ExcelWriter(OUT / "food_safety_review_queue.xlsx") as w:
    pd.DataFrame({"note": ["INTERNAL ONLY. Customer-REPORTED concerns detected by keyword rules (codebook v1.2 rule 8/8a).",
                           "Not verified, not evidence that a restaurant caused illness. Do not publish restaurant-level counts without manual review."]}).to_excel(w, sheet_name="README", index=False)
    q.to_excel(w, sheet_name="Queue", index=False)
from scipy.stats import spearmanr
val = []
for c, col in [("FOOD","detailed_rating_food"),("STAFF","detailed_rating_service"),("SPEED","detailed_rating_service"),("AMB","detailed_rating_atmosphere")]:
    d = F[(F[f"{c}_mention"] == 1) & F[col].notna()]
    if len(d) > 30:
        rho, p = spearmanr(d[f"{c}_net"], d[col]); val.append({"aspect": SHORT[c], "google_sub_rating": col, "n_reviews": len(d), "spearman_rho": round(rho, 3), "p_value": f"{p:.1e}"})
cov = pd.DataFrame({"metric": ["ABSA units", "units with >=1 aspect", "share of units with no aspect (NA)", "aspect mentions",
                               "text reviews", "text reviews with >=1 aspect", "food-safety flagged units (for manual review)"],
                    "value": [len(U), int(U.has_aspect.sum()), round(1 - U.has_aspect.mean(), 3), len(A), len(F),
                              int((F[[f"{c}_mention" for c in CODES]].sum(1) > 0).sum()), int(U.food_safety_flag.sum())]})
dist = A.groupby("aspect").sentiment.value_counts().unstack(fill_value=0).rename(index=SHORT)
with pd.ExcelWriter(OUT / "inference_qc.xlsx") as w:
    cov.to_excel(w, sheet_name="Coverage", index=False); dist.to_excel(w, sheet_name="Aspect x sentiment")
    pd.DataFrame(val).to_excel(w, sheet_name="Convergent validity", index=False)
print(cov.to_string(index=False)); print(dist.to_string()); print(pd.DataFrame(val).to_string(index=False))
