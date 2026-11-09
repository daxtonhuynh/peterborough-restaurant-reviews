# -*- coding: utf-8 -*-
"""
09a_rating_drivers.py (5 Nov 2026) - which aspects are ASSOCIATED with ratings (not causal).
Data: 5,165 text reviews with ABSA features (07. Outputs_ABSA/absa_review_features.parquet).
Models:
  M1 ordered logit: stars ~ aspect positive/negative dummies + log(words) + year + restaurant fixed effects
  M2 logit: P(1-2 stars) ~ same; cluster-robust SEs by restaurant; average marginal effects (percentage points)
  M3 gradient boosting (sklearn) for P(1-2 stars) + permutation importance (secondary check)
  plus P(1-2 stars) by number of negative aspects, and M2 by peer group for the main aspects.
Output: 08. Outputs_Analysis/rating_driver_results.xlsx, rating_driver_ame.csv (used by 09b)
"""
import os, sys, warnings
from pathlib import Path
import numpy as np, pandas as pd, statsmodels.api as sm
from statsmodels.miscmodels.ordinal_model import OrderedModel
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.inspection import permutation_importance
from sklearn.model_selection import train_test_split
from sklearn.metrics import roc_auc_score
warnings.filterwarnings("ignore")
BASE = Path(os.environ.get("PTBO_BASE", Path(__file__).resolve().parent.parent)); OUT = BASE / "08. Outputs_Analysis"
sys.path.insert(0, str(Path(__file__).resolve().parent)); from absa_lexicon import SHORT
F = pd.read_parquet(BASE / "07. Outputs_ABSA/absa_review_features.parquet").dropna(subset=["review_stars"])
OPS = ["FOOD","FRESH","PORT","MENU","PRICE","STAFF","SPEED","ACC","AMB","CLEAN","LOC","DELIV","DIET","COMPL"]
cols = [f"{c}_{s}" for c in OPS for s in ("pos","neg") if F[f"{c}_{s}"].sum() >= 15]
F["log_words"] = np.log1p(F.text_length_words.fillna(0)); F["year_c"] = F.review_year - F.review_year.median()
X = pd.concat([F[cols + ["log_words","year_c"]], pd.get_dummies(F.restaurant_id, prefix="R", drop_first=True, dtype=float)], axis=1).astype(float)
y = F.review_stars.astype(int)
lab = lambda c: f"{SHORT[c.rsplit('_',1)[0]]} - {'negative' if c.endswith('neg') else 'positive'} mention" if c[-4:] in ("_neg","_pos") else c

# M1 ordered logit
m1 = OrderedModel(y, X, distr="logit").fit(method="bfgs", maxiter=3000, disp=False)
ci = m1.conf_int()
r1 = pd.DataFrame({"term": [lab(c) for c in cols], "log_odds": m1.params[cols].round(3), "odds_ratio": np.exp(m1.params[cols]).round(2),
                   "OR_95CI_low": np.exp(ci.loc[cols, 0]).round(2), "OR_95CI_high": np.exp(ci.loc[cols, 1]).round(2), "p_value": m1.pvalues[cols].map(lambda p: f"{p:.3g}"),
                   "n_reviews_with_feature": [int(F[c].sum()) for c in cols]}).sort_values("log_odds")
# M2 low-rating logit, cluster-robust
ylow = (y <= 2).astype(int)
Xc = sm.add_constant(X)
m2 = sm.Logit(ylow, Xc).fit(disp=False, maxiter=500, method="newton", cov_type="cluster", cov_kwds={"groups": pd.factorize(F.restaurant_id)[0]})
me = m2.get_margeff(at="overall", dummy=True).summary_frame()
me.index = Xc.columns[1:]
r2 = pd.DataFrame({"term": [lab(c) for c in cols], "feature": cols, "AME_pp_low_rating": (100 * me.loc[cols, "dy/dx"]).round(1),
                   "AME_95CI_low": (100 * me.loc[cols, "Conf. Int. Low"]).round(1), "AME_95CI_high": (100 * me.loc[cols, "Cont. Int. Hi."]).round(1),
                   "p_value": me.loc[cols, "Pr(>|z|)"].map(lambda p: f"{p:.3g}"), "n_reviews_with_feature": [int(F[c].sum()) for c in cols]}).sort_values("AME_pp_low_rating", ascending=False)
