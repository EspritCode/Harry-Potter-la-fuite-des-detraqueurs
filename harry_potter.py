# -*- coding: utf-8 -*-
"""
HARRY POTTER - La Fuite des Détraqueurs
=======================================
Shoot'em up horizontal en Pygame, construit à partir des quatre visuels du
dossier `HarryPotter` :

    player.webp           -> fond de l'écran titre
    Harry-Potter-Logo.png -> logo du menu
    enemi1.png            -> Détraqueur (ennemi courant)
    enemi2.jpg            -> Détraqueur majeur (boss)

Harry vole vers la droite et repousse les Détraqueurs à coups de sorts.
Trois vagues puis un boss, et le niveau suivant recommence, plus dur.

Les images sont détourées automatiquement au chargement (le fond blanc
devient transparent), donc aucun travail de découpe n'est nécessaire.

Commandes
---------
  ← ↑ → ↓  ou  Z Q S D / W A S D : déplacer Harry
  ESPACE  (maintenu)             : lancer un sort
  P                              : pause
  R                              : rejouer
  ENTRÉE                         : commencer / continuer
  ÉCHAP                          : quitter
"""

import math
import os
import random
import sys

import pygame

# --------------------------------------------------------------------------- #
#  Réglages généraux
# --------------------------------------------------------------------------- #

W, H = 980, 640
FPS = 60


def _asset_dir():
    """
    Dossier où chercher les images.
      - lancé normalement : le dossier du script ;
      - empaqueté par PyInstaller : le dossier temporaire d'extraction
        (`sys._MEIPASS`), où PyInstaller range les fichiers ajoutés en « data ».
    """
    bundle = getattr(sys, "_MEIPASS", None)
    if bundle:
        return bundle
    return os.path.dirname(os.path.abspath(__file__))


def _save_dir():
    """
    Dossier où écrire le meilleur score et crash.log. Il doit rester
    accessible en écriture : à côté de l'exécutable, jamais dans le dossier
    temporaire de PyInstaller, qui est effacé à la fermeture.
    """
    if getattr(sys, "frozen", False):
        return os.path.dirname(os.path.abspath(sys.executable))
    return os.path.dirname(os.path.abspath(__file__))


HERE = _asset_dir()
SAVE_DIR = _save_dir()

PLAYER_X = 150.0
PLAYER_SPEED = 5.4
FIRE_DELAY = 9.0          # frames entre deux sorts
INVULN_TIME = 2.2 * FPS
START_LIVES = 3

WAVES_PER_LEVEL = 3

NIGHT = {
    "sky_top":   (10, 18, 44),
    "sky_bottom": (24, 42, 74),
    "moon":      (232, 240, 255),
    "star":      (200, 215, 245),
    "mount_far": (18, 28, 52),
    "mount_near": (11, 18, 36),
    "gold":      (232, 196, 106),
    "red":       (170, 40, 45),
    "spell":     (150, 225, 255),
    "spell_hot": (255, 255, 235),
    "dark":      (86, 66, 128),
    "dark_hot":  (188, 150, 255),
    "ui":        (168, 180, 205),
    "white":     (250, 250, 255),
}


# --------------------------------------------------------------------------- #
#  Chargement et détourage des images
# --------------------------------------------------------------------------- #

def load_image(name):
    """Charge une image du dossier ; renvoie None si elle est absente."""
    for candidate in (name, name.replace(".jpg", ".png"),
                      name.replace(".webp", ".png")):
        path = os.path.join(HERE, candidate)
        if os.path.exists(path):
            try:
                img = pygame.image.load(path)
            except pygame.error:
                continue
            # smoothscale exige une surface 24 ou 32 bits : on convertit ici
            # pour gérer aussi les PNG palettisés (8 bits), comme enemi1.png.
            try:
                return img.convert_alpha()
            except pygame.error:
                try:
                    return img.convert()
                except pygame.error:
                    return img
    return None


def to_smoothable(surf):
    """
    `smoothscale` n'accepte que des surfaces 24 ou 32 bits. Un PNG en palette
    (8 bits indexé) le fait échouer avec « Smoothscale format not supported »,
    ce qui empêchait le jeu de démarrer. On convertit donc systématiquement.
    """
    if surf.get_bitsize() in (24, 32):
        return surf
    try:
        return surf.convert_alpha()
    except pygame.error:
        try:
            return surf.convert()
        except pygame.error:
            return surf


def scale_to_height(surf, height):
    height = max(1, int(height))
    w = max(1, int(surf.get_width() * height / surf.get_height()))
    return pygame.transform.smoothscale(to_smoothable(surf), (w, height))


def scale_to_width(surf, width):
    width = max(1, int(width))
    h = max(1, int(surf.get_height() * width / surf.get_width()))
    return pygame.transform.smoothscale(to_smoothable(surf), (width, h))


def luminance_cutout(surf, white=False):
    """
    Détoure un sujet sombre posé sur fond blanc, sans NumPy.
    L'alpha est l'inverse de la luminosité : le blanc disparaît, le noir reste
    opaque, et les pixels intermédiaires donnent des bords doux.

    Avec `white=True`, le sujet devient une silhouette blanche : c'est un
    masque prêt à être teinté (utilisé pour le logo).
    """
    src = surf.convert_alpha()
    # On aplatit sur du blanc : sinon les pixels transparents ont des
    # composantes RVB arbitraires qui fausseraient la luminosité. Pour le PNG
    # déjà détouré, cela revient à conserver le sujet noir sur fond blanc,
    # c'est-à-dire exactement le cas traité ici.
    flat = pygame.Surface(src.get_size())
    flat.fill((255, 255, 255))
    flat.blit(src, (0, 0))
    src = flat
    w, h = src.get_size()
    # tobytes (pygame >= 2.1.3) avec repli sur tostring pour les versions
    # antérieures.
    to_bytes = getattr(pygame.image, "tobytes", None) or pygame.image.tostring
    from_bytes = getattr(pygame.image, "frombytes", None) \
        or pygame.image.fromstring
    data = bytearray(to_bytes(src, "RGBA"))
    for i in range(0, len(data), 4):
        r, g, b = data[i], data[i + 1], data[i + 2]
        lum = (r * 299 + g * 587 + b * 114) // 1000
        alpha = 255 - lum
        # Le voile blanc du JPEG autour du sujet est éliminé franchement.
        if alpha < 46:
            alpha = 0
        elif alpha < 90:
            alpha = (alpha - 46) * 255 // 44
        if white:
            # Silhouette blanche : sert de masque teignable (logo).
            data[i] = data[i + 1] = data[i + 2] = 255
        data[i + 3] = alpha
    out = from_bytes(bytes(data), (w, h), "RGBA")
    return out.convert_alpha()


