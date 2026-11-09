# -*- coding: utf-8 -*-
"""Content for taxonomy v1.1: aspect definitions, codebook, guideline rules, topic revisions."""

ASPECTS = [
 # code, name, type, change_from_v1_0, definition, include, exclude, pos_ex, neg_ex, ambiguous_ex, kpi
 ("FOOD","Food & drink taste & quality","core",
  "Renamed (was 'Food taste & overall quality'). Drinks, cocktails and coffee are now explicitly included.",
  "How the food or drink tastes and its overall quality: flavour, seasoning, spice level, authenticity, recipe, ingredient quality, presentation, or a dish judged good/bad overall.",
  "delicious; bland; too salty; not spicy enough; authentic / not authentic; 'best shawarma in town'; presentation; cocktail or coffee taste; dish-level praise or complaint.",
  "Temperature, freshness, doneness or texture (dry, soggy, overcooked, crispy) -> Freshness, temperature & cooking execution. Amount -> Portion size. Range of dishes -> Menu variety. Price -> Price & value. Naming a dish with no evaluation ('I ordered the lamb taco') -> Not applicable / context only.",
  "The brisket was super flavourful and moist with a great smoke ring and smoky flavour.  [FOOD Positive + FRESH Positive ('moist')]",
  "The food was severely lacking in flavor and seasoning.",
  "Good was good but definitely overpriced.  -> FOOD Positive + PRICE Negative (two aspects, two sentiments).",
  "Food-quality complaint rate; dish-level praise/complaints (menu engineering); taste vs peer group."),
 ("FRESH","Freshness, temperature & cooking execution","core",
  "Renamed (was 'Freshness, temperature & food condition'). Texture/doneness descriptors now belong here in BOTH directions (dry/soggy/overcooked and crispy/tender/cooked perfectly), so this aspect is not negative-only by construction.",
  "Whether food arrives fresh, at the right temperature and correctly cooked: fresh vs stale/frozen/reheated, hot vs cold/lukewarm, doneness and texture.",
  "cold food; lukewarm tea; soggy fries; dry chicken; overcooked steak; tasted microwaved/reheated; 'fresh', 'freshly made'; crispy; juicy; tender; cooked to perfection.",
  "Flavour/seasoning -> Food & drink (tag both if both are stated). Raw meat or spoiled food reported as a health risk -> ALSO tick Reported food-safety concern. Do not infer freshness from 'delicious' alone.",
  "The chips were warm, crunchy and delicious.  [FRESH Positive + FOOD Positive]",
  "We ordered fries instead of the corn chips and they were undercooked, soggy and not hot.",
  "So fresh and incredibly delicious!  -> FRESH Positive + FOOD Positive: 'fresh' is a stated attribute, so it is tagged even inside generic praise.",
  "Kitchen execution and hold-time issues; temperature complaints by channel (dine-in vs takeout)."),
 ("PORT","Portion size","core","Unchanged.",
  "Amount of food served: size, quantity, how filling, amount of protein or toppings.",
  "generous portions; small portions; 'barely three pieces of chicken'; servings were huge; kids portions.",
  "Whether the amount is worth the money -> ALSO Price & value (tag both if the sentence links amount and price).",
  "Kids portions are very generous.",
  "Ordered rice bowls chicken vindaloo and buttered chicken, I had maybe 5 small chicken pieces in mine.",
  "The portions were unacceptable for the amount I paid.  -> PORT Negative + PRICE Negative.",
  "Portion consistency / recipe-spec adherence; portion complaints vs price tier."),
 ("MENU","Menu variety & options","core",
  "Renamed (was 'Menu variety'). 'Dietary accommodation' removed from its description - all dietary content now goes to Dietary accommodation.",
  "Range, choice and novelty of what is offered: number of options, seasonal or special items, drink selection, items being unavailable, kids menu.",
  "winter menu; rotating specials; great beer selection; out of an item; 'should be a permanent menu item'; limited options.",
  "Vegan / gluten-free / allergy options -> Dietary accommodation. How a dish tastes -> Food & drink. Dish not matching the menu description -> Order & billing accuracy.",
  "The winter menu is fantastic!",
  "(constructed) The menu is quite small and hasn't changed in years.",
  "They got tons of Vegan option onto their menu.  -> DIET Positive, NOT MENU.",
  "Menu breadth vs peer group; stock-outs."),
 ("PRICE","Price & value","core","Unchanged.",
  "Affordability and value for money, including deals, happy hour, discounts and specials; price judged against quality or quantity.",
  "overpriced; reasonable; worth it / not worth the money; great deals; half-off happy hour; '$19 for a margarita'.",
  "Being charged the wrong amount / bill errors -> Order & billing accuracy. Payment options (cash only) -> Other / business-specific.",
  "Came in for happy hour and honestly didn't expect this much value.",
  "The food itself not worth the money.",
  "For 3oz of tequila and $19, you expect a strong, flavourful margarita but mine tasted diluted.  -> PRICE Negative + FOOD Negative.",
  "Value perception vs price tier and peer group; promotion effectiveness."),
 ("STAFF","Staff & service quality","core",
  "Renamed (was 'Staff friendliness & professionalism'). Now explicitly covers generic 'service was great/poor' (when speed is not mentioned) and owners/managers acting as hosts.",
  "How customers were treated by staff (servers, hosts, cashiers, owners/managers on the floor): friendliness, attentiveness, helpfulness, professionalism, menu knowledge, recommendations; generic service quality.",
  "named server praise; rude; attentive; checked on us; knowledgeable about the menu; 'the service was excellent'; server never came back (understaffing effect).",
  "Explicit time / waiting -> Service speed, waiting & seating. What staff did AFTER something went wrong -> Complaint handling & service recovery. Wrong item -> Order & billing accuracy.",
  "Hannah was attentive and friendly.",
  "Staff behaviour is very rude toward guests.",
  "The service was very nice though a little slow considering there were only 2 other tables.  -> STAFF Positive + SPEED Negative.",
  "Staff praise/complaint rate; named-staff recognition; training needs."),
 ("SPEED","Service speed, waiting & seating","core",
  "Renamed (was 'Service speed & waiting time'). Reservation and seating process now included (this replaces the Ambience secondary on Run1 T39).",
  "Time and flow of service: wait to be seated, reservations honoured or easy to make, time to order, time for food, time for the bill, pickup ready time.",
  "waited 45 minutes; food came fast; seated right away; reservation not honoured; reserving by phone was easy; took forever to get the bill; kitchen slow.",
  "The server's attitude while being slow -> ALSO Staff. A long wait for a takeout order is still SPEED (record channel = takeout), not Takeout & delivery.",
  "Service was super fast!",
  "Two hours from arrival to end of the main course with no appetizer or dessert.",
  "It was a Monday night so it wasn't too busy and we were seated right away.  -> SPEED Positive ('seated right away'); the rest is context.",
  "Wait-time complaint rate; peak-hour staffing; table turn."),
 ("ACC","Order & billing accuracy","core",
  "Renamed and extended (was 'Order accuracy'). Billing errors added.",
  "Getting the order and the bill right: correct items, nothing missing, special requests honoured, order heard and entered correctly, correct charges, split bills.",
  "wrong dish; teas missing from the takeout bag; forgot the sides; asked for spicy and it wasn't; overcharged; wrong bill; charged for items not ordered.",
  "Price level itself -> Price & value. How the mistake was resolved -> ALSO Complaint handling & service recovery.",
  "(constructed) Everything was exactly as ordered, even with our substitutions.",
  "However, when we got home and checked the order, the teas were missing.",
  "We resolve what should be on each bill and ... an offer to have some of the bill compensated for the confusion.  -> ACC Negative + COMPL Positive.",
  "Order error rate; POS / ticket process; takeout bag check."),
 ("AMB","Ambience & noise","core","Unchanged.",
  "Physical and sensory environment: atmosphere, vibe, decor, music, noise, lighting, seating comfort, crowding, patio, TVs.",
  "cozy; lively; too loud; live music; comfortable seats; beautiful interior; TVs.",
  "Cleanliness or smells -> Cleanliness & hygiene. 'Busy night' given as context with no evaluation -> Not applicable / context only.",
  "The atmosphere was comfortable and the seats were great.",
  "If I were to complain about anything, I don't particularly like TV's in restaurants.",
  "Went there on Friday evening - it was a fairly busy evening, so we sat at the bar.  -> Not applicable / context only (no evaluation).",
  "Ambience vs peer group (atmosphere sub-rating correlates r = 0.83 with stars in the EDA)."),
 ("CLEAN","Cleanliness & hygiene","core",
  "Renamed (was 'Cleanliness'). Food-handling and staff hygiene now included.",
  "Cleanliness of tables, washrooms, floors and dishes; staff and food-handling hygiene; smells.",
  "clean washrooms; dirty tables; sticky floor; hair in food; staff touching food after wiping sweat; smell of cleaner.",
  "Illness after eating with no hygiene detail -> Reported food-safety concern ONLY (do not assume the cause was hygiene).",
  "Drinks and food are always wonderful and the washrooms are super clean.  [FOOD Positive + CLEAN Positive]",
  "Watching sweaty people drip sweat and wiping their sweat and then touching our food was traumatizing.  [CLEAN Negative + SAFETY flag]",
  "There was an overwhelming smell of cleaner lingering in the dining room.  -> CLEAN Negative (rule: smells go to Cleanliness, not Ambience).",
  "Hygiene complaint rate (zero-tolerance metric)."),
 ("LOC","Location, parking & accessibility","core","Unchanged.",
  "Getting there and getting in: location convenience, parking, walking distance, wheelchair or stroller access, stairs, signage.",
  "easy parking; paid street parking; downtown location; hard to find; not wheelchair accessible.",
  "'Best spot in town' -> Overall (no location evaluation). Visiting Peterborough as context -> Not applicable.",
  "Pretty easy to find parking despite being downtown!",
  "(constructed) Parking is a nightmare and there's no accessible entrance.",
  "Parking is outside on the street, and it's paid.  -> LOC Neutral (factual, no judgement).",
  "Access barriers; information on the Google listing."),
 ("DELIV","Takeout & delivery experience","core",
  "Renamed (was 'Delivery & takeout'). Now an aspect ONLY when the off-premise experience itself is evaluated. The channel (dine-in / takeout / delivery) is recorded separately in the service_channel field.",
  "Evaluation of the off-premise experience: packaging, how food travels, pickup process, phone/online/app ordering, delivery driver or app.",
  "great takeout experience; packaging leaked; pickup was smooth; online ordering broken; delivery arrived cold (+ FRESH).",
  "'Ordered' / 'ordering' alone is NOT evidence of takeout. Intention to re-order -> Overall. Taste of a takeout meal -> Food & drink with service_channel = takeout.",
  "It's been years since I've had such a great takeout experience.",
  "Not so great for takeout.",
  "Definitely ordering that again next time.  -> OVR Positive (return intention), NOT DELIV (this was the v1.0 error on Run1 T87).",
  "Off-premise satisfaction; packaging; dine-in vs takeout comparison."),
 ("DIET","Dietary accommodation","core",
  "Scope unchanged, but it now owns ALL dietary content (removed from Menu variety).",
  "Availability of and care for dietary needs: vegan, vegetarian, gluten-free, halal, allergies, religious or ingredient restrictions, and how staff handle such requests.",
  "lots of vegan options; very accommodating to allergies; cross-contamination worries; 'made without garlic and onion' requests.",
  "Taste preferences (dislikes cilantro, wanted it spicier) -> Food & drink or Order accuracy. An allergic reaction reported as harm -> ALSO tick Reported food-safety concern.",
  "I have severe peanut and nut allergies and they were super accomdating!",
  "So, if you have dietary restrictions, I wouldn't trust the kitchen here.",
  "Warning if you don't like cilantro make sure to ask before hand.  -> FOOD (preference), NOT DIET (this replaces the v1.0 Dietary secondary on Run1 T47).",
  "Dietary coverage vs peer group; allergen protocol."),
 ("COMPL","Complaint handling & service recovery","core",
  "NEW. Previously hidden inside Other / business-specific (Run2 T30).",
  "What the restaurant did after something went wrong or after criticism, as described by the customer: apologies, remakes, refunds, comps, manager involvement, owner responses to complaints or reviews.",
  "they remade it right away; manager comped our drinks; owner handles criticism unprofessionally; no ownership of mistakes; 'called to have it remedied and they said that's it'.",
  "The original problem itself -> its own aspect (e.g. wrong order -> ACC). Tag BOTH when the sentence covers problem and response.",
  "The owner did reach out to me directly as well as replying to this, and I appreciate the effort.",
  "After speaking with owner they are not very professional with how they handle criticism.",
  "I called to have it remedied and they basically told me that's it that's all.  -> COMPL Negative; read the previous sentence to see what the original issue was.",
  "Service-recovery success; owner response practice (links to EDA 5F owner-response analysis)."),
 ("OVR","Overall experience, recommendation & return intention","core",
  "Name unchanged; scope narrowed: visit context without evaluation now goes to Not applicable / context only.",
  "Global evaluations not tied to one aspect: overall experience, loving the place, recommending it, would / would not return, 'hidden gem', star-rating statements without a reason.",
  "will definitely be back; would not recommend; great experience; 10/10; not enough stars; first and last time; hidden gem.",
  "Visit narrative with no evaluation ('We went for dinner last night') -> Not applicable. When a reason is given ('the reason for 3 stars is the price') -> the reason's aspect; add OVR only if a global judgement is also stated.",
  "We will definitely be back.",
  "Won't go back, not recommended.",
  "Great food, great service, will be back!  -> FOOD Positive + STAFF Positive + OVR Positive.",
  "Return / recommend intention rate (loyalty proxy)."),
 ("SAFETY","Reported food-safety concern (flag)","flag",
  "NEW flag (v1.0 mapped these sentences to Food taste - Run2 T21).",
  "The customer reports a possible health risk: illness after eating, foreign objects (plastic, hair, insects), allergic reaction, raw/undercooked meat or seafood, spoiled or mouldy food. Annotated IN ADDITION to any regular aspect; no sentiment.",
  "food poisoning; vomiting after eating; plastic in food; hair in my sushi; raw chicken; rice tasted mouldy.",
  "Figurative use ('Ariyana has spoiled me'); 'raw' as a menu term (sashimi); simply disliking a taste.",
  "n/a - the flag has no sentiment.",
  "We woke up the next morning absolutely sick to our stomachs, picture the worst food poisoning possible.",
  "Something smelled off but I assumed maybe something was spilt on the bag ... I started getting an upset stomach.  -> SAFETY (illness reported) + FRESH Negative ('smelled off').",
  "Internal manual-review queue only. Wording must stay 'customers reported'; never state or imply the restaurant caused illness. Excluded from aspect scores and peer rankings; reported as counts."),
 ("OTHER","Other / business-specific","residual",
  "Scope narrowed: owners as hosts -> Staff; owners handling complaints -> Complaint handling; chef/kitchen praise -> Food & drink.",
  "Evaluative content about the business that fits no aspect above: ownership change, franchising, opening hours, payment options, loyalty programmes, gift cards, events.",
  "new owners ruined it; cash only; closed earlier than the listed hours; trivia night.",
  "Anything that fits a core aspect. Use OTHER last.",
  "(constructed) Love that they do trivia night on Thursdays.",
  "I can already tell the new owners are going to ruin this place.",
  "Cheap owner with a barely maintained establishment.  -> OTHER Negative + CLEAN Negative ('barely maintained'); note it.",
  "Watch-list: if a sub-theme passes ~2% of labels in the pilot, promote it to its own aspect."),
 ("NA","Not applicable / context only","residual",
  "Renamed (was 'Not applicable / unclear'). Explicitly includes visit context, ordering narrative and meta-review talk.",
  "No evaluation of the restaurant: who/when/why of the visit, ordering narrative, naming a dish, meta-review talk, incomplete fragments, spam.",
  "We went for dinner last night; I ordered the lamb taco dish; Hopefully I can update my review; Reply to the owner:.",
  "Anything with an evaluation, even implicit ('we waited 45 minutes' -> SPEED Negative). Rating statements with a reason -> the reason's aspect.",
  "n/a","n/a",
  "It was our first time there. -> NA.   vs   First and last time for us. -> OVR Negative.",
  "None. Monitor its share: if NA exceeds ~25% of pilot sentences, revisit segmentation or sampling."),
]

