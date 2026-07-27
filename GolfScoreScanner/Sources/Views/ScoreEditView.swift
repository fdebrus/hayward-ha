import SwiftUI

/// Écran de vérification : l'utilisateur corrige les valeurs mal lues
/// par l'OCR (photo de la carte affichée en référence) avant le calcul.
struct ScoreEditView: View {
    @Binding var card: ScoreCard
    let image: UIImage?

    @State private var showResults = false

    var body: some View {
        Form {
            if let image {
                Section("Carte scannée") {
                    Image(uiImage: image)
                        .resizable()
                        .scaledToFit()
                        .frame(maxHeight: 220)
                        .clipShape(RoundedRectangle(cornerRadius: 8))
                }
            }

            Section("Parcours") {
                TextField("Nom du parcours", text: $card.courseName)
            }

            ForEach($card.players) { $player in
                Section {
                    TextField("Nom du joueur", text: $player.name)
                    HStack {
                        Text("Handicap")
                        Spacer()
                        TextField("—", value: $player.handicap, format: .number)
                            .keyboardType(.decimalPad)
                            .multilineTextAlignment(.trailing)
                            .frame(width: 80)
                    }
                    holesGrid(for: $player)
                } header: {
                    Text(player.name.isEmpty ? "Joueur" : player.name)
                }
            }

            Section {
                Button {
                    card.players.append(PlayerRound(name: "Joueur \(card.players.count + 1)"))
                } label: {
                    Label("Ajouter un joueur", systemImage: "person.badge.plus")
                }
                if card.players.count > 1 {
                    Button(role: .destructive) {
                        card.players.removeLast()
                    } label: {
                        Label("Retirer le dernier joueur", systemImage: "person.badge.minus")
                    }
                }
            }
        }
        .navigationTitle("Vérifier les scores")
        .toolbar {
            ToolbarItem(placement: .confirmationAction) {
                Button("Calculer") { showResults = true }
                    .disabled(card.players.allSatisfy { $0.strokes.isEmpty })
            }
        }
        .navigationDestination(isPresented: $showResults) {
            ResultView(card: card)
        }
    }

    /// Grille 18 trous : par (modifiable) et coups joués pour le joueur.
    private func holesGrid(for player: Binding<PlayerRound>) -> some View {
        LazyVGrid(columns: Array(repeating: GridItem(.flexible()), count: 3), spacing: 12) {
            ForEach($card.holes) { $hole in
                VStack(spacing: 4) {
                    Text("Trou \(hole.number)")
                        .font(.caption2)
                        .foregroundStyle(.secondary)
                    HStack(spacing: 4) {
                        Stepper(value: $hole.par, in: 3...6) {
                            Text("Par \(hole.par)")
                                .font(.caption)
                        }
                        .labelsHidden()
                        .scaleEffect(0.7)
                    }
                    TextField("—", value: strokesBinding(for: player, hole: hole.number), format: .number)
                        .keyboardType(.numberPad)
                        .multilineTextAlignment(.center)
                        .textFieldStyle(.roundedBorder)
                        .frame(width: 52)
                }
            }
        }
        .padding(.vertical, 4)
    }

    private func strokesBinding(for player: Binding<PlayerRound>, hole: Int) -> Binding<Int?> {
        Binding<Int?>(
            get: { player.wrappedValue.strokes[hole] },
            set: { newValue in
                if let newValue, newValue > 0 {
                    player.wrappedValue.strokes[hole] = newValue
                } else {
                    player.wrappedValue.strokes.removeValue(forKey: hole)
                }
            }
        )
    }
}

#Preview {
    NavigationStack {
        ScoreEditView(card: .constant(ScoreCard.standard18()), image: nil)
    }
}
