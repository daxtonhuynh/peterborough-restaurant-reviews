# -*- coding: utf-8 -*-
"""Shared ABSA resources (codebook v1.2): aspect codes, cue lexicons, sentiment rules, food-safety rules."""
import re
CODES = ["FOOD","FRESH","PORT","MENU","PRICE","STAFF","SPEED","ACC","AMB","CLEAN","LOC","DELIV","DIET","COMPL","OVR","OTHER"]
NAME = {"FOOD":"Food & drink taste & quality","FRESH":"Freshness, temperature & cooking execution","PORT":"Portion size",
 "MENU":"Menu variety & options","PRICE":"Price & value","STAFF":"Staff & service quality","SPEED":"Service speed, waiting & seating",
 "ACC":"Order & billing accuracy","AMB":"Ambience & noise","CLEAN":"Cleanliness & hygiene","LOC":"Location, parking & accessibility",
 "DELIV":"Takeout & delivery experience","DIET":"Dietary accommodation","COMPL":"Complaint handling & service recovery",
 "OVR":"Overall experience, recommendation & return intention","SAFETY":"Reported food-safety concern (flag)",
 "OTHER":"Other / business-specific","NA":"Not applicable / context only"}
SHORT = {"FOOD":"Food & drink","FRESH":"Freshness & cooking","PORT":"Portion size","MENU":"Menu variety","PRICE":"Price & value",
 "STAFF":"Staff & service","SPEED":"Speed & waiting","ACC":"Order & billing accuracy","AMB":"Ambience","CLEAN":"Cleanliness & hygiene",
 "LOC":"Location & parking","DELIV":"Takeout & delivery","DIET":"Dietary needs","COMPL":"Complaint handling","OVR":"Overall / return intention","OTHER":"Other"}
CODE_OF = {v: k for k, v in NAME.items()}
DISH = (r"tacos?|burritos?|enchiladas?|quesadillas?|nachos|guac\w*|salsas?|shawarmas?|shawerma|sushi|sashimi|rolls?|ramen|pho|curry|curries|"
        r"biryani|naan|paneer|samosas?|tikka|masala|pad thai|burgers?|fries|poutine|brisket|ribs|wings|chicken|beef|pork|lamb|steak|fish|seafood|"
        r"shrimp|salads?|soups?|broth|sandwich(es)?|wraps?|pizza|pasta|noodles|rice|desserts?|cake|cheesecake|churros|donuts?|eggs?|benedict|"
        r"waffles?|pancakes?|bread|cornbread|appetizers?|apps|entrees?|mains?|platters?|bowls?|kebabs?|falafel|hummus|souvlaki|gyros?|"
        r"cocktails?|margaritas?|mojitos?|drinks?|coffee|lattes?|chai|tea|lemonade|smoothies?|beers?|wine")