GUIDELINES = [
 ("1. Unit","Label ONE sentence. The previous and next sentences are shown only to resolve references ('It was cold' -> what is 'it'). Do not label aspects that appear only in the context sentences."),
 ("2. Multi-label","Tag every aspect the sentence evaluates (up to 3 slots; if more, use the 3 most specific and write the rest in notes). Slot order does not matter."),
 ("3. Sentiment per aspect","Positive / Negative / Neutral / Mixed, judged from this sentence's wording for THAT aspect only. Never inherit it from the star rating or from the BERTopic run (stars are hidden on purpose). Example: 'Food was delicious and made up for the service.' -> FOOD Positive; STAFF Negative."),
 ("3a. Neutral","Aspect mentioned factually without a judgement: 'Parking is outside on the street, and it's paid.' -> LOC Neutral."),
 ("3b. Mixed","Same aspect evaluated in both directions in this sentence: 'Some dishes were great, others bland.' -> FOOD Mixed. Different aspects with different directions are NOT Mixed - give each its own slot."),
 ("4. Evidence span","Copy the shortest exact text from the sentence that supports the aspect + sentiment ('lacking in flavor and seasoning'). For implicit aspects copy the cue ('waited 45 minutes'). Must be a verbatim substring."),
 ("5. Decision order","(a) Is there any evaluation? If not -> NA, no sentiment. (b) Which concrete aspect(s)? (c) Only if no concrete aspect fits -> OVR. (d) OTHER is the last resort."),
 ("6. Rating statements","Do not drop a sentence just because it mentions stars or reviews. 'The reason for 3 stars is the price.' -> PRICE Negative. 'Not enough stars for this place.' -> OVR Positive. 'Hopefully I can update my review.' -> NA."),
 ("7. Comparisons","Label the aspect being compared: 'Best shawarma in town' -> FOOD Positive. Competitor named with no aspect ('Maglicious over Osmow's any day') -> OVR (sentiment toward the restaurant under review)."),
 ("8. Food-safety flag","Set food_safety_flag = 1 for customer-reported illness, foreign objects, allergic reactions, raw/spoiled food. Also give the regular aspect if one applies (hair in food -> CLEAN; raw chicken -> FRESH). Pure illness report with no other detail -> aspect slot 1 = 'Reported food-safety concern (flag)', no sentiment."),
 ("9. service_channel","dine_in / takeout / delivery / unknown - from this sentence or the context shown. Default unknown. This is NOT an aspect: a takeout meal that tasted great is FOOD Positive with service_channel = takeout."),
 ("10. Sarcasm & idioms","Label the intended meaning: 'It was dryer than my humour!' -> FRESH Negative."),
 ("11. Ambiguity flag","Set ambiguity_flag = 1 whenever you hesitated between aspects or sentiments and write why in annotator_notes. These rows drive the v1.2 codebook revision - over-flagging is better than under-flagging."),
 ("12. LLM pre-labels","If an LLM pre-labels, store its output in separate columns, never in the human columns. Every row must be human-verified; record whether the human changed the label. LLM self-reported confidence is not a probability."),
 ("13. Agreement","Annotator B labels the double-annotation subset independently (no discussion first). Compute Cohen's kappa per aspect (presence/absence) and for sentiment on aspects both annotators tagged; target kappa >= 0.70 before scaling to 800-1,200 sentences. Discuss every disagreement and update this codebook (v1.2)."),
]

