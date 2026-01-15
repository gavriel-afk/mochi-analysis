"""Constants for Mochi Analytics."""

# Stage types (9 total)
STAGE_TYPES = [
    "NEW_LEAD",
    "IN_CONTACT",
    "QUALIFIED",
    "UNQUALIFIED",
    "BOOKED_CALL",
    "DEPOSIT",
    "WON",
    "LOST",
    "NO_SHOW"
]

# Time bins for activity analysis (8 total)
TIME_BINS = [
    "00_03",  # 00:00 - 03:00
    "03_06",  # 03:00 - 06:00
    "06_09",  # 06:00 - 09:00
    "09_12",  # 09:00 - 12:00
    "12_15",  # 12:00 - 15:00
    "15_18",  # 15:00 - 18:00
    "18_21",  # 18:00 - 21:00
    "21_24"   # 21:00 - 00:00
]

# Media types
MEDIA_TYPES = ["image", "video", "audio", "file", "other"]

# Objection categories (7 total)
OBJECTION_GROUPS = [
    "Financial Objection",              # Money concerns
    "Timing Objection",                 # Time concerns
    "Decision Making Objection",        # Need approval
    "Self Confidence Objection",        # Self-doubt
    "Lack of Trust/Authority Objection",# Trust issues
    "Competitor Objection",             # Alternatives
    "Lack of Information Objection"     # Need details
]

# Script categories
SCRIPT_CATEGORIES = [
    "opener",              # First message in conversation
    "follow_up",          # Follow-up after no response
    "nurture_discovery",  # Discovery questions, building rapport
    "cta"                 # Call to action (book call, make decision)
]
