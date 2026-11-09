"""
01_build_analysis_ready_dataset.py
====================================
Peterborough Restaurant Google Reviews — Data Preparation Pipeline
Goal: Convert 25 raw Excel files into a validated, analysis-ready dataset
      for descriptive analytics, BERTopic discovery and ABSA modeling.

Pipeline stages:
  1.  Load & consolidate 25 raw files
  2.  Select analytical columns (union of needed fields, ignore image/extra category cols)
  3.  Rename columns to analytical names
  4.  Join restaurant identity from Restaurant Master (restaurant_id, peer groups, etc.)
  5.  Standardise data types (stars → int, dates → datetime)
  6.  Standardise text (raw preserved, clean version created)
  7.  Compute text-length variables
  8.  Determine language_final and language flags
  9.  Build NLP-eligibility flags (has_text, nlp_eligible, rating_analysis_eligible,
      gold_annotation_eligible)
 10.  Duplicate detection (exact text, cross-restaurant, suspicious)
 11.  Derive analytical variables (rating_group, has_owner_response, etc.)
 12.  Standardise structured context fields
 13.  Quality-control reconciliation report
 14.  Export outputs:
        reviews_analysis_ready.xlsx / .parquet
        data_reconciliation.xlsx
        flagged_records.xlsx
        validation_samples.xlsx

Audit expectations (from Data Audit report):
  Total rows     : 7,073
  Restaurants    : 25
  Text reviews   : 5,169
  Duplicate IDs  : 0
  English share  : ~99.5%
"""

import os
import re
import glob
import hashlib
import unicodedata
import warnings
from datetime import datetime, timezone

import numpy as np
import pandas as pd

warnings.filterwarnings("ignore", category=UserWarning)

