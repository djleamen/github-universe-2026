"""
Author: Dilara J. Leamen (@djleamen)
Date: Oct 28, 2026
"""

import math
import os
import random
import sys

APP_DIR = "/system/apps/marble_maze"
os.chdir(APP_DIR)
sys.path.insert(0, APP_DIR)

import hints
from badgeware import State

badge.mode(HIRES | VSYNC)
screen.antialias = image.X2

STATE_KEY = "marble_maze"
WIDTH, HEIGHT = 320, 240
HUD_H = 24
FIELD_TOP = HUD_H
FIELD_H = HEIGHT - HUD_H

GRAVITY = 16384.0
TILT_X = 1.0
TILT_Y = 1.0
TILT_SMOOTH = 0.35
DEAD_ZONE = 0.03
ACCEL = 1500.0
PAD_LEAN = 0.35
FRICTION = 1.6
BOUNCE = 0.35
MAX_SPEED = 300.0
SUBSTEPS = 4
MAX_DT = 0.05
WALL = 3
PIT_LEVEL = 3
PIT_SHARE = 0.05
FALL_MS = 420
WIN_MS = 1400
LEVELS = (
    (8, 6), (10, 7), (12, 8), (13, 9), (14, 10), (16, 11), (18, 12), (20, 13), (22, 15), (26, 18),
)

BACKGROUND = color.rgb(13, 17, 23)
FLOOR = color.rgb(22, 27, 34)
WALL_PEN = color.rgb(110, 118, 129)
WALL_LIT = color.rgb(201, 209, 217)
MARBLE = color.rgb(95, 237, 131)
MARBLE_SHINE = color.rgb(230, 255, 236)
MARBLE_SHADOW = color.rgb(0, 0, 0, 90)
EXIT = color.rgb(137, 87, 229)
EXIT_GLOW = color.rgb(137, 87, 229, 70)
PIT = color.rgb(0, 0, 0)
PIT_RIM = color.rgb(48, 54, 61)
TEXT = color.rgb(230, 237, 243)
DIM = color.rgb(139, 148, 158)
FAINT = color.rgb(48, 54, 61)
VEIL = color.rgb(0, 0, 0, 160)

HUGE = font.ignore
TITLE = font.futile
BODY = font.bacteria
SMALL = font.sins

HINT_STYLE = hints.Style(TEXT, FAINT, BACKGROUND)
START_LIT = (BUTTON_SELECT,)
HINT_SHAPE = (BUTTON_LEFT, BUTTON_RIGHT, BUTTON_SELECT)
HINT_RADIUS = 5

state = {"level": 1, "best": {}}
State.load(STATE_KEY, state)


