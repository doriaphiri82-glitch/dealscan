"""
DealScan AI - County Configurations
Each county has specific data access methods and URLs.

The legacy COUNTY config is kept for scoring defaults and human-readable
metadata. Live source details for the newer ArcGIS counties are mirrored in
pipeline/scrapers/counties.py and the national registry.
"""

COUNTIES = {
    'cochise_az': {
        'name': 'Cochise County', 'state': 'Arizona', 'fips': '04003',
        'assessor_url': 'https://www.cochise.az.gov/assessor',
        'parcel_search_url': 'https://assessor.cochise.az.gov/',
        'recorder_url': 'https://www.cochise.az.gov/recorder', 'data_format': 'web',
        'avg_price_per_acre': 3500, 'market_velocity': 0.7,
        'notes': 'Strong land flipping market. Many absentee owners. Tax delinquent lists available.',
    },
    'mohave_az': {
        'name': 'Mohave County', 'state': 'Arizona', 'fips': '04015',
        'assessor_url': 'https://www.mohave.gov/assessor',
        'parcel_search_url': 'https://assessor.mohave.gov/',
        'recorder_url': 'https://www.mohave.gov/recorder', 'data_format': 'web',
        'avg_price_per_acre': 2800, 'market_velocity': 0.6,
        'notes': 'Large parcels, lower prices. Good for beginners. Many out-of-state owners.',
    },
    'el_paso_tx': {
        'name': 'El Paso County', 'state': 'Texas', 'fips': '48141',
        'assessor_url': 'https://www.epcad.org/',
        'parcel_search_url': 'https://www.epcad.org/property-search/',
        'recorder_url': 'https://www.epcounty.com/recorder', 'data_format': 'web',
        'avg_price_per_acre': 4200, 'market_velocity': 0.75,
        'notes': 'Growing market near El Paso metro. Higher prices but faster sales.',
    },
    'yavapai_az': {
        'name': 'Yavapai County', 'state': 'Arizona', 'fips': '04025',
        'assessor_url': 'https://www.yavapaiaz.gov/Mapping-and-Properties',
        'parcel_search_url': 'https://gis.yavapaiaz.gov/arcgis/rest/services/Property/FeatureServer/4',
        'recorder_url': None, 'data_format': 'arcgis',
        'avg_price_per_acre': 0, 'market_velocity': 0.65,
        'notes': 'Official county parcel service plus a dedicated Vacant Land layer. Source validated; enrichment mapping remains conservative.',
    },
    'washoe_nv': {
        'name': 'Washoe County', 'state': 'Nevada', 'fips': '32031',
        'assessor_url': 'https://www.washoecounty.gov/assessor/',
        'parcel_search_url': 'https://gisenterprise.washoecounty.gov/server/rest/services/WashoeGIS/Parcels/FeatureServer/0',
        'recorder_url': None, 'data_format': 'arcgis',
        'avg_price_per_acre': 0, 'market_velocity': 0.7,
        'notes': 'Official WashoeGIS parcel service with APN, acreage, address and zoning fields. Source validated; vacant-land classification/enrichment remains conservative.',
    },
    'pinal_az': {
        'name': 'Pinal County', 'state': 'Arizona', 'fips': '04021',
        'assessor_url': 'https://www.pinal.gov/assessor',
        'parcel_search_url': 'https://rogue.casagrandeaz.gov/arcgis/rest/services/Pinal_County/Pinal_County_Parcels/FeatureServer/0',
        'recorder_url': None, 'data_format': 'arcgis',
        'avg_price_per_acre': 0, 'market_velocity': 0.72,
        'notes': 'Public parcel service published by Casa Grande GIS with parcel, owner, address, land value, assessed value, tax and sale fields. Strong candidate for discovery after field mapping validation.',
    },
    'hudson_co': {
        'name': 'Huerfano County', 'state': 'Colorado', 'fips': '08055',
        'assessor_url': 'https://huerfano.us/assessor',
        'parcel_search_url': 'https://huerfano.us/assessor/property-search',
        'recorder_url': 'https://huerfano.us/recorder', 'data_format': 'web',
        'avg_price_per_acre': 5500, 'market_velocity': 0.5,
        'notes': 'Mountain properties. Scenic value drives demand. Slower but higher margins.',
    },
    'socorro_nm': {
        'name': 'Socorro County', 'state': 'New Mexico', 'fips': '35053',
        'assessor_url': 'https://www.socorrocounty.net/assessor',
        'parcel_search_url': 'https://www.socorrocounty.net/assessor/search',
        'recorder_url': 'https://www.socorrocounty.net/recorder', 'data_format': 'web',
        'avg_price_per_acre': 2200, 'market_velocity': 0.55,
        'notes': 'Very affordable entry point. Large parcels. Good for first-time flippers.',
    },
}

FUTURE_COUNTIES = [
    'apache_az', 'navajo_az', 'hudspeth_tx', 'costilla_co',
    'catron_nm', 'sierra_nm', 'lincoln_nv', 'nye_nv',
]
