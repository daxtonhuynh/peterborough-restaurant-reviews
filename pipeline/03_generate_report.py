"""
03_generate_report.py
=====================
Peterborough Restaurant Google Reviews — EDA Report Generator

Reads all PNG charts from the EDA output folder and compiles them
into a structured Word document (.docx) with:
  - Cover page
  - Table of contents (manual, no field codes)
  - One section per EDA step (5A → 5G)
  - Each chart on its own page with caption and plain-English interpretation
  - Key findings summary at the end
  - Data limitations note

Usage:
    python 03_generate_report.py

Output:
    03. Outputs_EDA/EDA_Report.docx
"""

import os
import glob
from datetime import datetime

from docx import Document
from docx.shared import Inches, Pt, RGBColor, Cm
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.section import WD_ORIENT
from docx.oxml.ns import qn
from docx.oxml import OxmlElement

# ─── Paths ────────────────────────────────────────────────────────────────────
# Workspace root (raw files + numbered output folders): set PTBO_BASE, or it defaults to the repository root.
PROJECT_DIR = os.environ.get("PTBO_BASE", os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
CHART_DIR   = os.path.join(PROJECT_DIR, "03. Outputs_EDA", "Charts")
OUT_DIR     = os.path.join(PROJECT_DIR, "03. Outputs_EDA")
REPORT_PATH = os.path.join(OUT_DIR, "EDA_Report.docx")

# ─── Colours (RGB) ────────────────────────────────────────────────────────────
NAVY   = RGBColor(0x04, 0x2C, 0x53)   # deep blue — headings
TEAL   = RGBColor(0x0F, 0x6E, 0x56)   # teal — section accents
GRAY   = RGBColor(0x5F, 0x5E, 0x5A)   # body text muted
WHITE  = RGBColor(0xFF, 0xFF, 0xFF)
CORAL  = RGBColor(0x99, 0x3C, 0x1D)   # warning / limitation notes

# ─── Chart metadata ──────────────────────────────────────────────────────────
# Each entry: (filename_stem, short_caption, interpretation_paragraph)
CHARTS = {
    "5A": {
        "title"  : "5A — Population and Data Coverage",
        "summary": (
            "This section establishes what the dataset contains and what it "
            "does not. Before reading any rating or trend, stakeholders should "
            "understand the size, composition and concentration of the observed sample."
        ),
        "charts" : [
            (
                "5A1_population_funnel",
                "Figure 5A.1 — Review population funnel",
                "Starting from 7,073 total records, the funnel shows how many reviews "
                "qualify for each type of analysis. The rating population (Population A) "
                "includes all reviews with valid stars, date and restaurant ID — including "
                "star-only reviews with no written text. The NLP population (Population B) "
                "requires written text and a supported language. These two populations are "
                "kept separate throughout the analysis to avoid mixing rating and text signals."
            ),
            (
                "5A2_volume_per_restaurant",
                "Figure 5A.2 — Review volume per restaurant",
                "Review volume varies substantially across the 25 restaurants. Restaurants "
                "shown in red fall below the minimum threshold of 30 reviews, which means "
                "their individual rankings and trend estimates should be interpreted with "
                "caution. Restaurants with very low counts are retained in market-level "
                "analysis but are flagged wherever individual comparisons are made."
            ),
            (
                "5A3_review_concentration",
                "Figure 5A.3 — Cumulative review concentration",
                "The top 5 restaurants account for approximately 47% of all reviews in "
                "the dataset. This level of concentration means that review-weighted "
                "market averages are more influenced by high-volume restaurants than by "
                "the typical restaurant in the sample. Restaurant-weighted metrics are "
                "used alongside review-weighted metrics throughout this report to control "
                "for this effect."
            ),
            (
                "5A4_field_coverage",
                "Figure 5A.4 — Field coverage for key analytical columns",
                "Core fields (stars, dates, restaurant ID) have near-complete coverage. "
                "Structured context fields such as wait time, noise level and parking have "
                "coverage below the 15% reporting threshold and are excluded from "
                "market-level conclusions. Detailed ratings for food, service and atmosphere "
                "have 88–91% coverage and are included in Section 5G analysis."
            ),
        ]
    },
    "5B": {
        "title"  : "5B — Market-Level Rating Analysis",
        "summary": (
            "This section describes the overall rating landscape of the observed sample. "
            "All metrics are computed on the rating population (Population A) and reported "
            "using both review-weighted and restaurant-weighted methods."
        ),
        "charts" : [
            (
                "5B1_star_distribution",
                "Figure 5B.1 — Star distribution and rating proxy breakdown",
                "The star distribution is heavily skewed toward 5-star reviews, which is "
                "typical of Google Reviews where satisfied customers are more likely to "
                "leave feedback. Approximately 87.7% of reviews are positive (4–5 stars), "
                "2.7% are neutral (3 stars), and 9.5% are negative (1–2 stars). These "
                "proportions are used as a star-based rating proxy throughout this report. "
                "They are not model-based sentiment labels — mixed-sentiment reviews are "
                "not captured at this stage."
            ),
            (
                "5B2_rw_vs_restw",
                "Figure 5B.2 — Review-weighted vs restaurant-weighted mean rating",
                "The review-weighted mean (4.526★) is slightly higher than the "
                "restaurant-weighted mean (4.495★), a difference of 0.031 stars. This "
                "small gap indicates that the market is not heavily distorted by a few "
                "high-volume, high-rating outliers. The 95% confidence intervals are "
                "narrow for the review-weighted estimate (large n) but wider for the "
                "restaurant-weighted estimate (only 25 data points). Both metrics should "
                "be reported together when describing 'market performance'."
            ),
            (
                "5B3_restaurant_ranking",
                "Figure 5B.3 — Restaurant ranking by mean rating with market benchmarks",
                "Restaurants are ranked by all-time mean star rating. The two dashed "
                "vertical lines show the review-weighted and restaurant-weighted market "
                "averages. Restaurants marked with ⚠ have fewer than 30 reviews — their "
                "position in this ranking may shift significantly with additional data. "
                "Rankings alone do not account for recent trends or rating stability, "
                "which are explored in Section 5D."
            ),
            (
                "5B4_positive_negative_share",
                "Figure 5B.4 — Positive and negative rating share per restaurant",
                "This chart shows the share of positive (4–5★) and negative (1–2★) "
                "reviews per restaurant, sorted by positive share. A restaurant with a "
                "high positive share but also a visible negative bar warrants attention — "
                "it may have polarised customer experiences. The negative share is "
                "particularly actionable because even a small proportion of 1–2 star "
                "reviews can disproportionately affect perceived reputation."
            ),
        ]
    },
    "5C": {
        "title"  : "5C — Temporal Analysis",
        "summary": (
            "This section examines how review volume and rating have changed over time. "
            "Review volume trends and rating trends are kept separate because volume "
            "growth does not necessarily indicate quality improvement. A composition-effect "
            "check compares review-weighted and restaurant-weighted trends to detect "
            "whether market-level changes are driven by genuine rating shifts or by "
            "changing restaurant mix."
        ),
        "charts" : [
            (
                "5C1_monthly_volume",
                "Figure 5C.1 — Monthly review volume",
                "Monthly review volume shows the pace at which the observed sample was "
                "generated. Months with very low volume (fewer than 10 reviews) produce "
                "unreliable rating averages and are excluded from trend charts. Spikes in "
                "volume may reflect seasonal patterns, promotional activity or changes in "
                "scraper collection timing rather than underlying business changes."
            ),
            (
                "5C2_rating_trend_rw_vs_restw",
                "Figure 5C.2 — Rating trend: review-weighted vs restaurant-weighted",
                "The solid lines show 3-month rolling averages for both weighting methods. "
                "When the two lines diverge, a composition effect is present — meaning "
                "the aggregate trend is partly driven by a shift in which restaurants "
                "are generating reviews, not only by changes in customer satisfaction. "
                "Periods where both lines decline together are stronger signals of a "
                "genuine market-wide rating decrease."
            ),
            (
                "5C3_year_over_year",
                "Figure 5C.3 — Year-over-year mean rating with 95% confidence intervals",
                "Annual averages provide a stable summary of rating performance across "
                "years. Error bars show 95% confidence intervals — wider bars indicate "
                "fewer reviews in that year and therefore less certainty. Year-over-year "
                "comparisons should account for the fact that the dataset covers only "
                "January 2024 to June 2026, meaning 2024 and 2026 may be partial years "
                "in terms of seasonal coverage."
            ),
            (
                "5C4_seasonality",
                "Figure 5C.4 — Rating and review volume by month of year",
                "Seasonality analysis examines whether certain months consistently produce "
                "higher or lower ratings and review volumes across all years in the dataset. "
                "Peterborough's seasonal patterns may be influenced by university term "
                "periods, summer tourism, and winter quieter periods. Months with very "
                "low review counts should be interpreted cautiously as the rating average "
                "is less stable."
            ),
        ]
    },
    "5D": {
        "title"  : "5D — Restaurant Benchmarking",
        "summary": (
            "This section benchmarks each restaurant against the market average, examines "
            "recent performance relative to historical performance, and assesses rating "
            "stability over time. All benchmarks use the rating population (Population A). "
            "Restaurants below the 30-review threshold are included but flagged."
        ),
        "charts" : [
            (
                "5D1_rating_vs_volume_scatter",
                "Figure 5D.1 — Rating vs review volume: restaurant positioning map",
                "Each dot represents one restaurant. The horizontal axis shows volume "
                "(evidence strength) and the vertical axis shows mean rating (performance). "
                "The market average line and median volume line divide the chart into four "
                "quadrants: strong performers (high volume, high rating), promising but "
                "low-evidence restaurants (low volume, high rating), priority improvement "
                "cases (low rating regardless of volume), and mid-field restaurants. "
                "Triangles indicate low-sample restaurants whose position may be unstable."
            ),
            (
                "5D2_recent_vs_historical",
                "Figure 5D.2 — Recent vs historical rating change per restaurant",
                "This chart compares each restaurant's mean rating in the last 12 months "
                "against its prior historical mean. Green bars indicate improving "
                "restaurants; red bars indicate declining ones. Restaurants with fewer "
                "than 5 reviews in either period are excluded from this comparison. A "
                "restaurant showing a large decline deserves investigation — the cause "
                "may be operational changes, new competition, or a single high-impact "
                "negative review period."
            ),
            (
                "5D3_rating_volatility",
                "Figure 5D.3 — Rating stability (volatility) per restaurant",
                "Volatility is measured as the standard deviation of monthly mean ratings. "
                "A higher value means the restaurant's rating fluctuates more from month "
                "to month, which can indicate inconsistent customer experience, seasonal "
                "effects, or low review volume making individual months noisy. A low "
                "volatility score combined with a high mean rating is the strongest "
                "signal of consistently positive performance."
            ),
        ]
    },
    "5E": {
        "title"  : "5E — Peer-Group Benchmarking",
        "summary": (
            "Restaurants are grouped into five operational peer groups based on service "
            "model and dining format. Peer-group comparison controls for the fact that "
            "fast casual restaurants and premium full-service restaurants face different "
            "customer expectations and therefore different natural rating baselines."
        ),
        "charts" : [
            (
                "5E1_peer_group_comparison",
                "Figure 5E.1 — Peer-group mean rating: review-weighted vs restaurant-weighted",
                "Each peer group is shown with both weighting methods and 95% confidence "
                "intervals. A large gap between the review-weighted and restaurant-weighted "
                "bar for a given group indicates that one high-volume restaurant is pulling "
                "the group average away from the typical restaurant in that group. Peer "
                "groups with fewer than 3 restaurants are flagged with ⚠ as their averages "
                "are more sensitive to individual outliers."
            ),
            (
                "5E2_peer_positive_negative",
                "Figure 5E.2 — Positive and negative rating share by peer group",
                "This chart shows the proportion of positive (4–5★) and negative (1–2★) "
                "reviews within each peer group. Differences in negative share across "
                "groups can indicate structural differences in customer expectations — "
                "for example, customers visiting premium full-service restaurants may "
                "hold higher standards and be more likely to leave a critical review "
                "when expectations are not met."
            ),
            (
                "5E3_peer_group_boxplot",
                "Figure 5E.3 — Rating distribution within each peer group",
                "Boxplots show the full distribution of individual review ratings within "
                "each peer group. The median line, interquartile range, and whiskers "
                "reveal within-group spread that average metrics conceal. A peer group "
                "with a high median but wide spread contains both strong and weak "
                "individual restaurants, suggesting the group average is less meaningful "
                "as a benchmark target."
            ),
        ]
    },
    "5F": {
        "title"  : "5F — Review and Engagement Behaviour",
        "summary": (
            "This section examines how reviewers write and how restaurants engage with "
            "reviews. Text behaviour is analysed on the NLP population (Population B) — "
            "reviews with written content. Owner response analysis uses the rating "
            "population (Population A). These are observational associations only."
        ),
        "charts" : [
            (
                "5F1_text_availability_by_star",
                "Figure 5F.1 — Text availability by star rating",
                "Not all reviewers write text — many leave only a star rating. The "
                "proportion of reviews with written text varies by star level. If negative "
                "reviewers are significantly more likely to write text than positive ones, "
                "the NLP population will over-represent complaints relative to the full "
                "rating population. This difference must be acknowledged when interpreting "
                "topic modelling and sentiment results in later pipeline stages."
            ),
            (
                "5F2_review_length_by_star",
                "Figure 5F.2 — Review length distribution by star rating (NLP population)",
                "Negative reviews (1–2★) tend to be longer than positive ones, as "
                "dissatisfied customers more often explain their experience in detail. "
                "This creates a length-based bias in the NLP corpus: topic models trained "
                "on this data will encounter more words per negative review, potentially "
                "surfacing complaint topics more prominently than their frequency alone "
                "would suggest. Review-length variables are included as controls in the "
                "rating regression model."
            ),
            (
                "5F3_owner_response_by_star",
                "Figure 5F.3 — Owner response rate by star rating",
                "Owners respond to 50.6% of negative reviews (1–2★) compared to 38.2% "
                "of positive reviews (4–5★). This indicates that restaurants are "
                "prioritising responses to critical feedback, which is a positive "
                "reputation management signal. However, this is an association — the "
                "data does not show whether responding to negative reviews improves "
                "subsequent ratings."
            ),
            (
                "5F4_owner_response_per_restaurant",
                "Figure 5F.4 — Owner response rate per restaurant",
                "Response rates vary widely across restaurants. Some restaurants respond "
                "to nearly all reviews while others respond to very few. A low response "
                "rate is not necessarily negative — it may reflect business size, "
                "staffing, or platform engagement strategy. However, restaurants with "
                "high negative-review rates and low response rates may be missing an "
                "opportunity for visible reputation recovery."
            ),
            (
                "5F5_local_guide_comparison",
                "Figure 5F.5 — Local Guide vs non-Local Guide mean rating",
                "Google Local Guides are a self-selected group of active reviewers who "
                "have opted into Google's programme. Their ratings may differ from "
                "general reviewers due to higher review frequency and potentially "
                "different evaluation standards. This chart shows whether Local Guide "
                "ratings systematically differ — any difference should be noted as a "
                "potential reviewer-composition effect in the dataset."
            ),
        ]
    },
    "5G": {
        "title"  : "5G — Structured Context Exploration",
        "summary": (
            "Google reviewers can optionally provide structured context such as meal "
            "type, order type, price per person and detailed sub-ratings for food, "
            "service and atmosphere. Only fields with at least 15% coverage are analysed. "
            "Fields below that threshold (wait time at 7%, noise level at 13.5%, "
            "parking at 1.8%) are excluded from market-level conclusions."
        ),
        "charts" : [
            (
                "5G_context_meal_type",
                "Figure 5G.1 — Mean rating by meal type (50.1% coverage)",
                "Reviewers who specify meal type provide a useful segmentation. Differences "
                "in mean rating across meal types (breakfast, lunch, dinner) may reflect "
                "different menus, staffing levels, or customer expectations at different "
                "times of day. However, because meal type is self-reported and optional, "
                "the covered subset may not be representative of all visits."
            ),
            (
                "5G_context_order_type",
                "Figure 5G.2 — Mean rating by order type (45.7% coverage)",
                "Dine-in, takeout and delivery customers may have fundamentally different "
                "experience drivers. Delivery ratings in particular are affected by "
                "third-party logistics outside the restaurant's control. Differences "
                "between order types indicate where operational focus may have the "
                "greatest impact on ratings."
            ),
            (
                "5G_context_price_per_person",
                "Figure 5G.3 — Mean rating by price per person (58.7% coverage)",
                "Perceived value-for-money is one of the strongest drivers of restaurant "
                "ratings. This chart shows how ratings vary across self-reported spend "
                "bands. A restaurant in a higher price band with a lower rating than "
                "lower-priced competitors may be failing to meet elevated value expectations."
            ),
            (
                "5G_detailed_rating_food",
                "Figure 5G.4 — Food detailed rating vs overall star (91.2% coverage, r=0.93)",
                "The food sub-rating correlates very strongly with the overall star rating "
                "(r = 0.93), indicating that food quality is the dominant driver of "
                "overall satisfaction in this dataset. This is consistent with restaurant "
                "research literature and provides early validation for the ABSA pipeline, "
                "which should surface food-quality aspects as highly rating-predictive."
            ),
            (
                "5G_detailed_rating_service",
                "Figure 5G.5 — Service detailed rating vs overall star (90.3% coverage, r=0.87)",
                "Service quality is the second-strongest correlate of overall rating "
                "(r = 0.87). While slightly weaker than food, service complaints are "
                "often more actionable in the short term — staffing, training and "
                "wait-time communication can be addressed without menu changes."
            ),
            (
                "5G_detailed_rating_atmosphere",
                "Figure 5G.6 — Atmosphere detailed rating vs overall star (88.6% coverage, r=0.83)",
                "Atmosphere is the weakest correlate of the three sub-ratings (r = 0.83), "
                "though still strongly associated with overall rating. Atmosphere is "
                "generally less controllable in the short term (it involves physical "
                "space, noise and decor) but may be a differentiator in peer-group "
                "comparisons where food and service are broadly similar."
            ),
        ]
    },
}

# ─── Helpers ─────────────────────────────────────────────────────────────────

def set_heading_style(para, text, level=1, colour=NAVY):
    """Add a styled heading paragraph."""
    para.clear()
    run = para.add_run(text)
    run.bold = True
    run.font.color.rgb = colour
    if level == 1:
        run.font.size = Pt(18)
        para.paragraph_format.space_before = Pt(18)
        para.paragraph_format.space_after  = Pt(6)
    elif level == 2:
        run.font.size = Pt(14)
        para.paragraph_format.space_before = Pt(14)
        para.paragraph_format.space_after  = Pt(4)
    else:
        run.font.size = Pt(11)
        run.font.color.rgb = TEAL
        para.paragraph_format.space_before = Pt(8)
        para.paragraph_format.space_after  = Pt(2)
    para.alignment = WD_ALIGN_PARAGRAPH.LEFT


def add_body(doc, text, colour=GRAY, size=Pt(10), space_after=Pt(8)):
    para = doc.add_paragraph()
    run  = para.add_run(text)
    run.font.size  = size
    run.font.color.rgb = colour
    para.paragraph_format.space_after = space_after
    return para


def add_caption(doc, text):
    para = doc.add_paragraph()
    run  = para.add_run(text)
    run.bold = True
    run.font.size = Pt(9)
    run.font.color.rgb = TEAL
    run.font.italic = True
    para.paragraph_format.space_before = Pt(4)
    para.paragraph_format.space_after  = Pt(4)
    para.alignment = WD_ALIGN_PARAGRAPH.CENTER


def add_note(doc, text):
    """Italic limitation/note paragraph."""
    para = doc.add_paragraph()
    run  = para.add_run("Note: " + text)
    run.italic = True
    run.font.size = Pt(9)
    run.font.color.rgb = CORAL
    para.paragraph_format.space_after = Pt(6)


def add_divider(doc):
    """Thin horizontal rule using paragraph bottom border."""
    para = doc.add_paragraph()
    pPr  = para._p.get_or_add_pPr()
    pBdr = OxmlElement("w:pBdr")
    bottom = OxmlElement("w:bottom")
    bottom.set(qn("w:val"),   "single")
    bottom.set(qn("w:sz"),    "4")
    bottom.set(qn("w:space"), "1")
    bottom.set(qn("w:color"), "B4B2A9")
    pBdr.append(bottom)
    pPr.append(pBdr)
    para.paragraph_format.space_after = Pt(6)


def page_break(doc):
    doc.add_page_break()


def add_chart(doc, chart_dir, section_key, stem,
              caption, interpretation, width_inches=5.8):
    """Insert chart image, caption, and interpretation paragraph."""
    path = os.path.join(chart_dir, section_key, f"{stem}.png")
    if not os.path.exists(path):
        add_body(doc, f"[Chart not found: {path}]", colour=CORAL)
        return

    # Centre the image
    img_para = doc.add_paragraph()
    img_para.alignment = WD_ALIGN_PARAGRAPH.CENTER
    img_para.paragraph_format.space_before = Pt(6)
    img_para.add_run().add_picture(path, width=Inches(width_inches))

    add_caption(doc, caption)

    add_body(doc, interpretation)


# ─── Build document ───────────────────────────────────────────────────────────

def build_report():
    doc = Document()

    # ── Page setup: A4, normal margins ───────────────────────────────────────
    section = doc.sections[0]
    section.page_width  = Cm(21)
    section.page_height = Cm(29.7)
    section.left_margin   = Cm(2.5)
    section.right_margin  = Cm(2.5)
    section.top_margin    = Cm(2.5)
    section.bottom_margin = Cm(2.0)

    # ── Cover page ────────────────────────────────────────────────────────────
    doc.add_paragraph()
    doc.add_paragraph()

    title_para = doc.add_paragraph()
    title_para.alignment = WD_ALIGN_PARAGRAPH.CENTER
    title_run = title_para.add_run(
        "Peterborough Restaurant Google Reviews"
    )
    title_run.bold = True
    title_run.font.size = Pt(24)
    title_run.font.color.rgb = NAVY

    sub_para = doc.add_paragraph()
    sub_para.alignment = WD_ALIGN_PARAGRAPH.CENTER
    sub_run = sub_para.add_run("Market Exploratory Analysis — EDA Report")
    sub_run.font.size = Pt(16)
    sub_run.font.color.rgb = TEAL

    doc.add_paragraph()
    add_divider(doc)
    doc.add_paragraph()

    meta_lines = [
        ("Dataset"   , "25 restaurants · 7,073 reviews · Jan 2024 – Jun 2026"),
        ("Analysis"  , "Phase 3 / Step 5 — Exploratory Data Analysis"),
        ("Generated" , datetime.now().strftime("%d %B %Y")),
        ("Status"    , "Observational · Not for causal inference"),
    ]
    for label, value in meta_lines:
        p = doc.add_paragraph()
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        r1 = p.add_run(f"{label}: ")
        r1.bold = True
        r1.font.size = Pt(11)
        r1.font.color.rgb = GRAY
        r2 = p.add_run(value)
        r2.font.size = Pt(11)
        r2.font.color.rgb = GRAY

    doc.add_paragraph()
    doc.add_paragraph()

    scope_para = doc.add_paragraph()
    scope_para.alignment = WD_ALIGN_PARAGRAPH.CENTER
    scope_run = scope_para.add_run(
        "This report reflects the observed sample of Google Reviews collected for "
        "25 Peterborough restaurants. It is not a census of all customers or all "
        "reviews posted on Google Maps. All findings are associations derived from "
        "the available data and should not be interpreted as causal claims."
    )
    scope_run.italic = True
    scope_run.font.size = Pt(9)
    scope_run.font.color.rgb = GRAY

    page_break(doc)

    # ── Table of contents (manual) ────────────────────────────────────────────
    toc_heading = doc.add_paragraph()
    set_heading_style(toc_heading, "Contents", level=1, colour=NAVY)

    toc_entries = [
        ("5A", "Population and Data Coverage"),
        ("5B", "Market-Level Rating Analysis"),
        ("5C", "Temporal Analysis"),
        ("5D", "Restaurant Benchmarking"),
        ("5E", "Peer-Group Benchmarking"),
        ("5F", "Review and Engagement Behaviour"),
        ("5G", "Structured Context Exploration"),
        ("—",  "Key Findings Summary"),
        ("—",  "Data Limitations and Assumptions"),
    ]
    for code, label in toc_entries:
        p = doc.add_paragraph()
        p.paragraph_format.space_after = Pt(3)
        r1 = p.add_run(f"Section {code}  " if code != "—" else "        ")
        r1.font.size = Pt(10)
        r1.font.color.rgb = TEAL
        r1.bold = True
        r2 = p.add_run(label)
        r2.font.size = Pt(10)
        r2.font.color.rgb = GRAY

    page_break(doc)

    # ── Sections 5A → 5G ─────────────────────────────────────────────────────
    for section_key, section_data in CHARTS.items():
        # Section heading
        h1 = doc.add_paragraph()
        set_heading_style(h1, section_data["title"], level=1)

        # Section summary paragraph
        add_body(doc, section_data["summary"], size=Pt(10))
        add_divider(doc)

        # Each chart
        for i, (stem, caption, interpretation) in enumerate(section_data["charts"]):
            add_chart(doc, CHART_DIR, section_key,
                      stem, caption, interpretation)
            # Separator between charts within a section (not after last)
            if i < len(section_data["charts"]) - 1:
                doc.add_paragraph().paragraph_format.space_after = Pt(4)

        page_break(doc)

    # ── Key Findings Summary ──────────────────────────────────────────────────
    h_findings = doc.add_paragraph()
    set_heading_style(h_findings, "Key Findings Summary", level=1)
    add_divider(doc)

    findings = [
        ("Market rating", (
            "The review-weighted mean rating is 4.526★ and the restaurant-weighted "
            "mean is 4.495★. The small gap (0.031★) indicates the market is not "
            "dominated by a few outlier restaurants. The median review is 5 stars, "
            "confirming the characteristic positivity skew of Google Reviews."
        )),
        ("Recent trend", (
            "Ratings in the last 12 months (4.472★) are marginally lower than the "
            "historical average (4.574★), a decline of 0.102★. This requires monitoring "
            "but is not yet a strong signal of systemic deterioration — the composition "
            "effect (changing restaurant mix) may account for part of this change."
        )),
        ("Review concentration", (
            "The top 5 restaurants by volume account for 46.8% of all reviews. "
            "Review-weighted market averages are therefore more influenced by these "
            "high-volume restaurants than by the typical restaurant in the sample."
        )),
        ("Owner response", (
            "Restaurants respond to 50.6% of negative reviews (1–2★) but only 38.2% "
            "of positive reviews. The overall response rate is 39.2% with a median "
            "response delay of 1 day. Response rates vary substantially across restaurants."
        )),
        ("Text and NLP bias", (
            "Negative reviews are significantly longer than positive reviews. This "
            "creates a length-based bias in the NLP corpus: complaint topics will be "
            "represented by more words per review than praise topics, which must be "
            "controlled for in topic modelling and sentiment analysis."
        )),
        ("Structured context", (
            "Food detailed rating (r = 0.93 with overall star) is the strongest "
            "sub-dimension correlate, followed by service (r = 0.87) and atmosphere "
            "(r = 0.83). These correlations provide early validation for the ABSA "
            "pipeline and suggest food quality is the primary rating driver."
        )),
        ("Low-coverage context fields", (
            "Wait time (7.0%), noise level (13.5%), parking (1.8%) and dietary "
            "restrictions (2.6%) fall below the 15% reporting threshold. No "
            "market-level conclusions should be drawn from these fields."
        )),
    ]

    for finding_title, finding_text in findings:
        h3 = doc.add_paragraph()
        set_heading_style(h3, finding_title, level=3)
        add_body(doc, finding_text)

    page_break(doc)

    # ── Data Limitations ─────────────────────────────────────────────────────
    h_limits = doc.add_paragraph()
    set_heading_style(h_limits, "Data Limitations and Assumptions", level=1)
    add_divider(doc)

    limitations = [
        ("Observed sample, not census",
         "This dataset contains approximately 40.6% of the Google-listed reviews for "
         "these 25 restaurants. The sample is recent-biased and non-random. Conclusions "
         "cannot be generalised to all customers or all time periods."),
        ("Google Reviews platform bias",
         "Customers who leave Google Reviews are self-selected. Satisfied and dissatisfied "
         "customers are both more likely to review than neutral ones, contributing to "
         "the bimodal 1★ and 5★ distribution."),
        ("Star-based proxy is not sentiment",
         "Positive (4–5★), neutral (3★) and negative (1–2★) categories are rating-based "
         "proxies only. A 4★ review may contain negative sentiment about specific aspects. "
         "Aspect-level sentiment analysis (ABSA) in the next pipeline stage will provide "
         "more precise sentiment measurement."),
        ("Association, not causation",
         "All relationships in this report — between owner response and ratings, between "
         "review length and star level, between context variables and ratings — are "
         "observational associations. No causal claims are supported by this data alone."),
        ("Restaurants with low review counts",
         f"Restaurants with fewer than 30 reviews have wide confidence intervals and "
         "unstable trend estimates. Individual rankings for these restaurants should not "
         "be used for competitive benchmarking without additional data."),
        ("Structured context is self-reported and sparse",
         "Context fields are filled in voluntarily by reviewers and may not be "
         "representative of all visits. Coverage varies substantially by field and "
         "by restaurant."),
    ]

    for lim_title, lim_text in limitations:
        h3 = doc.add_paragraph()
        set_heading_style(h3, lim_title, level=3)
        add_note(doc, lim_text)

    # ── Save ─────────────────────────────────────────────────────────────────
    doc.save(REPORT_PATH)
    print(f"\nReport saved: {REPORT_PATH}")
    print(f"Sections: {len(CHARTS)} | Charts included: "
          f"{sum(len(s['charts']) for s in CHARTS.values())}")


if __name__ == "__main__":
    build_report()
