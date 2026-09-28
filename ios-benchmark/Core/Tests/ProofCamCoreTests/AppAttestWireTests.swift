import XCTest
import Foundation
@testable import ProofCamCore
final class AppAttestWireTests: XCTestCase {
    func testCanonicalContextMatchesPython() throws {
        let data = try ProvenanceWire.attestContext(installation: String(repeating: "1", count: 64), session: String(repeating: "2", count: 32), challenge: Data(repeating: 51, count: 32), keyID: Data(repeating: 52, count: 32))
        XCTAssertEqual(data.map { String(format: "%02x", $0) }.joined(), "a66474797065781e70726f6f6663616d2e6465762e76312e6174746573742d636f6e74657874666b65795f6964582034343434343434343434343434343434343434343434343434343434343434346773657373696f6e782032323232323232323232323232323232323232323232323232323232323232326776657273696f6e01696368616c6c656e6765582033333333333333333333333333333333333333333333333333333333333333336c696e7374616c6c6174696f6e784031313131313131313131313131313131313131313131313131313131313131313131313131313131313131313131313131313131313131313131313131313131")
    }
    func testOnlineRequestMatchesPythonAndAssertionDomain() throws {
        let data = try ProvenanceWire.onlineCameraRequest(id: String(repeating: "0", count: 32), fileSHA256: String(repeating: "1", count: 64), session: String(repeating: "2", count: 32), challenge: Data(repeating: 51, count: 32))
        XCTAssertEqual(data.map { String(format: "%02x", $0) }.joined(), "a862696478203030303030303030303030303030303030303030303030303030303030303030646d6f6465666f6e6c696e656474797065781870726f6f6663616d2e6465762e76312e726567697374657266736f757263657163616d6572615f756e76657269666965646773657373696f6e782032323232323232323232323232323232323232323232323232323232323232326776657273696f6e01696368616c6c656e6765582033333333333333333333333333333333333333333333333333333333333333336b66696c655f736861323536784031313131313131313131313131313131313131313131313131313131313131313131313131313131313131313131313131313131313131313131313131313131")
        XCTAssertEqual(ProvenanceWire.assertionInput(request: Data([1,2])), Data("proofcam.dev.v1.app-attest.assertion\0".utf8) + Data([1,2]))
    }
    func testInvalidContextsAndBounds() throws {
        XCTAssertThrowsError(try ProvenanceWire.attestContext(installation: "bad", session: String(repeating: "2", count: 32), challenge: Data(repeating: 0, count: 32), keyID: Data(repeating: 0, count: 32)))
        XCTAssertThrowsError(try ProvenanceWire.challengeRequest(session: "../unsafe", purpose: "attest"))
        XCTAssertThrowsError(try ProvenanceWire.challengeRequest(session: String(repeating: "2", count: 32), purpose: "unknown"))
        XCTAssertThrowsError(try ProvenanceWire.attestedBundle(request: Data(repeating: 0, count: 16000), assertion: Data(repeating: 0, count: 1000)))
    }
}
