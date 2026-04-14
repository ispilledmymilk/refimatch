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
