// swift-tools-version: 5.10
import PackageDescription

let package = Package(
    name: "RefiMatch",
    platforms: [
        .iOS(.v17),
    ],
    products: [
        .executable(name: "RefiMatchApp", targets: ["RefiMatchApp"]),
    ],
    targets: [
        .executableTarget(
            name: "RefiMatchApp",
            path: "Sources/RefiMatchApp",
            resources: [.process("Resources")]
        ),
    ]
)
