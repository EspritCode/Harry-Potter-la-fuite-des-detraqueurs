# 🧟‍♂️ Harry Potter – La Fuite des Détraqueurs

Shoot'em up horizontal en Pygame. Harry vole vers la droite et repousse les Détraqueurs à coups de sorts. Trois vagues, puis un boss, et le niveau recommence plus dur.

![Langage](https://img.shields.io/badge/Python-3.13-blue)
![Pygame](https://img.shields.io/badge/Pygame-2.6-green)

## ⬇️ Télécharger (Windows)

L'exécutable est publié automatiquement sur la page
[Releases](https://github.com/EspritCode/Harry-Potter-la-fuite-des-detraqueurs/releases)
après chaque tag `v*` :

1. Télécharger `HarryPotter.exe`.
2. Double-cliquer pour jouer.

## 🚀 Installation (depuis les sources)

```bash
git clone https://github.com/EspritCode/Harry-Potter-la-fuite-des-detraqueurs.git
cd Harry-Potter-la-fuite-des-detraqueurs

# 1. Créer un environnement virtuel
python -m venv venv

# 2. L'activer
#    Windows : venv\Scripts\activate
#    Linux / macOS : source venv/bin/activate

# 3. Installer les dépendances
pip install -r requirements.txt

# 4. Lancer le jeu
python harry_potter.py
```

## 🎮 Commandes

- `← ↑ → ↓` ou `Z Q S D` / `W A S D` : déplacer Harry
- `ESPACE` (maintenu) : lancer un sort
- `P` : pause
- `R` : rejouer
- `ENTRÉE` : commencer / continuer
- `ÉCHAP` : quitter

## 🏗️ Construire l'exécutable

```bash
pip install pyinstaller
pyinstaller --noconfirm harry_potter.spec
```

ou double-cliquer sur `build_exe.bat`. Résultat : `dist/HarryPotter.exe`.

## 🖼️ Crédits

Univers Harry Potter. Assets du dossier `HarryPotter` : `player.webp`, `Harry-Potter-Logo.png`, `enemi1.png`, `enemi2.jpg`.
