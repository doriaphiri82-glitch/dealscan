"""
DealScan AI - County Configurations
Each county has specific data access methods and URLs.
"""

COUNTIES = {
    'cochise_az': {
        'name': 'Cochise County',
        'state': 'Arizona',
        'fips': '04003',
        'assessor_url': 'https://www.cochise.az.gov/assessor',
        'parcel_search_url': 'https://assessor.cochise.az.gov/',
        'recorder_url': 'https://www.cochise.az.gov/recorder',
        'data_format': 'web',  # 'web', 'api', 'ftp'
        'avg_price_per_acre': 3500,
        'market_velocity': 0.7,  # 0-1, how fast properties sell
        'notes': 'Strong land flipping market. Many absentee owners. Tax delinquent lists available.',
    },
    'mohave_az': {
        'name': 'Mohave County',
        'state': 'Arizona',
        'fips': '04015',
        'assessor_url': 'https://www.mohave.gov/assessor',
        'parcel_search_url': 'https://assessor.mohave.gov/',
        'recorder_url': 'https://www.mohave.gov/recorder',
        'data_format': 'web',
        'avg_price_per_acre': 2800,
        'market_velocity': 0.6,
        'notes': 'Large parcels, lower prices. Good for beginners. Many out-of-state owners.',
    },
    'el_paso_tx': {
        'name': 'El Paso County',
        'state': 'Texas',
        'fips': '48141',
        'assessor_url': 'https://www.epcad.org/',
        'parcel_search_url': 'https://www.epcad.org/property-search/',
        'recorder_url': 'https://www.epcounty.com/recorder',
        'data_format': 'web',
        'avg_price_per_acre': 4200,
        'market_velocity': 0.75,
        'notes': 'Growing market near El Paso metro. Higher prices but faster sales.',
    },
    'hudson_co': {
        'name': 'Huerfano County',
        'state': 'Colorado',
        'fips': '08055',
        'assessor_url': 'https://huerfano.us/assessor',
        'parcel_search_url': 'https://huerfano.us/assessor/property-search',
        'recorder_url': 'https://huerfano.us/recorder',
        'data_format': 'web',
        'avg_price_per_acre': 5500,
        'market_velocity': 0.5,
        'notes': 'Mountain properties. Scenic value drives demand. Slower but higher margins.',
    },
    'socorro_nm': {
        'name': 'Socorro County',
        'state': 'New Mexico',
        'fips': '35053',
        'assessor_url': 'https://www.socorrocounty.net/assessor',
        'parcel_search_url': 'https://www.socorrocounty.net/assessor/search',
        'recorder_url': 'https://www.socorrocounty.net/recorder',
        'data_format': 'web',
        'avg_price_per_acre': 2200,
        'market_velocity': 0.55,
        'notes': 'Very affordable entry point. Large parcels. Good for first-time flippers.',
    },
}

# Additional counties to add in future phases
FUTURE_COUNTIES = [
    'apache_az',      # Apache County, AZ
    'navajo_az',      # Navajo County, AZ
    'hudspeth_tx',    # Hudspeth County, TX
    'costilla_co',    # Costilla County, CO
    'catron_nm',      # Catron County, NM
    'sierra_nm',      # Sierra County, NM
    'lincoln_nv',     # Lincoln County, NV
    'nye_nv',         # Nye County, NV
]
