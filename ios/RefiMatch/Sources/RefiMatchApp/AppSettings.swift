import Foundation

final class AppSettings: ObservableObject {
    @Published var apiBaseURL: String {
        didSet { UserDefaults.standard.set(apiBaseURL, forKey: Self.baseURLKey) }
    }

    private static let baseURLKey = "refimatch.apiBaseURL"

    init() {
        let saved = UserDefaults.standard.string(forKey: Self.baseURLKey)
        self.apiBaseURL = saved ?? "http://127.0.0.1:8080"
    }
}
