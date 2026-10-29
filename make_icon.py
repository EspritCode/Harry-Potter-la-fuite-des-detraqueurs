# -*- coding: utf-8 -*-
"""
Génère harry_potter.ico (icône de l'exécutable) sans dépendance externe :
on dessine l'icône avec pygame puis on écrit un fichier ICO contenant un PNG.

Utilisation :  python make_icon.py
"""

import os

import pygame

HERE = os.path.dirname(os.path.abspath(__file__))
SIZE = 256


def draw_icon(size):
    """Un éclair doré sur fond nuit, avec un liseré clair."""
    surf = pygame.Surface((size, size), pygame.SRCALPHA)
    cx = size / 2.0

    # Disque de fond, dégradé simple du bleu nuit vers le noir
    for i in range(size // 2, 0, -1):
        k = i / (size / 2.0)
        col = (int(10 + 22 * k), int(16 + 32 * k), int(38 + 52 * k))
        pygame.draw.circle(surf, col, (int(cx), int(cx)), i)
    # Liseré
    pygame.draw.circle(surf, (232, 196, 106), (int(cx), int(cx)),
                       size // 2 - 2, max(3, size // 48))

    # Éclair (coordonnées relatives à une grille 100x100)
    pts = [(58, 10), (30, 56), (47, 56), (40, 92), (72, 42), (53, 42)]
    poly = [(int(x / 100.0 * size), int(y / 100.0 * size)) for x, y in pts]

    # Halo derrière l'éclair
    halo = pygame.Surface((size, size), pygame.SRCALPHA)
    pygame.draw.polygon(halo, (255, 220, 120, 70), poly)
    for _ in range(6):
        halo = pygame.transform.smoothscale(halo, (size, size))
    surf.blit(halo, (0, 0))

    pygame.draw.polygon(surf, (250, 226, 140), poly)
    pygame.draw.polygon(surf, (255, 252, 226), poly, max(2, size // 64))
    return surf


def write_ico(surface, path):
    """Écrit un ICO contenant une seule image PNG 256x256."""
    import struct
    import zlib

    w, h = surface.get_size()
    raw = pygame.image.tobytes(surface, "RGBA")

    # Encodeur PNG minimal (une seule passe, filtre 0 par ligne).
    rows = bytearray()
    stride = w * 4
    for y in range(h):
        rows.append(0)
        rows += raw[y * stride:(y + 1) * stride]

    def chunk(tag, data):
        out = struct.pack(">I", len(data)) + tag + data
        return out + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)

    png = b"\x89PNG\r\n\x1a\n"
    png += chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 6, 0, 0, 0))
    png += chunk(b"IDAT", zlib.compress(bytes(rows), 9))
    png += chunk(b"IEND", b"")

    # En-tête ICO + une entrée
    header = struct.pack("<HHH", 0, 1, 1)
    height = 0 if h >= 256 else h
    width = 0 if w >= 256 else w
    entry = struct.pack("<BBBBHHII", width, height, 0, 0, 1, 32,
                        len(png), 6 + 16)
    with open(path, "wb") as f:
        f.write(header + entry + png)


def main():
    pygame.init()
    pygame.display.set_mode((1, 1))
    icon = draw_icon(SIZE)
    out = os.path.join(HERE, "harry_potter.ico")
    write_ico(icon, out)
    print("Icône écrite :", out)
    pygame.quit()


if __name__ == "__main__":
    main()
