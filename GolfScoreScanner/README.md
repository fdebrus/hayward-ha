# Golf Score Scanner 🏌️ 📱

Application iPhone (SwiftUI) qui **scanne une carte de score de golf** avec l'appareil photo, lit les scores par OCR et **calcule automatiquement le résultat** : total brut, aller/retour, écart au par, score net et points Stableford.

## Fonctionnement

1. **Scan** — le scanner de documents natif d'iOS (`VNDocumentCameraViewController`) cadre la carte, corrige la perspective et l'éclairage.
2. **OCR** — le framework Vision (`VNRecognizeTextRequest`, mode *accurate*, sans correction de langue pour mieux lire les chiffres manuscrits) extrait tous les textes avec leur position.
3. **Reconstruction de la grille** — `ScorecardParser` regroupe les textes en lignes, repère la ligne d'en-tête des trous (1, 2, 3…) pour situer les colonnes, la ligne « Par », puis les lignes de joueurs. Les colonnes de totaux (OUT/IN/TOT) sont ignorées.
4. **Vérification** — l'OCR sur du manuscrit n'est jamais parfait : un écran d'édition affiche la photo et la grille pour corriger en quelques tapotements.
5. **Calcul** — `ScoreCalculator` produit aller, retour, total, écart au par, et si un handicap est saisi : score net (répartition des coups rendus selon l'index des trous) et points Stableford.

## Structure

```
GolfScoreScanner/
├── project.yml                  # Config XcodeGen
├── Sources/
│   ├── GolfScoreScannerApp.swift
│   ├── Models/
│   │   ├── ScoreCard.swift      # Trous, pars, joueurs
│   │   └── ScoreCalculator.swift# Totaux, net, Stableford
│   ├── Scanner/
│   │   ├── DocumentScannerView.swift  # Caméra (VisionKit)
│   │   ├── TextRecognizer.swift       # OCR (Vision)
│   │   └── ScorecardParser.swift      # Texte OCR → grille de scores
│   └── Views/
│       ├── ContentView.swift    # Accueil + lancement du scan
│       ├── ScoreEditView.swift  # Correction des scores lus
│       └── ResultView.swift     # Résultats calculés
└── Tests/                       # Tests unitaires (calculs + parseur)
```

## Compiler et lancer

Prérequis : un Mac avec Xcode 15+, un iPhone sous iOS 17+ (le scanner de documents nécessite un appareil réel ; le simulateur n'a pas de caméra).

```bash
brew install xcodegen
cd GolfScoreScanner
xcodegen generate
open GolfScoreScanner.xcodeproj
```

Dans Xcode : sélectionnez votre équipe de signature (Signing & Capabilities), branchez votre iPhone, puis ⌘R. Les tests unitaires se lancent avec ⌘U.

> Alternative sans XcodeGen : créez un projet iOS « App » (SwiftUI) dans Xcode, glissez le contenu de `Sources/` dedans, et ajoutez la clé `NSCameraUsageDescription` dans l'Info.plist.

## Pistes d'évolution

- Historique des parties (SwiftData) et statistiques par parcours.
- Détection des index de trous (ligne « Hcp ») pour un net plus précis.
- Amélioration OCR manuscrit : recadrage par cellule de la grille + un modèle Core ML dédié aux chiffres manuscrits (type MNIST) en secours de Vision.
- Partage du résultat (image récapitulative) et export CSV.
