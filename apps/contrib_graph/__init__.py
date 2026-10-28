"""
Author: Dilara J. Leamen (@djleamen)
Date: Oct 28, 2026
"""

import gc
import json
import os
import sys

APP_DIR = "/system/apps/contrib_graph"
os.chdir(APP_DIR)
sys.path.insert(0, APP_DIR)

import fetch
import hints
import missing_details
from badgeware import State

try:
    import secrets
except ImportError:
    secrets = None

badge.mode(HIRES | VSYNC)
screen.antialias = image.X2

STATE_KEY = "contrib_graph"
WIDTH, HEIGHT = 320, 240
CX = WIDTH / 2

CONTRIB_URL = "https://github.com/{user}.contribs"
HEADERS = {"User-Agent": "GitHub Universe Badge 2026"}
CACHE_DIR = "/state"
DATA_FILE = CACHE_DIR + "/contrib_graph_data.json"
TEMP_FILE = DATA_FILE + ".tmp"
RETRY_MS = 30000
REVEAL_MS = 1400

WEEKS = 53
DAYS = 7
YEAR_PITCH = 6
YEAR_CELL = 5
YEAR_LEFT = (WIDTH - WEEKS * YEAR_PITCH + 1) // 2
YEAR_TOP = 40
RECENT_WEEKS = 16
RECENT_PITCH = 19
RECENT_CELL = 16
RECENT_LEFT = (WIDTH - RECENT_WEEKS * RECENT_PITCH + (RECENT_PITCH - RECENT_CELL)) // 2
RECENT_TOP = 54

BACKGROUND = color.rgb(13, 17, 23)
PANEL = color.rgb(22, 27, 34)
TEXT = color.rgb(230, 237, 243)
DIM = color.rgb(139, 148, 158)
FAINT = color.rgb(48, 54, 61)
GREEN = color.rgb(63, 185, 80)
GREEN_BRIGHT = color.rgb(95, 237, 131)
WARNING = color.rgb(255, 125, 120)
LEVELS = (
    color.rgb(22, 27, 34),
    color.rgb(14, 68, 41),
    color.rgb(0, 109, 50),
    color.rgb(38, 166, 65),
    color.rgb(57, 211, 83),
)

TITLE = font.futile
SMALL = font.sins
HUGE = font.ignore
# Mona Sans is a vector font, so it takes a point size; the pixel fonts above
# take none. Bacteria (the obvious pixel body font) is a wide monospace that
# runs to 12px a character, far too wide for three columns of figures.
BODY = missing_details.mona_sans()
BODY_SIZE = 14
NOTE_SIZE = 12
LABEL_H = 12                # the height measure_text reports for sins
ROW_GAP = 10                # between a label line and the value under it

HINT_STYLE = hints.Style(TEXT, FAINT, BACKGROUND)
VIEW_LIT = (BUTTON_LEFT, BUTTON_RIGHT)
FETCH_LIT = (BUTTON_SELECT,)
HINT_SHAPE = VIEW_LIT + FETCH_LIT
HINT_RADIUS = 5

MONTHS = ("Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec")
WEEKDAYS = ("Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat")

fetch.AsyncFetch.MAX_HEADER_BYTES = 8192

try:
    os.mkdir(CACHE_DIR)
except OSError:
    pass

state = {"user": ""}
State.load(STATE_KEY, state)


def setting(key):
    return str(getattr(secrets, key, "") or "").strip()


def days_from_civil(year, month, day):
    year -= month <= 2
    era = (year if year >= 0 else year - 399) // 400
    yoe = year - era * 400
    doy = (153 * (month + (-3 if month > 2 else 9)) + 2) // 5 + day - 1
    doe = yoe * 365 + yoe // 4 - yoe // 100 + doy
    return era * 146097 + doe - 719468


