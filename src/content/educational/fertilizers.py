"""
Complete fertilizer application guide
"""
FERTILIZER_GUIDE = {
    "en": """🧪 *TOBACCO FERTILIZER GUIDE*

*📊 NUTRIENT REQUIREMENTS*

*Macronutrients per hectare:*
Nitrogen (N): 80-120 kg
Phosphorus (P): 40-60 kg
Potassium (K): 120-180 kg

*Secondary nutrients:*
Calcium (Ca): Important for cell walls
Magnesium (Mg): Essential for chlorophyll
Sulfur (S): Needed for protein formation

*Micronutrients:*
Boron (B): Critical for growing points
Zinc (Zn): Needed for hormone production
Manganese (Mn): Enzyme activation

*🌱 BASAL APPLICATION (Pre-planting)*

*Compound L (5:14:7): 400-600 kg/ha*

*Application method:*
1. Open planting furrows (15cm deep)
2. Apply fertilizer evenly in furrow
3. Mix thoroughly with soil
4. Cover with 5cm soil before planting

*Timing:*
• Apply 1-2 weeks before transplanting
• Allow rain to dissolve fertilizer
• Never plant directly into fertilizer

*🚀 TOP DRESSING 1 (4-6 weeks after planting)*

*Ammonium Nitrate (34.5% N): 150-200 kg/ha*

*When to apply:*
✓ Plants knee-high (30-40cm)
✓ 4-5 weeks after transplanting
✓ After first weeding
✓ When soil is moist

*Application method:*
• Place 15-20cm from plant stem
• Make 5cm deep holes
• Apply fertilizer and cover
• Water if no rain within 2 days

*⚡ TOP DRESSING 2 (8-10 weeks after planting)*

*Potassium Nitrate (13-0-46): 100-150 kg/ha*

*When to apply:*
✓ Just before flowering
✓ 8-10 weeks after transplanting
✓ When leaves are expanding
✓ For better leaf quality

*Benefits:*
• Improves leaf thickness
• Enhances burn quality
• Increases disease resistance
• Better curing properties

*🧪 SOIL TESTING*

*When to test:*
• Before first planting
• Every 2-3 years
• When problems appear
• After crop rotation

*What to test:*
• pH (target: 5.5-6.5)
• Organic matter (>2%)
• Available P, K, Ca, Mg
• Cation exchange capacity

*Interpreting results:*
• Low pH (<5.5): Add lime
• High pH (>7.0): Add sulfur
• Low P: Increase basal
• Low K: Increase top dressing

*🌿 FOLIAR FEEDING*

*When needed:*
• Deficiency symptoms appear
• Stress conditions
• Rapid growth phase
• Root problems

*Common foliar sprays:*
• Urea (0.5% solution)
• Potassium nitrate (1% solution)
• Multi-nutrient mixes
• Seaweed extract

*Application tips:*
• Spray early morning
• Avoid hot sunny days
• Use fine spray
• Wet both leaf surfaces

*⚠️ DEFICIENCY SYMPTOMS*

*Nitrogen deficiency:*
• Pale green leaves
• Stunted growth
• Lower leaves yellow

*Phosphorus deficiency:*
• Dark green leaves
• Purple undersides
• Slow growth

*Potassium deficiency:*
• Yellow leaf edges
• Brown scorching
• Weak stalks

*Calcium deficiency:*
• New leaves distorted
• Growing point dies
• Poor root growth

*📋 FERTILIZER SCHEDULE*

*Weeks after transplant:*

*Week 0-1:*
• Starter solution (optional)
• Low concentration
• Boost establishment

*Week 4-6:*
• Top dressing 1 (AN)
• 150-200 kg/ha
• After weeding

*Week 8-10:*
• Top dressing 2 (KNO3)
• 100-150 kg/ha
• Before flowering

*Week 12+:*
• Foliar if needed
• Based on symptoms
• Until topping

*🌧️ WEATHER CONSIDERATIONS*

*Apply fertilizer when:*
• Soil is moist
• Rain expected within 2 days
• Not during drought
• Not before heavy rain (leaching)

*Withhold fertilizer if:*
• Severe drought
• Waterlogged soil
• Disease outbreak
• Approaching harvest

*Reply 0 for Main Menu | 9 for Previous*"""
}

def get_fertilizer_guide(lang="en"):
    """Get fertilizer guide in specified language"""
    return FERTILIZER_GUIDE.get(lang, FERTILIZER_GUIDE["en"])