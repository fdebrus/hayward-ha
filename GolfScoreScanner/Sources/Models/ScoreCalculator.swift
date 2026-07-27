import Foundation

/// Résultat calculé pour un joueur.
struct ScoreResult: Equatable {
    var frontNine: Int
    var backNine: Int
    var total: Int
    var totalPar: Int
    var vsPar: Int
    var netTotal: Int?
    var stablefordPoints: Int?
    var holesPlayed: Int
}

enum ScoreCalculator {

    /// Calcule le score complet d'un joueur sur une carte donnée.
    static func result(for player: PlayerRound, on card: ScoreCard) -> ScoreResult {
        var front = 0, back = 0, playedPar = 0, played = 0

        for hole in card.holes {
            guard let strokes = player.strokes[hole.number] else { continue }
            played += 1
            playedPar += hole.par
            if hole.number <= 9 { front += strokes } else { back += strokes }
        }

        let total = front + back
        let net = netTotal(for: player, on: card)
        let stableford = player.handicap != nil ? stablefordPoints(for: player, on: card) : nil

        return ScoreResult(
            frontNine: front,
            backNine: back,
            total: total,
            totalPar: playedPar,
            vsPar: total - playedPar,
            netTotal: net,
            stablefordPoints: stableford,
            holesPlayed: played
        )
    }

    /// Coups rendus sur un trou : répartition du handicap de jeu selon l'index
    /// du trou (ou uniformément si les index ne sont pas connus).
    static func receivedStrokes(handicap: Double, hole: Hole, holeCount: Int) -> Int {
        let playingHandicap = Int(handicap.rounded())
        guard playingHandicap != 0, holeCount > 0 else { return 0 }
        let index = hole.strokeIndex ?? hole.number
        let base = playingHandicap / holeCount
        let extra = playingHandicap % holeCount
        // Un coup supplémentaire sur les `extra` trous les plus difficiles
        // (handicap négatif : on retire des coups, même logique inversée).
        if playingHandicap > 0 {
            return base + (index <= extra ? 1 : 0)
        } else {
            return base - (index <= -extra ? 1 : 0)
        }
    }

    /// Score net : brut moins les coups rendus (nécessite un handicap).
    static func netTotal(for player: PlayerRound, on card: ScoreCard) -> Int? {
        guard let handicap = player.handicap else { return nil }
        var net = 0
        for hole in card.holes {
            guard let strokes = player.strokes[hole.number] else { continue }
            net += strokes - receivedStrokes(handicap: handicap, hole: hole, holeCount: card.holes.count)
        }
        return net
    }

    /// Points Stableford : 2 points pour un par net, +1 par coup gagné,
    /// 0 en dessous de bogey net.
    static func stablefordPoints(for player: PlayerRound, on card: ScoreCard) -> Int {
        let handicap = player.handicap ?? 0
        var points = 0
        for hole in card.holes {
            guard let strokes = player.strokes[hole.number] else { continue }
            let received = receivedStrokes(handicap: handicap, hole: hole, holeCount: card.holes.count)
            let netScore = strokes - received
            points += max(0, 2 + hole.par - netScore)
        }
        return points
    }
}
