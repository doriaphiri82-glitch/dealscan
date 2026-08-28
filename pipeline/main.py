"""
DealScan AI - Main Pipeline Orchestrator

Usage:
    python main.py --setup-db       # Initialize database
    python main.py --run            # Run full pipeline
    python main.py --demo           # Run with demo data (for testing)
    python main.py --deliver        # Send daily deals to subscribers
"""
import argparse
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from database import init_db, save_property, save_deal, get_top_deals
from scoring.deal_scorer import score_and_enrich_deal
from config.counties import COUNTIES
from config.settings import MIN_DEAL_SCORE, MAX_DEALS_PER_EMAIL


def run_demo_pipeline():
    """Run pipeline with demo data to test the scoring engine."""
    print("\n" + "="*60)
    print("  DealScan AI - Demo Pipeline Run")
    print("="*60)

    # Demo properties (simulating what scrapers would find)
    demo_properties = [
        {
            'apn': '123-45-678A',
            'county_id': 'cochise_az',
            'county_state': 'Arizona',
            'address': 'Lot 12, Sierra Vista Estates',
            'lot_size_acres': 2.31,
            'assessed_value': 2100,
            'asking_price': 2100,
            'market_value': 3500,
            'owner_name': 'John R. Smith',
            'owner_address': '456 Oak Ave, Los Angeles, CA 90001',
            'owner_state': 'CA',
            'tax_amount': 45.00,
            'tax_delinquent_years': 3,
            'year_acquired': 2008,
            'zoning': 'Rural Residential',
            'land_use': 'Vacant Land',
            'has_improvements': False,
            'legal_description': 'Lot 12, Sierra Vista Estates, Unit 3',
        },
        {
            'apn': '456-78-901B',
            'county_id': 'mohave_az',
            'county_state': 'Arizona',
            'address': 'Parcel 7, Golden Valley Ranchos',
            'lot_size_acres': 5.02,
            'assessed_value': 4500,
            'asking_price': 4500,
            'market_value': 7200,
            'owner_name': 'Estate of Margaret Williams',
            'owner_address': '789 Pine St, Phoenix, AZ 85001',
            'owner_state': 'AZ',
            'tax_amount': 82.00,
            'tax_delinquent_years': 1,
            'year_acquired': 1995,
            'zoning': 'Rural Residential',
            'land_use': 'Vacant Land',
            'has_improvements': False,
            'legal_description': 'Parcel 7, Golden Valley Ranchos',
        },
        {
            'apn': '789-01-234C',
            'county_id': 'socorro_nm',
            'county_state': 'New Mexico',
            'address': 'Tract 3, Rio Grande Estates',
            'lot_size_acres': 10.5,
            'assessed_value': 3200,
            'asking_price': 3200,
            'market_value': 5800,
            'owner_name': 'Robert & Linda Johnson Trust',
            'owner_address': '321 Elm St, Dallas, TX 75201',
            'owner_state': 'TX',
            'tax_amount': 38.00,
            'tax_delinquent_years': 4,
            'year_acquired': 2003,
            'zoning': 'Agricultural Residential',
            'land_use': 'Vacant Land',
            'has_improvements': False,
            'legal_description': 'Tract 3, Rio Grande Estates, Phase 2',
        },
    ]

    # Demo comps (simulating recent sales data)
    demo_comps_map = {
        '123-45-678A': [
            {'address': 'Lot 8, Sierra Vista Estates', 'sale_price': 8500,
             'lot_size_acres': 2.1, 'distance_miles': 0.3},
            {'address': 'Lot 15, Sierra Vista Estates', 'sale_price': 11000,
             'lot_size_acres': 2.5, 'distance_miles': 0.7},
            {'address': 'Lot 3, Sierra Vista Estates', 'sale_price': 9200,
             'lot_size_acres': 2.0, 'distance_miles': 0.9},
        ],
        '456-78-901B': [
            {'address': 'Parcel 2, Golden Valley', 'sale_price': 12000,
             'lot_size_acres': 5.0, 'distance_miles': 0.5},
            {'address': 'Parcel 11, Golden Valley', 'sale_price': 14500,
             'lot_size_acres': 4.8, 'distance_miles': 1.2},
        ],
        '789-01-234C': [
            {'address': 'Tract 1, Rio Grande', 'sale_price': 7500,
             'lot_size_acres': 10.0, 'distance_miles': 0.8},
            {'address': 'Tract 5, Rio Grande', 'sale_price': 8200,
             'lot_size_acres': 11.0, 'distance_miles': 1.5},
            {'address': 'Tract 8, Rio Grande', 'sale_price': 6800,
             'lot_size_acres': 9.5, 'distance_miles': 2.0},
        ],
    }

    print("\nProcessing demo properties...\n")

    for prop in demo_properties:
        county_id = prop['county_id']
        county_config = COUNTIES.get(county_id, {'market_velocity': 0.5})
        comps = demo_comps_map.get(prop['apn'], [])

        # Score the deal
        deal_data = score_and_enrich_deal(prop, comps, county_config)

        if deal_data is None:
            print(f"  SKIP: {prop['apn']} - Below minimum profit threshold")
            continue

        # Save to database
        prop_id = save_property(prop)
        deal_data['property_id'] = prop_id
        deal_data['source'] = 'demo'
        # Convert list to string for database storage
        deal_data['motivation_signals'] = ','.join(deal_data['motivation_signals'])
        deal_id = save_deal(deal_data)

        # Print results
        print(f"  {'='*50}")
        print(f"  DEAL: {prop['address']}")
        print(f"  County: {county_config.get('name', county_id)}")
        print(f"  APN: {prop['apn']}")
        print(f"  Size: {prop['lot_size_acres']} acres")
        print(f"  Asking: ${prop['asking_price']:,.0f}")
        print(f"  Est. ARV: ${deal_data['estimated_arv_low']:,.0f} - ${deal_data['estimated_arv_high']:,.0f}")
        print(f"  Est. Profit: ${deal_data['estimated_profit_low']:,.0f} - ${deal_data['estimated_profit_high']:,.0f}")
        print(f"  Recommended Offer: ${deal_data['recommended_offer_low']:,.0f} - ${deal_data['recommended_offer_high']:,.0f}")
        print(f"  Motivation Signals: {deal_data['motivation_signals']}")
        print(f"  DEAL SCORE: {deal_data['deal_score']}/100")
        print(f"  Status: Saved (ID: {deal_id})")

    # Show top deals
    print(f"\n{'='*60}")
    print("  TOP DEALS (Ready for Delivery)")
    print(f"{'='*60}\n")

    top_deals = get_top_deals(limit=MAX_DEALS_PER_EMAIL, min_score=MIN_DEAL_SCORE)
    for i, deal in enumerate(top_deals, 1):
        print(f"  #{i} | Score: {deal['deal_score']}/100 | "
              f"{deal['address']} | "
              f"Profit: ${deal['estimated_profit_low']:,.0f}-${deal['estimated_profit_high']:,.0f}")

    print(f"\n  Total deals ready: {len(top_deals)}")
    print(f"\n  Pipeline complete. Run --deliver to send to subscribers.")


def main():
    parser = argparse.ArgumentParser(description='DealScan AI Pipeline')
    parser.add_argument('--setup-db', action='store_true', help='Initialize database')
    parser.add_argument('--run', action='store_true', help='Run full pipeline')
    parser.add_argument('--demo', action='store_true', help='Run with demo data')
    parser.add_argument('--deliver', action='store_true', help='Send deals to subscribers')
    args = parser.parse_args()

    if args.setup_db:
        init_db()
    elif args.demo:
        init_db()
        run_demo_pipeline()
    elif args.run:
        init_db()
        print("Full pipeline requires county scrapers. Use --demo for testing.")
        run_demo_pipeline()
    elif args.deliver:
        print("Delivery requires email configuration. Set EMAIL_API_KEY in .env")
    else:
        parser.print_help()


if __name__ == '__main__':
    main()
