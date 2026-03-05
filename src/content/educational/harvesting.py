"""
Complete tobacco harvesting guide
"""
HARVESTING_GUIDE = {
    "en": """🌾 *TOBACCO HARVESTING GUIDE*

*🌿 PRIMING METHOD*

*What is priming?*
Harvesting leaves from bottom upward as they ripen

*Number of primings:*
• 4-6 primings per season
• 2-3 leaves per priming
• 7-14 days between primings

*Priming sequence:*
1. Priming 1 (Lugs): Bottom leaves
2. Priming 2-3 (Cutters): Lower middle
3. Priming 4-5 (Leaf): Upper middle
4. Priming 6 (Tips): Top leaves

*✅ LEAF RIPENESS INDICATORS*

*Visual signs:*
• Color: Light green to yellow-green
• Tips: Slightly curved down
• Spots: Small yellow patches appear
• Surface: Slightly bumpy (crocodile skin)

*Physical signs:*
• Texture: Slightly sticky (gum)
• Midrib: Snaps cleanly (not stringy)
• Leaves: Come off easily with upward pull
• Sound: Slight crack when bent

*Chemical signs:*
• Starch: Converting to sugar
• Nicotine: At peak levels
• Moisture: 80-85%

*📋 PRIMING SCHEDULE*

*Priming 1 (Lugs): 60-65 days after transplant*
• Remove 2-3 bottom leaves
• Often sandy or damaged
• Lowest quality but valuable

*Priming 2 (Cutters): 70-75 days after transplant*
• Next 2-3 leaves
• Medium body and flavor
• Good for blending

*Priming 3 (Leaf): 80-85 days after transplant*
• Middle leaves
• Best quality
• Ideal thickness

*Priming 4 (Upper Leaf): 90-95 days after transplant*
• Upper middle
• Full body
• Strong flavor

*Priming 5 (Tips): 100-120 days after transplant*
• Top 3-4 leaves
• Small but potent
• Highest nicotine

*⏰ BEST TIME TO HARVEST*

*Morning harvest:*
• 8:00 AM - 11:00 AM
• Leaves crisp and turgid
• Easy to handle
• Less shattering

*Evening harvest:*
• 3:00 PM - 5:00 PM
• Leaves drier
• Ready for barn
• Good for flue-curing

*NEVER harvest:*
• In rain or early morning dew ❌
• During midday heat ❌
• When leaves are wet ❌
• During disease outbreaks ❌

*👐 HARVESTING TECHNIQUE*

*Step-by-step:*
1. Walk between rows
2. Select ripe leaves only
3. Hold stem near base
4. Pull downward and outward
5. Clean snap sound = perfect
6. Place carefully in basket

*Common mistakes:*
• Pulling too hard (damages stalk)
• Harvesting unripe leaves (poor quality)
• Bruising leaves (reduces value)
• Mixing grades in basket

*📦 HANDLING AFTER HARVEST*

*Immediate care:*
• Keep leaves in shade
• Don't overcrowd baskets
• Transport within 2-4 hours
• Handle by stem only

*Transport to barn:*
• Stack carefully
• Avoid compression
• Cover from sun
• Quick transport

*Grading in field:*
• Separate by position
• Remove damaged leaves
• Keep clean and dry
• Consistent sizes together

*🔥 CURING PREPARATION*

*Before barn loading:*
• Sort by maturity
• Remove trash
• Check for diseases
• Plan barn loading

*Barn loading tips:*
• Tie leaves on sticks
• Space evenly
• Dense at bottom
• Looser at top

*Curing schedule (flue-cured):*

*Yellowing (0-48 hours):*
• Temp: 32-38°C
• Humidity: 85-90%
• Goal: Leaves turn yellow

*Leaf drying (48-96 hours):*
• Temp: 38-52°C
• Humidity: 70-80%
• Goal: Lamina dries

*Midrib drying (96-120 hours):*
• Temp: 52-60°C
• Humidity: 50-60%
• Goal: Stems dry

*Killing out (120+ hours):*
• Temp: 60-71°C
• Humidity: 30-40%
• Goal: Sterilize, fix color

*📊 QUALITY INDICATORS*

*Grade A (Premium):*
• Large leaves
• Uniform color
• No spots
• Elastic texture

*Grade B (Good):*
• Medium leaves
• Good color
• Minor blemishes
• Acceptable texture

*Grade C (Fair):*
• Small leaves
• Off-color
• Some damage
• Acceptable for blending

*Grade D (Low):*
• Damaged leaves
• Poor color
• Trashy
• Local use only

*⚠️ PROBLEMS TO AVOID*

*Green tobacco:*
• Harvested too early
• Won't cure properly
• Harsh smoke

*Spotted tobacco:*
• Disease in field
• Reduces grade
• Poor appearance

*Mouldy tobacco:*
• Barn too humid
• Poor air circulation
• Worthless

*Scalded tobacco:*
• Temperature too high
• Brown/black leaves
• Burnt smell

*📋 HARVEST CHECKLIST*

✅ Check ripeness daily
✅ Prepare baskets/racks
✅ Organize transport
✅ Barn ready and clean
✅ Weather forecast checked
✅ Workers trained
✅ Grading area ready

*Reply 0 for Main Menu | 9 for Previous*"""
}

def get_harvesting_guide(lang="en"):
    """Get harvesting guide in specified language"""
    return HARVESTING_GUIDE.get(lang, HARVESTING_GUIDE["en"])