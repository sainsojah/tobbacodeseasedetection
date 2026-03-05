"""
Disease clarification questions for similar-looking diseases
"""
DISEASE_CLARIFICATIONS = {
    "Black Spot": {
        "similar_to": ["Leaf Spot", "Septoria Blight"],
        "questions": [
            {
                "question": "Are the spots perfectly round with defined edges?",
                "yes": "Likely Black Spot",
                "no": "May be another leaf spot disease"
            },
            {
                "question": "Do spots have yellow halos around them?",
                "yes": "Classic Black Spot symptom",
                "no": "Consider other options"
            }
        ]
    },
    "Early Blight": {
        "similar_to": ["Septoria Blight", "Leaf Spot"],
        "questions": [
            {
                "question": "Do spots have concentric rings (like a target)?",
                "yes": "Classic Early Blight symptom",
                "no": "Likely not Early Blight"
            },
            {
                "question": "Are spots mostly on lower, older leaves?",
                "yes": "Consistent with Early Blight",
                "no": "May be another disease"
            }
        ]
    },
    "Late Blight": {
        "similar_to": ["Early Blight", "Leaf Mold"],
        "questions": [
            {
                "question": "Is there white fuzzy growth on leaf undersides?",
                "yes": "Classic Late Blight in humid conditions",
                "no": "Likely not Late Blight"
            },
            {
                "question": "Are lesions water-soaked and spreading rapidly?",
                "yes": "Typical of Late Blight",
                "no": "Consider other diseases"
            }
        ]
    },
    "Powdery Mildew": {
        "similar_to": ["Leaf Mold"],
        "questions": [
            {
                "question": "Is there white powdery coating on leaf surface?",
                "yes": "Classic Powdery Mildew",
                "no": "May be Leaf Mold"
            },
            {
                "question": "Does powder wipe off easily?",
                "yes": "Definitely Powdery Mildew",
                "no": "Consider other options"
            }
        ]
    },
    "Spider Mites": {
        "similar_to": ["Nutrient Deficiency", "Yellow Leaf Spot"],
        "questions": [
            {
                "question": "Do you see fine webbing on the leaves?",
                "yes": "Definitely Spider Mites",
                "no": "May be nutrient issue"
            },
            {
                "question": "Are there tiny moving specks on leaf undersides?",
                "yes": "Spider Mites confirmed",
                "no": "Check for other causes"
            }
        ]
    },
    "Fusarium_Black_Shank_Complex": {
        "name": "Fusarium + Black Shank Complex",
        "description": "Combined soil-borne diseases attacking vascular system",
        "symptoms": "Severe wilting, black stem lesions, yellowing on one side, plant death",
        "questions": [
            {
                "question": "Is yellowing only on one side of the plant?",
                "yes": "Suggests Fusarium involvement",
                "no": "May be pure Black Shank"
            },
            {
                "question": "Are roots black and rotten?",
                "yes": "Both diseases present",
                "no": "Check soil conditions"
            }
        ],
        "recommendation": "• Remove and destroy infected plants\n• Long-term rotation (5+ years)\n• Use resistant varieties\n• Improve soil drainage\n• Consider soil solarization\n• Apply registered fungicides"
    }
}