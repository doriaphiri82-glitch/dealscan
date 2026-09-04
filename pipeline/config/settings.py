"""
DealScan AI - Global Settings
"""
import os

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass  # dotenv not installed; use environment variables directly


# Database
DATABASE_PATH = os.path.join(os.path.dirname(__file__), '..', 'data', 'dealscan.db')

# Email (using Resend or SendGrid)
EMAIL_PROVIDER = os.getenv('EMAIL_PROVIDER', 'console')  # 'console', 'resend', 'sendgrid'
EMAIL_API_KEY = os.getenv('EMAIL_API_KEY', '')
EMAIL_FROM = os.getenv('EMAIL_FROM', 'deals@dealscan.ai')
EMAIL_FROM_NAME = 'DealScan AI'

# Scoring weights (must sum to 1.0)
SCORING_WEIGHTS = {
    'profit_ratio': 0.30,       # Profit as % of asking price
    'motivation_signals': 0.25, # Number/strength of motivated seller signals
    'market_velocity': 0.20,    # How fast similar properties sell
    'competition': 0.15,        # How many other buyers are likely interested
    'accessibility': 0.10,      # Road access, utilities proximity
}

# Deal thresholds
# Keep this low enough to surface real opportunities in rural counties while
# still preventing zero/near-zero profit records from becoming deals.
MIN_PROFIT_ESTIMATE = 1000     # Minimum estimated profit to include
MIN_DEAL_SCORE = 40             # Minimum score to deliver
MAX_DEALS_PER_EMAIL = 10        # Max deals in daily email
MIN_DEALS_PER_EMAIL = 3         # Min deals (if fewer qualify, send what we have)

# Motivated seller signals
TAX_DELINQUENT_YEARS = 2        # Years of tax delinquency to flag
ABSENTEE_OWNER = True           # Flag if owner lives in different state
MIN_OWNERSHIP_YEARS = 10        # Years owned (long-term = more motivated)

# County data
# Production-enabled counties. New sources are added here only after their
# scraper has passed field validation and a live sample run.
DEFAULT_COUNTIES = [
    'cochise_az',
    'mohave_az',
    'el_paso_tx',
    'yavapai_az',
    'washoe_nv',
    'pinal_az',
    'hudson_co',
    'socorro_nm',
]

# Delivery
DELIVERY_HOUR = 6               # 6 AM delivery
DELIVERY_MINUTE = 0
TIMEZONE = 'America/Phoenix'    # Arizona time

# Free tier settings
FREE_TIER_DEALS_PER_WEEK = 3
FREE_TIER_DELAY_HOURS = 48      # Free members get deals 48hrs after paid
