"""Curated statewide parcel portals used to accelerate county source discovery.

These are discovery hints, not verification records. A county source still has to
pass DealScan's live schema/ETL validation before it can be considered verified.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List


@dataclass(frozen=True)
class StatewideSource:
    state: str
    name: str
    url: str
    source_type: str = "statewide_portal"
    notes: str = ""


# High-confidence public statewide parcel entry points. Keep this list small and
# authoritative; discovery can expand it later from Firecrawl/search results.
STATEWIDE_PARCEL_SOURCES: Dict[str, StatewideSource] = {
    "Ohio": StatewideSource(
        "Ohio",
        "Ohio Parcels",
        "https://ohioparcels-geohio.hub.arcgis.com/",
        notes="Statewide parcel map assembled from county-maintained parcel/assessment records.",
    ),
    "Florida": StatewideSource(
        "Florida Statewide Parcels",
        "https://geodata.floridagio.gov/datasets/FGIO::florida-statewide-parcels/about",
        notes="Statewide parcel dataset built from county property-appraiser tax-roll information.",
    ),
    "Washington": StatewideSource(
        "Washington Current Parcels",
        "https://geo.wa.gov/maps/2b603a599a0842a3b2284c04c8927f35",
        notes="State geospatial open-data parcel resource.",
    ),
    "Wisconsin": StatewideSource(
        "Wisconsin Statewide Parcel Map",
        "https://maps.sco.wisc.edu/Parcels/",
        notes="Statewide parcel map maintained by Wisconsin State Cartographer's Office.",
    ),
    "Connecticut": StatewideSource(
        "Connecticut Parcel & CAMA Data",
        "https://geodata.ct.gov/pages/parcels",
        notes="State parcel/CAMA collection page with statewide parcel viewer and open-data links.",
    ),
}


def statewide_sources_for_state(state: str) -> List[StatewideSource]:
    """Return known statewide parcel portals for a state, case-insensitively."""
    wanted = " ".join(str(state).lower().split())
    return [
        source
        for name, source in STATEWIDE_PARCEL_SOURCES.items()
        if " ".join(name.lower().split()) == wanted
    ]


def all_statewide_sources() -> List[StatewideSource]:
    """Return all curated statewide discovery hints in stable order."""
    return [STATEWIDE_PARCEL_SOURCES[state] for state in sorted(STATEWIDE_PARCEL_SOURCES)]
