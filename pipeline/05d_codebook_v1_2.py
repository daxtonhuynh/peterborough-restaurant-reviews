# -*- coding: utf-8 -*-
"""
05d_codebook_v1_2.py  -  codebook v1.2 (5 Nov 2026)
Resolves the 10 codebook questions raised while pre-labelling the pilot (Q1-Q10).
Topic mapping is unchanged; only definitions, boundary rules and annotation guidelines change.

Input : 05. Outputs_BERTopic/topic_to_aspect_mapping_v.1.1.xlsx
Output: 05. Outputs_BERTopic/topic_to_aspect_mapping_v.1.2.xlsx
Also refreshes the 'Aspect quick reference' + 'Annotation guidelines' sheets in the two pilot files that
nobody has started yet (annotation_pilot_v3_sentence.xlsx, annotation_pilot_v3_annotator_B.xlsx) - but only
if they are still byte-identical in content to what 05b produced (no annotation filled in).
annotation_pilot_v3_prelabelled.xlsx is NEVER touched here (it is being reviewed by hand).
"""
import os
from pathlib import Path
import pandas as pd
from openpyxl import load_workbook
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter

BASE = Path(os.environ.get("PTBO_BASE", Path(__file__).resolve().parent.parent))
BT = BASE / "05. Outputs_BERTopic"
IN, OUT = BT / "topic_to_aspect_mapping_v.1.1.xlsx", BT / "topic_to_aspect_mapping_v.1.2.xlsx"
PILOTS = [BT / "annotation_pilot_v3_sentence.xlsx", BT / "annotation_pilot_v3_annotator_B.xlsx"]

DECISIONS = [
 # Q, question, decision, rationale, pilot rows, label change for the pre-labelled pilot
 ("Q1","Long wait the customer explicitly accepts ('Waited 72 minutes ..., worth every penny!')",
  "SPEED = Neutral when the customer explicitly accepts the wait ('not an issue', 'worth it'). The 'worth it' praise goes to the aspect it is about (FOOD or PRICE).",
  "Sentiment is the customer's stance, not the analyst's view of the duration. Wait durations stay recoverable from the evidence span.",
  "P018, P105, P134","P105 and P134: change SPEED Negative -> Neutral."),
 ("Q2","Stale or spoiled food with no illness ('sour and old smell')",
  "Flag only if the food is described as mouldy, rotten, expired or spoiled, or causes illness. Stale / 'not fresh' / 'old smell' / sour / reheated -> FRESH Negative only, no flag.",
  "Keeps the flag for genuine health-risk reports so the manual-review queue stays small and defensible.",
  "P160","None (P160 is already FRESH only)."),
 ("Q3","Unsafe food handling with no illness ('servers grabbing the chips with their bare hands')",
  "Flag = 1 (observed unsafe handling: bare hands, sweat, no handwashing) + CLEAN Negative.",
  "Matches the existing CLEAN example; observed handling breaches are food-safety concerns even without illness.",
  "P190","None (P190 is already flagged)."),
 ("Q4","Feeling rushed - SPEED or STAFF?",
  "STAFF Negative (service manner). SPEED is reserved for slowness and waiting.",
  "Being rushed is the opposite operational problem to slowness; mixing it into SPEED would make SPEED sentiment uninterpretable.",
  "P111","P111: change SPEED Negative -> Staff & service quality Negative."),
 ("Q5","Dish not as advertised ('not spicy as advertised') - ACC or FOOD?",
  "ACC when the dish differs from what the menu or staff said; FOOD when it is only a taste preference with no promise attached.",
  "'As advertised' is a fulfilment failure the restaurant can fix at the pass, not a recipe question.",
  "P104","None."),
 ("Q6","Restaurant name contains a dish word ('Tora sushi was amazing!')",
  "When the subject is the restaurant name -> OVR. FOOD only if the sentence clearly refers to the dish.",
  "Avoids inflating FOOD with overall judgements for Tora Sushi, Madoi Sushi, Osmow's Shawarma, etc.",
  "P044","None."),
 ("Q7","Pricing-policy disputes (lunch vs dinner price, regular vs lunch order)",
  "Policy perceived as unfair -> PRICE Negative. Charge that does not match what was ordered or agreed -> ACC Negative. Tag both if both happen.",
  "Separates price-level/policy issues (owner decision) from execution errors (front-of-house process).",
  "P062, P199","None."),
 ("Q8","Customer cannot reach the restaurant to complain (calls not answered, website)",
  "COMPL Negative.",
  "Being unreachable after a problem is a service-recovery failure.",
  "P001, P060, P128","None."),
 ("Q9","OTHER watch-list (kids, catering, retail store, 'supporting local')",
  "Keep in OTHER and write a short sub-theme in annotator_notes. Any sub-theme reaching ~2% of labels is reviewed for promotion to its own aspect.",
  "Avoids creating aspects from single sentences while keeping the evidence trail.",
  "P032, P138, P154, P185","Add the sub-theme word in annotator_notes when you verify these rows."),
 ("Q10","Merged sentences ('..') give more than 3 aspects",
  "Pilot: keep sentence units, label the 3 most specific aspects, list the rest in annotator_notes. From the main sample on, the annotation and modelling unit is the refined ABSA unit (04. Outputs_NLP/absa_units.parquet), which splits '..' / '…' line-break merges while keeping the parent sentence_id and BERTopic links.",
  "Fixing segmentation upstream would change sentence_ids and invalidate the BERTopic runs; a refinement layer keeps everything traceable.",
  "P040, P110, P184, P194","None."),
]

