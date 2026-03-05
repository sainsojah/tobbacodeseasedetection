"""
Complete tobacco planting guide
"""
PLANTING_GUIDE = {
    "en": """🌱 *COMPLETE TOBACCO PLANTING GUIDE*

*📅 TIMELINE*
• Nursery: 6-8 weeks before transplanting
• Transplanting: When seedlings are pencil-thick
• Growth period: 60-90 days to harvest

*🏡 NURSERY PREPARATION*
Bed size: 1m wide x 10m long (for 1 hectare)
Raised beds: 15-20cm high

*Soil Sterilization Methods:*
🔥 Solarization: Cover with clear plastic for 4-6 weeks
🔥 Burning: Traditional method with wood
🧪 Chemical: Basamid (apply 4 weeks before sowing)

*Sowing:*
• Mix seeds with fine sand (1:50 ratio)
• Sow evenly on bed surface
• Cover lightly with straw or shade cloth
• Water gently with fine spray

*💧 SEEDLING MANAGEMENT*

*Weeks 1-2:*
• Water twice daily (morning and evening)
• Keep bed moist but not waterlogged
• Remove shade cloth after germination

*Weeks 3-4:*
• Apply starter fertilizer (2:3:2 at 25g/m²)
• Thin seedlings to 5cm apart
• Control weeds manually
• Watch for damping off

*Weeks 5-6:*
• Reduce watering (harden seedlings)
• Expose to full sun gradually
• Apply foliar feed if needed
• Prepare for transplanting

*🌍 FIELD PREPARATION*

*Land preparation:*
1. Plough deeply (25-30cm) - 4 weeks before
2. Harrow to fine tilth - 2 weeks before
3. Mark rows at 1.1-1.2m spacing
4. Open planting furrows

*Fertilizer application:*
• Basal: Compound L (5:14:7) at 400-600 kg/ha
• Apply in furrow and mix with soil
• Never place fertilizer directly under plant

*Plant population:*
• Target: 15,000 plants per hectare
• Between plants: 50-60cm
• Between ridges: 1.1-1.2m

*🌿 TRANSPLANTING*

*When to transplant:*
✓ Seedlings 15-20cm tall
✓ Pencil-thick stem
✓ 5-6 true leaves
✓ Well-developed roots

*How to transplant:*
1. Water nursery thoroughly night before
2. Lift seedlings carefully with roots
3. Transplant in late afternoon
4. Plant at same depth as nursery
5. Firm soil around roots
6. Water immediately

*Post-transplant care:*
• Gap filling within 7-10 days
• First irrigation within 24 hours
• Weed control from day one
• Scout for cutworms

*🚿 INITIAL IRRIGATION*

*First week:*
• Day 1-3: Daily light irrigation
• Day 4-7: Every 2 days
• Amount: 200-300ml per plant

*Establishment check:*
• 90%+ survival rate = good
• 80-90% = acceptable
• Below 80% = gap fill immediately

*🐛 PEST SCOUTING*

*Watch for:*
• Cutworms (at base of seedlings)
• Aphids (on growing points)
• Leaf miners (tunnels in leaves)
• Wireworms (in soil)

*Action thresholds:*
• Cutworms: 5% damage = treat
• Aphids: 10% infestation = treat
• Leaf miners: Monitor only initially

*📋 PLANTING CHECKLIST*

✅ Nursery beds prepared
✅ Seeds sown at right time
✅ Seedlings hardened
✅ Land prepared and fertilized
✅ Irrigation ready
✅ Gapping material ready
✅ Scouting schedule planned

*❌ COMMON MISTAKES*

• Planting too deep (causes stem rot)
• Planting too shallow (plants fall over)
• Watering at midday (leaf burn)
• Overcrowding (disease risk)
• Late gap filling (uneven crop)

*Reply 0 for Main Menu | 9 for Previous*"""
}

def get_planting_guide(lang="en"):
    """Get planting guide in specified language"""
    return PLANTING_GUIDE.get(lang, PLANTING_GUIDE["en"])