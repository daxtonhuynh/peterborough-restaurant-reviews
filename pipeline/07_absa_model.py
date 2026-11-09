# -*- coding: utf-8 -*-
"""
07_absa_model.py  (5 Nov 2026)  -  Aspect detection + aspect sentiment, evaluated on the 200-sentence SILVER pilot.

Labels: the pilot labels are LLM pre-labels (Claude, codebook v1.1/1.2) bulk-approved by the project lead without row-level
verification (+ 1 manual edit P011 + 3 codebook-v1.2 fixes). They are SILVER, not gold; no inter-annotator kappa exists.

No transformer models are reachable from the workspace (Hugging Face blocked), so:
  Aspect model (Model A): weak supervision = cue lexicon (absa_lexicon.py) + BERTopic topic->aspect mapping (high/medium
     certainty topics, unsplit sentences) -> one-vs-rest TF-IDF logistic regression. Final = lexicon OR classifier.
  Sentiment (Model B): VADER (+ restaurant-domain lexicon), scoped to the contrast clause holding the aspect cue, overridden
     by explicit domain rules for SPEED / PORT / FRESH / PRICE. Star ratings are NEVER used (avoids circularity with the
     rating-driver analysis).
Evaluation: pilot split into DEV (odd sample numbers, used to choose the variant) and TEST (even, reported).
Outputs (07. Outputs_ABSA/): absa_model_evaluation.xlsx ; models/ (vectoriser + classifiers, joblib)
         06. Outputs_Annotation/silver_absa_pilot_v1.csv
"""
import os, sys, re, json
from pathlib import Path
import numpy as np, pandas as pd, joblib
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import precision_recall_fscore_support, accuracy_score, f1_score
from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer
sys.path.insert(0, str(Path(__file__).resolve().parent))
from absa_lexicon import *

BASE = Path(os.environ.get("PTBO_BASE", Path(__file__).resolve().parent.parent))
OUT = BASE / "07. Outputs_ABSA"; (OUT / "models").mkdir(parents=True, exist_ok=True)
BT = BASE / "05. Outputs_BERTopic"

# ------------------------------------------------------------------ 1. silver pilot
rev = pd.read_excel(BT / "annotation_pilot_v3_prelabelled.xlsx", sheet_name="Review")
des = pd.read_excel(BT / "annotation_pilot_v3_prelabelled.xlsx", sheet_name="Sample design (open AFTER)")
FIX = {("P105","SPEED"): ("SPEED","Neutral"), ("P134","SPEED"): ("SPEED","Neutral"), ("P111","SPEED"): ("STAFF","Negative")}
sil = []
for r in rev.itertuples(index=False):
    r = r._asdict()
    for k in (1, 2, 3):
        a = r[f"aspect_{k}"]
        if pd.isna(a): continue
        code, s = CODE_OF[a], (None if pd.isna(r[f"sentiment_{k}"]) else r[f"sentiment_{k}"])
        fix = FIX.get((r["sample_id"], code))
        if fix: code, s = fix
        sil.append({"sample_id": r["sample_id"], "sentence_id": r["sentence_id"], "sentence_text": r["sentence_text"], "aspect": code,
                    "aspect_name": NAME[code], "sentiment": s, "evidence": r[f"evidence_{k}"], "food_safety_flag": int(r["food_safety_flag"]),
                    "service_channel": r["service_channel"],
                    "label_source": "LLM pre-label (Claude, codebook v1.1) bulk-approved by project lead 2026-11-05; not row-verified" +
                                    ("; edited by project lead" if r["sample_id"] == "P011" else "") +
                                    ("; codebook v1.2 fix" if fix else "")})
sil = pd.DataFrame(sil).merge(des[["sample_id","stratum","review_stars","restaurant_id"]], on="sample_id")
(BASE / "06. Outputs_Annotation").mkdir(exist_ok=True)
sil.to_csv(BASE / "06. Outputs_Annotation/silver_absa_pilot_v1.csv", index=False, encoding="utf-8-sig")
pilot_sents = set(sil.sentence_id)
num = sil.drop_duplicates("sample_id").set_index("sentence_id").sample_id.str[1:].astype(int)
split_of = {sid: ("DEV" if n % 2 else "TEST") for sid, n in num.items()}

# ------------------------------------------------------------------ 2. units + weak labels
U = pd.read_parquet(BASE / "04. Outputs_NLP/absa_units.parquet")
tm = pd.read_excel(BT / "topic_to_aspect_mapping_v.1.2.xlsx", sheet_name="Topic Mapping v1.1")
tm = tm[(tm.source_run == "Run1_All") & tm.aspect_certainty.isin(["high", "medium"])]
topic_code = {int(t): CODE_OF[p] for t, p in zip(tm.topic_id, tm.primary_aspect)}
def lex_hits(text):
    t = CANT_WAIT.sub(" cantwait ", text)
    return {c: m.start() for c in CODES if (m := LEX_RX[c].search(t))}
