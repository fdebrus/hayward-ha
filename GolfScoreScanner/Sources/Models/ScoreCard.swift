import Foundation

/// Un trou du parcours : numéro, par et éventuellement l'index (difficulté 1-18)
/// utilisé pour répartir les coups rendus lors du calcul du score net.
struct Hole: Identifiable, Codable, Equatable {
    let number: Int
    var par: Int
    var strokeIndex: Int?

    var id: Int { number }
}

/// Les coups joués par un joueur sur chaque trou.
/// `strokes[n]` correspond au trou numéro n (1-18) ; nil = non renseigné / non lu par l'OCR.
struct PlayerRound: Identifiable, Codable, Equatable {
    let id: UUID
    var name: String
    var handicap: Double?
    var strokes: [Int: Int]

    init(id: UUID = UUID(), name: String, handicap: Double? = nil, strokes: [Int: Int] = [:]) {
        self.id = id
        self.name = name
        self.handicap = handicap
        self.strokes = strokes
    }
}

/// Une carte de score complète : le parcours (trous + pars) et les joueurs.
struct ScoreCard: Codable, Equatable {
    var courseName: String
    var holes: [Hole]
    var players: [PlayerRound]

    /// Parcours 18 trous standard (par 72) utilisé comme base avant correction.
    static func standard18(courseName: String = "Parcours") -> ScoreCard {
        let pars = [4, 4, 3, 5, 4, 4, 3, 5, 4, 4, 3, 5, 4, 4, 3, 5, 4, 4]
        let holes = pars.enumerated().map { Hole(number: $0.offset + 1, par: $0.element, strokeIndex: nil) }
        return ScoreCard(courseName: courseName, holes: holes, players: [])
    }
}
