import Foundation

enum APIError: Error, LocalizedError {
    case invalidURL
    case badStatus(Int, String)
    case decoding(Error)

    var errorDescription: String? {
        switch self {
        case .invalidURL:
            return "Invalid URL"
        case let .badStatus(code, body):
            return "HTTP \(code): \(body)"
        case let .decoding(err):
            return "Decoding failed: \(err.localizedDescription)"
        }
    }
}

final class APIClient {
    private let session: URLSession
    private let encoder: JSONEncoder
    private let decoder: JSONDecoder

    init(session: URLSession = .shared) {
        self.session = session
        self.encoder = JSONEncoder()
        self.encoder.keyEncodingStrategy = .convertToSnakeCase
        self.decoder = JSONDecoder()
        self.decoder.keyDecodingStrategy = .convertFromSnakeCase
    }

    func healthCheck(baseURL: String) async -> Bool {
        guard let url = try? Self.makeURL(baseURL: baseURL, path: "/health") else { return false }
        do {
            let (_, response) = try await session.data(from: url)
            guard let http = response as? HTTPURLResponse else { return false }
            return (200 ... 299).contains(http.statusCode)
        } catch {
            return false
        }
    }

    func fetchDemoOffers(baseURL: String) async throws -> [DemoOfferDTO] {
        let url = try Self.makeURL(baseURL: baseURL, path: "/v1/catalog/demo-offers")
        let (data, response) = try await session.data(from: url)
        try Self.throwIfNeeded(response: response, data: data)
        struct Wrap: Codable { let offers: [DemoOfferDTO] }
        do {
            return try decoder.decode(Wrap.self, from: data).offers
        } catch {
            throw APIError.decoding(error)
        }
    }

    func runDemo(baseURL: String) async throws -> DemoRunResponse {
        let url = try Self.makeURL(baseURL: baseURL, path: "/v1/demo/run")
        var req = URLRequest(url: url)
        req.httpMethod = "POST"
        req.setValue("application/json", forHTTPHeaderField: "Content-Type")
        req.httpBody = Data("{}".utf8)
        let (data, response) = try await session.data(for: req)
        try Self.throwIfNeeded(response: response, data: data)
        do {
            return try decoder.decode(DemoRunResponse.self, from: data)
        } catch {
            throw APIError.decoding(error)
        }
    }

    func compareCatalog(baseURL: String, body: CompareCatalogRequest) async throws -> CompareResultDTO {
        let url = try Self.makeURL(baseURL: baseURL, path: "/v1/compare/catalog-selection")
        var req = URLRequest(url: url)
        req.httpMethod = "POST"
        req.setValue("application/json", forHTTPHeaderField: "Content-Type")
        req.httpBody = try encoder.encode(body)
        let (data, response) = try await session.data(for: req)
        try Self.throwIfNeeded(response: response, data: data)
        do {
            return try decoder.decode(CompareResultDTO.self, from: data)
        } catch {
            throw APIError.decoding(error)
        }
    }

    func compare(baseURL: String, body: CompareFullRequest) async throws -> CompareResultDTO {
        let url = try Self.makeURL(baseURL: baseURL, path: "/v1/compare")
        var req = URLRequest(url: url)
        req.httpMethod = "POST"
        req.setValue("application/json", forHTTPHeaderField: "Content-Type")
        req.httpBody = try encoder.encode(body)
        let (data, response) = try await session.data(for: req)
        try Self.throwIfNeeded(response: response, data: data)
        do {
            return try decoder.decode(CompareResultDTO.self, from: data)
        } catch {
            throw APIError.decoding(error)
        }
    }

    func explain(baseURL: String, compareResult: CompareResultDTO, question: String?) async throws -> ExplainResponse {
        let url = try Self.makeURL(baseURL: baseURL, path: "/v1/explain")
        var req = URLRequest(url: url)
        req.httpMethod = "POST"
        req.setValue("application/json", forHTTPHeaderField: "Content-Type")

        struct ExplainBody: Encodable {
            let compareResult: CompareResultDTO
            let userQuestion: String?
        }

        let body = ExplainBody(compareResult: compareResult, userQuestion: question)
        let enc = JSONEncoder()
        enc.keyEncodingStrategy = .convertToSnakeCase
        req.httpBody = try enc.encode(body)

        let (data, response) = try await session.data(for: req)
        try Self.throwIfNeeded(response: response, data: data)
        do {
            return try decoder.decode(ExplainResponse.self, from: data)
        } catch {
            throw APIError.decoding(error)
        }
    }

    func fetchDemoListings(baseURL: String) async throws -> DemoListingsResponse {
        let url = try Self.makeURL(baseURL: baseURL, path: "/v1/catalog/demo-listings")
        let (data, response) = try await session.data(from: url)
        try Self.throwIfNeeded(response: response, data: data)
        do {
            return try decoder.decode(DemoListingsResponse.self, from: data)
        } catch {
            throw APIError.decoding(error)
        }
    }

    func analyzeMarket(
        baseURL: String,
        loanBalance: Double?,
        originalLoanAtPurchase: Double?,
        subject: SubjectPropertyDTO?
    ) async throws -> MarketAnalysisDTO {
        let url = try Self.makeURL(baseURL: baseURL, path: "/v1/market/analyze")
        var req = URLRequest(url: url)
        req.httpMethod = "POST"
        req.setValue("application/json", forHTTPHeaderField: "Content-Type")
        req.httpBody = try encoder.encode(
            MarketAnalyzeRequest(
                loanBalance: loanBalance,
                originalLoanAtPurchase: originalLoanAtPurchase,
                subject: subject
            )
        )
        let (data, response) = try await session.data(for: req)
        try Self.throwIfNeeded(response: response, data: data)
        do {
            return try decoder.decode(MarketAnalysisDTO.self, from: data)
        } catch {
            throw APIError.decoding(error)
        }
    }

    func lookupMarket(baseURL: String, subject: SubjectPropertyDTO) async throws -> MarketLookupResponse {
        let url = try Self.makeURL(baseURL: baseURL, path: "/v1/market/lookup")
        var req = URLRequest(url: url)
        req.httpMethod = "POST"
        req.setValue("application/json", forHTTPHeaderField: "Content-Type")
        req.httpBody = try encoder.encode(MarketAnalyzeRequest(
            loanBalance: nil,
            originalLoanAtPurchase: nil,
            subject: subject
        ))
        let (data, response) = try await session.data(for: req)
        try Self.throwIfNeeded(response: response, data: data)
        do {
            return try decoder.decode(MarketLookupResponse.self, from: data)
        } catch {
            throw APIError.decoding(error)
        }
    }

    private static func makeURL(baseURL: String, path: String) throws -> URL {
        let trimmed = baseURL.trimmingCharacters(in: .whitespacesAndNewlines).trimmingCharacters(in: CharacterSet(charactersIn: "/"))
        guard let url = URL(string: trimmed + path) else { throw APIError.invalidURL }
        return url
    }

    private static func throwIfNeeded(response: URLResponse, data: Data) throws {
        guard let http = response as? HTTPURLResponse else { return }
        guard (200 ... 299).contains(http.statusCode) else {
            let body = String(data: data, encoding: .utf8) ?? ""
            throw APIError.badStatus(http.statusCode, body)
        }
    }
}
