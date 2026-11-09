# -*- coding: utf-8 -*-
"""
04b_build_absa_units.py  (5 Nov 2026)
Refines sentence segmentation into ABSA units WITHOUT changing review_sentences.parquet, so sentence_ids,
BERTopic runs and the pilot stay valid.

Problem: ~4% of 'sentences' are several sentences glued together by '..' or '…' (original line breaks
turned into dots during cleaning), e.g. 'Atmosphere was lacking, floor was sticky.. Food was good ...'.
Rule (conservative): split only where 2+ dots or '…' are followed by an UPPERCASE letter
  - '<2+ dots><spaces><Upper>'  or  '<exactly 2 dots><Upper>'  or  '…<spaces><Upper>'
Lowercase continuations ('Went today during lunch.. was pleasantly surprised') are NOT split.

Output (04. Outputs_NLP/):
  absa_units.parquet   one row per unit: unit_id = <sentence_id>-u<k>; parent sentence_id kept;
                       unit_char_start/end relative to sentence_text; all sentence metadata inherited;
                       run1_topic / run23_topic inherited from the parent sentence (NaN if not in BERTopic)
  absa_units_qc.xlsx   summary, split-rule counts, 60 random split sentences for eyeballing
"""
import os, re
from pathlib import Path
import pandas as pd

BASE = Path(os.environ.get("PTBO_BASE", Path(__file__).resolve().parent.parent))
NLP, BT = BASE / "04. Outputs_NLP", BASE / "05. Outputs_BERTopic"
SPLIT_RX = re.compile(r"(?:\.{2,}\s+|(?<!\.)\.\.(?!\.)|…\s*)(?=[A-Z])")

s = pd.read_parquet(NLP / "review_sentences.parquet")
rows = []
for x in s.itertuples(index=False):
    text = x.sentence_text
    cuts = [m.end() for m in SPLIT_RX.finditer(text)]
    bounds = [0] + cuts + [len(text)]
    pieces = []
    for a, b in zip(bounds[:-1], bounds[1:]):
        seg = text[a:b]
        lead = len(seg) - len(seg.lstrip()); trail = len(seg.rstrip())
        st, en = a + lead, a + trail
        if en > st: pieces.append((st, en))
    # merge pieces that carry no word (e.g. stray punctuation) into the previous piece
    merged = []
    for st, en in pieces:
        if merged and not re.search(r"[A-Za-z0-9]", text[st:en]): merged[-1] = (merged[-1][0], en)
        else: merged.append((st, en))
    for k, (st, en) in enumerate(merged, 1):
        rows.append({"unit_id": f"{x.sentence_id}-u{k}", "sentence_id": x.sentence_id, "unit_position": k,
                     "n_units_in_sentence": len(merged), "unit_text": text[st:en],
                     "unit_char_start": st, "unit_char_end": en,
                     "split_rule": "dot_linebreak" if len(merged) > 1 else "none"})
u = pd.DataFrame(rows)
meta_cols = [c for c in s.columns if c not in ("sentence_text",)]
u = u.merge(s[meta_cols + ["sentence_text"]], on="sentence_id", how="left")
u["unit_word_count"] = u.unit_text.str.split().str.len()
# BERTopic links from the parent sentence
r1 = pd.read_parquet(BT / "run1_all/topics.parquet")[["sentence_id", "topic"]].rename(columns={"topic": "run1_topic"})
r23 = pd.concat([pd.read_parquet(BT / f"{d}/topics.parquet").assign(run23=n) for d, n in
                 [("run2_negative", "Run2_Negative"), ("run3_positive", "Run3_Positive")]])[["sentence_id", "topic", "run23"]].rename(columns={"topic": "run23_topic"})
u = u.merge(r1, on="sentence_id", how="left").merge(r23, on="sentence_id", how="left")

# ---- QC
assert u.unit_id.is_unique
assert (u.apply(lambda r: r.sentence_text[r.unit_char_start:r.unit_char_end] == r.unit_text, axis=1)).all()
assert set(u.sentence_id) == set(s.sentence_id)
lost = (s.set_index("sentence_id").sentence_text.str.replace(r"\W", "", regex=True)
        != u.groupby("sentence_id").unit_text.apply(lambda t: "".join(t)).str.replace(r"\W", "", regex=True)
        .reindex(s.sentence_id).values)
assert lost.sum() == 0, f"text lost in {lost.sum()} sentences"
u.drop(columns=["sentence_text"]).to_parquet(NLP / "absa_units.parquet", index=False)

split_s = u[u.n_units_in_sentence > 1].sentence_id.unique()
summary = pd.DataFrame([
    ("sentences in review_sentences.parquet", len(s)),
    ("ABSA units", len(u)),
    ("sentences split", len(split_s)),
    ("share of sentences split (%)", round(100 * len(split_s) / len(s), 2)),
    ("units coming from split sentences", int((u.n_units_in_sentence > 1).sum())),
    ("max units in one sentence", int(u.n_units_in_sentence.max())),
    ("units with 1-2 words created by splitting (kept, check)", int(((u.unit_word_count <= 2) & (u.n_units_in_sentence > 1)).sum())),
    ("pilot rows affected (P040, P110, P184 ...) - pilot stays sentence-level", "see sample sheet"),
], columns=["metric", "value"])
dist = u.drop_duplicates("sentence_id").n_units_in_sentence.value_counts().sort_index().rename_axis("units_per_sentence").reset_index(name="n_sentences")
samp = u[u.sentence_id.isin(pd.Series(split_s).sample(60, random_state=42))][["sentence_id", "unit_id", "unit_text", "sentence_text"]]
with pd.ExcelWriter(NLP / "absa_units_qc.xlsx") as w:
    summary.to_excel(w, sheet_name="Summary", index=False); dist.to_excel(w, sheet_name="Units per sentence", index=False)
    samp.to_excel(w, sheet_name="60 split sentences", index=False)
print(summary.to_string(index=False)); print(dist.to_string(index=False))
