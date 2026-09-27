import Foundation
import XCTest
@testable import ProofCamCore
final class TiledTests: XCTestCase {
    let id = "00112233445566778899aabbccddeeff"
    func testSECDEDExhaustive() {
        for byte in UInt16(0)...255 {
            let word = TiledCandidate.code(UInt8(byte))
            XCTAssertEqual(TiledCandidate.uncode(word),UInt8(byte))
            for i in 0..<13 {
                var one = word; one[i] ^= 1
                XCTAssertEqual(TiledCandidate.uncode(one),UInt8(byte))
                for j in (i+1)..<13 { var two = one; two[j] ^= 1; XCTAssertNil(TiledCandidate.uncode(two)) }
            }
        }
    }
    func testTileCropAndConflict() throws {
        let source = try RGBImage(width:512,height:384,pixels:Array(repeating:0xff808080,count:512*384))
        let first = try TiledCandidate.embed(source,id:id)
        let crop = try first.cropped([51,38,461,346])
        XCTAssertEqual(Set(TiledCandidate.tiles(crop).map { $0.0 }),[id])
        let secondID = "ffeeddccbbaa99887766554433221100"
        let second = try TiledCandidate.embed(source,id:secondID)
        var mixed = first
        for y in 0..<384 { for x in 256..<512 { mixed.pixels[y*512+x] = second.pixels[y*512+x] } }
        XCTAssertEqual(Set(TiledCandidate.tiles(mixed).map { $0.0 }),[id,secondID])
    }
    func testCoefficientFilterAndOrientations() throws {
        let pixels = (0..<128*192).map { UInt32(0xff000000) | UInt32(($0*13579)%0xffffff) }
        let source = try RGBImage(width:128,height:192,pixels:pixels)
        let values = TiledCandidate.coefficients(source)
        for (x,y) in [(0,0),(7,13),(120,184)] { XCTAssertEqual(values[y*128+x],DCTCore.coefficient(source,x,y),accuracy:1e-9) }
        var turned = source
        for _ in 0..<4 { turned = try TiledCandidate.oriented(turned,turns:1,mirrored:false) }
        XCTAssertEqual(turned,source)
        XCTAssertEqual(try TiledCandidate.oriented(TiledCandidate.oriented(source,turns:0,mirrored:true),turns:0,mirrored:true),source)
        XCTAssertThrowsError(try TiledCandidate.embed(RGBImage(width:127,height:192,pixels:Array(repeating:0xff808080,count:127*192)),id:id))
        XCTAssertTrue(TiledCandidate.tiles(source).isEmpty)
    }
    func testGeometryAndBackgroundBounds() throws {
        let tiny = try RGBImage(width:2,height:3,pixels:(1...6).map { 0xff000000 | UInt32($0) })
        XCTAssertEqual(try TiledCandidate.oriented(tiny,turns:1,mirrored:false).pixels,[5,3,1,6,4,2].map { 0xff000000 | UInt32($0) })
        XCTAssertEqual(try TiledCandidate.rotated(tiny,degrees:0),tiny)
        XCTAssertThrowsError(try TiledCandidate.oriented(tiny,turns:4,mirrored:false))
        XCTAssertThrowsError(try TiledCandidate.rotated(tiny,degrees:.nan))
        var pixels = [UInt32](repeating:0xff123456,count:208*288)
        for y in 72..<216 { for x in 24..<184 { pixels[y*208+x] = 0xff808080 } }
        for y in 4..<20 { for x in 4..<20 { pixels[y*208+x] = 0xffffffff } }
        let screen = try RGBImage(width:208,height:288,pixels:pixels)
        XCTAssertEqual(TiledCandidate.contentRectangle(screen),[24,72,184,216])
        XCTAssertNil(TiledCandidate.uncode([]))
        XCTAssertNil(TiledCandidate.uncode(Array(repeating:2,count:13)))
    }
    func testPrepareFixtures() throws {
        guard let path = ProcessInfo.processInfo.environment["PROOFCAM_TILED_FIXTURES"] else { throw XCTSkip("Optional simulation fixture generation") }
        let folder = URL(fileURLWithPath:path)
        let jobs = try String(contentsOf:folder.appendingPathComponent("jobs.tsv"),encoding:.utf8)
        for line in jobs.split(separator:"\n") {
            let parts = line.split(separator:"\t").map(String.init)
            let bytes = Array(try Data(contentsOf:folder.appendingPathComponent(parts[0]+".rgb")))
            func integer(_ i: Int) -> Int { bytes[i..<i+4].reduce(0) { ($0 << 8)|Int($1) } }
            let w = integer(0), h = integer(4)
            let pixels = stride(from:8,to:bytes.count,by:3).map { 0xff000000 | UInt32(bytes[$0])<<16 | UInt32(bytes[$0+1])<<8 | UInt32(bytes[$0+2]) }
            let source = try RGBImage(width:w,height:h,pixels:pixels)
            let marked = try TiledCandidate.embed(source,id:parts[1])
            XCTAssertTrue(TiledCandidate.tiles(marked).contains { $0.0 == parts[1] })
            var output = Data(bytes.prefix(8))
            for p in marked.pixels { for shift in [16,8,0] { output.append(UInt8((p>>shift)&255)) } }
            try output.write(to:folder.appendingPathComponent(parts[0]+"-tiled.rgb"))
        }
    }
}
