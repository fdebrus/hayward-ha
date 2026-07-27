import XCTest
@testable import GolfScoreScanner

final class ScoreCalculatorTests: XCTestCase {

    private func card(withPlayer player: PlayerRound) -> ScoreCard {
        var card = ScoreCard.standard18()
        card.players = [player]
        return card
    }

    func testTotalAndNinesForFullRound() {
        var player = PlayerRound(name: "Test")
        let testCard = ScoreCard.standard18()
        for hole in testCard.holes { player.strokes[hole.number] = 5 }

        let result = ScoreCalculator.result(for: player, on: card(withPlayer: player))

        XCTAssertEqual(result.frontNine, 45)
        XCTAssertEqual(result.backNine, 45)
        XCTAssertEqual(result.total, 90)
        XCTAssertEqual(result.totalPar, 72)
        XCTAssertEqual(result.vsPar, 18)
        XCTAssertEqual(result.holesPlayed, 18)
    }

    func testPartialRoundOnlyCountsPlayedHoles() {
        var player = PlayerRound(name: "Test")
        player.strokes = [1: 4, 2: 5, 3: 3]

        let result = ScoreCalculator.result(for: player, on: card(withPlayer: player))

        XCTAssertEqual(result.total, 12)
        XCTAssertEqual(result.totalPar, 11) // pars 4 + 4 + 3
        XCTAssertEqual(result.vsPar, 1)
        XCTAssertEqual(result.holesPlayed, 3)
        XCTAssertNil(result.netTotal)
        XCTAssertNil(result.stablefordPoints)
    }

    func testReceivedStrokesDistribution() {
        // Handicap 18 sur 18 trous : exactement 1 coup rendu par trou.
        let hole = Hole(number: 7, par: 4, strokeIndex: 7)
        XCTAssertEqual(ScoreCalculator.receivedStrokes(handicap: 18, hole: hole, holeCount: 18), 1)

        // Handicap 20 : 1 coup partout + 1 de plus sur les index 1 et 2.
        let easyHole = Hole(number: 1, par: 4, strokeIndex: 15)
        let hardHole = Hole(number: 2, par: 4, strokeIndex: 1)
        XCTAssertEqual(ScoreCalculator.receivedStrokes(handicap: 20, hole: easyHole, holeCount: 18), 1)
        XCTAssertEqual(ScoreCalculator.receivedStrokes(handicap: 20, hole: hardHole, holeCount: 18), 2)

        // Handicap 0 : aucun coup rendu.
        XCTAssertEqual(ScoreCalculator.receivedStrokes(handicap: 0, hole: hole, holeCount: 18), 0)
    }

    func testNetTotalWithHandicap() {
        var player = PlayerRound(name: "Test", handicap: 18)
        let testCard = ScoreCard.standard18()
        for hole in testCard.holes { player.strokes[hole.number] = hole.par + 1 }

        let result = ScoreCalculator.result(for: player, on: card(withPlayer: player))

        XCTAssertEqual(result.total, 90)
        XCTAssertEqual(result.netTotal, 72) // bogey partout - 1 coup rendu par trou = par net
    }

    func testStablefordBogeyGolferWithMatchingHandicapScores36() {
        var player = PlayerRound(name: "Test", handicap: 18)
        let testCard = ScoreCard.standard18()
        for hole in testCard.holes { player.strokes[hole.number] = hole.par + 1 }

        let result = ScoreCalculator.result(for: player, on: card(withPlayer: player))

        XCTAssertEqual(result.stablefordPoints, 36) // par net sur chaque trou = 2 pts × 18
    }

    func testStablefordNeverNegative() {
        var player = PlayerRound(name: "Test", handicap: 0)
        player.strokes = [1: 12] // +8 sur un par 4

        let points = ScoreCalculator.stablefordPoints(for: player, on: card(withPlayer: player))

        XCTAssertEqual(points, 0)
    }
}
