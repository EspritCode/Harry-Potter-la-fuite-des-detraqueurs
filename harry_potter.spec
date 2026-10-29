# -*- mode: python ; coding: utf-8 -*-
"""
Spécification PyInstaller pour Harry Potter - La Fuite des Détraqueurs.

Utilisation, depuis le dossier HarryPotter :
    pyinstaller --noconfirm harry_potter.spec

Le résultat est dist/HarryPotter.exe : un seul fichier, sans fenêtre de
console, avec les quatre images embarquées à l'intérieur.

Si une image est absente au moment de la compilation, elle est simplement
ignorée (voir la liste ci-dessous) : le jeu démarre quand même, avec des
silhouettes de remplacement.
"""

import os

# Depuis PyInstaller 6, `SPECPATH` désigne le dossier du fichier .spec.
BASE = SPECPATH if "SPECPATH" in globals() else os.getcwd()

IMAGES = [
    "player.webp",
    "enemi1.png",
    "enemi2.jpg",
    "Harry-Potter-Logo.png",
]

datas = [(name, ".") for name in IMAGES
         if os.path.exists(os.path.join(BASE, name))]

a = Analysis(
    ["harry_potter.py"],
    pathex=[BASE],
    binaries=[],
    datas=datas,
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=["numpy", "tkinter", "unittest", "email", "http", "xml"],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name="HarryPotter",
    icon=(os.path.join(BASE, "harry_potter.ico")
          if os.path.exists(os.path.join(BASE, "harry_potter.ico"))
          else None),
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    # console=False : aucune fenêtre noire derrière le jeu. En contrepartie,
    # les erreurs ne s'affichent plus dans un terminal ; c'est pourquoi le
    # script écrit crash.log et affiche l'erreur à l'écran.
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
