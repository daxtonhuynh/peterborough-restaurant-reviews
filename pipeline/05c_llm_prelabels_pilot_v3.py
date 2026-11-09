# -*- coding: utf-8 -*-
"""
05c_llm_prelabels_pilot_v3.py
Builds annotation_pilot_v3_prelabelled.xlsx: the 200-sentence pilot pre-filled with LLM labels
(Claude Opus 5.5, codebook v1.1, 2026-11-05) for HUMAN VERIFICATION.

Inputs (05. Outputs_BERTopic/):
  annotation_pilot_v3_sentence.xlsx      blank pilot built by 05b (left untouched)
  llm_prelabels_v1_claude.txt            raw LLM labels, one line per sample:
      sample_id|CODE~Sent~evidence ;; CODE~Sent~evidence|service_channel|food_safety_flag|ambiguity_flag|note
Output:
  annotation_pilot_v3_prelabelled.xlsx

Rules (methodology Step 10): LLM output is a suggestion. A row counts as gold ONLY when verified = 1.
The untouched LLM output is kept in 'LLM labels (original)' so LLM-vs-human agreement can be measured.
Annotator B's file is NOT pre-labelled (keeps the kappa check independent).
"""
import os
from pathlib import Path
from collections import Counter
from openpyxl import load_workbook
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.formatting.rule import FormulaRule
from openpyxl.worksheet.datavalidation import DataValidation

BASE = Path(os.environ.get("PTBO_BASE", Path(__file__).resolve().parent.parent))
BT = BASE / "05. Outputs_BERTopic"
SRC, LBL, OUT = BT / "annotation_pilot_v3_sentence.xlsx", BT / "llm_prelabels_v1_claude.txt", BT / "annotation_pilot_v3_prelabelled.xlsx"

CODE2NAME = {"FOOD":"Food & drink taste & quality","FRESH":"Freshness, temperature & cooking execution","PORT":"Portion size",
 "MENU":"Menu variety & options","PRICE":"Price & value","STAFF":"Staff & service quality","SPEED":"Service speed, waiting & seating",
 "ACC":"Order & billing accuracy","AMB":"Ambience & noise","CLEAN":"Cleanliness & hygiene","LOC":"Location, parking & accessibility",
 "DELIV":"Takeout & delivery experience","DIET":"Dietary accommodation","COMPL":"Complaint handling & service recovery",
 "OVR":"Overall experience, recommendation & return intention","SAFETY":"Reported food-safety concern (flag)",
 "OTHER":"Other / business-specific","NA":"Not applicable / context only"}
SENT = {"Pos":"Positive","Neg":"Negative","Neu":"Neutral","Mix":"Mixed","":None}

# ---- parse + validate
labels = {}
for line in open(LBL, encoding="utf-8"):
    sid, asp, ch, fs, amb, note = line.rstrip("\n").split("|", 5)
    slots = [p.split("~", 2) for p in asp.split(" ;; ")]
    labels[sid] = dict(slots=slots, ch=ch, fs=int(fs), amb=int(amb), note=note)

wb = load_workbook(SRC)
ws = wb["Annotate"]; ws.title = "Review"
hdr = [c.value for c in ws[1]]
assert hdr[:4] == ["sample_id","sentence_text","previous_sentence","next_sentence"] and hdr[16] == "annotator_notes"
# insert llm_note + verified before annotator_notes (col Q)
ws.insert_cols(17, 2)
HDR_FILL = PatternFill("solid", start_color="1F3A5F"); HDR_FONT = Font(bold=True, color="FFFFFF", name="Arial", size=10)
thin = Side(style="thin", color="D0D0D0"); BORDER = Border(left=thin, right=thin, top=thin, bottom=thin)
for col, name in [(17, "llm_note"), (18, "verified")]:
    c = ws.cell(1, col, name); c.fill = HDR_FILL; c.font = HDR_FONT; c.border = BORDER
    c.alignment = Alignment(wrap_text=True, vertical="center")