U["lex"] = U.unit_text.apply(lex_hits)
def weak(row):
    s = set(row.lex)
    if row.n_units_in_sentence == 1 and pd.notna(row.run1_topic) and row.run1_topic in topic_code:
        c = topic_code[row.run1_topic]
        if c in CODES: s.add(c)
    return s
U["weak"] = U.apply(weak, axis=1)
U["is_pilot"] = U.sentence_id.isin(pilot_sents)
train = U[~U.is_pilot]

# ------------------------------------------------------------------ 3. classifier
vec = TfidfVectorizer(ngram_range=(1, 2), min_df=3, max_df=0.5, sublinear_tf=True, lowercase=True, max_features=60000)
Xtr = vec.fit_transform(train.unit_text); Xall = vec.transform(U.unit_text)
clf, P = {}, {}
for c in CODES:
    y = train.weak.apply(lambda s: c in s).astype(int).values
    if y.sum() < 20: continue
    m = LogisticRegression(C=4.0, max_iter=2000, class_weight="balanced"); m.fit(Xtr, y)
    clf[c] = m; P[c] = m.predict_proba(Xall)[:, 1]
P = pd.DataFrame(P, index=U.index)
joblib.dump({"vectorizer": vec, "classifiers": clf}, OUT / "models/aspect_model_tfidf_logreg.joblib")

# ------------------------------------------------------------------ 4. sentiment
va = SentimentIntensityAnalyzer(); va.lexicon.update(VADER_ADD)
def polarity(x, thr=0.05):
    c = va.polarity_scores(x)["compound"]
    return ("Positive" if c >= thr else "Negative" if c <= -thr else "Neutral"), c
def scope(text, pos):
    if pos is None or not CONTRAST.search(text): return text
    cuts = [0] + [m.start() for m in CONTRAST.finditer(text)] + [len(text)]
    for a, b in zip(cuts[:-1], cuts[1:]):
        if a <= pos < b: return text[a:b]
    return text
def aspect_sent(text, code, pos, mode="rules"):
    sc = scope(text, pos) if mode != "vader_unit" else text
    if mode == "rules":
        t = CANT_WAIT.sub(" cantwait ", sc)
        R = RULES_RX.get(code, {})
        if code == "SPEED" and R["accept"].search(t): return "Neutral", 0.0
        if "neg_first" in R and R["neg_first"].search(t): return "Negative", -0.6
        p = bool(R["pos"].search(t)) if "pos" in R else False
        n = bool(R["neg"].search(t)) if "neg" in R else False
        if p and not n: return "Positive", 0.6
        if n and not p: return "Negative", -0.6
        if "default" in R and not p: return R["default"], -0.6
        if code == "SPEED" and not p and not n and R["neutral_only"].search(t): return "Neutral", 0.0
        if GENERIC_NEG.search(t): return "Negative", -0.5
    return polarity(sc)

def predict(variant, rows, thr=0.5):
    """variant: topic | lexicon | clf | lex+clf ; returns {unit_idx: {code: pos_or_None}}"""
    out = {}
    for i, r in rows.iterrows():
        a = {}
        if variant == "topic":
            if r.n_units_in_sentence == 1 and pd.notna(r.run1_topic) and r.run1_topic in topic_code and topic_code[r.run1_topic] in CODES:
                a[topic_code[r.run1_topic]] = None
        if variant in ("lexicon", "lex+clf"): a.update({c: p for c, p in r.lex.items()})
        if variant in ("clf", "lex+clf"):
            for c in P.columns:
                if P.at[i, c] >= thr and c not in a: a[c] = r.lex.get(c)
        out[i] = a
    return out

# ------------------------------------------------------------------ 5. evaluation on silver pilot
PU = U[U.is_pilot]
gold = sil[~sil.aspect.isin(["NA", "SAFETY"])].groupby("sentence_id").apply(lambda g: dict(zip(g.aspect, g.sentiment))).to_dict()
for s in pilot_sents: gold.setdefault(s, {})
def to_sentence(pred):
    agg = {}
    for i, a in pred.items():
        sid = U.at[i, "sentence_id"]; agg.setdefault(sid, {})
        for c, pos in a.items(): agg[sid].setdefault(c, []).append((i, pos))
    return agg
def eval_aspects(agg, part):
    sids = [s for s in pilot_sents if part == "ALL" or split_of[s] == part]
    Y = np.array([[int(c in gold[s]) for c in CODES] for s in sids]); Yh = np.array([[int(c in agg.get(s, {})) for c in CODES] for s in sids])
    p, r, f, _ = precision_recall_fscore_support(Y, Yh, average="micro", zero_division=0)
    keep = Y.sum(0) >= 3
    mf = f1_score(Y[:, keep], Yh[:, keep], average="macro", zero_division=0)
    per = precision_recall_fscore_support(Y, Yh, average=None, zero_division=0)
    return dict(micro_P=p, micro_R=r, micro_F1=f, macro_F1_aspects_n3=mf), per, Y.sum(0)
