"""
DealScan AI - Data Models
"""
from dataclasses import dataclass, field
from datetime import datetime
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
    address: str
    lot_size_acres: float
    assessed_value: float
    market_value: float
    owner_name: str
    owner_address: str
    owner_state: str
    tax_amount: float
    tax_delinquent_years: int
    year_acquired: int
    zoning: str
    land_use: str
    has_improvements: bool
    legal_description: str
    latitude: Optional[float] = None
    longitude: Optional[float] = None


@dataclass
class Deal:
    """A scored deal ready for delivery."""
    id: Optional[int] = None
    property: Optional[Property] = None
    comps: List[CompSale] = field(default_factory=list)
    
    # Scoring
    deal_score: int = 0               # 1-100
    estimated_arv_low: float = 0
    estimated_arv_high: float = 0
    estimated_costs: float = 0
    estimated_profit_low: float = 0
    estimated_profit_high: float = 0
    asking_price: float = 0
    recommended_offer_low: float = 0
    recommended_offer_high: float = 0
    
    # Motivation
    motivation_signals: List[MotivationSignal] = field(default_factory=list)
    motivation_score: float = 0       # 0-1
    
    # Market
    market_velocity: float = 0        # 0-1
    competition_level: str = 'low'    # low, medium, high
    days_on_market: int = 0
    
    # Status
    status: DealStatus = DealStatus.DISCOVERED
    discovered_at: datetime = field(default_factory=datetime.now)
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
    budget_min: float = 5000
    budget_max: float = 50000
    target_states: List[str] = field(default_factory=list)
    target_counties: List[str] = field(default_factory=list)
    min_profit: float = 3000
    joined_at: datetime = field(default_factory=datetime.now)
    is_active: bool = True
