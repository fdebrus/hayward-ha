import SwiftUI

/// Résultats calculés : aller / retour / total, écart au par,
/// score net et points Stableford si un handicap est renseigné.
struct ResultView: View {
    let card: ScoreCard

    var body: some View {
        List {
            ForEach(card.players) { player in
                let result = ScoreCalculator.result(for: player, on: card)
                Section(player.name.isEmpty ? "Joueur" : player.name) {
                    row("Aller (1-9)", "\(result.frontNine)")
                    row("Retour (10-18)", "\(result.backNine)")
                    row("Total brut", "\(result.total)", bold: true)
                    row("Par joué", "\(result.totalPar)")
                    row("Écart au par", vsParText(result.vsPar), color: result.vsPar <= 0 ? .green : .red)
                    if let net = result.netTotal {
                        row("Total net", "\(net)")
                    }
                    if let stableford = result.stablefordPoints {
                        row("Stableford", "\(stableford) pts")
                    }
                    if result.holesPlayed < card.holes.count {
                        Text("\(result.holesPlayed) trous renseignés sur \(card.holes.count)")
                            .font(.footnote)
                            .foregroundStyle(.orange)
                    }
                }
            }
        }
        .navigationTitle(card.courseName)
        .navigationBarTitleDisplayMode(.inline)
    }

    private func vsParText(_ vsPar: Int) -> String {
        switch vsPar {
        case 0: return "Par"
        case ..<0: return "\(vsPar)"
        default: return "+\(vsPar)"
        }
    }

    private func row(_ label: String, _ value: String, bold: Bool = false, color: Color? = nil) -> some View {
        HStack {
            Text(label)
            Spacer()
            Text(value)
                .font(bold ? .body.bold() : .body)
                .foregroundStyle(color ?? .primary)
        }
    }
}

#Preview {
    NavigationStack {
        ResultView(card: {
            var card = ScoreCard.standard18(courseName: "Golf de Preview")
            var player = PlayerRound(name: "Frédéric", handicap: 18)
            for hole in card.holes { player.strokes[hole.number] = hole.par + 1 }
            card.players = [player]
            return card
        }())
    }
}
