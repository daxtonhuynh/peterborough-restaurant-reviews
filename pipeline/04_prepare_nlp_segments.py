"""
04_prepare_nlp_segments.py
==========================
Peterborough Restaurant Google Reviews — NLP Preparation Pipeline
Phase 4 / Step 6: Language Resolution and Hierarchical Text Segmentation

Goal:
    Convert NLP-eligible reviews into validated sentence-level and clause-level
    analytical units while preserving review context, language information,
    and full traceability back to the source review.

Architecture:
    Review (source unit, metadata carrier)
      └── Sentence (BERTopic corpus unit, context anchor)
            └── Clause  (ABSA analytical unit, sentiment target)

Design principles enforced:
    - Segmentation logic NEVER depends on review_stars (no preprocessing bias)
    - review_text_raw is NEVER modified
    - Every segment traces back to review_id + char offsets
    - Segments are flagged, never auto-deleted
    - Language metadata from pipeline 01 is the primary source;
      detector runs only as validation/fallback
    - spaCy dependency parse verifies conjunctions before clause splitting
      (spaCy-assisted rule-based, not pure regex)

Inputs:
    reviews_analysis_ready.parquet   (output of pipeline 01)

Outputs:
    04. Outputs_NLP/
    ├── review_sentences.parquet          BERTopic corpus unit
    ├── review_clauses.parquet            ABSA analytical unit
    ├── review_segments.parquet           Combined (sentences + clauses), full schema
    ├── segmentation_summary.xlsx         QC reconciliation + statistics
    ├── segmentation_manual_validation.xlsx  Stratified samples for human review
    └── segmentation_flagged_records.xlsx    Edge cases and anomalies

spaCy model:
    Prefers en_core_web_md (has dependency vectors).
    Falls back to en_core_web_sm automatically if md is not installed.
    Install on your machine:
        python -m spacy download en_core_web_md

Dependencies (install on your machine):
    pip install spacy langdetect pandas pyarrow openpyxl tqdm
    python -m spacy download en_core_web_md
"""

import os
import re
import hashlib
import warnings
import logging
from datetime import datetime, timezone
from typing import Optional

import numpy as np
import pandas as pd
from tqdm import tqdm

warnings.filterwarnings("ignore")
logging.basicConfig(level=logging.INFO,
                    format="%(asctime)s  %(levelname)s  %(message)s",
                    datefmt="%H:%M:%S")
log = logging.getLogger(__name__)

