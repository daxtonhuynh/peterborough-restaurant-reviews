"""
05_bertopic_discovery.py
========================
Peterborough Restaurant Google Reviews — BERTopic Topic Discovery
Phase 5 / Step 7: Exploratory Topic Discovery

Purpose:
    BERTopic is used exclusively as a DISCOVERY tool, not for final conclusions.
    Goal is to surface:
      - Complaint themes not anticipated in advance
      - Customer needs and delight drivers
      - Semantic clusters with local Peterborough context
      - Evidence base for building the aspect taxonomy

Architecture:
    Sentence text → Sentence embeddings → UMAP reduction
        → HDBSCAN clustering → BERTopic representation (c-TF-IDF + MMR)
        → Topic validation → Topic-to-aspect mapping prep

Runs performed (in order):
    Run 1 — Full corpus             (all NLP-eligible sentences, >3 words)
    Run 2 — Negative corpus         (sentences from 1–3★ reviews)
    Run 3 — Positive corpus         (sentences from 4–5★ reviews)
    Run 4 — Per peer group          (topic prevalence by operational group,
                                     reusing Run 1 assignments)
    Run 5 — Recent period           (last 12 months, uses Run 1 embeddings)

Design rules:
    - No BERTopic result is treated as ground truth
    - Topics with coherence < threshold are flagged, not removed
    - Every run produces human-readable validation output
    - All outputs are labelled with run_id for traceability
    - Short sentences (≤3 words) are excluded from embedding but preserved in data
    - Embeddings are cached to avoid redundant computation across runs

Inputs:
    04. Outputs_NLP/review_sentences.parquet

Outputs (in 05. Outputs_BERTopic/):
    embeddings_cache.npy               Sentence embeddings (cached)
    run1_all/                          Full corpus run
    run2_negative/                     1–3★ sentences
    run3_positive/                     4–5★ sentences
    ├── topics.parquet                 Sentence-level topic assignments
    ├── topic_info.xlsx                Topic list: keywords, size, prevalence
    ├── topic_validation_samples.xlsx  20–30 representative sentences per topic
    ├── topic_prevalence_chart.png     Visual topic size distribution
    └── umap_scatter.png               2D UMAP embedding plot coloured by topic

    run4_peer_group/
    ├── peer_group_topic_prevalence.xlsx  Cross-tabulation: topic × peer group
    └── peer_group_heatmap.png

    run5_recent/
    ├── topics.parquet
    ├── topic_info.xlsx
    └── topic_trend_comparison.xlsx   Recent vs historical topic prevalence

    bertopic_summary.xlsx             Master summary across all runs
    topic_to_aspect_mapping_draft.xlsx  Pre-filled draft for human review
    annotation_sample_v2_clause.xlsx    Clause-level annotation sample (1,200 records)
                                        with sentence context preserved (Option B)

Dependencies (install on your machine):
    pip install bertopic sentence-transformers umap-learn hdbscan
    pip install plotly matplotlib seaborn openpyxl pyarrow pandas numpy scipy
    python -m spacy download en_core_web_md   (optional, for KeyBERT repr)

    BERTopic requires ~4–8GB RAM for this corpus size (16K sentences).
    GPU optional but not required — CPU run takes ~10–20 min depending on machine.
"""

import os
import json
import warnings
import logging
import hashlib
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd
import matplotlib
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import seaborn as sns

matplotlib.use("Agg")
warnings.filterwarnings("ignore")
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)s  %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger(__name__)

