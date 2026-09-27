#!/bin/bash
set -euo pipefail
cd "$(dirname "$0")/.."
if [[ "$(uname -s)" != Darwin ]]; then
    echo "This validation requires macOS and Xcode." >&2
    exit 2
fi
xcodebuild -version
swift test --package-path Core -c debug
swift test --package-path Core -c release
xcodebuild -project ProofCamResearch.xcodeproj -scheme ProofCamResearch -configuration Release -sdk iphonesimulator -destination 'generic/platform=iOS Simulator' -derivedDataPath DerivedData CODE_SIGNING_ALLOWED=NO build