LEX = {
 "FOOD":  r"\b(food|dish|dishes|meals?|flavou?rs?|flavou?rful|tast\w*|delicious|yumm?y?|bland|salty|seasoning|seasoned|authentic|disgusting|"
          r"inedible|mouth.?watering|presentation|" + DISH + r")\b",
 "FRESH": r"\b(fresh(ly)?|stale|cold|lukewarm|warm|reheated|microwaved|frozen|soggy|dry|dried out|over.?cooked|under.?cooked|burnt|burned|"
          r"crispy|crisp|crunchy|tender|juicy|moist|greasy|oily|chewy|rubbery|cooked to perfection|perfectly cooked|well done|old oil)\b",
 "PORT":  r"\b(portions?|serving(s| size)?|generous|quantity|amount of|leftovers|skimp\w*|filling|huge (plate|portion|serving)s?|"
          r"(small|tiny|big|large|massive) (portion|serving|plate|amount)s?|pieces of|stuffed)\b",
 "MENU":  r"\b(menu|selection|variety|choices?|specials?|seasonal|sold out|ran out|run out|kids menu|on tap|tap beers?|craft beers?|wine list|"
          r"limited options|lots of options|many options)\b",
 "PRICE": r"(\$\s?\d+|\b(prices?|priced|pricey|pricing|expensive|cheap|affordable|over.?priced|value|money|dollars?|deals?|happy hour|"
          r"discounts?|bang for|buck|costs?|costed|rip.?off)\b)",
 "STAFF": r"\b(staff|servers?|waiters?|waitress(es)?|waitstaff|wait staff|host(ess)?|bartenders?|cashiers?|owners?|manager|employees?|team|"
          r"service|friendly|unfriendly|rude|attentive|inattentive|polite|welcoming|hospitab\w*|hospitality|kind|helpful|professional|"
          r"unprofessional|courteous|knowledgeable|recommendations?|ignored|grumpy|arrogant|rushed|hurried)\b",
 "SPEED": r"\b(wait(ed|ing)?|slow(ly)?|fast|quick(ly)?|prompt(ly)?|minutes?|mins?|hours?|hrs?|took (forever|ages|a while|so long|too long)|"
          r"long time|forever|delay(ed|s)?|seated|reservations?|right away|in no time|efficient(ly)?|no wait)\b",
 "ACC":   r"\b(wrong (order|dish|item|food|meal|drink)s?|got the wrong|missing|forgot|forgotten|mix(ed)?.?up|not what (i|we) (ordered|asked)|"
          r"incorrect(ly)?|over.?charged|charged|bill|bills|receipt|as advertised|special requests?|substitut\w*|left out|"
          r"(didn.?t|never) (get|got|receive|received|came))\b",
 "AMB":   r"\b(atmosphere|ambiance|ambience|vibes?|decor|d[eé]cor|music|noisy|noise|loud|quiet|cozy|cosy|patio|interior|lighting|seating|"
          r"seats|comfortable|setting|tvs?|ventilation|crowded|romantic|date night|charming|space|spacious|cramped)\b",
 "CLEAN": r"\b(clean|cleanliness|dirty|filthy|sticky|unsanitary|unhygienic|hygien\w*|washrooms?|bathrooms?|restrooms?|toilets?|smell(s|y|ed)?|"
          r"stinks?|hairs?|flies|bugs?|cockroach\w*|mice|bare hands|gloves|dingy|messy|spotless|tidy|grimy|greasy tables?)\b",
 "LOC":   r"\b(parking|parked|park|location|located|downtown|street|walking distance|easy to find|hard to find|accessible|accessibility|"
          r"wheelchair|stairs|stroller|convenient(ly)?|edge of town|plaza|parking lot)\b",
 "DELIV": r"\b(packag\w*|packed|containers?|spill(ed|ing)?|leak(ed|ing|y)?|drivers?|uber ?eats|skip ?the ?dishes|doordash|online orders?|"
          r"ordered online|order(ing)? online|delivery (time|was|took|arrived)|takeout experience|take out experience|for take ?out|"
          r"pick ?up (time|order|was|window)|ready for pick ?up|curbside)\b",
 "DIET":  r"\b(vegan|vegetarian|veggie options|gluten|celiac|coeliac|dairy.?free|lactose|allerg\w*|halal|kosher|keto|nut.?free|peanuts?|"
          r"dietary|restrictions?|plant.?based|without (garlic|onion|meat|dairy))\b",
 "COMPL": r"\b(apologi\w*|refund\w*|comped|comp(ed)? (us|our|the)|compensat\w*|remade|re-made|made it right|took it back|handled (it|the)|"
          r"criticism|replied|reply to the owner|response history|no response|hung up|answer the phone|attend your calls|ownership of|"
          r"(manager|owner) (came|apologi\w*|offered|fixed|reached))\b",
 "OVR":   r"(\b(recommend\w*|come back|coming back|be back|go back|going back|return(ing)?|revisit|again|gem|favou?rite|fav|must.?try|"
          r"must.?visit|experience|stars?|avoid|never again|go-to|goto|hidden gem|love (this|the) place|great (place|spot|restaurant)|"
          r"best (place|restaurant|spot)|worst (place|restaurant)|thank you|thanks)\b|\b\d{1,2}\s?/\s?10\b|\b[0-5]\s?/\s?5\b)",
 "OTHER": r"\b(new owners?|ownership|franchis\w*|opening hours|hours of operation|closed early|cash only|debit|loyalty|gift cards?|"
          r"catering|catered|trivia|retail|store behind|supporting local|support local|local business)\b",
}
LEX_RX = {k: re.compile(v, re.I) for k, v in LEX.items()}
CANT_WAIT = re.compile(r"\b(can.?t|cannot|can not) wait\b", re.I)