# Topic revisions after full re-review of keywords + representative sentences (Nov 2026).
# key: (run, topic_id) -> (primary, [secondary...], certainty, note, food_safety_signal, channel_signal)
R = {}
def rv(run, tid, prim, sec, cert, note, safety="none", channel=""):
    R[(run, tid)] = (prim, sec, cert, note, safety, channel)

# ---------------- Run 1 (all sentences) ----------------
rv("Run1_All",0,"FOOD",["STAFF"],"high","Generic 'great service and delicious food' praise. Two aspects, each with its own sentiment at sentence level. v1.0 collapsed this into Overall.")
rv("Run1_All",2,"OVR",[],"medium","Mostly overall restaurant praise; some sentences carry a concrete aspect (e.g. TV complaint -> Ambience).")
rv("Run1_All",3,"NA",["OVR"],"medium","Mostly visit context ('We went for dinner last night') - not an evaluation. Revisit behaviour ('came back with a group a week later') -> Overall.")
rv("Run1_All",6,"FOOD",["STAFF","AMB"],"high","Multi-aspect praise (food + service, sometimes atmosphere). v1.0 collapsed into Overall.")
rv("Run1_All",10,"FOOD",["FRESH"],"medium","Dish topic; includes cooking-execution complaints ('over cook your chicken ... extremely dry').")
rv("Run1_All",15,"STAFF",["FOOD","AMB"],"high","Staff + food (+ vibe) praise in the same sentences.")
rv("Run1_All",18,"FRESH",["FOOD"],"medium","Temperature/freshness signal mixed with generic taste praise.")
rv("Run1_All",19,"FOOD",[],"medium","Sushi topic, but representative sentences mix other dishes and restaurants.")
rv("Run1_All",20,"OVR",[],"low","Recommendations for visitors; part of the topic is context only ('AI recommended it for our visit').")
rv("Run1_All",23,"FOOD",["FRESH"],"medium","Meat dishes: seasoning -> Food; overcooked / tender -> Freshness, temperature & cooking execution.")
rv("Run1_All",24,"AMB",["FOOD","STAFF"],"medium","Multi-aspect praise (food, atmosphere, service).")
rv("Run1_All",26,"FOOD",["STAFF"],"medium","Breakfast topic; mixes food praise and service praise.")
rv("Run1_All",28,"SPEED",["ACC"],"high","Waiting time; some sentences also report wrong items -> Order & billing accuracy.")
rv("Run1_All",34,"FOOD",["FRESH"],"medium","Ingredient quality and flavour; 'fresh ingredients' -> also Freshness.")
rv("Run1_All",35,"FOOD",["FRESH"],"medium","Seafood/appetisers; 'served cold and very hard', 'greasy' -> Freshness/cooking.")
rv("Run1_All",39,"SPEED",["STAFF"],"medium","Reservation & seating process -> Service speed, waiting & seating. 'No table settings, needed to ask for everything' -> Staff. v1.0 Ambience secondary removed: no atmosphere evaluation in the sentences. Two v1.0 rows merged.")
rv("Run1_All",41,"FOOD",["PRICE"],"medium","Drinks (margaritas) count as Food & drink; '$19 ... tasted diluted' -> also Price.")
rv("Run1_All",43,"FOOD",["FRESH"],"medium","'Fresh and delicious' praise: taste is primary, 'fresh' tagged as Freshness. v1.0 had Freshness as primary.")
rv("Run1_All",45,"STAFF",["FOOD"],"medium","Staff + food praise.")
rv("Run1_All",47,"FOOD",[],"medium","Seasoning/spice/sauce = taste. v1.0 Dietary secondary removed: cilantro is a preference, not a dietary need. Two v1.0 rows merged.")
rv("Run1_All",49,"FOOD",["STAFF","AMB"],"medium","Vietnamese cuisine; sentences also mention the server and the music.")
rv("Run1_All",50,"FOOD",["FRESH"],"medium","Fries: flavour -> Food; soggy -> Freshness/cooking.")
rv("Run1_All",52,"DELIV",["ACC","SPEED"],"low","Phone/online ordering and pickup. Takeout & delivery only when the ordering/pickup process itself is evaluated; misheard/wrong orders -> Order accuracy; ready time -> Speed.",channel="takeout")
rv("Run1_All",53,"STAFF",["FOOD"],"medium","Named staff praise at Chaska. v1.0 had Overall.")
rv("Run1_All",54,"OVR",[],"low","Rating statements ('not enough stars'). Not excluded for mentioning stars: when a reason is given, label the reason's aspect ('took off one star for food' -> Food). v1.0 had Not applicable.")
rv("Run1_All",56,"STAFF",["COMPL"],"medium","Owners/managers acting as hosts -> Staff & service quality; owners handling complaints -> Complaint handling. v1.0 had Other.")
rv("Run1_All",57,"FOOD",["OVR"],"medium","Meals enjoyed. Keyword 'sick' -> a few sentences may be illness reports (flag at sentence level). v1.0 had Overall.",safety="partial")
rv("Run1_All",62,"OVR",[],"low","Competitor comparisons (Osmow's vs others); label the compared aspect when one is named.")
rv("Run1_All",64,"FOOD",["STAFF"],"medium","Chef/kitchen praise reflects food quality. v1.0 had Other.")
rv("Run1_All",65,"NA",["OVR"],"medium","Visit context ('It was our first time there'). v1.0 had Overall.")
rv("Run1_All",70,"SPEED",["STAFF"],"medium","Mix of speed and generic service praise; generic 'service was great' -> Staff & service quality.")
rv("Run1_All",73,"LOC",["OVR"],"medium","Parking/downtown; some sentences are generic 'best spot in town' -> Overall.")
rv("Run1_All",75,"FOOD",["FRESH","PORT"],"medium","Rice dishes; 'overcooked rice with barely three tiny pieces of chicken' -> Freshness + Portion.")
rv("Run1_All",78,"MENU",["FOOD"],"medium","Drink selection = Menu variety; drink taste -> Food & drink.")
rv("Run1_All",82,"FOOD",["FRESH"],"medium","Desserts; 'hard and chewy' churros -> Freshness/cooking.")
rv("Run1_All",83,"DIET",[],"high","Gluten-free / allergy options. Allergic-reaction reports in this topic carry the food-safety flag.",safety="partial")
rv("Run1_All",86,"FOOD",["FRESH"],"medium","'Tostones need to be served HOT' -> Freshness/temperature.")
rv("Run1_All",87,"OVR",["FOOD"],"medium","Intention to re-order a dish = return intention + food praise. 'Ordering' alone is not evidence of takeout/delivery. v1.0 had Delivery & takeout (error flagged in review).")
rv("Run1_All",95,"OVR",[],"low","Meta-review statements. Evaluative ones ('Very disappointing given the reviews of others') -> Overall; pure meta ('update my review') -> Not applicable. v1.0 had Not applicable.")
rv("Run1_All",98,"FOOD",["ACC"],"medium","Tea/chai; 'teas were missing' from a takeout order -> Order & billing accuracy.",channel="takeout (partial)")
rv("Run1_All",99,"STAFF",["SPEED","CLEAN"],"medium","Mostly friendly/attentive service; 'fast' -> Speed; 'clean, inviting' -> Cleanliness. v1.0 had Speed as primary.")
rv("Run1_All",101,"FOOD",["DIET"],"medium","Sauces; request to omit garlic and onion -> Dietary accommodation.")
rv("Run1_All",102,"FOOD",["STAFF"],"medium","'Best Indian food in Peterborough' = food praise; staff mentions. v1.0 had Overall.")
rv("Run1_All",103,"FOOD",["FRESH","SPEED"],"medium","Samosas; 'burnt from over-frying' -> Freshness/cooking; '30+ minute' wait -> Speed.")
rv("Run1_All",110,"AMB",["FOOD","STAFF"],"medium","Multi-aspect praise.")
rv("Run1_All",112,"FOOD",["PORT"],"medium","Bowls; 'half the amount you see' -> Portion.")
rv("Run1_All",113,"AMB",["STAFF"],"high","Atmosphere + service praise in the same sentences.")

