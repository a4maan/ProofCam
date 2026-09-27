// swift-tools-version: 5.9
import PackageDescription
let package = Package(
    name: "ProofCamCore",
    products: [.library(name: "ProofCamCore", targets: ["ProofCamCore"]),
               .executable(name: "CoreParity", targets: ["CoreParity"])],
    targets: [.target(name: "ProofCamCore"),
              .executableTarget(name: "CoreParity", dependencies: ["ProofCamCore"]),
              .testTarget(name: "ProofCamCoreTests", dependencies: ["ProofCamCore"])])
