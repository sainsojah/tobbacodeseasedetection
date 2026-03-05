"""
Professional Response Builder
Ensures consistent formatting across all bot messages.
"""

import textwrap
from src.core.constants import (
    CONFIDENCE_REJECT,
    CONFIDENCE_MODERATE,
    SYSTEM_MESSAGES
)


class ResponseBuilder:
    BRAND_HEADER = "🌿 *Tobacco AI Assistant*"
    DIVIDER = "---"

    # ==========================================================
    # BASE FORMATTER
    # ==========================================================

    @classmethod
    def build(cls, body: str, show_main=True, show_previous=False):
        """
        Wraps content with header and optional navigation.
        """
        message = f"{cls.BRAND_HEADER}\n\n{body}"

        nav = []
        if show_main:
            nav.append("0️⃣ Main Menu")
        if show_previous:
            nav.append("9️⃣ Previous")

        if nav:
            message += f"\n\n{cls.DIVIDER}\n{'  |  '.join(nav)}"

        return message

    # ==========================================================
    # DETECTION RESULT
    # ==========================================================

    @classmethod
    def detection_result(cls, disease, confidence, treatment, user_name):
        """
        Formats AI detection results professionally.
        Confidence expected as FLOAT (0.0 - 1.0)
        """

        confidence_percent = confidence * 100

        # Determine confidence level
        if confidence < CONFIDENCE_REJECT:
            return cls.build(
                SYSTEM_MESSAGES["rejected"],
                show_main=True
            )

        if confidence < CONFIDENCE_MODERATE:
            conf_emoji = "⚠️"
            confidence_note = SYSTEM_MESSAGES["low_confidence"]
        else:
            conf_emoji = "✅"
            confidence_note = None

        lines = [
            "📊 *Disease Detection Result*",
            "",
            f"👤 *Farmer:* {user_name}",
            f"{conf_emoji} *Diagnosis:* {disease}",
            f"📈 *Confidence:* {confidence_percent:.1f}%",
            ""
        ]

        if confidence_note:
            lines.append(confidence_note)
            lines.append("")

        # Healthy case
        if disease.lower() == "healthy":
            lines.extend([
                "🎉 *Good news!* Your crop appears healthy.",
                "",
                "📋 *Prevention Tips:*",
                "• Continue regular monitoring",
                "• Maintain proper irrigation",
                "• Follow fertilization schedule",
                "• Remove nearby infected plants"
            ])

        else:
            lines.extend([
                f"⚠️ *Severity:* {treatment.get('severity', 'Unknown')}",
                "",
                "🔍 *Symptoms:*",
                textwrap.fill(
                    treatment.get("symptoms", "Not available."),
                    width=60
                ),
                "",
                "🛠️ *Recommended Action:*"
            ])

            actions = treatment.get("action", "").split("\n")
            for action in actions:
                action = action.strip()
                if action:
                    lines.append(f"• {action}")

            chemicals = treatment.get("chemicals", [])
            if chemicals:
                lines.extend([
                    "",
                    "🧪 *Recommended Chemicals:*"
                ])
                for chem in chemicals[:3]:
                    lines.append(f"• {chem}")

        body = "\n".join(lines)

        return cls.build(body, show_main=True, show_previous=True)

    # ==========================================================
    # HISTORY
    # ==========================================================

    @classmethod
    def history(cls, history_list, user_name):
        if not history_list:
            body = (
                "📋 *Scan History*\n\n"
                f"👤 {user_name}, you have no previous scans.\n\n"
                "Send a photo to begin detection."
            )
            return cls.build(body, show_main=True)

        lines = [
            "📋 *Scan History*",
            "",
            f"👤 *Farmer:* {user_name}",
            f"📊 *Total Scans:* {len(history_list)}",
            "",
            "🕒 *Recent Results:*",
            ""
        ]

        for i, scan in enumerate(history_list[:5], 1):
            lines.append(
                f"{i}. *{scan.get('disease_detected', 'Unknown')}* "
                f"- {scan.get('confidence_score', 0):.1f}%"
            )
            lines.append(f"   🕐 {scan.get('date', 'Unknown date')}")
            lines.append("")

        return cls.build("\n".join(lines), show_main=True, show_previous=True)

    # ==========================================================
    # EDUCATIONAL CONTENT
    # ==========================================================

    @classmethod
    def educational(cls, title, content):
        body = (
            f"📚 *{title}*\n\n"
            f"{textwrap.fill(content, width=70)}"
        )
        return cls.build(body, show_main=True, show_previous=True)

    # ==========================================================
    # MENU HEADER
    # ==========================================================

    @classmethod
    def main_menu(cls, user_name):
        body = (
            f"👋 Welcome back, *{user_name}*!\n\n"
            "Please choose an option:\n\n"
            "1️⃣ Detect Disease\n"
            "2️⃣ Disease Education\n"
            "3️⃣ Scan History\n"
            "4️⃣ Expert Consultation\n"
            "5️⃣ Daily Farming Tip\n"
            "6️⃣ Provide Feedback"
        )
        return cls.build(body, show_main=False)

    # ==========================================================
    # ERROR HANDLING
    # ==========================================================

    @classmethod
    def error(cls, error_type="general"):
        return cls.build(
            SYSTEM_MESSAGES.get(error_type, SYSTEM_MESSAGES["error"]),
            show_main=True
        )