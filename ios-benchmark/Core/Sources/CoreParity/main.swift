import Foundation
import ProofCamCore
let directory = URL(fileURLWithPath: CommandLine.arguments[1])
func read(_ name: String) throws -> RGBImage {
    let bytes = Array(try Data(contentsOf: directory.appendingPathComponent(name)))
    guard bytes.count >= 8 else { throw ResearchError.invalidDimensions }
    func integer(_ start: Int) -> Int { bytes[start..<start+4].reduce(0) { ($0 << 8) | Int($1) } }
    let width = integer(0), height = integer(4)
    guard width <= 16384, height <= 16384, bytes.count == 8+width*height*3 else { throw ResearchError.invalidDimensions }
    let pixels = stride(from: 8, to: bytes.count, by: 3).map { 0xff000000 | UInt32(bytes[$0]) << 16 | UInt32(bytes[$0+1]) << 8 | UInt32(bytes[$0+2]) }
    return try RGBImage(width: width, height: height, pixels: pixels)
}
for line in try String(contentsOf: directory.appendingPathComponent("jobs.tsv"), encoding: .utf8).split(separator: "\n") {
    let parts = line.split(separator: "\t").map(String.init), name = parts[0], id = parts[1]
    for suffix in ["-python", "-java"] {
        guard try DCTCore.extract(read(name+suffix+".rgb")) == id else { fatalError("Cross-decoder mismatch: \(name)\(suffix)") }
    }
    let marked = try DCTCore.embed(read(name+".rgb"), id: id)
    guard try DCTCore.extract(marked) == id else { fatalError("Round trip mismatch") }
    var output = Data()
    for value in [marked.width, marked.height] { for shift in [24,16,8,0] { output.append(UInt8((value >> shift)&255)) } }
    for p in marked.pixels { for shift in [16,8,0] { output.append(UInt8((p >> shift)&255)) } }
    try output.write(to: directory.appendingPathComponent(name+"-swift.rgb"))
    print("PASS \(name): Python/Java → Swift; Swift round trip")
}
