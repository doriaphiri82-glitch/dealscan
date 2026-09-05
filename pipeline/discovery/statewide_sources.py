"""Curated statewide parcel portals used to accelerate county source discovery.

These are discovery hints, not verification records. A county source still has to
pass DealScan's live schema/ETL validation before it can be considered verified.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional


@dataclass(frozen=True)
class StatewideSource:
    state: str
    name: str
    url: str
    source_type: str = "statewide_portal"
    notes: str = ""
    county_name_field: Optional[str] = None
    county_fips_field: Optional[str] = None
    parcel_id_field: Optional[str] = None


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
        "Connecticut",
        "Connecticut Parcel & CAMA Data",
        "https://geodata.ct.gov/pages/parcels",
        notes="State parcel/CAMA collection page with statewide parcel viewer and open-data links.",
    ),
    "Florida": StatewideSource(
        "Florida",
        "Florida Statewide Parcels",
        "https://services9.arcgis.com/Gh9awoU677aKree0/arcgis/rest/services/Florida_Statewide_Cadastral/FeatureServer/0",
        source_type="arcgis_layer",
        notes="Official FDOR statewide parcel layer assembled from all 67 county property appraisers; county number is exposed as CO_NO.",
        county_fips_field="CO_NO",
        parcel_id_field="PARCEL_ID",
    ),
    "Maryland": StatewideSource(
        "Maryland",
        "Maryland Parcel Boundaries",
        "https://data.imap.maryland.gov/datasets/maryland::maryland-parcel-boundaries/about",
        notes="Official statewide Maryland parcel boundary dataset.",
    ),
    "North Carolina": StatewideSource(
        "North Carolina",
        "NC OneMap Parcels",
        "https://services.nconemap.gov/secure/rest/services/NC1Map_Parcels/MapServer/1",
        source_type="arcgis_layer",
        notes="Official statewide parcel layer covering all 100 North Carolina counties with standardized attributes and county FIPS fields.",
        county_name_field="cntyname",
        county_fips_field="cntyfips",
        parcel_id_field="parno",
    ),
    "Ohio": StatewideSource(
        "Ohio",
        "Ohio Parcels",
        "https://ohioparcels-geohio.hub.arcgis.com/",
        notes="Statewide parcel map assembled from county-maintained parcel and assessment records.",
    ),
    "Washington": StatewideSource(
        "Washington",
        "Washington Current Parcels",
        "https://services.arcgis.com/jsIt88o09Q0r1j8h/arcgis/rest/services/Current_Parcels/FeatureServer/0",
        source_type="arcgis_layer",
        notes="Official Washington statewide tax parcel service with normalized county and parcel identifiers plus values and addresses.",
        county_name_field="COUNTY_NM",
        county_fips_field="FIPS_NR",
        parcel_id_field="PARCEL_ID_NR",
    ),
    "Wisconsin": StatewideSource(
        "Wisconsin",
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