# ---------------- Run 2 (negative reviews, 1-3 stars) ----------------
rv("Run2_Negative",0,"SPEED",["STAFF","CLEAN"],"medium","Seating waits / reservations; 'no table settings' -> Staff; 'dirty' tables -> Cleanliness.")
rv("Run2_Negative",1,"SPEED",["FRESH"],"high","Long waits; 'the meat grew cold' -> Freshness/temperature.")
rv("Run2_Negative",2,"OVR",["FOOD","COMPL"],"medium","General disappointment; some sentences about food quality and management.")
rv("Run2_Negative",5,"ACC",["SPEED","DELIV"],"high","Wrong/forgotten orders, incl. phone/online orders; record channel separately.",channel="takeout (partial)")
rv("Run2_Negative",9,"FOOD",["FRESH"],"medium","Meat: seasoning -> Food; overcooked steak -> Freshness/cooking.")
rv("Run2_Negative",13,"OVR",["PRICE","FOOD","STAFF","COMPL"],"low","Rating justifications - must NOT be excluded. Label the aspect named as the reason ('3 stars ... is the price' -> Price; owner's response history -> Complaint handling). v1.0 had Not applicable (error flagged in review).")
rv("Run2_Negative",14,"FOOD",["PORT","SPEED"],"medium","Tacos; '3 tiny tortillas' -> Portion; slow kitchen -> Speed.")
rv("Run2_Negative",15,"FOOD",["STAFF","SPEED"],"medium","Food vs service contrast sentences; sentiment per aspect ('Food was delicious and made up for the service' = Food Positive, Staff Negative). Two v1.0 rows merged.")
rv("Run2_Negative",20,"FRESH",["FOOD","COMPL"],"medium","'Dry' brisket/burger = cooking execution; comment on the owner's reply -> Complaint handling. v1.0 had Food.")
rv("Run2_Negative",21,"SAFETY",["CLEAN"],"high","Customer-reported illness, foreign objects (plastic, hair) and allergic reactions. Flag for manual review; report as 'customers reported', never as an established cause. v1.0 had Food taste (error flagged in review).",safety="dominant")
rv("Run2_Negative",22,"STAFF",["ACC"],"medium","Rude/inattentive server; wrong dishes -> Order accuracy. A few sentences about plastic in food -> food-safety flag at sentence level.",safety="partial")
rv("Run2_Negative",23,"OVR",[],"low","Visitor / competitor recommendations; partly context only.")
rv("Run2_Negative",26,"FRESH",["FOOD"],"medium","Dry / raw chicken = cooking execution; raw meat -> food-safety flag at sentence level. v1.0 had Food.",safety="partial")
rv("Run2_Negative",27,"FOOD",["FRESH","SPEED"],"medium","Sushi; oxidised vegetables, hard rice -> Freshness; 'sushi pulled off someone's plate' -> food-safety flag.",safety="partial")
rv("Run2_Negative",28,"NA",["OVR"],"low","Mostly visit context; 'First and last time for us' -> Overall. v1.0 had Overall.")
rv("Run2_Negative",29,"FOOD",["FRESH"],"medium","Wraps; 'just soggy' -> Freshness/cooking.")
rv("Run2_Negative",30,"COMPL",["OTHER"],"medium","How owners handle criticism -> Complaint handling & service recovery; ownership-change comments -> Other. Checked: these are customer sentences (incl. 'Reply to the owner:' updates); no owner replies leaked into the corpus. v1.0 had Other.")
rv("Run2_Negative",31,"PORT",["PRICE"],"high","'Portions were unacceptable for the amount I paid' -> also Price & value.")
rv("Run2_Negative",35,"FOOD",["OVR"],"low","Chain comparisons across Osmow's locations; label dish quality when stated.")
rv("Run2_Negative",36,"FOOD",["FRESH"],"medium","'Chicken did not seem fresh' -> Freshness.")
rv("Run2_Negative",38,"STAFF",[],"medium","Positive staff mentions inside negative reviews: sentiment comes from the sentence, not from the review rating.")
rv("Run2_Negative",40,"MENU",["STAFF"],"medium","'Forgot initially to give us a kids menu' -> Staff.")
rv("Run2_Negative",41,"AMB",["MENU","STAFF"],"medium","'Service and atmosphere was great but found menu disappointing' -> multi-aspect.")
rv("Run2_Negative",43,"FOOD",["FRESH"],"medium","Fish: 'too oily' -> cooking; 'smelled awful and had to be tossed' -> freshness (+ food-safety flag if illness is reported).",safety="partial")
rv("Run2_Negative",44,"ACC",["COMPL"],"high","Billing errors -> Order & billing accuracy (renamed to cover billing); offer to compensate -> Complaint handling.")
rv("Run2_Negative",45,"FOOD",["ACC"],"medium","'60 dollar platter delivered, no sides' -> missing items = Order accuracy.")
rv("Run2_Negative",46,"NA",[],"medium","Visit context ('Went for lunch on a Saturday'). v1.0 had Overall.")
rv("Run2_Negative",47,"FOOD",["PRICE"],"medium","Salsa; '$20 which is very expensive' -> Price.")

