# -*- coding: utf-8 -*-
"""
06a_pilot_agreement_and_gold.py  (5 Nov 2026)
Run AFTER the pilot review. Turns verified pilot labels into the first gold file and measures agreement.

Inputs (05. Outputs_BERTopic/ by default):
  annotation_pilot_v3_prelabelled.xlsx  'Review' = Annotator A (only rows with verified = 1 count)
                                        'LLM labels (original)' = frozen LLM pre-labels
                                        'Sample design (open AFTER)' = metadata
  annotation_pilot_v3_annotator_B.xlsx  'Annotate' = Annotator B (40 blind rows; rows with any aspect count)
Outputs (06. Outputs_Annotation/):
  gold_absa_pilot_v1.csv        long format: one row per (sentence, aspect) from VERIFIED rows only
  pilot_agreement_report.xlsx   Summary, per-aspect kappa, sentiment agreement, LLM vs human, disagreements,
                                validation issues
Agreement (Cohen's kappa):
  A vs B   - human reliability (the number that decides whether we scale up; target >= 0.70)
  LLM vs A - how much the reviewer changed (inflated by anchoring)
  LLM vs B - LLM quality against a blind human (the honest LLM number)
Usage: python 06a_pilot_agreement_and_gold.py [--dry-run] [--pilot PATH] [--b-file PATH] [--out-dir PATH]
"""
import os, sys, argparse
from pathlib import Path
import numpy as np
import pandas as pd
from sklearn.metrics import cohen_kappa_score, precision_recall_fscore_support

BASE = Path(os.environ.get("PTBO_BASE", Path(__file__).resolve().parent.parent))
ap = argparse.ArgumentParser()
ap.add_argument("--pilot", default=str(BASE / "05. Outputs_BERTopic/annotation_pilot_v3_prelabelled.xlsx"))
ap.add_argument("--b-file", default=str(BASE / "05. Outputs_BERTopic/annotation_pilot_v3_annotator_B.xlsx"))
ap.add_argument("--out-dir", default=str(BASE / "06. Outputs_Annotation"))
ap.add_argument("--dry-run", action="store_true", help="print status only, write nothing")
args = ap.parse_args()
KAPPA_TARGET = 0.70
NO_SENT = {"Not applicable / context only", "Reported food-safety concern (flag)"}

def to_long(df, source):
    """Wide annotation sheet -> {sample_id: {'aspects': {aspect: sentiment}, 'evidence': {...}, 'channel', 'fs'}} + issues"""
    out, issues = {}, []
    for r in df.itertuples(index=False):
        r = r._asdict(); sid = r["sample_id"]; asp, ev = {}, {}
        for k in (1, 2, 3):
            a, s, e = r.get(f"aspect_{k}"), r.get(f"sentiment_{k}"), r.get(f"evidence_{k}")
            if pd.isna(a): 
                if pd.notna(s) or pd.notna(e): issues.append((source, sid, f"slot {k}: sentiment/evidence without aspect"))
                continue
            s = None if pd.isna(s) else s
            if a in NO_SENT and s: issues.append((source, sid, f"slot {k}: '{a}' should have no sentiment"))
            if a not in NO_SENT and not s: issues.append((source, sid, f"slot {k}: '{a}' has no sentiment"))
            if pd.notna(e) and str(e) not in str(r["sentence_text"]): issues.append((source, sid, f"slot {k}: evidence not verbatim: '{e}'"))
            if a in asp and asp[a] != s: issues.append((source, sid, f"aspect '{a}' used twice with different sentiments"))
            asp[a] = s; ev[a] = None if pd.isna(e) else e
        fs = r.get("food_safety_flag"); ch = r.get("service_channel")
        out[sid] = {"aspects": asp, "evidence": ev, "fs": 0 if pd.isna(fs) else int(fs), "channel": "unknown" if pd.isna(ch) else ch,
                    "amb": 0 if pd.isna(r.get("ambiguity_flag")) else int(r.get("ambiguity_flag")),
                    "notes": r.get("annotator_notes")}
    return out, issues