# descriptive: n negative aspects
nneg = F.assign(k=F.n_neg_aspects.clip(upper=3).map({0:"0",1:"1",2:"2",3:"3+"})).groupby("k").agg(n_reviews=("review_id","size"),
        pct_1_2_stars=("review_stars", lambda s: round(100 * (s <= 2).mean(), 1)), mean_stars=("review_stars", lambda s: round(s.mean(), 2))).reset_index()
# M3 GBM + permutation importance
Xg = pd.concat([F[cols + ["log_words","year_c"]], pd.get_dummies(F.operational_peer_group, prefix="PG", dtype=float)], axis=1).astype(float)
Xtr, Xte, ytr, yte = train_test_split(Xg, ylow, test_size=0.25, stratify=ylow, random_state=42)
gb = HistGradientBoostingClassifier(max_iter=300, learning_rate=0.05, max_depth=4, random_state=42).fit(Xtr, ytr)
auc = roc_auc_score(yte, gb.predict_proba(Xte)[:, 1])
pi = permutation_importance(gb, Xte, yte, scoring="roc_auc", n_repeats=20, random_state=42)
r3 = pd.DataFrame({"feature": [lab(c) for c in Xg.columns], "auc_drop_mean": pi.importances_mean.round(4), "auc_drop_sd": pi.importances_std.round(4)}).sort_values("auc_drop_mean", ascending=False).head(20)
# by peer group (main negatives)
main = [c for c in ["FOOD_neg","FRESH_neg","STAFF_neg","SPEED_neg","PRICE_neg","ACC_neg","PORT_neg"] if c in cols]
pg = []
for g, d in F.groupby("operational_peer_group"):
    Xp = sm.add_constant(pd.concat([d[main + ["log_words"]]], axis=1).astype(float)); yp = (d.review_stars <= 2).astype(int)
    try:
        mp = sm.Logit(yp, Xp).fit(disp=False, maxiter=200); mep = mp.get_margeff(at="overall", dummy=True).summary_frame(); mep.index = Xp.columns[1:]
        for c in main: pg.append({"peer_group": g, "n_reviews": len(d), "term": lab(c), "AME_pp_low_rating": round(100 * mep.loc[c, "dy/dx"], 1), "p_value": f"{mep.loc[c, 'Pr(>|z|)']:.3g}", "n_with_feature": int(d[c].sum())})
    except Exception as e:
        pg.append({"peer_group": g, "n_reviews": len(d), "term": "model failed", "AME_pp_low_rating": None, "p_value": str(e)[:60], "n_with_feature": None})
pg = pd.DataFrame(pg)
fit = pd.DataFrame([("M1 ordered logit: n reviews", len(F)), ("M1 pseudo R2 (McFadden)", round(m1.prsquared, 3)),
                    ("M2 low-rating logit: base rate of 1-2 stars", f"{ylow.mean():.1%}"), ("M2 pseudo R2", round(m2.prsquared, 3)),
                    ("M3 gradient boosting test AUC", round(auc, 3)),
                    ("Controls", "log(words), year, restaurant fixed effects (M1, M2); peer group (M3)"),
                    ("Reading", "Associations only. AME = change in probability of a 1-2 star rating when the review contains that mention, other features held at observed values.")],
                   columns=["item", "value"])
with pd.ExcelWriter(OUT / "rating_driver_results.xlsx") as w:
    fit.to_excel(w, sheet_name="Model fit", index=False); r2.drop(columns="feature").to_excel(w, sheet_name="Low-rating AME (M2)", index=False)
    r1.to_excel(w, sheet_name="Ordered logit (M1)", index=False); nneg.to_excel(w, sheet_name="Neg aspects vs rating", index=False)
    r3.to_excel(w, sheet_name="GBM importance (M3)", index=False); pg.to_excel(w, sheet_name="By peer group", index=False)
r2.to_csv(OUT / "rating_driver_ame.csv", index=False)
print(fit.to_string(index=False)); print(r2.head(16).to_string(index=False)); print(nneg.to_string(index=False)); print(r3.head(8).to_string(index=False))
