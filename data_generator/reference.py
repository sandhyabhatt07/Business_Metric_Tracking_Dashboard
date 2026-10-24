"""Static reference data: segments, geography, channels, plans and prices."""

COMPANY_NAME = "PulseBoard"
INTERNAL_EMAIL_DOMAIN = "pulseboard.io"

SEGMENTS = ["SMB", "Mid-Market", "Enterprise"]
SEGMENT_MIX = [0.70, 0.22, 0.08]
EMPLOYEE_RANGES = {"SMB": (5, 99), "Mid-Market": (100, 999), "Enterprise": (1000, 25000)}

# How the CRM spells each segment. Sales reps type these by hand.
SEGMENT_SPELLINGS = {
    "SMB": ["SMB", "SMB", "SMB", "smb", "Smb ", "Small Business"],
    "Mid-Market": ["Mid-Market", "Mid-Market", "Mid Market", "mid-market", "MM"],
    "Enterprise": ["Enterprise", "Enterprise", "enterprise", "ENT", "Enterprise "],
}

INDUSTRIES = [
    "Software", "Retail", "Financial Services", "Healthcare", "Manufacturing",
    "Education", "Media", "Logistics", "Professional Services", "Hospitality",
]

# country: (region, weight within region, currency, UTC offset in hours)
COUNTRIES = {
    "US": ("North America", 0.85, "USD", -5.0),
    "CA": ("North America", 0.15, "USD", -5.0),
    "GB": ("EMEA", 0.35, "GBP", 0.0),
    "DE": ("EMEA", 0.25, "EUR", 1.0),
    "FR": ("EMEA", 0.15, "EUR", 1.0),
    "NL": ("EMEA", 0.15, "EUR", 1.0),
    "ES": ("EMEA", 0.10, "EUR", 1.0),
    "IN": ("APAC", 0.45, "INR", 5.5),
    "AU": ("APAC", 0.35, "AUD", 10.0),
    "SG": ("APAC", 0.20, "USD", 8.0),
}
REGION_MIX = {"North America": 0.45, "EMEA": 0.35, "APAC": 0.20}

CHANNELS = ["organic", "paid_search", "paid_social", "referral", "partner", "outbound_sales"]
CHANNEL_MIX = {
    "SMB": [0.38, 0.25, 0.20, 0.12, 0.05, 0.00],
    "Mid-Market": [0.30, 0.20, 0.10, 0.15, 0.12, 0.13],
    "Enterprise": [0.15, 0.08, 0.02, 0.10, 0.25, 0.40],
}

# plan: (list price in USD per seat per month, minimum seats)
PLANS = {
    "Starter": (15, 1),
    "Growth": (30, 3),
    "Business": (50, 10),
    "Enterprise": (75, 25),
}
PLAN_ORDER = ["Starter", "Growth", "Business", "Enterprise"]
PLAN_MIX = {
    "SMB": [0.75, 0.23, 0.02, 0.00],
    "Mid-Market": [0.15, 0.60, 0.25, 0.00],
    "Enterprise": [0.00, 0.10, 0.40, 0.50],
}
ANNUAL_SHARE = {"SMB": 0.20, "Mid-Market": 0.45, "Enterprise": 0.70}
ANNUAL_DISCOUNT = 0.15

# Local price books: price in local currency = USD list price x multiplier.
PRICE_BOOK = {"USD": 1.0, "EUR": 0.95, "GBP": 0.82, "AUD": 1.50, "INR": 80.0}
# Starting USD -> X exchange rates for the mock FX feed.
FX_START = {"EUR": 0.92, "GBP": 0.79, "AUD": 1.52, "INR": 83.6}

SALES_REPS = [
    "a.patel", "j.nguyen", "m.garcia", "s.kowalski", "r.okafor", "l.chen",
    "d.muller", "e.rossi", "k.tanaka", "p.osei", "t.brennan", "n.ivanova",
]
SELF_SERVE_OWNER = "self-serve-queue"

CANCEL_REASONS = ["too_expensive", "missing_features", "switched_competitor",
                  "low_usage", "company_closed", "other"]

# Monthly signup seasonality (B2B: quiet December and August).
MONTH_SEASONALITY = {1: 1.10, 2: 1.05, 3: 1.05, 4: 1.00, 5: 1.00, 6: 0.95,
                     7: 0.92, 8: 0.85, 9: 1.05, 10: 1.08, 11: 1.00, 12: 0.75}

# Paid marketing platforms, as named in the ad-platform export.
AD_PLATFORMS = {
    "Google Ads": ("paid_search", 95.0, ["Brand Search", "Generic - Dashboards", "Competitor Terms"]),
    "Meta Ads": ("paid_social", 70.0, ["Prospecting - Lookalike", "Retargeting"]),
    "LinkedIn Ads": ("paid_social", 160.0, ["ABM - Mid-Market", "Thought Leadership"]),
}

NAME_PREFIXES = [
    "Blue", "North", "Bright", "Iron", "Silver", "Cedar", "Summit", "Harbor", "Nova", "Apex",
    "Atlas", "Granite", "Maple", "Orbit", "Pioneer", "Quantum", "River", "Stellar", "Vertex", "Willow",
    "Crescent", "Evergreen", "Falcon", "Golden", "Horizon", "Lumen", "Meridian", "Oak", "Prism", "Sable",
]
NAME_CORES = [
    "Analytics", "Logistics", "Foods", "Health", "Labs", "Retail", "Systems", "Capital", "Media", "Works",
    "Partners", "Studio", "Supply", "Learning", "Motors", "Energy", "Ventures", "Digital", "Goods", "Care",
]
NAME_SUFFIXES = ["Inc", "LLC", "Ltd", "GmbH", "Co", "Group", "Pvt Ltd", "Pty Ltd", "BV", "SAS"]
