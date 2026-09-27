import Foundation

public enum ResearchError: Error, LocalizedError, Sendable {
    case invalidDimensions, insufficientCapacity, invalidID, invalidRectangle
    public var errorDescription: String? {
        switch self {
        case .invalidDimensions: return "Image exceeds 20 megapixels/16384 pixels per side, or has invalid pixels."
        case .insufficientCapacity: return "The image cannot hold three complete watermark frames."
        case .invalidID: return "A complete lowercase 128-bit hexadecimal identifier is required."
        case .invalidRectangle: return "Enter left,top,right,bottom within the decoded screenshot."
        }
    }
}

public struct RGBImage: Sendable, Equatable {
    public let width: Int
    public let height: Int
    public internal(set) var pixels: [UInt32] // Opaque ARGB, matching the Java core's bit layout.
    public init(width: Int, height: Int, pixels: [UInt32]) throws {
        guard width > 0, height > 0, width <= 16384, height <= 16384,
              width * height <= 20_000_000, pixels.count == width * height,
              pixels.allSatisfy({ $0 >> 24 == 255 }) else { throw ResearchError.invalidDimensions }
        self.width = width; self.height = height; self.pixels = pixels
    }
    public func cropped(_ box: [Int]) throws -> RGBImage {
        guard box.count == 4, box[0] >= 0, box[1] >= 0, box[2] <= width, box[3] <= height,
              box[2] > box[0], box[3] > box[1] else { throw ResearchError.invalidRectangle }
        var output = [UInt32](); output.reserveCapacity((box[2]-box[0])*(box[3]-box[1]))
        for y in box[1]..<box[3] { output.append(contentsOf: pixels[(y*width+box[0])..<(y*width+box[2])]) }
        return try RGBImage(width: box[2]-box[0], height: box[3]-box[1], pixels: output)
    }
    /// Explicit pixel-center bilinear interpolation in 8-bit sRGB, not an Apple codec promise.
    public func resized(width newWidth: Int, height newHeight: Int) throws -> RGBImage {
        guard newWidth > 0, newHeight > 0, newWidth <= 16384, newHeight <= 16384,
              newWidth * newHeight <= 20_000_000 else { throw ResearchError.invalidDimensions }
        if newWidth == width && newHeight == height { return self }
        var output = [UInt32](repeating: 0xff000000, count: newWidth*newHeight)
        for y in 0..<newHeight {
            let sy = min(Double(height-1), max(0, (Double(y)+0.5)*Double(height)/Double(newHeight)-0.5))
            let y0 = Int(floor(sy)), y1 = min(height-1, y0+1), fy = sy-Double(y0)
            for x in 0..<newWidth {
                let sx = min(Double(width-1), max(0, (Double(x)+0.5)*Double(width)/Double(newWidth)-0.5))
                let x0 = Int(floor(sx)), x1 = min(width-1, x0+1), fx = sx-Double(x0)
                var pixel: UInt32 = 0xff000000
                for shift in [16, 8, 0] {
                    let a = Double((pixels[y0*width+x0] >> shift)&255)
                    let b = Double((pixels[y0*width+x1] >> shift)&255)
                    let c = Double((pixels[y1*width+x0] >> shift)&255)
                    let d = Double((pixels[y1*width+x1] >> shift)&255)
                    let value = ((a*(1-fx)+b*fx)*(1-fy)+(c*(1-fx)+d*fx)*fy).rounded(.toNearestOrEven)
                    pixel |= UInt32(min(255, max(0, value))) << shift
                }
                output[y*newWidth+x] = pixel
            }
        }
        return try RGBImage(width: newWidth, height: newHeight, pixels: output)
    }
    public func atLongEdge(_ edge: Int, upscale: Bool) throws -> RGBImage {
        guard edge > 0, edge <= 16384 else { throw ResearchError.invalidDimensions }
        let scale = Double(edge)/Double(max(width,height))
        if !upscale && scale >= 1 { return self }
        return try resized(width: max(1,Int((Double(width)*scale).rounded(.toNearestOrEven))),
                           height: max(1,Int((Double(height)*scale).rounded(.toNearestOrEven))))
    }
}

