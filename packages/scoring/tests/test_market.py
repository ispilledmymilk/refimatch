from datetime import date

from scoring.market import (
    MarketAnalysisRequest,
    MarketAreaStats,
    PropertyListing,
    SubjectProperty,
    analyze_market,
)


def test_appreciation_positive():
    subject = SubjectProperty(
        property_id="s1",
        address="1 Main",
        city="Austin",
        state="TX",
        zip_code="78704",
        beds=4,
        baths=2.5,
        sqft=2000,
        year_built=2010,
        purchase_price=400_000,
        purchase_date=date(2022, 1, 1),
        estimated_value=480_000,
    )
    market = MarketAreaStats(
        area_name="Test",
        city="Austin",
        state="TX",
        zip_code="78704",
        median_list_price=475_000,
        median_price_per_sqft=240,
        avg_days_on_market=20,
        active_listings_count=3,
        yoy_appreciation_pct=0.04,
        months_of_inventory=2.5,
    )
    listings = [
        PropertyListing(
            listing_id="l1",
            address="2 Main",
            city="Austin",
            state="TX",
            zip_code="78704",
            beds=3,
            baths=2,
            sqft=1800,
            year_built=2005,
            asking_price=450_000,
            days_on_market=10,
            distance_miles=0.3,
        )
    ]
    result = analyze_market(
        MarketAnalysisRequest(subject=subject, listings=listings, market=market)
    )
    assert result.appreciation.appreciation_dollars == 80_000
    assert result.appreciation.appreciation_pct == 0.2
    assert len(result.listing_comparisons) == 1


def test_equity_with_loan_balance():
    subject = SubjectProperty(
        property_id="s1",
        address="1 Main",
        city="Austin",
        state="TX",
        zip_code="78704",
        beds=4,
        baths=2.5,
        sqft=2000,
        year_built=2010,
        purchase_price=425_000,
        purchase_date=date(2022, 4, 15),
        estimated_value=512_000,
    )
    market = MarketAreaStats(
        area_name="Test",
        city="Austin",
        state="TX",
        zip_code="78704",
        median_list_price=499_000,
        median_price_per_sqft=248,
        avg_days_on_market=26,
        active_listings_count=6,
        yoy_appreciation_pct=0.041,
        months_of_inventory=2.8,
    )
    listings = [
        PropertyListing(
            listing_id="l1",
            address="2 Main",
            city="Austin",
            state="TX",
            zip_code="78704",
            beds=3,
            baths=2,
            sqft=1920,
            year_built=2005,
            asking_price=489_000,
            days_on_market=12,
            distance_miles=0.2,
        )
    ]
    result = analyze_market(
        MarketAnalysisRequest(
            subject=subject,
            listings=listings,
            market=market,
            loan_balance=333_447,
            original_loan_at_purchase=350_000,
        )
    )
    assert result.equity is not None
    assert result.equity.ltv_pct < 0.7
    assert result.equity.equity_dollars > 0
