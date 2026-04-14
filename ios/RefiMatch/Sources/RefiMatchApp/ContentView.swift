import Charts
import SwiftUI

struct ContentView: View {
    @EnvironmentObject private var settings: AppSettings
    @State private var catalog: [DemoOfferDTO] = []
    @State private var selected: Set<String> = []
    @State private var overrides: [String: DemoOfferDTO] = [:]

    @State private var principal: String = "350000"
    @State private var annualRatePercent: String = "6.75"
    @State private var termYears: String = "30"
    @State private var monthsPaid: String = "48"
    @State private var holdYears: String = "5"

    @State private var weightPayment: Double = 0.34
    @State private var weightTotalCost: Double = 0.33
    @State private var weightBreakeven: Double = 0.33

    @State private var result: CompareResultDTO?
    @State private var explain: ExplainResponse?
    @State private var isLoading = false
    @State private var errorMessage: String?

    private let client = APIClient()

    var body: some View {
        NavigationStack {
            Form {
                Section("API") {
                    TextField("Base URL", text: $settings.apiBaseURL)
                        .textInputAutocapitalization(.never)
                        .keyboardType(.URL)
                }

                Section("Your loan") {
                    TextField("Original principal", text: $principal)
                        .keyboardType(.decimalPad)
                    TextField("Current rate (%)", text: $annualRatePercent)
                        .keyboardType(.decimalPad)
                    TextField("Original term (years)", text: $termYears)
                        .keyboardType(.numberPad)
                    TextField("Months paid", text: $monthsPaid)
                        .keyboardType(.numberPad)
                    TextField("Compare horizon (years)", text: $holdYears)
                        .keyboardType(.numberPad)
                }

                Section("What matters more? (0–1 each)") {
                    VStack(alignment: .leading) {
                        Text("Lower monthly payment")
                        Slider(value: $weightPayment, in: 0 ... 1, step: 0.05)
                    }
                    VStack(alignment: .leading) {
                        Text("Lower total cost over horizon")
                        Slider(value: $weightTotalCost, in: 0 ... 1, step: 0.05)
                    }
                    VStack(alignment: .leading) {
                        Text("Faster breakeven")
                        Slider(value: $weightBreakeven, in: 0 ... 1, step: 0.05)
                    }
                }

                Section("Demo offers") {
                    if catalog.isEmpty {
                        Button("Load catalog") { Task { await loadCatalog() } }
                    } else {
                        ForEach(catalog) { offer in
                            VStack(alignment: .leading, spacing: 8) {
                                Toggle(isOn: Binding(
                                    get: { selected.contains(offer.lenderId) },
                                    set: { on in
                                        if on { selected.insert(offer.lenderId) } else { selected.remove(offer.lenderId) }
                                    }
                                )) {
                                    VStack(alignment: .leading) {
                                        Text(offer.lenderName).font(.headline)
                                        Text("APR \(percent(offer.apr)) • fees \(money(offer.lenderFees)) • points \(percent(offer.points))")
                                            .font(.caption)
                                            .foregroundStyle(.secondary)
                                    }
                                }

                                if selected.contains(offer.lenderId) {
                                    let o = overrides[offer.lenderId] ?? offer
                                    HStack {
                                        Text("APR %")
                                        TextField("APR", value: Binding(
                                            get: { o.apr * 100 },
                                            set: { overrides[offer.lenderId] = o.patched(apr: $0 / 100) }
                                        ), format: .number.precision(.fractionLength(3)))
                                        .keyboardType(.decimalPad)
                                    }
                                    HStack {
                                        Text("Fees")
                                        TextField("Fees", value: Binding(
                                            get: { o.lenderFees },
                                            set: { overrides[offer.lenderId] = o.patched(fees: $0) }
                                        ), format: .number.precision(.fractionLength(0)))
                                        .keyboardType(.numberPad)
                                    }
                                }
                            }
                        }
                    }
                }

                Section {
                    Button("Compare") { Task { await runCompare() } }
                        .disabled(isLoading || selected.isEmpty)
                    if let errorMessage {
                        Text(errorMessage).foregroundStyle(.red)
                    }
                }

                if let result {
                    Section("Ranking") {
                        ForEach(Array(result.rankedLenderIds.enumerated()), id: \.offset) { idx, lid in
                            if let m = result.metricsByLender[lid] {
                                VStack(alignment: .leading, spacing: 4) {
                                    Text("#\(idx + 1) \(name(for: lid))").font(.headline)
                                    Text("New payment \(money(m.newMonthlyPi)) / mo")
                                    Text("Closing \(money(m.closingCosts))")
                                    if let be = m.breakevenMonths {
                                        Text("Breakeven \(Int(ceil(be))) mo")
                                    } else {
                                        Text("Breakeven n/a")
                                    }
                                    Text("Horizon total \(money(m.totalCostHorizon))")
                                        .font(.caption)
                                        .foregroundStyle(.secondary)
                                }
                                .padding(.vertical, 4)
                            }
                        }
                    }

                    Section("Chart (new payment)") {
                        Chart {
                            ForEach(result.rankedLenderIds, id: \.self) { lid in
                                if let m = result.metricsByLender[lid] {
                                    BarMark(
                                        x: .value("Lender", shortName(lid)),
                                        y: .value("Payment", m.newMonthlyPi)
                                    )
                                }
                            }
                        }
                        .frame(height: 220)
                    }

                    Section("Why this order?") {
                        Button("Generate explanation") { Task { await runExplain() } }
                            .disabled(isLoading)
                        if let explain {
                            Text(explain.explanation)
                            if !explain.citations.isEmpty {
                                Text("Citations").font(.headline)
                                ForEach(explain.citations) { c in
                                    VStack(alignment: .leading, spacing: 6) {
                                        Text(c.text).font(.caption)
                                        Text("id: \(c.chunkId) • score: \(String(format: "%.3f", c.score))")
                                            .font(.caption2)
                                            .foregroundStyle(.secondary)
                                    }
                                    .padding(.vertical, 4)
                                }
                            }
                        }
                    }
                }
            }
            .navigationTitle("RefiMatch")
            .toolbar {
                ToolbarItem(placement: .topBarTrailing) {
                    if isLoading { ProgressView() }
                }
            }
        }
    }

