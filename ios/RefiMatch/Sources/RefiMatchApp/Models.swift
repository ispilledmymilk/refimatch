import Foundation

struct DemoOfferDTO: Codable, Identifiable, Hashable {
    var id: String { lenderId }
    let lenderId: String
    let lenderName: String
    let apr: Double
    let points: Double
    let lenderFees: Double
    let termMonths: Int
    let notes: String?

    enum CodingKeys: String, CodingKey {
        case lenderId = "lender_id"
        case lenderName = "lender_name"
        case apr
        case points
        case lenderFees = "lender_fees"
        case termMonths = "term_months"
        case notes
    }

    func patched(apr: Double? = nil, points: Double? = nil, fees: Double? = nil) -> DemoOfferDTO {
        DemoOfferDTO(
            lenderId: lenderId,
            lenderName: lenderName,
            apr: apr ?? self.apr,
            points: points ?? self.points,
            lenderFees: fees ?? self.lenderFees,
            termMonths: termMonths,
            notes: notes
        )
    }
}

struct LoanScenarioDTO: Codable {
    let originalPrincipal: Double
    let annualRate: Double
    let termMonths: Int
    let monthsPaid: Int
    let holdHorizonMonths: Int

    enum CodingKeys: String, CodingKey {
        case originalPrincipal = "original_principal"
        case annualRate = "annual_rate"
        case termMonths = "term_months"
        case monthsPaid = "months_paid"
        case holdHorizonMonths = "hold_horizon_months"
    }
}

struct RankingWeightsDTO: Codable {
    let monthlyPayment: Double
    let totalCostHorizon: Double
    let breakevenMonths: Double

    enum CodingKeys: String, CodingKey {
        case monthlyPayment = "monthly_payment"
        case totalCostHorizon = "total_cost_horizon"
        case breakevenMonths = "breakeven_months"
    }
}

struct CompareCatalogRequest: Codable {
    let scenario: LoanScenarioDTO
    let lenderIds: [String]
    let weights: RankingWeightsDTO?

    enum CodingKeys: String, CodingKey {
        case scenario
        case lenderIds = "lender_ids"
        case weights
    }
}

struct CompareFullRequest: Codable {
    let scenario: LoanScenarioDTO
    let offers: [DemoOfferDTO]
    let weights: RankingWeightsDTO?
}

struct OfferMetricsDTO: Codable, Identifiable {
    var id: String { lenderId }
    let lenderId: String
    let newMonthlyPi: Double
    let closingCosts: Double
    let breakevenMonths: Double?
    let totalCostHorizon: Double
    let effectiveApr: Double

    enum CodingKeys: String, CodingKey {
        case lenderId = "lender_id"
        case newMonthlyPi = "new_monthly_pi"
        case closingCosts = "closing_costs"
        case breakevenMonths = "breakeven_months"
        case totalCostHorizon = "total_cost_horizon"
        case effectiveApr = "effective_apr"
    }
}

struct CompareResultDTO: Codable {
    let rankedLenderIds: [String]
    let metricsByLender: [String: OfferMetricsDTO]
    let baselineMonthlyPi: Double
    let currentBalance: Double

    enum CodingKeys: String, CodingKey {
        case rankedLenderIds = "ranked_lender_ids"
        case metricsByLender = "metrics_by_lender"
        case baselineMonthlyPi = "baseline_monthly_pi"
        case currentBalance = "current_balance"
    }
}

struct ExplainResponse: Codable {
    let explanation: String
    let citations: [CitationDTO]
}

struct DemoRunResponse: Codable {
    let headline: String
    let compare: CompareResultDTO
    let explain: ExplainResponse
    let market: MarketAnalysisDTO?
}

struct CitationDTO: Codable, Identifiable {
    var id: String { chunkId }
    let chunkId: String
    let text: String
    let score: Double

    enum CodingKeys: String, CodingKey {
        case chunkId = "id"
        case text
        case score
    }
}

struct MarketAreaDTO: Codable {
    let areaName: String
    let city: String
    let state: String
    let zipCode: String
    let medianListPrice: Double
    let medianPricePerSqft: Double
    let avgDaysOnMarket: Double
    let activeListingsCount: Int
    let yoyAppreciationPct: Double

    enum CodingKeys: String, CodingKey {
        case areaName = "area_name"
        case city, state
        case zipCode = "zip_code"
        case medianListPrice = "median_list_price"
        case medianPricePerSqft = "median_price_per_sqft"
        case avgDaysOnMarket = "avg_days_on_market"
        case activeListingsCount = "active_listings_count"
        case yoyAppreciationPct = "yoy_appreciation_pct"
    }
}