rows_eval, per_rows = [], []
cands = [("topic", 0.5), ("lexicon", 0.5), ("clf", 0.5), ("clf", 0.7), ("lex+clf", 0.5), ("lex+clf", 0.7), ("lex+clf", 0.85)]
for v, thr in cands:
    agg = to_sentence(predict(v, PU, thr))
    for part in ("DEV", "TEST", "ALL"):
        m, per, sup = eval_aspects(agg, part)
        rows_eval.append({"variant": v, "threshold": thr, "split": part, **{k: round(x, 3) for k, x in m.items()}})
ev = pd.DataFrame(rows_eval)
best = ev[ev.split == "DEV"].sort_values("micro_F1", ascending=False).iloc[0]
BV, BT_ = best.variant, best.threshold
agg = to_sentence(predict(BV, PU, BT_))
m, per, sup = eval_aspects(agg, "TEST"); mA, perA, supA = eval_aspects(agg, "ALL")
per_df = pd.DataFrame({"aspect": [NAME[c] for c in CODES], "silver_support_ALL": supA, "precision_ALL": perA[0].round(3),
                       "recall_ALL": perA[1].round(3), "f1_ALL": perA[2].round(3), "silver_support_TEST": sup, "f1_TEST": per[2].round(3)})
# sentiment on correctly detected aspects
srows = []
for mode in ("vader_unit", "vader_scoped", "rules"):
    for part in ("DEV", "TEST", "ALL"):
        yt, yp = [], []
        for sid, a in agg.items():
            if part != "ALL" and split_of[sid] != part: continue
            for c, lst in a.items():
                g = gold[sid].get(c)
                if g in (None, "Mixed") or c not in gold[sid]: continue
                labs = [aspect_sent(U.at[i, "unit_text"], c, pos, mode)[0] for i, pos in lst]
                pr = "Negative" if "Negative" in labs and "Positive" not in labs else "Positive" if "Positive" in labs and "Negative" not in labs else labs[0]
                yt.append(g); yp.append(pr)
        srows.append({"sentiment_method": mode, "split": part, "n_pairs": len(yt), "accuracy": round(accuracy_score(yt, yp), 3),
                      "macro_F1": round(f1_score(yt, yp, average="macro", zero_division=0), 3),
                      "F1_Negative": round(f1_score(yt, yp, labels=["Negative"], average="macro", zero_division=0), 3),
                      "F1_Positive": round(f1_score(yt, yp, labels=["Positive"], average="macro", zero_division=0), 3)})
sev = pd.DataFrame(srows)
# food-safety flag
fs_gold = sil.drop_duplicates("sample_id").set_index("sentence_id").food_safety_flag
fs_pred = PU.groupby("sentence_id").unit_text.apply(lambda t: int(any(SAFETY_YES.search(x) and not SAFETY_NO.search(x) for x in t)))
fsm = precision_recall_fscore_support(fs_gold.reindex(fs_pred.index), fs_pred, average="binary", zero_division=0)
cfg = {"aspect_variant": BV, "threshold": float(BT_), "sentiment_method": "rules", "food_safety": "regex v1.2"}
json.dump(cfg, open(OUT / "models/chosen_config.json", "w"), indent=2)
with pd.ExcelWriter(OUT / "absa_model_evaluation.xlsx") as w:
    pd.DataFrame([("Evaluation set", "200 pilot sentences, SILVER labels (LLM, bulk-approved, not row-verified) - metrics are indicative"),
                  ("Selection", "variant chosen on DEV (odd P-numbers); TEST (even) reported as the headline"),
                  ("Chosen aspect variant", f"{BV} @ {BT_}"), ("Chosen sentiment method", "rules (VADER + scope + domain rules)"),
                  ("Food-safety flag P/R/F1 (ALL)", f"{fsm[0]:.2f} / {fsm[1]:.2f} / {fsm[2]:.2f}")], columns=["item", "value"]).to_excel(w, sheet_name="Summary", index=False)
    ev.to_excel(w, sheet_name="Aspect detection", index=False)
    per_df.to_excel(w, sheet_name="Per-aspect (chosen)", index=False)
    sev.to_excel(w, sheet_name="Aspect sentiment", index=False)
print(ev[ev.split != "ALL"].to_string(index=False)); print("CHOSEN", BV, BT_)
print(per_df.to_string(index=False)); print(sev.to_string(index=False)); print("food safety P/R/F1", [round(x, 2) for x in fsm[:3]])
# keep state for inference
U.drop(columns=["lex","weak"]).assign(**{f"p_{c}": P[c] for c in P.columns}).to_parquet(OUT / "_units_with_probs.parquet", index=False)
