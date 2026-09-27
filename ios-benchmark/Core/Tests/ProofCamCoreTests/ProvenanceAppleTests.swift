#if canImport(CryptoKit)
import XCTest
import CryptoKit
import Foundation
@testable import ProofCamCore

final class ProvenanceAppleTests: XCTestCase {
    // Public test key scalar 1. Never use this key outside test vectors.
    private func data(_ hex: String) -> Data {
        var result = Data(); var start = hex.startIndex
        while start < hex.endIndex {
            let end = hex.index(start, offsetBy: 2)
            result.append(UInt8(hex[start..<end], radix: 16)!); start = end
        }
        return result
    }
    func testPythonSignatureAgainstCryptoKit() throws {
        let publicKey = try P256.Signing.PublicKey(x963Representation: data("046b17d1f2e12c4247f8bce6e563a440f277037d812deb33a0f4a13945d898c2964fe342e2fe1a7f9b8ee7eb4a7c0f9e162bce33576b315ececbb6406837bf51f5"))
        let signature = try P256.Signing.ECDSASignature(rawRepresentation: data("14870743be5310bb54c58c5687dd45cc46e36502eb73d0acd09982e9cbdb31b924ff7d11050a514bc5f518a802faff081c688f1c2a9db6ad5500e37c2efc48d5"))
        let keyID = SHA256.hash(data: publicKey.x963Representation).map { String(format: "%02x", $0) }.joined()
        let payload = try ProvenanceWire.offlineCameraRequest(id: String(repeating: "0", count: 32), fileSHA256: String(repeating: "1", count: 64), session: String(repeating: "2", count: 32))
        let input = try ProvenanceWire.signatureInput(payload: payload, keyID: keyID, purpose: "register")
        XCTAssertTrue(publicKey.isValidSignature(signature, for: input))
        XCTAssertFalse(publicKey.isValidSignature(signature, for: input + Data([0])))
    }
    func testCryptoKitRawSignatureEnvelope() throws {
        let key = P256.Signing.PrivateKey()
        let keyID = SHA256.hash(data: key.publicKey.x963Representation).map { String(format: "%02x", $0) }.joined()
        let payload = try ProvenanceWire.offlineCameraRequest(id: String(repeating: "0", count: 32), fileSHA256: String(repeating: "1", count: 64), session: String(repeating: "2", count: 32))
        let input = try ProvenanceWire.signatureInput(payload: payload, keyID: keyID, purpose: "register")
        let signature = try key.signature(for: input)
        XCTAssertEqual(signature.rawRepresentation.count, 64)
        XCTAssertTrue(key.publicKey.isValidSignature(signature, for: input))
        XCTAssertEqual(try ProvenanceWire.envelope(payload: payload, keyID: keyID, signature: signature.rawRepresentation).first, 0xd2)
    }
}
#endif
