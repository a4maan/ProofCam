import Foundation

public enum ResearchUtilities {
    public static func rectangle(_ text: String) throws -> [Int]? {
        if text.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty { return nil }
        let values = text.split(separator: ",", omittingEmptySubsequences: false).map { Int($0.trimmingCharacters(in: .whitespacesAndNewlines)) }
        guard values.count == 4, values.allSatisfy({ $0 != nil }) else { throw ResearchError.invalidRectangle }
        return values.map { $0! }
    }
    public static func p95(_ values: [Double]) -> Double? {
        guard !values.isEmpty, values.allSatisfy({ $0.isFinite && $0 >= 0 }) else { return nil }
        return values.sorted()[Int(ceil(Double(values.count)*0.95))-1]
    }
    /// FileHandle reads may be short without reaching EOF. Never accept a truncated prefix.
    public static func readBounded(limit: Int, read: (Int) throws -> Data) throws -> Data {
        guard limit >= 0, limit < Int.max else { throw ResearchError.invalidDimensions }
        var result = Data()
        while result.count <= limit {
            let chunk = try read(min(65536, limit+1-result.count))
            if chunk.isEmpty { return result }
            guard chunk.count <= limit-result.count else { throw ResearchError.invalidDimensions }
            result.append(chunk)
        }
        throw ResearchError.invalidDimensions
    }
}