# ---------------- Run 3 (positive reviews, 4-5 stars) ----------------
rv("Run3_Positive",1,"FOOD",["STAFF"],"high","Same pattern as Run1 T0: food + service praise. v1.0 had Overall.")
rv("Run3_Positive",2,"FOOD",["FRESH"],"medium","'Fresh ingredients, delicious' praise.")
rv("Run3_Positive",3,"NA",["OVR"],"medium","Visit context (same pattern as Run1 T3). v1.0 had Overall.")
rv("Run3_Positive",5,"FOOD",["STAFF","AMB"],"high","Same pattern as Run1 T6. v1.0 had Overall.")
rv("Run3_Positive",9,"DELIV",["OVR","ACC"],"low","Mixes real takeout evaluations with 're-order' intention; Takeout & delivery only when pickup/delivery/packaging is evaluated.",channel="takeout (partial)")
rv("Run3_Positive",13,"STAFF",["FOOD","AMB"],"high","Staff + food (+ vibe) praise.")
rv("Run3_Positive",16,"NA",["SPEED","AMB"],"low","Visit circumstances (busy night, date night); 'seated right away', 'reserving was simple' -> Service speed, waiting & seating. Two v1.0 rows (Ambience + Overall) merged.")
rv("Run3_Positive",18,"NA",["OVR"],"medium","Visit context ('second visit', 'first time there'); 'every time we come it is fantastic' -> Overall. v1.0 had Overall.")
rv("Run3_Positive",26,"FOOD",["STAFF"],"medium","Breakfast topic; food + service praise.")
rv("Run3_Positive",36,"OVR",[],"low","Rating statements; label the reason's aspect when given (same as Run1 T54). v1.0 had Not applicable.")
rv("Run3_Positive",37,"STAFF",["FOOD"],"medium","Named staff praise at Chaska. v1.0 had Overall.")
rv("Run3_Positive",38,"OVR",[],"medium","Generic 'great place'; some sentences list several aspects -> multi-label at sentence level.")
rv("Run3_Positive",39,"SPEED",["STAFF"],"medium","Mix of speed and generic service praise.")
rv("Run3_Positive",40,"STAFF",["FOOD"],"medium","Staff + food praise.")
rv("Run3_Positive",43,"FOOD",["FRESH"],"medium","'Fresh and flavorful' praise: taste primary, 'fresh' tagged. v1.0 had Freshness as primary.")
rv("Run3_Positive",45,"FOOD",["STAFF","AMB"],"medium","Vietnamese cuisine; sentences also mention the server and music.")
rv("Run3_Positive",48,"CLEAN",["STAFF"],"medium","Clean washrooms + 'great staff' in the same topic.")
rv("Run3_Positive",50,"STAFF",[],"medium","Owners acting as hosts -> Staff & service quality. v1.0 had Other.")
rv("Run3_Positive",51,"FOOD",["FRESH"],"medium","'Cooked to perfection', 'tender' = cooking execution (positive).")
rv("Run3_Positive",58,"FOOD",["STAFF"],"medium","Chef/kitchen praise reflects food quality. v1.0 had Other.")
rv("Run3_Positive",60,"FOOD",["OVR"],"medium","'Everyone loved all of their food' -> Food. v1.0 had Overall.")
rv("Run3_Positive",61,"FOOD",["NA"],"low","Greek/Mediterranean food mixed with 'came from Toronto' context sentences.")
rv("Run3_Positive",62,"FOOD",["FRESH"],"medium","Meat: 'cooked to perfection' / 'overcooked' -> Freshness/cooking.")
rv("Run3_Positive",68,"FOOD",["SPEED"],"high","Drinks/cocktails = Food & drink; 'made the coffee and cocktails so quickly' -> Speed.")
rv("Run3_Positive",70,"MENU",["FOOD"],"medium","Drink selection = Menu variety; drink taste -> Food & drink.")
rv("Run3_Positive",71,"OVR",["FOOD"],"medium","Imperial Tandoor dining-experience topic; aligned with Run1 T79 (v1.0 mapped the two runs inconsistently).")
rv("Run3_Positive",74,"AMB",["FOOD","STAFF"],"medium","Multi-aspect praise.")
rv("Run3_Positive",75,"FOOD",["SPEED"],"high","Sauces; 'wait time was long but worth it' -> Speed.")
rv("Run3_Positive",76,"OVR",[],"low","Competitor comparisons (Osmow's).")
rv("Run3_Positive",77,"AMB",["FOOD"],"medium","Atmosphere + food praise.")
rv("Run3_Positive",79,"SPEED",["STAFF"],"medium","'Friendly and quick' -> Speed + Staff.")
rv("Run3_Positive",85,"FOOD",["STAFF"],"medium","'Best Indian food in Peterborough' = food praise. v1.0 had Overall.")
rv("Run3_Positive",89,"FOOD",["FRESH"],"medium","'Very warm', 'quite dry' -> Freshness/cooking.")
rv("Run3_Positive",92,"FOOD",["PORT"],"medium","Platters; 'servings were huge' -> Portion.")
rv("Run3_Positive",93,"FOOD",["FRESH"],"medium","Tea/chai; 'tea was lukewarm' -> temperature.")
rv("Run3_Positive",97,"AMB",["STAFF"],"high","Atmosphere + service praise in the same sentences.")

# =====================================================================================
# BUILD: topic_to_aspect_mapping_v.1.1.xlsx + sentence-level pilot sample v3
# (content above: ASPECTS, GUIDELINES, R)
# =====================================================================================
import os, re
from pathlib import Path
import numpy as np
import pandas as pd
from openpyxl import load_workbook
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.worksheet.datavalidation import DataValidation
from openpyxl.utils import get_column_letter

BASE = Path(os.environ.get("PTBO_BASE", Path(__file__).resolve().parent.parent))
BT   = BASE / "05. Outputs_BERTopic"
NLP  = BASE / "04. Outputs_NLP"
MAP_IN   = BT / "topic_to_aspect_mapping_v.1.0.xlsx"
MAP_OUT  = BT / "topic_to_aspect_mapping_v.1.1.xlsx"
PILOT_A  = BT / "annotation_pilot_v3_sentence.xlsx"
PILOT_B  = BT / "annotation_pilot_v3_annotator_B.xlsx"
SEED = 42

CODE2NAME = {a[0]: a[1] for a in ASPECTS}
OLD2CODE = {
 "Food taste & overall quality":"FOOD","Freshness, temperature & food condition":"FRESH","Portion size":"PORT",
 "Menu variety":"MENU","Price & value":"PRICE","Staff friendliness & professionalism":"STAFF",
 "Service speed & waiting time":"SPEED","Order accuracy":"ACC","Ambience & noise":"AMB","Cleanliness":"CLEAN",
 "Location, parking & accessibility":"LOC","Delivery & takeout":"DELIV","Dietary accommodation":"DIET",
 "Overall experience, recommendation & return intention":"OVR","Other / business-specific":"OTHER",
 "Not applicable / unclear":"NA"}
RUNS = {"Run1_All":"run1_all","Run2_Negative":"run2_negative","Run3_Positive":"run3_positive"}
RUN_LABEL = {"Run1_All":"Run 1 - all sentences","Run2_Negative":"Run 2 - negative reviews (1-3 stars)","Run3_Positive":"Run 3 - positive reviews (4-5 stars)"}

# ---------------------------------------------------------------- 1. topic table
old = pd.read_excel(MAP_IN, sheet_name="Topic Mapping (filled)")
rows = []
for (run, tid), g in old.groupby(["source_run","topic_id"], sort=False):
    g = g.reset_index(drop=True)
    first = g.iloc[0]
    old_codes = [OLD2CODE[a] for a in g["suggested_aspect"]]
    old_prim, old_sec = old_codes[0], old_codes[1:]
    old_cert = first["aspect_certainty"]
    if (run, tid) in R:
        prim, sec, cert, note, safety, chan = R[(run, tid)]
        reviewed = "revised"
    else:
        prim, sec, cert, note, safety, chan = old_prim, list(old_sec), old_cert, first["mapping_notes"], "none", ""
        reviewed = "kept"
    split = len(g) > 1
    if prim != old_prim:
        ctype = "Remapped (primary aspect changed)"
    elif split:
        ctype = "v1.0 split rows merged"
    elif set(sec) - set(old_sec):
        ctype = "Secondary aspect(s) added"
    elif cert != old_cert:
        ctype = "Certainty changed"
    else:
        ctype = "Unchanged"
    rows.append({
        "source_run": run, "topic_id": int(tid), "topic_keywords": first["topic_keywords"],
        "n_sentences": int(first["n_sentences"]), "prevalence_pct": first["prevalence_pct"],
        "negative_share_pct": first["negative_share_pct"], "positive_share_pct": first["positive_share_pct"],
        "top_peer_group": first["top_peer_group"], "representative_sentences": first["representative_sentences"],
        "aspect_v1_0": " + ".join(CODE2NAME_OLD for CODE2NAME_OLD in g["suggested_aspect"]),
        "certainty_v1_0": old_cert,
        "primary_aspect": CODE2NAME[prim], "secondary_aspects": "; ".join(CODE2NAME[s] for s in sec),
        "multi_aspect_topic": int(len(sec) > 0), "aspect_certainty": cert,
        "food_safety_signal": safety, "service_channel_signal": chan,
        "change_type": ctype, "mapping_notes_v1_1": note, "mapping_notes_v1_0": first["mapping_notes"],
        "_prim": prim, "_sec": sec,
    })
