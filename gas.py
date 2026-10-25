# gas.py - the gas stop that opens every trip: a 2D side-view cut-scene. The Ford GT pulls up to
# the one pump of a little 1980s Sinclair station in the empty desert, with the
# big longneck dinosaur standing out front. Then it drives off and the trip goes on.
import math

from gfx import W, buf, px, hline, vline, line, blit, make_sprite
import world as wd
from sprites import CAR_ROWS, DINO_ROWS

CAR = make_sprite(CAR_ROWS)
DINO = make_sprite(DINO_ROWS)
WHEELS = ((6, 8), (21, 8))
RING = ((1, 0), (1, 1), (0, 1), (-1, 1), (-1, 0), (-1, -1), (0, -1), (1, -1))

def set_car(spr):
    """Use this car sprite in the cut-scene (code.py swaps it every trip)."""
    global CAR
    CAR = spr


GROUND = 24          # row the station stands on (the edge of the road)
CAR_Y = 19           # top row of the car; its wheels touch row 30
STOP_X = 33          # where the car parks, beside the pump
PUMP_X = 17          # left edge of the pump
GALLONS = 14

# ---- timeline, in seconds since the cut-scene began ----
FADE = 0.6                       # dither fade between road view and cut-scene
T_IN, T_STOP = 1.0, 4.9          # the car rolls in and brakes to a stop
T_HOSE0, T_FILL0 = 5.5, 6.1      # the nozzle goes into the car
T_FILL1, T_HOSE1 = 12.7, 13.3    # ...fuelling... then comes back out
T_GO, T_GONE = 13.9, 17.5        # the car pulls away
T_END = 18.1                     # the cut-scene fades out here

# ---- tiny 3x5 font for the sign and the pump counter ----
FONT = {
    "S": ("###", "#..", "###", "..#", "###"),
    "I": ("#", "#", "#", "#", "#"),
    "N": ("###", "#.#", "#.#", "#.#", "#.#"),
    "C": ("###", "#..", "#..", "#..", "###"),
    "L": ("#..", "#..", "#..", "#..", "###"),
    "A": (".#.", "#.#", "###", "#.#", "#.#"),
    "R": ("##.", "#.#", "##.", "#.#", "#.#"),
    "0": ("###", "#.#", "#.#", "#.#", "###"),
    "1": (".#.", "##.", ".#.", ".#.", "###"),
    "2": ("###", "..#", "###", "#..", "###"),
    "3": ("###", "..#", "###", "..#", "###"),
    "4": ("#.#", "#.#", "###", "..#", "..#"),
    "5": ("###", "#..", "###", "..#", "###"),
    "6": ("###", "#..", "###", "#.#", "###"),
    "7": ("###", "..#", "..#", "..#", "..#"),
    "8": ("###", "#.#", "###", "#.#", "###"),
    "9": ("###", "#.#", "###", "..#", "###"),
}

# a few fixed pebbles / specks of desert between the horizon and the road
DOTS = [(wd.rnd(i) % W, 13 + wd.rnd(i + 70) % 10) for i in range(46)]


class Cut:
    pass


def start(first=False):
    """first=True at power-on: no road view to fade out, just fade in from black."""
    c = Cut()
    c.first = first
    c.t = FADE if first else 0.0
    c.x = -34.0      # car's left edge
    c.ph = 0.0       # wheel rotation phase
    c.v = 0.0        # car speed, px/s
    return c


def car_x(t):
    if t < T_IN:
        return -34.0
    if t < T_STOP:                       # fast in, long smooth braking
        u = (t - T_IN) / (T_STOP - T_IN)
        e = 1 - (1 - u) * (1 - u) * (1 - u) * (1 - u)
        return -34.0 + (STOP_X + 34) * e
    if t < T_GO:
        return float(STOP_X)
    u = (t - T_GO) / (T_GONE - T_GO)     # accelerate away
    if u > 1:
        u = 1.0
    return STOP_X + (W + 4 - STOP_X) * u * u


