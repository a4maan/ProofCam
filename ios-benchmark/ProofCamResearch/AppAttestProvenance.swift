import Foundation
import CryptoKit
import DeviceCheck
import Security

/// Opt-in Apple calls. Free Personal Team builds retain basic research capture.
@MainActor enum AppAttestDeviceKey {
    enum Failure: Error { case notConfigured, unsupported, keychain, invalidResponse }
    static var enabled: Bool {
        let setting = Bundle.main.object(forInfoDictionaryKey: "ProofCamAppAttestEnabled")
        return setting as? Bool == true || setting as? String == "YES"
    }
    static func identifier() async throws -> String {
        guard enabled else { throw Failure.notConfigured }
        guard DCAppAttestService.shared.isSupported else { throw Failure.unsupported }
        let query: [String: Any] = [kSecClass as String: kSecClassGenericPassword,
                                  kSecAttrService as String: "ProofCam.AppAttest.Development.v1",
                                  kSecAttrAccount as String: "key-id", kSecAttrSynchronizable as String: false]
        var lookup = query; lookup[kSecReturnData as String] = true
        var value: CFTypeRef?
        let status = SecItemCopyMatching(lookup as CFDictionary, &value)
        if status == errSecSuccess, let data = value as? Data, let id = String(data: data, encoding: .utf8), Data(base64Encoded: id)?.count == 32 { return id }
        guard status == errSecItemNotFound else { throw Failure.keychain }
        let id: String = try await withCheckedThrowingContinuation { continuation in
            DCAppAttestService.shared.generateKey { id, error in
                if let error { continuation.resume(throwing: error) }
                else if let id { continuation.resume(returning: id) }
                else { continuation.resume(throwing: Failure.invalidResponse) }
            }
        }
        guard Data(base64Encoded: id)?.count == 32 else { throw Failure.invalidResponse }
        var item = query; item[kSecValueData as String] = Data(id.utf8)
        item[kSecAttrAccessible as String] = kSecAttrAccessibleWhenUnlockedThisDeviceOnly
        guard SecItemAdd(item as CFDictionary, nil) == errSecSuccess else { throw Failure.keychain }
        return id
    }
}

private struct AppAttestChallenge: Decodable {
    let nonce: Data
    let expires: Int64
    let session: String
    let purpose: String
    static func read(_ url: URL, purpose: String) throws -> Self {
        let accessed = url.startAccessingSecurityScopedResource()
        defer { if accessed { url.stopAccessingSecurityScopedResource() } }
        let handle = try FileHandle(forReadingFrom: url); defer { try? handle.close() }
        let data = try ResearchUtilities.readBounded(limit: 4096) { try handle.read(upToCount: $0) ?? Data() }
        let challenge = try JSONDecoder().decode(Self.self, from: data)
        guard challenge.nonce.count == 32, challenge.purpose == purpose, challenge.expires > 0 else { throw ProvenanceWire.Invalid.identifier }
        _ = try ProvenanceWire.challengeRequest(session: challenge.session, purpose: purpose)
        // Server time, session/installation binding and expiry are authoritative.
        return challenge
    }
}

extension CaptureProvenance {
    func appAttestChallengeRequest(purpose: String) throws -> Data {
        guard AppAttestDeviceKey.enabled else { throw AppAttestDeviceKey.Failure.notConfigured }
        let payload = try ProvenanceWire.challengeRequest(session: CaptureKey.identifier(), purpose: purpose)
        return try CaptureKey.signed(payload, key: CaptureKey.load(), purpose: "challenge")
    }

    func appAttestExport(from url: URL, capture: PendingCapture?) async throws -> Data {
        guard !busy else { throw AppAttestDeviceKey.Failure.invalidResponse }
        busy = true; defer { busy = false }
        let challenge = try AppAttestChallenge.read(url, purpose: capture == nil ? "attest" : "register")
        let destination = try capture.map { $0.folder.appendingPathComponent("app-attest-request-" + challenge.session + ".cbor") }
            ?? directory().appendingPathComponent("app-attest-enrollment-" + challenge.session + ".cbor")
        if FileManager.default.fileExists(atPath: destination.path) {
            let handle = try FileHandle(forReadingFrom: destination); defer { try? handle.close() }
            return try ResearchUtilities.readBounded(limit: 16384) { try handle.read(upToCount: $0) ?? Data() }
        }
        let id = try await AppAttestDeviceKey.identifier()
        guard let keyID = Data(base64Encoded: id), keyID.count == 32 else { throw ProvenanceWire.Invalid.identifier }
        let key = try CaptureKey.load()
        let installation = SHA256.hash(data: key.publicKey.x963Representation).map { String(format: "%02x", $0) }.joined()
        let output: Data
        if let capture {
            let handle = try FileHandle(forReadingFrom: capture.jpeg); defer { try? handle.close() }
            let photo = try ResearchUtilities.readBounded(limit: 25*1024*1024) { try handle.read(upToCount: $0) ?? Data() }
            guard !photo.isEmpty else { throw ProvenanceWire.Invalid.identifier }
            let digest = SHA256.hash(data: photo).map { String(format: "%02x", $0) }.joined()
            let payload = try ProvenanceWire.onlineCameraRequest(id: capture.id, fileSHA256: digest, session: challenge.session, challenge: challenge.nonce)
            let request = try CaptureKey.signed(payload, key: key, purpose: "register")
            let clientHash = Data(SHA256.hash(data: ProvenanceWire.assertionInput(request: request)))
            let assertion: Data = try await withCheckedThrowingContinuation { continuation in
                DCAppAttestService.shared.generateAssertion(id, clientDataHash: clientHash) { assertion, error in
                    if let error { continuation.resume(throwing: error) }
                    else if let assertion { continuation.resume(returning: assertion) }
                    else { continuation.resume(throwing: AppAttestDeviceKey.Failure.invalidResponse) }
                }
            }
            output = try ProvenanceWire.attestedBundle(request: request, assertion: assertion)
        } else {
            let context = try ProvenanceWire.attestContext(installation: installation, session: challenge.session, challenge: challenge.nonce, keyID: keyID)
            let clientHash = Data(SHA256.hash(data: context))
            let attestation: Data = try await withCheckedThrowingContinuation { continuation in
                DCAppAttestService.shared.attestKey(id, clientDataHash: clientHash) { attestation, error in
                    if let error { continuation.resume(throwing: error) }
                    else if let attestation { continuation.resume(returning: attestation) }
                    else { continuation.resume(throwing: AppAttestDeviceKey.Failure.invalidResponse) }
                }
            }
            let payload = try ProvenanceWire.attestRequest(session: challenge.session, challenge: challenge.nonce, keyID: keyID, attestation: attestation)
            output = try CaptureKey.signed(payload, key: key, purpose: "attest")
        }
        guard output.count <= 16384 else { throw ProvenanceWire.Invalid.signature }
        try output.write(to: destination, options: [.atomic, .completeFileProtection])
        refresh()
        status = "App Attest evidence saved locally. Submit this exact file on your Mac; server validation is still pending."
        return output
    }
}
