import Foundation

/// Research v3: lower-frequency carrier, minimum-change embedding and soft Viterbi decoding.
public enum AdaptiveCandidate {
    public static let name = "ios-tiled-adaptive-conv-v3"
    static let basis=(0..<36).map { i in (1.0/3)*cos(Double(2*(i/6)+1)*Double.pi/12)*cos(Double(2*(i%6)+1)*Double.pi/12) }
    public static func embed(_ image: RGBImage,id: String) throws -> RGBImage {
        let bits=TiledCandidate.marker + encodedFrame(try DCTCore.frame(id))
        guard image.width>=132,image.height>=120 else { throw ResearchError.insufficientCapacity }
        let plane=GrayPlane(image),coefficients=plane.coefficients(block:6)
        var output=image
        for ty in stride(from:0,through:image.height-120,by:120) { for tx in stride(from:0,through:image.width-132,by:132) {
            for (i,bit) in bits.enumerated() {
                let bx=tx+(i%22)*6,by=ty+(i/22)*6,c=coefficients[by*image.width+bx]
                var sum=0.0,squared=0.0
                for y in 0..<6 { for x in 0..<6 { let value=plane.pixels[(by+y)*image.width+bx+x];sum += value;squared += value*value } }
                let variance=max(0,squared/36-(sum/36)*(sum/36)),strength=max(12,min(60,12+2*max(0,sqrt(variance)-30)))
                let target=bit==1 ? max(strength,c):min(-strength,c),delta=target-c
                for y in 0..<6 { for x in 0..<6 {
                    let offset=(by+y)*image.width+bx+x,p=image.pixels[offset]
                    var changed: UInt32=0xff000000
                    for shift in [16,8,0] { let channel=(Double((p>>shift)&255)+delta*basis[y*6+x]).rounded(.toNearestOrEven); changed |= UInt32(max(0,min(255,channel))) << shift }
                    output.pixels[offset]=changed
                }}
            }
        }}
        return output
    }
    static func encodedFrame(_ bytes: [UInt8]) -> [Int] {
        let bits=bytes.flatMap { byte in (0..<8).map { Int((byte >> (7-$0))&1) } } + Array(repeating:0,count:6)
        var state=0,output=[Int]()
        for bit in bits {
            let register=(state<<1)|bit
            output.append((register & 0o171).nonzeroBitCount%2)
            output.append((register & 0o133).nonzeroBitCount%2)
            state=register&63
        }
        return output
    }
    static func frame(_ values: [Double]) -> String? {
        guard values.count==364,values.allSatisfy({$0.isFinite}) else { return nil }
        var metrics=[Double](repeating:.infinity,count:64),ambiguous=[Bool](repeating:false,count:64)
        metrics[0]=0
        var previous=[UInt8](repeating:0,count:182*64)
        for t in 0..<182 {
            var next=[Double](repeating:.infinity,count:64),ties=[Bool](repeating:false,count:64)
            for state in 0..<64 where metrics[state].isFinite { for bit in 0...1 {
                let register=(state<<1)|bit,target=register&63
                let a=(register & 0o171).nonzeroBitCount%2,b=(register & 0o133).nonzeroBitCount%2
                let cost=metrics[state]+((values[t*2]>=0 ? 1:0)==a ? 0:abs(values[t*2]))+((values[t*2+1]>=0 ? 1:0)==b ? 0:abs(values[t*2+1]))
                if cost<next[target] { next[target]=cost;previous[t*64+target]=UInt8(state);ties[target]=ambiguous[state] }
                else if cost==next[target] { ties[target]=true }
            }}
            metrics=next;ambiguous=ties
        }
        guard !ambiguous[0],metrics[0].isFinite else { return nil }
        var state=0,bits=[Int](repeating:0,count:182)
        for t in stride(from:181,through:0,by:-1) { bits[t]=state&1;state=Int(previous[t*64+state]) }
        guard state==0,bits[176..<182].allSatisfy({$0==0}) else { return nil }
        let bytes=(0..<22).map { byte in (0..<8).reduce(UInt8(0)) { ($0<<1)|UInt8(bits[byte*8+$1]) } }
        guard bytes[0]==80,bytes[1]==67,DCTCore.crc32(Array(bytes[0..<18]))==bytes[18..<22].reduce(UInt32(0),{($0<<8)|UInt32($1)}) else { return nil }
        return bytes[2..<18].map { String(format:"%02x",$0) }.joined()
    }
    static func tiles(_ image: GrayPlane, block: Int = 6, allOrientations: Bool = false, coarse: Int = 1, onSynchronization: ((Int) -> Void)? = nil) -> [(String,[Int])] {
        let w=image.width,raw=image.coefficients(block:block)
        let values=raw
        var found=[String:[Int]]()
        for mirror in allOrientations ? [false,true]:[false] { for turn in 0..<(allOrientations ? 4:1) {
            let tw=(turn%2==0 ? 22:20)*block,th=(turn%2==0 ? 20:22)*block
            guard w>=tw,image.height>=th else { continue }
            let sign = mirror != (turn%2==1) ? -1.0:1.0
            let offsets=(0..<428).map { i -> Int in
                let x=mirror ? 21-i%22:i%22,y=i/22
                let point: (Int,Int)
                switch turn { case 0:point=(x,y);case 1:point=(19-y,x);case 2:point=(21-x,19-y);default:point=(y,21-x) }
                return point.1*block*w+point.0*block
            }
            func matches(_ x: Int,_ y: Int,loose: Bool) -> Bool {
                let start=y*w+x
                var errors=0,energy=0.0
                for i in 0..<64 {
                    let value=values[start+offsets[i]]*sign
                    energy += abs(value)
                    if (value>=0 ? 1:0) != TiledCandidate.marker[i] { errors += 1 }
                    if (i<16 && errors>(loose ? 4:3)) || errors>(loose ? 14:10) { return false }
                }
                if energy>=96 && !loose { onSynchronization?(errors) }
                return energy>=96
            }
            var visited=Set<Int>()
            for y in stride(from:0,through:image.height-th,by:coarse) { for x in stride(from:0,through:w-tw,by:coarse) {
                guard matches(x,y,loose:coarse>1) else { continue }
                let radius=coarse-1
                for yy in max(0,y-radius)...min(image.height-th,y+radius) { for xx in max(0,x-radius)...min(w-tw,x+radius) {
                    let start=yy*w+xx
                    guard visited.insert(start).inserted,(coarse==1 || matches(xx,yy,loose:false)) else { continue }
                    let payload=(64..<428).map { values[start+offsets[$0]]*sign }
                    if let id=frame(payload),found[id]==nil { found[id]=[xx,yy,xx+tw,yy+th] }
                }}
            }}
        }}
        return found.keys.sorted().map { ($0,found[$0]!) }
    }
    public static func extract(_ image: RGBImage) throws -> Recovery {
        var ids=Set<String>(),attempts=[SearchAttempt]()
        @discardableResult func search(_ view: GrayPlane,_ label: String,_ box: [Int],block: Int,coarse: Int = 1) -> Int {
            var best=65
            let found=tiles(view,block:block,allOrientations:true,coarse:coarse,onSynchronization:{ best=min(best,$0) })
            attempts.append(SearchAttempt(geometry:label,width:view.width,height:view.height,rectangle:box,status:view.width<22*block || view.height<20*block ? "insufficient_capacity":"searched",decodedID:nil))
            for (id,tile) in found { ids.insert(id); attempts.append(SearchAttempt(geometry:label+":tile_coordinates_in_transformed_view",width:view.width,height:view.height,rectangle:tile,status:"decoded",decodedID:id)) }
            return best
        }
        var regions: [(RGBImage,String,[Int])]=[(image,"whole",[0,0,image.width,image.height])]
        if let box=RegisteredCandidate.uniformBorder(image) { regions.append((try image.cropped(box),"uniform_border",box)) }
        if let box=TiledCandidate.contentRectangle(image),!regions.contains(where:{$0.2==box}) { regions.append((try image.cropped(box),"dominant_background",box)) }
        for (region,label,box) in regions {
            let plane=GrayPlane(region),native=max(region.width,region.height)
            var seen=Set<Int>()
            for edge in [native,512,768,1024,native*2,max(1,native/2)] where edge<=1600 && seen.insert(edge).inserted {
                let resized=plane.resized(edge:edge)
                search(resized,"\(label):edge\(edge):all_symmetries",box,block:6)
                if edge==native { search(resized,"\(label):native_half_pitch",box,block:3) }
            }
        }
        // Full-angle search on a smaller luma plane, with both supported tile pitches.
        let small=GrayPlane(image).resized(edge:min(512,max(image.width,image.height)))
        var scores=[Double:Int]()
        for step in -90..<90 where step != 0 {
            let angle=Double(step)/2,view=small.transformed(degrees:angle)
            for block in [3,6] { let score=search(view,"whole:angle\(angle):pitch\(block):all_symmetries",[0,0,image.width,image.height],block:block,coarse:block==3 ? 2:3); scores[angle]=min(scores[angle] ?? 65,score) }
        }
        // Refine only the strongest synchronization hypotheses, not angles chosen using an expected ID.
        let native=GrayPlane(image).resized(edge:min(1024,max(image.width,image.height)))
        let angles=scores.keys.filter { scores[$0]!<=10 }.sorted {
            if scores[$0] != scores[$1] { return scores[$0]!<scores[$1]! }
            return abs($0)==abs($1) ? $0<$1:abs($0)<abs($1)
        }
        for angle in angles.prefix(4) { for delta in [-0.25,0,0.25] {
            search(native.transformed(degrees:angle+delta),"whole:refined_angle\(angle+delta):all_symmetries",[0,0,image.width,image.height],block:6,coarse:3)
        }}
        return Recovery(candidate:name,decodedIDs:ids.sorted(),attempts:attempts,searchComplete:attempts.contains { $0.status=="searched" })
    }
}