def advance(c, dt):
    c.t += dt
    x = car_x(c.t)
    if dt > 0:
        c.v = (x - c.x) / dt
    c.ph += (x - c.x) * 0.36
    c.x = x


def on_stage(c):
    """True once the road view has faded away and the cut-scene is showing."""
    return c.t >= FADE


def blank(t):
    """How much of the picture is faded to black right now (0 = none, 1 = all)."""
    if t < FADE:
        return t / FADE
    if t < 2 * FADE:
        return 1 - (t - FADE) / FADE
    if t > T_END - FADE:
        return (t - (T_END - FADE)) / FADE
    return 0.0


MASKS = ((0xEE, 0xBB), (0xAA, 0x55), (0x22, 0x88), (0, 0))


def dim(frac):
    """Dither the finished frame towards black (frac 0..1)."""
    i = int(frac * 5)
    if i < 1:
        return
    if i > 4:
        i = 4
    me, mo = MASKS[i - 1]
    for x in range(W):
        m = me if (x & 1) == 0 else mo
        buf[x] &= m
        buf[W + x] &= m
        buf[2 * W + x] &= m
        buf[3 * W + x] &= m


# ------------------------------------------------------------- scenery ----
def glyph(ch, x, y):
    rows = FONT[ch]
    for r in range(5):
        row = rows[r]
        for c in range(len(row)):
            if row[c] == "#":
                px(x + c, y + r)
    return len(rows[0])


def box(x0, y0, x1, y1):
    """Black-filled rectangle with a white outline."""
    for y in range(y0, y1 + 1):
        hline(x0, y, x1 - x0 + 1, False)
    hline(x0, y0, x1 - x0 + 1)
    hline(x0, y1, x1 - x0 + 1)
    vline(x0, y0, y1)
    vline(x1, y0, y1)


def tumbleweed(clk):
    x = W + 6 - int(clk * 20) % (W + 30)
    y = 16 - int(abs(math.sin(clk * 5.0)) * 3)
    for dx, dy in ((1, 0), (2, 0), (3, 0), (0, 1), (4, 1), (0, 2), (4, 2),
                   (0, 3), (4, 3), (1, 4), (2, 4), (3, 4)):
        px(x + dx, y + dy)
    if int(clk * 6) & 1:
        px(x + 1, y + 1)
        px(x + 3, y + 3)
    else:
        px(x + 3, y + 1)
        px(x + 1, y + 3)
    px(x + 2, y + 2)


def draw_station(clk):
    # roof-top sign
    box(68, 5, 98, 13)
    x = 70
    for ch in "SINCLAIR":
        x += glyph(ch, x, 7) + 1
    if int(clk * 2) & 1:                # bulbs on the sign blink
        px(67, 9)
        px(99, 9)
    # the little shop
    hline(66, 14, 35)                   # roof slab
    hline(66, 15, 35, False)
    for xx in range(66, 101, 2):
        px(xx, 15)
    for yy in range(16, GROUND):
        hline(69, yy, 29, False)
    vline(68, 16, GROUND)
    vline(98, 16, GROUND)
    box(72, 18, 77, GROUND)             # door
    px(75, 21)
    box(81, 18, 94, 22)                 # lit window
    for yy in range(19, 22):
        for xx in range(82, 94):
            if (xx + yy) & 1 == 0:
                px(xx, yy)
    vline(87, 18, 22)


def draw_dino(clk):
    sx, sy = 100, GROUND - 20
    blit(DINO, sx, sy, False)
    if (clk % 4.0) < 0.15:              # blink: the black eye closes
        px(sx + 2, sy + 1)


