import SwiftUI

struct SettingsView: View {
    @EnvironmentObject private var settings: AppSettings
    @Environment(\.dismiss) private var dismiss

    var body: some View {
        NavigationStack {
            Form {
                Section {
                    TextField("API base URL", text: $settings.apiBaseURL)
                        .textInputAutocapitalization(.never)
                        .keyboardType(.URL)
                    Text("Simulator: http://127.0.0.1:8080")
                        .font(.caption)
                        .foregroundStyle(.secondary)
                    Text("Physical device: use your Mac’s LAN IP, e.g. http://192.168.1.10:8080")
                        .font(.caption)
                        .foregroundStyle(.secondary)
                } header: {
                    Text("Backend")
                }

                Section {
                    Button("Reset to defaults") {
                        settings.apiBaseURL = AppSettings.defaultBaseURL
                    }
                }
            }
            .navigationTitle("Settings")
            .toolbar {
                ToolbarItem(placement: .confirmationAction) {
                    Button("Done") { dismiss() }
                }
            }
        }
    }
}
