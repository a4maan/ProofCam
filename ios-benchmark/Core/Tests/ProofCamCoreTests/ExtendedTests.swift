import XCTest
@testable import ProofCamCore
final class ExtendedTests: XCTestCase {
    let id = "00112233445566778899aabbccddeeff"
    func image(_ w: Int = 256, _ h: Int = 256, _ color: UInt32 = 0xff808080) throws -> RGBImage {
        try RGBImage(width: w, height: h, pixels: Array(repeating: color, count: w*h))
    }
    func testInvalidDimensionsAndAlpha() {
        for (w,h) in [(0,1),(-1,1),(1,0),(16385,1),(5000,5000),(Int.max,Int.max)] {
            XCTAssertThrowsError(try RGBImage(width:w,height:h,pixels:[]))
        }
        XCTAssertThrowsError(try RGBImage(width:1,height:1,pixels:[0xfeffffff]))
        XCTAssertThrowsError(try RGBImage(width:1,height:1,pixels:[]))
    }
    func testIDValidationAndFrame() throws {
        for invalid in ["",String(repeating:"0",count:31),String(repeating:"0",count:33),String(repeating:"A",count:32),String(repeating:"é",count:16),String(repeating:"g",count:32)] { XCTAssertThrowsError(try DCTCore.frame(invalid)) }
        let frame = try DCTCore.frame(id)
        XCTAssertEqual(Array(frame.prefix(18)), [80,67,0,17,34,51,68,85,102,119,136,153,170,187,204,221,238,255])
        XCTAssertEqual(DCTCore.crc32([]),0)
    }
    func testExactCapacityAndIncompleteBorders() throws {
        XCTAssertThrowsError(try DCTCore.embed(image(176,184),id:id))
        let source = try image(179,199)
        let marked = try DCTCore.embed(source,id:id)
        XCTAssertEqual(try DCTCore.extract(marked), id)
        for y in 0..<199 { for x in 0..<179 where x>=176 || y>=192 { XCTAssertEqual(marked.pixels[y*179+x], source.pixels[y*179+x]) } }
    }
    func testDeterministicRandomRoundTrips() throws {
        var state: UInt64 = 71
        for index in 0..<20 {
            let pixels: [UInt32] = (0..<65536).map { _ in
                state = state &* 6364136223846793005 &+ 1
                return 0xff000000 | UInt32((state >> 32)&0xffffff)
            }
            let source = try RGBImage(width:256,height:256,pixels:pixels)
            let token = String(format:"%032x",index)
            XCTAssertEqual(try DCTCore.extract(DCTCore.embed(source,id:token)),token)
            XCTAssertNil(try DCTCore.extract(source))
        }
    }
    func testBlackWhiteAndFlatNegatives() throws {
        for color: UInt32 in [0xff000000,0xffffffff,0xff808080,0xffff0000,0xff00ff00,0xff0000ff] {
            XCTAssertNil(try DCTCore.extract(image(256,256,color)))
        }
    }
    func testPayloadCorruptionFailsCRC() throws {
        let source = try image()
        var original = try DCTCore.embed(source,id:id)
        let alternate = try DCTCore.embed(source,id:"80112233445566778899aabbccddeeff")
        // Flip the first ID bit in every repetition, preserving the original CRC.
        for block in 0..<1024 where block % DCTCore.frameBits == 16 {
            let bx = (block % 32)*8, by = (block / 32)*8
            for y in 0..<8 { for x in 0..<8 { original.pixels[(by+y)*256+bx+x] = alternate.pixels[(by+y)*256+bx+x] } }
        }
        XCTAssertNil(try DCTCore.extract(original))
    }
    func testCropsAndBounds() throws {
        let source = try RGBImage(width:2,height:2,pixels:[0xff000001,0xff000002,0xff000003,0xff000004])
        XCTAssertEqual(try source.cropped([1,0,2,2]).pixels,[0xff000002,0xff000004])
        for box in [[],[0,0,2],[0,0,2,2,2],[-1,0,2,2],[0,0,3,2],[1,0,0,2],[0,0,0,1],[0,2,2,3],[Int.min,0,Int.max,2]] { XCTAssertThrowsError(try source.cropped(box)) }
    }
    func testResizeGuardsAndScalePolicy() throws {
        let source = try image(320,240)
        XCTAssertEqual(try source.atLongEdge(1024,upscale:false),source)
        let resized = try source.atLongEdge(160,upscale:false)
        XCTAssertEqual(resized.width,160); XCTAssertEqual(resized.height,120)
        XCTAssertTrue(resized.pixels.allSatisfy { $0 == 0xff808080 })
        for edge in [-1,0,16385,Int.max] { XCTAssertThrowsError(try source.atLongEdge(edge,upscale:true)) }
        XCTAssertThrowsError(try source.resized(width:5000,height:5000))
    }
    func testUniformBorderAndRecovery() throws {
        let marked = try DCTCore.embed(image(),id:id)
        var pixels = [UInt32](repeating:0xff123456,count:280*288)
        for y in 0..<256 { for x in 0..<256 { pixels[(y+13)*280+x+9] = marked.pixels[y*256+x] } }
        let framed = try RGBImage(width:280,height:288,pixels:pixels)
        XCTAssertEqual(RegisteredCandidate.uniformBorder(framed),[9,13,265,269])
        let recovery = try RegisteredCandidate.extract(framed)
        XCTAssertEqual(recovery.decodedIDs,[id]); XCTAssertEqual(recovery.attempts.count,4)
        XCTAssertNil(RegisteredCandidate.uniformBorder(try image()))
    }
    func testSkipAndErrorSearchSemantics() throws {
        let source = try image()
        let skipped = try RegisteredCandidate.search(source) { _ in throw ResearchError.insufficientCapacity }
        XCTAssertFalse(skipped.searchComplete); XCTAssertTrue(skipped.decodedIDs.isEmpty)
        XCTAssertTrue(skipped.attempts.allSatisfy { $0.status == "insufficient_capacity" })
        XCTAssertThrowsError(try RegisteredCandidate.search(source) { _ in throw ResearchError.invalidDimensions })
        let found = try RegisteredCandidate.search(image(1024,256)) { _ in self.id }
        XCTAssertEqual(found.attempts.count,1)
    }
    func testRecoveryJSONRoundTrip() throws {
        let recovery = try RegisteredCandidate.extract(DCTCore.embed(image(),id:id))
        XCTAssertEqual(try JSONDecoder().decode(Recovery.self,from:JSONEncoder().encode(recovery)),recovery)
    }
    func testRectangleParsing() throws {
        XCTAssertNil(try ResearchUtilities.rectangle(" \n"))
        XCTAssertEqual(try ResearchUtilities.rectangle(" 1, 2,3, 4 "),[1,2,3,4])
        for text in ["1,2,3","1,2,,4","1,2,3,4,","a,2,3,4","9999999999999999999999,0,1,1"] { XCTAssertThrowsError(try ResearchUtilities.rectangle(text)) }
    }
    func testP95() {
        XCTAssertNil(ResearchUtilities.p95([]))
        XCTAssertNil(ResearchUtilities.p95([.nan])); XCTAssertNil(ResearchUtilities.p95([.infinity])); XCTAssertNil(ResearchUtilities.p95([-1]))
        XCTAssertEqual(ResearchUtilities.p95([42]),42)
        XCTAssertEqual(ResearchUtilities.p95((1...20).reversed().map(Double.init)),19)
    }
    func testBoundedReadsHandleShortChunksAndOverflow() throws {
        var chunks = [Data([1]),Data([2,3]),Data()]
        XCTAssertEqual(try ResearchUtilities.readBounded(limit:3) { _ in chunks.removeFirst() },Data([1,2,3]))
        chunks = [Data([1,2]),Data([3,4])]
        XCTAssertThrowsError(try ResearchUtilities.readBounded(limit:3) { _ in chunks.removeFirst() })
        XCTAssertEqual(try ResearchUtilities.readBounded(limit:0) { _ in Data() },Data())
        XCTAssertThrowsError(try ResearchUtilities.readBounded(limit:0) { _ in Data([1]) })
        XCTAssertThrowsError(try ResearchUtilities.readBounded(limit:10) { _ in throw ResearchError.invalidDimensions })
    }
}