APPEND = {  # aspect_name -> {column: text appended}, plus change_log
 "Food & drink taste & quality": {"exclude -> where it goes instead": " Restaurant name containing a dish word ('Tora Sushi was amazing!') -> Overall (v1.2)."},
 "Freshness, temperature & cooking execution": {"exclude -> where it goes instead": " Stale / 'not fresh' / 'old smell' / sour / reheated -> FRESH only, NO food-safety flag (v1.2)."},
 "Price & value": {"include (cues)": "; pricing policy felt unfair - lunch/dinner cut-off, charged for extras (v1.2)."},
 "Staff & service quality": {"include (cues)": "; rushed us / pushed us to order or leave (v1.2)."},
 "Service speed, waiting & seating": {
   "exclude -> where it goes instead": " Being rushed -> Staff & service quality (v1.2). Wait explicitly accepted ('not an issue', 'worth it') -> SPEED Neutral (v1.2).",
   "ambiguous_example -> resolution": "  |  v1.2: 'I have waited 40 minutes for my food and it was worth every minute!' -> SPEED Neutral + FOOD Positive."},
 "Order & billing accuracy": {"include (cues)": "; dish not as described on the menu or by staff - 'not spicy as advertised' (v1.2).",
   "exclude -> where it goes instead": " Pricing policy felt unfair (lunch vs dinner price) -> Price & value; add ACC only if the charge doesn't match what was ordered/agreed (v1.2)."},
 "Complaint handling & service recovery": {"include (cues)": "; calls not answered / no response when trying to complain (v1.2)."},
 "Overall experience, recommendation & return intention": {"include (cues)": "; the restaurant name as subject even if it contains a dish word - 'Tora sushi was amazing!' (v1.2)."},
 "Reported food-safety concern (flag)": {
   "definition": " v1.2 - FLAG WHEN: illness after eating; foreign object, hair or insect; allergic reaction; raw/undercooked meat, poultry or seafood; food described as mouldy, rotten, expired or spoiled; observed unsafe handling (bare hands, sweat, no handwashing).",
   "exclude -> where it goes instead": " v1.2 - NOT flagged: stale, 'not fresh', 'old smell', sour, reheated (-> FRESH only); self-caused illness ('ate so much ... sorry for the vomit')."},
 "Other / business-specific": {"definition": " v1.2: write a short sub-theme in annotator_notes (kids, catering, retail, local business ...); sub-themes reaching ~2% of labels are reviewed for promotion."},
}
GUIDE_V12 = [
 ("3c. Accepted waits (v1.2)","If the customer explicitly accepts a wait ('not an issue', 'worth it') -> SPEED Neutral; put the 'worth it' praise on the aspect it is about (FOOD or PRICE). [Q1]"),
 ("8. Food-safety flag (v1.2 - replaces v1.1 rule 8)","food_safety_flag = 1 for: illness after eating; foreign object/hair/insect; allergic reaction; raw/undercooked meat, poultry or seafood; food described as mouldy, rotten, expired or spoiled; observed unsafe handling. Also give the regular aspect (hair -> CLEAN; raw chicken -> FRESH; bare hands -> CLEAN). Pure illness report with nothing else -> aspect_1 = 'Reported food-safety concern (flag)', no sentiment. [Q2, Q3]"),
 ("8a. NOT flagged (v1.2)","Stale, 'not fresh', 'old smell', sour, reheated -> FRESH Negative only. Self-caused illness (over-eating) -> no flag. A keyword alone is never enough. [Q2]"),
 ("14. Being rushed (v1.2)","Rushed / pushed to order or leave -> STAFF Negative. SPEED is only slowness and waiting. [Q4]"),
 ("15. Not as described (v1.2)","Dish differs from the menu or what staff said ('not spicy as advertised') -> ACC Negative. Pure taste preference -> FOOD. [Q5]"),
 ("16. Restaurant names (v1.2)","Subject is the restaurant name, even if it contains a dish word ('Tora sushi was amazing!') -> OVR. [Q6]"),
 ("17. Pricing policies (v1.2)","Policy felt unfair (lunch/dinner cut-off, extras) -> PRICE Negative; charge not matching the order/agreement -> ACC Negative; both if both. [Q7]"),
 ("18. Unreachable for complaints (v1.2)","Calls not answered / no response / no way to complain -> COMPL Negative. [Q8]"),
 ("19. OTHER sub-themes (v1.2)","When you use OTHER, write a one-word sub-theme in annotator_notes (kids, catering, retail, local ...). [Q9]"),
 ("20. Merged sentences (v1.2)","Pilot only: if a 'sentence' is really several sentences joined by '..', label the 3 most specific aspects and list the rest in annotator_notes. From the main sample on, units are pre-split (absa_units). [Q10]"),
]

