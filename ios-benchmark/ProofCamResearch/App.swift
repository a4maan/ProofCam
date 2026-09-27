import SwiftUI
import UniformTypeIdentifiers
import ImageIO
import CryptoKit
import Security
import Darwin

private func sha(_ data: Data) -> String { SHA256.hash(data: data).map { String(format: "%02x", $0) }.joined() }
private func decode(_ data: Data) throws -> RGBImage {
    guard data.count <= 25*1024*1024,
          let source = CGImageSourceCreateWithData(data as CFData, nil), CGImageSourceGetCount(source) == 1,
          let type = CGImageSourceGetType(source) as String?, ["public.jpeg", "public.png"].contains(type),
          let properties = CGImageSourceCopyPropertiesAtIndex(source, 0, nil) as? [CFString: Any],
          let width = properties[kCGImagePropertyPixelWidth] as? Int,
          let height = properties[kCGImagePropertyPixelHeight] as? Int,
          width > 0, height > 0, width <= 16384, height <= 16384, width*height <= 20_000_000,
          let image = CGImageSourceCreateThumbnailAtIndex(source, 0, [
            kCGImageSourceCreateThumbnailFromImageAlways: true,
            kCGImageSourceCreateThumbnailWithTransform: true,
            kCGImageSourceThumbnailMaxPixelSize: max(width,height)] as CFDictionary)
    else { throw ResearchError.invalidDimensions }
    var bytes = [UInt8](repeating: 0, count: image.width*image.height*4)
    let rendered = bytes.withUnsafeMutableBytes { buffer -> Bool in
        guard let context = CGContext(data: buffer.baseAddress, width: image.width, height: image.height,
            bitsPerComponent: 8, bytesPerRow: image.width*4, space: CGColorSpace(name: CGColorSpace.sRGB)!,
            bitmapInfo: CGBitmapInfo.byteOrder32Big.rawValue | CGImageAlphaInfo.premultipliedLast.rawValue) else { return false }
        context.draw(image, in: CGRect(x: 0, y: 0, width: CGFloat(image.width), height: CGFloat(image.height))); return true
    }
    guard rendered else { throw ResearchError.invalidDimensions }
    return try RGBImage(width: image.width, height: image.height, pixels: stride(from: 0, to: bytes.count, by: 4).map {
        UInt32(bytes[$0+3]) << 24 | UInt32(bytes[$0]) << 16 | UInt32(bytes[$0+1]) << 8 | UInt32(bytes[$0+2])
    })
}
private func jpeg(_ image: RGBImage) throws -> Data {
    var bytes = [UInt8](); bytes.reserveCapacity(image.pixels.count*4)
    for p in image.pixels { bytes += [UInt8((p>>16)&255), UInt8((p>>8)&255), UInt8(p&255),255] }
    guard let provider = CGDataProvider(data: Data(bytes) as CFData),
          let cg = CGImage(width: image.width, height: image.height, bitsPerComponent: 8, bitsPerPixel: 32,
            bytesPerRow: image.width*4, space: CGColorSpace(name: CGColorSpace.sRGB)!,
            bitmapInfo: CGBitmapInfo(rawValue: CGBitmapInfo.byteOrder32Big.rawValue | CGImageAlphaInfo.premultipliedLast.rawValue),
            provider: provider, decode: nil, shouldInterpolate: false, intent: .defaultIntent)
    else { throw ResearchError.invalidDimensions }
    let output = NSMutableData()
    guard let destination = CGImageDestinationCreateWithData(output, UTType.jpeg.identifier as CFString, 1, nil) else { throw ResearchError.invalidDimensions }
    CGImageDestinationAddImage(destination, cg, [kCGImageDestinationLossyCompressionQuality: 0.95] as CFDictionary)
    guard CGImageDestinationFinalize(destination) else { throw ResearchError.invalidDimensions }
    return output as Data
}
struct ExportFile: FileDocument {
    static var readableContentTypes: [UTType] { [.data] }
    var data: Data
    init(data: Data) { self.data = data }
    init(configuration: ReadConfiguration) throws { data = configuration.file.regularFileContents ?? Data() }
    func fileWrapper(configuration: WriteConfiguration) throws -> FileWrapper { FileWrapper(regularFileWithContents: data) }
}
struct Sample: Codable { let embedJPEGMilliseconds: Double; let extractMilliseconds: Double; let recovery: Recovery }
struct ScreenshotResult: Codable { let sha256: String; let width: Int; let height: Int; let rectangle: [Int]?; let operatorAttestedOSCapture: Bool; let recovery: Recovery }
struct Report: Codable {
    let hardwareModel: String; let executableSHA256: String?
    let inputWidth: Int; let inputHeight: Int
    var embedP95Milliseconds: Double { samples.map(\.embedJPEGMilliseconds).sorted()[18] }
    var extractP95Milliseconds: Double { samples.map(\.extractMilliseconds).sorted()[18] }
    let candidate: String; let createdAt: Date; let operatingSystem: String; let runtime: String
    let sourceSHA256: String; let markedSHA256: String; let expectedID: String
    let warmups: Int; let samples: [Sample]; var screenshots: [ScreenshotResult]
    let memoryMeasurement: String = "not_measured"
}
@MainActor final class Model: ObservableObject {
    @Published var status = "Import a JPEG or PNG from Files. Research use only."
    @Published var busy = false
    @Published var marked: Data?
    @Published var report: Report?
    func load(_ url: URL, screenshot: Bool, rectangle: String, attested: Bool) {
        guard !busy else { return }; busy = true
        if !screenshot { report = nil; marked = nil }
        let prior = report
        Task {
            do {
                let result = try await Task.detached(priority: .userInitiated) { () -> (Data?, Report) in
                    let accessed = url.startAccessingSecurityScopedResource(); defer { if accessed { url.stopAccessingSecurityScopedResource() } }
                    let handle = try FileHandle(forReadingFrom: url); defer { try? handle.close() }
                    let data = try handle.read(upToCount: 25*1024*1024+1) ?? Data()
                    let original = try decode(data)
                    if screenshot {
                        guard var current = prior else { throw ResearchError.invalidID }
                        let box: [Int]?
                        if rectangle.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty { box = nil }
                        else {
                            let values = rectangle.split(separator: ",", omittingEmptySubsequences: false).map { Int($0.trimmingCharacters(in: .whitespaces)) }
                            guard values.count == 4, values.allSatisfy({ $0 != nil }) else { throw ResearchError.invalidRectangle }
                            box = values.map { $0! }
                        }
                        let region = try box.map { try original.cropped($0) } ?? original
                        let recovered = try RegisteredCandidate.extract(region)
                        current.screenshots.append(ScreenshotResult(sha256: sha(data), width: original.width, height: original.height, rectangle: box, operatorAttestedOSCapture: attested, recovery: recovered))
                        return (nil, current)
                    }
                    let input = try original.atLongEdge(1024, upscale: false)
                    var random = [UInt8](repeating: 0, count: 16)
                    guard SecRandomCopyBytes(kSecRandomDefault, random.count, &random) == errSecSuccess else { throw ResearchError.invalidID }
                    let id = random.map { String(format: "%02x", $0) }.joined()
                    var samples = [Sample](), output = Data()
                    for iteration in 0..<23 {
                        let start = DispatchTime.now().uptimeNanoseconds
                        output = try jpeg(DCTCore.embed(input, id: id))
                        let encoded = DispatchTime.now().uptimeNanoseconds
                        let decoded = try decode(output)
                        let extractStart = DispatchTime.now().uptimeNanoseconds
                        let recovery = try RegisteredCandidate.extract(decoded)
                        let end = DispatchTime.now().uptimeNanoseconds
                        if iteration >= 3 { samples.append(Sample(embedJPEGMilliseconds: Double(encoded-start)/1e6, extractMilliseconds: Double(end-extractStart)/1e6, recovery: recovery)) }
                    }
                    #if targetEnvironment(simulator)
                    let runtime = "simulator"
                    #else
                    let runtime = "physical_device"
                    #endif
                    var system = utsname(); uname(&system)
                    let hardware = withUnsafeBytes(of: &system.machine) { bytes in String(decoding: bytes.prefix { $0 != 0 }, as: UTF8.self) }
                    let executable = Bundle.main.executableURL.flatMap { try? Data(contentsOf: $0) }.map(sha)
                    return (output, Report(hardwareModel: hardware, executableSHA256: executable, inputWidth: input.width, inputHeight: input.height, candidate: RegisteredCandidate.name, createdAt: Date(), operatingSystem: ProcessInfo.processInfo.operatingSystemVersionString, runtime: runtime, sourceSHA256: sha(data), markedSHA256: sha(output), expectedID: id, warmups: 3, samples: samples, screenshots: []))
                }.value
                if let data = result.0 { marked = data }; report = result.1
                let correct = result.1.samples.filter { $0.recovery.decodedIDs == [result.1.expectedID] }.count
                status = "Completed: \(correct)/20 JPEG recoveries. \(result.1.screenshots.count) screenshot tests recorded. Export JSON for all attempts. JPEG p95: \(Int(result.1.embedP95Milliseconds)) ms; extraction p95: \(Int(result.1.extractP95Milliseconds)) ms."
                if let last = result.1.screenshots.last { status += " Latest screenshot: " + (last.recovery.decodedIDs == [result.1.expectedID] ? "matching ID." : last.recovery.decodedIDs.isEmpty ? "no ID recovered." : "different or conflicting IDs.") }
            } catch { status = "Failed: \(error.localizedDescription)" }
            busy = false
        }
    }
}
@main struct ProofCamResearchApp: App { var body: some Scene { WindowGroup { ContentView() } } }
struct ContentView: View {
    @StateObject private var model = Model()
    @State private var importing = false, screenshot = false, exporting = false, attested = false
    @State private var rectangle = "", filename = "report.json"
    @State private var document = ExportFile(data: Data())
    @State private var exportType: UTType = .json
    var body: some View {
        NavigationStack {
            Form {
                Section("Research benchmark") {
                    Text(model.status)
                    if model.busy { ProgressView("Running locally…") }
                    Button("Choose image and run 20 samples") { screenshot = false; importing = true }.disabled(model.busy)
                    if let data = model.marked, let image = UIImage(data: data) { Image(uiImage: image).resizable().scaledToFit() }
                    Button("Save marked JPEG") { export(model.marked, name: "proofcam-marked.jpg", type: .jpeg) }.disabled(model.marked == nil || model.busy)
                }
                Section("Screenshot recovery") {
                    Text("Save the marked JPEG, open it in a viewer, take an iOS screenshot, then save that screenshot to Files and import it here.")
                    TextField("Optional left,top,right,bottom", text: $rectangle).textInputAutocapitalization(.never)
                    Toggle("I captured this using iOS screenshot", isOn: $attested)
                    Button("Import screenshot") { screenshot = true; importing = true }.disabled(model.report == nil || model.busy)
                }
                Section {
                    Button("Export research JSON") {
                        do { let encoder = JSONEncoder(); encoder.outputFormatting = [.prettyPrinted,.sortedKeys]; encoder.dateEncodingStrategy = .iso8601
                            export(try encoder.encode(model.report), name: "proofcam-report.json", type: .json)
                        } catch { model.status = error.localizedDescription }
                    }.disabled(model.report == nil || model.busy)
                    Text("This prototype tests watermark recovery. A detected identifier is not proof that a photo is authentic. No network services are used.").font(.footnote)
                }
            }.navigationTitle("ProofCam Research")
        }
        .fileImporter(isPresented: $importing, allowedContentTypes: [.jpeg,.png]) { result in
            switch result { case .success(let url): model.load(url, screenshot: screenshot, rectangle: rectangle, attested: attested)
            case .failure(let error): model.status = error.localizedDescription }
        }
        .fileExporter(isPresented: $exporting, document: document, contentType: exportType, defaultFilename: filename) { result in
            if case .failure(let error) = result { model.status = error.localizedDescription }
        }
    }
    private func export(_ data: Data?, name: String, type: UTType) { guard let data else { return }; document = ExportFile(data: data); filename = name; exportType = type; exporting = true }
}
