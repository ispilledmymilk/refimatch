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

    @State private var propStreet: String = "1842 Maple Ridge Dr"
    @State private var propCity: String = "Austin"
    @State private var propState: String = "TX"
    @State private var propZip: String = "78704"
    @State private var propBeds: String = "4"
    @State private var propBaths: String = "2.5"
    @State private var propSqft: String = "2180"
    @State private var propYear: String = "2008"
    @State private var propCondition: String = "good"
    @State private var purchasePrice: String = "425000"
    @State private var purchaseDate: String = "2022-04-15"
    @State private var estimatedValue: String = "512000"
    @State private var askingPrice: String = "519000"

    @State private var result: CompareResultDTO?
    @State private var explain: ExplainResponse?
    @State private var market: MarketAnalysisDTO?
    @State private var listings: [PropertyListingDTO] = []
    @State private var subjectProperty: SubjectPropertyDTO?
    @State private var headline: String?
    @State private var isLoading = false
    @State private var errorMessage: String?
    @State private var apiOnline: Bool?
    @State private var showSettings = false

    private let client = APIClient()

    var body: some View {
        NavigationStack {
            ScrollView {
                VStack(alignment: .leading, spacing: 20) {
                    heroHeader
                    disclaimerCard

                    if let headline, result != nil {
                        Text(headline)
                            .font(.headline)
                            .foregroundStyle(RefiTheme.winner)
                            .refiCard()
                    }

                    loanSection
                    propertySection
                    prioritiesSection
                    listingsSection
                    offersSection
                    actionSection

                    if let result {
                        winnerSection(result)
                        rankingSection(result)
                        chartSection(result)
                        explainSection
                        marketSection
                    }
                }
                .padding()
            }
            .background(Color(.systemGroupedBackground))
            .navigationTitle("RefiMatch")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .topBarLeading) {
                    connectionBadge
                }
                ToolbarItem(placement: .topBarTrailing) {
                    HStack(spacing: 12) {
                        if isLoading { ProgressView() }
                        Button {
                            showSettings = true
                        } label: {
                            Image(systemName: "gearshape")
                        }
                    }
                }
            }
            .sheet(isPresented: $showSettings) {
                SettingsView()
                    .environmentObject(settings)
            }
            .task {
                await bootstrap()
            }
        }
    }

    private var heroHeader: some View {
        VStack(alignment: .leading, spacing: 10) {
            Text("RefiMatch")
                .font(.largeTitle.bold())
                .foregroundStyle(.white)
            Text("Compare refinance offers with transparent math and AI-backed explanations.")
                .font(.subheadline)
                .foregroundStyle(.white.opacity(0.92))
            Label("Demo data only — not financial advice", systemImage: "info.circle")
                .font(.caption)
                .foregroundStyle(.white.opacity(0.85))
        }
        .frame(maxWidth: .infinity, alignment: .leading)
        .padding(20)
        .background(RefiTheme.heroGradient)
        .clipShape(RoundedRectangle(cornerRadius: 20, style: .continuous))
    }

    private var disclaimerCard: some View {
        Text("Educational decision-support prototype. Lender offers are synthetic for demonstration.")
            .font(.caption)
            .foregroundStyle(.secondary)
            .refiCard()
    }

    @ViewBuilder
    private var connectionBadge: some View {
        if let apiOnline {
            HStack(spacing: 6) {
                Circle()
                    .fill(apiOnline ? Color.green : Color.orange)
                    .frame(width: 8, height: 8)
                Text(apiOnline ? "API online" : "Offline")
                    .font(.caption2)
                    .foregroundStyle(.secondary)
            }
        }
    }

    private var loanSection: some View {
        VStack(alignment: .leading, spacing: 12) {
            sectionTitle("Your current loan")
            gridField("Balance", text: $principal, keyboard: .decimalPad)
            gridField("Rate (%)", text: $annualRatePercent, keyboard: .decimalPad)
            HStack {
                gridField("Term (yrs)", text: $termYears, keyboard: .numberPad)
                gridField("Paid (mo)", text: $monthsPaid, keyboard: .numberPad)
            }
            gridField("Compare horizon (yrs)", text: $holdYears, keyboard: .numberPad)
        }
        .refiCard()
    }

    private var prioritiesSection: some View {
        VStack(alignment: .leading, spacing: 12) {
            sectionTitle("What matters most?")
            prioritySlider("Lower monthly payment", value: $weightPayment)
            prioritySlider("Lower total cost", value: $weightTotalCost)
            prioritySlider("Faster breakeven", value: $weightBreakeven)
        }
        .refiCard()
    }

    private var offersSection: some View {
        VStack(alignment: .leading, spacing: 12) {
            sectionTitle("Lender offers")
            if catalog.isEmpty {
                Text("Loading offers…")
                    .foregroundStyle(.secondary)
            } else {
                ForEach(catalog) { offer in
                    offerRow(offer)
                }
            }
        }
        .refiCard()
    }

    private var actionSection: some View {
        VStack(spacing: 12) {
            Button {
                Task { await runFullAnalysis() }
            } label: {
                Label("Analyze & explain", systemImage: "sparkles")
                    .frame(maxWidth: .infinity)
            }
            .buttonStyle(.borderedProminent)
            .controlSize(.large)
            .disabled(isLoading || selected.isEmpty)

            Button {
                Task { await runQuickDemo() }
            } label: {
                Label("One-tap demo", systemImage: "play.circle")
                    .frame(maxWidth: .infinity)
            }
            .buttonStyle(.bordered)
            .disabled(isLoading)

            if let errorMessage {
                Text(errorMessage)
                    .font(.caption)
                    .foregroundStyle(.red)
                    .frame(maxWidth: .infinity, alignment: .leading)
            }
        }
    }

    @ViewBuilder
    private func winnerSection(_ result: CompareResultDTO) -> some View {
        if let top = result.rankedLenderIds.first,
           let metrics = result.metricsByLender[top] {
            VStack(alignment: .leading, spacing: 8) {
                Label("Best match", systemImage: "star.fill")
                    .font(.headline)
                    .foregroundStyle(RefiTheme.winner)
                Text(name(for: top))
                    .font(.title2.bold())
                HStack {
                    metricPill("Payment", money(metrics.newMonthlyPi))
                    metricPill("Breakeven", breakevenText(metrics.breakevenMonths))
                }
                Text("Current payment baseline: \(money(result.baselineMonthlyPi))/mo")
                    .font(.caption)
                    .foregroundStyle(.secondary)
            }
            .refiCard()
            .overlay(
                RoundedRectangle(cornerRadius: 16, style: .continuous)
                    .stroke(RefiTheme.winner.opacity(0.35), lineWidth: 2)
            )
        }
    }

    private func rankingSection(_ result: CompareResultDTO) -> some View {
        VStack(alignment: .leading, spacing: 12) {
            sectionTitle("Full ranking")
            ForEach(Array(result.rankedLenderIds.enumerated()), id: \.offset) { idx, lid in
                if let m = result.metricsByLender[lid] {
                    HStack(alignment: .top) {
                        Text("\(idx + 1)")
                            .font(.title3.bold())
                            .foregroundStyle(idx == 0 ? RefiTheme.winner : .secondary)
                            .frame(width: 28)
                        VStack(alignment: .leading, spacing: 4) {
                            Text(name(for: lid)).font(.headline)
                            Text("\(money(m.newMonthlyPi))/mo • closing \(money(m.closingCosts))")
                            Text("Horizon total \(money(m.totalCostHorizon)) • \(breakevenText(m.breakevenMonths))")
                                .font(.caption)
                                .foregroundStyle(.secondary)
                        }
                    }
                    if idx < result.rankedLenderIds.count - 1 {
                        Divider()
                    }
                }
            }
        }
        .refiCard()
    }

    private func chartSection(_ result: CompareResultDTO) -> some View {
        VStack(alignment: .leading, spacing: 12) {
            sectionTitle("Monthly payment comparison")
            Chart {
                ForEach(result.rankedLenderIds, id: \.self) { lid in
                    if let m = result.metricsByLender[lid] {
                        BarMark(
                            x: .value("Lender", shortName(lid)),
                            y: .value("Payment", m.newMonthlyPi)
                        )
                        .foregroundStyle(lid == result.rankedLenderIds.first ? RefiTheme.winner : RefiTheme.accent)
                    }
                }
            }
            .frame(height: 220)
        }
        .refiCard()
    }

    private var propertySection: some View {
        VStack(alignment: .leading, spacing: 12) {
            sectionTitle("Your property")
            gridField("Street", text: $propStreet, keyboard: .default)
            HStack {
                gridField("City", text: $propCity, keyboard: .default)
                gridField("Prov/State", text: $propState, keyboard: .default)
            }
            HStack {
                gridField("Postal/ZIP", text: $propZip, keyboard: .default)
                VStack(alignment: .leading, spacing: 4) {
                    Text("Condition").font(.caption).foregroundStyle(.secondary)
                    Picker("Condition", selection: $propCondition) {
                        Text("Fair").tag("fair")
                        Text("Good").tag("good")
                        Text("Excellent").tag("excellent")
                    }
                    .pickerStyle(.menu)
                }
            }
            HStack {
                gridField("Beds", text: $propBeds, keyboard: .numberPad)
                gridField("Baths", text: $propBaths, keyboard: .decimalPad)
            }
            HStack {
                gridField("Sqft", text: $propSqft, keyboard: .numberPad)
                gridField("Year built", text: $propYear, keyboard: .numberPad)
            }
            gridField("Purchase price", text: $purchasePrice, keyboard: .decimalPad)
            gridField("Purchase date (YYYY-MM-DD)", text: $purchaseDate, keyboard: .numbersAndPunctuation)
            HStack {
                gridField("Est. value", text: $estimatedValue, keyboard: .decimalPad)
                gridField("Asking (opt)", text: $askingPrice, keyboard: .decimalPad)
            }
            Button {
                Task { await lookupPropertyMarket() }
            } label: {
                Label("Lookup comps & appreciation", systemImage: "mappin.and.ellipse")
                    .frame(maxWidth: .infinity)
            }
            .buttonStyle(.bordered)
            .disabled(isLoading)
        }
        .refiCard()
    }

    private var listingsSection: some View {
        VStack(alignment: .leading, spacing: 12) {
            sectionTitle("Nearby listings")
            if listings.isEmpty {
                Text("Loading listings…")
                    .foregroundStyle(.secondary)
            } else {
                ForEach(listings.prefix(4)) { listing in
                    VStack(alignment: .leading, spacing: 4) {
                        Text(listing.address).font(.subheadline.bold())
                        Text("\(money(listing.askingPrice)) · \(listing.beds)bd · \(listing.sqft) sqft · \(listing.daysOnMarket) DOM")
                            .font(.caption)
                            .foregroundStyle(.secondary)
                    }
                    .padding(.vertical, 4)
                }
            }
        }
        .refiCard()
    }

    private var explainSection: some View {
        VStack(alignment: .leading, spacing: 12) {
            sectionTitle("AI summary")
            if let explain {
                Text(explain.explanation)
                    .font(.body)
                if !explain.citations.isEmpty {
                    Text("Sources")
                        .font(.subheadline.bold())
                    ForEach(explain.citations.prefix(3)) { c in
                        Text("• \(c.text)")
                            .font(.caption)
                            .foregroundStyle(.secondary)
                    }
                }
            } else {
                Text("Run analysis to generate a grounded explanation.")
                    .foregroundStyle(.secondary)
            }
        }
        .refiCard()
    }

    @ViewBuilder
    private var marketSection: some View {
        if let market {
            VStack(alignment: .leading, spacing: 12) {
                sectionTitle("Property & market analysis")
                if let headline = market.summary["headline"] {
                    Text(headline)
                        .font(.headline)
                        .foregroundStyle(RefiTheme.winner)
                }
                HStack {
                    metricPill("Appreciation", money(market.appreciation.appreciationDollars))
                    metricPill("Annualized", percent(market.appreciation.annualizedAppreciationPct))
                }
                if let equity = market.equity {
                    HStack {
                        metricPill("Equity", money(equity.equityDollars))
                        metricPill("LTV", percent(equity.ltvPct))
                    }
                }
                Text("Your home: $\(Int(market.subjectPricePerSqft))/sqft")
                    .font(.caption)
                    .foregroundStyle(.secondary)
                Text("Nearby comps")
                    .font(.subheadline.bold())
                ForEach(market.listingComparisons.prefix(3)) { comp in
                    VStack(alignment: .leading, spacing: 2) {
                        Text(comp.address).font(.caption.bold())
                        Text("\(money(comp.askingPrice)) · \(money(comp.vsSubjectPriceDelta)) vs your estimate")
                            .font(.caption2)
                            .foregroundStyle(.secondary)
                    }
                }
            }
            .refiCard()
        }
    }

    @ViewBuilder
    private func offerRow(_ offer: DemoOfferDTO) -> some View {
        VStack(alignment: .leading, spacing: 8) {
            Toggle(isOn: Binding(
                get: { selected.contains(offer.lenderId) },
                set: { on in
                    if on { selected.insert(offer.lenderId) } else { selected.remove(offer.lenderId) }
                }
            )) {
                VStack(alignment: .leading, spacing: 4) {
                    Text(offer.lenderName).font(.headline)
                    Text("APR \(percent(offer.apr)) • fees \(money(offer.lenderFees))")
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
            }
        }
        .padding(.vertical, 4)
    }

    private func sectionTitle(_ text: String) -> some View {
        Text(text).font(.headline)
    }

    private func gridField(_ label: String, text: Binding<String>, keyboard: UIKeyboardType) -> some View {
        VStack(alignment: .leading, spacing: 4) {
            Text(label).font(.caption).foregroundStyle(.secondary)
            TextField(label, text: text)
                .keyboardType(keyboard)
                .padding(10)
                .background(Color(.tertiarySystemGroupedBackground))
                .clipShape(RoundedRectangle(cornerRadius: 10, style: .continuous))
        }
    }

    private func prioritySlider(_ label: String, value: Binding<Double>) -> some View {
        VStack(alignment: .leading, spacing: 4) {
            Text(label).font(.caption)
            Slider(value: value, in: 0 ... 1, step: 0.05)
        }
    }

    private func metricPill(_ title: String, _ value: String) -> some View {
        VStack(alignment: .leading, spacing: 2) {
            Text(title).font(.caption2).foregroundStyle(.secondary)
            Text(value).font(.subheadline.bold())
        }
        .padding(.horizontal, 10)
        .padding(.vertical, 6)
        .background(RefiTheme.accentSoft)
        .clipShape(RoundedRectangle(cornerRadius: 8, style: .continuous))
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
        String(format: "%.2f%%", frac * 100)
    }

    private func money(_ v: Double) -> String {
        let f = NumberFormatter()
        f.numberStyle = .currency
        f.maximumFractionDigits = 0
        return f.string(from: NSNumber(value: v)) ?? "\(Int(v))"
    }

    private func breakevenText(_ months: Double?) -> String {
        guard let months, months.isFinite else { return "Breakeven n/a" }
        return "Breakeven \(Int(ceil(months))) mo"
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
        return LoanScenarioDTO(
            originalPrincipal: p,
            annualRate: r / 100.0,
            termMonths: Int(ty * 12),
            monthsPaid: max(0, mp),
            holdHorizonMonths: hy * 12
        )
    }

    private func bootstrap() async {
        apiOnline = await client.healthCheck(baseURL: settings.apiBaseURL)
        await loadListings()
        await loadCatalog()
    }

    private func loadListings() async {
        do {
            let data = try await client.fetchDemoListings(baseURL: settings.apiBaseURL)
            listings = data.listings
            subjectProperty = data.subjectProperty
            applySubjectToForm(data.subjectProperty)
        } catch {
            listings = []
        }
    }

    private func applySubjectToForm(_ s: SubjectPropertyDTO) {
        propStreet = s.address
        propCity = s.city
        propState = s.state
        propZip = s.zipCode
        propBeds = "\(s.beds)"
        propBaths = String(format: "%g", s.baths)
        propSqft = "\(s.sqft)"
        propYear = "\(s.yearBuilt)"
        propCondition = s.condition
        purchasePrice = String(Int(s.purchasePrice))
        purchaseDate = String(s.purchaseDate.prefix(10))
        estimatedValue = String(Int(s.estimatedValue))
        askingPrice = s.askingPrice.map { String(Int($0)) } ?? ""
    }

    private func parseSubjectFromForm() throws -> SubjectPropertyDTO {
        guard !propStreet.trimmingCharacters(in: .whitespaces).isEmpty,
              !propCity.trimmingCharacters(in: .whitespaces).isEmpty,
              !propState.trimmingCharacters(in: .whitespaces).isEmpty else {
            throw URLError(.badURL)
        }
        guard let beds = Int(propBeds),
              let baths = Double(propBaths),
              let sqft = Int(propSqft), sqft > 0,
              let year = Int(propYear),
              let purchase = Double(purchasePrice), purchase > 0 else {
            throw URLError(.badURL)
        }
        let est = Double(estimatedValue) ?? purchase
        let ask = Double(askingPrice)
        return SubjectPropertyDTO(
            propertyId: "user-home",
            address: propStreet.trimmingCharacters(in: .whitespaces),
            city: propCity.trimmingCharacters(in: .whitespaces),
            state: propState.trimmingCharacters(in: .whitespaces).uppercased(),
            zipCode: propZip.trimmingCharacters(in: .whitespaces).isEmpty ? "00000" : propZip,
            beds: beds,
            baths: baths,
            sqft: sqft,
            yearBuilt: year,
            purchasePrice: purchase,
            purchaseDate: purchaseDate,
            estimatedValue: est,
            askingPrice: ask,
            condition: propCondition
        )
    }

    private func lookupPropertyMarket() async {
        isLoading = true
        errorMessage = nil
        defer { isLoading = false }
        do {
            let subject = try parseSubjectFromForm()
            let data = try await client.lookupMarket(baseURL: settings.apiBaseURL, subject: subject)
            listings = data.listings
            subjectProperty = data.subjectProperty
            applySubjectToForm(data.subjectProperty)
            apiOnline = true
        } catch {
            errorMessage = friendlyError(error)
        }
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
            apiOnline = true
        } catch {
            catalog = LocalDemoCatalog.offers
            selected = Set(catalog.map(\.lenderId))
            apiOnline = false
            errorMessage = "Using bundled offers. Start the API to run analysis."
        }
    }

    private func runFullAnalysis() async {
        isLoading = true
        errorMessage = nil
        explain = nil
        market = nil
        headline = nil
        defer { isLoading = false }
        do {
            if catalog.isEmpty { await loadCatalog() }
            let scenario = try parseScenario()
            let offers: [DemoOfferDTO] = Array(selected).compactMap { lid in
                guard let base = catalog.first(where: { $0.lenderId == lid }) else { return nil }
                return overrides[lid] ?? base
            }
            let req = CompareFullRequest(scenario: scenario, offers: offers, weights: normalizedWeights())
            let compareResult = try await client.compare(baseURL: settings.apiBaseURL, body: req)
            result = compareResult
            if let top = compareResult.rankedLenderIds.first {
                headline = "Top pick: \(name(for: top))"
            }
            explain = try await client.explain(
                baseURL: settings.apiBaseURL,
                compareResult: compareResult,
                question: "Explain this ranking for a homeowner in plain language."
            )
            market = try await client.analyzeMarket(
                baseURL: settings.apiBaseURL,
                loanBalance: compareResult.currentBalance,
                originalLoanAtPurchase: scenario.originalPrincipal,
                subject: try parseSubjectFromForm()
            )
            apiOnline = true
        } catch {
            errorMessage = friendlyError(error)
        }
    }

    private func runQuickDemo() async {
        isLoading = true
        errorMessage = nil
        market = nil
        defer { isLoading = false }
        do {
            let demo = try await client.runDemo(baseURL: settings.apiBaseURL)
            result = demo.compare
            explain = demo.explain
            market = demo.market
            headline = demo.headline
            if catalog.isEmpty { await loadCatalog() }
            apiOnline = true
        } catch {
            errorMessage = friendlyError(error)
        }
    }

    private func friendlyError(_ error: Error) -> String {
        if let api = error as? APIError {
            return api.localizedDescription
        }
        return "Could not reach the API. In Settings, confirm the base URL and that uvicorn is running."
    }
}

#Preview {
    ContentView()
        .environmentObject(AppSettings())
}