struct SubjectPropertyDTO: Codable {
    var propertyId: String
    var address: String
    var city: String
    var state: String
    var zipCode: String
    var beds: Int
    var baths: Double
    var sqft: Int
    var yearBuilt: Int
    var purchasePrice: Double
    var purchaseDate: String
    var estimatedValue: Double
    var askingPrice: Double?
    var condition: String

    enum CodingKeys: String, CodingKey {
        case propertyId = "property_id"
        case address, city, state, beds, baths, sqft, condition
        case zipCode = "zip_code"
        case yearBuilt = "year_built"
        case purchasePrice = "purchase_price"
        case purchaseDate = "purchase_date"
        case estimatedValue = "estimated_value"
        case askingPrice = "asking_price"
    }
}

struct PropertyListingDTO: Codable, Identifiable {
    var id: String { listingId }
    let listingId: String
    let address: String
    let beds: Int
    let baths: Double
    let sqft: Int
    let askingPrice: Double
    let daysOnMarket: Int
    let distanceMiles: Double

    enum CodingKeys: String, CodingKey {
        case listingId = "listing_id"
        case address, beds, baths, sqft
        case askingPrice = "asking_price"
        case daysOnMarket = "days_on_market"
        case distanceMiles = "distance_miles"
    }
}

struct AppreciationMetricsDTO: Codable {
    let purchasePrice: Double
    let estimatedValue: Double
    let askingPrice: Double?
    let appreciationDollars: Double
    let appreciationPct: Double
    let annualizedAppreciationPct: Double
    let yearsHeld: Double

    enum CodingKeys: String, CodingKey {
        case purchasePrice = "purchase_price"
        case estimatedValue = "estimated_value"
        case askingPrice = "asking_price"
        case appreciationDollars = "appreciation_dollars"
        case appreciationPct = "appreciation_pct"
        case annualizedAppreciationPct = "annualized_appreciation_pct"
        case yearsHeld = "years_held"
    }
}

struct EquityMetricsDTO: Codable {
    let equityDollars: Double
    let ltvPct: Double
    let equityGainSincePurchase: Double

    enum CodingKeys: String, CodingKey {
        case equityDollars = "equity_dollars"
        case ltvPct = "ltv_pct"
        case equityGainSincePurchase = "equity_gain_since_purchase"
    }
}

struct ListingComparisonDTO: Codable, Identifiable {
    var id: String { listingId }
    let listingId: String
    let address: String
    let askingPrice: Double
    let pricePerSqft: Double
    let beds: Int
    let baths: Double
    let sqft: Int
    let daysOnMarket: Int
    let vsSubjectPriceDelta: Double

    enum CodingKeys: String, CodingKey {
        case listingId = "listing_id"
        case address, beds, baths, sqft
        case askingPrice = "asking_price"
        case pricePerSqft = "price_per_sqft"
        case daysOnMarket = "days_on_market"
        case vsSubjectPriceDelta = "vs_subject_price_delta"
    }
}

struct MarketAnalysisDTO: Codable {
    let appreciation: AppreciationMetricsDTO
    let equity: EquityMetricsDTO?
    let subjectPricePerSqft: Double
    let listingComparisons: [ListingComparisonDTO]
    let summary: [String: String]

    enum CodingKeys: String, CodingKey {
        case appreciation, equity, summary
        case subjectPricePerSqft = "subject_price_per_sqft"
        case listingComparisons = "listing_comparisons"
    }
}

struct DemoListingsResponse: Codable {
    let market: MarketAreaDTO
    let subjectProperty: SubjectPropertyDTO
    let listings: [PropertyListingDTO]

    enum CodingKeys: String, CodingKey {
        case market, listings
        case subjectProperty = "subject_property"
    }
}

struct MarketAnalyzeRequest: Codable {
    let loanBalance: Double?
    let originalLoanAtPurchase: Double?
    let subject: SubjectPropertyDTO?

    enum CodingKeys: String, CodingKey {
        case loanBalance = "loan_balance"
        case originalLoanAtPurchase = "original_loan_at_purchase"
        case subject
    }
}

struct MarketLookupResponse: Codable {
    let market: MarketAreaDTO
    let subjectProperty: SubjectPropertyDTO
    let listings: [PropertyListingDTO]

    enum CodingKeys: String, CodingKey {
        case market, listings
        case subjectProperty = "subject_property"
    }
}