    private func name(for lenderId: String) -> String {
        catalog.first(where: { $0.lenderId == lenderId })?.lenderName ?? lenderId
    }

    private func shortName(_ lenderId: String) -> String {
        let n = name(for: lenderId)
        if n.count <= 14 { return n }
        return String(n.prefix(12)) + "…"
    }

    private func percent(_ frac: Double) -> String {
        String(format: "%.3f%%", frac * 100)
    }

    private func money(_ v: Double) -> String {
        let f = NumberFormatter()
        f.numberStyle = .currency
        f.maximumFractionDigits = 0
        return f.string(from: NSNumber(value: v)) ?? "\(Int(v))"
    }

    private func normalizedWeights() -> RankingWeightsDTO {
        let a = max(weightPayment, 0)
        let b = max(weightTotalCost, 0)
        let c = max(weightBreakeven, 0)
        let s = a + b + c
        let ss = s == 0 ? 1.0 : s
        return RankingWeightsDTO(monthlyPayment: a / ss, totalCostHorizon: b / ss, breakevenMonths: c / ss)
    }

    private func parseScenario() throws -> LoanScenarioDTO {
        guard let p = Double(principal), p > 0 else { throw URLError(.badURL) }
        guard let r = Double(annualRatePercent), r > 0 else { throw URLError(.badURL) }
        guard let ty = Double(termYears), ty > 0 else { throw URLError(.badURL) }
        guard let mp = Int(monthsPaid) else { throw URLError(.badURL) }
        guard let hy = Int(holdYears), hy > 0 else { throw URLError(.badURL) }
        let termMonths = Int(ty * 12)
        return LoanScenarioDTO(
            originalPrincipal: p,
            annualRate: r / 100.0,
            termMonths: termMonths,
            monthsPaid: max(0, mp),
            holdHorizonMonths: hy * 12
        )
    }

    private func loadCatalog() async {
        isLoading = true
        errorMessage = nil
        defer { isLoading = false }
        do {
            catalog = try await client.fetchDemoOffers(baseURL: settings.apiBaseURL)
            if selected.isEmpty {
                selected = Set(catalog.map(\.lenderId))
            }
        } catch {
            errorMessage = error.localizedDescription
        }
    }

    private func runCompare() async {
        isLoading = true
        errorMessage = nil
        explain = nil
        defer { isLoading = false }
        do {
            if catalog.isEmpty {
                try await Task.sleep(nanoseconds: 1)
            }
            if catalog.isEmpty {
                catalog = try await client.fetchDemoOffers(baseURL: settings.apiBaseURL)
            }
            let scenario = try parseScenario()
            let offers: [DemoOfferDTO] = Array(selected).compactMap { lid in
                guard let base = catalog.first(where: { $0.lenderId == lid }) else { return nil }
                return overrides[lid] ?? base
            }
            guard offers.count == selected.count else {
                errorMessage = "Missing catalog entries for selection."
                return
            }
            let req = CompareFullRequest(scenario: scenario, offers: offers, weights: normalizedWeights())
            result = try await client.compare(baseURL: settings.apiBaseURL, body: req)
        } catch {
            errorMessage = error.localizedDescription
        }
    }

    private func runExplain() async {
        guard let result else { return }
        isLoading = true
        errorMessage = nil
        defer { isLoading = false }
        do {
            explain = try await client.explain(
                baseURL: settings.apiBaseURL,
                compareResult: result,
                question: "Explain the ranking in plain language for a homeowner."
            )
        } catch {
            errorMessage = error.localizedDescription
        }
    }
}

#Preview {
    ContentView()
        .environmentObject(AppSettings())
}