topics = pd.DataFrame(rows)
assert len(topics) == 268, len(topics)
assert topics.duplicated(["source_run","topic_id"]).sum() == 0

# ---------------------------------------------------------------- 2. run-level sentence tables
run_tbl = {r: pd.read_parquet(BT / d / "topics.parquet") for r, d in RUNS.items()}
for r, t in run_tbl.items():
    cnt = t[t.topic != -1].groupby("topic").size()
    m = topics[topics.source_run == r].set_index("topic_id")["n_sentences"]
    bad = (cnt.reindex(m.index) != m).sum()
    assert bad == 0, f"{r}: n_sentences mismatch on {bad} topics"
assert len(run_tbl["Run2_Negative"]) + len(run_tbl["Run3_Positive"]) == len(run_tbl["Run1_All"])
assert not set(run_tbl["Run2_Negative"].sentence_id) & set(run_tbl["Run3_Positive"].sentence_id)

# ---------------------------------------------------------------- 3. summary (per run, no double counting)
summ = []
for code, name, typ, *_ in ASPECTS:
    row = {"aspect": name, "type": typ}
    for r in RUNS:
        tt = topics[topics.source_run == r]
        N = len(run_tbl[r])
        p = tt[tt._prim == code]
        s = tt[tt._sec.apply(lambda x: code in x)]
        k = r.split("_")[0]
        row[f"{k}_topics_primary"] = len(p)
        row[f"{k}_sentences_primary"] = int(p.n_sentences.sum())
        row[f"{k}_pct_of_run"] = round(100 * p.n_sentences.sum() / N, 2)
        row[f"{k}_topics_as_secondary"] = len(s)
    summ.append(row)
summ = pd.DataFrame(summ)
out_row = {"aspect": "Outliers (topic -1, not mapped)", "type": "-"}
tot_row = {"aspect": "TOTAL (= all sentences in the run)", "type": "-"}
for r in RUNS:
    k = r.split("_")[0]; t = run_tbl[r]; N = len(t)
    out_row[f"{k}_topics_primary"] = "-"; out_row[f"{k}_sentences_primary"] = int((t.topic == -1).sum())
    out_row[f"{k}_pct_of_run"] = round(100 * (t.topic == -1).mean(), 2); out_row[f"{k}_topics_as_secondary"] = "-"
    tot_row[f"{k}_topics_primary"] = int((topics.source_run == r).sum()); tot_row[f"{k}_sentences_primary"] = N
    tot_row[f"{k}_pct_of_run"] = round(summ[f"{k}_pct_of_run"].sum() + out_row[f"{k}_pct_of_run"], 2)
    tot_row[f"{k}_topics_as_secondary"] = "-"
summ = pd.concat([summ, pd.DataFrame([out_row, tot_row])], ignore_index=True)
for k in ["Run1","Run2","Run3"]:
    assert abs(summ.iloc[-1][f"{k}_pct_of_run"] - 100) < 0.05, summ.iloc[-1]

# ---------------------------------------------------------------- 4. pilot sample v3 (sentence level)
S = pd.read_parquet(NLP / "review_sentences.parquet")
pool = S[(S.gold_annotation_eligible == 1) & (S.suspicious_duplicate_flag == 0)].copy()
r1 = run_tbl["Run1_All"][["sentence_id","topic"]].rename(columns={"topic":"run1_topic"})
r23 = pd.concat([run_tbl["Run2_Negative"].assign(r="Run2_Negative"), run_tbl["Run3_Positive"].assign(r="Run3_Positive")])
r23 = r23[["sentence_id","topic","r"]].rename(columns={"topic":"run23_topic","r":"run23"})
pool = pool.merge(r1, on="sentence_id", how="left").merge(r23, on="sentence_id", how="left")
tkey = topics.set_index(["source_run","topic_id"])
def topic_info(run, tid):
    if pd.isna(tid) or tid == -1: return None
    return tkey.loc[(run, int(tid))]
prim_set, sec_set, cert_min, multi = [], [], [], []
order = {"low":0,"medium":1,"high":2}
for _, x in pool.iterrows():
    infos = [topic_info("Run1_All", x.run1_topic)]
    if isinstance(x.run23, str): infos.append(topic_info(x.run23, x.run23_topic))
    infos = [i for i in infos if i is not None]
    prim_set.append({i["_prim"] for i in infos}); sec_set.append({s for i in infos for s in i["_sec"]})
    cert_min.append(min([i["aspect_certainty"] for i in infos], key=lambda c: order[c]) if infos else None)
    multi.append(int(any(i["multi_aspect_topic"] for i in infos)))
pool["mapped_primary"] = prim_set; pool["mapped_secondary"] = sec_set
pool["min_topic_certainty"] = cert_min; pool["in_multi_aspect_topic"] = multi
SAFETY_RX = (r"(?i)\b(?:sick|food poisoning|poison|vomit|puk(?:e|ed|ing)|threw up|throw(?:ing)? up|diarrh|dysentery|upset stomach|"
             r"stomach (?:ache|pain|cramp)|parasite|allergic|hairs? (?:in|on)|hair .*food|plastic|bug in|cockroach|insect|"
             r"mou?ldy?|\braw\b|undercooked chicken|rotten|smelled off|expired|health (?:inspector|unit|department|safety))")
pool["safety_keyword_hit"] = pool.sentence_text.str.contains(SAFETY_RX).astype(int)

rng = np.random.default_rng(SEED)
chosen, per_review = [], {}
def take(cands, n, stratum, note=""):
    cands = cands[~cands.sentence_id.isin([c[0] for c in chosen])]
    cands = cands.sample(frac=1, random_state=int(rng.integers(1e9)))
    got = 0
    for _, x in cands.iterrows():
        if got >= n: break
        if per_review.get(x.review_id, 0) >= 2: continue
        chosen.append((x.sentence_id, stratum, note)); per_review[x.review_id] = per_review.get(x.review_id, 0) + 1; got += 1
    return got

log = []
# A. random baseline: 1 per restaurant + 35 random (natural distribution -> unbiased pilot prevalence)
for rid in sorted(pool.restaurant_id.unique()):
    take(pool[pool.restaurant_id == rid], 1, "A_random", "1 per restaurant")
log.append(("A_random", take(pool, 35, "A_random", "uniform random") + pool.restaurant_id.nunique()))
# B. negative oversample (1-3 stars)
log.append(("B_negative_1to3_stars", take(pool[pool.review_stars <= 3], 30, "B_negative_1to3_stars")))
# C. rare aspects (4 each), primary topic mapping first, then secondary
rare = ["CLEAN","ACC","LOC","DIET","DELIV","COMPL","PORT","MENU"]
c_tot = 0
for code in rare:
    g = take(pool[pool.mapped_primary.apply(lambda s: code in s)], 4, "C_rare_aspect", code)
    if g < 4: g += take(pool[pool.mapped_secondary.apply(lambda s: code in s)], 4 - g, "C_rare_aspect", code + " (via secondary)")
    c_tot += g
log.append(("C_rare_aspect", c_tot))
# D. multi-aspect: contrast sentences + sentences from multi-aspect topics
d = take(pool[pool.contains_contrast == 1], 13, "D_multi_aspect", "contrast word")
d += take(pool[(pool.in_multi_aspect_topic == 1) & (pool.min_topic_certainty != "low")], 12, "D_multi_aspect", "multi-aspect topic")
log.append(("D_multi_aspect", d))
# E. ambiguous mappings: sentences in low-certainty topics
log.append(("E_ambiguous_mapping", take(pool[pool.min_topic_certainty == "low"], 20, "E_ambiguous_mapping")))
# F. Run 1 outliers (topic -1): taxonomy coverage never checked here
log.append(("F_bertopic_outlier", take(pool[pool.run1_topic == -1], 20, "F_bertopic_outlier")))
# G. food-safety keyword candidates (keyword hit != confirmed; annotator decides)
log.append(("G_food_safety_candidate", take(pool[pool.safety_keyword_hit == 1], 8, "G_food_safety_candidate")))
# H. very short sentences (<= 3 words) excluded from BERTopic
log.append(("H_short_sentence", take(pool[pool.word_count <= 3], 5, "H_short_sentence")))

