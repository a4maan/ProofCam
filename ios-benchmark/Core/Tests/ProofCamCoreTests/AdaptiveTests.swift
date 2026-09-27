import XCTest
import Foundation
@testable import ProofCamCore
final class AdaptiveTests: XCTestCase {
    func testSoftCorrectionAndChecksumRejection() throws {
        let id = "00112233445566778899aabbccddeeff"
        let payload = try AdaptiveCandidate.encodedFrame(DCTCore.frame(id)).map { $0 == 1 ? 24.0 : -24.0 }
        XCTAssertEqual(AdaptiveCandidate.frame(payload),id)
        var damaged = payload
        for word in [3,5,8] { for bit in [1,7] { let i=word*13+bit; damaged[i] = damaged[i]>0 ? -0.01 : 0.01 } }
        XCTAssertEqual(AdaptiveCandidate.frame(damaged),id)
        XCTAssertNil(AdaptiveCandidate.frame([]))
        XCTAssertNil(AdaptiveCandidate.frame(Array(repeating:0,count:364)))
    }
    func testCoefficientRecurrence() throws {
        let image=try RGBImage(width:193,height:201,pixels:(0..<193*201).map { 0xff000000 | UInt32(($0*137123)%0xffffff) })
        let plane=GrayPlane(image)
        for block in [3,6,8] {
            let values=plane.coefficients(block:block)
            for (x,y) in [(0,0),(7,19),(182,187)] {
                var direct=0.0
                for dy in 0..<block { for dx in 0..<block { direct += plane.pixels[(y+dy)*193+x+dx]*(2/Double(block))*cos(Double(2*dx+1)*Double.pi/Double(2*block))*cos(Double(2*dy+1)*Double.pi/Double(2*block)) } }
                XCTAssertEqual(values[y*193+x],direct,accuracy:1e-7)
            }
        }
        XCTAssertEqual(plane.transformed(degrees:0).pixels,plane.pixels)
    }
    func testIndependentEncoderVectorAndCorruptedCRC() throws {
        XCTAssertEqual(AdaptiveCandidate.encodedFrame([80,67]).map(String.init).joined(),"00110111101101001000010011110101011100010111")
        for value in 0..<16 {
            let id=String(format:"%032x",value)
            let encoded=AdaptiveCandidate.encodedFrame(try DCTCore.frame(id)).map { $0==1 ? 12.0:-12.0 }
            XCTAssertEqual(AdaptiveCandidate.frame(encoded),id)
        }
        var bytes=try DCTCore.frame("00112233445566778899aabbccddeeff");bytes[2] ^= 1
        XCTAssertNil(AdaptiveCandidate.frame(AdaptiveCandidate.encodedFrame(bytes).map { $0==1 ? 12.0:-12.0 }))
        XCTAssertNil(AdaptiveCandidate.frame(Array(repeating:.nan,count:364)))
    }
    func testSymmetrySearchAndConflictingIDs() throws {
        let source=try RGBImage(width:264,height:240,pixels:Array(repeating:0xff808080,count:264*240))
        let first="00112233445566778899aabbccddeeff",second="ffeeddccbbaa99887766554433221100"
        var marked=try AdaptiveCandidate.embed(source,id:first)
        let other=try AdaptiveCandidate.embed(source,id:second)
        for y in 0..<240 { for x in 132..<264 { marked.pixels[y*264+x]=other.pixels[y*264+x] } }
        for mirrored in [false,true] { for turn in 0..<4 {
            let oriented=try TiledCandidate.oriented(marked,turns:turn,mirrored:mirrored)
            XCTAssertEqual(Set(AdaptiveCandidate.tiles(GrayPlane(oriented),allOrientations:true).map { $0.0 }),[first,second])
        }}
    }
    func testClippedColorsAndUntouchedEdges() throws {
        let id="00112233445566778899aabbccddeeff"
        for color: UInt32 in [0xff000000,0xffffffff,0xffff0000,0xff0000ff] {
            let source=try RGBImage(width:137,height:127,pixels:Array(repeating:color,count:137*127))
            let marked=try AdaptiveCandidate.embed(source,id:id)
            XCTAssertEqual(AdaptiveCandidate.tiles(GrayPlane(marked)).map { $0.0 },[id])
            for y in 0..<127 { for x in 0..<137 where x>=132 || y>=120 { XCTAssertEqual(marked.pixels[y*137+x],color) } }
        }
    }
    func testPrepareFixtures() throws {
        guard let path=ProcessInfo.processInfo.environment["PROOFCAM_ADAPTIVE_FIXTURES"] else { throw XCTSkip("Optional development fixture generation") }
        let folder=URL(fileURLWithPath:path)
        let jobs=try String(contentsOf:folder.appendingPathComponent("jobs.tsv"),encoding:.utf8)
        for line in jobs.split(separator:"\n") {
            let parts=line.split(separator:"\t").map(String.init)
            let bytes=Array(try Data(contentsOf:folder.appendingPathComponent(parts[0]+".rgb")))
            func integer(_ i: Int) -> Int { bytes[i..<i+4].reduce(0) { ($0 << 8)|Int($1) } }
            let w=integer(0),h=integer(4)
            let pixels=stride(from:8,to:bytes.count,by:3).map { 0xff000000 | UInt32(bytes[$0])<<16 | UInt32(bytes[$0+1])<<8 | UInt32(bytes[$0+2]) }
            let marked=try AdaptiveCandidate.embed(RGBImage(width:w,height:h,pixels:pixels),id:parts[1])
            XCTAssertTrue(AdaptiveCandidate.tiles(GrayPlane(marked)).contains { $0.0==parts[1] })
            var output=Data(bytes.prefix(8))
            for p in marked.pixels { for shift in [16,8,0] { output.append(UInt8((p>>shift)&255)) } }
            try output.write(to:folder.appendingPathComponent(parts[0]+"-adaptive.rgb"))
        }
    }
    func testKnownGeometryProbe() throws {
        guard let path=ProcessInfo.processInfo.environment["PROOFCAM_ADAPTIVE_PROBE"] else { throw XCTSkip("Optional development geometry diagnostic") }
        struct Input: Decodable { let name: String; let file: String; let expected: String? }
        let folder=URL(fileURLWithPath:path)
        let inputs=try JSONDecoder().decode([Input].self,from:Data(contentsOf:folder.appendingPathComponent("inputs.json")))
        for input in inputs where input.name.contains("crop_then_half") || input.name.contains("rotate_7.3") || input.name.contains("rotate_20_") {
            let bytes=Array(try Data(contentsOf:folder.appendingPathComponent(input.file)))
            func integer(_ i: Int) -> Int { bytes[i..<i+4].reduce(0) { ($0 << 8)|Int($1) } }
            let w=integer(0),h=integer(4)
            let pixels=stride(from:8,to:bytes.count,by:3).map { 0xff000000 | UInt32(bytes[$0])<<16 | UInt32(bytes[$0+1])<<8 | UInt32(bytes[$0+2]) }
            let plane=GrayPlane(try RGBImage(width:w,height:h,pixels:pixels))
            let view=input.name.contains("crop_then_half") ? plane : plane.resized(edge:min(512,max(w,h))).transformed(degrees:input.name.contains("7.3") ? 7 : 20)
            let found=AdaptiveCandidate.tiles(view,block:input.name.contains("crop_then_half") || max(w,h)>512 ? 3:6).map { $0.0 }
            print("PROBE \(input.name) \(found == [input.expected!])")
        }
    }
}
