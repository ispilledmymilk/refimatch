import SwiftUI

enum RefiTheme {
    static let accent = Color(red: 0.11, green: 0.42, blue: 0.72)
    static let accentSoft = Color(red: 0.88, green: 0.94, blue: 0.99)
    static let winner = Color(red: 0.12, green: 0.58, blue: 0.42)
    static let cardBackground = Color(.secondarySystemGroupedBackground)
    static let heroGradient = LinearGradient(
        colors: [
            Color(red: 0.08, green: 0.22, blue: 0.45),
            Color(red: 0.11, green: 0.42, blue: 0.72),
        ],
        startPoint: .topLeading,
        endPoint: .bottomTrailing
    )
}

struct CardModifier: ViewModifier {
    func body(content: Content) -> some View {
        content
            .padding()
            .background(RefiTheme.cardBackground)
            .clipShape(RoundedRectangle(cornerRadius: 16, style: .continuous))
            .shadow(color: .black.opacity(0.06), radius: 8, y: 4)
    }
}

extension View {
    func refiCard() -> some View {
        modifier(CardModifier())
    }
}