ch = pd.DataFrame(chosen, columns=["sentence_id","stratum","stratum_note"])
assert len(ch) == 200 and ch.sentence_id.is_unique, (len(ch), log)
smp = ch.merge(pool, on="sentence_id", how="left")
# context sentences
S_idx = S.set_index(["review_id","sentence_position"])["sentence_text"]
def ctx(rid, pos):
    try: return S_idx.loc[(rid, pos)]
    except KeyError: return ""
smp["previous_sentence"] = [ctx(r, p - 1) for r, p in zip(smp.review_id, smp.sentence_position)]
smp["next_sentence"] = [ctx(r, p + 1) for r, p in zip(smp.review_id, smp.sentence_position)]
# double-annotation subset (20%), stratified
dbl_n = {"A_random":12,"B_negative_1to3_stars":6,"C_rare_aspect":6,"D_multi_aspect":5,"E_ambiguous_mapping":4,"F_bertopic_outlier":4,"G_food_safety_candidate":2,"H_short_sentence":1}
smp["double_annotate"] = 0
for st, n in dbl_n.items():
    idx = smp[smp.stratum == st].sample(n, random_state=SEED).index
    smp.loc[idx, "double_annotate"] = 1
assert smp.double_annotate.sum() == 40
smp = smp.sample(frac=1, random_state=SEED).reset_index(drop=True)
smp["sample_id"] = [f"P{i:03d}" for i in range(1, len(smp) + 1)]

# ---------------------------------------------------------------- 5. Excel helpers
HDR_FILL = PatternFill("solid", start_color="1F3A5F"); HDR_FONT = Font(bold=True, color="FFFFFF", name="Arial", size=10)
BODY = Font(name="Arial", size=10); BOLD = Font(name="Arial", size=10, bold=True)
TITLE = Font(name="Arial", size=14, bold=True, color="1F3A5F")
ANN_FILL = PatternFill("solid", start_color="FFF8E1"); GREY = Font(name="Arial", size=9, color="808080")
CHG_FILL = PatternFill("solid", start_color="FDECEA"); NEW_FILL = PatternFill("solid", start_color="E8F5E9")
thin = Side(style="thin", color="D0D0D0"); BORDER = Border(left=thin, right=thin, top=thin, bottom=thin)
WRAP = Alignment(wrap_text=True, vertical="top")

def style_table(ws, widths, header_row=1, freeze="B2"):
    for c in ws[header_row]:
        c.fill = HDR_FILL; c.font = HDR_FONT; c.alignment = Alignment(wrap_text=True, vertical="center"); c.border = BORDER
    for row in ws.iter_rows(min_row=header_row + 1):
        for c in row:
            c.font = BODY; c.alignment = WRAP; c.border = BORDER
    for i, w in enumerate(widths, 1):
        ws.column_dimensions[get_column_letter(i)].width = w
    ws.freeze_panes = freeze
    ws.auto_filter.ref = ws.dimensions

def write_df(wb, name, df, widths, freeze="B2"):
    ws = wb.create_sheet(name)
    ws.append(list(df.columns))
    for r in df.itertuples(index=False):
        ws.append([None if (isinstance(v, float) and np.isnan(v)) else v for v in r])
    style_table(ws, widths, freeze=freeze)
    return ws

def write_text_sheet(wb, name, title, blocks, width=120):
    ws = wb.create_sheet(name, 0) if name == "README" else wb.create_sheet(name)
    ws["A1"] = title; ws["A1"].font = TITLE
    r = 3
    for head, body in blocks:
        if head:
            ws.cell(r, 1, head).font = BOLD; r += 1
        for line in body:
            c = ws.cell(r, 1, line); c.font = BODY; c.alignment = Alignment(wrap_text=True, vertical="top"); r += 1
        r += 1
    ws.column_dimensions["A"].width = width
    return ws

# ---------------------------------------------------------------- 6. mapping workbook v1.1
from openpyxl import Workbook
wb = Workbook(); wb.remove(wb.active)
ct = topics.change_type.value_counts().to_dict(); cc = topics.aspect_certainty.value_counts().to_dict()
cc0 = topics.certainty_v1_0.value_counts().to_dict()
readme = [
 ("What this file is", [
   "Taxonomy v1.1 and the corrected topic-to-aspect mapping for the 268 BERTopic topics (Run 1 all sentences, Run 2 negative reviews, Run 3 positive reviews).",
   "It replaces topic_to_aspect_mapping_v.1.0.xlsx (kept unchanged next to this file). Built by 05b_taxonomy_v1_1_and_pilot_v3.py.",
   "The mapping is a TOPIC-level hypothesis used to (1) test the taxonomy against what customers actually write, (2) find rare aspects to oversample, and (3) stratify the pilot. It is NOT a set of labels: real labels come from the sentence-level pilot (annotation_pilot_v3_sentence.xlsx)."]),
 ("What changed vs v1.0", [
   f"One row per topic: 268 rows (v1.0 had 272 because 4 multi-aspect topics were duplicated with their full n_sentences each). Multi-aspect topics now use primary_aspect + secondary_aspects.",
   f"Change types: " + "; ".join(f"{k}: {v}" for k, v in ct.items()) + ".",
   f"Certainty v1.0: {cc0}. Certainty v1.1: {cc}. Certainty was re-judged from keywords + 3 representative sentences only (no topic was fully read); 'high' now means keywords and all representative sentences point to one aspect. The pilot is what validates it.",
   "coherence_flag dropped: it was 'ok' for every topic and carried no information.",
   "The 6 issues raised in the external review (Run1 T0, Run1 T87, Run2 T13, Run2 T21, Run2 T44, Run2 T30) are all fixed - see 'Changes vs v1.0'.",
   "Taxonomy: 2 new categories (Complaint handling & service recovery; Reported food-safety concern as a flag), 1 extended (Order & billing accuracy), several renamed with sharper boundaries, and all codebook columns filled in."]),
 ("How to read Aspect Summary", [
   "Each run is summarised separately and runs must NEVER be added: Run 2 + Run 3 = Run 1 exactly (2,733 + 11,570 = 14,303 sentences, no overlap). v1.0's summary added all three runs, so every sentence was counted twice (e.g. Food 7,023 and Overall 6,364 were ~2x inflated).",
   "Only the PRIMARY aspect of each topic is counted, so the column adds up to 100% together with the outlier row. 'topics_as_secondary' shows where an aspect also appears, and is not additive.",
   "The 'missing' 30% / 41% / 26% in v1.0 were the BERTopic outliers (topic -1) of Run 1 / Run 2 / Run 3. Those sentences have never been checked against the taxonomy - the pilot samples 20 of them on purpose.",
   "These are topic-level estimates. Real aspect prevalence, negative rate and rating association are only computed after sentence-level labelling and the ABSA model, aggregated to review_id."]),
 ("Next step", [
   "Annotate annotation_pilot_v3_sentence.xlsx (200 sentences) with the Aspect Taxonomy v1.1 and Annotation guidelines sheets open. Send annotation_pilot_v3_annotator_B.xlsx (40 sentences) to a second annotator. Compute kappa, review disagreements, revise to v1.2."]),
]
write_text_sheet(wb, "README", "Topic-to-aspect mapping v1.1 - Peterborough restaurant reviews", readme)

tm = topics.drop(columns=["_prim","_sec"])
ws = write_df(wb, "Topic Mapping v1.1", tm,
    [14,8,40,9,9,9,9,18,60,30,10,32,40,9,10,11,12,22,60,40], freeze="C2")
col_ct = list(tm.columns).index("change_type") + 1
for r in range(2, ws.max_row + 1):
    v = ws.cell(r, col_ct).value
    if v and v.startswith("Remapped"):
        for c in range(1, ws.max_column + 1): ws.cell(r, c).fill = CHG_FILL