def crop_opaque(surf, margin=0):
    """
    Recadre sur la zone non transparente. On passe par pygame.mask, qui
    travaille en C : une boucle Python sur ~1 million de pixels serait
    beaucoup trop lente au démarrage.
    """
    mask = pygame.mask.from_surface(surf, 24)
    rects = mask.get_bounding_rects()
    if not rects:
        return surf
    # `get_bounding_rects()` renvoie des pygame.Rect : on en fait une copie,
    # car modifier directement le rect renvoyé par Pygame n'est pas fiable
    # et provoquait un plantage au démarrage.
    union = pygame.Rect(rects[0])
    for other in rects[1:]:
        union.union_ip(other)
    w, h = surf.get_size()
    union.inflate_ip(margin * 2, margin * 2)
    union = union.clip(pygame.Rect(0, 0, w, h))
    if union.width <= 0 or union.height <= 0:
        return surf
    out = pygame.Surface(union.size, pygame.SRCALPHA)
    out.blit(surf, (0, 0), union)
    return out


def tinted(cut, color, alpha_scale=1.0):
    """
    Repeint une découpe dans une couleur donnée en conservant sa forme.
    On laisse l'alpha intact et on ne touche qu'au RVB : le blanc pur
    multiplié par la couleur donne exactement la couleur voulue.
    """
    out = cut.copy()
    out.fill((*color, 255), special_flags=pygame.BLEND_RGB_MULT)
    if alpha_scale != 1.0:
        out.set_alpha(int(255 * alpha_scale))
    return out


def prepare_logo(surf):
    """
    Le logo fourni est noir sur fond blanc : sur un ciel de nuit il serait
    invisible. On le détoure puis on le repeint en doré avec un halo, ce qui
    rappelle le logo officiel.
    """
    cut = luminance_cutout(surf, white=True)
    w, h = cut.get_size()
    out = pygame.Surface((w, h), pygame.SRCALPHA)

    # Halo diffus : plusieurs copies décalées, semi-transparentes.
    halo = tinted(cut, NIGHT["gold"], 0.34)
    for dx, dy in ((-3, 0), (3, 0), (0, -3), (0, 3),
                   (-2, -2), (2, 2), (-2, 2), (2, -2)):
        out.blit(halo, (dx, dy))

    # Corps du logo, doré plein.
    out.blit(tinted(cut, NIGHT["gold"]), (0, 0))

    # Reflet clair sur le haut des lettres.
    out.blit(tinted(cut, (255, 246, 214), 0.30), (0, -1))
    return out


def prepare(path_name, size, mode="height"):
    """Charge, redimensionne puis détoure une image. None si indisponible."""
    raw = load_image(path_name)
    if raw is None:
        return None
    # On réduit d'abord : le détourage coûte un parcours de tous les pixels,
    # autant le faire sur la taille finale.
    if mode == "height":
        raw = scale_to_height(raw, size)
    else:
        raw = scale_to_width(raw, size)
    return luminance_cutout(raw)


# --------------------------------------------------------------------------- #
#  Sprite de Harry (dessiné en code)
# --------------------------------------------------------------------------- #

def make_harry(w=84, h=58):
    """Harry sur son balai, tourné vers la droite, dessiné en vectoriel."""
    S = 4
    surf = pygame.Surface((w * S, h * S), pygame.SRCALPHA)
    P = pygame.draw
    brown = (126, 84, 44)
    straw = (206, 174, 112)
    cloak = (23, 26, 46)
    lining = NIGHT["red"]
    skin = (236, 196, 160)
    hair = (34, 26, 24)

    def p(x, y):
        return int(x * S), int(y * S)

    # --- balai : manche puis broussaille à l'arrière -------------------
    P.line(surf, brown, p(20, 34), p(66, 25), 7 * S)
    P.line(surf, (84, 54, 28), p(20, 34), p(66, 25), 3 * S)
    P.polygon(surf, straw, [p(21, 29), p(4, 22), p(2, 34), p(20, 39)])
    P.polygon(surf, (176, 142, 88), [p(20, 31), p(6, 25), p(6, 32),
                                     p(19, 36)])
    for k in range(5):
        P.line(surf, (162, 130, 80),
               p(5 + k, 24 + k * 0.4), p(2 + k * 0.6, 32 + k))

    # --- cape -----------------------------------------------------------
    P.polygon(surf, cloak, [p(38, 18), p(62, 16), p(70, 30), p(64, 40),
                            p(36, 38), p(30, 28)])
    P.polygon(surf, lining, [p(36, 30), p(62, 32), p(66, 40), p(38, 40)])
    P.polygon(surf, cloak, [p(34, 24), p(44, 20), p(40, 42), p(26, 44),
                            p(28, 32)])

    # --- écharpe qui flotte derrière -------------------------------------
    P.polygon(surf, (150, 38, 44), [p(30, 22), p(38, 20), p(34, 27),
                                    p(24, 26)])
    P.polygon(surf, NIGHT["gold"], [p(30, 25), p(37, 23), p(34, 29),
                                    p(25, 28)])
    P.polygon(surf, (150, 38, 44), [p(14, 26), p(24, 26), p(20, 34),
                                    p(8, 32)])

    # --- tête -------------------------------------------------------------
    P.circle(surf, skin, p(58, 15), 8 * S)
    P.polygon(surf, hair, [p(50, 8), p(64, 6), p(66, 13), p(60, 11),
                           p(52, 14)])
    P.circle(surf, (24, 20, 30), p(61, 13), 3 * S)      # lunettes
    P.circle(surf, (200, 220, 240), p(61, 13), 1 * S)
    P.line(surf, (24, 20, 30), p(57, 13), p(54, 12), 2 * S)

    # --- baguette et éclat de sort ---------------------------------------
    P.line(surf, (58, 40, 30), p(64, 20), p(76, 12), 3 * S)
    P.circle(surf, (255, 250, 220), p(77, 11), 4 * S)
    P.circle(surf, (255, 255, 255), p(77, 11), 2 * S)

    return pygame.transform.smoothscale(surf, (w, h))


# --------------------------------------------------------------------------- #
#  Interface
# --------------------------------------------------------------------------- #

def pick_font(size, bold=True):
    for name in ("bahnschrift", "segoeui", "georgia", "consolas",
                 "couriernew", "arial"):
        try:
            f = pygame.font.SysFont(name, size, bold=bold)
            if f is not None:
                return f
        except pygame.error:
            continue
    return pygame.font.Font(None, size)


class UI:
    def __init__(self):
        self.tiny = pick_font(17)
        self.small = pick_font(21)
        self.mid = pick_font(28)
        self.big = pick_font(52)
        self.huge = pick_font(78)
        self._cache = {}

    def _build(self, text, font, color, glow):
        base = font.render(text, True, color)
        if not glow:
            return base, (0, 0)
        m = 6
        out = pygame.Surface((base.get_width() + m * 2,
                              base.get_height() + m * 2), pygame.SRCALPHA)
        halo = base.copy()
        halo.set_alpha(52)
        for dx, dy in ((-3, 0), (3, 0), (0, -3), (0, 3),
                       (-2, -2), (2, 2), (-2, 2), (2, -2)):
            out.blit(halo, (m + dx, m + dy))
        out.blit(base, (m, m))
        return out, (-m, -m)

    def measure(self, text, font, color, glow=None):
        key = (text, id(font), color, glow)
        if key not in self._cache:
            self._cache[key] = self._build(text, font, color, glow)
        return self._cache[key]

    def text(self, surf, text, font, color, x, y, center=True, glow=None):
        img, pos = self.measure(text, font, color, glow)
        r = img.get_rect()
        if center:
            r.midtop = (int(x), int(y))
        else:
            r.topleft = (int(x), int(y))
        r.move_ip(*pos)
        surf.blit(img, r)
        return r


