"""
Complete treatment database for all tobacco diseases
Based on your trained model classes
"""
TREATMENTS = {
    "Black Spot": {
        "severity": "Moderate",
        "symptoms": "Black circular spots on leaves, usually starting on lower leaves. Spots may have yellow halos.",
        "causes": "Fungal infection - Cercospora nicotianae. Spreads by wind and rain splash.",
        "prevention": "• Use disease-free seed\n• Practice crop rotation (3 years)\n• Avoid overhead irrigation\n• Maintain proper plant spacing",
        "action": "• Remove and destroy infected lower leaves\n• Apply copper-based fungicides\n• Improve air circulation in field",
        "chemicals": ["Mancozeb", "Copper oxychloride", "Chlorothalonil"],
        "organic": ["Neem oil", "Baking soda solution", "Compost tea"]
    },
    "Black Shank": {
        "severity": "High",
        "symptoms": "Black lesions on stem base, wilting even when soil is moist, root rot, stunted plants. Plants collapse and die.",
        "causes": "Soil-borne fungus (Phytophthora parasitica var. nicotianae). Thrives in wet conditions.",
        "prevention": "• Use resistant varieties (e.g., K326, NC71)\n• Ensure well-drained soils\n• Avoid over-irrigation\n• Long crop rotation (4+ years)",
        "action": "• Remove and destroy infected plants immediately\n• Apply recommended fungicides\n• Improve field drainage\n• Solarize soil in hot season",
        "chemicals": ["Ridomil Gold", "Mefenoxam", "Metalaxyl"],
        "organic": ["Trichoderma species", "Crop rotation with marigolds"]
    },
    "Early Blight": {
        "severity": "Moderate",
        "symptoms": "Target-like spots with concentric rings on lower leaves. Yellowing around spots. Leaves wither and drop.",
        "causes": "Fungus (Alternaria solani). Common in warm, humid conditions.",
        "prevention": "• Maintain proper plant spacing\n• Mulch to reduce soil splash\n• Avoid overhead irrigation\n• Remove crop debris after harvest",
        "action": "• Remove infected leaves promptly\n• Apply fungicides preventatively\n• Rotate with non-host crops (cereals)",
        "chemicals": ["Dithane M-45", "Mancozeb", "Azoxystrobin"],
        "organic": ["Copper fungicides", "Bacillus subtilis"]
    },
    "Late Blight": {
        "severity": "High",
        "symptoms": "Water-soaked lesions on leaves, white fungal growth on undersides in humid conditions. Rapid leaf death. Dark brown spots on stems.",
        "causes": "Fungus-like organism (Phytophthora infestans). Spreads rapidly in cool, wet weather.",
        "prevention": "• Avoid excessive moisture\n• Scout fields daily in wet weather\n• Use disease-free transplants\n• Destroy volunteer plants",
        "action": "• Remove and destroy infected plants immediately\n• Apply protectant fungicides\n• Improve air circulation\n• Harvest early if possible",
        "chemicals": ["Ridomil Gold", "Curzate", "Mancozeb", "Chlorothalonil"],
        "organic": ["Copper hydroxide", "Copper sulfate"]
    },
    "Leaf Mold": {
        "severity": "Moderate",
        "symptoms": "Pale green or yellow spots on upper leaf surface, olive-green to gray-purple mold on underside. Leaves turn brown and curl.",
        "causes": "Fungus (Passalora fulva). Thrives in high humidity and poor air circulation.",
        "prevention": "• Reduce humidity\n• Improve ventilation\n• Space plants properly\n• Avoid overhead irrigation",
        "action": "• Remove affected leaves immediately\n• Apply sulfur-based fungicides\n• Avoid working in wet fields\n• Reduce nitrogen fertilization",
        "chemicals": ["Sulfur", "Chlorothalonil", "Copper fungicides"],
        "organic": ["Potassium bicarbonate", "Neem oil"]
    },
    "Leaf Spot": {
        "severity": "Low to Moderate",
        "symptoms": "Small circular spots with defined margins, may have yellow halos. Spots may merge in severe cases.",
        "causes": "Various fungal pathogens. Common in humid conditions.",
        "prevention": "• Proper spacing for air circulation\n• Avoid wetting leaves when irrigating\n• Remove crop debris\n• Rotate crops",
        "action": "• Remove infected leaves\n• Apply copper-based fungicides\n• Improve field sanitation",
        "chemicals": ["Copper oxychloride", "Mancozeb"],
        "organic": ["Compost tea", "Baking soda spray"]
    },
    "Powdery Mildew": {
        "severity": "Low to Moderate",
        "symptoms": "White powdery growth on leaf surfaces, starting on lower leaves. Leaves may yellow and distort.",
        "causes": "Fungus (Erysiphe cichoracearum). Favors dry days, humid nights.",
        "prevention": "• Plant resistant varieties\n• Avoid overcrowding\n• Maintain good air flow\n• Avoid high nitrogen fertilizer",
        "action": "• Apply sulfur-based fungicides\n• Remove severely infected leaves\n• Improve air circulation\n• Water at base of plants",
        "chemicals": ["Sulfur", "Potassium bicarbonate", "Myclobutanil"],
        "organic": ["Milk spray (1:9 ratio)", "Baking soda solution", "Neem oil"]
    },
    "Septoria Blight": {
        "severity": "Moderate",
        "symptoms": "Small water-soaked spots that turn gray or tan with dark brown borders. Black dots (pycnidia) in center of spots.",
        "causes": "Fungus (Septoria species). Spreads by rain splash and tools.",
        "prevention": "• Crop rotation (2-3 years)\n• Avoid overhead irrigation\n• Remove crop debris\n• Stake plants for air flow",
        "action": "• Remove infected lower leaves\n• Apply protectant fungicides\n• Improve air circulation\n• Mulch to prevent soil splash",
        "chemicals": ["Chlorothalonil", "Mancozeb", "Copper fungicides"],
        "organic": ["Copper soap", "Garlic spray"]
    },
    "Tobacco Cillium Virus": {
        "severity": "High",
        "symptoms": "Mottled light and dark green pattern on leaves (mosaic). Leaf distortion, stunting, yellowing veins.",
        "causes": "Tobacco Mosaic Virus (TMV). Highly contagious through contact.",
        "prevention": "• Use resistant varieties\n• Wash hands with milk or soap before handling\n• No smoking near plants\n• Disinfect tools with bleach",
        "action": "• NO CURE - Remove and destroy infected plants immediately\n• Disinfect tools and hands after handling\n• Control weeds that may harbor virus\n• Roguing is critical",
        "chemicals": ["No chemical cure - prevention only"],
        "organic": ["Milk spray (may reduce spread)", "Remove infected plants"]
    },
    "Tobacco Cillium TMDL": {
        "severity": "High",
        "symptoms": "Severe mosaic patterns, leaf distortion, stunting, vein clearing. Plants may be completely unproductive.",
        "causes": "Likely severe viral strain or mixed infection",
        "prevention": "• Use certified virus-free seed\n• Control insect vectors\n• Remove infected plants immediately\n• Disinfect tools",
        "action": "• Remove and destroy infected plants\n• Consult agricultural officer\n• Long crop rotation\n• Avoid planting near infected fields",
        "chemicals": ["No chemical cure available"],
        "organic": ["Remove plants", "Solarize soil"]
    },
    "Yellow Leaf Spot": {
        "severity": "Low to Moderate",
        "symptoms": "Yellow spots on leaves that may turn brown with age. General yellowing of leaf tissue.",
        "causes": "May be fungal infection or nutrient deficiency",
        "prevention": "• Balanced fertilization\n• Proper irrigation\n• Field sanitation\n• Regular soil testing",
        "action": "• Remove affected leaves\n• Apply copper-based treatments\n• Monitor spread\n• Test soil nutrients",
        "chemicals": ["Copper fungicides", "Mancozeb"],
        "organic": ["Compost tea", "Fish emulsion"]
    },
    "from Yellow Leaf Spot": {
        "severity": "Low",
        "symptoms": "Yellow discoloration, possible nutrient deficiency symptoms. Similar to Yellow Leaf Spot.",
        "causes": "May be duplicate class - refer to Yellow Leaf Spot treatment",
        "prevention": "• Regular soil testing\n• Balanced nutrition\n• Proper pH management (5.5-6.5)",
        "action": "• Check soil nutrients\n• Apply balanced fertilizer\n• Monitor progression\n• Consider tissue testing",
        "chemicals": ["Foliar feed if nutrient deficiency"],
        "organic": ["Compost", "Manure tea"]
    },
    "Spider Mites": {
        "severity": "Moderate",
        "symptoms": "Tiny yellow/white specks on leaves (stippling). Fine webbing on leaf undersides. Leaves turn yellow, then bronze.",
        "causes": "Spider mites (Tetranychus species) - tiny arachnids. Thrive in hot, dry conditions.",
        "prevention": "• Maintain humidity\n• Avoid water stress\n• Scout regularly, especially undersides\n• Encourage beneficial insects",
        "action": "• Apply miticides\n• Use insecticidal soap\n• Introduce predatory mites\n• Spray water to dislodge",
        "chemicals": ["Abamectin", "Bifenazate", "Insecticidal soap"],
        "organic": ["Neem oil", "Predatory mites", "Garlic spray"]
    },
    "Healthy": {
        "severity": "None",
        "symptoms": "Green, uniform leaves with no spots, discoloration, or deformities. Healthy plant growth.",
        "causes": "Good farming practices!",
        "prevention": "• Continue good practices\n• Regular monitoring\n• Balanced fertilization\n• Proper irrigation schedule",
        "action": "• Great job! Keep up the good work\n• Continue prevention measures\n• Monitor regularly for early signs\n• Maintain field records",
        "chemicals": ["No treatment needed"],
        "organic": ["Continue organic practices"]
    }
}