tax = pd.DataFrame([{
    "aspect_name": a[1], "code": a[0], "type": a[2], "change_from_v1_0": a[3], "definition": a[4],
    "include (cues)": a[5], "exclude -> where it goes instead": a[6], "positive_example": a[7],
    "negative_example": a[8], "ambiguous_example -> resolution": a[9], "kpi_linkage": a[10]} for a in ASPECTS])
ws = write_df(wb, "Aspect Taxonomy v1.1", tax, [30,8,9,40,50,45,55,45,45,55,40], freeze="B2")
col_ch = 4
for r in range(2, ws.max_row + 1):
    v = ws.cell(r, col_ch).value or ""
    if v.startswith("NEW"):
        for c in range(1, ws.max_column + 1): ws.cell(r, c).fill = NEW_FILL

gl = pd.DataFrame(GUIDELINES, columns=["rule","guideline"])
write_df(wb, "Annotation guidelines", gl, [24,130], freeze="A2")

ws = write_df(wb, "Aspect Summary", summ, [44,9] + [10,11,10,11] * 3, freeze="C2")
r0 = ws.max_row + 2
for i, line in enumerate([
    "Run 1 = all 14,303 BERTopic sentences. Run 2 (2,733) + Run 3 (11,570) = Run 1. Never sum across runs.",
    "pct_of_run uses ALL sentences in the run as denominator, incl. outliers, so each pct column sums to 100.",
    "Counts are topic-level (each topic counted once, under its primary aspect). They are a guide for sampling, not aspect prevalence."]):
    ws.cell(r0 + i, 1, line).font = GREY

chg = topics[topics.change_type != "Unchanged"][["source_run","topic_id","topic_keywords","n_sentences","aspect_v1_0","primary_aspect","secondary_aspects","certainty_v1_0","aspect_certainty","change_type","mapping_notes_v1_1"]]
chg = chg.sort_values(["change_type","source_run","topic_id"])
write_df(wb, "Changes vs v1.0", chg, [14,8,40,9,32,32,40,10,10,26,70], freeze="C2")
wb.save(MAP_OUT)

# ---------------------------------------------------------------- 7. pilot workbooks
ANN_COLS = ["sample_id","sentence_text","previous_sentence","next_sentence",
            "aspect_1","sentiment_1","evidence_1","aspect_2","sentiment_2","evidence_2","aspect_3","sentiment_3","evidence_3",
            "service_channel","food_safety_flag","ambiguity_flag","annotator_notes","sentence_id"]
LISTS = {"aspects":[a[1] for a in ASPECTS], "sentiment":["Positive","Negative","Neutral","Mixed"],
         "channel":["dine_in","takeout","delivery","unknown"], "flag":[0,1]}

def add_lists(wb):
    ws = wb.create_sheet("Lists")
    for j, (k, vals) in enumerate(LISTS.items(), 1):
        ws.cell(1, j, k)
        for i, v in enumerate(vals, 2): ws.cell(i, j, v)
    ws.sheet_state = "hidden"

def ann_sheet(wb, df, name):
    ws = wb.create_sheet(name)
    ws.append(ANN_COLS)
    for r in df.itertuples(index=False):
        d = r._asdict()
        ws.append([d["sample_id"], d["sentence_text"], d["previous_sentence"], d["next_sentence"]] + [None] * 13 + [d["sentence_id"]])
    style_table(ws, [9,60,35,35,30,11,28,30,11,28,30,11,28,12,9,9,35,18], freeze="C2")
    n = ws.max_row
    for col in range(5, 17):
        for r in range(2, n + 1): ws.cell(r, col).fill = ANN_FILL
    for r in range(2, n + 1): ws.cell(r, 18).font = GREY
    def dv(formula, cols):
        v = DataValidation(type="list", formula1=formula, allow_blank=True, showErrorMessage=True)
        ws.add_data_validation(v)
        for c in cols: v.add(f"{c}2:{c}{n}")
    dv(f"=Lists!$A$2:$A${len(LISTS['aspects'])+1}", ["E","H","K"])
    dv("=Lists!$B$2:$B$5", ["F","I","L"])
    dv("=Lists!$C$2:$C$5", ["N"])
    dv("=Lists!$D$2:$D$3", ["O","P"])
    return ws

quick = pd.DataFrame([{"aspect": a[1], "type": a[2], "definition": a[4], "goes elsewhere": a[6]} for a in ASPECTS])
def common_sheets(wb):
    write_df(wb, "Aspect quick reference", quick, [34,9,70,80], freeze="B2")
    write_df(wb, "Annotation guidelines", gl, [24,130], freeze="A2")
    add_lists(wb)

how = [
 ("How to annotate (5 minutes to read)", [
   "1. Read sentence_text. previous_sentence / next_sentence are context only.",
   "2. For each aspect the sentence evaluates, fill aspect_n (dropdown), sentiment_n and evidence_n (exact words copied from the sentence). Up to 3 aspects.",
   "3. No evaluation at all -> aspect_1 = 'Not applicable / context only', leave sentiment empty.",
   "4. service_channel: dine_in / takeout / delivery / unknown. food_safety_flag: 1 for customer-reported illness, foreign objects, allergic reactions, raw/spoiled food.",
   "5. ambiguity_flag = 1 whenever you hesitated; say why in annotator_notes.",
   "Star ratings, restaurant names and the expected aspect are hidden on purpose so they cannot steer the labels.",
   "Rules and examples: 'Annotation guidelines' and 'Aspect quick reference' sheets; full codebook in topic_to_aspect_mapping_v.1.1.xlsx -> 'Aspect Taxonomy v1.1'."]),
]
# A (master)
wbA = Workbook(); wbA.remove(wbA.active)
strat_counts = smp.stratum.value_counts().reindex([s for s, _ in log]).to_dict()
design_note = [
 ("Sample design (200 sentences, seed 42)", [f"{k}: {v}" for k, v in strat_counts.items()] + [
   "Max 2 sentences per review; all 25 restaurants covered (stratum A takes 1 per restaurant first).",
   "Pool: review_sentences.parquet with gold_annotation_eligible = 1 and suspicious_duplicate_flag = 0 (16,419 sentences).",
   "40 sentences (20%, stratified) are marked double_annotate = 1 and copied to annotation_pilot_v3_annotator_B.xlsx.",
   "Stratum A (60) is the only part that estimates natural prevalence; strata B-H are deliberate oversamples to stress-test the codebook."]),
]
write_text_sheet(wbA, "README", "Pilot annotation v3 - sentence level (Annotator A)", how + design_note)
ann_sheet(wbA, smp, "Annotate")
common_sheets(wbA)
design = smp[["sample_id","sentence_id","review_id","restaurant_id","restaurant_name","review_stars","operational_peer_group",
              "cuisine_cluster","word_count","contains_contrast","stratum","stratum_note","double_annotate","run1_topic","run23",
              "run23_topic","mapped_primary","mapped_secondary","min_topic_certainty","safety_keyword_hit"]].copy()
for c in ["mapped_primary","mapped_secondary"]:
    design[c] = design[c].apply(lambda s: "; ".join(CODE2NAME[x] for x in sorted(s)) if s else "")
ws = write_df(wbA, "Sample design (open AFTER)", design, [9,18,18,10,24,7,22,16,7,7,22,22,8,8,14,8,40,40,10,8], freeze="C2")
ws.sheet_properties.tabColor = "999999"
wbA.save(PILOT_A)
# B (double-annotation subset, no design info)
wbB = Workbook(); wbB.remove(wbB.active)
write_text_sheet(wbB, "README", "Pilot annotation v3 - sentence level (Annotator B, 40 sentences)", how + [
 ("Important", ["Label independently - do not discuss sentences with Annotator A until both files are finished. The 40 sentences are a subset of A's 200, same sample_id."])])
ann_sheet(wbB, smp[smp.double_annotate == 1].sort_values("sample_id"), "Annotate")
common_sheets(wbB)
wbB.save(PILOT_B)

print("mapping:", MAP_OUT.name, "| topics", len(topics), "| change types", ct, "| certainty", cc)
print("pilot:", dict(log), "| restaurants", smp.restaurant_id.nunique(), "| per-rest min", smp.restaurant_id.value_counts().min())
print("stars in pilot:", smp.review_stars.value_counts().sort_index().to_dict())
print(summ[["aspect","Run1_pct_of_run","Run2_pct_of_run","Run3_pct_of_run"]].to_string())