LLM_FONT = Font(name="Arial", size=10, color="1F4E9B")
NOTE_FONT = Font(name="Arial", size=9, italic=True, color="7F6000")
AMB_FILL = PatternFill("solid", start_color="F8CBAD"); VER_FILL = PatternFill("solid", start_color="FFF2CC")
WRAP = Alignment(wrap_text=True, vertical="top")
missing = []
for r in range(2, ws.max_row + 1):
    sid = ws.cell(r, 1).value; text = ws.cell(r, 2).value
    L = labels.get(sid)
    if L is None: missing.append(sid); continue
    for i, (code, s, ev) in enumerate(L["slots"][:3]):
        assert ev in text, (sid, ev)
        base = 5 + 3 * i
        ws.cell(r, base, CODE2NAME[code]); ws.cell(r, base + 1, SENT[s]); ws.cell(r, base + 2, ev)
        for k in range(3): ws.cell(r, base + k).font = LLM_FONT
    ws.cell(r, 14, L["ch"]); ws.cell(r, 15, L["fs"]); ws.cell(r, 16, L["amb"])
    for k in (14, 15, 16): ws.cell(r, k).font = LLM_FONT
    n = ws.cell(r, 17, L["note"] or None); n.font = NOTE_FONT; n.alignment = WRAP; n.border = BORDER
    v = ws.cell(r, 18); v.fill = VER_FILL; v.border = BORDER; v.alignment = WRAP
    if L["amb"]: ws.cell(r, 1).fill = AMB_FILL
assert not missing, missing
for col, w in zip("QRST", [40, 9, 35, 18]): ws.column_dimensions[col].width = w
n = ws.max_row
dv = DataValidation(type="list", formula1="=Lists!$D$2:$D$3", allow_blank=True); ws.add_data_validation(dv); dv.add(f"R2:R{n}")
ws.auto_filter.ref = f"A1:T{n}"

# ---- frozen copy of the LLM output (before any human edit)
orig = wb.copy_worksheet(ws); orig.title = "LLM labels (original)"
orig.protection.sheet = True; orig.sheet_properties.tabColor = "1F4E9B"; orig.freeze_panes = "C2"
for col, w in zip("ABCDEFGHIJKLMNOPQRST", [9,60,35,35,30,11,28,30,11,28,30,11,28,12,9,9,40,9,35,18]):
    orig.column_dimensions[col].width = w

# ---- highlight any cell the reviewer changes (vs the frozen LLM copy)
CHG = PatternFill("solid", start_color="C6EFCE", end_color="C6EFCE")
ws.conditional_formatting.add(f"E2:P{n}", FormulaRule(formula=["E2<>'LLM labels (original)'!E2"], fill=CHG))

