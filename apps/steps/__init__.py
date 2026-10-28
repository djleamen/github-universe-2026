"""
Author: Dilara J. Leamen (@djleamen)
Date: Oct 28, 2026
"""

import math
import os
import sys
import time

APP_DIR = "/system/apps/steps"
os.chdir(APP_DIR)
sys.path.insert(0, APP_DIR)

import hints
from badgeware import State

badge.mode(HIRES | VSYNC)
screen.antialias = image.X2

STATE_KEY = "steps"
WIDTH, HEIGHT = 320, 240
CX = WIDTH / 2

IMU_ADDRESS = 0x6A
CTRL10_C = 0x19
STEP_COUNTER_L = 0x4B
FUNC_EN = 0x04
PEDO_EN = 0x10
HARDWARE_POLL_MS = 250 # how often the chip's count is read while open

GRAVITY = 16384.0
BASELINE_MS = 900
SMOOTH_MS = 60
STEP_UP = 0.18
STEP_DOWN = 0.06
MIN_STEP_MS = 260
MAX_STEP_MS = 2000
STRIDE_M = 0.74
GOAL_STEP = 500
GOAL_MIN, GOAL_MAX = 500, 50000
SAVE_EVERY = 25
RESET_HOLD_MS = 1200
GLOW_MS = 320

TRACE_LEN = 64
TRACE_SCALE = 70.0
TRACE_TOP, TRACE_H = 186, 36

BACKGROUND = color.rgb(13, 17, 23)
PANEL = color.rgb(22, 27, 34)
TEXT = color.rgb(230, 237, 243)
DIM = color.rgb(139, 148, 158)
FAINT = color.rgb(48, 54, 61)
GREEN = color.rgb(63, 185, 80)
GREEN_DIM = color.rgb(14, 68, 41)
GREEN_BRIGHT = color.rgb(95, 237, 131)
WARNING = color.rgb(255, 125, 120)

HUGE = font.ignore
TITLE = font.futile
BODY = font.bacteria
SMALL = font.sins

HINT_STYLE = hints.Style(TEXT, FAINT, BACKGROUND)
GOAL_LIT = (BUTTON_UP, BUTTON_DOWN)
RESET_LIT = (BUTTON_SELECT,)
HINT_SHAPE = GOAL_LIT + RESET_LIT
HINT_RADIUS = 5

RING_CX, RING_CY, RING_R, RING_W = 258, 96, 50, 9

state = {"today": 0, "total": 0, "best": 0, "goal": 8000, "day": "", "hw_last": -1}
State.load(STATE_KEY, state)


def today_key():
    try:
        year, month, day = time.localtime()[:3]
    except (OSError, OverflowError, ValueError):
        return ""
    if year < 2025:
        return ""
    return "%04d-%02d-%02d" % (year, month, day)


def roll_day():
    key = today_key()
    if key and state["day"] and key != state["day"]:
        state["best"] = max(state["best"], state["today"])
        state["today"] = 0
    if key:
        state["day"] = key


roll_day()


class HardwareCounter:
    """The step counter inside the IMU, reached through the firmware's own
    driver where possible so there is never a second owner of the I2C bus."""

    def __init__(self):
        self.reader = None
        self.bus = None
        self.how = ""
        try:
            self.attach()
        except Exception as reason:  # noqa: BLE001
            print("steps: hardware counter unavailable:", reason)
            self.reader = None

    def attach(self):
        imu = getattr(badge, "_imu", None)
        if imu is not None and callable(getattr(imu, "get_step_count", None)):
            self.bus = getattr(imu, "bus", None) or getattr(imu, "i2c", None)
            self.reader = lambda: imu.get_step_count() & 0xFFFF
            self.how = "imu driver"
        else:
            bus = None
            if imu is not None:
                bus = getattr(imu, "bus", None) or getattr(imu, "i2c", None)
            if bus is None:
                import machine
                pins = machine.Pin.board
                bus = machine.I2C(1, sda=getattr(pins, "I2C_INTERNAL_SDA"), scl=getattr(pins, "I2C_INTERNAL_SCL"))
                self.how = "internal i2c"
            else:
                self.how = "imu bus"
            self.bus = bus
            self.reader = lambda: int.from_bytes(bus.readfrom_mem(IMU_ADDRESS, STEP_COUNTER_L, 2), "little")
        self.enable()
        # a first read proves the path works before anything relies on it
        self.reader()

    def enable(self):
        """Make sure the chip's pedometer is switched on, touching nothing else."""
        if self.bus is None:
            return
        try:
            current = self.bus.readfrom_mem(IMU_ADDRESS, CTRL10_C, 1)[0]
            wanted = current | FUNC_EN | PEDO_EN
            if wanted != current:
                self.bus.writeto_mem(IMU_ADDRESS, CTRL10_C, bytes([wanted]))
        except (OSError, AttributeError, TypeError) as reason:
            print("steps: could not check pedometer enable:", reason)

    @property
    def available(self):
        return self.reader is not None

    def read(self):
        try:
            return self.reader()
        except Exception as reason:  # noqa: BLE001
            print("steps: hardware counter read failed:", reason)
            self.reader = None
            return None


