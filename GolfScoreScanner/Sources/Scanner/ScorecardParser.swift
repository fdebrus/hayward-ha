import Foundation
import CoreGraphics

/// Reconstruit une carte de score à partir des fragments de texte OCR.
///
/// Principe :
/// 1. Les fragments sont regroupés en lignes selon leur position verticale.
/// 2. La ligne d'en-tête contenant les numéros de trous (1, 2, 3…) définit
///    la position horizontale de chaque colonne.
/// 3. La ligne contenant « Par » donne le par de chaque trou.
/// 4. Chaque ligne commençant par un libellé non numérique suivie de chiffres
///    est traitée comme une ligne de joueur ; chaque chiffre est affecté au
///    trou dont la colonne est la plus proche.
///
/// L'OCR sur des cartes manuscrites est imparfait : le résultat est une
/// proposition que l'utilisateur corrige ensuite dans l'écran d'édition.
enum ScorecardParser {

    struct Row {
        let items: [RecognizedText]
        let centerY: CGFloat
    }

    static func parse(_ texts: [RecognizedText], courseName: String = "Parcours scanné") -> ScoreCard {
        var card = ScoreCard.standard18(courseName: courseName)
        guard !texts.isEmpty else { return card }

        let rows = groupIntoRows(texts)
        let columns = holeColumns(in: rows)

        if let parRow = rows.first(where: { isLabelRow($0, keyword: "par") }) {
            let pars = assignValues(in: parRow, to: columns, validRange: 3...6)
            for (hole, par) in pars {
                if let index = card.holes.firstIndex(where: { $0.number == hole }) {
                    card.holes[index].par = par
                }
            }
        }

        for row in rows {
            guard let name = playerName(in: row) else { continue }
            let strokes = assignValues(in: row, to: columns, validRange: 1...15)
            guard strokes.count >= 3 else { continue }
            card.players.append(PlayerRound(name: name, strokes: strokes))
        }

        return card
    }

    // MARK: - Regroupement en lignes

    static func groupIntoRows(_ texts: [RecognizedText]) -> [Row] {
        let sorted = texts.sorted { $0.boundingBox.midY > $1.boundingBox.midY }
        let tolerance = medianHeight(of: texts) * 0.6

        var rows: [[RecognizedText]] = []
        for text in sorted {
            if var last = rows.last,
               let ref = last.first,
               abs(ref.boundingBox.midY - text.boundingBox.midY) < tolerance {
                last.append(text)
                rows[rows.count - 1] = last
            } else {
                rows.append([text])
            }
        }
        return rows.map { items in
            let sortedItems = items.sorted { $0.boundingBox.midX < $1.boundingBox.midX }
            let centerY = items.map(\.boundingBox.midY).reduce(0, +) / CGFloat(items.count)
            return Row(items: sortedItems, centerY: centerY)
        }
    }

    private static func medianHeight(of texts: [RecognizedText]) -> CGFloat {
        let heights = texts.map(\.boundingBox.height).sorted()
        guard !heights.isEmpty else { return 0.02 }
        return heights[heights.count / 2]
    }

    // MARK: - Colonnes des trous

    /// Cherche la ligne d'en-tête contenant la plus longue suite de numéros
    /// de trous consécutifs et retourne la position X de chaque numéro.
    static func holeColumns(in rows: [Row]) -> [Int: CGFloat] {
        var best: [Int: CGFloat] = [:]
        for row in rows {
            var columns: [Int: CGFloat] = [:]
            var expected = 1
            for item in row.items {
                guard let value = Int(item.string.trimmingCharacters(in: .whitespaces)) else { continue }
                if value == expected || (value == 10 && expected <= 10) {
                    columns[value] = item.boundingBox.midX
                    expected = value + 1
                }
            }
            if columns.count > best.count { best = columns }
        }
        return best
    }

    // MARK: - Lignes de par et de joueurs

    private static func isLabelRow(_ row: Row, keyword: String) -> Bool {
        row.items.contains { $0.string.lowercased().contains(keyword) }
    }

    /// Un libellé non numérique en début de ligne, suivi d'au moins un chiffre.
    private static func playerName(in row: Row) -> String? {
        guard let first = row.items.first else { return nil }
        let label = first.string.trimmingCharacters(in: .whitespaces)
        guard Int(label) == nil, label.count >= 2 else { return nil }
        let lowered = label.lowercased()
        let reserved = ["par", "trou", "hole", "index", "hcp", "out", "in", "total", "tot", "distance", "m.", "mètres"]
        guard !reserved.contains(where: { lowered.contains($0) }) else { return nil }
        let hasNumbers = row.items.dropFirst().contains { Int($0.string.trimmingCharacters(in: .whitespaces)) != nil }
        return hasNumbers ? label : nil
    }

    /// Affecte chaque valeur numérique de la ligne au trou dont la colonne
    /// est la plus proche. Sans colonnes détectées, les valeurs sont
    /// affectées dans l'ordre aux trous 1, 2, 3…
    static func assignValues(in row: Row, to columns: [Int: CGFloat], validRange: ClosedRange<Int>) -> [Int: Int] {
        var result: [Int: Int] = [:]
        var fallbackHole = 1

        for item in row.items {
            guard let value = Int(item.string.trimmingCharacters(in: .whitespaces)),
                  validRange.contains(value) else { continue }

            if columns.isEmpty {
                result[fallbackHole] = value
                fallbackHole += 1
                continue
            }

            let x = item.boundingBox.midX
            guard let (hole, columnX) = columns.min(by: { abs($0.value - x) < abs($1.value - x) }) else { continue }
            // Rejette les valeurs trop éloignées de toute colonne
            // (typiquement les totaux OUT / IN / TOTAL).
            let spacing = averageSpacing(of: columns)
            guard abs(columnX - x) < spacing * 0.75 else { continue }
            result[hole] = value
        }
        return result
    }

    private static func averageSpacing(of columns: [Int: CGFloat]) -> CGFloat {
        let xs = columns.values.sorted()
        guard xs.count > 1 else { return 0.1 }
        let gaps = zip(xs.dropFirst(), xs).map(-)
        return gaps.reduce(0, +) / CGFloat(gaps.count)
    }
}