# ─── Paths ────────────────────────────────────────────────────────────────────
# Workspace root (raw files + numbered output folders): set PTBO_BASE, or it defaults to the repository root.
PROJECT_DIR = os.environ.get("PTBO_BASE", os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
PARQUET_IN  = os.path.join(PROJECT_DIR, "02. Outputs_Data Mining", "reviews_analysis_ready.parquet")
if not os.path.exists(PARQUET_IN):  # earlier layout kept the file at the workspace root
    PARQUET_IN = os.path.join(PROJECT_DIR, "reviews_analysis_ready.parquet")
OUT_DIR     = os.path.join(PROJECT_DIR, "04. Outputs_NLP")
os.makedirs(OUT_DIR, exist_ok=True)

# ─── Segmentation constants ───────────────────────────────────────────────────

# Language detection
SHORT_TEXT_THRESHOLD   = 4    # words; too short for reliable language detection
LANG_CONFIDENCE_THRESHOLD = 0.80  # minimum confidence to trust detector override

# Sentence segmentation
MIN_SENTENCE_WORDS = 1    # flag but keep: "Never again." has ABSA value
MAX_SENTENCE_WORDS = 150  # flag as unusually long; not split automatically

# Clause splitting
# Contrast markers always trigger a split attempt (highest-confidence conjunctions)
CONTRAST_MARKERS = {
    "but", "however", "although", "though", "yet", "nevertheless",
    "nonetheless", "even though", "except", "despite", "whereas",
    "while", "whilst",
}
# Additive/causal conjunctions: split only when dep-parse confirms two predicates
ADDITIVE_MARKERS = {"and", "but also", "so", "because", "since", "as"}

MIN_CLAUSE_WORDS   = 2    # below this → is_short_segment flag
MAX_CLAUSE_WORDS   = 120  # above this → flag as unusually long clause

# Negation and contrast indicators (for feature flags)
NEGATION_TOKENS = {
    "not", "no", "never", "nobody", "nothing", "nowhere", "neither",
    "nor", "none", "without", "barely", "hardly", "scarcely",
    "wasn't", "weren't", "isn't", "aren't", "didn't", "doesn't",
    "don't", "won't", "wouldn't", "couldn't", "shouldn't", "can't",
}
CONTRAST_TOKENS = CONTRAST_MARKERS | {
    "but", "however", "although", "though", "yet", "nevertheless",
    "nonetheless", "despite", "whereas", "while", "on the other hand",
    "on the contrary", "in contrast",
}

# Manual validation sample sizes
VALIDATION_N_PER_STAR     = 10
VALIDATION_N_SHORT        = 20
VALIDATION_N_LONG         = 15
VALIDATION_N_MULTILINE    = 15
VALIDATION_N_CONJUNCTION  = 20
VALIDATION_N_NON_ENGLISH  = 15   # all, if fewer
VALIDATION_N_PER_RESTAURANT = 2

# ─── Metadata columns to carry through from source reviews ───────────────────
CARRY_COLS = [
    "review_id", "restaurant_id", "restaurant_name",
    "review_stars", "rating_group",
    "published_at", "review_year", "review_month", "review_year_month",
    "review_quarter", "operational_peer_group", "cuisine_cluster",
    "brand_type", "price_tier", "restaurant_report_status",
    "language_final", "is_english", "has_english_translation",
    "review_text_raw", "review_text_for_nlp",
    "text_length_words", "text_length_chars", "text_length_sentences",
    "suspicious_duplicate_flag", "gold_annotation_eligible",
    "has_owner_response", "nlp_readiness_score",
]


# ════════════════════════════════════════════════════════════════════════════════
# STAGE 1 — Load data
# ════════════════════════════════════════════════════════════════════════════════

def load_nlp_population(path: str) -> pd.DataFrame:
    log.info(f"Loading: {path}")
    df = pd.read_parquet(path)

    # Ensure datetime
    for col in ["published_at"]:
        if col in df.columns:
            df[col] = pd.to_datetime(df[col], errors="coerce")

    # Filter to NLP population only
    nlp = df[df["nlp_eligible"].fillna(0) == 1].copy()
    log.info(f"NLP-eligible reviews: {len(nlp):,} of {len(df):,} total")

    # Carry only needed columns (gracefully skip missing ones)
    carry = [c for c in CARRY_COLS if c in nlp.columns]
    # review_text_for_nlp is already in CARRY_COLS — no need to append again
    nlp = nlp[carry].copy()

    # Ensure all columns use numpy-compatible dtypes (not ArrowDtype).
    # parquet files written with pyarrow may produce ArrowDtype 'string' columns
    # that don't support .str accessor in all pandas versions.
    # Nuclear approach: convert every column to object if its dtype name == "string".
    dtypes_map = {}
    for col_name in nlp.columns:
        try:
            if str(nlp[col_name].dtype) == "string":
                dtypes_map[col_name] = "object"
        except Exception:
            pass
    if dtypes_map:
        nlp = nlp.astype(dtypes_map)

    nlp["review_text_for_nlp"] = nlp["review_text_for_nlp"].fillna("").astype(str).str.strip()
    nlp = nlp[nlp["review_text_for_nlp"].str.len() > 0].copy()
    log.info(f"After removing empty texts: {len(nlp):,} reviews")

    return nlp.reset_index(drop=True)


# ════════════════════════════════════════════════════════════════════════════════
# STAGE 2 — Language resolution and validation
# ════════════════════════════════════════════════════════════════════════════════

def _detect_language(text: str) -> tuple[str, float]:
    """Run langdetect; return (lang_code, confidence). Safe — never raises."""
    try:
        from langdetect import detect_langs
        results = detect_langs(text)
        if results:
            best = results[0]
            return str(best.lang), float(best.prob)
    except Exception:
        pass
    return "unknown", 0.0


def resolve_language(df: pd.DataFrame) -> pd.DataFrame:
    """
    Validate existing language metadata.
    language_final from pipeline 01 is authoritative.
    Detector runs only as:
      - validation for ambiguous/missing cases
      - fallback when language_final is missing
      - check for possible code-switching in long reviews

    Status values:
      metadata_confirmed   — language_final present, no conflict detected
      detector_confirmed   — metadata missing; detector filled the gap
      detector_conflict    — detector disagrees with metadata (flag for review)
      too_short_to_detect  — fewer than SHORT_TEXT_THRESHOLD words
      code_switch_possible — long text but detector returns non-English
      unknown              — no language info available at all
    """
    log.info("Stage 2 — Language resolution")

    statuses   = []
    det_langs  = []
    det_confs  = []

    for _, row in tqdm(df.iterrows(), total=len(df), desc="  Language"):
        text          = str(row["review_text_for_nlp"])
        lang_meta     = str(row.get("language_final", "")).strip()
        word_count    = len(text.split())

        if word_count < SHORT_TEXT_THRESHOLD:
            statuses.append("too_short_to_detect")
            det_langs.append(pd.NA)
            det_confs.append(pd.NA)
            continue

        # Run detector
        det_lang, det_conf = _detect_language(text)
        det_langs.append(det_lang)
        det_confs.append(round(det_conf, 3))

        if not lang_meta or lang_meta in ("nan", "None", ""):
            # No existing metadata — use detector
            statuses.append("detector_confirmed")
        elif det_conf >= LANG_CONFIDENCE_THRESHOLD and det_lang != lang_meta:
            # High-confidence disagreement
            if lang_meta == "en" and det_lang != "en" and word_count >= 8:
                statuses.append("code_switch_possible")
            else:
                statuses.append("detector_conflict")
        else:
            statuses.append("metadata_confirmed")

    df["language_detection_status"]   = statuses
    df["detector_language"]           = pd.array(det_langs, dtype="object")
    df["detector_language_confidence"] = pd.array(det_confs, dtype="object")

    status_counts = pd.Series(statuses).value_counts().to_dict()
    log.info(f"  Language status distribution: {status_counts}")
    return df


# ════════════════════════════════════════════════════════════════════════════════
# STAGE 3 — spaCy model setup
# ════════════════════════════════════════════════════════════════════════════════

def load_spacy_model():
    """
    Load en_core_web_md (preferred — has dependency vectors).
    Falls back to en_core_web_sm if md is not installed.
    Adds custom sentencizer rules for restaurant review patterns.
    """
    import spacy
    from spacy.language import Language

    model_name = None
    for candidate in ("en_core_web_md", "en_core_web_sm"):
        try:
            nlp = spacy.load(candidate)
            model_name = candidate
            log.info(f"  Loaded spaCy model: {model_name}")
            break
        except OSError:
            continue

    if model_name is None:
        # Last-resort fallback: blank English model with rule-based sentencizer.
        # This provides sentence segmentation but NO dependency parsing,
        # so clause splitting will use conservative-only rules (no dep verify).
        import spacy
        nlp = spacy.blank("en")
        nlp.add_pipe("sentencizer")
        model_name = "en_blank_sentencizer"
        log.warning(
            "No trained spaCy model found. Using blank sentencizer as fallback.\n"
            "Clause splitting will use conservative rules without dep-parse verification.\n"
            "For full functionality, run: python -m spacy download en_core_web_md"
        )

    # ── Custom sentencizer rules ──────────────────────────────────────────────
    # These prevent the default sentencizer from breaking on common patterns
    # in restaurant reviews that are NOT sentence boundaries.
    if "sentencizer" not in nlp.pipe_names and "senter" not in nlp.pipe_names:
        # Parser-based sentencizer is already active in _md/_sm
        pass

    # Add custom rule: don't split on abbreviations common in reviews
    # e.g. "St.", "Dr.", "Mr.", "vs.", "approx.", "incl.", decimal prices
    @Language.component("review_sentence_fixer")
    def review_sentence_fixer(doc):
        """
        Post-process: merge short sentence fragments back to their predecessor
        when the 'sentence' is only punctuation or a single emoji character.
        Also handle newline-separated paragraph blocks as potential boundaries.
        """
        for token in doc[:-1]:
            # Suppress boundary after abbreviations followed by lowercase
            if (token.text in {"St", "Dr", "Mr", "Mrs", "Ms", "vs", "approx",
                               "incl", "excl", "est", "Ave", "Blvd", "Jr", "Sr"}
                    and token.i + 1 < len(doc)
                    and doc[token.i + 1].is_lower):
                if doc[token.i + 1].is_sent_start:
                    doc[token.i + 1].is_sent_start = False

            # Suppress boundary for decimal numbers (price: $12.50)
            if (token.like_num
                    and token.i + 1 < len(doc)
                    and doc[token.i + 1].text in {".", ","}):
                if token.i + 2 < len(doc) and doc[token.i + 2].is_sent_start:
                    doc[token.i + 2].is_sent_start = False

        return doc

    # Add after existing pipeline components (safe to add even if already there)
    if "review_sentence_fixer" not in nlp.pipe_names:
        nlp.add_pipe("review_sentence_fixer", last=True)

    log.info(f"  Pipeline components: {nlp.pipe_names}")
    has_dep = model_name in ("en_core_web_md", "en_core_web_lg", "en_core_web_trf")
    log.info(f"  Dependency parsing available: {has_dep}")
    return nlp, has_dep


# ════════════════════════════════════════════════════════════════════════════════
# STAGE 4 — Pre-processing: normalise review text for segmentation
# ════════════════════════════════════════════════════════════════════════════════

def _preprocess_for_segmentation(text: str) -> str:
    """
    Minimal pre-processing to help spaCy segment more accurately.
    Does NOT modify review_text_raw or review_text_for_nlp.
    This version is only used internally during segmentation.

    Operations:
    1. Replace paragraph-level double newlines with '. ' to create sentence
       boundaries (e.g. 'UPDATE\n\nI returned...' → 'UPDATE. I returned...')
    2. Normalise single newlines to space (bullet-list lines stay together)
    3. Ensure space after sentence-ending punctuation if missing
    4. Normalise repeated exclamation/question marks to single
    """
    # Double newlines → sentence boundary
    text = re.sub(r"\n\s*\n+", ". ", text)
    # Remaining single newlines → space
    text = re.sub(r"\n", " ", text)
    # Ensure space after . ! ? when followed by capital letter
    text = re.sub(r"([.!?])([A-Z])", r"\1 \2", text)
    # Collapse repeated punctuation (!!!!! → !)
    text = re.sub(r"([!?]){3,}", r"\1", text)
    # Collapse multiple spaces
    text = re.sub(r" {2,}", " ", text)
    return text.strip()


# ════════════════════════════════════════════════════════════════════════════════
# STAGE 5 — Sentence segmentation
# ════════════════════════════════════════════════════════════════════════════════

def _segment_sentences(text: str, nlp) -> list[dict]:
    """
    Segment a single review text into sentences using spaCy.
    Returns list of dicts with text, char_start, char_end, token_count.
    """
    proc_text = _preprocess_for_segmentation(text)
    if not proc_text.strip():
        return []

    doc = nlp(proc_text)
    sentences = []
    for sent in doc.sents:
        sent_text = sent.text.strip()
        if not sent_text:
            continue
        sentences.append({
            "sentence_text" : sent_text,
            "char_start"    : sent.start_char,
            "char_end"      : sent.end_char,
            "token_count"   : len([t for t in sent if not t.is_space]),
            "word_count"    : len(sent_text.split()),
        })
    return sentences


def build_sentence_table(df: pd.DataFrame, nlp) -> pd.DataFrame:
    """
    Create the review_sentences table.
    One row per sentence per review.
    """
    log.info("Stage 4 — Sentence segmentation")
    rows = []

    for _, review in tqdm(df.iterrows(), total=len(df), desc="  Sentences"):
        rid  = review["review_id"]
        rest = review.get("restaurant_id", pd.NA)
        text = str(review["review_text_for_nlp"])

        sentences = _segment_sentences(text, nlp)

        # If spaCy produces no sentences (very short / empty), treat whole text as one
        if not sentences:
            sentences = [{
                "sentence_text": text,
                "char_start"   : 0,
                "char_end"     : len(text),
                "token_count"  : len(text.split()),
                "word_count"   : len(text.split()),
            }]

        for s_idx, sent in enumerate(sentences):
            sentence_id = f"{rid}_S{s_idx+1:02d}"
            wc = sent["word_count"]
            rows.append({
                # ── Identity ───────────────────────────────────────────────
                "review_id"       : rid,
                "restaurant_id"   : rest,
                "sentence_id"     : sentence_id,
                "sentence_position": s_idx + 1,
                "sentence_count_in_review": len(sentences),
                # ── Text ───────────────────────────────────────────────────
                "sentence_text"   : sent["sentence_text"],
                "char_start"      : sent["char_start"],
                "char_end"        : sent["char_end"],
                "token_count"     : sent["token_count"],
                "word_count"      : wc,
                # ── Flags ──────────────────────────────────────────────────
                "is_short_segment"    : int(wc < MIN_SENTENCE_WORDS + 2),
                "is_long_segment"     : int(wc > MAX_SENTENCE_WORDS),
                "contains_negation"   : int(bool(
                    re.search(r"\b(" + "|".join(NEGATION_TOKENS) + r")\b",
                              sent["sentence_text"], re.I)
                )),
                "contains_contrast"   : int(bool(
                    re.search(r"\b(" + "|".join(
                        [re.escape(m) for m in CONTRAST_TOKENS]
                    ) + r")\b",
                    sent["sentence_text"], re.I)
                )),
                "is_first_sentence"   : int(s_idx == 0),
                "is_last_sentence"    : int(s_idx == len(sentences) - 1),
                "has_emoji"           : int(bool(
                    re.search(r"[\U0001F300-\U0001FFFF]",
                              sent["sentence_text"])
                )),
                # ── Language ───────────────────────────────────────────────
                "language_final"              : review.get("language_final", pd.NA),
                "language_detection_status"   : review.get("language_detection_status", pd.NA),
                # ── Review metadata ────────────────────────────────────────
                **{col: review.get(col, pd.NA)
                   for col in [
                       "restaurant_name", "review_stars", "rating_group",
                       "published_at", "review_year", "review_month",
                       "review_year_month", "review_quarter",
                       "operational_peer_group", "cuisine_cluster",
                       "brand_type", "price_tier", "restaurant_report_status",
                       "suspicious_duplicate_flag", "gold_annotation_eligible",
                       "review_text_for_nlp",
                   ]},
            })

    sent_df = pd.DataFrame(rows)
    log.info(f"  Sentences produced: {len(sent_df):,} "
             f"from {df['review_id'].nunique():,} reviews "
             f"(avg {len(sent_df)/len(df):.1f} sentences/review)")
    return sent_df


# ════════════════════════════════════════════════════════════════════════════════
# STAGE 6 — Clause segmentation (spaCy-assisted rule-based)
# ════════════════════════════════════════════════════════════════════════════════

def _has_independent_predicate(span, conj_token, nlp_doc) -> bool:
    """
    Use spaCy dependency parse to verify that a conjunction connects
    two independent clauses (each with its own subject + predicate),
    rather than two nouns in a noun phrase or two adjectives.

    Returns True if we should split; False if we should keep together.
    """
    # Find the token *after* the conjunction
    if conj_token.i + 1 >= len(nlp_doc):
        return False

    after_conj = nlp_doc[conj_token.i + 1:]

    # Check if the span after the conjunction contains a verb (predicate)
    has_verb_after = any(
        t.pos_ in ("VERB", "AUX") for t in after_conj[:12]  # look ahead 12 tokens
    )
    # Check if there's a subject after the conjunction (independent clause signal)
    has_subj_after = any(
        "subj" in t.dep_ for t in after_conj[:12]
    )

    # For contrast markers (but/however/although): split even if no explicit subj
    # (ellipsis is common: "Food was great but service slow")
    is_contrast = conj_token.text.lower() in CONTRAST_MARKERS

    if is_contrast and has_verb_after:
        return True
    if has_verb_after and has_subj_after:
        return True

    return False


def _split_sentence_into_clauses(
        sentence_text: str,
        sentence_id: str,
        nlp,
        has_dep: bool
) -> list[dict]:
    """
    Split one sentence into clauses using spaCy-assisted rule-based splitting.

    Strategy:
    1. Parse with spaCy to get tokens and dependency info
    2. Identify candidate split points (conjunction tokens)
    3. For each candidate:
       - If contrast marker → attempt split (always)
       - If additive marker → split only if dep-parse confirms two predicates
    4. Apply splits, ensuring no fragment is left degenerate
    5. Fall back: if only one clause results, return sentence as single clause

    Returns list of clause dicts.
    """
    proc = _preprocess_for_segmentation(sentence_text)
    if not proc.strip():
        return [{
            "clause_text": sentence_text,
            "split_trigger": None,
            "split_method": "no_split",
        }]

    doc = nlp(proc)
    tokens = list(doc)
    n = len(tokens)

    # Find candidate split positions
    split_positions = []  # list of (token_index, trigger_word, is_contrast)

    i = 0
    while i < n:
        tok = tokens[i]
        lower = tok.text.lower()

        # Multi-word markers first (e.g. "even though", "on the other hand")
        two_word = f"{lower} {tokens[i+1].text.lower()}" if i + 1 < n else ""
        three_word = (f"{lower} {tokens[i+1].text.lower()} {tokens[i+2].text.lower()}"
                      if i + 2 < n else "")

        matched_marker = None
        is_contrast_split = False

        if three_word in CONTRAST_MARKERS:
            matched_marker = three_word
            is_contrast_split = True
            advance = 3
        elif two_word in CONTRAST_MARKERS:
            matched_marker = two_word
            is_contrast_split = True
            advance = 2
        elif lower in CONTRAST_MARKERS:
            matched_marker = lower
            is_contrast_split = True
            advance = 1
        elif lower in ADDITIVE_MARKERS:
            matched_marker = lower
            is_contrast_split = False
            advance = 1
        else:
            i += 1
            continue

        # Don't split at the very start (e.g. "However, this was great")
        if tok.i < 2:
            i += advance
            continue

        # For additive markers, verify with dep-parse if available
        should_split = False
        if is_contrast_split:
            if has_dep:
                should_split = _has_independent_predicate(doc, tok, doc)
            else:
                # Without dep-parse, trust contrast markers conservatively
                # (require at least 4 tokens before and after)
                tokens_before = tok.i
                tokens_after  = n - tok.i - 1
                should_split  = tokens_before >= 3 and tokens_after >= 3
        else:
            # Additive: only split with dep-parse confirmation
            if has_dep:
                should_split = _has_independent_predicate(doc, tok, doc)
            else:
                should_split = False  # skip without dep-parse

        if should_split:
            split_positions.append((tok.i, matched_marker, is_contrast_split))

        i += advance

    # If no splits found → return original sentence as single clause
    if not split_positions:
        return [{
            "clause_text"  : sentence_text.strip(),
            "split_trigger": None,
            "split_method" : "no_split",
        }]

    # Build clauses by slicing at split positions
    clauses_raw = []
    prev_end = 0
    for split_idx, trigger, is_contrast in split_positions:
        # Text before conjunction
        before = doc[prev_end:split_idx].text.strip()
        if before:
            clauses_raw.append((before, None, "pre_split"))
        prev_end = split_idx + 1  # skip the conjunction itself

    # Final clause (after last split)
    last = doc[prev_end:].text.strip()
    if last:
        clauses_raw.append((last, split_positions[-1][1], "post_split"))

    # Build result list — filter degenerate fragments (less than 2 real tokens)
    results = []
    for clause_text, trigger, method in clauses_raw:
        wc = len(clause_text.split())
        if wc == 0:
            continue
        results.append({
            "clause_text"  : clause_text,
            "split_trigger": trigger,
            "split_method" : method,
        })

    # Safety: if splitting produced only fragments, revert to no-split
    if len(results) <= 1:
        return [{
            "clause_text"  : sentence_text.strip(),
            "split_trigger": None,
            "split_method" : "no_split_reverted",
        }]

    return results


def build_clause_table(sent_df: pd.DataFrame, nlp, has_dep: bool) -> pd.DataFrame:
    """
    Create the review_clauses table.
    One row per clause per sentence per review.
    """
    log.info("Stage 5 — Clause segmentation")
    rows = []
    split_counts = {"no_split": 0, "contrast_split": 0, "additive_split": 0,
                    "no_split_reverted": 0}

    meta_cols = [
        "review_id", "restaurant_id", "restaurant_name",
        "review_stars", "rating_group",
        "published_at", "review_year", "review_month",
        "review_year_month", "review_quarter",
        "operational_peer_group", "cuisine_cluster",
        "brand_type", "price_tier", "restaurant_report_status",
        "suspicious_duplicate_flag", "gold_annotation_eligible",
        "review_text_for_nlp", "language_final",
        "language_detection_status",
    ]

    for _, sent_row in tqdm(sent_df.iterrows(),
                            total=len(sent_df), desc="  Clauses"):
        sid       = sent_row["sentence_id"]
        rid       = sent_row["review_id"]
        sent_text = sent_row["sentence_text"]

        clauses = _split_sentence_into_clauses(sent_text, sid, nlp, has_dep)

        for c_idx, clause in enumerate(clauses):
            cid  = f"{sid}_C{c_idx+1:02d}"
            wc   = len(clause["clause_text"].split())
            meth = clause["split_method"]

            # Track split statistics
            if meth == "no_split":
                split_counts["no_split"] += 1
            elif meth == "no_split_reverted":
                split_counts["no_split_reverted"] += 1
            elif clause.get("split_trigger") in CONTRAST_MARKERS:
                split_counts["contrast_split"] += 1
            else:
                split_counts["additive_split"] += 1

            rows.append({
                # ── Identity ───────────────────────────────────────────────
                "review_id"           : rid,
                "restaurant_id"       : sent_row.get("restaurant_id", pd.NA),
                "sentence_id"         : sid,
                "clause_id"           : cid,
                "clause_position"     : c_idx + 1,
                "clause_count_in_sentence": len(clauses),
                "sentence_position"   : sent_row["sentence_position"],
                "sentence_count_in_review": sent_row["sentence_count_in_review"],
                # ── Text ───────────────────────────────────────────────────
                "clause_text"         : clause["clause_text"],
                "sentence_text"       : sent_text,          # parent context
                "word_count"          : wc,
                "split_trigger"       : clause.get("split_trigger"),
                "split_method"        : meth,
                # ── Flags ──────────────────────────────────────────────────
                "is_short_segment"    : int(wc < MIN_CLAUSE_WORDS),
                "is_long_segment"     : int(wc > MAX_CLAUSE_WORDS),
                "is_single_clause_sentence": int(len(clauses) == 1),
                "is_contrast_clause"  : int(
                    clause.get("split_trigger") in CONTRAST_MARKERS
                    if clause.get("split_trigger") else False
                ),
                "contains_negation"   : int(bool(
                    re.search(r"\b(" + "|".join(NEGATION_TOKENS) + r")\b",
                              clause["clause_text"], re.I)
                )),
                "contains_contrast"   : int(bool(
                    re.search(r"\b(" + "|".join(
                        [re.escape(m) for m in CONTRAST_TOKENS]
                    ) + r")\b",
                    clause["clause_text"], re.I)
                )),
                "has_emoji"           : int(bool(
                    re.search(r"[\U0001F300-\U0001FFFF]", clause["clause_text"])
                )),
                # ── Metadata pass-through ──────────────────────────────────
                **{col: sent_row.get(col, pd.NA) for col in meta_cols
                   if col not in ("review_id", "restaurant_id", "language_final",
                                  "language_detection_status")},
            })

    clause_df = pd.DataFrame(rows)

    log.info(f"  Clauses produced: {len(clause_df):,} "
             f"from {sent_df['sentence_id'].nunique():,} sentences")
    log.info(f"  Split method distribution: {split_counts}")

    avg_clauses = len(clause_df) / sent_df["review_id"].nunique()
    log.info(f"  Avg clauses per review: {avg_clauses:.1f}")

    return clause_df


# ════════════════════════════════════════════════════════════════════════════════
# STAGE 7 — Build combined segments table
# ════════════════════════════════════════════════════════════════════════════════

def build_segments_table(sent_df: pd.DataFrame,
                         clause_df: pd.DataFrame) -> pd.DataFrame:
    """
    Create a unified segments table combining sentences and clauses.
    segment_type: 'sentence' | 'clause'
    segment_id  : globally unique ID
    This is the primary input for BERTopic (filter segment_type='sentence')
    and for ABSA (filter segment_type='clause').
    """
    log.info("Stage 6 — Building combined segments table")

    # Sentence rows
    s_rows = sent_df.rename(columns={
        "sentence_id"  : "segment_id",
        "sentence_text": "segment_text",
        "sentence_position": "segment_position",
    }).copy()
    s_rows["segment_type"]       = "sentence"
    s_rows["parent_sentence_id"] = pd.NA
    s_rows["clause_position"]    = pd.NA

    # Clause rows
    c_rows = clause_df.rename(columns={
        "clause_id"  : "segment_id",
        "clause_text": "segment_text",
    }).copy()
    c_rows["segment_type"]       = "clause"
    c_rows["parent_sentence_id"] = c_rows["sentence_id"]

    # Unify columns — keep superset
    combined = pd.concat([s_rows, c_rows], ignore_index=True, sort=False)
    combined = combined.sort_values(
        ["review_id", "segment_type", "segment_id"]
    ).reset_index(drop=True)

    log.info(f"  Total segments: {len(combined):,} "
             f"({(combined['segment_type']=='sentence').sum():,} sentences + "
             f"{(combined['segment_type']=='clause').sum():,} clauses)")
    return combined


# ════════════════════════════════════════════════════════════════════════════════
# STAGE 8 — Quality control and reconciliation
# ════════════════════════════════════════════════════════════════════════════════

def run_quality_checks(df_input: pd.DataFrame,
                       sent_df: pd.DataFrame,
                       clause_df: pd.DataFrame) -> dict:
    """
    Comprehensive QC checks. Returns dict of check results.
    All failures are logged; none auto-fix data.
    """
    log.info("Stage 7 — Quality control")
    results = {}

    n_input_reviews  = df_input["review_id"].nunique()
    n_sent_reviews   = sent_df["review_id"].nunique()
    n_clause_reviews = clause_df["review_id"].nunique()

    # A — Reconciliation: all input reviews must appear in output
    results["A_review_reconciliation"] = {
        "input_nlp_reviews"   : n_input_reviews,
        "reviews_in_sentences": n_sent_reviews,
        "reviews_in_clauses"  : n_clause_reviews,
        "missing_from_sentences": n_input_reviews - n_sent_reviews,
        "missing_from_clauses"  : n_input_reviews - n_clause_reviews,
        "status": "PASS" if n_input_reviews == n_sent_reviews == n_clause_reviews
                         else "FAIL",
    }

    # B — No empty segment text
    empty_sent   = (sent_df["sentence_text"].str.strip() == "").sum()
    empty_clause = (clause_df["clause_text"].str.strip() == "").sum()
    results["B_empty_segments"] = {
        "empty_sentence_text" : int(empty_sent),
        "empty_clause_text"   : int(empty_clause),
        "status": "PASS" if empty_sent == 0 and empty_clause == 0 else "FAIL",
    }

    # C — No null review_id or restaurant_id
    null_rid_sent    = sent_df["review_id"].isna().sum()
    null_rest_sent   = sent_df["restaurant_id"].isna().sum()
    null_rid_clause  = clause_df["review_id"].isna().sum()
    results["C_null_identity"] = {
        "null_review_id_sentences"    : int(null_rid_sent),
        "null_restaurant_id_sentences": int(null_rest_sent),
        "null_review_id_clauses"      : int(null_rid_clause),
        "status": "PASS" if all(v == 0 for v in [
            null_rid_sent, null_rest_sent, null_rid_clause]) else "WARN",
    }

    # D — Parent-child integrity: every clause_id must reference a valid sentence_id
    valid_sids     = set(sent_df["sentence_id"])
    clause_sids    = set(clause_df["sentence_id"])
    orphan_clauses = clause_sids - valid_sids
    results["D_parent_child_integrity"] = {
        "orphan_clause_sentence_ids": len(orphan_clauses),
        "status": "PASS" if not orphan_clauses else "FAIL",
    }

    # E — Stars integrity preserved
    for col in ["review_stars"]:
        if col in sent_df.columns:
            mismatch = sent_df[sent_df[col].notna() &
                               ~sent_df[col].isin([1,2,3,4,5])].shape[0]
            results[f"E_stars_integrity_{col}"] = {
                "invalid_star_values": int(mismatch),
                "status": "PASS" if mismatch == 0 else "WARN",
            }

    # F — Short segment rate
    short_sent_rate   = (sent_df["is_short_segment"] == 1).mean()
    short_clause_rate = (clause_df["is_short_segment"] == 1).mean()
    results["F_short_segments"] = {
        "short_sentence_rate_pct"  : round(short_sent_rate * 100, 1),
        "short_clause_rate_pct"    : round(short_clause_rate * 100, 1),
        "status": "INFO",
    }

    # G — Language coverage
    non_english_sent = (sent_df.get("language_final", pd.Series()) != "en").sum()
    results["G_language"] = {
        "non_english_sentences": int(non_english_sent),
        "language_distribution": sent_df["language_final"].value_counts()
                                  .head(10).to_dict() if "language_final" in sent_df.columns
                                  else {},
        "status": "INFO",
    }

    # H — Segmentation statistics
    sents_per_review  = sent_df.groupby("review_id").size()
    clauses_per_sent  = clause_df.groupby("sentence_id").size()
    clauses_per_review = clause_df.groupby("review_id").size()
    results["H_segmentation_stats"] = {
        "total_sentences"       : len(sent_df),
        "total_clauses"         : len(clause_df),
        "avg_sentences_review"  : round(sents_per_review.mean(), 2),
        "median_sentences_review": round(sents_per_review.median(), 2),
        "avg_clauses_sentence"  : round(clauses_per_sent.mean(), 2),
        "avg_clauses_review"    : round(clauses_per_review.mean(), 2),
        "median_words_sentence" : round(sent_df["word_count"].median(), 1),
        "median_words_clause"   : round(clause_df["word_count"].median(), 1),
        "sentences_with_clause_split": int(
            (clause_df.groupby("sentence_id")["clause_position"].max() > 1).sum()
        ),
        "status": "INFO",
    }

    # Print summary
    for check, res in results.items():
        status = res.get("status", "INFO")
        symbol = {"PASS":"✓","FAIL":"✗","WARN":"⚠","INFO":"·"}.get(status, "?")
        log.info(f"  {symbol} {check}: {status}")

    return results


# ════════════════════════════════════════════════════════════════════════════════
# STAGE 9 — Build validation samples
# ════════════════════════════════════════════════════════════════════════════════

def build_validation_samples(df_input: pd.DataFrame,
                             sent_df: pd.DataFrame,
                             clause_df: pd.DataFrame) -> dict:
    """
    Stratified samples for manual human review.
    Returns dict of sheet_name → DataFrame.
    """
    log.info("Stage 8 — Building validation samples")
    rng = np.random.default_rng(seed=42)

    core_cols_s = [
        "review_id", "restaurant_id", "restaurant_name",
        "review_stars", "sentence_id", "sentence_text",
        "word_count", "is_short_segment", "contains_negation",
        "contains_contrast", "has_emoji", "language_final",
        "language_detection_status",
    ]
    core_cols_c = [
        "review_id", "restaurant_name", "review_stars",
        "sentence_id", "clause_id", "sentence_text", "clause_text",
        "word_count", "split_trigger", "split_method",
        "is_short_segment", "contains_negation", "contains_contrast",
    ]
    sc = [c for c in core_cols_s if c in sent_df.columns]
    cc = [c for c in core_cols_c if c in clause_df.columns]

    def sample_idx(mask, n):
        idx = sent_df[mask].index.tolist()
        return sent_df.loc[
            rng.choice(idx, size=min(n, len(idx)), replace=False), sc
        ].copy() if idx else pd.DataFrame(columns=sc)

    samples = {}

    # Per-star stratum
    for star in [1, 2, 3, 4, 5]:
        mask = sent_df["review_stars"] == star
        samp = sample_idx(mask, VALIDATION_N_PER_STAR)
        if len(samp):
            samples[f"star_{star}"] = samp

    # Short segments
    samples["short_segments"] = sample_idx(
        sent_df["is_short_segment"] == 1, VALIDATION_N_SHORT
    )

    # Long segments
    samples["long_segments"] = sample_idx(
        sent_df["word_count"] > 80, VALIDATION_N_LONG
    )

    # Contains contrast/but
    samples["contrast_sentences"] = sample_idx(
        sent_df["contains_contrast"] == 1, VALIDATION_N_CONJUNCTION
    )

    # Non-English
    non_en_mask = sent_df.get("language_final", pd.Series(dtype=str)) != "en"
    samples["non_english"] = sample_idx(non_en_mask, VALIDATION_N_NON_ENGLISH)

    # Per-restaurant (2 per restaurant)
    per_rest_frames = []
    for rid, grp in sent_df.groupby("restaurant_id"):
        n_samp = min(VALIDATION_N_PER_RESTAURANT, len(grp))
        per_rest_frames.append(grp.sample(n=n_samp, random_state=42))
    per_rest = pd.concat(per_rest_frames, ignore_index=True)
    samples["per_restaurant"] = per_rest[[c for c in sc if c in per_rest.columns]].copy()

    # Clause splitting examples (where split happened)
    split_clauses = clause_df[clause_df["split_method"].str.contains(
        "split", na=False) & ~clause_df["split_method"].str.contains(
        "no_split", na=False)]
    if len(split_clauses):
        idx_c = rng.choice(
            split_clauses.index.tolist(),
            size=min(30, len(split_clauses)),
            replace=False
        )
        samples["clause_split_examples"] = split_clauses.loc[idx_c, cc].copy()

    # QC template with annotation columns
    manual_template_cols = sc + [
        "segmentation_quality", "error_type", "manual_note"
    ]
    if "per_restaurant" in samples:
        template = samples["per_restaurant"].copy()
        for col in ["segmentation_quality", "error_type", "manual_note"]:
            template[col] = ""
        samples["manual_qc_template"] = template[
            [c for c in manual_template_cols if c in template.columns]
        ]

    log.info(f"  Validation sample sheets: {list(samples.keys())}")
    return samples


# ════════════════════════════════════════════════════════════════════════════════
# STAGE 10 — Build flagged records
# ════════════════════════════════════════════════════════════════════════════════

def build_flagged_records(sent_df: pd.DataFrame,
                          clause_df: pd.DataFrame,
                          df_input: pd.DataFrame) -> dict:
    """
    Collect all records needing human review into named sheets.
    No records are deleted — only flagged.
    """
    log.info("Stage 9 — Collecting flagged records")

    sc = [c for c in [
        "review_id", "restaurant_name", "review_stars",
        "sentence_id", "sentence_text", "word_count",
        "language_final", "language_detection_status",
        "is_short_segment", "contains_negation", "contains_contrast",
    ] if c in sent_df.columns]

    flagged = {}

    # Language conflicts
    if "language_detection_status" in sent_df.columns:
        conflict_mask = sent_df["language_detection_status"].isin(
            ["detector_conflict", "code_switch_possible"]
        )
        # Deduplicate to one row per review_id
        flagged["language_conflicts"] = (
            sent_df[conflict_mask]
            .drop_duplicates(subset="review_id")[sc].copy()
        )

    # Short segments
    flagged["short_segments"] = sent_df[
        sent_df["is_short_segment"] == 1
    ][sc].copy()

    # Long segments
    flagged["long_segments"] = sent_df[
        sent_df.get("word_count", pd.Series(dtype=int)) > MAX_SENTENCE_WORDS
    ][sc].copy() if "word_count" in sent_df.columns else pd.DataFrame(columns=sc)

    # Suspicious duplicate reviews in segment table
    if "suspicious_duplicate_flag" in sent_df.columns:
        flagged["suspicious_duplicates_in_segments"] = (
            sent_df[sent_df["suspicious_duplicate_flag"].fillna(0) == 1]
            .drop_duplicates(subset="review_id")[sc].copy()
        )

    # Reviews that produced only 1 sentence AND that sentence is very short
    single_short = (
        sent_df[
            (sent_df["sentence_count_in_review"] == 1)
            & (sent_df["is_short_segment"] == 1)
        ][sc].copy()
    )
    flagged["single_short_sentence_reviews"] = single_short

    # Clauses where split may have been over-aggressive (very short post-split)
    if "split_method" in clause_df.columns:
        over_split_mask = (
            clause_df["split_method"].str.contains("post_split|pre_split", na=False)
            & (clause_df["word_count"] < 3)
        )
        cc = [c for c in [
            "review_id", "restaurant_name", "review_stars",
            "sentence_id", "clause_id", "sentence_text", "clause_text",
            "word_count", "split_trigger", "split_method",
        ] if c in clause_df.columns]
        flagged["potential_over_split_clauses"] = clause_df[over_split_mask][cc].copy()

    for name, fdf in flagged.items():
        log.info(f"  {name}: {len(fdf):,} records")

    return flagged


# ════════════════════════════════════════════════════════════════════════════════
# STAGE 11 — Build segmentation summary Excel
# ════════════════════════════════════════════════════════════════════════════════

def build_summary_excel(df_input: pd.DataFrame,
                        sent_df: pd.DataFrame,
                        clause_df: pd.DataFrame,
                        qc_results: dict) -> pd.DataFrame:
    """
    Comprehensive summary workbook: reconciliation, stats, per-restaurant,
    per-rating, per-peer-group, language, split-method distribution.
    """
    log.info("Stage 10 — Building summary Excel")

    summary_sheets = {}

    # ── QC reconciliation ─────────────────────────────────────────────────────
    qc_rows = []
    for check, res in qc_results.items():
        for k, v in res.items():
            if k == "status":
                continue
            qc_rows.append({"Check": check, "Metric": k, "Value": str(v),
                             "Status": res.get("status","")})
    summary_sheets["QC_Reconciliation"] = pd.DataFrame(qc_rows)

    # ── Overall stats ─────────────────────────────────────────────────────────
    sents_per_review  = sent_df.groupby("review_id").size()
    clauses_per_sent  = clause_df.groupby("sentence_id").size()
    clauses_per_review = clause_df.groupby("review_id").size()
    overall = [
        ("Input NLP-eligible reviews",      df_input["review_id"].nunique()),
        ("Total sentences produced",         len(sent_df)),
        ("Total clauses produced",           len(clause_df)),
        ("Avg sentences per review",         round(sents_per_review.mean(),2)),
        ("Median sentences per review",      round(sents_per_review.median(),1)),
        ("Avg clauses per review",           round(clauses_per_review.mean(),2)),
        ("Avg clauses per sentence",         round(clauses_per_sent.mean(),2)),
        ("Median words per sentence",        round(sent_df["word_count"].median(),1)),
        ("Median words per clause",          round(clause_df["word_count"].median(),1)),
        ("Short sentence rate (%)",          round((sent_df["is_short_segment"]==1).mean()*100,1)),
        ("Short clause rate (%)",            round((clause_df["is_short_segment"]==1).mean()*100,1)),
        ("Sentences with negation (%)",      round((sent_df["contains_negation"]==1).mean()*100,1)),
        ("Sentences with contrast (%)",      round((sent_df["contains_contrast"]==1).mean()*100,1)),
        ("Sentences with emoji (%)",         round((sent_df["has_emoji"]==1).mean()*100,1)),
        ("Clauses from contrast split",      int((clause_df["split_method"].str.contains("post_split",na=False)).sum())),
        ("Sentences NOT split into clauses", int((clause_df["clause_count_in_sentence"]==1).sum())),
    ]
    summary_sheets["Overall_Stats"] = pd.DataFrame(overall, columns=["Metric","Value"])

    # ── Per restaurant ────────────────────────────────────────────────────────
    if "restaurant_name" in sent_df.columns:
        per_rest = (
            sent_df.groupby(["restaurant_id","restaurant_name"]).agg(
                n_reviews    =("review_id","nunique"),
                n_sentences  =("sentence_id","count"),
                avg_words_sent=("word_count","mean"),
                short_sent_pct=("is_short_segment","mean"),
                contrast_pct  =("contains_contrast","mean"),
                negation_pct  =("contains_negation","mean"),
            ).round(3).reset_index()
        )
        clause_rest = (
            clause_df.groupby("restaurant_id").agg(
                n_clauses=("clause_id","count"),
                avg_words_clause=("word_count","mean"),
            ).round(3).reset_index()
        )
        per_rest = per_rest.merge(clause_rest, on="restaurant_id", how="left")
        per_rest["short_sent_pct"] = (per_rest["short_sent_pct"]*100).round(1)
        per_rest["contrast_pct"]   = (per_rest["contrast_pct"]*100).round(1)
        per_rest["negation_pct"]   = (per_rest["negation_pct"]*100).round(1)
        summary_sheets["Per_Restaurant"] = per_rest

    # ── Per star rating ───────────────────────────────────────────────────────
    if "review_stars" in sent_df.columns:
        per_star = (
            sent_df.groupby("review_stars").agg(
                n_reviews=("review_id","nunique"),
                n_sentences=("sentence_id","count"),
                median_words=("word_count","median"),
                contrast_pct=("contains_contrast","mean"),
                negation_pct=("contains_negation","mean"),
                short_pct   =("is_short_segment","mean"),
            ).round(3).reset_index()
        )
        for pct_col in ["contrast_pct","negation_pct","short_pct"]:
            per_star[pct_col] = (per_star[pct_col]*100).round(1)
        summary_sheets["Per_Star_Rating"] = per_star

    # ── Per operational peer group ────────────────────────────────────────────
    if "operational_peer_group" in sent_df.columns:
        per_peer = (
            sent_df.groupby("operational_peer_group").agg(
                n_reviews=("review_id","nunique"),
                n_sentences=("sentence_id","count"),
                median_words=("word_count","median"),
                contrast_pct=("contains_contrast","mean"),
                negation_pct=("contains_negation","mean"),
            ).round(3).reset_index()
        )
        for pct_col in ["contrast_pct","negation_pct"]:
            per_peer[pct_col] = (per_peer[pct_col]*100).round(1)
        summary_sheets["Per_Peer_Group"] = per_peer

    # ── Language distribution ─────────────────────────────────────────────────
    if "language_final" in sent_df.columns:
        lang_dist = (
            sent_df.drop_duplicates("review_id")["language_final"]
            .value_counts().reset_index()
        )
        lang_dist.columns = ["language", "n_reviews"]
        summary_sheets["Language_Distribution"] = lang_dist

    if "language_detection_status" in sent_df.columns:
        det_status = (
            sent_df.drop_duplicates("review_id")["language_detection_status"]
            .value_counts().reset_index()
        )
        det_status.columns = ["detection_status","n_reviews"]
        summary_sheets["Language_Detection_Status"] = det_status

    # ── Split method distribution ──────────────────────────────────────────────
    if "split_method" in clause_df.columns:
        split_dist = clause_df["split_method"].value_counts().reset_index()
        split_dist.columns = ["split_method","n_clauses"]
        summary_sheets["Split_Method_Distribution"] = split_dist

    if "split_trigger" in clause_df.columns:
        trigger_dist = clause_df["split_trigger"].value_counts().reset_index()
        trigger_dist.columns = ["split_trigger","n_clauses"]
        summary_sheets["Split_Trigger_Distribution"] = trigger_dist

    return summary_sheets


# ════════════════════════════════════════════════════════════════════════════════
# STAGE 12 — Export all outputs
# ════════════════════════════════════════════════════════════════════════════════

def export_outputs(sent_df: pd.DataFrame,
                   clause_df: pd.DataFrame,
                   segments_df: pd.DataFrame,
                   summary_sheets: dict,
                   validation_samples: dict,
                   flagged_records: dict) -> None:

    log.info("Stage 11 — Exporting outputs")

    def _strip_tz(df):
        df = df.copy()
        for col in df.columns:
            if pd.api.types.is_datetime64_any_dtype(df[col]):
                try:    df[col] = df[col].dt.tz_localize(None)
                except: df[col] = df[col].dt.tz_convert(None)
        return df

    def _safe_parquet(df, path):
        """Convert period/pyarrow types to str before saving parquet."""
        df = df.copy()
        for col in df.columns:
            if hasattr(df[col], "dt") and hasattr(df[col].dt, "to_timestamp"):
                try:
                    df[col] = df[col].astype(str)
                except Exception:
                    pass
            if pd.api.types.is_extension_array_dtype(df[col]):
                try:
                    df[col] = df[col].astype(object)
                except Exception:
                    pass
        df.to_parquet(path, index=False, engine="pyarrow")
        log.info(f"  Saved: {path}  ({len(df):,} rows × {len(df.columns)} cols)")

    # ── Parquet outputs ───────────────────────────────────────────────────────
    _safe_parquet(sent_df,    os.path.join(OUT_DIR, "review_sentences.parquet"))
    _safe_parquet(clause_df,  os.path.join(OUT_DIR, "review_clauses.parquet"))
    _safe_parquet(segments_df, os.path.join(OUT_DIR, "review_segments.parquet"))

    # ── Summary Excel ─────────────────────────────────────────────────────────
    path_summary = os.path.join(OUT_DIR, "segmentation_summary.xlsx")
    with pd.ExcelWriter(path_summary, engine="openpyxl") as w:
        for sheet, tbl in summary_sheets.items():
            if isinstance(tbl, pd.DataFrame) and len(tbl):
                _strip_tz(tbl).to_excel(w, sheet_name=sheet[:31], index=False)
    log.info(f"  Saved: {path_summary}")

    # ── Manual validation Excel ───────────────────────────────────────────────
    path_val = os.path.join(OUT_DIR, "segmentation_manual_validation.xlsx")
    with pd.ExcelWriter(path_val, engine="openpyxl") as w:
        for sheet, tbl in validation_samples.items():
            if isinstance(tbl, pd.DataFrame) and len(tbl):
                _strip_tz(tbl).to_excel(w, sheet_name=sheet[:31], index=False)
    log.info(f"  Saved: {path_val}")

    # ── Flagged records Excel ─────────────────────────────────────────────────
    path_flagged = os.path.join(OUT_DIR, "segmentation_flagged_records.xlsx")
    with pd.ExcelWriter(path_flagged, engine="openpyxl") as w:
        for sheet, tbl in flagged_records.items():
            if isinstance(tbl, pd.DataFrame) and len(tbl):
                _strip_tz(tbl).to_excel(w, sheet_name=sheet[:31], index=False)
    log.info(f"  Saved: {path_flagged}")


# ════════════════════════════════════════════════════════════════════════════════
# MAIN
# ════════════════════════════════════════════════════════════════════════════════

def main():
    print("=" * 70)
    print("  Peterborough Restaurant Reviews — NLP Preparation Pipeline")
    print(f"  Run at: {datetime.now(timezone.utc).isoformat()}")
    print(f"  Input  : {PARQUET_IN}")
    print(f"  Output : {OUT_DIR}")
    print("=" * 70)

    # Stage 1 — Load
    df_input = load_nlp_population(PARQUET_IN)

    # Stage 2 — Language resolution
    df_input = resolve_language(df_input)

    # Stage 3 — Load spaCy
    log.info("Stage 3 — Loading spaCy model")
    nlp, has_dep = load_spacy_model()

    # Stage 4 — Sentence segmentation
    sent_df = build_sentence_table(df_input, nlp)

    # Stage 5 — Clause segmentation
    clause_df = build_clause_table(sent_df, nlp, has_dep)

    # Stage 6 — Combined segments table
    segments_df = build_segments_table(sent_df, clause_df)

    # Stage 7 — QC
    qc_results = run_quality_checks(df_input, sent_df, clause_df)

    # Stage 8 — Validation samples
    validation_samples = build_validation_samples(df_input, sent_df, clause_df)

    # Stage 9 — Flagged records
    flagged_records = build_flagged_records(sent_df, clause_df, df_input)

    # Stage 10 — Summary
    summary_sheets = build_summary_excel(df_input, sent_df, clause_df, qc_results)

    # Stage 11 — Export
    export_outputs(sent_df, clause_df, segments_df,
                   summary_sheets, validation_samples, flagged_records)

    # ── Final print ───────────────────────────────────────────────────────────
    print("\n" + "=" * 70)
    print("  Pipeline complete.")
    print(f"  Input reviews    : {df_input['review_id'].nunique():,}")
    print(f"  Sentences        : {len(sent_df):,}")
    print(f"  Clauses          : {len(clause_df):,}")
    print(f"  Combined segments: {len(segments_df):,}")
    print()
    print("  Outputs written to:")
    for fname in [
        "review_sentences.parquet",
        "review_clauses.parquet",
        "review_segments.parquet",
        "segmentation_summary.xlsx",
        "segmentation_manual_validation.xlsx",
        "segmentation_flagged_records.xlsx",
    ]:
        print(f"    {os.path.join(OUT_DIR, fname)}")
    print()
    print("  Next steps:")
    print("    1. Open segmentation_manual_validation.xlsx")
    print("       → Review 150–250 segments across all strata")
    print("       → Fill in segmentation_quality, error_type, manual_note")
    print("    2. If error rate > 10% on contrast splits → tune CONTRAST_MARKERS")
    print("    3. If error rate > 15% on any stratum → consider Version 2")
    print("       (dependency-based clause splitting)")
    print("    4. Run 05_bertopic_discovery.py on review_sentences.parquet")
    print("       (use review_clauses.parquet for sensitivity analysis)")
    print("=" * 70)

    return sent_df, clause_df, segments_df


if __name__ == "__main__":
    sent_df, clause_df, segments_df = main()