class Pedometer:
    def __init__(self):
        self.hardware = HardwareCounter()
        self.next_hardware_read = 0
        self.baseline = None
        self.level = None
        self.armed = False
        self.last_step = -MAX_STEP_MS
        self.unsaved = 0
        self.trace = [0.0] * TRACE_LEN
        self.trace_at = 0
        self.step_gaps = []

    def sample(self, dt):
        ax, ay, az = badge.imu()[:3]
        magnitude = math.sqrt(ax * ax + ay * ay + az * az) / GRAVITY
        if self.baseline is None:
            self.baseline = magnitude
            self.level = magnitude
        smooth = 1 - math.exp(-dt / SMOOTH_MS)
        self.level += (magnitude - self.level) * smooth
        follow = 1 - math.exp(-dt / BASELINE_MS)
        self.baseline += (self.level - self.baseline) * follow
        signal = self.level - self.baseline
        self.trace[self.trace_at] = signal
        self.trace_at = (self.trace_at + 1) % TRACE_LEN
        return signal

    def update(self):
        dt = min(badge.ticks_delta, 100)
        signal = self.sample(dt)
        now = badge.ticks
        stepped = False
        if not self.armed and signal > STEP_UP and now - self.last_step >= MIN_STEP_MS:
            self.armed = True
            gap = now - self.last_step
            self.last_step = now
            stepped = True
            if gap <= MAX_STEP_MS:
                self.step_gaps.append(gap)
                self.step_gaps = self.step_gaps[-6:]
        elif self.armed and signal < STEP_DOWN:
            self.armed = False
        if self.hardware.available:
            # the chip is the source of truth; detector above only drives the trace, the cadence figure and the glow
            if now >= self.next_hardware_read:
                self.next_hardware_read = now + HARDWARE_POLL_MS
                self.count(self.bank())
        elif stepped:
            self.count(1)
        if not self.walking():
            self.step_gaps = []
        return stepped

    def bank(self):
        """Steps the chip has counted since the last look, allowing for the
        count starting over after a power cycle or wrapping at 16 bits."""
        raw = self.hardware.read()
        if raw is None:
            return 0
        last = state["hw_last"]
        if last < 0:
            delta = raw
        elif raw >= last:
            delta = raw - last
        else:
            delta = raw
        state["hw_last"] = raw
        return delta

    def count(self, steps):
        if steps <= 0:
            return
        state["today"] += steps
        state["total"] += steps
        self.unsaved += steps

    def walking(self):
        return badge.ticks - self.last_step < MAX_STEP_MS

    def steps_per_minute(self):
        if len(self.step_gaps) < 2 or not self.walking():
            return 0
        return round(60000 / (sum(self.step_gaps) / len(self.step_gaps)))

    def save(self):
        self.unsaved = 0
        state["best"] = max(state["best"], state["today"])
        State.save(STATE_KEY, state)

    def reset_today(self):
        state["today"] = 0
        self.save()


pedometer = Pedometer()
reset_started = None
glow_until = 0


def text_width(text, typeface, scale=1):
    screen.font = typeface
    return screen.measure_text(text)[0] * scale


def write(text, x, y, typeface, pen, scale=1):
    screen.font = typeface
    screen.pen = pen
    if scale == 1:
        screen.text(text, x, y)
        return
    at = vec2(x, y)
    screen.text(text, at, transform=mat3().translate(at).scale(scale, scale).translate(vec2(-x, -y)))


def centred(text, y, typeface, pen, cx=CX, scale=1):
    write(text, cx - text_width(text, typeface, scale) / 2, y, typeface, pen, scale)


def thousands(value):
    text = str(int(value))
    out = ""
    while len(text) > 3:
        out = "," + text[-3:] + out
        text = text[:-3]
    return text + out


def distance_label(steps):
    metres = steps * STRIDE_M
    if metres < 1000:
        return "%d m" % metres
    return "%.2f km" % (metres / 1000)


def draw_ring():
    done = min(1.0, state["today"] / state["goal"]) if state["goal"] else 0
    screen.pen = FAINT
    screen.shape(shape.arc(RING_CX, RING_CY, RING_R - RING_W, RING_R, 0, 360))
    if done > 0:
        screen.pen = GREEN_BRIGHT if done >= 1 else GREEN
        screen.shape(shape.arc(RING_CX, RING_CY, RING_R - RING_W, RING_R, -90, -90 + 360 * done))
    block_h = 13 + 2 + 8
    ink_top = RING_CY - block_h / 2
    centred("%d%%" % round(done * 100), ink_top - 7, TITLE, TEXT, RING_CX)
    centred("of " + thousands(state["goal"]), ink_top + 13 + 2 - 2, SMALL, DIM, RING_CX)


HUGE_TOP_BEARING = 7
HUGE_INK = 17
STATS_TOP = 122
STAT_PITCH = 30


