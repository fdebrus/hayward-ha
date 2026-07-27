import Foundation
import Vision
import UIKit

/// Un fragment de texte reconnu par l'OCR, avec sa position normalisée
/// dans l'image (repère Vision : origine en bas à gauche, valeurs 0...1).
struct RecognizedText: Equatable {
    let string: String
    let boundingBox: CGRect
}

enum TextRecognizerError: Error {
    case invalidImage
}

/// Enveloppe autour de Vision (VNRecognizeTextRequest) pour extraire
/// tout le texte d'une photo de carte de score.
enum TextRecognizer {

    static func recognizeText(in image: UIImage) async throws -> [RecognizedText] {
        guard let cgImage = image.cgImage else { throw TextRecognizerError.invalidImage }

        return try await withCheckedThrowingContinuation { continuation in
            let request = VNRecognizeTextRequest { request, error in
                if let error {
                    continuation.resume(throwing: error)
                    return
                }
                let observations = (request.results as? [VNRecognizedTextObservation]) ?? []
                let results = observations.compactMap { observation -> RecognizedText? in
                    guard let candidate = observation.topCandidates(1).first else { return nil }
                    return RecognizedText(string: candidate.string, boundingBox: observation.boundingBox)
                }
                continuation.resume(returning: results)
            }
            // Les cartes de score sont souvent manuscrites : le mode "accurate"
            // avec correction de langue désactivée donne les meilleurs chiffres.
            request.recognitionLevel = .accurate
            request.usesLanguageCorrection = false
            request.recognitionLanguages = ["fr-FR", "en-US"]

            let handler = VNImageRequestHandler(cgImage: cgImage, options: [:])
            DispatchQueue.global(qos: .userInitiated).async {
                do {
                    try handler.perform([request])
                } catch {
                    continuation.resume(throwing: error)
                }
            }
        }
    }
}