# ─── Paths ────────────────────────────────────────────────────────────────────
# Workspace root (raw files + numbered output folders): set PTBO_BASE, or it defaults to the repository root.
PROJECT_DIR  = os.environ.get("PTBO_BASE", os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
SENTENCES_IN = os.path.join(PROJECT_DIR, "04. Outputs_NLP", "review_sentences.parquet")
CLAUSES_IN   = os.path.join(PROJECT_DIR, "04. Outputs_NLP", "review_clauses.parquet")
OUT_DIR      = os.path.join(PROJECT_DIR, "05. Outputs_BERTopic")
os.makedirs(OUT_DIR, exist_ok=True)

# ─── BERTopic configuration ───────────────────────────────────────────────────

# Embedding model
EMBEDDING_MODEL = "all-MiniLM-L6-v2"   # fast, good quality for English reviews
                                         # Alternative: "all-mpnet-base-v2" (slower, better)
EMBEDDING_CACHE  = os.path.join(OUT_DIR, "embeddings_cache.npy")
SENTENCE_IDS_CACHE = os.path.join(OUT_DIR, "sentence_ids_cache.json")

# UMAP parameters
UMAP_N_NEIGHBORS   = 15    # larger = more global structure; smaller = more local
UMAP_N_COMPONENTS  = 5     # dimensions for HDBSCAN (not for visualisation)
UMAP_MIN_DIST      = 0.0   # 0 = tighter clusters (good for HDBSCAN downstream)
UMAP_METRIC        = "cosine"
UMAP_RANDOM_STATE  = 42
UMAP_N_COMPONENTS_VIZ = 2  # separate 2D projection just for scatter plot

# HDBSCAN parameters
HDBSCAN_MIN_CLUSTER_SIZE  = 30   # minimum sentences to form a topic
                                  # lower = more granular topics; higher = more stable
HDBSCAN_MIN_SAMPLES       = 10   # controls outlier sensitivity
HDBSCAN_METRIC            = "euclidean"
HDBSCAN_CLUSTER_SELECTION = "eom"  # "eom" = excess of mass (good for uneven clusters)
HDBSCAN_PREDICTION_DATA   = True  # needed for soft clustering / topic assignment

# BERTopic representation
N_GRAM_RANGE     = (1, 2)    # unigrams + bigrams in topic keywords
TOP_N_WORDS      = 12        # keywords per topic shown in outputs
MIN_TOPIC_SIZE   = 20        # topics smaller than this get merged into -1 (noise)
MMR_DIVERSITY    = 0.3       # Maximal Marginal Relevance diversity (0=redundant, 1=diverse)
# NR_TOPICS_HINT controls post-clustering topic merging:
#   "auto" = BERTopic decides (tends to over-merge — e.g. 121→22, bad for discovery)
#   None   = no reduction — keeps all HDBSCAN clusters (best for discovery)
#   int    = force-reduce to exactly N topics
# We use None for all runs. If a run produces >MAX_TOPICS_SAFETY_CAP topics,
# a second pass at nr_topics=MAX_TOPICS_SAFETY_CAP is logged alongside for comparison.
NR_TOPICS_HINT       = None   # no reduction — discovery mode
MAX_TOPICS_SAFETY_CAP = 120   # if topics > this, log a warning (do NOT auto-reduce)

# Filtering
MIN_WORDS_FOR_EMBEDDING = 3  # sentences with ≤ this many words are skipped

# Validation samples per topic
VALIDATION_N_PER_TOPIC   = 25   # representative sentences per topic
VALIDATION_N_OUTLIER     = 15   # samples from noise/outlier cluster (-1)

# Run definitions
RECENT_MONTHS = 12
PEER_ORDER = [
    "Fast Casual & Counter Service",
    "Breakfast, Diner & Family Casual",
    "Casual Full-Service Ethnic Dining",
    "Pub, Burger & Smokehouse Casual",
    "Premium Full-Service & Experience Dining",
]

# Coherence thresholds (used for flagging, NOT for deletion)
MIN_TOPIC_COHERENCE_WORDS = 3     # topics with fewer distinct content words → flagged
GENERIC_KEYWORDS = {              # if top-5 keywords are all generic → flag
    "good", "great", "nice", "bad", "ok", "okay", "amazing", "awesome",
    "excellent", "terrible", "horrible", "wonderful", "fantastic",
    "place", "food", "restaurant", "came", "went", "got",
}

# ─── Draft topic-to-aspect mapping template ──────────────────────────────────
# Pre-defined 14 aspects for the mapping template
ASPECT_TAXONOMY_DRAFT = [
    ("Food taste & overall quality",
     "Taste, flavour, quality of food dishes"),
    ("Freshness, temperature & food condition",
     "Freshness, temperature, texture, food arriving hot/cold"),
    ("Portion size",
     "Size, quantity, value-for-portion perception"),
    ("Menu variety",
     "Range of options, dietary accommodation, seasonal menu"),
    ("Price & value",
     "Perceived affordability, value for money, price-quality ratio"),
    ("Staff friendliness & professionalism",
     "Attitude, helpfulness, friendliness, professionalism of staff"),
    ("Service speed & waiting time",
     "Wait to be seated, order taken, food delivered, bill received"),
    ("Order accuracy",
     "Correct items delivered, special requests honoured"),
    ("Ambience & noise",
     "Atmosphere, noise level, music, décor, lighting, crowd"),
    ("Cleanliness",
     "Cleanliness of tables, washrooms, kitchen visible, overall hygiene"),
    ("Location, parking & accessibility",
     "Ease of finding, parking availability, wheelchair access"),
    ("Delivery & takeout",
     "Delivery experience, packaging, takeout quality, order apps"),
    ("Dietary accommodation",
     "Gluten-free, vegan, allergy-aware options, accommodation of restrictions"),
    ("Overall experience, recommendation & return intention",
     "General sentiment, would recommend, would return, overall impression"),
    ("Other / business-specific",
     "Topics with business meaning not captured in above categories"),
    ("Not applicable / unclear",
     "Generic filler, spam, ambiguous, no extractable aspect"),
]


# ════════════════════════════════════════════════════════════════════════════════
# HELPERS
# ════════════════════════════════════════════════════════════════════════════════

def section(title: str) -> None:
    log.info(f"\n{'═'*66}\n  {title}\n{'═'*66}")


def _strip_tz(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    for col in df.columns:
        if pd.api.types.is_datetime64_any_dtype(df[col]):
            try:
                df[col] = df[col].dt.tz_localize(None)
            except Exception:
                try:
                    df[col] = df[col].dt.tz_convert(None)
                except Exception:
                    pass
    return df


def _safe_str(series: pd.Series) -> pd.Series:
    """Convert ArrowDtype/nullable string to plain str."""
    return series.astype(object).fillna("").astype(str)


def _topic_coherence_flag(keywords: list[str]) -> str:
    """Flag topics whose top keywords are predominantly generic."""
    if len(keywords) < MIN_TOPIC_COHERENCE_WORDS:
        return "too_few_keywords"
    generic_overlap = sum(1 for kw in keywords[:5] if kw.lower() in GENERIC_KEYWORDS)
    if generic_overlap >= 4:
        return "generic_keywords"
    return "ok"


def save_png(fig, path: str) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    fig.savefig(path, dpi=150, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    log.info(f"  Chart saved: {path}")


def write_xlsx(sheets: dict, path: str) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with pd.ExcelWriter(path, engine="openpyxl") as w:
        for sheet, df in sheets.items():
            if isinstance(df, pd.DataFrame) and len(df):
                # Excel sheet names cannot contain: / \ ? * [ ] :
                safe_name = str(sheet).replace("/","_").replace("\\","_") \
                    .replace("?","").replace("*","").replace("[","").replace("]","") \
                    .replace(":","")[:31]
                _strip_tz(df).to_excel(w, sheet_name=safe_name, index=False)
    log.info(f"  Excel saved: {path}")


# ════════════════════════════════════════════════════════════════════════════════
# STAGE 1 — Load sentence data
# ════════════════════════════════════════════════════════════════════════════════

def load_sentences(path: str) -> pd.DataFrame:
    section("Stage 1 — Load sentence data")
    df = pd.read_parquet(path)
    df["published_at"] = pd.to_datetime(df["published_at"], errors="coerce")

    # Cast ArrowDtype string columns
    str_cols = [c for c in df.columns if str(df[c].dtype) == "string"]
    if str_cols:
        df = df.astype({c: "object" for c in str_cols})

    # Clean sentence text
    df["sentence_text"] = df["sentence_text"].fillna("").astype(str).str.strip()
    df["word_count"] = df["word_count"].fillna(0).astype(int)

    # Embedding eligibility flag (used to filter, not to delete)
    df["embedding_eligible"] = (df["word_count"] > MIN_WORDS_FOR_EMBEDDING).astype(int)

    total     = len(df)
    eligible  = df["embedding_eligible"].sum()
    log.info(f"  Total sentences: {total:,}")
    log.info(f"  Embedding-eligible (>{MIN_WORDS_FOR_EMBEDDING} words): {eligible:,}")
    log.info(f"  Excluded (too short): {total - eligible:,}")
    log.info(f"  Stars distribution: "
             f"{df[df['embedding_eligible']==1]['review_stars'].value_counts().sort_index().to_dict()}")
    return df


# ════════════════════════════════════════════════════════════════════════════════
# STAGE 2 — Sentence embeddings (cached)
# ════════════════════════════════════════════════════════════════════════════════

def compute_embeddings(df: pd.DataFrame) -> tuple[np.ndarray, pd.DataFrame]:
    """
    Compute or load cached sentence embeddings.
    Only embedding-eligible sentences are embedded.
    Cache is keyed by a hash of sentence IDs to detect stale caches.
    Returns (embeddings_array, eligible_df).
    """
    section("Stage 2 — Sentence embeddings")

    eligible = df[df["embedding_eligible"] == 1].reset_index(drop=True)
    texts = eligible["sentence_text"].tolist()
    sid_hash = hashlib.md5(
        "".join(eligible["sentence_id"].astype(str).tolist()).encode()
    ).hexdigest()[:16]

    # Check cache
    if os.path.exists(EMBEDDING_CACHE) and os.path.exists(SENTENCE_IDS_CACHE):
        with open(SENTENCE_IDS_CACHE) as f:
            cached_meta = json.load(f)
        if cached_meta.get("sid_hash") == sid_hash:
            embeddings = np.load(EMBEDDING_CACHE)
            log.info(f"  Loaded cached embeddings: {embeddings.shape}")
            return embeddings, eligible

    log.info(f"  Computing embeddings for {len(texts):,} sentences...")
    log.info(f"  Model: {EMBEDDING_MODEL}")
    log.info("  This may take 5–15 minutes on CPU. GPU will be ~10× faster.")

    from sentence_transformers import SentenceTransformer
    model = SentenceTransformer(EMBEDDING_MODEL)

    # Batch encode with progress bar
    embeddings = model.encode(
        texts,
        batch_size=128,
        show_progress_bar=True,
        convert_to_numpy=True,
        normalize_embeddings=True,   # cosine similarity → dot product
    )
    log.info(f"  Embeddings shape: {embeddings.shape}")

    # Save cache
    np.save(EMBEDDING_CACHE, embeddings)
    with open(SENTENCE_IDS_CACHE, "w") as f:
        json.dump({
            "sid_hash": sid_hash,
            "n_sentences": len(texts),
            "model": EMBEDDING_MODEL,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }, f, indent=2)
    log.info(f"  Embeddings cached: {EMBEDDING_CACHE}")

    return embeddings, eligible


# ════════════════════════════════════════════════════════════════════════════════
# STAGE 3 — BERTopic model factory
# ════════════════════════════════════════════════════════════════════════════════

def build_bertopic_model(min_cluster_size: int = HDBSCAN_MIN_CLUSTER_SIZE,
                          nr_topics=NR_TOPICS_HINT) -> "BERTopic":
    """
    Build a BERTopic model with all components configured.
    Uses pre-computed embeddings so SentenceTransformer is not called again.
    """
    from bertopic import BERTopic
    from umap import UMAP
    from hdbscan import HDBSCAN
    from sklearn.feature_extraction.text import CountVectorizer
    from bertopic.representation import MaximalMarginalRelevance

    umap_model = UMAP(
        n_neighbors   = UMAP_N_NEIGHBORS,
        n_components  = UMAP_N_COMPONENTS,
        min_dist      = UMAP_MIN_DIST,
        metric        = UMAP_METRIC,
        random_state  = UMAP_RANDOM_STATE,
        low_memory    = False,
    )
    hdbscan_model = HDBSCAN(
        min_cluster_size   = min_cluster_size,
        min_samples        = HDBSCAN_MIN_SAMPLES,
        metric             = HDBSCAN_METRIC,
        cluster_selection_method = HDBSCAN_CLUSTER_SELECTION,
        prediction_data    = HDBSCAN_PREDICTION_DATA,
        gen_min_span_tree  = True,
    )
    vectorizer_model = CountVectorizer(
        ngram_range     = N_GRAM_RANGE,
        stop_words      = "english",
        min_df          = 3,       # ignore terms appearing in <3 docs (noise filter)
        max_df          = 0.90,    # ignore terms in >90% of docs (too generic)
        token_pattern   = r"(?u)\b[a-zA-Z][a-zA-Z]+\b",  # min 2-char words
    )
    representation_model = MaximalMarginalRelevance(diversity=MMR_DIVERSITY)

    topic_model = BERTopic(
        umap_model          = umap_model,
        hdbscan_model       = hdbscan_model,
        vectorizer_model    = vectorizer_model,
        representation_model= representation_model,
        top_n_words         = TOP_N_WORDS,
        min_topic_size      = min_cluster_size,
        nr_topics           = nr_topics,
        calculate_probabilities = False,  # faster; set True if you need soft assignments
        verbose             = True,
    )
    return topic_model


def fit_bertopic(texts: list[str],
                 embeddings: np.ndarray,
                 run_label: str,
                 min_cluster_size: int = HDBSCAN_MIN_CLUSTER_SIZE,
                 nr_topics=NR_TOPICS_HINT) -> tuple:
    """
    Fit BERTopic on a subset of texts+embeddings.
    Returns (topic_model, topics_list, topic_info_df).
    """
    log.info(f"  [{run_label}] Fitting BERTopic on {len(texts):,} sentences...")
    topic_model = build_bertopic_model(min_cluster_size, nr_topics)
    topics, _ = topic_model.fit_transform(texts, embeddings=embeddings)

    topic_info = topic_model.get_topic_info()
    n_topics = len(topic_info[topic_info["Topic"] != -1])
    n_outliers = (np.array(topics) == -1).sum()
    log.info(f"  [{run_label}] Topics found: {n_topics} | "
             f"Outliers (-1): {n_outliers:,} ({n_outliers/len(topics):.1%})")
    if n_topics > MAX_TOPICS_SAFETY_CAP:
        log.warning(
            f"  [{run_label}] Topic count ({n_topics}) exceeds safety cap "
            f"({MAX_TOPICS_SAFETY_CAP}). This is acceptable for discovery. "
            f"If validation is too heavy, re-run with NR_TOPICS_HINT={MAX_TOPICS_SAFETY_CAP}."
        )
    return topic_model, topics, topic_info


# ════════════════════════════════════════════════════════════════════════════════
# STAGE 4 — Post-processing: enrich topic info
# ════════════════════════════════════════════════════════════════════════════════

def enrich_topic_info(topic_model,
                      topic_info: pd.DataFrame,
                      eligible_df: pd.DataFrame,
                      topics_list: list,
                      total_sentences: int,
                      run_label: str) -> pd.DataFrame:
    """
    Add metadata to the topic_info table:
      - keyword list (clean string)
      - prevalence (% of total eligible corpus)
      - coherence flag
      - representative sentences (top 3 inline)
      - star composition
      - peer group top mention
      - human_label column (empty, for manual fill)
    """
    eligible_df = eligible_df.copy()
    eligible_df["topic"] = topics_list

    rows = []
    for _, row in topic_info.iterrows():
        tid = row["Topic"]
        if tid == -1:
            label_name = "OUTLIER / NOISE"
        else:
            # Get keywords from model
            try:
                kw_tuples = topic_model.get_topic(tid)
                keywords  = [w for w, _ in kw_tuples] if kw_tuples else []
            except Exception:
                keywords = []
            label_name = ", ".join(keywords[:6])

        n_docs = int(row["Count"])
        pct    = n_docs / total_sentences * 100

        # Coherence flag (skip for outlier)
        if tid == -1:
            coherence = "outlier"
        else:
            try:
                kw_tuples = topic_model.get_topic(tid)
                kws = [w for w, _ in kw_tuples] if kw_tuples else []
            except Exception:
                kws = []
            coherence = _topic_coherence_flag(kws)

        # Star composition for this topic
        sub = eligible_df[eligible_df["topic"] == tid]
        if len(sub) and "review_stars" in sub.columns:
            star_counts = sub["review_stars"].value_counts().sort_index().to_dict()
            neg_share = sum(star_counts.get(s, 0) for s in [1, 2, 3]) / len(sub)
            pos_share = sum(star_counts.get(s, 0) for s in [4, 5]) / len(sub)
            dominant_sentiment = (
                "negative" if neg_share >= 0.55 else
                "positive" if pos_share >= 0.75 else
                "mixed"
            )
        else:
            neg_share, pos_share = 0.0, 0.0
            dominant_sentiment = "unknown"

        # Top peer group
        if len(sub) and "operational_peer_group" in sub.columns:
            top_peer = sub["operational_peer_group"].value_counts().idxmax()
        else:
            top_peer = ""

        # Representative sentences (top 3 by centrality proxy — just take first 3)
        rep_sents = sub["sentence_text"].dropna().head(3).tolist()
        rep_text  = " | ".join(rep_sents)

        rows.append({
            "run"               : run_label,
            "topic_id"          : tid,
            "topic_keywords"    : label_name,
            "n_sentences"       : n_docs,
            "prevalence_pct"    : round(pct, 2),
            "negative_share_pct": round(neg_share * 100, 1),
            "positive_share_pct": round(pos_share * 100, 1),
            "dominant_sentiment": dominant_sentiment,
            "top_peer_group"    : top_peer,
            "coherence_flag"    : coherence,
            "representative_sentences": rep_text,
            "human_topic_label" : "",   # fill manually
            "notes"             : "",   # fill manually
        })

    enriched = pd.DataFrame(rows).sort_values("n_sentences", ascending=False)
    return enriched, eligible_df


# ════════════════════════════════════════════════════════════════════════════════
# STAGE 5 — Validation samples
# ════════════════════════════════════════════════════════════════════════════════

def build_validation_samples(eligible_df: pd.DataFrame,
                              enriched_info: pd.DataFrame) -> dict:
    """
    For each topic, draw up to VALIDATION_N_PER_TOPIC representative sentences.
    For outlier (-1), draw VALIDATION_N_OUTLIER samples.
    Returns dict of topic_id → DataFrame.
    """
    rng = np.random.default_rng(seed=42)
    sample_cols = [
        "sentence_id", "sentence_text", "word_count",
        "review_stars", "restaurant_name", "operational_peer_group",
        "published_at", "topic",
    ]
    sc = [c for c in sample_cols if c in eligible_df.columns]

    sheets = {}
    for _, row in enriched_info.iterrows():
        tid   = row["topic_id"]
        label = row["topic_keywords"][:40] if row["topic_keywords"] else "?"
        n_draw = VALIDATION_N_OUTLIER if tid == -1 else VALIDATION_N_PER_TOPIC

        sub = eligible_df[eligible_df["topic"] == tid]
        if len(sub) == 0:
            continue
        n_actual = min(n_draw, len(sub))
        idx = rng.choice(sub.index.tolist(), size=n_actual, replace=False)
        sample = sub.loc[idx, sc].copy()
        # Add empty annotation columns for human review
        sample["human_topic_label"] = ""
        sample["annotation_notes"]  = ""

        raw_name   = f"T{tid}_{label}"
        sheet_name = raw_name.replace("/","_").replace("\\","_") \
            .replace("?","").replace("*","").replace("[","").replace("]","") \
            .replace(":","")[:31]
        sheets[sheet_name] = sample

    return sheets


# ════════════════════════════════════════════════════════════════════════════════
# STAGE 6 — Charts
# ════════════════════════════════════════════════════════════════════════════════

def chart_topic_prevalence(enriched_info: pd.DataFrame,
                           run_label: str,
                           out_dir: str) -> None:
    """Horizontal bar chart of topic prevalence (excluding outlier)."""
    plot_df = enriched_info[enriched_info["topic_id"] != -1].copy()
    plot_df = plot_df.sort_values("prevalence_pct", ascending=True).tail(30)

    colors = [
        "#D85A30" if s == "negative" else
        "#1D9E75" if s == "positive" else
        "#7F77DD"
        for s in plot_df["dominant_sentiment"]
    ]
    fig, ax = plt.subplots(figsize=(10, max(5, len(plot_df) * 0.38)))
    ax.barh(range(len(plot_df)), plot_df["prevalence_pct"],
            color=colors, height=0.7, edgecolor="white")
    ax.set_yticks(range(len(plot_df)))
    ax.set_yticklabels(
        [f"T{tid}: {kw[:45]}"
         for tid, kw in zip(plot_df["topic_id"], plot_df["topic_keywords"])],
        fontsize=8
    )
    ax.set_xlabel("Prevalence (% of eligible corpus)")
    ax.set_title(f"BERTopic — Topic prevalence [{run_label}]\n"
                 f"(green=positive-dominant, red=negative-dominant, purple=mixed)",
                 fontweight="bold", fontsize=10)
    from matplotlib.patches import Patch
    ax.legend(handles=[
        Patch(color="#1D9E75", label="Positive-dominant"),
        Patch(color="#D85A30", label="Negative-dominant"),
        Patch(color="#7F77DD", label="Mixed"),
    ], fontsize=8, loc="lower right")
    ax.grid(axis="x", alpha=0.3)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    plt.tight_layout()
    save_png(fig, os.path.join(out_dir, "topic_prevalence_chart.png"))


def chart_umap_scatter(embeddings_2d: np.ndarray,
                       topics: list,
                       run_label: str,
                       out_dir: str) -> None:
    """2D UMAP scatter plot coloured by topic."""
    n_topics = len(set(t for t in topics if t != -1))
    cmap = plt.cm.get_cmap("tab20", max(n_topics, 1))

    fig, ax = plt.subplots(figsize=(10, 8))
    # Outliers in light grey first
    mask_out = np.array(topics) == -1
    if mask_out.any():
        ax.scatter(embeddings_2d[mask_out, 0], embeddings_2d[mask_out, 1],
                   c="#D3D1C7", s=4, alpha=0.3, label="Outlier", zorder=1)
    # Topics coloured
    for tid in sorted(set(t for t in topics if t != -1))[:20]:
        mask = np.array(topics) == tid
        ax.scatter(embeddings_2d[mask, 0], embeddings_2d[mask, 1],
                   color=cmap(tid % 20), s=6, alpha=0.6,
                   label=f"T{tid}", zorder=2)
    ax.set_title(f"UMAP 2D embedding — [{run_label}]\n"
                 f"(each point = one sentence; colour = topic)",
                 fontweight="bold", fontsize=10)
    ax.set_xlabel("UMAP dim 1")
    ax.set_ylabel("UMAP dim 2")
    ax.legend(fontsize=7, markerscale=2, loc="upper right",
              ncol=2, framealpha=0.7)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    plt.tight_layout()
    save_png(fig, os.path.join(out_dir, "umap_scatter.png"))


def chart_star_heatmap(enriched_info: pd.DataFrame,
                       run_label: str,
                       out_dir: str) -> None:
    """Heatmap of negative_share vs positive_share per topic."""
    plot_df = enriched_info[enriched_info["topic_id"] != -1].copy()
    plot_df = plot_df.sort_values("negative_share_pct", ascending=False).head(20)

    fig, ax = plt.subplots(figsize=(8, max(4, len(plot_df) * 0.4)))
    data = plot_df[["negative_share_pct", "positive_share_pct"]].values.T
    labels_y = ["Negative %", "Positive %"]
    labels_x = [f"T{tid}: {kw[:30]}"
                 for tid, kw in zip(plot_df["topic_id"], plot_df["topic_keywords"])]
    im = ax.imshow(data, cmap="RdYlGn", aspect="auto",
                   vmin=0, vmax=100)
    ax.set_xticks(range(len(labels_x)))
    ax.set_xticklabels(labels_x, rotation=45, ha="right", fontsize=7)
    ax.set_yticks([0, 1])
    ax.set_yticklabels(labels_y, fontsize=9)
    for i in range(2):
        for j in range(len(plot_df)):
            ax.text(j, i, f"{data[i, j]:.0f}%",
                    ha="center", va="center", fontsize=7, fontweight="bold",
                    color="black" if 25 < data[i, j] < 75 else "white")
    plt.colorbar(im, ax=ax, label="Share (%)")
    ax.set_title(f"Topic sentiment composition [{run_label}]\n"
                 f"(top 20 topics by negative share — sorted by complaint intensity)",
                 fontweight="bold", fontsize=9)
    plt.tight_layout()
    save_png(fig, os.path.join(out_dir, "topic_sentiment_heatmap.png"))


# ════════════════════════════════════════════════════════════════════════════════
# STAGE 7 — Per-run output writer
# ════════════════════════════════════════════════════════════════════════════════

def run_and_save(run_id: str,
                 run_label: str,
                 texts: list[str],
                 embeddings: np.ndarray,
                 eligible_df: pd.DataFrame,
                 total_n: int,
                 min_cluster_size: int = HDBSCAN_MIN_CLUSTER_SIZE,
                 nr_topics=NR_TOPICS_HINT) -> tuple:
    """
    Full run cycle: fit → enrich → validate → chart → save.
    Returns (enriched_info, eligible_with_topics).
    """
    out_dir = os.path.join(OUT_DIR, run_id)
    os.makedirs(out_dir, exist_ok=True)
    log.info(f"\n{'─'*60}\n  {run_label} — {len(texts):,} sentences\n{'─'*60}")

    # Fit model
    topic_model, topics, topic_info = fit_bertopic(
        texts, embeddings, run_label, min_cluster_size, nr_topics
    )

    # Enrich
    enriched, eligible_with_topics = enrich_topic_info(
        topic_model, topic_info, eligible_df.copy(),
        topics, total_n, run_label
    )

    # Save topic assignments parquet
    sent_topics = eligible_with_topics[[
        c for c in [
            "sentence_id", "review_id", "restaurant_id", "restaurant_name",
            "review_stars", "operational_peer_group", "cuisine_cluster",
            "published_at", "sentence_text", "word_count",
            "is_short_segment", "contains_negation", "contains_contrast",
            "topic",
        ] if c in eligible_with_topics.columns
    ]].copy()
    sent_topics.to_parquet(os.path.join(out_dir, "topics.parquet"), index=False)

    # Save topic_info Excel
    write_xlsx({"Topic Info": enriched}, os.path.join(out_dir, "topic_info.xlsx"))

    # Validation samples
    val_sheets = build_validation_samples(eligible_with_topics, enriched)
    write_xlsx(val_sheets, os.path.join(out_dir, "topic_validation_samples.xlsx"))

    # Charts
    chart_topic_prevalence(enriched, run_label, out_dir)
    chart_star_heatmap(enriched, run_label, out_dir)

    # UMAP 2D visualisation (separate lower-dim projection just for plotting)
    try:
        log.info("  Computing 2D UMAP for scatter plot...")
        from umap import UMAP as UMAP2D
        umap_2d = UMAP2D(
            n_components=UMAP_N_COMPONENTS_VIZ,
            n_neighbors=UMAP_N_NEIGHBORS,
            min_dist=0.1,
            metric=UMAP_METRIC,
            random_state=UMAP_RANDOM_STATE,
        )
        emb_2d = umap_2d.fit_transform(embeddings)
        chart_umap_scatter(emb_2d, topics, run_label, out_dir)
    except Exception as e:
        log.warning(f"  UMAP 2D scatter skipped: {e}")

    log.info(f"  [{run_label}] Run complete. Output: {out_dir}")
    return enriched, eligible_with_topics, topic_model


# ════════════════════════════════════════════════════════════════════════════════
# STAGE 8 — Peer group prevalence analysis (uses Run 1 topic assignments)
# ════════════════════════════════════════════════════════════════════════════════

def run_peer_group_analysis(eligible_with_topics: pd.DataFrame,
                             enriched_info_r1: pd.DataFrame) -> None:
    """
    Instead of training separate BERTopic models per peer group,
    we assign Run 1 topics to sentences and compute prevalence per peer group.
    This avoids small-sample instability in per-group models.
    """
    out_dir = os.path.join(OUT_DIR, "run4_peer_group")
    os.makedirs(out_dir, exist_ok=True)
    section("Run 4 — Peer-group topic prevalence")

    df = eligible_with_topics.copy()
    if "operational_peer_group" not in df.columns or "topic" not in df.columns:
        log.warning("  Skipping peer group analysis — missing columns.")
        return

    # Remove outlier topics
    df = df[df["topic"] != -1]

    # Cross-tabulation: rows = topic, cols = peer group (prevalence %)
    crosstab = pd.crosstab(
        df["topic"],
        df["operational_peer_group"],
        normalize="columns",
    ) * 100

    # Merge with topic keywords
    kw_map = enriched_info_r1[enriched_info_r1["topic_id"] != -1].set_index("topic_id")[
        "topic_keywords"
    ].to_dict()
    crosstab.index = [f"T{tid}: {kw_map.get(tid, '')[:40]}"
                      for tid in crosstab.index]
    crosstab = crosstab.round(2)

    # Keep only peer groups that exist in data
    peer_cols = [p for p in PEER_ORDER if p in crosstab.columns]
    crosstab = crosstab[peer_cols]

    # Top-N topics by variance (most differentiating)
    crosstab["variance"] = crosstab.var(axis=1)
    crosstab_sorted = crosstab.sort_values("variance", ascending=False).drop(
        columns="variance"
    )

    # Excel output
    summary_by_peer = []
    for pg in peer_cols:
        grp = df[df["operational_peer_group"] == pg]
        top_topic = grp["topic"].value_counts().idxmax() if len(grp) else None
        top_kw    = kw_map.get(top_topic, "") if top_topic else ""
        neg_share = (grp["review_stars"].isin([1, 2, 3]).sum() / len(grp) * 100
                     if len(grp) else 0)
        summary_by_peer.append({
            "peer_group"     : pg,
            "n_sentences"    : len(grp),
            "top_topic"      : f"T{top_topic}: {top_kw}" if top_topic else "",
            "negative_share_pct": round(neg_share, 1),
        })

    write_xlsx(
        {"Prevalence by Peer Group": crosstab_sorted.reset_index(),
         "Peer Group Summary"      : pd.DataFrame(summary_by_peer)},
        os.path.join(out_dir, "peer_group_topic_prevalence.xlsx")
    )

    # Heatmap chart (top 20 most-differentiating topics)
    plot_data = crosstab_sorted.head(20)
    fig, ax = plt.subplots(figsize=(max(8, len(peer_cols)*2),
                                    max(6, len(plot_data)*0.4)))
    sns.heatmap(
        plot_data, annot=True, fmt=".1f", cmap="YlOrRd",
        linewidths=0.5, ax=ax, cbar_kws={"label": "% of peer group sentences"},
        annot_kws={"size": 8}
    )
    ax.set_title("Topic prevalence by operational peer group\n"
                 "(top 20 most-differentiating topics; % within each peer group)",
                 fontweight="bold", fontsize=10)
    ax.set_xlabel("")
    ax.set_ylabel("Topic")
    ax.tick_params(axis="x", rotation=25, labelsize=8)
    ax.tick_params(axis="y", labelsize=7)
    plt.tight_layout()
    save_png(fig, os.path.join(out_dir, "peer_group_heatmap.png"))
    log.info("  Peer-group analysis complete.")


# ════════════════════════════════════════════════════════════════════════════════
# STAGE 9 — Recent vs historical comparison (Run 5)
# ════════════════════════════════════════════════════════════════════════════════

def run_recent_analysis(df_full: pd.DataFrame,
                         embeddings_full: np.ndarray,
                         eligible_df_full: pd.DataFrame,
                         enriched_r1: pd.DataFrame,
                         eligible_r1: pd.DataFrame) -> None:
    """
    Run BERTopic on recent (last 12M) sentences separately,
    then compare topic prevalence to historical period.
    Also adds a 'topic trend' column to the master summary.
    """
    out_dir = os.path.join(OUT_DIR, "run5_recent")
    os.makedirs(out_dir, exist_ok=True)
    section("Run 5 — Recent period analysis")

    cutoff = eligible_df_full["published_at"].max() - pd.DateOffset(months=RECENT_MONTHS)
    recent_mask  = eligible_df_full["published_at"] >= cutoff
    hist_mask    = eligible_df_full["published_at"] <  cutoff

    recent_df   = eligible_df_full[recent_mask].reset_index(drop=True)
    recent_emb  = embeddings_full[recent_mask.values]

    log.info(f"  Recent ({RECENT_MONTHS}M): {len(recent_df):,} sentences | "
             f"Historical: {hist_mask.sum():,} sentences")

    if len(recent_df) < 100:
        log.warning("  Recent corpus too small for reliable BERTopic. Skipping Run 5.")
        return

    # Fit on recent
    enriched_r5, recent_with_topics, _ = run_and_save(
        run_id       = "run5_recent",
        run_label    = f"Recent {RECENT_MONTHS}M",
        texts        = recent_df["sentence_text"].tolist(),
        embeddings   = recent_emb,
        eligible_df  = recent_df,
        total_n      = len(recent_df),
        min_cluster_size = max(15, HDBSCAN_MIN_CLUSTER_SIZE // 2),  # smaller threshold for subset
    )

    # Compare Run 1 topic prevalence: recent vs historical
    r1_recent = eligible_r1[eligible_r1["published_at"] >= cutoff]
    r1_hist   = eligible_r1[eligible_r1["published_at"] <  cutoff]

    def _prevalence(df_sub, total):
        if total == 0 or "topic" not in df_sub.columns:
            return {}
        return (df_sub[df_sub["topic"] != -1]["topic"]
                .value_counts()
                .div(total)
                .mul(100)
                .round(2)
                .to_dict())

    recent_prev  = _prevalence(r1_recent, len(r1_recent))
    hist_prev    = _prevalence(r1_hist,   len(r1_hist))
    kw_map       = enriched_r1[enriched_r1["topic_id"] != -1].set_index("topic_id")[
                       "topic_keywords"].to_dict()

    trend_rows = []
    for tid in set(list(recent_prev.keys()) + list(hist_prev.keys())):
        r_pct = recent_prev.get(tid, 0.0)
        h_pct = hist_prev.get(tid, 0.0)
        delta = r_pct - h_pct
        trend_rows.append({
            "topic_id"         : tid,
            "topic_keywords"   : kw_map.get(tid, ""),
            "recent_pct"       : r_pct,
            "historical_pct"   : h_pct,
            "change_pct_points": round(delta, 2),
            "trend"            : "↑ increasing" if delta >= 0.5 else
                                 "↓ decreasing" if delta <= -0.5 else
                                 "→ stable",
        })
    trend_df = pd.DataFrame(trend_rows).sort_values("change_pct_points", ascending=False)

    write_xlsx(
        {"Trend Comparison": trend_df,
         "Recent Topics"   : enriched_r5},
        os.path.join(out_dir, "topic_trend_comparison.xlsx")
    )

    # Chart: top emerging and declining topics
    top_inc = trend_df[trend_df["change_pct_points"] > 0].head(10)
    top_dec = trend_df[trend_df["change_pct_points"] < 0].tail(10)
    plot_df = pd.concat([top_inc, top_dec]).sort_values("change_pct_points")

    if len(plot_df):
        fig, ax = plt.subplots(figsize=(9, max(4, len(plot_df) * 0.45)))
        colors_t = ["#D85A30" if v < 0 else "#1D9E75"
                    for v in plot_df["change_pct_points"]]
        ax.barh(range(len(plot_df)), plot_df["change_pct_points"],
                color=colors_t, height=0.7)
        ax.set_yticks(range(len(plot_df)))
        ax.set_yticklabels(
            [f"T{tid}: {kw[:40]}"
             for tid, kw in zip(plot_df["topic_id"], plot_df["topic_keywords"])],
            fontsize=8
        )
        ax.axvline(0, color="black", lw=0.8)
        ax.set_xlabel("Change in prevalence (percentage points)")
        ax.set_title(f"Topic trend — recent {RECENT_MONTHS}M vs historical\n"
                     "(green = growing; red = declining)",
                     fontweight="bold", fontsize=9)
        ax.grid(axis="x", alpha=0.3)
        ax.spines["top"].set_visible(False)
        ax.spines["right"].set_visible(False)
        plt.tight_layout()
        save_png(fig, os.path.join(out_dir, "topic_trend_chart.png"))

    log.info("  Recent analysis complete.")


# ════════════════════════════════════════════════════════════════════════════════
# STAGE 10 — Master summary and topic-to-aspect mapping draft
# ════════════════════════════════════════════════════════════════════════════════

def build_master_summary(all_enriched: dict) -> None:
    """
    Concatenate all run topic tables into one master summary.
    Produces bertopic_summary.xlsx.
    """
    section("Stage 10 — Master summary")
    frames = []
    for run_id, df in all_enriched.items():
        df = df.copy()
        df["run_id"] = run_id
        frames.append(df)

    if not frames:
        return

    master = pd.concat(frames, ignore_index=True)
    write_xlsx({"Master Summary": master}, os.path.join(OUT_DIR, "bertopic_summary.xlsx"))
    log.info(f"  Master summary: {len(master)} topic rows across {len(frames)} runs")


def build_topic_to_aspect_mapping(enriched_r1: pd.DataFrame,
                                   enriched_r2: pd.DataFrame,
                                   enriched_r3: pd.DataFrame) -> None:
    """
    Pre-fill a topic-to-aspect mapping draft for human review.
    Combines topics from all three main runs, de-duped by keyword similarity.
    Each topic gets an empty 'suggested_aspect' column for the analyst to fill.
    """
    section("Stage 10b — Topic-to-aspect mapping draft")
    out_path = os.path.join(OUT_DIR, "topic_to_aspect_mapping_draft.xlsx")

    # Combine all non-outlier topics
    frames = []
    for run_label, df in [("Run1_All", enriched_r1),
                           ("Run2_Negative", enriched_r2),
                           ("Run3_Positive", enriched_r3)]:
        sub = df[df["topic_id"] != -1].copy()
        sub["source_run"] = run_label
        frames.append(sub)

    if not frames:
        return
    combined = pd.concat(frames, ignore_index=True)

    # Keep columns useful for mapping
    map_cols = [
        "source_run", "topic_id", "topic_keywords",
        "n_sentences", "prevalence_pct",
        "negative_share_pct", "positive_share_pct", "dominant_sentiment",
        "top_peer_group", "coherence_flag", "representative_sentences",
    ]
    mapping = combined[[c for c in map_cols if c in combined.columns]].copy()

    # Add aspect taxonomy columns (blank — human fills these)
    mapping["suggested_aspect"]     = ""
    mapping["aspect_certainty"]     = ""  # high / medium / low
    mapping["mapping_notes"]        = ""

    # Add taxonomy reference sheet
    tax_df = pd.DataFrame(ASPECT_TAXONOMY_DRAFT,
                           columns=["aspect_name", "description"])
    tax_df["include_examples"] = ""
    tax_df["exclude_examples"] = ""
    tax_df["positive_example"] = ""
    tax_df["negative_example"] = ""
    tax_df["ambiguous_example"]= ""
    tax_df["kpi_linkage"]      = ""

    write_xlsx(
        {"Topic Mapping (fill this)": mapping,
         "Aspect Taxonomy v1"       : tax_df},
        out_path
    )
    log.info(f"  Topic-to-aspect mapping draft: {len(mapping)} rows")


# ════════════════════════════════════════════════════════════════════════════════
# STAGE 11 — Annotation sample (for Step 8/9 handoff)
# ════════════════════════════════════════════════════════════════════════════════

def build_annotation_sample(df_full: pd.DataFrame,
                              eligible_r1: pd.DataFrame,
                              clauses_path: str = None) -> None:
    """
    Build a clause-level annotation sample (Option B) ~1,200 records.

    Option B: sample sentences → expand to all their clauses.
    Each clause is the annotation unit; sentence_text is context for annotator.

    Stratification (at sentence level, expanded to clauses):
      A — Negative reviews (1-3 star): 35%
      B — Contrast / negation:         15%
      C — High-negative-share topics:  15%
      D — Restaurant minimum (25/rest): enforced
      E — Rare topics (bottom 20%):     5%
      F — Positive top-up:             remainder to 1,200
    """
    section("Stage 11 — Clause-level annotation sample (v2)")

    TARGET_CLAUSES     = 1200
    MIN_PER_RESTAURANT = 25
    PILOT_N            = 200
    rng = np.random.default_rng(seed=42)

    if clauses_path is None or not os.path.exists(clauses_path):
        log.warning("  Clauses parquet not found — fallback to sentence-level.")
        _build_sentence_annotation_fallback(eligible_r1, rng)
        return

    clauses = pd.read_parquet(clauses_path)
    str_cols = [c for c in clauses.columns if str(clauses[c].dtype) == "string"]
    if str_cols:
        clauses = clauses.astype({c: "object" for c in str_cols})
    for col in ["clause_text", "sentence_text"]:
        clauses[col] = clauses[col].fillna("").astype(str).str.strip()
    clauses["published_at"] = pd.to_datetime(clauses["published_at"], errors="coerce")

    elig = clauses[
        (clauses["gold_annotation_eligible"].fillna(0) == 1) &
        (clauses["suspicious_duplicate_flag"].fillna(0) == 0) &
        (clauses["clause_text"].str.len() > 0)
    ].copy()
    log.info(f"  Eligible clauses: {len(elig):,}")

    # Join Run 1 topic assignments via sentence_id
    if "topic" in eligible_r1.columns and "sentence_id" in eligible_r1.columns:
        tmap = eligible_r1.set_index("sentence_id")["topic"].to_dict()
        elig["topic"] = elig["sentence_id"].map(tmap).fillna(-99).astype(int)
        log.info(f"  Topic join: {(elig['topic']!=-99).sum()} matched, "
                 f"{(elig['topic']==-99).sum()} unmatched (topic=-99)")
    else:
        elig["topic"] = -99

    def _clauses_for(sids):
        return elig[elig["sentence_id"].isin(sids)]

    def _pick_sents(pool, n_clause_target):
        cpc = pool.groupby("sentence_id").size().reset_index(name="n")
        if len(cpc) == 0:
            return set()
        order = rng.permutation(len(cpc))
        sel, acc = set(), 0
        for i in order:
            if acc >= n_clause_target:
                break
            sel.add(cpc.iloc[i]["sentence_id"])
            acc += int(cpc.iloc[i]["n"])
        return sel

    sel = set()

    # A — Negative
    pool_a = elig[elig["review_stars"].isin([1, 2, 3])]
    sids_a = _pick_sents(pool_a, int(TARGET_CLAUSES * 0.35))
    sel.update(sids_a)
    log.info(f"  A neg: {len(sids_a)} sents -> {len(_clauses_for(sids_a))} clauses")

    # B — Contrast/negation
    is_neg_col = elig["contains_negation"].fillna(0)
    is_con_col = elig["contains_contrast"].fillna(0)
    is_cc_col  = elig.get("is_contrast_clause", pd.Series(0, index=elig.index)).fillna(0)
    pool_b = elig[(is_neg_col==1)|(is_con_col==1)|(is_cc_col==1)]
    sids_b = _pick_sents(pool_b, int(TARGET_CLAUSES * 0.15))
    sel.update(sids_b)
    log.info(f"  B contrast: {len(sids_b)} sents -> {len(_clauses_for(sids_b))} clauses")

    # C — High-negative-share topics
    if elig["topic"].nunique() > 2:
        neg_rate = (
            elig[elig["review_stars"].isin([1,2,3])].groupby("topic").size()
            .div(elig.groupby("topic").size()).fillna(0)
        )
        high_neg_t = set(neg_rate[neg_rate >= 0.40].index) - {-99}
        pool_c = elig[elig["topic"].isin(high_neg_t)]
        sids_c = _pick_sents(pool_c, int(TARGET_CLAUSES * 0.15))
        sel.update(sids_c)
        log.info(f"  C high-neg topics: {len(sids_c)} sents added")

    # D — Restaurant minimum
    for rid, rgrp in elig.groupby("restaurant_id"):
        already = len(_clauses_for(sel)[_clauses_for(sel)["restaurant_id"]==rid]) if sel else 0
        if already < MIN_PER_RESTAURANT:
            pool_d = rgrp[~rgrp["sentence_id"].isin(sel)]
            sel.update(_pick_sents(pool_d, MIN_PER_RESTAURANT - already))
    log.info(f"  D restaurant min: {len(sel)} total sents selected")

    # E — Rare topics
    if elig["topic"].nunique() > 5:
        tsizes = elig[elig["topic"] >= 0]["topic"].value_counts()
        rare_t = set(tsizes[tsizes <= tsizes.quantile(0.20)].index)
        pool_e = elig[elig["topic"].isin(rare_t)]
        sids_e = _pick_sents(pool_e, int(TARGET_CLAUSES * 0.05))
        sel.update(sids_e)
        log.info(f"  E rare topics: {len(sids_e)} sents added")

    # F — Positive top-up
    cur_n = len(_clauses_for(sel))
    if cur_n < TARGET_CLAUSES:
        pool_f = elig[
            elig["review_stars"].isin([4,5]) &
            ~elig["sentence_id"].isin(sel)
        ]
        sel.update(_pick_sents(pool_f, TARGET_CLAUSES - cur_n))
        log.info(f"  F positive top-up added")

    # Final dataset
    ann = _clauses_for(sel).copy()
    sort_cols = [c for c in ["restaurant_id","review_id",
                              "sentence_position","clause_position"]
                 if c in ann.columns]
    ann = ann.sort_values(sort_cols).reset_index(drop=True)

    out_cols = [
        "clause_id","sentence_id","review_id",
        "restaurant_id","restaurant_name",
        "review_stars","operational_peer_group","cuisine_cluster","published_at",
        "clause_text","sentence_text",
        "clause_position","clause_count_in_sentence",
        "word_count","split_method","split_trigger",
        "contains_negation","contains_contrast","is_contrast_clause",
        "gold_annotation_eligible","suspicious_duplicate_flag","topic",
    ]
    ann = ann[[c for c in out_cols if c in ann.columns]].copy()

    for col in ["aspect_category","sentiment","opinion_phrase",
                "implicit_aspect","severity","return_intention",
                "ambiguity_flag","annotator_notes"]:
        ann[col] = ""

    # Pilot: balanced across restaurants
    pilot_parts = []
    n_rests = ann["restaurant_id"].nunique()
    for rid, rg in ann.groupby("restaurant_id"):
        pilot_parts.append(rg.head(max(1, PILOT_N // n_rests)))
    pilot_df = pd.concat(pilot_parts).drop_duplicates("clause_id").head(PILOT_N)
    main_df  = ann[~ann["clause_id"].isin(pilot_df["clause_id"])].copy()

    rest_summ = ann.groupby(["restaurant_id","restaurant_name"]).agg(
        n_clauses     =("clause_id","count"),
        neg_share_pct =("review_stars", lambda x: (x.isin([1,2,3])).mean()*100),
        avg_stars     =("review_stars","mean"),
    ).round(2).reset_index()
    below_min = rest_summ[rest_summ["n_clauses"] < MIN_PER_RESTAURANT]

    log.info(f"  Final: {len(ann):,} clauses (pilot={len(pilot_df)}, main={len(main_df)})")
    log.info(f"  Stars: {ann['review_stars'].value_counts().sort_index().to_dict()}")
    log.info(f"  Neg share: {ann['review_stars'].isin([1,2,3]).mean():.1%}")
    log.info(f"  Restaurants: {ann['restaurant_id'].nunique()}/25")
    if len(below_min):
        log.warning(f"  Below min {MIN_PER_RESTAURANT}: "
                    f"{below_min.set_index('restaurant_name')['n_clauses'].to_dict()}")

    write_xlsx(
        {"Pilot 200 — annotate first" : pilot_df,
         "Main pool 1000+"            : main_df,
         "Full pool (all clauses)"    : ann,
         "Restaurant coverage"        : rest_summ},
        os.path.join(OUT_DIR, "annotation_sample_v2_clause.xlsx")
    )
    log.info("  Saved: annotation_sample_v2_clause.xlsx")
    log.info("  Unit=clause_text | Context=sentence_text | topic=-99=not in BERTopic")


def _build_sentence_annotation_fallback(eligible_r1: pd.DataFrame,
                                         rng: np.random.Generator) -> None:
    """Fallback: sentence-level when clauses parquet is unavailable."""
    log.warning("  Fallback: sentence-level annotation sample.")
    ann = eligible_r1.sample(n=min(1000, len(eligible_r1)), random_state=42).copy()
    for col in ["aspect_category","sentiment","opinion_phrase","annotator_notes"]:
        ann[col] = ""
    write_xlsx({"Fallback sentence sample": ann},
               os.path.join(OUT_DIR, "annotation_sample_v2_clause.xlsx"))


# MAIN
# ════════════════════════════════════════════════════════════════════════════════

def main():
    print("=" * 70)
    print("  Peterborough Restaurant Reviews — BERTopic Discovery Pipeline")
    print(f"  Run at: {datetime.now(timezone.utc).isoformat()}")
    print(f"  Input  : {SENTENCES_IN}")
    print(f"  Output : {OUT_DIR}")
    print(f"  Embedding model: {EMBEDDING_MODEL}")
    print(f"  HDBSCAN min_cluster_size: {HDBSCAN_MIN_CLUSTER_SIZE}")
    print("=" * 70)

    # Stage 1 — Load
    df = load_sentences(SENTENCES_IN)

    # Stage 2 — Embeddings (cached after first run)
    embeddings, eligible_df = compute_embeddings(df)

    # ── Run 1: Full corpus ────────────────────────────────────────────────────
    section("Run 1 — Full corpus")
    enriched_r1, eligible_r1, model_r1 = run_and_save(
        run_id      = "run1_all",
        run_label   = "Full corpus",
        texts       = eligible_df["sentence_text"].tolist(),
        embeddings  = embeddings,
        eligible_df = eligible_df,
        total_n     = len(eligible_df),
        nr_topics   = None,   # discovery mode: no topic reduction
    )

    # ── Run 2: Negative corpus (1–3★) ────────────────────────────────────────
    section("Run 2 — Negative corpus (1–3★)")
    neg_mask    = eligible_df["review_stars"].isin([1, 2, 3])
    neg_df      = eligible_df[neg_mask].reset_index(drop=True)
    neg_emb     = embeddings[neg_mask.values]
    enriched_r2, eligible_r2, _ = run_and_save(
        run_id      = "run2_negative",
        run_label   = "Negative (1–3★)",
        texts       = neg_df["sentence_text"].tolist(),
        embeddings  = neg_emb,
        eligible_df = neg_df,
        total_n     = len(neg_df),
        min_cluster_size = max(10, HDBSCAN_MIN_CLUSTER_SIZE // 2),
        nr_topics   = None,   # discovery mode: no topic reduction
    )

    # ── Run 3: Positive corpus (4–5★) ────────────────────────────────────────
    section("Run 3 — Positive corpus (4–5★)")
    pos_mask    = eligible_df["review_stars"].isin([4, 5])
    pos_df      = eligible_df[pos_mask].reset_index(drop=True)
    pos_emb     = embeddings[pos_mask.values]
    enriched_r3, eligible_r3, _ = run_and_save(
        run_id      = "run3_positive",
        run_label   = "Positive (4–5★)",
        texts       = pos_df["sentence_text"].tolist(),
        embeddings  = pos_emb,
        eligible_df = pos_df,
        total_n     = len(pos_df),
        nr_topics   = None,   # discovery mode: no topic reduction
    )

    # ── Run 4: Peer group prevalence (reuse Run 1 assignments) ───────────────
    run_peer_group_analysis(eligible_r1, enriched_r1)

    # ── Run 5: Recent period ──────────────────────────────────────────────────
    run_recent_analysis(df, embeddings, eligible_df, enriched_r1, eligible_r1)

    # ── Master summary ────────────────────────────────────────────────────────
    build_master_summary({
        "run1_all"      : enriched_r1,
        "run2_negative" : enriched_r2,
        "run3_positive" : enriched_r3,
    })

    # ── Topic-to-aspect mapping draft ─────────────────────────────────────────
    build_topic_to_aspect_mapping(enriched_r1, enriched_r2, enriched_r3)

    # ── Annotation sample ─────────────────────────────────────────────────────
    build_annotation_sample(df, eligible_r1, clauses_path=CLAUSES_IN)

    # ── Final print ───────────────────────────────────────────────────────────
    print("\n" + "=" * 70)
    print("  BERTopic pipeline complete.")
    print(f"  Input sentences (eligible): {len(eligible_df):,}")
    print(f"  Topics found (Run 1):       "
          f"{len(enriched_r1[enriched_r1['topic_id'] != -1])}")
    print(f"  Topics found (Run 2 neg):   "
          f"{len(enriched_r2[enriched_r2['topic_id'] != -1])}")
    print(f"  Topics found (Run 3 pos):   "
          f"{len(enriched_r3[enriched_r3['topic_id'] != -1])}")
    print()
    print("  Outputs written to:")
    for item in [
        "embeddings_cache.npy",
        "run1_all/  (topics.parquet, topic_info.xlsx, charts)",
        "run2_negative/",
        "run3_positive/",
        "run4_peer_group/  (peer_group_topic_prevalence.xlsx, heatmap)",
        "run5_recent/  (topic_trend_comparison.xlsx, trend chart)",
        "bertopic_summary.xlsx",
        "topic_to_aspect_mapping_draft.xlsx",
        "annotation_sample_v2_clause.xlsx  (clause-level, ~1200 records)",
    ]:
        print(f"    {item}")
    print()
    print("  NEXT STEPS (manual work before Step 8):")
    print("  ─────────────────────────────────────────")
    print("  1. Open topic_to_aspect_mapping_draft.xlsx")
    print("     → For each topic row: fill 'suggested_aspect' from the taxonomy tab")
    print("     → Set 'aspect_certainty' (high/medium/low)")
    print("     → Note merges, splits or new aspects in 'mapping_notes'")
    print()
    print("  2. Open bertopic_summary.xlsx + run1_all/topic_validation_samples.xlsx")
    print("     → Read 20–30 sentences per topic")
    print("     → Fill 'human_topic_label' with a plain-English topic name")
    print("     → Flag coherence issues (generic, noisy, too broad)")
    print()
    print("  3. If >15% of topics are flagged as generic or incoherent:")
    print("     → Increase HDBSCAN_MIN_CLUSTER_SIZE (try 40–50)")
    print("     → Re-run this script (embeddings are cached — fast)")
    print()
    print("  4. Open annotation_sample_v2_clause.xlsx → sheet 'Pilot 200 — annotate first'")
    print("     → Annotate using aspect_taxonomy from topic_to_aspect_mapping_draft")
    print("     → After pilot: revise taxonomy, then annotate main pool")
    print("=" * 70)


if __name__ == "__main__":
    main()
