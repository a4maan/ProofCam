import SwiftUI
import UniformTypeIdentifiers
import ImageIO
import CryptoKit
import Security
import Darwin

private func sha(_ data: Data) -> String { SHA256.hash(data: data).map { String(format: "%02x", $0) }.joined() }
private func recover(_ image: RGBImage,candidate: String) throws -> Recovery {
    if candidate==AdaptiveCandidate.name { return try AdaptiveCandidate.extract(image) }
    if candidate==TiledCandidate.name { return try TiledCandidate.extract(image) }
    return try RegisteredCandidate.extract(image)
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
    var embedP95Milliseconds: Double { ResearchUtilities.p95(samples.map(\.embedJPEGMilliseconds)) ?? 0 }
    var extractP95Milliseconds: Double { ResearchUtilities.p95(samples.map(\.extractMilliseconds)) ?? 0 }
    let candidate: String; let createdAt: Date; let operatingSystem: String; let runtime: String
    let sourceSHA256: String; let markedSHA256: String; let expectedID: String
    let warmups: Int; let samples: [Sample]; var screenshots: [ScreenshotResult]
    let memoryMeasurement: String = "not_measured"
}
@MainActor final class Model: ObservableObject {
    @Published var status = "Import a JPEG or PNG from Files. Research use only."
    @Published var busy = false
    @Published var candidateVersion = 3
    @Published var marked: Data?
    @Published var report: Report?
    func load(_ url: URL, screenshot: Bool, rectangle: String, attested: Bool) {
        guard !busy else { return }; busy = true
        if !screenshot { report = nil; marked = nil }
        let prior = report
        let version = candidateVersion
        let tiled = version != 1
        let candidate = version == 3 ? AdaptiveCandidate.name : tiled ? TiledCandidate.name : RegisteredCandidate.name
        Task {
            do {
                let result = try await Task.detached(priority: .userInitiated) { () -> (Data?, Report) in
                    let accessed = url.startAccessingSecurityScopedResource(); defer { if accessed { url.stopAccessingSecurityScopedResource() } }
                    let handle = try FileHandle(forReadingFrom: url); defer { try? handle.close() }
                    let data = try ResearchUtilities.readBounded(limit: 25*1024*1024) { try handle.read(upToCount: $0) ?? Data() }
                    let original = try AppleImageCodec.decode(data)
                    if screenshot {
                        guard var current = prior else { throw ResearchError.invalidID }
                        let box = try ResearchUtilities.rectangle(rectangle)
                        let region = try box.map { try original.cropped($0) } ?? original
                        let recovered = try recover(region,candidate:current.candidate)
                        current.screenshots.append(ScreenshotResult(sha256: sha(data), width: original.width, height: original.height, rectangle: box, operatorAttestedOSCapture: attested, recovery: recovered))
                        return (nil, current)
                    }
                    let input = try original.atLongEdge(1024, upscale: tiled)
                    var random = [UInt8](repeating: 0, count: 16)
                    guard SecRandomCopyBytes(kSecRandomDefault, random.count, &random) == errSecSuccess else { throw ResearchError.invalidID }
                    let id = random.map { String(format: "%02x", $0) }.joined()
                    var samples = [Sample](), output = Data()
                    for iteration in 0..<23 {
                        try autoreleasepool {
                        let start = DispatchTime.now().uptimeNanoseconds
                        let markedImage = try version == 3 ? AdaptiveCandidate.embed(input,id:id) : tiled ? TiledCandidate.embed(input,id:id) : DCTCore.embed(input,id:id)
                        output = try AppleImageCodec.jpeg(markedImage)
                        let encoded = DispatchTime.now().uptimeNanoseconds
                        let decoded = try AppleImageCodec.decode(output)
                        let extractStart = DispatchTime.now().uptimeNanoseconds
                        let recovery = try recover(decoded,candidate:candidate)
                        let end = DispatchTime.now().uptimeNanoseconds
                        if iteration >= 3 { samples.append(Sample(embedJPEGMilliseconds: Double(encoded-start)/1e6, extractMilliseconds: Double(end-extractStart)/1e6, recovery: recovery)) }
                        }
                        await MainActor.run { self.status = iteration < 3 ? "Warmup \(iteration+1)/3" : "Measured sample \(iteration-2)/20" }
                    }
                    #if targetEnvironment(simulator)
                    let runtime = "simulator"
                    #else
                    let runtime = "physical_device"
                    #endif
                    var system = utsname(); uname(&system)
                    let hardware = withUnsafeBytes(of: &system.machine) { bytes in String(decoding: bytes.prefix { $0 != 0 }, as: UTF8.self) }
                    let executable = Bundle.main.executableURL.flatMap { try? Data(contentsOf: $0) }.map(sha)
                    return (output, Report(hardwareModel: hardware, executableSHA256: executable, inputWidth: input.width, inputHeight: input.height, candidate: candidate, createdAt: Date(), operatingSystem: ProcessInfo.processInfo.operatingSystemVersionString, runtime: runtime, sourceSHA256: sha(data), markedSHA256: sha(output), expectedID: id, warmups: 3, samples: samples, screenshots: []))
                }.value
                if let data = result.0 { marked = data }; report = result.1
                let correct = result.1.samples.filter { $0.recovery.decodedIDs == [result.1.expectedID] }.count
                status = "\(result.1.candidate): \(correct)/20 JPEG recoveries. \(result.1.screenshots.count) screenshot tests recorded. Export JSON for all attempts. JPEG p95: \(Int(result.1.embedP95Milliseconds)) ms; extraction p95: \(Int(result.1.extractP95Milliseconds)) ms."
                if let last = result.1.screenshots.last { status += " Latest screenshot: " + (last.recovery.decodedIDs == [result.1.expectedID] ? "matching ID." : last.recovery.decodedIDs.isEmpty ? "no ID recovered." : "different or conflicting IDs.") }
            } catch ResearchError.insufficientCapacity where tiled {
                status = version == 3 ? "Failed: v3 needs at least a 132×120-pixel tile after normalization." : "Failed: v2 needs at least a 160×144-pixel tile after normalization."
            } catch { status = "Failed: \(error.localizedDescription)" }
            busy = false
        }
    }
}
@main struct ProofCamResearchApp: App { var body: some Scene { WindowGroup { ContentView() } } }
struct ContentView: View {
    @StateObject private var model = Model()
    @StateObject private var provenance = CaptureProvenance()
    @State private var importingEnrollment = false
    @State private var importing = false, screenshot = false, exporting = false, attested = false
    @State private var rectangle = "", filename = "report.json"
    @State private var document = ExportFile(data: Data())
    @State private var exportType: UTType = .json
    var body: some View {
        NavigationStack {
            Form {
                captureSection
                Section("Research benchmark") {
                    Text(model.status)
                    Picker("Watermark for next source", selection: $model.candidateVersion) { Text("v1").tag(1); Text("v2").tag(2); Text("v3").tag(3) }.pickerStyle(.segmented).disabled(model.busy)
                    Text("Applies to the next source. v2 favors stronger marking; v3 uses smaller tiles and adaptive strength. Both search for edited images and can take longer than v1.").font(.footnote)
                    if model.busy { ProgressView("Running locally…") }
                    Button("Choose image and run 20 samples") { importingEnrollment = false; screenshot = false; rectangle = ""; attested = false; importing = true }.disabled(model.busy)
                    if let data = model.marked, let image = UIImage(data: data) { Image(uiImage: image).resizable().scaledToFit() }
                    Button("Save marked JPEG") { export(model.marked, name: "proofcam-marked.jpg", type: .jpeg) }.disabled(model.marked == nil || model.busy)
                }
                Section("Screenshot recovery") {
                    Text("Save the marked JPEG, open it in a viewer, take an iOS screenshot, then save that screenshot to Files and import it here.")
                    TextField("Optional left,top,right,bottom", text: $rectangle).textInputAutocapitalization(.never)
                    Toggle("I captured this using iOS screenshot", isOn: $attested)
                    Button("Import screenshot") { importingEnrollment = false; screenshot = true; importing = true }.disabled(model.report == nil || model.busy)
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
        .fileImporter(isPresented: $importing, allowedContentTypes: importingEnrollment ? [.data] : [.jpeg,.png]) { result in
            switch result { case .success(let url):
                if importingEnrollment {
                    do { export(try provenance.enrollment(from: url), name: "proofcam-enrollment.cbor", type: .data) }
                    catch { provenance.status = "Enrollment preparation failed. Check the invitation and unlock the physical iPhone." }
                } else { model.load(url, screenshot: screenshot, rectangle: rectangle, attested: attested) }
            case .failure(let error): model.status = error.localizedDescription }
        }
        .fullScreenCover(isPresented: $provenance.showCamera) {
            ProofCamCamera(completed: { provenance.captured($0) }, cancelled: { provenance.showCamera = false })
                .ignoresSafeArea()
        }
        .fileExporter(isPresented: $exporting, document: document, contentType: exportType, defaultFilename: filename) { result in
            if case .failure(let error) = result { model.status = error.localizedDescription }
        }
    }
    private var captureSection: some View {
                Section("Capture provenance — development") {
                    Text(provenance.status)
                    Button("Prepare device enrollment") { importingEnrollment = true; importing = true }
                        .disabled(model.busy || provenance.busy)
                    Text("Select the private invitation file from your local server, then save the signed enrollment request. Keep both files private.").font(.footnote)
                    Button("Take and sign a photo") { provenance.startCamera() }.disabled(model.busy || provenance.busy)
                    if provenance.busy { ProgressView("Saving signed capture…") }
                    Button("Refresh saved captures") { provenance.refresh() }.disabled(provenance.busy)
                    ForEach(provenance.pending) { capture in
                        Text("Capture \(capture.id.prefix(8))" + (capture.hasRequest ? " — registration pending" : " — incomplete, photo retained"))
                        Button("Export capture JPEG") {
                            do { export(try Data(contentsOf: capture.jpeg), name: capture.id + ".jpg", type: .jpeg) }
                            catch { provenance.status = "Unable to read the saved photo." }
                        }
                        if capture.hasRequest {
                            Button("Export signed request") {
                                do { export(try Data(contentsOf: capture.request), name: capture.id + ".cbor", type: .data) }
                                catch { provenance.status = "Unable to read the saved request." }
                            }
                        }
                    }
                    Text("Device signatures bind exported bytes. Registration and independent verification run on your Mac. This does not certify camera origin or absence of AI.").font(.footnote)
                }
    }
    private func export(_ data: Data?, name: String, type: UTType) { guard let data else { return }; document = ExportFile(data: data); filename = name; exportType = type; exporting = true }
}
