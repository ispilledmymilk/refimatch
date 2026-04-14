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