def draw_pump(gal):
    x0 = PUMP_X
    hline(x0 - 1, 11, 13)               # top cap
    for yy in range(12, GROUND):
        hline(x0, yy, 11, False)
        px(x0, yy)
        px(x0 + 10, yy)
    hline(x0 - 2, GROUND, 15)           # base
    box(x0 + 1, 13, x0 + 9, 19)         # counter window
    glyph(str(gal // 10), x0 + 2, 14)
    glyph(str(gal % 10), x0 + 6, 14)
    for yy in range(21, GROUND):        # striped panel
        for xx in range(x0 + 1, x0 + 10):
            if (xx + yy) & 1 == 0:
                px(xx, yy)
    px(x0 + 11, 16)                     # hose port


def hose_p(t):
    if t < T_HOSE0:
        return 0.0
    if t < T_FILL0:
        return (t - T_HOSE0) / (T_FILL0 - T_HOSE0)
    if t < T_FILL1:
        return 1.0
    if t < T_HOSE1:
        return 1.0 - (t - T_FILL1) / (T_HOSE1 - T_FILL1)
    return 0.0


def draw_hose(t):
    p = hose_p(t)
    e = p * p * (3 - 2 * p)
    fx, fy = STOP_X + 2, 24                         # the filler, on the rear flank
    tx = int(PUMP_X + 11 + (fx - PUMP_X - 11) * e + 0.5)
    ty = int(19 + (fy - 19) * e + 0.5)
    nx, ny = tx - int(3 * e + 0.5), ty - 3          # back end of the nozzle
    mx, my = (PUMP_X + 12 + nx) // 2 + 1, (16 + ny) // 2 + 1
    line(PUMP_X + 12, 16, mx, my)                   # the hose
    line(mx, my, nx, ny)
    line(nx, ny, tx, ty)                            # the nozzle
    px(nx - 1, ny)
    if e == 1.0 and int(t * 8) & 1:                 # fuel flowing
        px(tx + 1, ty - 1)


def draw_car(c, clk):
    sx = int(c.x + 0.5)
    sy = CAR_Y
    if sx >= W or sx < -34:
        return
    t = c.t
    for xx in range(1, 29, 2):
        px(sx + xx, sy + 12)
    blit(CAR, sx, sy, True, False)
    spin = int(c.ph) & 7
    for wx, wy in WHEELS:
        for j in (spin, (spin + 4) & 7):
            ox, oy = RING[j]
            hline(sx + wx + ox, sy + wy + oy, 1, False)
    if c.v > 25:                                    # speed streaks at the nose
        frame = int(clk * 20)
        for k in range(1, 9):
            if (k + frame) % 2 == 0:
                px(sx + 31 + k, sy + 5 + int(k * 0.12))
    rate = 16 if abs(c.v) > 5 else 5                # exhaust, slower at idle
    for k in range(3):
        d = (clk * rate + k * 5) % 14
        px(sx - 1 - int(d), sy + 7 - int(d / 6))
    if T_IN + 2.0 < t < T_STOP + 0.8:               # dust kicked up while braking
        for k in range(6):
            d = (clk * 14 + k * 4) % 12
            px(sx + 2 - int(d), 30 - int(d * 0.4) - (k & 1))


def draw(c, clk):
    """Draw the whole cut-scene into the (already cleared) canvas."""
    t = c.t
    wd.draw_stars(clk, 0)
    wd.draw_far_at(wd.DESERT, 310, clk)         # a distant mesa, behind the car
    for x, y in DOTS:
        px(x, y)
    wd.cactus(8, GROUND - 2, 10, 1)
    tumbleweed(clk)
    hline(0, GROUND, W)                         # edge of the road
    for x in range(4, W, 14):                   # dashed centre line
        hline(x, 28, 7)
    draw_station(clk)
    draw_dino(clk)
    g = 0
    if t >= T_FILL0:
        u = (t - T_FILL0) / (T_FILL1 - T_FILL0)
        g = GALLONS if u >= 1 else int(GALLONS * u)
    draw_pump(g)
    draw_car(c, clk)
    draw_hose(t)