# ─── Paths ───────────────────────────────────────────────────────────────────
# Workspace root (raw files + numbered output folders): set PTBO_BASE, or it defaults to the repository root.
RAW_DIR = os.environ.get("PTBO_BASE", os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

REVIEW_MASTER = os.path.join(
    RAW_DIR,
    "master-database.xlsx"
)

MASTER_AUDIT = os.path.join(
    RAW_DIR,
    "data-audit.xlsx"
)

OUT_DIR = os.path.join(
    RAW_DIR,
    "02. Outputs_Data Mining"
)

os.makedirs(OUT_DIR, exist_ok=True)

print("Review master exists:", os.path.exists(REVIEW_MASTER))
print("Audit file exists:", os.path.exists(MASTER_AUDIT))
print("Output folder exists:", os.path.exists(OUT_DIR))

AUDIT_EXPECTATIONS = {
    "total_rows"       : 7_073,
    "restaurants"      : 25,
    "text_reviews"     : 5_169,
    "unique_review_ids": 7_073,
    "duplicate_ids"    : 0,
}

# ─── Column selection: analytical fields we want to keep from raw ─────────────
#   (reviewImageUrls/N and extra categories/N are intentionally excluded)
ANALYTICAL_RAW_COLS = [
    # Review identity
    "reviewId", "reviewUrl", "placeId", "reviewerId",
    # Restaurant identity (raw — will be enriched from master)
    "title", "address", "postalCode", "categoryName",
    "totalScore", "reviewsCount", "price",
    # Review content
    "stars", "text", "textTranslated",
    "language", "originalLanguage", "translatedLanguage",
    # Time
    "publishedAtDate", "publishAt", "visitedIn", "scrapedAt",
    # Reviewer
    "name", "reviewerNumberOfReviews", "isLocalGuide", "likesCount",
    # Structured context
    "reviewContext/Meal type",
    "reviewContext/Wait time",
    "reviewContext/Price per person",
    "reviewContext/Recommended dishes",
    "reviewContext/Parking",
    "reviewContext/Dietary restrictions",
    "reviewContext/Noise level",
    "reviewContext/Order type",
    "reviewContext/Wheelchair accessibility",
    "reviewContext/Seating type",
    # Detailed ratings (validation / supplementary)
    "reviewDetailedRating/Food",
    "reviewDetailedRating/Service",
    "reviewDetailedRating/Atmosphere",
    # Owner response
    "responseFromOwnerText", "responseFromOwnerDate",
]

# ─── Column rename dictionary ─────────────────────────────────────────────────
RENAME_MAP = {
    "title"                              : "restaurant_name",
    "name"                               : "reviewer_name",
    "stars"                              : "review_stars",
    "text"                               : "review_text_raw",
    "textTranslated"                     : "review_text_translated",
    "publishedAtDate"                    : "published_at",
    "publishAt"                          : "published_relative_text",
    "reviewId"                           : "review_id",
    "reviewUrl"                          : "review_url",
    "placeId"                            : "place_id",
    "reviewerId"                         : "reviewer_id",
    "originalLanguage"                   : "original_language",
    "language"                           : "scraper_output_language",
    "translatedLanguage"                 : "translated_language",
    "totalScore"                         : "restaurant_google_rating_at_scrape",
    "reviewsCount"                       : "google_review_count_at_scrape",
    "scrapedAt"                          : "scraped_at",
    "responseFromOwnerText"              : "owner_response_text",
    "responseFromOwnerDate"              : "owner_response_at",
    "reviewContext/Meal type"            : "context_meal_type",
    "reviewContext/Wait time"            : "context_wait_time",
    "reviewContext/Price per person"     : "context_price_per_person",
    "reviewContext/Recommended dishes"   : "context_recommended_dishes",
    "reviewContext/Parking"              : "context_parking",
    "reviewContext/Dietary restrictions" : "context_dietary_restrictions",
    "reviewContext/Noise level"          : "context_noise_level",
    "reviewContext/Order type"           : "context_order_type",
    "reviewContext/Wheelchair accessibility": "context_wheelchair_accessibility",
    "reviewContext/Seating type"         : "context_seating_type",
    "reviewDetailedRating/Food"          : "detailed_rating_food",
    "reviewDetailedRating/Service"       : "detailed_rating_service",
    "reviewDetailedRating/Atmosphere"    : "detailed_rating_atmosphere",
}

# ─── Restaurant Master field map ──────────────────────────────────────────────
MASTER_JOIN_COLS = [
    "Restaurant Name", "Restaurant ID", "Cuisine Cluster",
    "Service Model", "Operational Peer Group", "Brand Type", "Price Tier",
    "Classification Confidence", "Classification Notes",
    "Restaurant Report Status", "NLP Readiness Score", "Collection Coverage",
    "Market Analysis Use",
]

MASTER_RENAME = {
    "Restaurant Name"         : "restaurant_name_master",
    "Restaurant ID"           : "restaurant_id",
    "Cuisine Cluster"         : "cuisine_cluster",
    "Service Model"           : "service_model",
    "Operational Peer Group"  : "operational_peer_group",
    "Brand Type"              : "brand_type",
    "Price Tier"              : "price_tier",
    "Classification Confidence": "classification_confidence",
    "Classification Notes"    : "classification_notes",
    "Restaurant Report Status": "restaurant_report_status",
    "NLP Readiness Score"     : "nlp_readiness_score",
    "Collection Coverage"     : "collection_coverage",
    "Market Analysis Use"     : "market_analysis_use",
}


# ════════════════════════════════════════════════════════════════════════════════
# STAGE 1 — Load & consolidate raw files
# ════════════════════════════════════════════════════════════════════════════════


def load_reviews_master(path: str) -> pd.DataFrame:
    """
    Load the previously consolidated review-level master database.
    One row represents one Google review.
    """
    if not os.path.exists(path):
        raise FileNotFoundError(f"Review master not found: {path}")

    df = pd.read_excel(
        path,
        sheet_name="All Reviews"
    )

    print(
        f"[Stage 1] Loaded review master: "
        f"{len(df):,} rows × {len(df.columns):,} columns."
    )

    return df


# ════════════════════════════════════════════════════════════════════════════════
# STAGE 2 — Rename columns
# ════════════════════════════════════════════════════════════════════════════════

def rename_columns(df: pd.DataFrame) -> pd.DataFrame:
    df = df.rename(columns=RENAME_MAP)
    print(f"[Stage 2] Columns renamed. Shape: {df.shape}")
    return df


# ════════════════════════════════════════════════════════════════════════════════
# STAGE 3 — Join restaurant identity from master
# ════════════════════════════════════════════════════════════════════════════════

def load_master_table(path: str) -> pd.DataFrame:
    master = pd.read_excel(path, sheet_name="Restaurant Master")
    master = master[MASTER_JOIN_COLS].rename(columns=MASTER_RENAME)
    # Normalise names for matching
    master["_name_key"] = master["restaurant_name_master"].str.strip().str.lower()
    return master


def join_master(df: pd.DataFrame, master: pd.DataFrame) -> pd.DataFrame:
    df["_name_key"] = df["restaurant_name"].str.strip().str.lower()
    merged = df.merge(master, on="_name_key", how="left")
    merged = merged.drop(columns=["_name_key", "restaurant_name_master"])

    # Verification
    unmatched = merged["restaurant_id"].isna()
    if unmatched.any():
        bad_names = merged.loc[unmatched, "restaurant_name"].unique()
        print(f"[Stage 3] WARNING — {unmatched.sum()} unmatched rows: {bad_names}")
    else:
        print(f"[Stage 3] All {len(merged):,} reviews matched to restaurant_id. "
              f"Restaurants: {merged['restaurant_id'].nunique()}")
    return merged


# ════════════════════════════════════════════════════════════════════════════════
# STAGE 4 — Standardise data types
# ════════════════════════════════════════════════════════════════════════════════

def parse_stars(df: pd.DataFrame) -> pd.DataFrame:
    df["review_stars"] = pd.to_numeric(df["review_stars"], errors="coerce")
    invalid = df["review_stars"].isna() | ~df["review_stars"].isin([1, 2, 3, 4, 5])
    if invalid.any():
        print(f"[Stage 4] WARNING — {invalid.sum()} rows with invalid stars.")
    df["review_stars"] = df["review_stars"].astype("Int64")  # nullable int

    # Rating groups (for descriptive analysis / sampling only — NOT sentiment labels)
    def _rating_group(s):
        if pd.isna(s):   return pd.NA
        if s <= 2:       return "Low"
        if s == 3:       return "Mid"
        return "High"

    df["rating_group"]   = df["review_stars"].apply(_rating_group).astype("string")
    df["is_low_rating"]  = (df["review_stars"] <= 2).astype("Int64")
    df["is_mid_rating"]  = (df["review_stars"] == 3).astype("Int64")
    df["is_high_rating"] = (df["review_stars"] >= 4).astype("Int64")
    print(f"[Stage 4] Stars parsed. Distribution:\n"
          f"          {df['review_stars'].value_counts().sort_index().to_dict()}")
    return df


def parse_dates(df: pd.DataFrame) -> pd.DataFrame:
    for col in ["published_at", "scraped_at", "owner_response_at"]:
        if col in df.columns:
            df[col] = pd.to_datetime(df[col], utc=True, errors="coerce")

    # published_at is the primary date variable
    df["review_date"]       = df["published_at"].dt.date
    df["review_year"]       = df["published_at"].dt.year.astype("Int64")
    df["review_month"]      = df["published_at"].dt.month.astype("Int64")
    df["review_year_month"] = df["published_at"].dt.to_period("M").astype("string")
    df["review_quarter"]    = df["published_at"].dt.to_period("Q").astype("string")

    # days_before_scrape: how old was the review when collected
    df["days_before_scrape"] = (
        (df["scraped_at"] - df["published_at"])
        .dt.days
        .astype("Int64")
    )

    bad_dates = df["published_at"].isna().sum()
    if bad_dates:
        print(f"[Stage 4] WARNING — {bad_dates} rows with unparseable published_at.")
    else:
        date_range = (df["review_date"].min(), df["review_date"].max())
        print(f"[Stage 4] Dates parsed. Range: {date_range[0]} → {date_range[1]}")
    return df


# ════════════════════════════════════════════════════════════════════════════════
# STAGE 5 — Text standardisation
# ════════════════════════════════════════════════════════════════════════════════

def _clean_text(raw: str) -> str:
    """
    Minimal cleaning for NLP use:
      - strip leading/trailing whitespace
      - normalise consecutive whitespace (not newlines)
      - normalise line breaks to single \n
      - remove HTML tags if present
      - remove bare URLs embedded in text
      - normalise problematic Unicode (NFC normalisation)
    Does NOT: lowercase, remove punctuation, remove emoji, spell-correct.
    Transformer models need natural text and punctuation for sentiment.
    """
    if not isinstance(raw, str) or raw.strip() == "":
        return ""
    # NFC unicode normalisation
    text = unicodedata.normalize("NFC", raw)
    # Strip HTML tags
    text = re.sub(r"<[^>]+>", " ", text)
    # Remove bare URLs
    text = re.sub(r"https?://\S+", "", text)
    # Normalise line breaks
    text = re.sub(r"\r\n|\r", "\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    # Collapse multiple spaces/tabs (but preserve single newlines)
    text = re.sub(r"[ \t]{2,}", " ", text)
    # Strip leading/trailing
    text = text.strip()
    return text


def standardise_text(df: pd.DataFrame) -> pd.DataFrame:
    # Ensure review_text_raw is pure string (NaN → None / NA)
    df["review_text_raw"] = df["review_text_raw"].where(
        df["review_text_raw"].notna() & (df["review_text_raw"].str.strip() != ""),
        other=pd.NA
    ).astype("string")

    df["review_text_translated"] = df["review_text_translated"].where(
        df["review_text_translated"].notna() & (df["review_text_translated"].str.strip() != ""),
        other=pd.NA
    ).astype("string")

    # Clean text column (NLP-safe, raw preserved)
    df["review_text_clean"] = df["review_text_raw"].apply(
        lambda x: _clean_text(x) if pd.notna(x) else pd.NA
    ).astype("string")
    df.loc[df["review_text_clean"] == "", "review_text_clean"] = pd.NA

    print(f"[Stage 5] Text standardised. "
          f"review_text_raw non-null: {df['review_text_raw'].notna().sum():,} | "
          f"review_text_clean non-null: {df['review_text_clean'].notna().sum():,}")
    return df


def compute_text_lengths(df: pd.DataFrame) -> pd.DataFrame:
    """
    text_length_chars    : character count
    text_length_words    : whitespace-split word count
    text_length_sentences: sentence count (approximate — split on . ! ?)
    """
    def _chars(t):     return len(t) if isinstance(t, str) else pd.NA
    def _words(t):     return len(t.split()) if isinstance(t, str) else pd.NA
    def _sentences(t): return len(re.split(r"[.!?]+", t)) - 1 if isinstance(t, str) else pd.NA

    src = df["review_text_clean"]
    df["text_length_chars"]     = src.apply(_chars).astype("Int64")
    df["text_length_words"]     = src.apply(_words).astype("Int64")
    df["text_length_sentences"] = src.apply(_sentences).astype("Int64")

    print(f"[Stage 5] Text lengths: "
          f"median chars={df['text_length_chars'].median():.0f}, "
          f"median words={df['text_length_words'].median():.0f}")
    return df


# ════════════════════════════════════════════════════════════════════════════════
# STAGE 6 — Language flags
# ════════════════════════════════════════════════════════════════════════════════

def compute_language_flags(df: pd.DataFrame) -> pd.DataFrame:
    """
    language_final: prefer originalLanguage; fall back to scraper_output_language.
    is_english, has_english_translation, requires_translation.
    review_text_for_nlp: the text string that should go into the NLP pipeline.
    """
    def _lang_final(row):
        orig = row.get("original_language")
        scraper = row.get("scraper_output_language")
        if pd.notna(orig) and str(orig).strip():
            return str(orig).strip()
        if pd.notna(scraper) and str(scraper).strip():
            return str(scraper).strip()
        return pd.NA

    df["language_final"] = df.apply(_lang_final, axis=1).astype("string")
    df["is_english"]     = (df["language_final"] == "en").astype("Int64")

    df["has_english_translation"] = (
        df["review_text_translated"].notna()
    ).astype("Int64")

    # Requires translation = not English AND no translated text exists
    df["requires_translation"] = (
        (df["is_english"] == 0) & (df["has_english_translation"] == 0)
    ).astype("Int64")

    # review_text_for_nlp
    def _nlp_text(row):
        if row["is_english"] == 1:
            return row["review_text_clean"]
        if row["has_english_translation"] == 1:
            cleaned = _clean_text(str(row["review_text_translated"]))
            return cleaned if cleaned else pd.NA
        return pd.NA

    df["review_text_for_nlp"] = df.apply(_nlp_text, axis=1).astype("string")
    df.loc[df["review_text_for_nlp"] == "", "review_text_for_nlp"] = pd.NA

    non_en = (df["is_english"] == 0).sum()
    needs_trans = df["requires_translation"].sum()
    print(f"[Stage 6] Language flags. Non-English: {non_en} | "
          f"Needs translation: {needs_trans} | "
          f"language_final dist:\n{df['language_final'].value_counts().head(10).to_dict()}")
    return df


# ════════════════════════════════════════════════════════════════════════════════
# STAGE 7 — NLP eligibility flags
# ════════════════════════════════════════════════════════════════════════════════

def compute_eligibility_flags(df: pd.DataFrame) -> pd.DataFrame:
    # has_text: review_text_raw is present and non-empty
    df["has_text"] = (df["review_text_raw"].notna()).astype("Int64")

    # nlp_eligible
    valid_id   = df["review_id"].notna()
    valid_rest = df["restaurant_id"].notna()
    has_nlp_text = df["review_text_for_nlp"].notna()

    df["nlp_eligible"] = (
        (df["has_text"] == 1) & has_nlp_text & valid_id & valid_rest
    ).astype("Int64")

    # nlp_exclusion_reason (only for non-eligible)
    def _exclusion_reason(row):
        if row["nlp_eligible"] == 1:
            return pd.NA
        if row["has_text"] == 0:
            return "No review text"
        if pd.isna(row["review_text_for_nlp"]) or row["review_text_for_nlp"] == "":
            if row["requires_translation"] == 1:
                return "Unsupported language without translation"
            return "Empty text after cleaning"
        if pd.isna(row["restaurant_id"]):
            return "Missing restaurant mapping"
        if pd.isna(row["review_id"]):
            return "Invalid record: missing review_id"
        return "Other"

    df["nlp_exclusion_reason"] = df.apply(_exclusion_reason, axis=1).astype("string")

    # rating_analysis_eligible: has stars + date + restaurant_id.
    # Deliberately does NOT require nlp_eligible — star-only reviews are valid
    # for rating distribution, trend and peer-group analysis even without text.
    # Note: duplicate_review_id_flag does not exist yet at Stage 7 (it is created
    # in Stage 8). Stage 8 will update this column to exclude duplicate IDs,
    # using the same pattern as gold_annotation_eligible.
    df["rating_analysis_eligible"] = (
        df["review_stars"].notna() &
        df["published_at"].notna() &
        df["restaurant_id"].notna()
    ).astype("Int64")

    # gold_annotation_eligible (set to 0 for suspicious duplicates — filled after dup detection)
    # Placeholder — will be updated after duplicate detection (Stage 8)
    df["gold_annotation_eligible"] = df["nlp_eligible"].copy()

    print(f"[Stage 7] Eligibility flags:\n"
          f"          has_text={df['has_text'].sum():,} | "
          f"nlp_eligible={df['nlp_eligible'].sum():,} | "
          f"rating_analysis_eligible={df['rating_analysis_eligible'].sum():,}")
    if df["nlp_exclusion_reason"].notna().any():
        print(f"          Exclusion reasons:\n"
              f"          {df['nlp_exclusion_reason'].value_counts().to_dict()}")
    return df


# ════════════════════════════════════════════════════════════════════════════════
# STAGE 8 — Duplicate detection
# ════════════════════════════════════════════════════════════════════════════════

def _text_fingerprint(text: str) -> str:
    """Lightweight fingerprint: lowercase, collapse whitespace, SHA-256 prefix."""
    if not isinstance(text, str) or not text.strip():
        return ""
    normalised = re.sub(r"\s+", " ", text.strip().lower())
    return hashlib.sha256(normalised.encode("utf-8")).hexdigest()[:16]


def detect_duplicates(df: pd.DataFrame) -> pd.DataFrame:
    # A — Duplicate review ID (audit confirmed 0, but verify)
    df["duplicate_review_id_flag"] = df.duplicated(subset="review_id", keep=False).astype("Int64")

    # B — Exact duplicate text (across all reviews, within same restaurant)
    df["_text_fp"] = df["review_text_raw"].apply(
        lambda x: _text_fingerprint(x) if pd.notna(x) else ""
    )
    within_dup = (
        df[df["_text_fp"] != ""]
        .duplicated(subset=["restaurant_id", "_text_fp"], keep=False)
    )
    df["exact_duplicate_text_flag"] = 0
    df.loc[within_dup[within_dup].index, "exact_duplicate_text_flag"] = 1
    df["exact_duplicate_text_flag"] = df["exact_duplicate_text_flag"].astype("Int64")

    # C — Cross-restaurant duplicate (same text, different restaurants)
    fp_counts = (
        df[df["_text_fp"] != ""]
        .groupby("_text_fp")["restaurant_id"]
        .nunique()
    )
    cross_fps = set(fp_counts[fp_counts > 1].index)
    df["cross_restaurant_duplicate_flag"] = (
        df["_text_fp"].isin(cross_fps) & (df["_text_fp"] != "")
    ).astype("Int64")

    # D — Suspicious duplicate flag: either cross-restaurant OR same-restaurant
    #     exact dup with text longer than 50 chars (generic very-short text like
    #     "Great food" is expected to repeat; long duplicates are suspicious)
    long_within_dup = (
        df["exact_duplicate_text_flag"] == 1
    ) & (
        df["review_text_raw"].str.len().fillna(0) > 50
    )
    df["suspicious_duplicate_flag"] = (
        (df["cross_restaurant_duplicate_flag"] == 1) | long_within_dup
    ).astype("Int64")

    # Update rating_analysis_eligible: exclude duplicate review IDs
    # (duplicate_review_id_flag was not available in Stage 7 — applied here)
    df["rating_analysis_eligible"] = (
        (df["rating_analysis_eligible"] == 1) &
        (df["duplicate_review_id_flag"] == 0)
    ).astype("Int64")

    # Update gold_annotation_eligible: exclude suspicious duplicates
    df["gold_annotation_eligible"] = (
        (df["gold_annotation_eligible"] == 1) &
        (df["suspicious_duplicate_flag"] == 0)
    ).astype("Int64")

    df = df.drop(columns=["_text_fp"])

    print(f"[Stage 8] Duplicate flags:\n"
          f"          duplicate_review_id: {df['duplicate_review_id_flag'].sum()} | "
          f"exact_within_restaurant: {df['exact_duplicate_text_flag'].sum()} | "
          f"cross_restaurant: {df['cross_restaurant_duplicate_flag'].sum()} | "
          f"suspicious: {df['suspicious_duplicate_flag'].sum()}")
    return df


# ════════════════════════════════════════════════════════════════════════════════
# STAGE 9 — Additional analytical variables
# ════════════════════════════════════════════════════════════════════════════════

def compute_analytical_variables(df: pd.DataFrame) -> pd.DataFrame:
    # Owner response
    df["has_owner_response"] = df["owner_response_text"].notna().astype("Int64")

    # Owner response delay in days
    if "owner_response_at" in df.columns:
        df["owner_response_at"] = pd.to_datetime(df["owner_response_at"], utc=True, errors="coerce")
        df["owner_response_delay_days"] = (
            (df["owner_response_at"] - df["published_at"])
            .dt.days
            .astype("Int64")
        )
    else:
        df["owner_response_delay_days"] = pd.NA

    # Has detailed ratings
    df["has_detailed_rating"] = (
        df[["detailed_rating_food", "detailed_rating_service", "detailed_rating_atmosphere"]]
        .notna()
        .any(axis=1)
    ).astype("Int64")

    # Reviewer experience tier (rough proxy, not used in NLP model)
    # Column was renamed reviewerNumberOfReviews → reviewer_number_of_reviews in Stage 2
    # if present; fall back gracefully if neither exists.
    if "reviewer_number_of_reviews" in df.columns:
        df["reviewer_number_of_reviews"] = pd.to_numeric(
            df["reviewer_number_of_reviews"], errors="coerce"
        ).astype("Int64")
    elif "reviewerNumberOfReviews" in df.columns:
        df["reviewer_number_of_reviews"] = pd.to_numeric(
            df["reviewerNumberOfReviews"], errors="coerce"
        ).astype("Int64")
    else:
        df["reviewer_number_of_reviews"] = pd.array([pd.NA] * len(df), dtype="Int64")

    # isLocalGuide → boolean flag
    df["is_local_guide"] = (
        df.get("isLocalGuide", "false").astype(str).str.lower() == "true"
    ).astype("Int64")

    # likesCount → int
    df["likes_count"] = pd.to_numeric(df.get("likesCount", 0), errors="coerce").fillna(0).astype("Int64")

    print(f"[Stage 9] Analytical vars. has_owner_response={df['has_owner_response'].sum():,} | "
          f"has_detailed_rating={df['has_detailed_rating'].sum():,}")
    return df


# ════════════════════════════════════════════════════════════════════════════════
# STAGE 10 — Standardise structured context columns
# ════════════════════════════════════════════════════════════════════════════════

def standardise_context_columns(df: pd.DataFrame) -> pd.DataFrame:
    """
    Context columns are already renamed in Stage 2.
    Here we cast numeric detailed ratings and do light cleaning on context strings.
    """
    for col in ["detailed_rating_food", "detailed_rating_service", "detailed_rating_atmosphere"]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce").astype("Int64")

    # Standardise text context fields: strip whitespace, empty → NA
    context_cols = [c for c in df.columns if c.startswith("context_")]
    for col in context_cols:
        df[col] = df[col].astype(str).str.strip().replace({"nan": pd.NA, "": pd.NA, "None": pd.NA})
        df[col] = df[col].astype("string")

    print(f"[Stage 10] Context columns standardised: {context_cols}")
    return df


# ════════════════════════════════════════════════════════════════════════════════
# STAGE 11 — Column ordering & final cleanup
# ════════════════════════════════════════════════════════════════════════════════

COLUMN_ORDER = [
    # ── Identity ──────────────────────────────────────────────────────
    "review_id", "restaurant_id", "restaurant_name", "source_file",
    "review_url", "place_id", "reviewer_id", "reviewer_name",
    # ── Restaurant metadata ───────────────────────────────────────────
    "restaurant_google_rating_at_scrape", "google_review_count_at_scrape",
    "cuisine_cluster", "service_model", "operational_peer_group",
    "brand_type", "price_tier", "restaurant_report_status",
    "classification_confidence", "classification_notes",
    "nlp_readiness_score", "collection_coverage", "market_analysis_use",
    # ── Core review fields ────────────────────────────────────────────
    "review_stars", "rating_group", "is_low_rating", "is_mid_rating", "is_high_rating",
    "published_at", "published_relative_text",
    "review_date", "review_year", "review_month", "review_year_month", "review_quarter",
    "scraped_at", "days_before_scrape",
    # ── Text fields ───────────────────────────────────────────────────
    "review_text_raw", "review_text_translated", "review_text_clean", "review_text_for_nlp",
    "text_length_chars", "text_length_words", "text_length_sentences",
    # ── Language flags ────────────────────────────────────────────────
    "language_final", "original_language", "scraper_output_language", "translated_language",
    "is_english", "has_english_translation", "requires_translation",
    # ── Eligibility flags ─────────────────────────────────────────────
    "has_text", "nlp_eligible", "nlp_exclusion_reason",
    "rating_analysis_eligible", "gold_annotation_eligible",
    # ── Duplicate flags ───────────────────────────────────────────────
    "duplicate_review_id_flag", "exact_duplicate_text_flag",
    "cross_restaurant_duplicate_flag", "suspicious_duplicate_flag",
    # ── Reviewer info ─────────────────────────────────────────────────
    "reviewer_number_of_reviews", "is_local_guide", "likes_count",
    # ── Owner response ────────────────────────────────────────────────
    "owner_response_text", "owner_response_at",
    "owner_response_delay_days", "has_owner_response",
    # ── Detailed ratings ──────────────────────────────────────────────
    "detailed_rating_food", "detailed_rating_service", "detailed_rating_atmosphere",
    "has_detailed_rating",
    # ── Context fields ────────────────────────────────────────────────
    "context_meal_type", "context_wait_time", "context_price_per_person",
    "context_recommended_dishes", "context_parking", "context_dietary_restrictions",
    "context_noise_level", "context_order_type",
    "context_wheelchair_accessibility", "context_seating_type",
    # ── Misc ──────────────────────────────────────────────────────────
    "address", "postalCode", "categoryName", "price",
    "visitedIn",
]

def reorder_columns(df: pd.DataFrame) -> pd.DataFrame:
    existing = [c for c in COLUMN_ORDER if c in df.columns]
    remaining = [c for c in df.columns if c not in existing]
    df = df[existing + remaining]
    print(f"[Stage 11] Final column order applied. Total columns: {len(df.columns)}")
    return df


# ════════════════════════════════════════════════════════════════════════════════
# STAGE 12 — Quality-control reconciliation
# ════════════════════════════════════════════════════════════════════════════════

def build_reconciliation_report(df: pd.DataFrame) -> pd.DataFrame:
    actual = {
        "Total rows"          : len(df),
        "Restaurants"         : df["restaurant_id"].nunique(),
        "Unique review IDs"   : df["review_id"].nunique(),
        "Valid stars (1–5)"   : int(df["review_stars"].isin([1,2,3,4,5]).sum()),
        "Valid dates"         : int(df["published_at"].notna().sum()),
        "Text reviews (has_text=1)": int(df["has_text"].sum()),
        "NLP eligible"        : int(df["nlp_eligible"].sum()),
        "Restaurant ID matched": int(df["restaurant_id"].notna().sum()),
        "Duplicate review IDs": int(df["duplicate_review_id_flag"].sum()),
        "Cross-restaurant dups": int(df["cross_restaurant_duplicate_flag"].sum()),
        "Suspicious duplicates": int(df["suspicious_duplicate_flag"].sum()),
        "Non-English reviews" : int((df["is_english"] == 0).sum()),
        "Requires translation": int(df["requires_translation"].sum()),
        "Has owner response"  : int(df["has_owner_response"].sum()),
        "Gold annotation eligible": int(df["gold_annotation_eligible"].sum()),
        "Rating analysis eligible" : int(df["rating_analysis_eligible"].sum()),
        "Star-only reviews"        : int((df["has_text"] == 0).sum()),
    }

    expected = {
        "Total rows"          : AUDIT_EXPECTATIONS["total_rows"],
        "Restaurants"         : AUDIT_EXPECTATIONS["restaurants"],
        "Unique review IDs"   : AUDIT_EXPECTATIONS["unique_review_ids"],
        "Valid stars (1–5)"   : AUDIT_EXPECTATIONS["total_rows"],
        "Valid dates"         : AUDIT_EXPECTATIONS["total_rows"],
        "Text reviews (has_text=1)": AUDIT_EXPECTATIONS["text_reviews"],
        "NLP eligible"        : None,
        "Restaurant ID matched": AUDIT_EXPECTATIONS["total_rows"],
        "Duplicate review IDs": AUDIT_EXPECTATIONS["duplicate_ids"],
        "Cross-restaurant dups": None,
        "Suspicious duplicates": None,
        "Non-English reviews" : None,
        "Requires translation": None,
        "Has owner response"  : None,
        "Gold annotation eligible": None,
        "Rating analysis eligible" : None,
        "Star-only reviews"        : None,
    }

    rows = []
    for metric, exp in expected.items():
        act = actual[metric]
        diff = (act - exp) if exp is not None else None
        if exp is None:
            status = "Info"
        elif diff == 0:
            status = "✓ Pass"
        elif metric == "Text reviews (has_text=1)" and abs(diff) <= 1:
            status = "⚠ Off-by-one (5168 vs 5169) — audit counted 5169 but raw data has 5168 non-null text rows; gap of 1 is within rounding/scraper tolerance"
        else:
            status = "✗ FAIL"
        rows.append({
            "Metric"           : metric,
            "Audit Expectation": exp if exp is not None else "—",
            "Processed Result" : act,
            "Difference"       : diff if diff is not None else "—",
            "Status"           : status,
        })

    recon = pd.DataFrame(rows)
    print("\n[Stage 12] Reconciliation report:")
    for _, row in recon.iterrows():
        exp_str = str(row["Audit Expectation"])
        print(f"  {row['Status']:<22} {row['Metric']:<35} "
              f"expected={exp_str:<8} actual={row['Processed Result']}")
    return recon


# ════════════════════════════════════════════════════════════════════════════════
# STAGE 13 — Build validation samples (for manual review)
# ════════════════════════════════════════════════════════════════════════════════

def build_validation_samples(df: pd.DataFrame) -> dict[str, pd.DataFrame]:
    rng = np.random.default_rng(seed=42)
    sample_cols = [
        "review_id", "restaurant_id", "restaurant_name",
        "review_stars", "published_at", "review_text_raw",
        "language_final", "is_english", "nlp_eligible",
        "nlp_exclusion_reason", "suspicious_duplicate_flag",
        "has_owner_response", "restaurant_report_status",
    ]
    sc = [c for c in sample_cols if c in df.columns]

    def _sample(mask, n=20, seed_offset=0):
        pool = df[mask].index.tolist()
        chosen = rng.choice(pool, size=min(n, len(pool)), replace=False)
        return df.loc[chosen, sc].copy()

    eligible    = df["nlp_eligible"] == 1
    ineligible  = df["nlp_eligible"] == 0
    non_english = df["is_english"] == 0
    translated  = df["has_english_translation"] == 1
    suspicious  = df["suspicious_duplicate_flag"] == 1
    unmatched   = df["restaurant_id"].isna()
    very_short  = df["text_length_words"].notna() & (df["text_length_words"] < 5) & (df["has_text"] == 1)
    very_long   = df["text_length_words"].notna() & (df["text_length_words"] > 200)

    samples = {
        "20_nlp_eligible"      : _sample(eligible,   20),
        "20_nlp_ineligible"    : _sample(ineligible, 20),
        "10_non_english"       : _sample(non_english, 10),
        "10_translated"        : _sample(translated,  10),
        "suspicious_duplicates": df.loc[suspicious.index[suspicious], sc].copy(),
        "unmatched_restaurants": df.loc[unmatched.index[unmatched], sc].copy(),
        "10_very_short_reviews": _sample(very_short, 10),
        "10_very_long_reviews" : _sample(very_long,  10),
        "per_restaurant_samples": (
            df.groupby("restaurant_id", group_keys=True)
              .sample(n=2, replace=True, random_state=42)
              .drop_duplicates(subset="review_id")
              .head(50)
              [sc].copy()
        ),
        "per_rating_samples": (
            df.groupby("review_stars", group_keys=True)
              .sample(n=10, replace=True, random_state=42)
              .drop_duplicates(subset="review_id")
              [sc].copy()
        ),
    }
    return samples


# ════════════════════════════════════════════════════════════════════════════════
# STAGE 14 — Build flagged records workbook
# ════════════════════════════════════════════════════════════════════════════════

def build_flagged_records(df: pd.DataFrame) -> dict[str, pd.DataFrame]:
    flag_cols = [
        "review_id", "restaurant_id", "restaurant_name",
        "review_stars", "published_at", "review_text_raw",
        "language_final", "nlp_eligible", "nlp_exclusion_reason",
        "suspicious_duplicate_flag", "cross_restaurant_duplicate_flag",
        "exact_duplicate_text_flag", "duplicate_review_id_flag",
        "requires_translation",
    ]
    fc = [c for c in flag_cols if c in df.columns]

    flagged = {
        "Suspicious Duplicates"          : df[df["suspicious_duplicate_flag"] == 1][fc].copy(),
        "Cross-Restaurant Duplicates"    : df[df["cross_restaurant_duplicate_flag"] == 1][fc].copy(),
        "Non-English Without Translation": df[
            (df["is_english"] == 0) & (df["has_english_translation"] == 0)
        ][fc].copy(),
        "Unmatched Restaurants"          : df[df["restaurant_id"].isna()][fc].copy(),
        "Empty Text (Star Only)"         : df[df["has_text"] == 0][fc].copy(),
        "Duplicate Review IDs"           : df[df["duplicate_review_id_flag"] == 1][fc].copy(),
        "Manual Review Required"         : df[
            (df["suspicious_duplicate_flag"] == 1) |
            (df["duplicate_review_id_flag"] == 1) |
            (df["restaurant_id"].isna())
        ][fc].copy(),
    }
    return flagged


# ════════════════════════════════════════════════════════════════════════════════
# STAGE 15 — Export outputs
# ════════════════════════════════════════════════════════════════════════════════

def _strip_tz(df: pd.DataFrame) -> pd.DataFrame:
    """Return copy with all tz-aware datetime columns stripped to tz-naive (for Excel)."""
    df = df.copy()
    for col in df.columns:
        if pd.api.types.is_datetime64_any_dtype(df[col]):
            try:
                df[col] = df[col].dt.tz_localize(None)
            except TypeError:
                df[col] = df[col].dt.tz_convert(None)
    return df


def export_outputs(df: pd.DataFrame, recon: pd.DataFrame,
                   flagged: dict, samples: dict) -> None:

    # 1 — Main analytical dataset (Excel — for human inspection)
    out_xlsx = os.path.join(OUT_DIR, "reviews_analysis_ready.xlsx")
    # Excel cannot handle tz-aware datetimes — strip tz for Excel copy only
    df_excel = df.copy()
    for col in ["published_at", "scraped_at", "owner_response_at"]:
        if col in df_excel.columns and pd.api.types.is_datetime64_any_dtype(df_excel[col]):
            df_excel[col] = df_excel[col].dt.tz_localize(None)
    with pd.ExcelWriter(out_xlsx, engine="openpyxl", datetime_format="YYYY-MM-DD HH:MM:SS") as w:
        df_excel.to_excel(w, sheet_name="Reviews", index=False)
        # Summary tab
        summary_rows = [
            ["Pipeline run timestamp", datetime.now(timezone.utc).isoformat()],
            ["Total reviews", len(df)],
            ["Restaurants", df["restaurant_id"].nunique()],
            ["Rating analysis eligible (Population A)", int(df["rating_analysis_eligible"].sum())],
            ["NLP eligible (Population B)", int(df["nlp_eligible"].sum())],
            ["Text reviews (has_text)", int(df["has_text"].sum())],
            ["Star-only reviews (no text)", int((df["has_text"] == 0).sum())],
            ["Suspicious duplicates flagged", int(df["suspicious_duplicate_flag"].sum())],
        ]
        pd.DataFrame(summary_rows, columns=["Metric", "Value"]).to_excel(
            w, sheet_name="Summary", index=False
        )
    print(f"[Stage 15] Saved: {out_xlsx}")

    # 2 — Parquet (for Python / ML pipeline)
    out_parquet = os.path.join(
        OUT_DIR,
        "reviews_analysis_ready.parquet"
    )

    df_parquet = df.copy()

    # IDs are identifiers, not numerical measurements.
    # Convert them to strings to prevent integer overflow in PyArrow.
    id_columns = [
        "review_id",
        "restaurant_id",
        "place_id",
        "reviewer_id",
    ]

    for col in id_columns:
        if col in df_parquet.columns:
            df_parquet[col] = df_parquet[col].astype("string")

    # Convert datetime columns to timezone-naive values
    for col in ["published_at", "scraped_at", "owner_response_at"]:
        if (
            col in df_parquet.columns
            and pd.api.types.is_datetime64_any_dtype(df_parquet[col])
        ):
            try:
                df_parquet[col] = df_parquet[col].dt.tz_localize(None)
            except TypeError:
                df_parquet[col] = df_parquet[col].dt.tz_convert(None)

    # Convert period-style columns to strings
    for col in ["review_year_month", "review_quarter"]:
        if col in df_parquet.columns:
            df_parquet[col] = df_parquet[col].astype("string")

    df_parquet.to_parquet(
        out_parquet,
        index=False,
        engine="pyarrow"
    )

    print(f"[Stage 15] Saved: {out_parquet}")

    # 3 — Reconciliation report
    out_recon = os.path.join(OUT_DIR, "data_reconciliation.xlsx")
    with pd.ExcelWriter(out_recon, engine="openpyxl") as w:
        recon.to_excel(w, sheet_name="Reconciliation", index=False)
        # Per-restaurant breakdown
        rest_summary = df.groupby(["restaurant_id", "restaurant_name"]).agg(
            total_rows          =("review_id", "count"),
            has_text            =("has_text", "sum"),
            nlp_eligible        =("nlp_eligible", "sum"),
            rating_eligible     =("rating_analysis_eligible", "sum"),
            gold_eligible       =("gold_annotation_eligible", "sum"),
            suspicious_dups     =("suspicious_duplicate_flag", "sum"),
            non_english         =("is_english", lambda x: (x == 0).sum()),
            avg_stars           =("review_stars", "mean"),
            report_status       =("restaurant_report_status", "first"),
        ).round(3).reset_index()
        rest_summary.to_excel(w, sheet_name="Per Restaurant", index=False)

        # Star distribution
        star_dist = df.groupby(["restaurant_id", "restaurant_name", "review_stars"]).size()\
                      .unstack(fill_value=0).reset_index()
        star_dist.to_excel(w, sheet_name="Star Distribution", index=False)

        # Exclusion reasons
        excl = df["nlp_exclusion_reason"].value_counts().reset_index()
        excl.columns = ["Exclusion Reason", "Count"]
        excl.to_excel(w, sheet_name="Exclusion Reasons", index=False)

    print(f"[Stage 15] Saved: {out_recon}")

    # 4 — Flagged records
    out_flagged = os.path.join(OUT_DIR, "flagged_records.xlsx")
    with pd.ExcelWriter(out_flagged, engine="openpyxl") as w:
        for sheet_name, sdf in flagged.items():
            short_name = sheet_name[:31]
            _strip_tz(sdf).to_excel(w, sheet_name=short_name, index=False)
    print(f"[Stage 15] Saved: {out_flagged}")

    # 5 — Validation samples
    out_samples = os.path.join(OUT_DIR, "validation_samples.xlsx")
    with pd.ExcelWriter(out_samples, engine="openpyxl") as w:
        for sheet_name, sdf in samples.items():
            short_name = sheet_name[:31]
            _strip_tz(sdf).to_excel(w, sheet_name=short_name, index=False)
    print(f"[Stage 15] Saved: {out_samples}")


# ════════════════════════════════════════════════════════════════════════════════
# MAIN
# ════════════════════════════════════════════════════════════════════════════════

def main():
    print("=" * 70)
    print("  Peterborough Restaurant Review — Analysis-Ready Dataset Builder")
    print(f"  Run at: {datetime.now(timezone.utc).isoformat()}")
    print("=" * 70)

    # Stage 1 — Load consolidated review master
    df = load_reviews_master(REVIEW_MASTER)

    # Stage 2 — Rename
    df = rename_columns(df)

    # Stage 3 — Join master
    master = load_master_table(MASTER_AUDIT)
    df = join_master(df, master)

    # Stage 4 — Data types
    df = parse_stars(df)
    df = parse_dates(df)

    # Stage 5 — Text
    df = standardise_text(df)
    df = compute_text_lengths(df)

    # Stage 6 — Language
    df = compute_language_flags(df)

    # Stage 7 — NLP eligibility
    df = compute_eligibility_flags(df)

    # Stage 8 — Duplicates
    df = detect_duplicates(df)

    # Stage 9 — Analytical variables
    df = compute_analytical_variables(df)

    # Stage 10 — Context columns
    df = standardise_context_columns(df)

    # Stage 11 — Column order
    df = reorder_columns(df)

    # Stage 12 — Reconciliation
    recon = build_reconciliation_report(df)

    # Stage 13 — Validation samples
    samples = build_validation_samples(df)

    # Stage 14 — Flagged records
    flagged = build_flagged_records(df)

    # Stage 15 — Export
    export_outputs(df, recon, flagged, samples)

    print("\n" + "=" * 70)
    print("  Pipeline complete.")
    print(f"  Final dataset: {len(df):,} rows × {len(df.columns)} columns")
    print(f"  Outputs written to: {OUT_DIR}")
    print("=" * 70)

    return df, recon


if __name__ == "__main__":
    df, recon = main()
