#if canImport(ImageIO) && canImport(UniformTypeIdentifiers)
import XCTest
import CoreGraphics
import ImageIO
import UniformTypeIdentifiers
@testable import ProofCamCore
/// These execute on macOS via validate-mac.sh, not on Linux.
final class AppleCodecTests: XCTestCase {
    func png(width: Int, height: Int, pixels: [UInt8], orientation: Int = 1) throws -> Data {
        let provider = try XCTUnwrap(CGDataProvider(data: Data(pixels) as CFData))
        let image = try XCTUnwrap(CGImage(width: width, height: height, bitsPerComponent: 8, bitsPerPixel: 32, bytesPerRow: width*4,
            space: CGColorSpace(name: CGColorSpace.sRGB)!, bitmapInfo: CGBitmapInfo(rawValue: CGBitmapInfo.byteOrder32Big.rawValue | CGImageAlphaInfo.premultipliedLast.rawValue),
            provider: provider, decode: nil, shouldInterpolate: false, intent: .defaultIntent))
        let data = NSMutableData()
        let destination = try XCTUnwrap(CGImageDestinationCreateWithData(data, UTType.png.identifier as CFString, 1, nil))
        CGImageDestinationAddImage(destination,image,[kCGImagePropertyOrientation:orientation] as CFDictionary)
        XCTAssertTrue(CGImageDestinationFinalize(destination)); return data as Data
    }
    func testPNGPreservesPixelOrder() throws {
        let bytes: [UInt8] = [255,0,0,255, 0,255,0,255, 0,0,255,255, 255,255,255,255]
        let decoded = try AppleImageCodec.decode(png(width:2,height:2,pixels:bytes))
        XCTAssertEqual(decoded.pixels,[0xffff0000,0xff00ff00,0xff0000ff,0xffffffff])
    }
    func testRejectsMalformedAndTransparentImages() throws {
        for data in [Data(),Data("not an image".utf8),Data(repeating:0,count:25*1024*1024+1)] { XCTAssertThrowsError(try AppleImageCodec.decode(data)) }
        let transparent = try png(width:1,height:1,pixels:[0,0,0,0])
        XCTAssertThrowsError(try AppleImageCodec.decode(transparent))
    }
    func testJPEGDimensionsAndRecovery() throws {
        let source = try RGBImage(width:256,height:256,pixels:Array(repeating:0xff808080,count:65536))
        let id = "00112233445566778899aabbccddeeff"
        let decoded = try AppleImageCodec.decode(AppleImageCodec.jpeg(DCTCore.embed(source,id:id)))
        XCTAssertEqual(decoded.width,256); XCTAssertEqual(decoded.height,256)
        XCTAssertEqual(try DCTCore.extract(decoded),id)
    }
    func testTiledAppleJPEGRecovery() throws {
        let source = try RGBImage(width:320,height:288,pixels:Array(repeating:0xff808080,count:320*288))
        let id = "00112233445566778899aabbccddeeff"
        let decoded = try AppleImageCodec.decode(AppleImageCodec.jpeg(TiledCandidate.embed(source,id:id)))
        XCTAssertTrue(TiledCandidate.tiles(decoded).contains { $0.0 == id })
    }
    func testOrientationNormalization() throws {
        let decoded = try AppleImageCodec.decode(png(width:2,height:1,pixels:[255,0,0,255,0,0,255,255],orientation:6))
        XCTAssertEqual(decoded.width,1); XCTAssertEqual(decoded.height,2)
        XCTAssertEqual(decoded.pixels,[0xffff0000,0xff0000ff])
    }
}
#endif