# --------------------------------------------------------------------------- #
#  Particules
# --------------------------------------------------------------------------- #

class Particles:
    def __init__(self):
        self.items = []

    def burst(self, x, y, color, count=16, speed=3.2, life=30, size=3,
              spread=math.tau, angle=0.0, grav=0.04):
        for _ in range(count):
            a = random.uniform(0.0, spread) + angle
            sp = random.uniform(0.22, 1.0) * speed
            self.items.append({
                "x": x, "y": y,
                "vx": math.cos(a) * sp, "vy": math.sin(a) * sp,
                "life": random.uniform(0.55, 1.0) * life,
                "max": life, "color": color, "size": size, "grav": grav,
            })

    def update(self, dt=1.0):
        alive = []
        for p in self.items:
            p["x"] += p["vx"] * dt
            p["y"] += p["vy"] * dt
            p["vx"] *= 0.95
            p["vy"] = p["vy"] * 0.95 + p["grav"] * dt
            p["life"] -= dt
            if p["life"] > 0:
                alive.append(p)
        self.items = alive

    def draw(self, surf):
        for p in self.items:
            k = p["life"] / p["max"]
            s = max(1, int(p["size"] * k) + 1)
            col = tuple(int(c * (0.4 + 0.6 * k)) for c in p["color"])
            pygame.draw.rect(surf, col,
                             (int(p["x"]), int(p["y"]), s, s))


# --------------------------------------------------------------------------- #
#  Décor de nuit (étoiles, lune, montagnes en parallaxe)
# --------------------------------------------------------------------------- #

class Sky:
    """Ciel dégradé, lune, étoiles et deux plans de montagnes qui défilent."""

    def __init__(self, w, h):
        self.w, self.h = w, h
        self.back = self.build_sky()
        self.far = self.build_ridge(h * 0.72, 90, NIGHT["mount_far"], 3)
        self.near = self.build_ridge(h * 0.84, 130, NIGHT["mount_near"], 1)
        self.stars = []
        for _ in range(110):
            self.stars.append({
                "x": random.uniform(0, w), "y": random.uniform(0, h * 0.7),
                "s": random.choice((1, 1, 1, 2)),
                "tw": random.uniform(0.0, math.tau),
                "sp": random.uniform(0.25, 0.9),
            })
        self.ox_far = 0.0
        self.ox_near = 0.0

    def build_sky(self):
        surf = pygame.Surface((self.w, self.h))
        top, bottom = NIGHT["sky_top"], NIGHT["sky_bottom"]
        for y in range(self.h):
            k = y / max(1, self.h - 1)
            surf.fill(tuple(int(top[i] + (bottom[i] - top[i]) * k)
                            for i in range(3)), (0, y, self.w, 1))
        # Lune avec halo
        mx, my, mr = int(self.w * 0.76), int(self.h * 0.20), 62
        for i, alpha in enumerate((16, 26, 40, 58)):
            r = mr + (4 - i) * 26
            halo = pygame.Surface((r * 2, r * 2), pygame.SRCALPHA)
            pygame.draw.circle(halo, (*NIGHT["moon"], alpha),
                               (r, r), r)
            surf.blit(halo, (mx - r, my - r))
        pygame.draw.circle(surf, NIGHT["moon"], (mx, my), mr)
        pygame.draw.circle(surf, (205, 216, 238), (mx - 16, my - 12), 11)
        pygame.draw.circle(surf, (205, 216, 238), (mx + 18, my + 14), 8)
        pygame.draw.circle(surf, (205, 216, 238), (mx + 6, my - 24), 5)
        return surf

    def build_ridge(self, base_y, height, color, humps):
        """Silhouette de montagne sur une largeur double (défilement continu)."""
        w = self.w * 2
        surf = pygame.Surface((w, self.h), pygame.SRCALPHA)
        points = [(0, self.h)]
        x = 0
        step = w // (humps * 3)
        y = base_y
        while x < w:
            y = base_y + random.uniform(-height * 0.55, height * 0.35)
            points.append((x, y))
            x += step
            points.append((x, base_y + random.uniform(-height * 0.1,
                                                      height * 0.5)))
            x += step
        points.append((w, base_y + height * 0.6))
        points.append((w, self.h))
        pygame.draw.polygon(surf, color, points)
        return surf

    def update(self, dt, speed=1.0):
        for st in self.stars:
            st["x"] -= st["sp"] * dt * 0.6
            st["tw"] += 0.05 * dt
            if st["x"] < 0:
                st["x"] += self.w
                st["y"] = random.uniform(0, self.h * 0.7)
        self.ox_far = (self.ox_far + 0.35 * speed * dt) % self.w
        self.ox_near = (self.ox_near + 0.95 * speed * dt) % self.w

    def draw(self, surf, shake=0.0):
        surf.blit(self.back, (0, 0))
        for st in self.stars:
            k = 0.55 + 0.45 * math.sin(st["tw"])
            c = tuple(min(255, int(v * k)) for v in NIGHT["star"])
            pygame.draw.rect(surf, c, (int(st["x"]), int(st["y"]),
                                       st["s"], st["s"]))
        surf.blit(self.far, (-int(self.ox_far), 0))
        surf.blit(self.near, (-int(self.ox_near), 0))


# --------------------------------------------------------------------------- #
#  Projectiles
# --------------------------------------------------------------------------- #

class Spell:
    """Sort lancé par Harry."""

    def __init__(self, x, y):
        self.x, self.y = float(x), float(y)
        self.vx = 13.0
        self.r = 6
        self.dead = False
        self.trail = []

    @property
    def rect(self):
        return pygame.Rect(int(self.x - self.r), int(self.y - self.r),
                           self.r * 2, self.r * 2)

    def update(self, dt=1.0):
        self.x += self.vx * dt
        if self.x > W + 30:
            self.dead = True

    def draw(self, surf):
        x, y = int(self.x), int(self.y)
        for i, alpha in enumerate((40, 70, 120)):
            r = self.r + (3 - i) * 4
            g = pygame.Surface((r * 2, r * 2), pygame.SRCALPHA)
            pygame.draw.circle(g, (*NIGHT["spell"], alpha), (r, r), r)
            surf.blit(g, (x - r, y - r))
        pygame.draw.circle(surf, NIGHT["spell"], (x, y), self.r)
        pygame.draw.circle(surf, NIGHT["spell_hot"], (x - 1, y - 1),
                           max(1, self.r - 3))
        # petite traînée
        pygame.draw.line(surf, (70, 120, 160), (x - 22, y), (x - 6, y), 2)


