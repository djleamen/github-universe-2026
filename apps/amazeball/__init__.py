"""
Author: Dilara J. Leamen (@djleamen)
Date: Oct 28, 2026
"""

import math
import os
import random
import sys
from array import array

APP_DIR = "/system/apps/amazeball"
os.chdir(APP_DIR)
sys.path.insert(0, APP_DIR)

import hints
import missing_details

badge.mode(HIRES | VSYNC)
screen.antialias = image.X4

WIDTH, HEIGHT = 320, 240
CX, CY = 160.0, 122.0
R = 86
EAR_R = 26
EAR_DX = R + 4
EAR_DY = 8

GRAVITY = 16384.0
ENERGY_DECAY = 0.88
SHAKE_ON = 0.9
SHAKE_OFF = 0.25
SETTLE_MS = 450
FAKE_SHAKE_MS = 900
FLIP_MS = 520
RISE_MS = 650
HOLD_MS = 400
JITTER = 6.0

ANSWERS = (
    "Ship it!",
    "LGTM",
    "Needs a\nrebase",
    "Ask after\ncoffee",
    "Works on\nmy machine",
    "Add a\ntest first",
    "It's a\nfeature",
    "Revert it",
    "Approved,\nwith nits",
    "Not on a\nFriday",
    "Rate\nlimited",
    "Squash and\nmerge",
    "Open an\nissue",
    "Write the\ndocs",
    "404",
    "CI says no",
    "Pair on it",
    "Trust the\nlinter",
    "Ask the\nduck",
    "Merge with\nconfidence",
    "Retry the\njob",
    "Force push.\nTell no one",
    "Context\ntoo long",
    "Draft PR\nfirst",
    "Only if it\ncompiles",
    "Next\nsprint",
    "Yes",
    "No",
    "Definitely",
    "Outlook\nflaky",
)

BACKGROUND = color.rgb(13, 17, 23)
GLOW = color.rgb(143, 106, 220, 22)
SHELL = color.rgb(143, 106, 220)
SHELL_LIGHT = color.rgb(170, 138, 238)
SHELL_DARK = color.rgb(104, 72, 184)
SHELL_SEAM = color.rgb(92, 62, 168)
EAR = color.rgb(158, 118, 232)
EAR_DARK = color.rgb(118, 84, 200)
VISOR = color.rgb(18, 26, 58)
VISOR_DEEP = color.rgb(11, 16, 40)
VISOR_SHINE = color.rgb(255, 255, 255, 28)
GOGGLE = color.rgb(52, 168, 246)
GOGGLE_LIGHT = color.rgb(120, 206, 255)
GOGGLE_DARK = color.rgb(30, 120, 200)
LENS = color.rgb(14, 22, 52)
LENS_SHINE = color.rgb(255, 255, 255, 60)
EYE = color.rgb(52, 168, 246)
WINDOW_RIM = color.rgb(118, 84, 200)
WINDOW = color.rgb(8, 10, 22)
INK = color.rgb(14, 18, 48)
TRIANGLE = color.rgb(44, 92, 236)
TRIANGLE_DEEP = color.rgb(26, 56, 190)
TRIANGLE_EDGE = color.rgb(90, 140, 255)
TEXT = color.rgb(240, 246, 252)
DIM = color.rgb(139, 148, 158)
FAINT = color.rgb(48, 54, 61)
ACCENT = color.rgb(143, 106, 220)

HINT_STYLE = hints.Style(TEXT, FAINT, BACKGROUND)
HINT_SHAPE = (BUTTON_SELECT,)
HINT_RADIUS = 5

TITLE = font.futile
SMALL = font.sins
BODY = missing_details.mona_sans()
ANSWER_SIZE = 12


