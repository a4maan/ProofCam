import SwiftUI
import UIKit
import AVFoundation
import CryptoKit
import Security

/// Development enrollment uses a real device key, but the server does not yet attest it.
enum CaptureKey {
    enum Failure: Error { case unavailable, keychain(OSStatus), accessControl }
    static func identifier() throws -> String {
        var bytes = [UInt8](repeating: 0, count: 16)
        guard SecRandomCopyBytes(kSecRandomDefault, bytes.count, &bytes) == errSecSuccess else { throw Failure.unavailable }
        return bytes.map { String(format: "%02x", $0) }.joined()
    }
    static func load() throws -> SecureEnclave.P256.Signing.PrivateKey {
        guard SecureEnclave.isAvailable else { throw Failure.unavailable }
        let query: [String: Any] = [kSecClass as String: kSecClassGenericPassword,
                                  kSecAttrService as String: "ProofCam.DevelopmentCapture.v1",
                                  kSecAttrAccount as String: "enclave-key",
                                  kSecAttrSynchronizable as String: false]
        var lookup = query
        lookup[kSecReturnData as String] = true
        var result: CFTypeRef?
        let status = SecItemCopyMatching(lookup as CFDictionary, &result)
        if status == errSecSuccess, let data = result as? Data {
            return try SecureEnclave.P256.Signing.PrivateKey(dataRepresentation: data)
        }
        guard status == errSecItemNotFound else { throw Failure.keychain(status) }
        guard let access = SecAccessControlCreateWithFlags(nil, kSecAttrAccessibleWhenUnlockedThisDeviceOnly,
                                                           .privateKeyUsage, nil) else { throw Failure.accessControl }
        let key = try SecureEnclave.P256.Signing.PrivateKey(compactRepresentable: false, accessControl: access)
        var item = query
        item[kSecValueData as String] = key.dataRepresentation
        item[kSecAttrAccessible as String] = kSecAttrAccessibleWhenUnlockedThisDeviceOnly
        let added = SecItemAdd(item as CFDictionary, nil)
        guard added == errSecSuccess else { throw Failure.keychain(added) }
        return key
    }
    static func signed(_ payload: Data, key: SecureEnclave.P256.Signing.PrivateKey, purpose: String) throws -> Data {
        let id = SHA256.hash(data: key.publicKey.x963Representation).map { String(format: "%02x", $0) }.joined()
        let input = try ProvenanceWire.signatureInput(payload: payload, keyID: id, purpose: purpose)
        return try ProvenanceWire.envelope(payload: payload, keyID: id, signature: key.signature(for: input).rawRepresentation)
    }
}

struct PendingCapture: Identifiable {
    let id: String
    let folder: URL
    var jpeg: URL { folder.appendingPathComponent("photo.jpg") }
    var request: URL { folder.appendingPathComponent("request.cbor") }
    var hasRequest: Bool { FileManager.default.fileExists(atPath: request.path) }
}

@MainActor final class CaptureProvenance: ObservableObject {
    @Published var status = "Camera captures can be saved with a device-signed request. Registration is a separate Mac step."
    @Published var pending = [PendingCapture]()
    @Published var appAttestExports = [URL]()
    @Published var busy = false
    @Published var showCamera = false
    init() { refresh() }