HDR_FILL = PatternFill("solid", start_color="1F3A5F"); HDR_FONT = Font(bold=True, color="FFFFFF", name="Arial", size=10)
BODY = Font(name="Arial", size=10); thin = Side(style="thin", color="D0D0D0"); BORDER = Border(left=thin, right=thin, top=thin, bottom=thin)
V12_FILL = PatternFill("solid", start_color="E8F5E9")
def write_df(wb, name, df, widths, idx=None, freeze="B2"):
    if name in wb.sheetnames: idx = wb.sheetnames.index(name) if idx is None else idx; wb.remove(wb[name])
    ws = wb.create_sheet(name, idx)
    ws.append(list(df.columns))
    for r in df.itertuples(index=False): ws.append([None if pd.isna(v) else v for v in r])
    for c in ws[1]: c.fill = HDR_FILL; c.font = HDR_FONT; c.alignment = Alignment(wrap_text=True, vertical="center"); c.border = BORDER
    for row in ws.iter_rows(min_row=2):
        for c in row: c.font = BODY; c.alignment = Alignment(wrap_text=True, vertical="top"); c.border = BORDER
    for i, w in enumerate(widths, 1): ws.column_dimensions[get_column_letter(i)].width = w
    ws.freeze_panes = freeze; ws.auto_filter.ref = ws.dimensions
    return ws

# ---- taxonomy v1.2
tax = pd.read_excel(IN, sheet_name="Aspect Taxonomy v1.1").rename(columns={"change_from_v1_0": "change_log"})
for name, edits in APPEND.items():
    i = tax.index[tax.aspect_name == name]; assert len(i) == 1, name; i = i[0]
    for col, txt in edits.items():
        tax.at[i, col] = (str(tax.at[i, col]) if pd.notna(tax.at[i, col]) else "") + txt
    tax.at[i, "change_log"] = f"{tax.at[i, 'change_log']}  |  v1.2: " + "; ".join(edits.keys()) + " updated (see Decision log v1.2)."
gl = pd.read_excel(IN, sheet_name="Annotation guidelines")
gl = gl[~gl.rule.str.startswith("8. ")]
gl = pd.concat([gl, pd.DataFrame(GUIDE_V12, columns=["rule", "guideline"])], ignore_index=True)
order = lambda r: (int(''.join(ch for ch in r.split('.')[0] if ch.isdigit())), r)
gl = gl.iloc[sorted(range(len(gl)), key=lambda k: order(gl.rule.iloc[k]))].reset_index(drop=True)
dec = pd.DataFrame(DECISIONS, columns=["question","issue","decision_v1_2","rationale","pilot_rows","change_needed_in_prelabelled_pilot"])
quick = tax[["aspect_name","type","definition","exclude -> where it goes instead"]].rename(columns={"aspect_name":"aspect","exclude -> where it goes instead":"goes elsewhere"})

wb = load_workbook(IN)
write_df(wb, "Aspect Taxonomy v1.1", tax, [30,8,9,45,55,50,60,45,45,60,40]).title = "Aspect Taxonomy v1.2"
ws = wb["Aspect Taxonomy v1.2"]
for r in range(2, ws.max_row + 1):
    if "v1.2" in str(ws.cell(r, 4).value):
        for c in range(1, ws.max_column + 1): ws.cell(r, c).fill = V12_FILL
ws = write_df(wb, "Annotation guidelines", gl, [34,130], freeze="A2")
for r in range(2, ws.max_row + 1):
    if "(v1.2" in str(ws.cell(r, 1).value):
        for c in (1, 2): ws.cell(r, c).fill = V12_FILL
write_df(wb, "Decision log v1.2", dec, [8,40,60,50,18,40], idx=1)
rd = wb["README"]
rd.insert_rows(3, 3)
rd["A3"] = "VERSION 1.2 (5 Nov 2026): codebook questions Q1-Q10 resolved - see 'Decision log v1.2'. Changed rows are green in 'Aspect Taxonomy v1.2' and 'Annotation guidelines'. The topic mapping itself is unchanged from v1.1."
rd["A3"].font = Font(name="Arial", size=10, bold=True, color="2E7D32"); rd["A3"].alignment = Alignment(wrap_text=True)
rd["A1"] = "Topic-to-aspect mapping v1.2 - Peterborough restaurant reviews"
wb.save(OUT)

# ---- refresh guideline sheets in untouched pilot files
for f in PILOTS:
    pw = load_workbook(f)
    ann = pd.read_excel(f, sheet_name="Annotate")
    filled = ann[[c for c in ann.columns if c.startswith(("aspect_","sentiment_","evidence_")) or c in ("annotator_notes",)]].notna().values.sum()
    if filled:
        print(f"SKIP {f.name}: {filled} annotation cells already filled - not touched"); continue
    write_df(pw, "Aspect quick reference", quick, [34,9,70,80])
    write_df(pw, "Annotation guidelines", gl, [34,130], freeze="A2")
    pw.save(f); print("refreshed guidelines v1.2 in", f.name)
print("saved", OUT.name, "| guideline rules", len(gl), "| decisions", len(dec))
