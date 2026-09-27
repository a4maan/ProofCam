#!/bin/bash
set -euo pipefail
cd "$(dirname "$0")/.."
xcodebuild -version
swift test --package-path Core -c release
xcodebuild -project ProofCamResearch.xcodeproj -scheme ProofCamResearch -configuration Release -sdk iphonesimulator -destination 'generic/platform=iOS Simulator' -derivedDataPath DerivedData CODE_SIGNING_ALLOWED=NO build