    func directory() throws -> URL {
        var url = try FileManager.default.url(for: .applicationSupportDirectory, in: .userDomainMask,
                                              appropriateFor: nil, create: true).appendingPathComponent("ProvenancePending", isDirectory: true)
        try FileManager.default.createDirectory(at: url, withIntermediateDirectories: true,
                                                attributes: [.protectionKey: FileProtectionType.complete])
        var values = URLResourceValues(); values.isExcludedFromBackup = true
        try url.setResourceValues(values)
        return url
    }
    func refresh() {
        do {
            let urls = try FileManager.default.contentsOfDirectory(at: directory(), includingPropertiesForKeys: nil)
            var attestFiles = urls.filter { $0.lastPathComponent.hasPrefix("app-attest-") && $0.pathExtension == "cbor" }
            for folder in urls where !folder.lastPathComponent.hasPrefix("app-attest-") {
                if let children = try? FileManager.default.contentsOfDirectory(at: folder, includingPropertiesForKeys: nil) {
                    attestFiles += children.filter { $0.lastPathComponent.hasPrefix("app-attest-") && $0.pathExtension == "cbor" }
                }
            }
            appAttestExports = attestFiles.sorted { $0.lastPathComponent < $1.lastPathComponent }
            pending = urls.filter { FileManager.default.fileExists(atPath: $0.appendingPathComponent("photo.jpg").path) }
                .map { PendingCapture(id: $0.lastPathComponent.trimmingCharacters(in: CharacterSet(charactersIn: ".")), folder: $0) }.sorted { $0.id < $1.id }
        } catch { status = "Saved captures are unavailable while storage is inaccessible. Unlock the phone and try again." }
    }
    func startCamera() {
        guard !busy else { return }
        guard UIImagePickerController.isSourceTypeAvailable(.camera), SecureEnclave.isAvailable else {
            status = "Camera signing requires a physical iPhone with Secure Enclave support."; return
        }
        Task {
            let granted = await AVCaptureDevice.requestAccess(for: .video)
            guard granted else { status = "Camera permission is needed. Enable it in Settings to capture."; return }
            do { _ = try CaptureKey.load(); showCamera = true }
            catch { status = "The protected signing key is unavailable. No software key was substituted." }
        }
    }
    func enrollment(from url: URL) throws -> Data {
        let accessed = url.startAccessingSecurityScopedResource()
        defer { if accessed { url.stopAccessingSecurityScopedResource() } }
        let handle = try FileHandle(forReadingFrom: url); defer { try? handle.close() }
        let data = try ResearchUtilities.readBounded(limit: 1024) { try handle.read(upToCount: $0) ?? Data() }
        let invitation = try ProvenanceWire.invitation(from: data)
        let key = try CaptureKey.load()
        return try CaptureKey.signed(ProvenanceWire.enrollment(publicKey: key.publicKey.x963Representation, invitation: invitation), key: key, purpose: "enroll")
    }
    func captured(_ image: UIImage) {
        showCamera = false
        guard !busy else { return }
        busy = true; status = "Finalizing and signing camera export…"
        // Downsize before creating an encoded intermediate; only the camera callback reaches here.
        let scale = min(1, 1024 / max(image.size.width, image.size.height))
        let format = UIGraphicsImageRendererFormat(); format.scale = 1; format.opaque = true
        let size = CGSize(width: max(1, floor(image.size.width * scale)), height: max(1, floor(image.size.height * scale)))
        let normalized = UIGraphicsImageRenderer(size: size, format: format).image { _ in image.draw(in: CGRect(origin: .zero, size: size)) }
        guard let data = normalized.jpegData(compressionQuality: 1) else { busy = false; status = "Camera export failed."; return }
        Task {
            do {
                let root = try directory()
                try await Task.detached(priority: .userInitiated) {
                    let id = try CaptureKey.identifier()
                    let session = try CaptureKey.identifier()
                    let key = try CaptureKey.load()
                    let source = try AppleImageCodec.decode(data).atLongEdge(1024, upscale: true)
                    let jpeg = try AppleImageCodec.jpeg(AdaptiveCandidate.embed(source, id: id))
                    let folder = root.appendingPathComponent("." + id, isDirectory: true)
                    try FileManager.default.createDirectory(at: folder, withIntermediateDirectories: false,
                                                            attributes: [.protectionKey: FileProtectionType.complete])
                    // Preserve the sole finalized photo if later signing/storage fails.
                    let photo = folder.appendingPathComponent("photo.jpg")
                    try jpeg.write(to: photo, options: [.atomic, .completeFileProtection])
                    let finalBytes = try Data(contentsOf: photo)
                    guard finalBytes == jpeg else { throw ProvenanceWire.Invalid.signature }
                    let digest = SHA256.hash(data: finalBytes).map { String(format: "%02x", $0) }.joined()
                    let payload = try ProvenanceWire.offlineCameraRequest(id: id, fileSHA256: digest, session: session)
                    let signed = try CaptureKey.signed(payload, key: key, purpose: "register")
                    try signed.write(to: folder.appendingPathComponent("request.cbor"), options: [.atomic, .completeFileProtection])
                    try FileManager.default.moveItem(at: folder, to: root.appendingPathComponent(id, isDirectory: true))
                }.value
                refresh(); status = "Saved locally. Export the JPEG and signed request, then register on your Mac. Camera origin and absence of AI are not certified."
            } catch {
                refresh(); status = "Capture finalization failed. Any written photo remains in protected local storage; no registration was claimed."
            }
            busy = false
        }
    }
}

struct ProofCamCamera: UIViewControllerRepresentable {
    let completed: (UIImage) -> Void
    let cancelled: () -> Void
    func makeCoordinator() -> Coordinator { Coordinator(self) }
    func makeUIViewController(context: Context) -> UIImagePickerController {
        let picker = UIImagePickerController()
        picker.sourceType = .camera; picker.cameraCaptureMode = .photo
        picker.mediaTypes = ["public.image"]; picker.allowsEditing = false
        picker.delegate = context.coordinator
        return picker
    }
    func updateUIViewController(_ controller: UIImagePickerController, context: Context) {}
    final class Coordinator: NSObject, UINavigationControllerDelegate, UIImagePickerControllerDelegate {
        let parent: ProofCamCamera
        init(_ parent: ProofCamCamera) { self.parent = parent }
        func imagePickerControllerDidCancel(_ picker: UIImagePickerController) { parent.cancelled() }
        func imagePickerController(_ picker: UIImagePickerController, didFinishPickingMediaWithInfo info: [UIImagePickerController.InfoKey: Any]) {
            guard let image = info[.originalImage] as? UIImage else { parent.cancelled(); return }
            parent.completed(image)
        }
    }
}