# ---- sentiment rules (scope text -> 'Positive'/'Negative'/'Neutral' or None = defer to VADER)
RULES = {
 "SPEED": dict(accept=r"(worth (it|the wait|every)|not an issue|didn.?t mind|no problem|was fine|expected (it|that)|understandabl)",
               neg_first=r"(not worth the wait|never .{0,40}on time|not on time|took forever)",
               pos=r"\b(fast|quick(ly)?|prompt(ly)?|right away|immediately|no wait|in no time|efficient(ly)?|on time|in a timely|speedy)\b",
               neg=r"(\bslow(ly|est)?\b|\bwait(ed|ing)\b|\btook (forever|ages|a while|so long|too long|over|about|around|almost|nearly|\d)|"
                   r"\b\d+\s*(-\s*\d+\s*)?(min|mins|minutes|hour|hours|hr|hrs)\b|\blong time\b|\bforever\b|\bdelay(ed|s)?\b|\blate\b)",
               neutral_only=r"\breservations?\b"),
 "PORT": dict(pos=r"\b(generous|huge|large|big|plenty|filling|leftovers|stuffed|massive|ample|hearty|good size|good portions?|great portions?)\b",
              neg=r"\b(small|tiny|not enough|skimp\w*|lesser|half the|barely|smaller|stingy|meager|meagre|little (food|chicken|meat))\b"),
 "FRESH": dict(neg_first=r"(\bnot (taste |tasting |very |that |so |really )?(fresh|hot|warm|crispy)\b|\b(wasn.?t|weren.?t|isn.?t|aren.?t) (very |that |so )?(fresh|hot|warm|crispy)\b)",
               neg=r"\b(stale|cold|lukewarm|soggy|dry|dried out|over.?cooked|under.?cooked|burnt|burned|raw|greasy|oily|chewy|rubbery|"
                   r"reheated|microwaved|frozen|old|hard)\b",
               pos=r"\b(fresh(ly)?|hot|warm|crisp(y)?|crunchy|tender|juicy|moist|perfectly cooked|cooked to perfection|cooked perfectly)\b"),
 "PRICE": dict(neg=r"(over.?priced|\bexpensive\b|\bpricey\b|not worth|waste of money|rip.?off|\bsteep\b|too much (money|for)|high price|"
                   r"price(s)? (is|are|was|were) (too |a bit |quite |very |really )?(high|steep)|charged (the |us )?(full|extra|more)|charged us)",
               pos=r"(\baffordable\b|reasonabl\w*|\bcheap\b|great (value|price|deal)s?|good (value|price|deal)s?|worth (it|every)|bang for|"
                   r"happy hour|\bdeals?\b|value for|fair price|best price|well priced|inexpensive)"),
 "ACC": dict(pos=r"(exactly as (ordered|requested|asked)|got (it|everything|our order) right|correct(ly)?|accurate(ly)?|as requested)",
             default="Negative"),
 "COMPL": dict(pos=r"(made it right|refunded|reached out|appreciate|remade|re-made|took it back|replaced|comped|offered (to|us)|apologized and)",
               default="Negative"),
 "CLEAN": dict(neg_first=r"\bnot (very |that |so )?clean\b",
               neg=r"\b(dirty|filthy|sticky|unsanitary|unhygienic|hairs?|flies|bugs?|cockroach\w*|mice|dingy|messy|grimy|stink\w*|bare hands|smell(y|ed)?)\b",
               pos=r"\b(clean|spotless|tidy|immaculate|sanitary)\b"),
 "OVR": dict(neg_first=r"(never (go(ing)? back|return\w*|again|coming back|be back)|won.?t (be back|return|go back|be returning|be coming)|"
                       r"would(n.?t| not) (recommend|return|go back|come back)|(not|don.?t|do not|never) recommend|\bavoid\b|first and last|"
                       r"\b[0-2]\s?/\s?10\b|\bworst\b|waste of|stay away|never again)",
             pos=r"((will|would|we.?ll|i.?ll|definitely|surely|can.?t wait to|cannot wait to)( definitely| surely| be)? (be back|come back|coming back|return|go back|visit again|order again|be ordering)|"
                 r"recommend\w*|must.?(try|visit)|\bgem\b|favou?rite|\b(9|10)\s?/\s?10\b|\b5\s?/\s?5\b|love (this|the) place|best (place|restaurant|spot)|go-to|\bwe.?ll be back\b|will be back)"),
 "DIET": dict(neg=r"(wouldn.?t trust|not (accommodat\w*|careful)|cross.?contamina\w*|no (vegan|vegetarian|gluten)|lack of (vegan|vegetarian|options)|not respectful)",
              pos=r"(options?|accommodat\w*|plenty of|lots of|friendly)"),
 "AMB": dict(neg=r"\b(issue|problem|too loud|loud|noisy|cramped|crowded|hazy|stuffy|freezing|dark|dated|lacking|not a pub)\b"),
 "LOC": dict(neg=r"(out of (the )?way|hard to find|no parking|horrible parking|difficult (to )?park|edge of town|limited parking|rundown)",
             pos=r"(easy (to find|parking)|easy to find parking|convenient\w*|close to|walking distance|plenty of parking|right downtown)"),
}
GENERIC_NEG = re.compile(r"\b(no one|nobody|none of us|neither of us) (was|were|is|liked|enjoyed|particularly)|would be (much |a lot )?better if|"
    r"could (be|use) (better|more|some)|needs? (to be )?(improv\w*|work)|nothing special|not (particularly|very|that|really) (thrilled|impressed|good|great)|"
    r"not impressed|not great|not good|not worth|disappointing|disappointed|lack(ed|ing)\b", re.I)