class Shaker:
    IDLE, SHAKING, SETTLING, REVEAL = range(4)

    def __init__(self):
        self.mode = self.IDLE
        self.energy = 0.0
        self.since = badge.ticks
        self.answer = ""
        self.previous = None
        self.fake_until = 0
        self.last_mag = None
        self.turn = 0.0
        self.turn_to = 0.0

    def read(self):
        ax, ay, az = badge.imu()[:3]
        magnitude = math.sqrt(ax * ax + ay * ay + az * az) / GRAVITY
        if self.last_mag is None:
            self.last_mag = magnitude
        jerk = abs(magnitude - self.last_mag)
        self.last_mag = magnitude
        return jerk + max(0.0, abs(magnitude - 1.0) - 0.15)

    def update(self):
        now = badge.ticks
        dt = min(badge.ticks_delta, 100)
        frames = dt / 33.0
        self.energy = self.energy * (ENERGY_DECAY ** frames) + self.read()
        if badge.pressed(BUTTON_SELECT) and self.mode in (self.IDLE, self.REVEAL):
            self.fake_until = now + FAKE_SHAKE_MS
        if now < self.fake_until:
            self.energy = max(self.energy, SHAKE_ON + 0.3)

        if self.mode == self.IDLE:
            if self.energy > SHAKE_ON:
                self.enter(self.SHAKING, now)
        elif self.mode == self.SHAKING:
            self.turn_to = 0.0
            if self.energy < SHAKE_OFF:
                self.enter(self.SETTLING, now)
        elif self.mode == self.SETTLING:
            if self.energy > SHAKE_ON:
                self.enter(self.SHAKING, now)
            elif now - self.since >= SETTLE_MS:
                self.pick()
                self.turn_to = 1.0
                self.enter(self.REVEAL, now)
        elif self.mode == self.REVEAL:
            if self.energy > SHAKE_ON and now - self.since >= HOLD_MS + FLIP_MS:
                self.enter(self.SHAKING, now)

        step = dt / FLIP_MS
        if self.turn < self.turn_to:
            self.turn = min(self.turn_to, self.turn + step)
        elif self.turn > self.turn_to:
            self.turn = max(self.turn_to, self.turn - step)

    def enter(self, mode, now):
        self.mode = mode
        self.since = now

    def pick(self):
        options = [answer for answer in ANSWERS if answer != self.previous]
        self.answer = random.choice(options)
        self.previous = self.answer

    def shaking(self):
        return self.mode == self.SHAKING or badge.ticks < self.fake_until

    def intensity(self):
        return max(0.0, min(1.0, (self.energy - SHAKE_OFF) / (SHAKE_ON * 2)))

    def rise(self):
        if self.mode != self.REVEAL:
            return 0.0
        return max(0.0, min(1.0, (badge.ticks - self.since - FLIP_MS) / RISE_MS))


shaker = Shaker()


def text_width(text, typeface):
    screen.font = typeface
    return screen.measure_text(text)[0]


def write(text, x, y, typeface, pen):
    screen.font = typeface
    screen.pen = pen
    screen.text(text, x, y)


def centred(text, y, typeface, pen, cx=CX):
    write(text, cx - text_width(text, typeface) / 2, y, typeface, pen)


def polygon(points):
    flat = array("f")
    for px, py in points:
        flat.append(px)
        flat.append(py)
    return shape.custom(flat)


class Squash:
    def __init__(self, cx, cy, sx):
        self.cx, self.cy, self.sx = cx, cy, sx
        self.matrix = mat3().translate(cx, cy).scale(sx, 1.0).translate(-cx, -cy)

    def shape(self, shp, pen):
        shp.transform = self.matrix
        screen.pen = pen
        screen.shape(shp)

    def circle(self, x, y, r, pen):
        self.shape(shape.circle(x, y, r), pen)

    def rounded(self, x, y, w, h, radius, pen):
        self.shape(shape.rounded_rectangle(x, y, w, h, radius), pen)


def draw_ears(q, x, y):
    for side in (-1, 1):
        ex = x + side * EAR_DX
        q.circle(ex + side * 2, y + EAR_DY + 3, EAR_R, EAR_DARK)
        q.circle(ex, y + EAR_DY, EAR_R, EAR)
        q.circle(ex - side * 6, y + EAR_DY - 8, EAR_R * 0.45, SHELL_LIGHT)


def draw_shell(q, x, y):
    q.circle(x, y, R + 1, SHELL_DARK)
    q.circle(x - 1, y - 2, R - 1, SHELL)
    q.shape(shape.arc(x, y, R - 12, R - 5, 200, 262), SHELL_LIGHT)


def draw_front(q, x, y, now):
    draw_ears(q, x, y)
    draw_shell(q, x, y)

    q.circle(x, y + 13, R - 19, VISOR_DEEP)
    q.circle(x - 1, y + 11, R - 21, VISOR)
    q.shape(shape.arc(x, y + 11, R - 34, R - 26, 215, 250), VISOR_SHINE)

    lens_w, lens_h, rim = 58, 50, 8
    gap = 4
    ly = y - 14
    for side in (-1, 1):
        lx = x + side * (gap / 2 + lens_w / 2)
        left, top = lx - lens_w / 2, ly - lens_h / 2
        q.rounded(left + 1, top + 3, lens_w, lens_h, 18, GOGGLE_DARK)
        q.rounded(left, top, lens_w, lens_h, 18, GOGGLE)
        q.rounded(left + 2, top + 2, lens_w - 4, 10, 5, GOGGLE_LIGHT)
        inner_h = lens_h - rim * 2
        inner_top = ly - inner_h / 2
        q.rounded(left + rim, inner_top, lens_w - rim * 2, inner_h, 12, LENS)
        q.rounded(lx - side * 12 - 6, inner_top + 5, 12, 7, 3, LENS_SHINE)
    q.rounded(x - gap / 2 - 10, ly - 7, gap + 20, 14, 4, GOGGLE)
    q.rounded(x - gap / 2 - 10, ly - 7, gap + 20, 5, 2, GOGGLE_LIGHT)

    squint = shaker.intensity() if shaker.shaking() else 0.0
    blink = 1.0 if (now % 4200) > 4080 else 0.0
    shut = max(squint * 0.6, blink)
    eye_w, eye_h = 11, 26
    open_h = max(3, eye_h * (1 - shut))
    eye_cy = y + 30 + eye_h / 2
    for side in (-1, 1):
        ex = x + side * 20 - eye_w / 2
        top = eye_cy - open_h / 2
        q.rounded(ex + 1, top + 2, eye_w, open_h, min(5, open_h / 2), GOGGLE_DARK)
        q.rounded(ex, top, eye_w, open_h, min(5, open_h / 2), EYE)
        if open_h > 10:
            q.rounded(ex + 2, top + 2, 3, open_h * 0.5, 1, GOGGLE_LIGHT)