class DarkOrb:
    """Boule de ténèbres lancée par un Détraqueur."""

    def __init__(self, x, y, vx, vy, radius=8):
        self.x, self.y = float(x), float(y)
        self.vx, self.vy = vx, vy
        self.r = radius
        self.dead = False

    @property
    def rect(self):
        return pygame.Rect(int(self.x - self.r), int(self.y - self.r),
                           self.r * 2, self.r * 2)

    def update(self, dt=1.0):
        self.x += self.vx * dt
        self.y += self.vy * dt
        if self.x < -40 or self.x > W + 40 or self.y < -40 or self.y > H + 40:
            self.dead = True

    def draw(self, surf):
        x, y = int(self.x), int(self.y)
        for i, alpha in enumerate((34, 60, 96)):
            r = self.r + (3 - i) * 5
            g = pygame.Surface((r * 2, r * 2), pygame.SRCALPHA)
            pygame.draw.circle(g, (*NIGHT["dark_hot"], alpha), (r, r), r)
            surf.blit(g, (x - r, y - r))
        pygame.draw.circle(surf, (26, 18, 44), (x, y), self.r)
        pygame.draw.circle(surf, NIGHT["dark"], (x, y), self.r, 2)


# --------------------------------------------------------------------------- #
#  Ennemis
# --------------------------------------------------------------------------- #

class Dementor:
    """
    Détraqueur commun (image enemi1). Il avance en ondulant et tire parfois
    une boule de ténèbres vers la position de Harry.
    """

    def __init__(self, art, level, wave_kind="straight"):
        base = art.get("dementor")
        h = int(random.uniform(92, 118)) + level * 3
        if base is not None:
            self.image = scale_to_height(base, h)
        else:
            self.image = None
        self.w = self.image.get_width() if self.image else 58
        self.h = self.image.get_height() if self.image else 96
        self.x = float(W + random.uniform(20, 140))
        self.y = random.uniform(90, H - 120)
        self.base_y = self.y
        self.t = random.uniform(0.0, math.tau)
        self.speed = 1.5 + level * 0.22 + random.uniform(-0.2, 0.4)
        self.wave_kind = wave_kind
        self.amp = random.uniform(26, 62)
        self.freq = random.uniform(0.020, 0.040)
        self.hp = 2 + level // 2
        self.r = max(1, int(min(self.w, self.h) * 0.26))
        self.hit_flash = 0.0
        self.dead = False
        self.fire_timer = random.uniform(50, 150)
        self.sway = random.uniform(-0.4, 0.4)

    @property
    def rect(self):
        cx = int(self.x + self.w / 2)
        cy = int(self.y + self.h / 2)
        return pygame.Rect(cx - self.r, cy - self.r, self.r * 2, self.r * 2)

    def update(self, dt, player_pos, orbs):
        self.t += dt
        self.x -= self.speed * dt
        if self.wave_kind == "sine":
            self.y = self.base_y + math.sin(self.t * self.freq) * self.amp
        elif self.wave_kind == "dive":
            self.y = self.base_y + math.sin(self.t * 0.012) * self.amp * 1.4
            self.x -= 0.8 * dt
        else:
            self.y += self.sway * dt
            if self.y < 70 or self.y > H - self.h - 50:
                self.sway *= -1
        self.y = max(50, min(H - self.h - 40, self.y))

        self.hit_flash = max(0.0, self.hit_flash - dt)

        self.fire_timer -= dt
        if self.fire_timer <= 0 and self.x < W - 40 and self.x > 80:
            self.fire_timer = random.uniform(90, 210)
            px, py = player_pos
            dx = px - (self.x + self.w / 2)
            dy = py - (self.y + self.h / 2)
            dist = max(1.0, math.hypot(dx, dy))
            sp = 3.4
            orbs.append(DarkOrb(self.x + self.w / 2, self.y + self.h / 2,
                                dx / dist * sp, dy / dist * sp))

        if self.x + self.w < -60:
            self.dead = True

    def hurt(self, amount=1):
        self.hp -= amount
        self.hit_flash = 8.0
        return self.hp <= 0

    def draw(self, surf):
        x, y = int(self.x), int(self.y)
        if self.image is None:
            pygame.draw.rect(surf, (20, 16, 34), (x, y, self.w, self.h),
                             border_radius=12)
            return
        surf.blit(self.image, (x, y))
        if self.hit_flash > 0:
            flash = self.image.copy()
            flash.fill((210, 190, 255, 0), special_flags=pygame.BLEND_RGBA_ADD)
            surf.blit(flash, (x, y), special_flags=pygame.BLEND_RGBA_ADD)


class Boss:
    """
    Détraqueur majeur (image enemi2). Il entre par la droite, reste sur place,
    oscille verticalement et alterne trois attaques.
    """

    def __init__(self, art, level):
        base = art.get("boss")
        target_w = int(W * 0.34)
        if base is not None:
            self.image = scale_to_width(base, target_w)
        else:
            self.image = None
        if self.image:
            self.w, self.h = self.image.get_size()
        else:
            self.w, self.h = target_w, 240
        self.x = float(W + 40)
        self.y = H / 2 - self.h / 2
        self.home_x = W - self.w - 40.0
        self.max_hp = 26 + level * 12
        self.hp = self.max_hp
        self.t = 0.0
        self.level = level
        self.state = "enter"
        self.phase_timer = 0.0
        self.attack = 0
        self.hit_flash = 0.0
        self.dead = False
        self.attack_cd = 40.0
        self.bob = 0.0

    @property
    def rect(self):
        cx = int(self.x + self.w / 2)
        cy = int(self.y + self.h * 0.45)
        return pygame.Rect(cx - int(self.w * 0.32), cy - int(self.h * 0.36),
                           int(self.w * 0.64), int(self.h * 0.72))

    def update(self, dt, player_pos, orbs):
        self.t += dt
        if self.state == "enter":
            self.x -= 2.2 * dt
            if self.x <= self.home_x:
                self.x = self.home_x
                self.state = "fight"
            return
        if self.state == "dying":
            self.phase_timer -= dt
            if self.phase_timer <= 0:
                self.dead = True
            return

        self.bob += 0.014 * dt
        self.y = H / 2 - self.h / 2 + math.sin(self.bob) * 46
        self.y = max(40, min(H - self.h - 20, self.y))

        self.hit_flash = max(0.0, self.hit_flash - dt)

        self.attack_cd -= dt
        if self.attack_cd <= 0:
            self.attack_cd = max(46.0, 96.0 - self.level * 5.0)
            self.attack = random.choice((0, 1, 2))
            self.fire(player_pos, orbs)

        # Petit tir d'entretien
        self.phase_timer += dt
        if self.phase_timer > 96:
            self.phase_timer = 0.0
            self.aimed(player_pos, orbs, 3.0)

    def aimed(self, player_pos, orbs, speed=3.6):
        px, py = player_pos
        sx = self.x + self.w * 0.15
        sy = self.y + self.h * 0.45
        dx, dy = px - sx, py - sy
        dist = max(1.0, math.hypot(dx, dy))
        orbs.append(DarkOrb(sx, sy, dx / dist * speed, dy / dist * speed,
                            radius=9))

    def fire(self, player_pos, orbs):
        sx = self.x + self.w * 0.15
        sy = self.y + self.h * 0.45
        if self.attack == 0:
            # Éventail
            for i in range(-3, 4):
                a = math.radians(180 + i * 11)
                orbs.append(DarkOrb(sx, sy, math.cos(a) * 3.6,
                                    math.sin(a) * 3.6, radius=9))
        elif self.attack == 1:
            # Pluie verticale
            for i in range(6):
                px = self.x - i * 46
                orbs.append(DarkOrb(px, self.y + 30,
                                    -1.0, random.uniform(1.6, 3.4),
                                    radius=8))
        else:
            # Salve guidée
            for i in range(3):
                self.aimed(player_pos, orbs, 3.2 + i * 0.6)

    def hurt(self, amount=1):
        if self.state == "dying":
            return False
        self.hp -= amount
        self.hit_flash = 7.0
        if self.hp <= 0:
            self.state = "dying"
            self.phase_timer = 1.2 * FPS
            return True
        return False

    def draw(self, surf):
        x, y = int(self.x), int(self.y)
        if self.image is None:
            pygame.draw.rect(surf, (16, 12, 28), (x, y, self.w, self.h),
                             border_radius=20)
        else:
            surf.blit(self.image, (x, y))
            if self.hit_flash > 0:
                flash = self.image.copy()
                flash.fill((230, 210, 255, 0),
                           special_flags=pygame.BLEND_RGBA_ADD)
                surf.blit(flash, (x, y), special_flags=pygame.BLEND_RGBA_ADD)

        # Barre de vie au-dessus du boss
        if self.state != "enter":
            bw = int(self.w * 0.8)
            bx = x + (self.w - bw) // 2
            by = max(12, y - 26)
            pygame.draw.rect(surf, (30, 22, 48), (bx, by, bw, 12),
                             border_radius=6)
            ratio = max(0.0, self.hp / self.max_hp)
            if ratio > 0:
                col = (200, 60, 80) if ratio > 0.35 else (240, 120, 60)
                pygame.draw.rect(surf, col,
                                 (bx, by, int(bw * ratio), 12),
                                 border_radius=6)
            pygame.draw.rect(surf, (150, 130, 180), (bx, by, bw, 12), 1,
                             border_radius=6)