def kappa(a, b):
    a, b = list(a), list(b)
    if len(a) == 0: return np.nan
    if len(set(a) | set(b)) == 1: return np.nan  # both constant & identical -> undefined
    return cohen_kappa_score(a, b)

def compare(X, Y, nx, ny, aspects):
    ids = sorted(set(X) & set(Y)); res = {"pair": f"{nx} vs {ny}", "n_sentences": len(ids)}
    if not ids: return res, pd.DataFrame(), pd.DataFrame()
    per = []
    xa_all, ya_all = [], []
    for a in aspects:
        xa = [int(a in X[i]["aspects"]) for i in ids]; ya = [int(a in Y[i]["aspects"]) for i in ids]
        xa_all += xa; ya_all += ya
        per.append({"pair": res["pair"], "aspect": a, "n_first": sum(xa), "n_second": sum(ya),
                    "agreement_pct": round(100 * np.mean(np.array(xa) == np.array(ya)), 1), "kappa": kappa(xa, ya)})
    per = pd.DataFrame(per)
    res["aspect_presence_kappa_pooled"] = kappa(xa_all, ya_all)
    res["exact_aspect_set_match_pct"] = round(100 * np.mean([set(X[i]["aspects"]) == set(Y[i]["aspects"]) for i in ids]), 1)
    pairs = [(X[i]["aspects"][a], Y[i]["aspects"][a]) for i in ids for a in X[i]["aspects"] if a in Y[i]["aspects"] and a not in NO_SENT]
    res["n_shared_aspects_for_sentiment"] = len(pairs)
    res["sentiment_agreement_pct"] = round(100 * np.mean([p == q for p, q in pairs]), 1) if pairs else np.nan
    res["sentiment_kappa"] = kappa([p for p, _ in pairs], [q for _, q in pairs])
    res["food_safety_kappa"] = kappa([X[i]["fs"] for i in ids], [Y[i]["fs"] for i in ids])
    res["service_channel_agreement_pct"] = round(100 * np.mean([X[i]["channel"] == Y[i]["channel"] for i in ids]), 1)
    dis = [{"sample_id": i, f"{nx}_labels": fmt(X[i]), f"{ny}_labels": fmt(Y[i])} for i in ids if fmt(X[i]) != fmt(Y[i])]
    return res, per, pd.DataFrame(dis)

def fmt(L):
    return " ; ".join(f"{a} [{s or '-'}]" for a, s in sorted(L["aspects"].items())) + f" | fs={L['fs']} | {L['channel']}"

# ---------------------------------------------------------------- load
review = pd.read_excel(args.pilot, sheet_name="Review")
llm_df = pd.read_excel(args.pilot, sheet_name="LLM labels (original)")
design = pd.read_excel(args.pilot, sheet_name="Sample design (open AFTER)")
aspect_list = pd.read_excel(args.pilot, sheet_name="Lists")["aspects"].dropna().tolist() if "Lists" in pd.ExcelFile(args.pilot).sheet_names else None
verified = review[review.verified == 1]
A, iA = to_long(verified, "A")
LLM, iL = to_long(llm_df, "LLM")
B, iB = {}, []
if Path(args.b_file).exists():
    bdf = pd.read_excel(args.b_file, sheet_name="Annotate")
    bdf = bdf[bdf[["aspect_1", "aspect_2", "aspect_3"]].notna().any(axis=1)]
    B, iB = to_long(bdf, "B")
aspects = aspect_list or sorted({a for D in (A, B, LLM) for L in D.values() for a in L["aspects"]})
print(f"Verified by A: {len(A)}/200 | labelled by B: {len(B)}/40 | LLM rows: {len(LLM)}")
issues = pd.DataFrame(iA + iB, columns=["source", "sample_id", "issue"])
print(f"Validation issues (A+B): {len(issues)}")
if args.dry_run: sys.exit(0)
if not A:
    print("Nothing verified yet - no gold written. Set verified = 1 on reviewed rows and re-run."); sys.exit(0)

