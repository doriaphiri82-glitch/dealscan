"""DealScan - Demo pipeline (generates demo properties + comps for testing)."""
from __future__ import annotations

import sys
import os
from typing import List, Dict

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from database import save_property, save_deal, get_top_deals  # noqa: E402
from scoring.deal_scorer import score_and_enrich_deal  # noqa: E402
from config.counties import COUNTIES  # noqa: E402
from config.settings import MIN_DEAL_SCORE, MAX_DEALS_PER_EMAIL  # noqa: E402


def run():
    """Run the scraper with demo data (no network) to test the scoring + DB."""
    print("\n" + "=" * 60)
    print("  DealScan AI - Demo Pipeline Run")
    print("=" * 60)

    demo_properties = [
        {
            'apn': '123-45-678A', 'county_id': 'cochise_az',
            'county_state': 'Arizona', 'address': 'Lot 12, Sierra Vista Estates',
            'lot_size_acres': 2.31, 'assessed_value': 2100, 'asking_price': 2100,
            'market_value': 3500, 'owner_name': 'John R. Smith',
            'owner_address': '456 Oak Ave, Los Angeles, CA 90001',
            'owner_state': 'CA', 'tax_amount': 45.00, 'tax_delinquent_years': 3,
            'year_acquired': 2008, 'zoning': 'Rural Residential',
            'land_use': 'Vacant Land', 'has_improvements': False,
            'legal_description': 'Lot 12, Sierra Vista Estates, Unit 3',
        },
        {
            'apn': '456-78-901B', 'county_id': 'mohave_az',
            'county_state': 'Arizona', 'address': 'Parcel 7, Golden Valley Ranchos',
            'lot_size_acres': 5.02, 'assessed_value': 4500, 'asking_price': 4500,
            'market_value': 7200, 'owner_name': 'Estate of Margaret Williams',
            'owner_address': '789 Pine St, Phoenix, AZ 85001',
            'owner_state': 'AZ', 'tax_amount': 82.00, 'tax_delinquent_years': 1,
            'year_acquired': 1995, 'zoning': 'Rural Residential',
            'land_use': 'Vacant Land', 'has_improvements': False,
            'legal_description': 'Parcel 7, Golden Valley Ranchos',
        },
        {
            'apn': '789-01-234C', 'county_id': 'socorro_nm',
            'county_state': 'New Mexico', 'address': 'Tract 3, Rio Grande Estates',
            'lot_size_acres': 10.5, 'assessed_value': 3200, 'asking_price': 3200,
            'market_value': 5800, 'owner_name': 'Robert & Linda Johnson Trust',
            'owner_address': '321 Elm St, Dallas, TX 75201',
            'owner_state': 'TX', 'tax_amount': 38.00, 'tax_delinquent_years': 4,
            'year_acquired': 2003, 'zoning': 'Agricultural Residential',
            'land_use': 'Vacant Land', 'has_improvements': False,
            'legal_description': 'Tract 3, Rio Grande Estates, Phase 2',
        },
    ]

    demo_comps_map = {
        '123-45-678A': [
            {'address': 'Lot 8, Sierra Vista Estates', 'sale_price': 8500,
             'lot_size_acres': 2.1, 'distance_miles': 0.3},
            {'address': 'Lot 14, Sierra Vista Estates', 'sale_price': 11200,
             'lot_size_acres': 2.5, 'distance_miles': 0.5},
        ],
        '789-01-234C': [
            {'address': 'Tract 5, Rio Grande', 'sale_price': 8200,
             'lot_size_acres': 11.0, 'distance_miles': 1.5},
        ],
    }

    print("\nProcessing demo properties...\n")

    for prop in demo_properties:
        county_id = prop['county_id']
        county_config = COUNTIES.get(county_id, {'market_velocity': 0.5})
        comps = demo_comps_map.get(prop['apn'], [])
        deal_data = score_and_enrich_deal(prop, comps, county_config)
        if deal_data is None:
            print(f"  SKIP: {prop['apn']} - Below minimum profit threshold")
            continue
        prop_id = save_property(prop)
        deal_data['property_id'] = prop_id
        deal_data['source'] = 'demo'
        deal_data['motivation_signals'] = ','.join(deal_data['motivation_signals'])
        deal_id = save_deal(deal_data)
        print(f"  {'=' * 50}")
        print(f"  DEAL: {prop['address']}")
        print(f"  County: {county_config.get('name', county_id)}")
        print(f"  APN: {prop['apn']} | {prop['lot_size_acres']} acres | ${prop['asking_price']:,.0f}")
        print(f"  ARV: ${deal_data['estimated_arv_low']:,.0f} - ${deal_data['estimated_arv_high']:,.0f}")
        print(f"  Profit: ${deal_data['estimated_profit_low']:,.0f} - ${deal_data['estimated_profit_high']:,.0f}")
        print(f"  Signals: {deal_data['motivation_signals']}")
        print(f"  DEAL SCORE: {deal_data['deal_score']}/100")
        print(f"  Saved (ID: {deal_id})")

    print(f"\n{'=' * 60}")
    print("  TOP DEALS (Ready for Delivery)")
    print(f"{'=' * 60}\n")
    top_deals = get_top_deals(limit=MAX_DEALS_PER_EMAIL, min_score=MIN_DEAL_SCORE)
    for i, deal in enumerate(top_deals, 1):
        print(f"  #{i} | Score: {deal['deal_score']}/100 | "
              f"{deal['address']} | "
              f"Profit: ${deal['estimated_profit_low']:,.0f}-${deal['estimated_profit_high']:,.0f}")

    print(f"\n  Total deals ready: {len(top_deals)}")
    print(f"\n  Pipeline complete. Run --deliver to send to subscribers.")

    # Also publish a web bundle so the site has something to render in dev.
    from runregistry import write_bundle
    try:
        path = write_bundle(
            [
                {
                    "apn": d.get("apn"),
                    "address": d.get("address"),
                    "county_id": d.get("county_id"),
                    "lot_size_acres": d.get("lot_size_acres"),
                    "asking_price": d.get("asking_price"),
                    "deal_score": d.get("deal_score"),
                    "estimated_arv_low": d.get("estimated_arv_low"),
                    "estimated_arv_high": d.get("estimated_arv_high"),
                    "estimated_profit_low": d.get("estimated_profit_low"),
                    "estimated_profit_high": d.get("estimated_profit_high"),
                    "motivation_signals": (d.get("motivation_signals") or "").split(","),
                    "market_velocity": d.get("market_velocity"),
                    "competition_level": d.get("competition_level"),
                    "owner_state": d.get("owner_state"),
                    "zoning": d.get("zoning"),
                    "tax_delinquent_years": d.get("tax_delinquent_years"),
                    "source": "demo",
                }
                for d in top_deals
            ],
            ["demo"],
            status="demo",
        )
        print(f"\n  Demo bundle written: {path}")
    except Exception as e:
        print(f"\n  (demo bundle skipped: {e})")