def draw_back(q, x, y, now):
    draw_ears(q, x, y)
    draw_shell(q, x, y)

    for side in (-1, 1):
        q.shape(shape.line(x + side * 28, y - R + 4, x + side * 36, y - 30, 2), SHELL_SEAM)
        q.shape(shape.line(x + side * 36, y - 30, x + side * 34, y + 54, 2), SHELL_SEAM)

    wy = y - 12
    q.circle(x, wy + 3, 44, SHELL_DARK)
    q.circle(x, wy, 42, WINDOW_RIM)
    q.circle(x, wy, 37, WINDOW)
    q.circle(x, wy + 2, 34, INK)

    rise = shaker.rise()
    if rise > 0:
        eased = 1 - (1 - rise) * (1 - rise)
        half = 30 * eased
        top = wy - 22 * eased + (1 - eased) * 12
        apex = wy + 30 * eased + (1 - eased) * 12
        q.shape(polygon(((x - half - 2, top - 2), (x + half + 2, top - 2), (x, apex + 3))), TRIANGLE_EDGE)
        q.shape(polygon(((x - half, top), (x + half, top), (x, apex))), TRIANGLE_DEEP)
        inset = 0.86
        q.shape(polygon(((x - half * inset, top + 4), (x + half * inset, top + 4), (x, top + 4 + (apex - top - 4) * inset))), TRIANGLE)
        if rise >= 1 and q.sx > 0.95:
            screen.font = BODY
            screen.pen = TEXT
            screen.text(shaker.answer, rect(x - 30, top + 4, 60, 32), ANSWER_SIZE,
                        align=(image.CENTER, image.MIDDLE))

    q.shape(shape.arc(x, wy, 30, 36, 205, 250), VISOR_SHINE)

    for row in range(3):
        gy = y + 42 + row * 11
        q.rounded(x - 20, gy + 1, 40, 6, 2, SHELL_LIGHT)
        q.rounded(x - 20, gy, 40, 6, 2, SHELL_SEAM)


def wobble():
    if not shaker.shaking():
        return 0.0, 0.0
    strength = JITTER * (0.4 + shaker.intensity())
    return (random.random() * 2 - 1) * strength, (random.random() * 2 - 1) * strength


def draw_caption(now):
    centred("copilot amazeball", 8, TITLE, TEXT)
    if shaker.mode == shaker.IDLE:
        pulse = 0.6 + 0.4 * math.sin(now / 400)
        centred("ask a question, then shake", 226, SMALL, color.rgb(139, 148, 158, int(255 * pulse)))
    elif shaker.mode in (shaker.SHAKING, shaker.SETTLING):
        centred("consulting the repo of destiny...", 226, SMALL, ACCENT)
    else:
        centred("shake again for a second opinion", 226, SMALL, DIM)
    hints.draw_hint(HINT_STYLE, HINT_SHAPE, HINT_SHAPE, WIDTH - 50, 230, HINT_RADIUS)
    write("shake", WIDTH - 40, 226, SMALL, DIM)


def lights(now):
    if shaker.shaking():
        badge.caselights(0.2 + 0.6 * shaker.intensity())
    elif shaker.mode == shaker.REVEAL:
        since = now - shaker.since - FLIP_MS
        flash = max(0.0, 1.0 - since / 600) if since >= 0 else 0.0
        badge.caselights(flash * 0.9)
    else:
        badge.caselights(0)


def update():
    now = badge.ticks
    shaker.update()
    lights(now)

    screen.pen = BACKGROUND
    screen.clear()

    jx, jy = wobble()
    bob = 0 if shaker.shaking() else math.sin(now / 900) * 2
    x, y = CX + jx, CY + jy + bob

    screen.pen = GLOW
    screen.circle(vec2(x, y), R + 24 + math.sin(now / 700) * 3)

    angle = shaker.turn * math.pi
    sx = max(0.04, abs(math.cos(angle)))
    q = Squash(x, y, sx)
    if shaker.turn < 0.5:
        draw_front(q, x, y, now)
    else:
        draw_back(q, x, y, now)
    draw_caption(now)


def on_exit():
    badge.caselights(0)


run(update)
