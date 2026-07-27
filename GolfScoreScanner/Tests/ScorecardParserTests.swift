import XCTest
import CoreGraphics
@testable import GolfScoreScanner

final class ScorecardParserTests: XCTestCase {

    /// Fabrique un fragment OCR synthétique : `x` et `y` sont les centres
    /// normalisés (repère Vision, origine en bas à gauche).
    private func text(_ string: String, x: CGFloat, y: CGFloat) -> RecognizedText {
        RecognizedText(string: string,
                       boundingBox: CGRect(x: x - 0.02, y: y - 0.015, width: 0.04, height: 0.03))
    }

    /// Une carte 9 trous simulée : en-tête de trous, ligne de par,
    /// une ligne joueur, plus une colonne TOTAL à ignorer.
    private func nineHoleTexts() -> [RecognizedText] {
        var texts: [RecognizedText] = []
        let xs: [CGFloat] = (0..<9).map { 0.2 + CGFloat($0) * 0.08 }

        texts.append(text("Trou", x: 0.08, y: 0.8))
        for (index, x) in xs.enumerated() {
            texts.append(text("\(index + 1)", x: x, y: 0.8))
        }
        texts.append(text("TOT", x: 0.95, y: 0.8))

        texts.append(text("Par", x: 0.08, y: 0.7))
        let pars = [4, 3, 5, 4, 4, 3, 4, 5, 4]
        for (index, par) in pars.enumerated() {
            texts.append(text("\(par)", x: xs[index], y: 0.7))
        }
        texts.append(text("36", x: 0.95, y: 0.7))

        texts.append(text("Marc", x: 0.08, y: 0.6))
        let strokes = [5, 4, 6, 4, 5, 3, 5, 6, 4]
        for (index, s) in strokes.enumerated() {
            texts.append(text("\(s)", x: xs[index], y: 0.6))
        }
        texts.append(text("42", x: 0.95, y: 0.6))

        return texts
    }

    func testRowGroupingKeepsAlignedItemsTogether() {
        let rows = ScorecardParser.groupIntoRows(nineHoleTexts())
        XCTAssertEqual(rows.count, 3)
        // Les lignes sont triées de haut en bas et de gauche à droite.
        XCTAssertEqual(rows[0].items.first?.string, "Trou")
        XCTAssertEqual(rows[1].items.first?.string, "Par")
        XCTAssertEqual(rows[2].items.first?.string, "Marc")
    }

    func testHoleColumnsDetectedFromHeader() {
        let rows = ScorecardParser.groupIntoRows(nineHoleTexts())
        let columns = ScorecardParser.holeColumns(in: rows)
        XCTAssertEqual(columns.count, 9)
        XCTAssertEqual(Set(columns.keys), Set(1...9))
    }

    func testParseExtractsParsPlayerAndIgnoresTotals() {
        let card = ScorecardParser.parse(nineHoleTexts())

        XCTAssertEqual(card.holes[0].par, 4)
        XCTAssertEqual(card.holes[1].par, 3)
        XCTAssertEqual(card.holes[2].par, 5)

        XCTAssertEqual(card.players.count, 1)
        let player = card.players[0]
        XCTAssertEqual(player.name, "Marc")
        XCTAssertEqual(player.strokes[1], 5)
        XCTAssertEqual(player.strokes[3], 6)
        XCTAssertEqual(player.strokes[9], 4)
        // La colonne TOTAL (42) ne doit pas être affectée à un trou.
        XCTAssertFalse(player.strokes.values.contains(42))
        XCTAssertEqual(player.strokes.count, 9)
    }

    func testParseWithNoTextReturnsEmptyStandardCard() {
        let card = ScorecardParser.parse([])
        XCTAssertEqual(card.holes.count, 18)
        XCTAssertTrue(card.players.isEmpty)
    }
}