# --------------------------------------------------------------------------- #
#  Jeu
# --------------------------------------------------------------------------- #

class Game:
    MENU, PLAYING, PAUSED, WAVE_CLEAR, GAME_OVER = range(5)

    def __init__(self):
        pygame.display.set_caption("Harry Potter - La Fuite des Détraqueurs")
        self.screen = pygame.display.set_mode((W, H))
        self.clock = pygame.time.Clock()
        self.ui = UI()

        self.frame = pygame.Surface((W, H))
        self.world = pygame.Surface((W, H), pygame.SRCALPHA)

        self.art = self.build_art()
        self.sky = Sky(W, H)
        self.particles = Particles()
        self.hero = make_harry()
        self.best = self.load_best()

        self.t = 0.0
        self.shake = 0.0
        self.state = self.MENU
        self.next_state_at = 0.0
        self.reset()
        # reset() prépare une partie (et bascule en PLAYING) : on revient au
        # menu pour que le jeu ne démarre pas tout seul au lancement.
        self.state = self.MENU

    # ---------------------------------------------------------------- assets
    def build_art(self):
        """Prépare les trois sprites issus des images fournies."""
        art = {}
        art["dementor"] = prepare("enemi1.png", 118)
        art["boss"] = prepare("enemi2.jpg", int(W * 0.36), mode="width")
        art["title_bg"] = load_image("player.webp")
        logo = load_image("Harry-Potter-Logo.png")
        if logo is not None:
            # Le fichier d'origine est en 3840x2160 : on le ramène d'abord à une
            # largeur raisonnable, sinon le détourage parcourt 8 millions de
            # pixels pour rien.
            logo = scale_to_width(logo, int(W * 0.62))
            logo = prepare_logo(logo)
            # Le fichier est très large (ratio 16:9) : on le recadre sur la
            # hauteur utile des lettres pour qu'il ne mange pas l'écran.
            logo = crop_opaque(logo, margin=6)
            if logo.get_height() > 150:
                logo = scale_to_width(
                    logo, int(logo.get_width() * 150 / logo.get_height()))
            art["logo"] = logo
        else:
            art["logo"] = None
        if art["title_bg"] is not None:
            art["title_bg"] = scale_to_height(art["title_bg"], H)
        return art

    # ------------------------------------------------------------ persistence
    @staticmethod
    def _score_path():
        return os.path.join(SAVE_DIR, "harry_potter.highscore.txt")

    def load_best(self):
        try:
            with open(self._score_path(), "r", encoding="utf-8") as f:
                return int(f.read().strip() or 0)
        except (OSError, ValueError):
            return 0

    def save_best(self):
        try:
            with open(self._score_path(), "w", encoding="utf-8") as f:
                f.write(str(self.best))
        except OSError:
            pass

    # ------------------------------------------------------------------ setup
    def reset(self):
        self.x = PLAYER_X
        self.y = H / 2.0
        self.lives = START_LIVES
        self.score = 0
        self.level = 1
        self.wave = 1
        self.kills = 0
        self.bosses = 0
        self.spells = []
        self.orbs = []
        self.enemies = []
        self.boss = None
        self.cooldown = 0.0
        self.invuln = 0.0
        self.pops = []
        self.banner = ""
        self.banner_t = 0
        self.banner_total = 1
        self.wave_timer = 0.0
        self.spawn_left = 0
        self.spawn_gap = 0.0
        self.wave_kind = "straight"
        self.record = False
        self.best_at_start = self.best
        self.shake = 0.0
        self.particles.items = []
        self.start_wave()

    @property
    def player_rect(self):
        return pygame.Rect(int(self.x - 20), int(self.y - 16), 40, 32)

    @property
    def player_pos(self):
        return self.x + 26, self.y

    # ------------------------------------------------------------------ vagues
    def start_wave(self):
        is_boss = (self.wave > WAVES_PER_LEVEL)
        if is_boss:
            self.boss = Boss(self.art, self.level)
            self.banner = "LE DÉTRAQUEUR MAJEUR"
            self.banner_total = 2000
            self.spawn_left = 0
        else:
            kind = ("straight", "sine", "dive")[(self.wave - 1) % 3]
            self.wave_kind = kind
            self.spawn_left = 4 + self.wave + self.level
            self.spawn_gap = max(22.0, 64.0 - self.level * 4.0)
            self.wave_timer = 30.0
            self.banner = "VAGUE %d" % self.wave
            self.banner_total = 1400
        self.banner_t = self.banner_total
        play("wave")

    def next_wave(self):
        """
        Passe à la vague suivante. Le rythme d'un niveau est :
        vague 1, 2, 3 puis boss (vague 4), après quoi le niveau augmente et
        on repart à la vague 1.
        """
        if self.wave >= WAVES_PER_LEVEL + 1:
            self.wave = 1
            self.level += 1
            self.lives = min(5, self.lives + 1)
        else:
            self.wave += 1
        self.start_wave()
        self.state = self.PLAYING

    # ------------------------------------------------------------------ score
    def add_score(self, n):
        self.score += n
        if self.score > self.best:
            self.best = self.score

    def pop_text(self, x, y, text, color):
        self.pops.append({"x": x, "y": y, "text": text, "color": color,
                          "life": 52.0, "max": 52.0})

    def show_banner(self, text, ms=1400):
        self.banner = text
        self.banner_total = ms
        self.banner_t = ms

    def add_shake(self, amt):
        self.shake = min(9.0, self.shake + amt)

    # ------------------------------------------------------------------ dégâts
    def hurt_player(self):
        if self.invuln > 0:
            return
        self.lives -= 1
        self.invuln = INVULN_TIME
        self.add_shake(9)
        px, py = self.x, self.y
        self.particles.burst(px, py, NIGHT["gold"], count=34, speed=5.5,
                             size=4)
        self.particles.burst(px, py, NIGHT["white"], count=14, speed=3.0,
                             size=3)
        play("hurt")
        if self.lives <= 0:
            self.game_over()

    def kill_enemy(self, enemy):
        cx, cy = enemy.x + enemy.w / 2, enemy.y + enemy.h / 2
        self.particles.burst(cx, cy, NIGHT["dark_hot"], count=26, speed=4.4,
                             size=4)
        self.particles.burst(cx, cy, (40, 30, 60), count=16, speed=2.6,
                             size=5, grav=-0.02)
        self.add_score(120)
        self.kills += 1
        self.pop_text(cx, cy - 20, "+120", NIGHT["gold"])
        self.add_shake(3)
        play("banish")

    def game_over(self):
        if self.state == self.GAME_OVER:
            return
        self.state = self.GAME_OVER
        self.next_state_at = self.t + 1.2 * FPS
        self.record = self.score > self.best_at_start
        if self.score > self.best:
            self.best = self.score
        self.save_best()
        play("gameover")

    # ------------------------------------------------------------------ update
    def update_playing(self, dt):
        keys = pygame.key.get_pressed()

        # --- déplacement ---------------------------------------------------
        dx = dy = 0.0
        if keys[pygame.K_LEFT] or keys[pygame.K_a] or keys[pygame.K_q]:
            dx -= 1.0
        if keys[pygame.K_RIGHT] or keys[pygame.K_d]:
            dx += 1.0
        if keys[pygame.K_UP] or keys[pygame.K_w] or keys[pygame.K_z]:
            dy -= 1.0
        if keys[pygame.K_DOWN] or keys[pygame.K_s]:
            dy += 1.0
        if dx and dy:
            dx *= 0.7071
            dy *= 0.7071
        self.x += dx * PLAYER_SPEED * dt
        self.y += dy * PLAYER_SPEED * dt
        self.x = max(40.0, min(W * 0.62, self.x))
        self.y = max(52.0, min(H - 56.0, self.y))

        self.invuln = max(0.0, self.invuln - dt)

        # --- tir ------------------------------------------------------------
        self.cooldown = max(0.0, self.cooldown - dt)
        if (keys[pygame.K_SPACE] or keys[pygame.K_f]) and self.cooldown <= 0:
            self.cooldown = FIRE_DELAY
            sx, sy = self.player_pos
            self.spells.append(Spell(sx, sy - 2))
            self.particles.burst(sx, sy, NIGHT["spell"], count=4, speed=1.8,
                                 life=12, size=2, grav=0.0)
            play("spell", 0.4)

        # --- projectiles -----------------------------------------------------
        for s in self.spells:
            s.update(dt)
        for o in self.orbs:
            o.update(dt)

        # --- ennemis ----------------------------------------------------------
        for e in self.enemies:
            e.update(dt, self.player_pos, self.orbs)

        # --- boss -------------------------------------------------------------
        if self.boss is not None:
            self.boss.update(dt, self.player_pos, self.orbs)

        # --- apparitions -------------------------------------------------------
        if self.spawn_left > 0:
            self.wave_timer -= dt
            if self.wave_timer <= 0:
                self.wave_timer = self.spawn_gap
                self.spawn_left -= 1
                self.enemies.append(
                    Dementor(self.art, self.level, self.wave_kind))

        # --- collisions : sorts contre ennemis ---------------------------------
        for s in self.spells:
            if s.dead:
                continue
            for e in self.enemies:
                if e.dead:
                    continue
                if s.rect.colliderect(e.rect):
                    s.dead = True
                    self.particles.burst(e.x + e.w / 2, e.y + e.h / 2,
                                         NIGHT["spell"], count=10, speed=2.6,
                                         life=18, size=3)
                    if e.hurt(1):
                        e.dead = True
                        self.kill_enemy(e)
                    play("hit", 0.35)
                    break
            if s.dead:
                continue
            if self.boss is not None and self.boss.state == "fight" \
                    and s.rect.colliderect(self.boss.rect):
                s.dead = True
                self.particles.burst(s.x, s.y, NIGHT["spell"], count=8,
                                     speed=2.4, life=16, size=3)
                if self.boss.hurt(1):
                    self.add_score(1500 + self.level * 500)
                    self.bosses += 1
                    bx = self.boss.x + self.boss.w / 2
                    by = self.boss.y + self.boss.h / 2
                    self.particles.burst(bx, by, NIGHT["dark_hot"],
                                         count=70, speed=7.0, size=5)
                    self.add_shake(9)
                    play("bossdown")
                else:
                    play("hit", 0.3)

        # --- collisions : dégâts au joueur --------------------------------------
        pr = self.player_rect
        for o in self.orbs:
            if not o.dead and pr.colliderect(o.rect):
                o.dead = True
                self.hurt_player()
                break
        if self.invuln <= 0:
            for e in self.enemies:
                if not e.dead and pr.colliderect(e.rect):
                    e.dead = True
                    self.particles.burst(e.x + e.w / 2, e.y + e.h / 2,
                                         NIGHT["dark_hot"], count=20,
                                         speed=4.0, size=4)
                    self.hurt_player()
                    break
            if self.boss is not None and self.boss.state == "fight" \
                    and pr.colliderect(self.boss.rect):
                self.hurt_player()

        # --- nettoyage ----------------------------------------------------------
        self.spells = [s for s in self.spells if not s.dead]
        self.orbs = [o for o in self.orbs if not o.dead]
        self.enemies = [e for e in self.enemies if not e.dead]

        if self.boss is not None and self.boss.dead:
            self.boss = None

        for p in self.pops:
            p["life"] -= dt
            p["y"] -= 0.4 * dt
        self.pops = [p for p in self.pops if p["life"] > 0]
        if self.banner_t > 0:
            self.banner_t = max(0.0, self.banner_t - dt * 16.67)

        # --- fin de vague -------------------------------------------------------
        if self.state == self.PLAYING:
            wave_done = (self.spawn_left == 0 and not self.enemies
                         and self.boss is None)
            boss_done = (self.boss is None and self.wave > WAVES_PER_LEVEL
                         and self.spawn_left == 0)
            if wave_done or boss_done:
                self.state = self.WAVE_CLEAR
                self.next_state_at = self.t + 1.4 * FPS

    # ------------------------------------------------------------------ draw
    def draw_player(self, surf):
        if self.invuln > 0 and int(self.t / 4) % 2 == 0:
            return
        img = self.hero
        bob = math.sin(self.t * 0.09) * 3.0
        rect = img.get_rect(center=(int(self.x), int(self.y + bob)))
        # halo doré
        glow = pygame.Surface((rect.w + 44, rect.h + 44), pygame.SRCALPHA)
        pygame.draw.ellipse(glow, (*NIGHT["gold"], 26),
                            (0, 0, rect.w + 44, rect.h + 44))
        surf.blit(glow, (rect.x - 22, rect.y - 22))
        surf.blit(img, rect)

    def draw_hud(self, surf):
        ui = self.ui
        # Vies sous forme d'éclairs
        for i in range(self.lives):
            x = 24 + i * 26
            y = 22
            pygame.draw.polygon(surf, NIGHT["gold"],
                                [(x + 6, y), (x, y + 12), (x + 6, y + 12),
                                 (x + 2, y + 24), (x + 12, y + 9),
                                 (x + 6, y + 9)])
        ui.text(surf, "SCORE", ui.tiny, NIGHT["ui"], 24, 54, center=False)
        ui.text(surf, "%06d" % self.score, ui.small, NIGHT["white"], 24, 72,
                center=False, glow=True)

        ui.text(surf, "NIVEAU %d   VAGUE %d/%d"
                % (self.level, min(self.wave, WAVES_PER_LEVEL + 1),
                   WAVES_PER_LEVEL), ui.tiny, NIGHT["ui"], W // 2, 20)
        ui.text(surf, "MEILLEUR %06d" % self.best, ui.tiny, NIGHT["gold"],
                W - 24, 20, center=False)

    def draw(self):
        world = self.world
        world.fill((0, 0, 0, 0))

        if self.state == self.MENU:
            self.draw_menu(world)
        else:
            self.sky.draw(world)
            self.sky.update(0.0)

            for e in self.enemies:
                e.draw(world)
            if self.boss is not None:
                self.boss.draw(world)
            for o in self.orbs:
                o.draw(world)
            for s in self.spells:
                s.draw(world)
            if self.state != self.GAME_OVER:
                self.draw_player(world)
            self.particles.draw(world)

        if self.shake > 0.2:
            ox = random.uniform(-self.shake, self.shake)
            oy = random.uniform(-self.shake, self.shake)
        else:
            ox = oy = 0.0
        self.frame.fill((0, 0, 0))
        self.frame.blit(world, (int(ox), int(oy)))

        if self.state != self.MENU:
            self.draw_hud(self.frame)
            self.draw_overlay(self.frame)

        self.screen.blit(self.frame, (0, 0))
        pygame.display.flip()

    def draw_menu(self, surf):
        bg = self.art.get("title_bg")
        if bg is not None:
            bw = bg.get_width()
            if bw < W:
                bg = scale_to_width(bg, W)
                bw = bg.get_width()
            span = max(0, bw - W)
            ox = int((math.sin(self.t * 0.004) * 0.5 + 0.5) * span)
            surf.blit(bg, (-ox, 0))
        else:
            self.sky.draw(surf)

        veil = pygame.Surface((W, H), pygame.SRCALPHA)
        veil.fill((6, 10, 26, 150))
        surf.blit(veil, (0, 0))

        logo = self.art.get("logo")
        if logo is not None:
            r = logo.get_rect()
            ly = int(H * 0.11 + math.sin(self.t * 0.03) * 5)
            surf.blit(logo, (W // 2 - r.w // 2, ly))
            base_y = ly + r.h + 10
        else:
            self.ui.text(surf, "HARRY POTTER", self.ui.huge, NIGHT["gold"],
                         W // 2, 74, glow=True)
            base_y = 172

        self.ui.text(surf, "LA FUITE DES DÉTRAQUEURS", self.ui.mid,
                     NIGHT["gold"], W // 2, base_y, glow=True)
        if int(self.t / FPS * 2) % 2 == 0:
            self.ui.text(surf, "APPUYEZ SUR ENTRÉE POUR JOUER",
                         self.ui.mid, NIGHT["white"], W // 2, base_y + 56)
        for i, line in enumerate((
                "← ↑ → ↓  ou  Z Q S D   :  DIRIGER HARRY",
                "ESPACE  (maintenu)      :  LANCER UN SORT",
                "P : PAUSE     R : REJOUER     ÉCHAP : QUITTER")):
            self.ui.text(surf, line, self.ui.tiny, NIGHT["ui"], W // 2,
                         base_y + 116 + i * 25)
        if self.best:
            self.ui.text(surf, "MEILLEUR SCORE : %d" % self.best,
                         self.ui.small, NIGHT["gold"], W // 2, base_y + 212)

    def draw_overlay(self, surf):
        cx, cy = W // 2, H // 2

        if self.state == self.PAUSED:
            veil = pygame.Surface((W, H), pygame.SRCALPHA)
            veil.fill((4, 8, 22, 165))
            surf.blit(veil, (0, 0))
            self.ui.text(surf, "PAUSE", self.ui.big, NIGHT["gold"], cx,
                         cy - 60, glow=True)
            self.ui.text(surf, "P pour reprendre", self.ui.small,
                         NIGHT["ui"], cx, cy + 6)

        elif self.state == self.WAVE_CLEAR:
            if self.banner_t > 0:
                k = min(1.0, (self.banner_total - self.banner_t) / 280.0)
                col = tuple(int(c * (0.45 + 0.55 * k)) for c in NIGHT["gold"])
                self.ui.text(surf, self.banner, self.ui.big, col, cx,
                             cy - 70, glow=True)
            self.ui.text(surf, "Vague suivante...", self.ui.small,
                         NIGHT["ui"], cx, cy + 10)

        elif self.state == self.GAME_OVER:
            veil = pygame.Surface((W, H), pygame.SRCALPHA)
            veil.fill((4, 8, 22, 190))
            surf.blit(veil, (0, 0))
            if self.t < self.next_state_at:
                return
            self.ui.text(surf, "LA NUIT T'EMPORTE", self.ui.big,
                         (210, 90, 110), cx, cy - 200, glow=True)
            rows = (("SCORE", "%d" % self.score),
                    ("NIVEAU ATTEINT", "%d" % self.level),
                    ("DÉTRAQUEURS CHASSÉS", "%d" % self.kills),
                    ("BOSS VAINCUS", "%d" % self.bosses),
                    ("MEILLEUR", "%d" % self.best))
            y = cy - 110
            for label, value in rows:
                self.ui.text(surf, label, self.ui.small, NIGHT["ui"],
                             cx - 190, y, center=False)
                self.ui.text(surf, value, self.ui.small, NIGHT["white"],
                             cx + 90, y, center=False)
                y += 34
            if self.record and int(self.t / FPS * 3) % 2 == 0:
                self.ui.text(surf, "★ NOUVEAU RECORD ★", self.ui.mid,
                             NIGHT["gold"], cx, y + 12, glow=True)
            if int(self.t / FPS * 2) % 2 == 0:
                self.ui.text(surf, "R POUR REJOUER   -   ENTRÉE POUR LE MENU",
                             self.ui.small, NIGHT["white"], cx, y + 62)

        elif self.banner_t > 0 and self.state == self.PLAYING:
            k = min(1.0, (self.banner_total - self.banner_t) / 300.0)
            col = tuple(int(c * (0.45 + 0.55 * k)) for c in NIGHT["gold"])
            self.ui.text(surf, self.banner, self.ui.mid, col, cx, 96,
                         glow=True)

    # ------------------------------------------------------------------ loop
    def handle_key(self, key):
        if key == pygame.K_ESCAPE:
            return False
        if key in (pygame.K_RETURN, pygame.K_KP_ENTER):
            if self.state == self.MENU:
                self.reset()
                self.state = self.PLAYING
            elif self.state == self.GAME_OVER:
                self.state = self.MENU
                self.reset()
        elif key == pygame.K_p and self.state in (self.PLAYING, self.PAUSED):
            self.state = (self.PAUSED if self.state == self.PLAYING
                          else self.PLAYING)
        elif key == pygame.K_r and self.state in (self.PLAYING, self.PAUSED,
                                                  self.GAME_OVER):
            self.reset()
            self.state = self.PLAYING
        return True

    def run(self):
        running = True
        while running:
            dt = self.clock.tick(FPS) / (1000.0 / FPS)
            dt = max(0.2, min(dt, 3.0))
            self.t += dt

            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    running = False
                elif event.type == pygame.KEYDOWN:
                    if not self.handle_key(event.key):
                        running = False

            self.particles.update(dt)
            self.shake = max(0.0, self.shake - 0.5 * dt)
            if self.state != self.MENU:
                self.sky.update(dt)

            if self.state == self.PLAYING:
                self.update_playing(dt)
            elif self.state == self.WAVE_CLEAR and self.t >= self.next_state_at:
                self.next_wave()

            self.draw()

        self.save_best()
        pygame.quit()
        sys.exit(0)


# --------------------------------------------------------------------------- #
#  Sons générés (aucun fichier audio)
# --------------------------------------------------------------------------- #

SOUND_RATE = 22050
SFX = {}


def _emit(samples):
    init = pygame.mixer.get_init()
    if not init:
        return None
    _freq, size, channels = init
    if size in (-8, 8):
        if size == -8:
            # 8 bits signé : la valeur -128..127 est encodée telle quelle.
            buf = bytearray(max(-128, min(127, int(v * 127))) & 0xFF
                            for v in samples)
        else:
            # 8 bits non signé : décalage de 128.
            buf = bytearray(max(0, min(255, int(v * 127) + 128))
                            for v in samples)
        if channels == 2:
            st = bytearray()
            for b in buf:
                st += bytes((b, b))
            buf = st
        return bytes(buf)
    if abs(size) == 16:
        from array import array
        arr = array("h")
        for v in samples:
            arr.append(int(max(-1.0, min(1.0, v)) * 32000))
        if channels == 2:
            st = array("h")
            for v in arr:
                st.append(v)
                st.append(v)
            arr = st
        if sys.byteorder == "big":
            arr.byteswap()
        return arr.tobytes()
    return None


def _samples(fn, ms, noise=False, fade=True):
    n = max(1, int(SOUND_RATE * ms / 1000.0))
    rnd = random.random
    out = []
    for i in range(n):
        t = i / SOUND_RATE
        v = (rnd() * 2.0 - 1.0) if noise else fn(t)
        if fade:
            v *= max(0.0, 1.0 - i / n)
        out.append(v)
    return out


def _sine(phase):
    return math.sin(phase * math.tau)


def init_sounds():
    sounds = {}
    try:
        if pygame.mixer.get_init() is None:
            pygame.mixer.init()
        if pygame.mixer.get_init() is None:
            return sounds
        pygame.mixer.set_num_channels(16)
    except pygame.error:
        return sounds

    def add(key, fn, ms, noise=False):
        data = _emit(_samples(fn, ms, noise))
        if not data:
            return
        try:
            sounds[key] = pygame.mixer.Sound(buffer=data)
        except pygame.error:
            pass

    add("spell", lambda t: _sine(t * (520 + t * 1500)), 110)
    add("hit", lambda t: _sine(t * 300), 70)
    add("banish", lambda t: _sine(t * (260 - t * 200)), 260)
    add("hurt", None, 420, noise=True)
    add("wave", lambda t: _sine(t * (300 + t * 600)), 300)
    add("bossdown", None, 900, noise=True)
    add("gameover", None, 800, noise=True)
    return sounds


def play(name, volume=1.0):
    snd = SFX.get(name)
    if snd is None:
        return
    try:
        snd.set_volume(volume)
        snd.play()
    except pygame.error:
        pass


# --------------------------------------------------------------------------- #

def main():
    random.seed()
    try:
        pygame.mixer.pre_init(SOUND_RATE, -8, 1, 512)
    except pygame.error:
        pass
    pygame.init()
    pygame.display.set_mode((W, H))
    # Icône de la fenêtre (absente si le fichier .ico n'a pas été généré).
    icon_path = os.path.join(HERE, "harry_potter.ico")
    if os.path.exists(icon_path):
        try:
            pygame.display.set_icon(pygame.image.load(icon_path))
        except pygame.error:
            pass
    SFX.update(init_sounds())
    Game().run()


def run_with_report():
    """
    Lance le jeu et, si quelque chose échoue, affiche l'erreur au lieu de
    laisser la fenêtre se refermer sans explication. Un fichier crash.log est
    aussi écrit à côté du script, utile si le jeu est lancé par double-clic.
    """
    try:
        main()
    except SystemExit:
        raise
    except BaseException:
        import traceback
        report = traceback.format_exc()
        try:
            with open(os.path.join(SAVE_DIR, "crash.log"), "w",
                      encoding="utf-8") as f:
                f.write(report)
        except OSError:
            pass
        print(report)
        try:
            screen = pygame.display.get_surface()
            if screen is not None:
                font = pygame.font.SysFont("consolas", 16)
                screen.fill((12, 10, 22))
                lines = report.strip().splitlines()[-18:]
                y = 14
                for line in lines:
                    img = font.render(line[:118], True, (255, 190, 190))
                    screen.blit(img, (14, y))
                    y += 20
                hint = font.render(
                    "Détail complet dans crash.log — appuyez sur une touche",
                    True, (200, 210, 235))
                screen.blit(hint, (14, y + 10))
                pygame.display.flip()
                waiting = True
                while waiting:
                    for ev in pygame.event.get():
                        if ev.type in (pygame.QUIT, pygame.KEYDOWN,
                                       pygame.MOUSEBUTTONDOWN):
                            waiting = False
        except Exception:
            pass
        pygame.quit()
        sys.exit(1)


if __name__ == "__main__":
    run_with_report()