public enum DCTCore {
    public static let frameBits = 176
    static let basis: [Double] = (0..<64).map { i in
        0.25 * cos(Double(2*(i/8)+1)*Double.pi/16) * cos(Double(2*(i%8)+1)*2*Double.pi/16)
    }
    static let crcTable: [UInt32] = (0..<256).map { i in
        var value = UInt32(i)
        for _ in 0..<8 { value = value & 1 != 0 ? 0xedb88320 ^ (value >> 1) : value >> 1 }
        return value
    }
    public static func crc32(_ bytes: [UInt8]) -> UInt32 {
        var crc: UInt32 = 0xffffffff
        for byte in bytes { crc = crcTable[Int((crc ^ UInt32(byte)) & 255)] ^ (crc >> 8) }
        return crc ^ 0xffffffff
    }
    public static func frame(_ id: String) throws -> [UInt8] {
        let text = Array(id.utf8)
        guard text.count == 32, text.allSatisfy({ (48...57).contains($0) || (97...102).contains($0) }) else { throw ResearchError.invalidID }
        func digit(_ b: UInt8) -> UInt8 { b >= 97 ? b-87 : b-48 }
        var bytes: [UInt8] = [80,67]
        for i in stride(from: 0, to: 32, by: 2) { bytes.append(digit(text[i])*16+digit(text[i+1])) }
        let crc = crc32(bytes)
        for shift in [24,16,8,0] { bytes.append(UInt8((crc >> shift)&255)) }
        return bytes
    }
    static func validate(_ image: RGBImage) throws {
        guard (image.width/8)*(image.height/8) >= frameBits*3 else { throw ResearchError.insufficientCapacity }
    }
    static func coefficient(_ image: RGBImage, _ bx: Int, _ by: Int) -> Double {
        var value = 0.0
        for y in 0..<8 { for x in 0..<8 {
            let p = image.pixels[(by+y)*image.width+bx+x]
            let luma = 0.299*Double((p >> 16)&255) + 0.587*Double((p >> 8)&255) + 0.114*Double(p&255)
            value += luma*basis[y*8+x]
        }}
        return value
    }
    public static func embed(_ image: RGBImage, id: String) throws -> RGBImage {
        try validate(image); let payload = try frame(id); var output = image; var block = 0
        for by in stride(from: 0, through: image.height-8, by: 8) {
            for bx in stride(from: 0, through: image.width-8, by: 8) {
                let index = block % frameBits; block += 1
                let bit = Double((payload[index/8] >> (7-index%8))&1)
                let c = coefficient(image,bx,by)
                let target = (2*((c/12-bit)/2).rounded(.toNearestOrEven)+bit)*12
                for y in 0..<8 { for x in 0..<8 {
                    let offset = (by+y)*image.width+bx+x, p = image.pixels[offset]
                    let delta = (target-c)*basis[y*8+x]; var changed: UInt32 = 0xff000000
                    for shift in [16,8,0] {
                        let channel = (Double((p >> shift)&255)+delta).rounded(.toNearestOrEven)
                        changed |= UInt32(max(0,min(255,channel))) << shift
                    }
                    output.pixels[offset] = changed
                }}
            }
        }
        return output
    }
    public static func extract(_ image: RGBImage) throws -> String? {
        try validate(image); var ones = [Int](repeating: 0,count: frameBits), total = ones, block = 0
        for by in stride(from: 0, through: image.height-8, by: 8) {
            for bx in stride(from: 0, through: image.width-8, by: 8) {
                let index = block % frameBits; block += 1; total[index] += 1
                let value = Int((coefficient(image,bx,by)/12).rounded(.toNearestOrEven))
                ones[index] += ((value%2)+2)%2
            }
        }
        var bytes = [UInt8](repeating: 0,count: 22)
        for i in 0..<frameBits {
            if ones[i]*2 == total[i] { return nil }
            if ones[i]*2 > total[i] { bytes[i/8] |= 1 << (7-i%8) }
        }
        guard bytes[0] == 80, bytes[1] == 67 else { return nil }
        let stored = bytes[18..<22].reduce(UInt32(0)) { ($0 << 8)|UInt32($1) }
        guard crc32(Array(bytes[0..<18])) == stored else { return nil }
        let alphabet = Array("0123456789abcdef".utf8)
        return String(decoding: bytes[2..<18].flatMap { [alphabet[Int($0 >> 4)],alphabet[Int($0&15)]] },as: UTF8.self)
    }
}

public struct SearchAttempt: Codable, Sendable, Equatable {
    public let geometry: String
    public let width: Int
    public let height: Int
    public let rectangle: [Int]
    public let status: String
    public let decodedID: String?
}
public struct Recovery: Codable, Sendable, Equatable {
    public let candidate: String
    public let decodedIDs: [String]
    public let attempts: [SearchAttempt]
    public let searchComplete: Bool
}
public enum RegisteredCandidate {
    public static let name = "ios-qim12-bilinear-v1"
    public static func uniformBorder(_ image: RGBImage) -> [Int]? {
        let color = image.pixels[0]; var left = image.width, top = image.height, right = -1, bottom = -1
        for y in 0..<image.height { for x in 0..<image.width where image.pixels[y*image.width+x] != color {
            left = min(left,x); right = max(right,x); top = min(top,y); bottom = max(bottom,y)
        }}
        guard right >= left, (right-left+1)*(bottom-top+1) >= image.width*image.height/4,
              !(left == 0 && top == 0 && right == image.width-1 && bottom == image.height-1) else { return nil }
        return [left,top,right+1,bottom+1]
    }
    public static func extract(_ image: RGBImage) throws -> Recovery { try search(image,decoder: DCTCore.extract) }
    static func search(_ image: RGBImage,decoder: (RGBImage) throws -> String?) throws -> Recovery {
        var ids = Set<String>(), attempts = [SearchAttempt]()
        func view(_ image: RGBImage,_ label: String,_ box: [Int]) throws {
            do {
                let id = try decoder(image); if let id { ids.insert(id) }
                attempts.append(SearchAttempt(geometry:label,width:image.width,height:image.height,rectangle:box,status:"searched",decodedID:id))
            } catch ResearchError.insufficientCapacity {
                attempts.append(SearchAttempt(geometry:label,width:image.width,height:image.height,rectangle:box,status:"insufficient_capacity",decodedID:nil))
            }
        }
        func region(_ image: RGBImage,_ label: String,_ box: [Int]) throws {
            try view(image,label+":native",box)
            if max(image.width,image.height) != 1024 { try view(image.atLongEdge(1024,upscale:true),label+":edge1024",box) }
        }
        try region(image,"whole",[0,0,image.width,image.height])
        if let box = uniformBorder(image) { try region(image.cropped(box),"uniform_border_trim",box) }
        precondition(attempts.count <= 4)
        return Recovery(candidate:name,decodedIDs:ids.sorted(),attempts:attempts,searchComplete:attempts.contains { $0.status == "searched" })
    }
}