def civil_from_days(days):
    days += 719468
    era = (days if days >= 0 else days - 146096) // 146097
    doe = days - era * 146097
    yoe = (doe - doe // 1460 + doe // 36524 - doe // 146096) // 365
    year = yoe + era * 400
    doy = doe - (365 * yoe + yoe // 4 - yoe // 100)
    mp = (5 * doy + 2) // 153
    day = doy - (153 * mp + 2) // 5 + 1
    month = mp + (3 if mp < 10 else -9)
    return year + (month <= 2), month, day


def parse_date(text):
    year, month, day = (int(part) for part in text.split("-"))
    return days_from_civil(year, month, day)


def short_date(days):
    year, month, day = civil_from_days(days)
    return "%d %s" % (day, MONTHS[month - 1])


class Graph:
    def __init__(self):
        self.loaded = False
        self.counts = []
        self.levels = []
        self.first_day = 0
        self.week_of = []
        self.weekday_of = []
        self.total = 0
        self.current_streak = 0
        self.longest_streak = 0
        self.longest_ends = 0
        self.best_count = 0
        self.best_day = 0
        self.active_days = 0
        self.weekday_totals = [0] * DAYS
        self.month_columns = []
        self.generated = ""

    def load(self, path):
        with open(path, "r") as file:
            data = json.load(file)
        counts, levels, week_of, weekday_of = [], [], [], []
        first_day = None
        month_columns = []
        last_month = None
        for column, week in enumerate(data["weeks"][:WEEKS]):
            start = parse_date(week["first_day"])
            if first_day is None:
                first_day = start
            month = civil_from_days(start)[1]
            if month != last_month:
                month_columns.append((column, MONTHS[month - 1]))
                last_month = month
            for entry in week["contribution_days"]:
                weekday = int(entry["weekday"])
                counts.append(int(entry["count"]))
                levels.append(max(0, min(4, int(entry["level"]))))
                week_of.append(column)
                weekday_of.append(weekday)
        month_columns = [
            label for index, label in enumerate(month_columns)
            if index + 1 == len(month_columns) or month_columns[index + 1][0] - label[0] >= 3
        ]
        self.generated = str(data.get("generated_at", ""))[:10]
        total = data.get("total_contributions")
        del data
        gc.collect()
        if not counts:
            raise ValueError("no contribution days")
        self.counts, self.levels = counts, levels
        self.week_of, self.weekday_of = week_of, weekday_of
        self.first_day = first_day
        self.month_columns = month_columns
        self.total = int(total) if total is not None else sum(counts)
        self.figure()
        self.loaded = True

    def figure(self):
        counts = self.counts
        longest = longest_ends = run = 0
        best = best_at = 0
        active = 0
        weekday_totals = [0] * DAYS
        for index, count in enumerate(counts):
            if count:
                run += 1
                active += 1
                if run > longest:
                    longest, longest_ends = run, index
            else:
                run = 0
            if count > best:
                best, best_at = count, index
            weekday_totals[self.weekday_of[index]] += count
        current = 0
        index = len(counts) - 1
        if counts[index] == 0:
            index -= 1
        while index >= 0 and counts[index]:
            current += 1
            index -= 1
        self.longest_streak, self.longest_ends = longest, longest_ends
        self.current_streak = current
        self.best_count, self.best_day = best, best_at
        self.active_days = active
        self.weekday_totals = weekday_totals

    def day_number(self, index):
        return self.first_day + index

    @property
    def last_week(self):
        return self.week_of[-1] if self.week_of else 0


graph = Graph()


class Downloader:
    def __init__(self, user):
        self.user = user
        self.request = None
        self.error = None
        self.retry_at = 0
        self.fetched = False
        self.wanted = False

    def start(self):
        self.wanted = True

    def update(self):
        if self.request is None:
            if not self.wanted or badge.ticks < self.retry_at:
                return
            if missing_details.missing("WIFI_SSID"):
                self.error = "no wifi details"
                self.wanted = False
                return
            self.request = fetch.url(CONTRIB_URL.format(user=self.user), headers=HEADERS).to(TEMP_FILE)
            self.error = None
            return
        if self.request:
            self.request = None
            self.wanted = False
            try:
                os.rename(TEMP_FILE, DATA_FILE)
                graph.load(DATA_FILE)
                state["user"] = self.user
                State.save(STATE_KEY, state)
                self.fetched = True
                reveal.start()
            except (OSError, ValueError, KeyError, TypeError) as reason:
                self.fail("%s: %s" % (type(reason).__name__, reason))
        elif self.request.error:
            error = self.request.error
            self.request = None
            self.fail(str(error))

    def fail(self, error):
        print("contrib_graph:", error)
        self.error = error
        self.retry_at = badge.ticks + RETRY_MS
        try:
            os.remove(TEMP_FILE)
        except OSError:
            pass

    @property
    def busy(self):
        return self.request is not None

    def status(self):
        if self.request is not None:
            text = self.request.state
            return text if text not in ("Idle", "Fetching") else "fetching contributions..."
        if self.error:
            return "fetch failed: " + self.error
        if self.fetched:
            return "up to date"
        return "cached copy" if graph.loaded else ""


class Reveal:
    def __init__(self):
        self.since = None

    def start(self):
        self.since = badge.ticks

    def column_limit(self, columns):
        if self.since is None:
            return columns
        done = (badge.ticks - self.since) / REVEAL_MS
        if done >= 1:
            self.since = None
            return columns
        return done * columns


reveal = Reveal()

user = setting("GITHUB_USERNAME")
downloader = Downloader(user)
view = 0
VIEWS = 3

if user:
    if state.get("user", "").lower() == user.lower() and file_exists(DATA_FILE):
        try:
            graph.load(DATA_FILE)
            reveal.start()
        except (OSError, ValueError, KeyError, TypeError) as reason:
            print("contrib_graph: cache unreadable:", reason)
    if not graph.loaded:
        downloader.start()


def text_width(text, typeface, scale=1, size=None):
    screen.font = typeface
    if size:
        return screen.measure_text(text, font_size=size)[0]
    return screen.measure_text(text)[0] * scale


def write(text, x, y, typeface, pen, scale=1, size=None):
    screen.font = typeface
    screen.pen = pen
    if size:
        screen.text(text, x, y, size)
        return
    if scale == 1:
        screen.text(text, x, y)
        return
    at = vec2(x, y)
    screen.text(text, at, transform=mat3().translate(at).scale(scale, scale).translate(vec2(-x, -y)))


def centred(text, y, typeface, pen, cx=CX, scale=1, size=None):
    write(text, cx - text_width(text, typeface, scale, size) / 2, y, typeface, pen, scale, size)


def body(text, x, y, pen=None, size=BODY_SIZE):
    write(text, x, y, BODY, TEXT if pen is None else pen, size=size)


def body_centred(text, y, pen=None, size=BODY_SIZE, cx=CX):
    centred(text, y, BODY, TEXT if pen is None else pen, cx, size=size)


def thousands(value):
    text = str(int(value))
    out = ""
    while len(text) > 3:
        out = "," + text[-3:] + out
        text = text[:-3]
    return text + out


def plural(count, word):
    return "%d %s%s" % (count, word, "" if count == 1 else "s")


def draw_header():
    screen.pen = PANEL
    screen.rectangle(0, 0, WIDTH, 30)
    titles = ("past year", "last %d weeks" % RECENT_WEEKS, "by the numbers")
    label = titles[view]
    label_w = text_width(label, BODY, size=BODY_SIZE)
    handle = fit("@" + user if user else "contributions", WIDTH - 12 - label_w - 24, TITLE)
    write(handle, 12, 7, TITLE, TEXT)
    body(label, WIDTH - 12 - label_w, 8, GREEN)


def draw_cells(left, top, pitch, size, first_week, columns):
    limit = reveal.column_limit(columns)
    cell = shape.rounded_rectangle(0, 0, size, size, 1 if size < 8 else 3)
    for index in range(len(graph.counts)):
        column = graph.week_of[index] - first_week
        if column < 0 or column >= limit:
            continue
        screen.pen = LEVELS[graph.levels[index]]
        cell.transform = mat3().translate(left + column * pitch, top + graph.weekday_of[index] * pitch)
        screen.shape(cell)


def draw_placeholder(left, top, pitch, size, columns):
    cell = shape.rounded_rectangle(0, 0, size, size, 1 if size < 8 else 3)
    screen.pen = LEVELS[0]
    for column in range(columns):
        for row in range(DAYS):
            cell.transform = mat3().translate(left + column * pitch, top + row * pitch)
            screen.shape(cell)


def draw_year():
    if graph.loaded:
        for column, name in graph.month_columns:
            if column < WEEKS - 2:
                write(name, YEAR_LEFT + column * YEAR_PITCH, YEAR_TOP - 10, SMALL, DIM)
        draw_cells(YEAR_LEFT, YEAR_TOP, YEAR_PITCH, YEAR_CELL, 0, WEEKS)
    else:
        draw_placeholder(YEAR_LEFT, YEAR_TOP, YEAR_PITCH, YEAR_CELL, WEEKS)
    # three evenly spaced columns of figures under the graph, each with its
    # label above, then the legend on a line of its own
    columns = (16, 118, 220)
    base = YEAR_TOP + DAYS * YEAR_PITCH + 14
    stat(columns[0], base, "contributions", thousands(graph.total) if graph.loaded else "-")
    stat(columns[1], base, "current streak", plural(graph.current_streak, "day") if graph.loaded else "-")
    stat(columns[2], base, "longest streak", plural(graph.longest_streak, "day") if graph.loaded else "-")
    base += STAT_H + 12
    if graph.loaded:
        best = "%s on %s" % (thousands(graph.best_count), short_date(graph.day_number(graph.best_day)))
        share = "%d of %d days" % (graph.active_days, len(graph.counts))
        rate = "%.1f a day" % (graph.total / max(1, len(graph.counts)))
    else:
        best = share = rate = "-"
    stat(columns[0], base, "busiest day", best)
    stat(columns[1], base, "active days", share)
    stat(columns[2], base, "average", rate)
    draw_legend(CX, base + STAT_H + 14)


def draw_legend(cx, y):
    less_w = text_width("less", SMALL)
    more_w = text_width("more", SMALL)
    swatches = 5 * 11 - 3
    total = less_w + 6 + swatches + 6 + more_w
    x = cx - total / 2
    write("less", x, y - 1, SMALL, DIM)
    x += less_w + 6
    swatch = shape.rounded_rectangle(0, 0, 8, 8, 1)
    for level in range(5):
        screen.pen = LEVELS[level]
        swatch.transform = mat3().translate(x + level * 11, y)
        screen.shape(swatch)
    write("more", x + swatches + 6, y - 1, SMALL, DIM)


STAT_H = LABEL_H + ROW_GAP + BODY_SIZE


def stat(x, y, label, value):
    write(label, x, y, SMALL, DIM)
    body(value, x, y + ROW_GAP + 2)


def draw_recent():
    first_week = max(0, graph.last_week - RECENT_WEEKS + 1) if graph.loaded else 0
    for row, name in enumerate(WEEKDAYS):
        if row % 2 == 1:
            write(name, RECENT_LEFT - 24, RECENT_TOP + row * RECENT_PITCH + 5, SMALL, DIM)
    if graph.loaded:
        for column, name in graph.month_columns:
            shown = column - first_week
            if 0 <= shown < RECENT_WEEKS - 1:
                write(name, RECENT_LEFT + shown * RECENT_PITCH, RECENT_TOP - 12, SMALL, DIM)
        draw_cells(RECENT_LEFT, RECENT_TOP, RECENT_PITCH, RECENT_CELL, first_week, RECENT_WEEKS)
        start = None
        for index in range(len(graph.counts)):
            if graph.week_of[index] >= first_week:
                start = index
                break
        recent = graph.counts[start:] if start is not None else []
        summary = "%s contributions in the last %d weeks" % (thousands(sum(recent)), RECENT_WEEKS)
        body_centred(summary, RECENT_TOP + DAYS * RECENT_PITCH + 12)
    else:
        draw_placeholder(RECENT_LEFT, RECENT_TOP, RECENT_PITCH, RECENT_CELL, RECENT_WEEKS)


def draw_numbers():
    if not graph.loaded:
        body_centred("nothing to count yet", 110, DIM)
        return
    # ignore's digits carry about 7px of blank above 17px of ink; at 1.5x
    # the ink runs 10px to 36px below the line, so the caption hangs off that
    centred(thousands(graph.total), 36, HUGE, GREEN_BRIGHT, scale=1.5)
    body_centred("contributions in the past year", 36 + 36 + 6, DIM)
    top = 100
    pitch, bar_h = 15, 10
    bar_left, bar_width = 60, 190
    peak = max(graph.weekday_totals) or 1
    for row in range(DAYS):
        y = top + row * pitch
        write(WEEKDAYS[row], 24, y - 1, SMALL, DIM)
        screen.pen = FAINT
        screen.rectangle(bar_left, y, bar_width, bar_h)
        share = graph.weekday_totals[row] / peak
        screen.pen = GREEN_BRIGHT if share >= 0.999 else GREEN
        screen.rectangle(bar_left, y, bar_width * share, bar_h)
        write(thousands(graph.weekday_totals[row]), bar_left + bar_width + 8, y - 1, SMALL, TEXT)
    foot = top + DAYS * pitch + 4
    if graph.longest_streak:
        ends = graph.day_number(graph.longest_ends)
        starts = ends - graph.longest_streak + 1
        note = "longest streak %s to %s" % (short_date(starts), short_date(ends))
        body_centred(note, foot, DIM, NOTE_SIZE)


def draw_footer():
    cy = HEIGHT - 12
    hints.draw_hint(HINT_STYLE, HINT_SHAPE, VIEW_LIT, 28, cy, HINT_RADIUS)
    write("view", 28 + hints.hint_width(HINT_SHAPE, HINT_RADIUS) / 2 + 6, cy - 4, SMALL, DIM)
    hints.draw_hint(HINT_STYLE, HINT_SHAPE, FETCH_LIT, 96, cy, HINT_RADIUS)
    write("refresh", 96 + hints.hint_width(HINT_SHAPE, HINT_RADIUS) / 2 + 6, cy - 4, SMALL, DIM)

    right = WIDTH - 12
    if downloader.busy:
        screen.pen = color.rgb(255, 255, 255, 40)
        screen.shape(shape.arc(right - 5, cy, 3, 5, 0, 360))
        turned = badge.ticks / 1000 * 360
        screen.pen = GREEN
        screen.shape(shape.arc(right - 5, cy, 3, 5, turned, turned + 100))
        right -= 16
    text = downloader.status()
    if not text and graph.generated:
        text = "data from " + graph.generated
    if text:
        text = fit(text, right - 160, SMALL)
        pen = WARNING if downloader.error else DIM
        write(text, right - text_width(text, SMALL), cy - 4, SMALL, pen)


def fit(text, width, typeface):
    while len(text) > 1 and text_width(text, typeface) > width:
        text = text[:-1]
    return text


def handle_buttons():
    global view
    if badge.pressed(BUTTON_RIGHT):
        view = (view + 1) % VIEWS
        reveal.start()
    if badge.pressed(BUTTON_LEFT):
        view = (view - 1) % VIEWS
        reveal.start()
    if badge.pressed(BUTTON_SELECT) and not downloader.busy:
        downloader.retry_at = 0
        downloader.start()


def update():
    screen.pen = BACKGROUND
    screen.clear()
    if not user:
        missing_details.show(["GITHUB_USERNAME"], draw_header)
        return
    handle_buttons()
    downloader.update()
    draw_header()
    if view == 0:
        draw_year()
    elif view == 1:
        draw_recent()
    else:
        draw_numbers()
    if not graph.loaded and downloader.error and not downloader.busy:
        body_centred("could not fetch contributions", 194, WARNING)
    draw_footer()


run(update)
