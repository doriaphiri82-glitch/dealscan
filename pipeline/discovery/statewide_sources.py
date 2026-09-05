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


# High-confidence public statewide parcel entry points. Keep this list authoritative;
# county-level discovery and ETL verification remain separate steps.
STATEWIDE_PARCEL_SOURCES: Dict[str, StatewideSource] = {
    "Colorado": StatewideSource(
        "Colorado",
        "Colorado Public Parcels",
        "https://geodata.colorado.gov/datasets/colorado-public-parcels/about",
        notes="Official statewide public parcel dataset assembled through county/state relationships.",
    ),
    "Connecticut": StatewideSource(
        "Connecticut Parcel & CAMA Data",
        "https://geodata.ct.gov/pages/parcels",
        notes="State parcel/CAMA collection page with statewide parcel viewer and open-data links.",
    ),
    "Florida": StatewideSource(
        "Florida Statewide Parcels",
        "https://geodata.floridagio.gov/datasets/FGIO::florida-statewide-parcels/about",
        notes="Statewide parcel dataset built from county property-appraiser tax-roll information.",
    ),
    "Maryland": StatewideSource(
        "Maryland Parcel Boundaries",
        "https://data.imap.maryland.gov/datasets/maryland::maryland-parcel-boundaries/about",
        notes="Official statewide Maryland parcel boundary dataset.",
    ),
    "North Carolina": StatewideSource(
        "NC OneMap Parcels",
        "https://www.nconemap.gov/pages/parcels",
        notes="Official statewide parcel resource covering all 100 North Carolina counties with standardized attributes and web services.",
    ),
    "Ohio": StatewideSource(
        "Ohio Parcels",
        "https://ohioparcels-geohio.hub.arcgis.com/",
        notes="Statewide parcel map assembled from county-maintained parcel and assessment records.",
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