def draw_count():
    count = thousands(state["today"])
    scale = 2.5 if len(count) <= 5 else 2
    top = 36
    write(count, 14, top, HUGE, TEXT, scale)
    ink_bottom = top + (HUGE_TOP_BEARING + HUGE_INK) * scale
    write("steps today", 16, ink_bottom + 4, BODY, GREEN)


def cadence_label():
    if not pedometer.walking():
        return "resting"
    rate = pedometer.steps_per_minute()
    return "%d/min" % rate if rate else "walking"


def draw_stats():
    rows = (
        ("distance", distance_label(state["today"])),
        ("cadence", cadence_label()),
        ("best day", thousands(max(state["best"], state["today"]))),
        ("all time", thousands(state["total"])),
    )
    for index, (label, value) in enumerate(rows):
        x = 16 + (index % 2) * 96
        y = STATS_TOP + (index // 2) * STAT_PITCH
        write(label, x, y, SMALL, DIM)
        write(value, x, y + 9, BODY, TEXT)


def draw_trace():
    screen.pen = PANEL
    screen.rectangle(0, TRACE_TOP, WIDTH, TRACE_H)
    mid = TRACE_TOP + TRACE_H / 2
    screen.pen = FAINT
    screen.rectangle(0, mid, WIDTH, 1)
    threshold_y = mid - STEP_UP * TRACE_SCALE
    screen.pen = GREEN_DIM
    screen.rectangle(0, threshold_y, WIDTH, 1)
    step = WIDTH / (TRACE_LEN - 1)
    walking = pedometer.walking()
    screen.pen = GREEN_BRIGHT if walking else DIM
    previous = None
    for index in range(TRACE_LEN):
        value = pedometer.trace[(pedometer.trace_at + index) % TRACE_LEN]
        y = max(TRACE_TOP + 1, min(TRACE_TOP + TRACE_H - 1, mid - value * TRACE_SCALE))
        point = vec2(index * step, y)
        if previous is not None:
            screen.line(previous, point)
        previous = point
    write("walking" if walking else "still", 6, TRACE_TOP + 3, SMALL, GREEN_BRIGHT if walking else DIM)


def draw_title():
    screen.pen = PANEL
    screen.rectangle(0, 0, WIDTH, 32)
    write("steps", 12, 8, TITLE, TEXT)
    if pedometer.hardware.available:
        note = "counting in the background"
        pen = GREEN
    else:
        note = "counts while open only"
        pen = DIM
    write(note, WIDTH - 12 - text_width(note, SMALL), 9, SMALL, pen)
    key = state["day"] if state["day"] else "clock unset: no daily rollover"
    write(key, WIDTH - 12 - text_width(key, SMALL), 19, SMALL, DIM)


def draw_hints():
    cy = TRACE_TOP + TRACE_H + 10
    hints.draw_hint(HINT_STYLE, HINT_SHAPE, GOAL_LIT, 70, cy, HINT_RADIUS)
    write("goal", 70 + hints.hint_width(HINT_SHAPE, HINT_RADIUS) / 2 + 6, cy - 4, SMALL, DIM)
    hints.draw_hint(HINT_STYLE, HINT_SHAPE, RESET_LIT, 200, cy, HINT_RADIUS)
    write("hold to reset today", 200 + hints.hint_width(HINT_SHAPE, HINT_RADIUS) / 2 + 6, cy - 4, SMALL, DIM)


def draw_reset_progress():
    if reset_started is None:
        return
    done = min(1.0, (badge.ticks - reset_started) / RESET_HOLD_MS)
    screen.pen = WARNING
    screen.rectangle(0, HEIGHT - 3, WIDTH * done, 3)


def handle_buttons():
    global reset_started
    if badge.pressed(BUTTON_UP):
        state["goal"] = min(GOAL_MAX, state["goal"] + GOAL_STEP)
        pedometer.unsaved = SAVE_EVERY
    if badge.pressed(BUTTON_DOWN):
        state["goal"] = max(GOAL_MIN, state["goal"] - GOAL_STEP)
        pedometer.unsaved = SAVE_EVERY
    if badge.held(BUTTON_SELECT):
        if reset_started is None:
            reset_started = badge.ticks
        elif badge.ticks - reset_started >= RESET_HOLD_MS:
            pedometer.reset_today()
            reset_started = None
    else:
        reset_started = None


def update():
    global glow_until
    handle_buttons()
    if pedometer.update():
        glow_until = badge.ticks + GLOW_MS
    if pedometer.unsaved >= SAVE_EVERY:
        pedometer.save()

    glow = max(0.0, (glow_until - badge.ticks) / GLOW_MS)
    badge.caselights(glow * 0.6)

    screen.pen = BACKGROUND
    screen.clear()
    draw_title()
    draw_count()
    draw_ring()
    draw_stats()
    draw_trace()
    draw_hints()
    draw_reset_progress()


def on_exit():
    pedometer.save()
    badge.caselights(0)


run(update)
