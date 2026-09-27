import XCTest
import Foundation
@testable import ProofCamCore

final class ProvenanceWireTests: XCTestCase {
    private func hex(_ value: Data) -> String { value.map { String(format: "%02x", $0) }.joined() }
    func testPythonCanonicalRequestAndSignatureInput() throws {
        let payload = try ProvenanceWire.offlineCameraRequest(id: String(repeating: "0", count: 32), fileSHA256: String(repeating: "1", count: 64), session: String(repeating: "2", count: 32))
        XCTAssertEqual(hex(payload), "a862696478203030303030303030303030303030303030303030303030303030303030303030646d6f6465676f66666c696e656474797065781870726f6f6663616d2e6465762e76312e726567697374657266736f757263657163616d6572615f756e76657269666965646773657373696f6e782032323232323232323232323232323232323232323232323232323232323232326776657273696f6e01696368616c6c656e6765f66b66696c655f736861323536784031313131313131313131313131313131313131313131313131313131313131313131313131313131313131313131313131313131313131313131313131313131")
        XCTAssertEqual(hex(try ProvenanceWire.signatureInput(payload: payload, keyID: String(repeating: "3", count: 64), purpose: "register")), "846a5369676e6174757265315846a2012604584033333333333333333333333333333333333333333333333333333333333333333333333333333333333333333333333333333333333333333333333333333333581870726f6f6663616d2e6465762e76312e726567697374657258f7a862696478203030303030303030303030303030303030303030303030303030303030303030646d6f6465676f66666c696e656474797065781870726f6f6663616d2e6465762e76312e726567697374657266736f757263657163616d6572615f756e76657269666965646773657373696f6e782032323232323232323232323232323232323232323232323232323232323232326776657273696f6e01696368616c6c656e6765f66b66696c655f736861323536784031313131313131313131313131313131313131313131313131313131313131313131313131313131313131313131313131313131313131313131313131313131")
    }
    func testInvitationBoundsAndCanonicalForm() throws {
        let invite = ProvenanceCBOR.map([(.text("invitation"), .bytes(Data(repeating: 7, count: 32)))]).encoded
        XCTAssertEqual(try ProvenanceWire.invitation(from: invite), Data(repeating: 7, count: 32))
        for data in [Data(), invite + Data([0]), Data(invite.dropLast()), Data(repeating: 0, count: 20000)] {
            XCTAssertThrowsError(try ProvenanceWire.invitation(from: data))
        }
    }
    func testInvalidIdentifiersAndSignatureSizes() throws {
        XCTAssertThrowsError(try ProvenanceWire.offlineCameraRequest(id: "bad", fileSHA256: String(repeating: "1", count: 64), session: String(repeating: "2", count: 32)))
        XCTAssertThrowsError(try ProvenanceWire.offlineCameraRequest(id: String(repeating: "A", count: 32), fileSHA256: String(repeating: "1", count: 64), session: String(repeating: "2", count: 32)))
        XCTAssertThrowsError(try ProvenanceWire.envelope(payload: Data(), keyID: String(repeating: "3", count: 64), signature: Data(repeating: 0, count: 63)))
        XCTAssertThrowsError(try ProvenanceWire.signatureInput(payload: Data(), keyID: String(repeating: "3", count: 64), purpose: "certificate"))
    }
    func testIntegerAndByteBoundaries() {
        XCTAssertEqual(hex(ProvenanceCBOR.unsigned(23).encoded), "17")
        XCTAssertEqual(hex(ProvenanceCBOR.unsigned(24).encoded), "1818")
        XCTAssertEqual(hex(ProvenanceCBOR.unsigned(256).encoded), "190100")
        XCTAssertEqual(hex(ProvenanceCBOR.unsigned(65536).encoded), "1a00010000")
        XCTAssertEqual(hex(ProvenanceCBOR.unsigned(4294967296).encoded), "1b0000000100000000")
        XCTAssertEqual(hex(ProvenanceCBOR.negative(-7).encoded), "26")
        XCTAssertEqual(hex(ProvenanceCBOR.bytes(Data(repeating: 0, count: 24)).encoded.prefix(2)), "5818")
    }
}