RULES_RX = {a: {k: (v if k == "default" else re.compile(v, re.I)) for k, v in d.items()} for a, d in RULES.items()}
CONTRAST = re.compile(r"\b(but|however|although|though|except|yet|whereas|while|unfortunately)\b|;", re.I)
VADER_ADD = {"bland": -1.5, "soggy": -1.8, "overcooked": -1.5, "undercooked": -1.8, "stale": -1.8, "overpriced": -2.0, "greasy": -1.2,
             "lukewarm": -1.2, "tasteless": -2.0, "flavourful": 2.0, "flavorful": 2.0, "tender": 1.2, "juicy": 1.5, "crispy": 1.0,
             "attentive": 1.8, "inattentive": -1.8, "gem": 2.0, "mid": -0.6, "inedible": -2.5, "rude": -2.3, "unprofessional": -1.8,
             "unsanitary": -2.5, "filthy": -2.5, "dirty": -1.8, "sticky": -1.0, "rushed": -1.2, "ignored": -1.6, "skimpy": -1.5,
             "generous": 1.6, "affordable": 1.4, "pricey": -1.0, "underwhelming": -1.6, "mediocre": -1.4, "meh": -1.0, "dry": -0.8}

# ---- food safety (codebook v1.2 rules 8 / 8a)
SAFETY_YES = re.compile(r"\b(food poisoning|got sick|get sick|gets sick|getting sick|became sick|were sick|was sick|so sick|very sick|super sick|"
    r"sick (after|from|to our stomach)|vomit\w*|threw up|throw(ing)? up|puk(e|ed|ing)|diarrh\w*|dysentery|upset stomach|stomach (ache|pain|cramps?|issues?)|"
    r"parasites?|allergic reaction|hairs? (in|on)|found (a )?hairs?|plastic (in|piece)|piece of plastic|it was just plastic|bug in|insects? in|"
    r"cockroach\w*|mou?ldy?|rotten|expired|raw (in the middle|inside|chicken|meat|pork)|pink (meat|inside|chicken)|red and pink|"
    r"under.?cooked (chicken|meat|pork)|bare hands|without gloves|touching our food|health (inspector|unit|department|and safety|safety))\b", re.I)
SAFETY_NO = re.compile(r"\b(spoiled me|spoil(ed)? us|sick of|eat so much|ate so much|over.?ate|raw fish|sashimi|poke|tartare|ceviche)\b", re.I)
RETURN_POS = re.compile(r"\b(come back|coming back|be back|go back|going back|return(ing)?|revisit|again|regulars?|repeat customers?)\b", re.I)
RETURN_NEG = re.compile(r"\b(never|won.?t|will not|wouldn.?t|not (be )?(coming|going)|last time|first and last|no longer)\b", re.I)
CHANNEL = [("delivery", re.compile(r"\b(deliver(y|ed)|uber ?eats|skip ?the ?dishes|doordash|driver)\b", re.I)),
           ("takeout", re.compile(r"\b(take ?out|take-out|to go|pick(ed)? ?up|pickup|curbside|brought (it )?home|got home)\b", re.I)),
           ("dine_in", re.compile(r"\b(dine[ -]?in|dined|dining room|our (server|waiter|waitress)|seated|table|patio)\b", re.I))]

# ---- sentiment functions (identical to those evaluated in 07_absa_model.py)
from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer
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