# ---- README
old_readme = wb["README"]; idx = wb.sheetnames.index("README"); wb.remove(old_readme)
rd = wb.create_sheet("README", idx)
counts = Counter(c for L in labels.values() for c, _, _ in L["slots"])
sent_counts = Counter(SENT[s] for L in labels.values() for c, s, _ in L["slots"] if s)
lines = [
 ("Pilot v3 - LLM pre-labelled, for HUMAN VERIFICATION", True),
 ("", False),
 ("What this is", True),
 ("The 200 pilot sentences pre-labelled by an LLM (Claude Opus 5.5, 5 Nov 2026) using codebook v1.1 (topic_to_aspect_mapping_v.1.1.xlsx). Methodology Step 10: LLM labels are suggestions, never ground truth.", False),
 ("A row becomes gold ONLY when you set verified = 1. Unverified rows are excluded from gold_absa_dataset.", False),
 ("", False),
 ("How to review (target ~30 sec per clear row)", True),
 ("1. Work in the 'Review' sheet. Blue text = LLM suggestion. Edit any aspect / sentiment / evidence / channel / flag cell directly - edited cells turn green automatically.", False),
 ("2. Orange sample_id = the LLM was unsure (ambiguity_flag = 1, reason in llm_note). Do these carefully; they are the codebook test cases.", False),
 ("3. When the row is right (after any edits), set verified = 1. Use annotator_notes for your reasoning when you disagree.", False),
 ("4. Missing aspect? Fill the next empty slot. Wrong aspect? Overwrite it, or clear all three cells of that slot.", False),
 ("5. Do NOT edit 'LLM labels (original)' (protected): it is the frozen LLM output used to measure LLM-vs-human agreement.", False),
 ("", False),
 ("Known bias and how it is controlled", True),
 ("Reviewing pre-filled labels anchors you towards accepting them. Controls: (a) Annotator B labels 40 of these sentences BLIND (annotation_pilot_v3_annotator_B.xlsx, not pre-labelled); (b) report kappa for you vs B AND for LLM vs B; (c) if LLM vs B is much lower than you vs LLM, anchoring is likely - re-check before scaling.", False),
 ("", False),
 ("LLM label profile", True),
 (f"Aspect slots used: {sum(counts.values())} across 200 sentences. " + ", ".join(f"{CODE2NAME[k]}: {v}" for k, v in counts.most_common()), False),
 (f"Sentiment: {dict(sent_counts)}. Rows flagged ambiguous by the LLM: {sum(L['amb'] for L in labels.values())}. Food-safety flags: {sum(L['fs'] for L in labels.values())}.", False),
 ("", False),
 ("Codebook questions raised while pre-labelling (decide during review -> v1.2)", True),
 ("Q1  Long wait the customer explicitly accepts ('Waited 72 minutes ..., worth every penny!') - SPEED Negative or Neutral? (P105, P134)", False),
 ("Q2  Stale/spoiled food with no illness reported ('sour and old smell') - food-safety flag or FRESH only? (P160)", False),
 ("Q3  Unsafe food handling with no illness ('servers grabbing the chips with their bare hands') - flag? (P190)", False),
 ("Q4  Feeling rushed - SPEED or STAFF? (P111)", False),
 ("Q5  Dish not as advertised ('not spicy as advertised') - ACC or FOOD? (P104)", False),
 ("Q6  Restaurant name contains a dish ('Tora sushi was amazing!') - OVR or FOOD? (P044)", False),
 ("Q7  Pricing-policy disputes (lunch vs dinner price, charged for a regular order) - PRICE, ACC or OTHER? (P062, P199)", False),
 ("Q8  Customer cannot reach the restaurant to complain (calls not answered, website) - COMPL? (P001, P060, P128)", False),
 ("Q9  OTHER watch-list: kid-friendliness (P138), catering (P185), adjacent retail store (P154), 'supporting local' (P032).", False),
 ("Q10 Segmentation misses: '..' and missing spaces merge several sentences, giving >3 aspects (P040, P110, P184, P194). Consider fixing '..' splitting in 04_prepare_nlp_segments or adding a 4th slot.", False),
 ("", False),
 ("Files", True),
 ("annotation_pilot_v3_sentence.xlsx - blank version (unchanged), if you prefer to annotate blind.", False),
 ("llm_prelabels_v1_claude.txt - raw LLM output (traceability). 05c_llm_prelabels_pilot_v3.py rebuilds this workbook.", False),
]
for i, (t, bold) in enumerate(lines, 1):
    c = rd.cell(i, 1, t); c.font = Font(name="Arial", size=14 if i == 1 else 10, bold=bold, color="1F3A5F" if i == 1 else "000000")
    c.alignment = Alignment(wrap_text=True, vertical="top")
rd.column_dimensions["A"].width = 130
wb.active = wb.sheetnames.index("Review")
wb.save(OUT)
print("saved", OUT.name, "| aspects", dict(counts.most_common()), "| sentiment", dict(sent_counts))
