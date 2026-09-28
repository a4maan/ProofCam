import Foundation

/// Minimal deterministic CBOR encoder for the development provenance protocol.
/// It is not a general-purpose untrusted CBOR decoder.
public indirect enum ProvenanceCBOR {
    case unsigned(UInt64), negative(Int64), bytes(Data), text(String)
    case array([ProvenanceCBOR]), map([(ProvenanceCBOR, ProvenanceCBOR)]), null

    private static func head(_ major: UInt8, _ value: UInt64) -> Data {
        if value < 24 { return Data([major << 5 | UInt8(value)]) }
        let count = value <= 0xff ? 1 : value <= 0xffff ? 2 : value <= 0xffffffff ? 4 : 8
        let additional: UInt8 = count == 1 ? 24 : count == 2 ? 25 : count == 4 ? 26 : 27
        var output = Data([major << 5 | additional])
        for index in stride(from: count - 1, through: 0, by: -1) {
            output.append(UInt8(truncatingIfNeeded: value >> (index * 8)))
        }
        return output
    }

    public var encoded: Data {
        switch self {
        case .unsigned(let value): return Self.head(0, value)
        case .negative(let value):
            precondition(value < 0)
            return Self.head(1, UInt64(-(value + 1)))
        case .bytes(let value): return Self.head(2, UInt64(value.count)) + value
        case .text(let value):
            let bytes = Data(value.utf8)
            return Self.head(3, UInt64(bytes.count)) + bytes
        case .array(let values): return Self.head(4, UInt64(values.count)) + values.reduce(Data()) { $0 + $1.encoded }
        case .map(let entries):
            let sorted = entries.map { ($0.0.encoded, $0.1.encoded) }.sorted {
                $0.0.count == $1.0.count ? $0.0.lexicographicallyPrecedes($1.0) : $0.0.count < $1.0.count
            }
            return Self.head(5, UInt64(sorted.count)) + sorted.reduce(Data()) { $0 + $1.0 + $1.1 }
        case .null: return Data([0xf6])
        }
    }
}

public enum ProvenanceWire {
    public enum Invalid: Error { case invitation, identifier, signature }
    private static let prefix = "proofcam.dev.v1."
    private static func object(_ fields: [(String, ProvenanceCBOR)]) -> Data {
        ProvenanceCBOR.map(fields.map { (.text($0.0), $0.1) }).encoded
    }
    private static func hexadecimal(_ value: String, count: Int) -> Bool {
        value.utf8.count == count && value.utf8.allSatisfy { (48...57).contains($0) || (97...102).contains($0) }
    }
    public static func invitation(from data: Data) throws -> Data {
        let template = object([("invitation", .bytes(Data(repeating: 0, count: 32)))])
        guard data.count == template.count, data.dropLast(32) == template.dropLast(32) else { throw Invalid.invitation }
        return Data(data.suffix(32))
    }
    public static func enrollment(publicKey: Data, invitation: Data) throws -> Data {
        guard publicKey.count == 65, publicKey.first == 4, invitation.count == 32 else { throw Invalid.invitation }
        return object([("type", .text(prefix + "enroll")), ("version", .unsigned(1)),
                       ("public_key", .bytes(publicKey)), ("invitation", .bytes(invitation))])
    }
    public static func offlineCameraRequest(id: String, fileSHA256: String, session: String) throws -> Data {
        guard hexadecimal(id, count: 32), hexadecimal(fileSHA256, count: 64), hexadecimal(session, count: 32) else { throw Invalid.identifier }
        return object([("type", .text(prefix + "register")), ("version", .unsigned(1)),
                       ("id", .text(id)), ("file_sha256", .text(fileSHA256)), ("session", .text(session)),
                       ("mode", .text("offline")), ("challenge", .null), ("source", .text("camera_unverified"))])
    }
    public static func challengeRequest(session: String, purpose: String) throws -> Data {
        guard hexadecimal(session, count: 32), ["attest", "register"].contains(purpose) else { throw Invalid.identifier }
        return object([("type", .text(prefix + "challenge")), ("version", .unsigned(1)), ("session", .text(session)), ("purpose", .text(purpose))])
    }
    public static func attestContext(installation: String, session: String, challenge: Data, keyID: Data) throws -> Data {
        guard hexadecimal(installation, count: 64), hexadecimal(session, count: 32), challenge.count == 32, keyID.count == 32 else { throw Invalid.identifier }
        return object([("type", .text(prefix + "attest-context")), ("version", .unsigned(1)), ("installation", .text(installation)),
                       ("session", .text(session)), ("challenge", .bytes(challenge)), ("key_id", .bytes(keyID))])
    }
    public static func attestRequest(session: String, challenge: Data, keyID: Data, attestation: Data) throws -> Data {
        guard hexadecimal(session, count: 32), challenge.count == 32, keyID.count == 32, !attestation.isEmpty, attestation.count <= 14000 else { throw Invalid.identifier }
        return object([("type", .text(prefix + "attest")), ("version", .unsigned(1)), ("session", .text(session)),
                       ("challenge", .bytes(challenge)), ("key_id", .bytes(keyID)), ("attestation", .bytes(attestation))])
    }
    public static func onlineCameraRequest(id: String, fileSHA256: String, session: String, challenge: Data) throws -> Data {
        guard hexadecimal(id, count: 32), hexadecimal(fileSHA256, count: 64), hexadecimal(session, count: 32), challenge.count == 32 else { throw Invalid.identifier }
        return object([("type", .text(prefix + "register")), ("version", .unsigned(1)), ("id", .text(id)),
                       ("file_sha256", .text(fileSHA256)), ("session", .text(session)), ("mode", .text("online")),
                       ("challenge", .bytes(challenge)), ("source", .text("camera_unverified"))])
    }
    public static func assertionInput(request: Data) -> Data {
        Data("proofcam.dev.v1.app-attest.assertion\0".utf8) + request
    }
    public static func attestedBundle(request: Data, assertion: Data) throws -> Data {
        guard !request.isEmpty, !assertion.isEmpty else { throw Invalid.signature }
        let bundle = object([("request", .bytes(request)), ("assertion", .bytes(assertion))])
        guard bundle.count <= 16384 else { throw Invalid.signature }
        return bundle
    }
    public static func protectedHeader(keyID: String) throws -> Data {
        guard hexadecimal(keyID, count: 64) else { throw Invalid.identifier }
        return ProvenanceCBOR.map([(.unsigned(1), .negative(-7)), (.unsigned(4), .bytes(Data(keyID.utf8)))]).encoded
    }
    public static func signatureInput(payload: Data, keyID: String, purpose: String) throws -> Data {
        guard ["register", "enroll", "challenge", "attest"].contains(purpose) else { throw Invalid.signature }
        return ProvenanceCBOR.array([.text("Signature1"), .bytes(try protectedHeader(keyID: keyID)),
                                     .bytes(Data((prefix + purpose).utf8)), .bytes(payload)]).encoded
    }
    public static func envelope(payload: Data, keyID: String, signature: Data) throws -> Data {
        guard signature.count == 64 else { throw Invalid.signature }
        return Data([0xd2]) + ProvenanceCBOR.array([.bytes(try protectedHeader(keyID: keyID)), .map([]),
                                                   .bytes(payload), .bytes(signature)]).encoded
    }
}
