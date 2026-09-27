import XCTest
@testable import ProofCamCore
final class CoreTests: XCTestCase {
    let id = "00112233445566778899aabbccddeeff"
    func testCRC() { XCTAssertEqual(DCTCore.crc32(Array("123456789".utf8)), 0xcbf43926) }
    func testRoundTrip() throws {
        let source = try RGBImage(width: 256, height: 256, pixels: Array(repeating: 0xff808080, count: 65536))
        XCTAssertNil(try DCTCore.extract(source))
        for token in [id, String(repeating: "f", count: 32), String(repeating: "0", count: 32)] {
            XCTAssertEqual(try DCTCore.extract(DCTCore.embed(source, id: token)), token)
        }
    }
    func testGuards() throws {
        XCTAssertThrowsError(try DCTCore.frame("bad"))
        XCTAssertThrowsError(try RGBImage(width: 1, height: 1, pixels: [0]))
        let tiny = try RGBImage(width: 1, height: 1, pixels: [0xff000000])
        XCTAssertThrowsError(try DCTCore.extract(tiny))
        XCTAssertThrowsError(try tiny.cropped([0,0,2,2]))
    }
    func testResize() throws {
        let source = try RGBImage(width: 2, height: 2, pixels: [0xff000000,0xffffffff,0xffffffff,0xff000000])
        XCTAssertEqual(try source.resized(width: 1, height: 1).pixels, [0xff808080])
        XCTAssertEqual(try source.resized(width: 2, height: 2), source)
    }
    func testSearchRetainsConflicts() throws {
        var pixels = Array(repeating: UInt32(0xff000000), count: 256*256)
        for y in 16..<240 { for x in 16..<240 { pixels[y*256+x] = 0xff808080 } }
        let source = try RGBImage(width: 256, height: 256, pixels: pixels)
        var calls = 0
        let result = try RegisteredCandidate.search(source) { _ in calls += 1; return calls == 1 ? self.id : String(repeating: "f", count: 32) }
        XCTAssertEqual(calls, 4); XCTAssertEqual(result.decodedIDs.count, 2)
        XCTAssertEqual(RegisteredCandidate.uniformBorder(source), [16,16,240,240])
    }
}
