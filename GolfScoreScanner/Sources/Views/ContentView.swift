import SwiftUI

/// Écran d'accueil : lance le scan, montre l'état de l'analyse,
/// puis navigue vers l'écran de correction / résultats.
struct ContentView: View {
    @State private var showScanner = false
    @State private var isAnalyzing = false
    @State private var scannedImage: UIImage?
    @State private var card: ScoreCard?
    @State private var errorMessage: String?

    var body: some View {
        NavigationStack {
            VStack(spacing: 24) {
                Spacer()

                Image(systemName: "figure.golf")
                    .font(.system(size: 72))
                    .foregroundStyle(.green)

                Text("Golf Score Scanner")
                    .font(.largeTitle.bold())

                Text("Photographiez votre carte de score : les scores sont lus automatiquement, vous les vérifiez, et le total est calculé pour vous.")
                    .font(.body)
                    .foregroundStyle(.secondary)
                    .multilineTextAlignment(.center)
                    .padding(.horizontal, 32)

                Spacer()

                if isAnalyzing {
                    ProgressView("Lecture de la carte…")
                } else {
                    Button {
                        showScanner = true
                    } label: {
                        Label("Scanner une carte", systemImage: "camera.viewfinder")
                            .font(.headline)
                            .frame(maxWidth: .infinity)
                    }
                    .buttonStyle(.borderedProminent)
                    .tint(.green)
                    .padding(.horizontal, 32)
                    .disabled(!DocumentScannerView.isSupported)

                    Button("Saisir manuellement") {
                        card = ScoreCard.standard18()
                        card?.players.append(PlayerRound(name: "Joueur 1"))
                    }
                    .font(.subheadline)
                }

                if let errorMessage {
                    Text(errorMessage)
                        .font(.footnote)
                        .foregroundStyle(.red)
                        .padding(.horizontal, 32)
                }

                Spacer(minLength: 40)
            }
            .navigationDestination(item: $card) { _ in
                if let binding = Binding($card) {
                    ScoreEditView(card: binding, image: scannedImage)
                }
            }
            .fullScreenCover(isPresented: $showScanner) {
                DocumentScannerView(
                    onScan: { image in
                        showScanner = false
                        analyze(image)
                    },
                    onCancel: { showScanner = false }
                )
                .ignoresSafeArea()
            }
        }
    }

    private func analyze(_ image: UIImage) {
        scannedImage = image
        isAnalyzing = true
        errorMessage = nil

        Task {
            do {
                let texts = try await TextRecognizer.recognizeText(in: image)
                var parsed = ScorecardParser.parse(texts)
                let nothingRead = parsed.players.isEmpty
                if nothingRead {
                    parsed.players.append(PlayerRound(name: "Joueur 1"))
                }
                await MainActor.run {
                    if nothingRead {
                        errorMessage = "Aucun score n'a pu être lu automatiquement — vérifiez la netteté de la photo. Vous pouvez saisir les scores manuellement."
                    }
                    card = parsed
                    isAnalyzing = false
                }
            } catch {
                await MainActor.run {
                    errorMessage = "La lecture de la carte a échoué : \(error.localizedDescription)"
                    isAnalyzing = false
                }
            }
        }
    }
}

extension ScoreCard: Hashable {
    func hash(into hasher: inout Hasher) {
        hasher.combine(courseName)
        hasher.combine(players.map(\.id))
    }
}

#Preview {
    ContentView()
}
