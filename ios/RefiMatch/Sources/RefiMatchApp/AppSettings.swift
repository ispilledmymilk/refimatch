import Foundation

final class AppSettings: ObservableObject {
    static let defaultBaseURL = "http://127.0.0.1:8080"

    @Published var apiBaseURL: String {
        didSet { UserDefaults.standard.set(apiBaseURL, forKey: Self.baseURLKey) }
    }

    private static let baseURLKey = "refimatch.apiBaseURL"

    init() {
        let saved = UserDefaults.standard.string(forKey: Self.baseURLKey)
        self.apiBaseURL = saved ?? Self.defaultBaseURL
    }
}
