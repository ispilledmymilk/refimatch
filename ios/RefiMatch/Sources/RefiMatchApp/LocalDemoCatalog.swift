import Foundation

enum LocalDemoCatalog {
    /// Bundled fallback when the API is unreachable (catalog display only).
    static let offers: [DemoOfferDTO] = [
        DemoOfferDTO(
            lenderId: "demo-aurora",
            lenderName: "Aurora Community Bank",
            apr: 0.0589,
            points: 0.0025,
            lenderFees: 3200,
            termMonths: 360,
            notes: "Balanced rate and closing costs."
        ),
        DemoOfferDTO(
            lenderId: "demo-river",
            lenderName: "River Valley Credit Union",
            apr: 0.0605,
            points: 0.0,
            lenderFees: 1800,
            termMonths: 360,
            notes: "Lower upfront fees."
        ),
        DemoOfferDTO(
            lenderId: "demo-summit",
            lenderName: "Summit Home Lending",
            apr: 0.0575,
            points: 0.01,
            lenderFees: 4500,
            termMonths: 360,
            notes: "Lowest rate; higher points."
        ),
    ]
}
