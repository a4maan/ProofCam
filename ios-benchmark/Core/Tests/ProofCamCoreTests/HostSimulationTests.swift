import Foundation
import XCTest
@testable import ProofCamCore
final class HostSimulationTests: XCTestCase {
    struct Input: Codable { let name: String; let file: String; let expected: String?; let mustRecover: Bool }
    struct Result: Codable { let name: String; let expected: String?; let recovered: [String]; let matching: Bool; let unexpectedIDs: [String]; let attempts: [SearchAttempt] }
    func testSyntheticScreenshotMatrix() throws {
        guard let directory = ProcessInfo.processInfo.environment["PROOFCAM_SIMULATION_DIRECTORY"] else { throw XCTSkip("Run tools/simulate.py to supply host-only fixtures") }
        let root = URL(fileURLWithPath: directory)
        let inputs = try JSONDecoder().decode([Input].self, from: Data(contentsOf: root.appendingPathComponent("inputs.json")))
        var results = [Result]()
        for input in inputs {
            let bytes = Array(try Data(contentsOf: root.appendingPathComponent(input.file)))
            func number(_ offset: Int) -> Int { bytes[offset..<offset+4].reduce(0) { ($0 << 8) | Int($1) } }
            guard bytes.count >= 8 else { throw ResearchError.invalidDimensions }
            let width = number(0), height = number(4)
            guard width > 0, height > 0, width <= 16384, height <= 16384, width*height <= 20_000_000, bytes.count == 8+width*height*3 else { throw ResearchError.invalidDimensions }
            let pixels = stride(from:8,to:bytes.count,by:3).map { 0xff000000 | UInt32(bytes[$0]) << 16 | UInt32(bytes[$0+1]) << 8 | UInt32(bytes[$0+2]) }
            let recovery = try RegisteredCandidate.extract(RGBImage(width:width,height:height,pixels:pixels))
            let matching = input.expected.map { recovery.decodedIDs == [$0] } ?? recovery.decodedIDs.isEmpty
            let unexpected = recovery.decodedIDs.filter { $0 != input.expected }
            results.append(Result(name:input.name,expected:input.expected,recovered:recovery.decodedIDs,matching:matching,unexpectedIDs:unexpected,attempts:recovery.attempts))
            if input.mustRecover { XCTAssertTrue(matching,input.name) }
            XCTAssertTrue(unexpected.isEmpty,"Unexpected ID: \(input.name)")
        }
        let encoder = JSONEncoder(); encoder.outputFormatting = [.prettyPrinted,.sortedKeys]
        try encoder.encode(results).write(to:root.appendingPathComponent("results.json"))
    }
    func testDeterministicMalformedGeometry() throws {
        let image = try RGBImage(width:16,height:16,pixels:Array(repeating:0xff123456,count:256))
        var state: UInt64 = 42
        for _ in 0..<2000 {
            var box = [Int]()
            for _ in 0..<4 { state = state &* 6364136223846793005 &+ 1; box.append(Int((state >> 32)%65)-24) }
            let valid = box[0]>=0 && box[1]>=0 && box[2]<=16 && box[3]<=16 && box[2]>box[0] && box[3]>box[1]
            if valid {
                let crop = try image.cropped(box)
                XCTAssertEqual(crop.pixels.count,(box[2]-box[0])*(box[3]-box[1]))
            } else { XCTAssertThrowsError(try image.cropped(box)) }
        }
    }
    func testExtremeAspectRatios() throws {
        for (width,height) in [(1,16384),(16384,1),(8,16384),(16384,8)] {
            let source = try RGBImage(width:width,height:height,pixels:Array(repeating:0xff808080,count:width*height))
            let scaled = try source.atLongEdge(1024,upscale:true)
            XCTAssertEqual(max(scaled.width,scaled.height),1024)
            XCTAssertGreaterThan(min(scaled.width,scaled.height),0)
            let recovery = try RegisteredCandidate.extract(source)
            XCTAssertTrue(recovery.decodedIDs.isEmpty)
        }
    }
}
