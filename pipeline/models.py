"""
DealScan AI - Data Models
"""
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional, List
from enum import Enum


class DealStatus(Enum):
    DISCOVERED = 'discovered'
    SCORED = 'scored'
    DELIVERED = 'delivered'
    OFFERED = 'offered'
    UNDER_CONTRACT = 'under_contract'
    CLOSED = 'closed'
    EXPIRED = 'expired'


class MotivationSignal(Enum):
    TAX_DELINQUENT = 'tax_delinquent'
    ABSENTEE_OWNER = 'absentee_owner'
    PROBATE = 'probate'
    INHERITED = 'inherited'
    LONG_OWNERSHIP = 'long_ownership'
    NO_IMPROVEMENTS = 'no_improvements'
    VACANT_LAND = 'vacant_land'
    MULTIPLE_PARCELS = 'multiple_parcels'


@dataclass
class CompSale:
    """A comparable sale used for ARV estimation."""
    address: str
    sale_price: float
    sale_date: datetime
    distance_miles: float
    lot_size_acres: float
    price_per_acre: float


@dataclass
class Property:
    """A property record from county data."""
    apn: str                          # Assessor's Parcel Number
    county_id: str
    address: Optional[str] = None
    lot_size_acres: Optional[float] = None
    assessed_value: Optional[float] = None
    market_value: Optional[float] = None
    owner_name: Optional[str] = None
    owner_address: Optional[str] = None
    owner_state: Optional[str] = None
    tax_amount: Optional[float] = None
    tax_delinquent_years: Optional[int] = None
    year_acquired: Optional[int] = None
    zoning: Optional[str] = None
    land_use: Optional[str] = None
    has_improvements: Optional[bool] = None
    legal_description: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None


@dataclass
class Deal:
    """A private assessment; its existence never authorizes publication or delivery."""
    id: Optional[int] = None
    property: Optional[Property] = None
    comps: List[CompSale] = field(default_factory=list)

    # Scoring
    deal_score: Optional[int] = None               # 1-100
    estimated_arv_low: Optional[float] = None
    estimated_arv_high: Optional[float] = None
    estimated_costs: Optional[float] = None
    estimated_profit_low: Optional[float] = None
    estimated_profit_high: Optional[float] = None
    asking_price: Optional[float] = None
    recommended_offer_low: Optional[float] = None
    recommended_offer_high: Optional[float] = None

    # Motivation
    motivation_signals: List[MotivationSignal] = field(default_factory=list)
    motivation_score: Optional[float] = None       # 0-1

    # Market
    market_velocity: Optional[float] = None        # 0-1
    competition_level: Optional[str] = None    # low, medium, high
    days_on_market: Optional[int] = None

    verification_status: str = 'pending_review'
    verified_at: Optional[datetime] = None
    verification_expires_at: Optional[datetime] = None

    # Status
    status: DealStatus = DealStatus.DISCOVERED
    discovered_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    delivered_at: Optional[datetime] = None

    # Metadata
    notes: str = ''
    source: str = ''


@dataclass
class Subscriber:
    """A DealScan subscriber."""
    id: Optional[int] = None
    email: str = ''
    name: str = ''
    tier: str = 'free'                # free, pro, elite
    budget_min: Optional[float] = None
    budget_max: Optional[float] = None
    target_states: List[str] = field(default_factory=list)
    target_counties: List[str] = field(default_factory=list)
    min_profit: Optional[float] = None
    joined_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    is_active: bool = False
    consented_at: Optional[datetime] = None
    unsubscribe_url: Optional[str] = None