# ---------------------------------------------------------------- gold export (A, verified only)
meta = design.set_index("sample_id")
txt = review.set_index("sample_id")["sentence_text"]
gold = []
for sid, L in A.items():
    m = meta.loc[sid]
    for a, s in L["aspects"].items():
        gold.append({"sample_id": sid, "sentence_id": m.sentence_id, "review_id": m.review_id, "restaurant_id": m.restaurant_id,
                     "restaurant_name": m.restaurant_name, "review_stars": m.review_stars, "operational_peer_group": m.operational_peer_group,
                     "cuisine_cluster": m.cuisine_cluster, "stratum": m.stratum, "sentence_text": txt[sid], "aspect": a, "sentiment": s,
                     "evidence": L["evidence"].get(a), "service_channel": L["channel"], "food_safety_flag": L["fs"],
                     "ambiguity_flag": L["amb"], "annotator_notes": L["notes"],
                     "llm_same_aspect": int(a in LLM.get(sid, {"aspects": {}})["aspects"]),
                     "llm_same_aspect_and_sentiment": int(LLM.get(sid, {"aspects": {}})["aspects"].get(a, "<none>") == s),
                     "label_source": "LLM pre-label, human verified", "codebook_version": "1.2"})
gold = pd.DataFrame(gold)
out = Path(args.out_dir); out.mkdir(parents=True, exist_ok=True)
gold.to_csv(out / "gold_absa_pilot_v1.csv", index=False, encoding="utf-8-sig")

# ---------------------------------------------------------------- agreement
summ, per_all, dis_all = [], [], {}
for X, Y, nx, ny in [(A, B, "A", "B"), (LLM, A, "LLM", "A"), (LLM, B, "LLM", "B")]:
    r, p, d = compare(X, Y, nx, ny, aspects); summ.append(r)
    if len(p): per_all.append(p)
    if len(d): dis_all[f"{nx} vs {ny}"] = d
summ = pd.DataFrame(summ)
# LLM vs A precision/recall per aspect (A = reference)
ids = sorted(set(A) & set(LLM)); prf = []
for a in aspects:
    y = [int(a in A[i]["aspects"]) for i in ids]; p = [int(a in LLM[i]["aspects"]) for i in ids]
    if sum(y) + sum(p) == 0: continue
    pr, rc, f1, _ = precision_recall_fscore_support(y, p, average="binary", zero_division=0)
    prf.append({"aspect": a, "n_A": sum(y), "n_LLM": sum(p), "precision": round(pr, 3), "recall": round(rc, 3), "f1": round(f1, 3)})
changed = np.mean([fmt(A[i]) != fmt(LLM[i]) for i in ids]) if ids else np.nan
summ["note"] = ["Human reliability - must reach kappa >= 0.70 before scaling",
                f"Reviewer changed {changed:.0%} of verified rows (anchoring inflates this agreement)",
                "Honest LLM quality vs a blind human"]
with pd.ExcelWriter(out / "pilot_agreement_report.xlsx") as w:
    summ.to_excel(w, sheet_name="Summary", index=False)
    (pd.concat(per_all) if per_all else pd.DataFrame()).to_excel(w, sheet_name="Per-aspect kappa", index=False)
    pd.DataFrame(prf).to_excel(w, sheet_name="LLM vs A (P-R-F1)", index=False)
    for k, d in dis_all.items(): d.to_excel(w, sheet_name=f"Disagree {k}"[:31], index=False)
    issues.to_excel(w, sheet_name="Validation issues", index=False)
    gold.groupby(["aspect", "sentiment"], dropna=False).size().unstack(fill_value=0).to_excel(w, sheet_name="Gold label counts")
print(summ.drop(columns=["note"]).to_string(index=False))
print(f"Gold rows: {len(gold)} from {len(A)} verified sentences -> {out / 'gold_absa_pilot_v1.csv'}")
