import Foundation

/// Research v2: self-contained tiles, sign modulation, SECDED coding and pixel-phase search.
/// It deliberately trades distortion and search cost for geometric robustness.
public enum TiledCandidate {
    public static let name = "ios-tiled-sign24-secded-v2"
    static let tileWidth = 160, tileHeight = 144
    static let marker: [Int] = (0..<64).map { Int((UInt64(0xd39a65c72e81b40f) >> (63-$0)) & 1) }
    static let horizontal = (0..<8).map { cos(Double(2*$0+1)*2*Double.pi/16)*0.5 }
    static let vertical = (0..<8).map { cos(Double(2*$0+1)*Double.pi/16)*0.5 }
    static let dataPositions = [3,5,6,7,9,10,11,12]
    static func code(_ byte: UInt8) -> [Int] {
        var word = [Int](repeating:0,count:14)
        for (i,p) in dataPositions.enumerated() { word[p] = Int((byte >> (7-i)) & 1) }
        for p in [1,2,4,8] { for i in 1...12 where i & p != 0 && i != p { word[p] ^= word[i] } }
        word[13] = word[1...12].reduce(0,^)
        return Array(word[1...13])
    }
    static func uncode(_ bits: [Int]) -> UInt8? {
        guard bits.count == 13, bits.allSatisfy({ $0 == 0 || $0 == 1 }) else { return nil }
        var word = [0]+bits, syndrome = 0
        for i in 1...12 where word[i] != 0 { syndrome ^= i }
        let parity = word[1...13].reduce(0,^)
        if syndrome != 0 {
            guard parity == 1, syndrome <= 12 else { return nil }
            word[syndrome] ^= 1
        }
        return dataPositions.reduce(UInt8(0)) { ($0 << 1) | UInt8(word[$1]) }
    }
    public static func embed(_ image: RGBImage, id: String) throws -> RGBImage {
        let frame = try DCTCore.frame(id)
        guard image.width >= tileWidth, image.height >= tileHeight else { throw ResearchError.insufficientCapacity }
        let bits = marker + frame.flatMap(code)
        var output = image
        for ty in stride(from:0,through:image.height-tileHeight,by:tileHeight) {
            for tx in stride(from:0,through:image.width-tileWidth,by:tileWidth) {
                for (i,bit) in bits.enumerated() {
                    let bx = tx+(i%20)*8, by = ty+(i/20)*8
                    let target = bit == 1 ? 24.0 : -24.0
                    let delta = target-DCTCore.coefficient(image,bx,by)
                    for y in 0..<8 { for x in 0..<8 {
                        let offset = (by+y)*image.width+bx+x, pixel = image.pixels[offset]
                        var changed: UInt32 = 0xff000000
                        for shift in [16,8,0] {
                            let value = (Double((pixel >> shift)&255)+delta*DCTCore.basis[y*8+x]).rounded(.toNearestOrEven)
                            changed |= UInt32(min(255,max(0,value))) << shift
                        }
                        output.pixels[offset] = changed
                    }}
                }
            }
        }
        return output
    }
    /// Coefficients at every integer pixel phase, using a separable 8x8 filter.
    static func coefficients(_ image: RGBImage) -> [Double] {
        let w = image.width, h = image.height
        var row = [Double](repeating:0,count:w*h), result = row
        var luma = [Double](repeating:0,count:w*h)
        for i in image.pixels.indices { let p = image.pixels[i]; luma[i] = 0.299*Double((p>>16)&255)+0.587*Double((p>>8)&255)+0.114*Double(p&255) }
        for y in 0..<h { for x in 0..<(w-7) {
            var value = 0.0
            for dx in 0..<8 { value += luma[y*w+x+dx]*horizontal[dx] }
            row[y*w+x] = value
        }}
        for y in 0..<(h-7) { for x in 0..<(w-7) {
            var value = 0.0
            for dy in 0..<8 { value += row[(y+dy)*w+x]*vertical[dy] }
            result[y*w+x] = value
        }}
        return result
    }
    static func tiles(_ image: RGBImage) -> [(String,[Int])] {
        guard image.width >= tileWidth, image.height >= tileHeight else { return [] }
        let values = coefficients(image), w = image.width
        var found = [String:[Int]]()
        for y in 0...image.height-tileHeight { for x in 0...w-tileWidth {
            if !markerMatches(values,w,x,y) { continue }
            var bytes = [UInt8]()
            for index in 0..<22 {
                let bits = (0..<13).map { j -> Int in
                    let i = 64+index*13+j
                    return values[(y+(i/20)*8)*w+x+(i%20)*8] >= 0 ? 1 : 0
                }
                guard let byte = uncode(bits) else { break }
                bytes.append(byte)
            }
            guard bytes.count == 22, bytes[0] == 80, bytes[1] == 67 else { continue }
            let crc = bytes[18..<22].reduce(UInt32(0)) { ($0 << 8)|UInt32($1) }
            guard DCTCore.crc32(Array(bytes[0..<18])) == crc else { continue }
            let id = bytes[2..<18].map { String(format:"%02x",$0) }.joined()
            if found[id] == nil { found[id] = [x,y,x+tileWidth,y+tileHeight] }
        }}
        return found.keys.sorted().map { ($0,found[$0]!) }
    }
    static func markerMatches(_ values: [Double], _ w: Int, _ x: Int, _ y: Int) -> Bool {
        var errors = 0
        for i in 0..<64 {
            let value = values[(y+(i/20)*8)*w+x+(i%20)*8]
            if abs(value)<3 || (value >= 0 ? 1 : 0) != marker[i] { errors += 1 }
            if (i < 16 && errors > 2) || errors > 6 { return false }
        }
        return true
    }
    public static func oriented(_ image: RGBImage, turns: Int, mirrored: Bool) throws -> RGBImage {
        guard (0..<4).contains(turns) else { throw ResearchError.invalidRectangle }
        let w = turns%2 == 0 ? image.width : image.height, h = turns%2 == 0 ? image.height : image.width
        var pixels = [UInt32](repeating:0xff000000,count:w*h)
        for y in 0..<image.height { for x in 0..<image.width {
            let mx = mirrored ? image.width-1-x : x
            let target: (Int,Int)
            switch turns {
            case 0: target = (mx,y)
            case 1: target = (image.height-1-y,mx)
            case 2: target = (image.width-1-mx,image.height-1-y)
            default: target = (y,image.width-1-mx)
            }
            pixels[target.1*w+target.0] = image.pixels[y*image.width+x]
        }}
        return try RGBImage(width:w,height:h,pixels:pixels)
    }
    /// Same-canvas bilinear deskew. Unsupported angles remain a documented search limit.
    public static func rotated(_ image: RGBImage, degrees: Double) throws -> RGBImage {
        guard degrees.isFinite, abs(degrees) <= 180 else { throw ResearchError.invalidRectangle }
        let angle = degrees*Double.pi/180, c = cos(angle), s = sin(angle)
        let cx = Double(image.width-1)/2, cy = Double(image.height-1)/2
        var pixels = [UInt32](repeating:0xff000000,count:image.pixels.count)
        for y in 0..<image.height { for x in 0..<image.width {
            let dx = Double(x)-cx, dy = Double(y)-cy
            let sx = c*dx+s*dy+cx, sy = -s*dx+c*dy+cy
            guard sx >= 0, sy >= 0, sx <= Double(image.width-1), sy <= Double(image.height-1) else { continue }
            let x0 = Int(floor(sx)), y0 = Int(floor(sy)), x1 = min(image.width-1,x0+1), y1 = min(image.height-1,y0+1)
            let fx = sx-Double(x0), fy = sy-Double(y0)
            var pixel: UInt32 = 0xff000000
            for shift in [16,8,0] {
                let a = Double((image.pixels[y0*image.width+x0]>>shift)&255), b = Double((image.pixels[y0*image.width+x1]>>shift)&255)
                let d = Double((image.pixels[y1*image.width+x0]>>shift)&255), e = Double((image.pixels[y1*image.width+x1]>>shift)&255)
                let value = ((a*(1-fx)+b*fx)*(1-fy)+(d*(1-fx)+e*fx)*fy).rounded(.toNearestOrEven)
                pixel |= UInt32(max(0,min(255,value))) << shift
            }
            pixels[y*image.width+x] = pixel
        }}
        return try RGBImage(width:image.width,height:image.height,pixels:pixels)
    }
    /// Density-based crop for mostly solid viewer backgrounds; ignores small isolated controls.
    static func contentRectangle(_ image: RGBImage) -> [Int]? {
        func color(_ p: UInt32) -> UInt32 { p & 0xfff0f0f0 }
        var counts = [UInt32:Int]()
        for x in 0..<image.width { counts[color(image.pixels[x]),default:0] += 1; counts[color(image.pixels[(image.height-1)*image.width+x]),default:0] += 1 }
        for y in 0..<image.height { counts[color(image.pixels[y*image.width]),default:0] += 1; counts[color(image.pixels[y*image.width+image.width-1]),default:0] += 1 }
        guard let background = counts.keys.sorted().max(by:{ counts[$0]! < counts[$1]! }) else { return nil }
        var rows = [Int](repeating:0,count:image.height), columns = [Int](repeating:0,count:image.width)
        for y in 0..<image.height { for x in 0..<image.width where color(image.pixels[y*image.width+x]) != background { rows[y] += 1; columns[x] += 1 } }
        guard let top = rows.firstIndex(where:{$0 > image.width/4}), let bottom = rows.lastIndex(where:{$0 > image.width/4}),
              let left = columns.firstIndex(where:{$0 > image.height/4}), let right = columns.lastIndex(where:{$0 > image.height/4}),
              (right-left+1)*(bottom-top+1) >= image.width*image.height/4 else { return nil }
        let box = [left,top,right+1,bottom+1]
        return box == [0,0,image.width,image.height] ? nil : box
    }
    public static func extract(_ image: RGBImage) throws -> Recovery {
        // All hypotheses run, including after a match. No expected identifier is supplied.
        var attempts = [SearchAttempt](), ids = Set<String>()
        var regions: [(RGBImage,String,[Int])] = [(image,"whole",[0,0,image.width,image.height])]
        if let box = RegisteredCandidate.uniformBorder(image) { regions.append((try image.cropped(box),"uniform_border",box)) }
        if let box = contentRectangle(image), !regions.contains(where: { $0.2 == box }) { regions.append((try image.cropped(box),"dominant_background",box)) }
        for (region,label,box) in regions {
            let nativeEdge = max(region.width,region.height)
            let edges = [nativeEdge,512,768,1024,nativeEdge*2,max(1,nativeEdge/2)]
            var seen = Set<Int>()
            for edge in edges where seen.insert(edge).inserted {
                // Search budgets are explicit, not unlimited full-resolution work.
                guard edge <= 1600 else { continue }
                let resized = try region.atLongEdge(edge,upscale:true)
                for mirror in [false,true] { for turn in 0..<4 {
                    let view = try oriented(resized,turns:turn,mirrored:mirror)
                    let found = tiles(view)
                    let geometry = "\(label):edge\(edge):turn\(turn):mirror\(mirror)"
                    attempts.append(SearchAttempt(geometry:geometry,width:view.width,height:view.height,rectangle:box,status:view.width<tileWidth || view.height<tileHeight ? "insufficient_capacity" : "searched",decodedID:nil))
                    for (id,tile) in found {
                        ids.insert(id)
                        attempts.append(SearchAttempt(geometry:geometry+":tile_coordinates_in_transformed_view",width:view.width,height:view.height,rectangle:tile,status:"decoded",decodedID:id))
                    }
                }}
            }
        }
        let deskewSource = try image.atLongEdge(min(1024,max(image.width,image.height)),upscale:false)
        for step in -15...15 where step != 0 {
            let angle = Double(step)
            let view = try rotated(deskewSource,degrees:angle)
            let found = tiles(view), geometry = "whole:deskew\(angle):native_capped1024"
            attempts.append(SearchAttempt(geometry:geometry,width:view.width,height:view.height,rectangle:[0,0,image.width,image.height],status:view.width<tileWidth || view.height<tileHeight ? "insufficient_capacity" : "searched",decodedID:nil))
            for (id,tile) in found { ids.insert(id); attempts.append(SearchAttempt(geometry:geometry+":tile_coordinates_in_transformed_view",width:view.width,height:view.height,rectangle:tile,status:"decoded",decodedID:id)) }
        }
        return Recovery(candidate:name,decodedIDs:ids.sorted(),attempts:attempts,searchComplete:attempts.contains { $0.status == "searched" })
    }
}