class Maze:
    def __init__(self, columns, rows):
        self.columns = columns
        self.rows = rows
        self.cell = min((WIDTH - 2 * WALL) // columns, (FIELD_H - 2 * WALL) // rows)
        self.left = (WIDTH - columns * self.cell) // 2
        self.top = FIELD_TOP + (FIELD_H - rows * self.cell) // 2
        self.right = [[True] * rows for _ in range(columns)]
        self.bottom = [[True] * rows for _ in range(columns)]
        self.carve()
        self.walls = self.collect_walls()
        self.pits = set()

    def carve(self):
        columns, rows = self.columns, self.rows
        visited = [[False] * rows for _ in range(columns)]
        stack = [(0, 0)]
        visited[0][0] = True
        self.dead_ends = []
        while stack:
            x, y = stack[-1]
            options = []
            if x > 0 and not visited[x - 1][y]:
                options.append((x - 1, y))
            if x < columns - 1 and not visited[x + 1][y]:
                options.append((x + 1, y))
            if y > 0 and not visited[x][y - 1]:
                options.append((x, y - 1))
            if y < rows - 1 and not visited[x][y + 1]:
                options.append((x, y + 1))
            if not options:
                if len(stack) > 1 and self.exits(x, y) == 1:
                    self.dead_ends.append((x, y))
                stack.pop()
                continue
            nx, ny = random.choice(options)
            if nx < x:
                self.right[nx][y] = False
            elif nx > x:
                self.right[x][y] = False
            elif ny < y:
                self.bottom[x][ny] = False
            else:
                self.bottom[x][y] = False
            visited[nx][ny] = True
            stack.append((nx, ny))

    def exits(self, x, y):
        count = 0
        if x > 0 and not self.right[x - 1][y]:
            count += 1
        if not self.right[x][y]:
            count += 1
        if y > 0 and not self.bottom[x][y - 1]:
            count += 1
        if not self.bottom[x][y]:
            count += 1
        return count

    def collect_walls(self):
        cell, left, top = self.cell, self.left, self.top
        walls = {}

        def add(cx, cy, rect_):
            walls.setdefault((cx, cy), []).append(rect_)

        for x in range(self.columns):
            for y in range(self.rows):
                px, py = left + x * cell, top + y * cell
                if self.right[x][y]:
                    wall = (px + cell - WALL / 2, py - WALL / 2, WALL, cell + WALL)
                    add(x, y, wall)
                    if x + 1 < self.columns:
                        add(x + 1, y, wall)
                if self.bottom[x][y]:
                    wall = (px - WALL / 2, py + cell - WALL / 2, cell + WALL, WALL)
                    add(x, y, wall)
                    if y + 1 < self.rows:
                        add(x, y + 1, wall)
        for x in range(self.columns):
            add(x, 0, (left + x * cell - WALL / 2, top - WALL / 2, cell + WALL, WALL))
        for y in range(self.rows):
            add(0, y, (left - WALL / 2, top + y * cell - WALL / 2, WALL, cell + WALL))
        return walls

    def place_pits(self, share):
        candidates = [cell for cell in self.dead_ends if cell != (0, 0) and cell != self.goal_cell()]
        for index in range(len(candidates) - 1, 0, -1):
            swap = random.randint(0, index)
            candidates[index], candidates[swap] = candidates[swap], candidates[index]
        self.pits = set(candidates[:max(1, round(len(candidates) * share))] if candidates else [])

    def goal_cell(self):
        return (self.columns - 1, self.rows - 1)

    def centre(self, x, y):
        return self.left + (x + 0.5) * self.cell, self.top + (y + 0.5) * self.cell

    def cell_at(self, px, py):
        return int((px - self.left) // self.cell), int((py - self.top) // self.cell)

    def nearby_walls(self, px, py):
        cx, cy = self.cell_at(px, py)
        found = []
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                found.extend(self.walls.get((cx + dx, cy + dy), ()))
        return found

    def draw(self):
        cell = self.cell
        screen.pen = FLOOR
        screen.rectangle(self.left, self.top, self.columns * cell, self.rows * cell)
        screen.pen = PIT_RIM
        radius = cell * 0.32
        for x, y in self.pits:
            px, py = self.centre(x, y)
            screen.circle(vec2(px, py), radius)
            screen.pen = PIT
            screen.circle(vec2(px, py), radius - 2)
            screen.pen = PIT_RIM
        screen.pen = WALL_PEN
        for x in range(self.columns):
            for y in range(self.rows):
                px, py = self.left + x * cell, self.top + y * cell
                if self.right[x][y]:
                    screen.rectangle(px + cell - 1, py - 1, WALL, cell + WALL - 1)
                if self.bottom[x][y]:
                    screen.rectangle(px - 1, py + cell - 1, cell + WALL - 1, WALL)
        screen.pen = WALL_LIT
        screen.rectangle(self.left - 1, self.top - 1, self.columns * cell + WALL - 1, WALL)
        screen.rectangle(self.left - 1, self.top - 1, WALL, self.rows * cell + WALL - 1)
        screen.rectangle(self.left - 1, self.top + self.rows * cell - 1, self.columns * cell + WALL - 1, WALL)
        screen.rectangle(self.left + self.columns * cell - 1, self.top - 1, WALL, self.rows * cell + WALL - 1)


class Tilt:
    def __init__(self):
        self.level_x = 0.0
        self.level_y = 0.0
        self.x = 0.0
        self.y = 0.0

    def read(self):
        ax, ay = badge.imu()[:2]
        x, y = ax / GRAVITY * TILT_X, ay / GRAVITY * TILT_Y
        if badge.rotate_180():
            x, y = -x, -y
        return x, y

    def calibrate(self):
        self.level_x, self.level_y = self.read()
        self.x = self.y = 0.0

    def update(self):
        x, y = self.read()
        lean_x = x - self.level_x
        lean_y = y - self.level_y
        self.x += (lean_x - self.x) * TILT_SMOOTH
        self.y += (lean_y - self.y) * TILT_SMOOTH
        pad_x = int(badge.held(BUTTON_RIGHT)) - int(badge.held(BUTTON_LEFT))
        pad_y = int(badge.held(BUTTON_DOWN)) - int(badge.held(BUTTON_UP))
        return dead(self.x) + pad_x * PAD_LEAN, dead(self.y) + pad_y * PAD_LEAN


def dead(lean):
    if lean > DEAD_ZONE:
        return lean - DEAD_ZONE
    if lean < -DEAD_ZONE:
        return lean + DEAD_ZONE
    return 0.0


class Marble:
    def __init__(self, maze):
        self.maze = maze
        self.radius = max(3.0, maze.cell * 0.28)
        self.reset()

    def reset(self):
        self.x, self.y = self.maze.centre(0, 0)
        self.vx = self.vy = 0.0

    def push_out(self, wall):
        wx, wy, ww, wh = wall
        nearest_x = max(wx, min(self.x, wx + ww))
        nearest_y = max(wy, min(self.y, wy + wh))
        dx = self.x - nearest_x
        dy = self.y - nearest_y
        distance_squared = dx * dx + dy * dy
        radius = self.radius
        if distance_squared >= radius * radius:
            return False
        if distance_squared == 0:
            if ww < wh:
                dx, dy = (1.0 if self.x > wx + ww / 2 else -1.0), 0.0
                nearest_x = wx + ww if dx > 0 else wx
            else:
                dx, dy = 0.0, (1.0 if self.y > wy + wh / 2 else -1.0)
                nearest_y = wy + wh if dy > 0 else wy
        else:
            distance = math.sqrt(distance_squared)
            dx, dy = dx / distance, dy / distance
        self.x = nearest_x + dx * radius
        self.y = nearest_y + dy * radius
        along = self.vx * dx + self.vy * dy
        if along < 0:
            self.vx -= (1 + BOUNCE) * along * dx
            self.vy -= (1 + BOUNCE) * along * dy
        return True

    def update(self, lean_x, lean_y, seconds):
        self.vx += lean_x * ACCEL * seconds
        self.vy += lean_y * ACCEL * seconds
        drag = max(0.0, 1.0 - FRICTION * seconds)
        self.vx *= drag
        self.vy *= drag
        speed = math.sqrt(self.vx * self.vx + self.vy * self.vy)
        if speed > MAX_SPEED:
            self.vx *= MAX_SPEED / speed
            self.vy *= MAX_SPEED / speed
        step = seconds / SUBSTEPS
        for _ in range(SUBSTEPS):
            self.x += self.vx * step
            self.y += self.vy * step
            for wall in self.maze.nearby_walls(self.x, self.y):
                self.push_out(wall)

    def cell(self):
        return self.maze.cell_at(self.x, self.y)

    def over(self, cell, within):
        px, py = self.maze.centre(*cell)
        dx, dy = self.x - px, self.y - py
        return dx * dx + dy * dy < within * within

    def draw(self, scale=1.0):
        radius = self.radius * scale
        if radius <= 0.5:
            return
        screen.pen = MARBLE_SHADOW
        screen.circle(vec2(self.x + 2, self.y + 2), radius)
        screen.pen = MARBLE
        screen.circle(vec2(self.x, self.y), radius)
        screen.pen = MARBLE_SHINE
        screen.circle(vec2(self.x - radius * 0.35, self.y - radius * 0.35), max(1.0, radius * 0.28))


class Game:
    TITLE, PLAYING, FALLING, WON = range(4)

    def __init__(self):
        self.tilt = Tilt()
        self.mode = self.TITLE
        self.level = max(1, min(len(LEVELS), int(state.get("level", 1))))
        self.new_maze()
        self.started = 0
        self.elapsed = 0
        self.completed = 0
        self.record = False
        self.mode_since = 0

    def new_maze(self):
        columns, rows = LEVELS[self.level - 1]
        self.maze = Maze(columns, rows)
        if self.level >= PIT_LEVEL:
            self.maze.place_pits(PIT_SHARE + (self.level - PIT_LEVEL) * 0.02)
        self.marble = Marble(self.maze)
        self.goal = self.maze.goal_cell()

    def begin(self):
        self.tilt.calibrate()
        self.marble.reset()
        self.started = badge.ticks
        self.mode = self.PLAYING

    def finish(self):
        self.elapsed = badge.ticks - self.started
        self.completed = self.level
        key = str(self.level)
        best = state["best"].get(key)
        self.record = best is None or self.elapsed < best
        if self.record:
            state["best"][key] = self.elapsed
        if self.level < len(LEVELS):
            self.level += 1
        state["level"] = self.level
        State.save(STATE_KEY, state)
        self.mode = self.WON
        self.mode_since = badge.ticks

    def update(self):
        now = badge.ticks
        if self.mode == self.TITLE:
            if badge.pressed(BUTTON_SELECT):
                self.begin()
        elif self.mode == self.PLAYING:
            self.play(now)
        elif self.mode == self.FALLING:
            if now - self.mode_since >= FALL_MS:
                self.marble.reset()
                self.mode = self.PLAYING
        elif self.mode == self.WON:
            if now - self.mode_since >= WIN_MS and badge.pressed(BUTTON_SELECT):
                self.new_maze()
                self.begin()
        if badge.held(BUTTON_LEFT) and badge.held(BUTTON_RIGHT) and (badge.pressed(BUTTON_LEFT) or badge.pressed(BUTTON_RIGHT)):
            self.level = 1
            state["level"] = 1
            State.save(STATE_KEY, state)
            self.new_maze()
            self.mode = self.TITLE
        self.draw(now)

    def play(self, now):
        if badge.pressed(BUTTON_SELECT):
            self.tilt.calibrate()
        lean_x, lean_y = self.tilt.update()
        seconds = min(MAX_DT, badge.ticks_delta / 1000)
        self.marble.update(lean_x, lean_y, seconds)
        reach = self.maze.cell * 0.3
        if self.marble.over(self.goal, reach):
            self.finish()
            return
        cell = self.marble.cell()
        if cell in self.maze.pits and self.marble.over(cell, self.maze.cell * 0.22):
            self.mode = self.FALLING
            self.mode_since = now
            self.fall_from = (self.marble.x, self.marble.y)
            self.marble.vx = self.marble.vy = 0.0

    def draw_exit(self, now):
        px, py = self.maze.centre(*self.goal)
        pulse = 0.5 + 0.5 * math.sin(now / 260)
        radius = self.maze.cell * 0.34
        screen.pen = EXIT_GLOW
        screen.circle(vec2(px, py), radius + 3 + pulse * 3)
        screen.pen = EXIT
        screen.circle(vec2(px, py), radius)
        screen.pen = FLOOR
        screen.circle(vec2(px, py), max(1.0, radius - 3))
        screen.pen = EXIT
        screen.circle(vec2(px, py), max(1.0, radius * 0.3))

    def draw_hud(self, now):
        screen.pen = BACKGROUND
        screen.rectangle(0, 0, WIDTH, HUD_H)
        write("level %d/%d" % (self.level, len(LEVELS)), 10, 6, BODY, TEXT)
        if self.mode in (self.PLAYING, self.FALLING):
            elapsed = now - self.started
        elif self.mode == self.WON:
            elapsed = self.elapsed
        else:
            elapsed = 0
        clock = fmt_time(elapsed)
        write(clock, WIDTH / 2 - text_width(clock, BODY) / 2, 6, BODY, TEXT)
        best = state["best"].get(str(self.level))
        if best is not None and self.mode != self.WON:
            label = "best " + fmt_time(best)
            write(label, WIDTH - 10 - text_width(label, SMALL), 9, SMALL, DIM)

    def draw(self, now):
        screen.pen = BACKGROUND
        screen.clear()
        self.maze.draw()
        self.draw_exit(now)
        if self.mode == self.FALLING:
            self.marble.draw(1.0 - (now - self.mode_since) / FALL_MS)
        else:
            self.marble.draw()
        self.draw_hud(now)
        if self.mode == self.TITLE:
            self.draw_title(now)
        elif self.mode == self.WON:
            self.draw_won(now)

    def draw_title(self, now):
        screen.pen = VEIL
        screen.rectangle(0, 0, WIDTH, HEIGHT)
        bob = math.sin(now / 520.0) * 3
        centred("marble maze", 52 + bob, HUGE, MARBLE, scale=2)
        centred("tilt the badge to roll", 108, BODY, TEXT)
        centred("the badge levels itself when you press start", 128, SMALL, DIM)
        if self.level >= PIT_LEVEL:
            centred("mind the pits", 142, SMALL, DIM)
        hint_with_label("start", START_LIT, WIDTH / 2, 186)

    def draw_won(self, now):
        screen.pen = VEIL
        screen.rectangle(0, 0, WIDTH, HEIGHT)
        heading = "all clear!" if self.completed == len(LEVELS) else "level up!"
        centred(heading, 56, HUGE, EXIT, scale=2)
        centred(fmt_time(self.elapsed), 104, TITLE, TEXT, scale=2)
        if self.record:
            centred("new best", 136, BODY, MARBLE)
        if now - self.mode_since >= WIN_MS:
            hint_with_label("next maze", START_LIT, WIDTH / 2, 186)


def fmt_time(ms):
    seconds = ms // 1000
    return "%d:%02d.%d" % (seconds // 60, seconds % 60, (ms % 1000) // 100)


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


def centred(text, y, typeface, pen, cx=WIDTH / 2, scale=1):
    write(text, cx - text_width(text, typeface, scale) / 2, y, typeface, pen, scale)


def hint_with_label(label, lit, cx, cy):
    hints.draw_hint(HINT_STYLE, HINT_SHAPE, lit, cx, cy, HINT_RADIUS)
    centred(label, cy + hints.hint_height(HINT_SHAPE, HINT_RADIUS) / 2 + 6, BODY, TEXT, cx)


game = Game()


def update():
    game.update()


def on_exit():
    state["level"] = game.level
    State.save(STATE_KEY, state)


run(update)
