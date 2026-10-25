# code.py - Road trip: city -> desert -> farmland -> mountains -> forest -> big city -> neon grid
# Adafruit 2.23" 128x32 SSD1305 OLED on a Raspberry Pi Pico (CircuitPython)
# Files needed on CIRCUITPY: code.py, gfx.py, world.py, sprites.py, cars.py, gas.py,
#                            tunnel.py
#                            + adafruit_ssd1305 in /lib
#
# Every trip opens at a 1980s Sinclair gas station in the desert (a cut-scene), then
# drives the whole route: desert -> farmland -> mountains -> forest -> big city ->
# neon grid -> city (22.5 minutes) and comes back to the gas station. The car that
# leaves the station is the next one from the garage (stock, wedge, pony, stock...).
# Once per trip, in the mountains, the road dives into a tunnel: the car vanishes
# into the rock and a 30 s first-person drive through it plays; then the car comes
# out of the far portal on the other side of the screen.
# Rain comes and goes (never in the desert), snow falls only in the mountains. The
# car changes lanes only when it has to: to dodge puddles (rain), snakes (desert),
# fallen rocks (mountains), or to overtake a slower vehicle. A faster car passes now
# and then.
# Every kind of vehicle has its own speed. In the neon grid zone the traffic becomes
# light-cycles, by far the fastest thing on the road, each laying a light-wall trail
# that slowly fades away.
import math
import random
import time

from gfx import (W, H, buf, px, hline, vline, show, clear, gy, make_sprite,
                 blit, SLOPE)
import world as wd
import gas

# A half-copied or old file on the board gives confusing errors later, so check first.
for _n in ("FADE", "T_END", "start", "advance", "draw", "dim", "glyph", "blank",
           "on_stage", "set_car"):
    if not hasattr(gas, _n):
        raise RuntimeError("gas.py on the board is old or incomplete (no %s): "
                           "copy the newest gas.py, eject, then press Ctrl-D" % _n)
import tunnel
from cars import WEDGE_ROWS, PONY_ROWS
from sprites import (CAR_ROWS, SEDAN_ROWS, TRUCK_ROWS, TRACTOR_ROWS,
                     CYCLE_ROWS)

# ---------------------------------------------------------------- tuning ----
LANE_MOVE = 0.9      # seconds a lane change takes
# speed of each vehicle relative to our car, px/s (negative = slower than us).
# Every vehicle gets +-12% on top, so no two look quite alike.
REL_SLOW = {"tractor": -40, "truck": -27, "sedan": -17}
REL_FAST = 34        # a faster sedan pulling ahead of us
REL_CYCLE = 125      # light-cycles: super fast
TRAIL_FADE = 2.6     # seconds for a light-trail to dissolve completely
CAR_X = 36           # left edge of our car (near lane)
CAR_BOTTOM = 30      # wheel-contact row of the near lane
LANE_DX, LANE_DY = 3, 6
PUDDLE_REF = (28.5, 22.1)   # lane-centre rows at x = 64: (near, far)
MAX_DT = 0.08        # a slow frame never jumps the world more than this

# --------------------------------------------------------------- sprites ----
GARAGE = (CAR_ROWS, WEDGE_ROWS, PONY_ROWS)   # one per trip, in this order
CAR = make_sprite(CAR_ROWS)
CAR_H = len(CAR_ROWS)
WHEELS = ((6, 8), (21, 8))
RING = ((1, 0), (1, 1), (0, 1), (-1, 1), (-1, 0), (-1, -1), (0, -1), (1, -1))


def _vehicle(rows):
    """(sprite, height, row of the wheel-contact line)"""
    ground = 0
    for y in range(len(rows)):
        if '#' in rows[y] or ':' in rows[y]:
            ground = y
    return make_sprite(rows), len(rows), ground


VEH = {
    "sedan": _vehicle(SEDAN_ROWS),
    "truck": _vehicle(TRUCK_ROWS),
    "tractor": _vehicle(TRACTOR_ROWS),
    "cycle": _vehicle(CYCLE_ROWS),
}


# ---------------------------------------------------------------- state ----
class Trip:
    pass


S = Trip()
S.tt = 0.0           # trip clock (wraps every 20 minutes)
S.clk = 0.0          # free-running animation clock
S.lane_tgt = 0       # 0 = near/home lane, 1 = far lane
S.lane_f = 0.0
S.mv_from = 0.0
S.mv_t0 = -10.0
S.ev = None          # the one active hazard / vehicle, or None
S.next_ev = 30.0
S.free_since = 0.0   # when the road last became clear
S.wk = None
S.wi = 0.0
S.cut = None         # the gas-stop cut-scene while it plays
S.cut_fin = 0.0      # fade-in time left once the cut-scene is over
S.car_i = 0          # which car of the GARAGE we are driving
S.tun = None         # the mountain tunnel while it is on screen
S.tun_done = False   # has this trip's tunnel happened yet?


def begin_cut(mod, *args):
    """Start a cut-scene module (gas or tunnel); the main loop drives it generically."""
    S.cut = mod.start(*args)
    S.cut.mod = mod


def set_car(i):
    """Switch to car i of the garage (on the road and in the gas-stop cut-scene)."""
    global CAR, CAR_H
    S.car_i = i
    CAR = make_sprite(GARAGE[i])
    CAR_H = len(GARAGE[i])
    gas.set_car(CAR)


def set_lane(l):
    if l != S.lane_tgt:
        S.mv_from = S.lane_f
        S.lane_tgt = l
        S.mv_t0 = S.clk


def update_lane():
    p = (S.clk - S.mv_t0) / LANE_MOVE
    if p >= 1:
        S.lane_f = float(S.lane_tgt)
    else:
        s = p * p * (3 - 2 * p)
        S.lane_f = S.mv_from + (S.lane_tgt - S.mv_from) * s


# --------------------------------------------------------------- events ----
HAZ_HW = {"puddle": 8, "snake": 8, "rock": 6}


def pick_event():
    b = wd.biome_at(S.tt)
    opts = []
    if S.wk == "rain" and S.wi > 0.45:
        opts.append(("puddle", 6))
    if b == wd.DESERT:
        opts.append(("snake", 6))
    if b == wd.MOUNT:
        opts.append(("rock", 5))
    hazards = len(opts) > 0
    opts.append(("slow", 1.2 if hazards else 1))
    opts.append(("fast", 1.0))
    total = 0
    for k, w in opts:
        total += w
    r = random.random() * total
    for k, w in opts:
        r -= w
        if r <= 0:
            return k, hazards
    return opts[-1][0], hazards


def spawn():
    kind, hazards = pick_event()
    b = wd.biome_at(S.tt)
    if b == wd.GRID and kind not in HAZ_HW:
        kind = "fast"            # in the void, light-cycles simply blast past
    ev = Trip()
    ev.k = kind
    ev.trig = False
    ev.passed = False
    ev.t0 = S.clk
    ev.trail = 0                 # 1 for a light-cycle (it leaves a light-wall)
    ev.te = None                 # when the light-wall stopped being laid
    jit = 0.88 + random.random() * 0.24
    if kind in HAZ_HW:
        ev.lane = S.lane_tgt
        ev.x = 138.0
        ev.hw = HAZ_HW[kind]
        ev.rest = 28 + random.random() * 27
    else:
        if b == wd.GRID:
            ev.vk = "cycle"
            ev.trail = 1
            ev.v = REL_CYCLE * jit
            ev.rest = 28 + random.random() * 25
        else:
            if kind == "slow" and b == wd.FARM:
                ev.vk = "tractor"
            elif kind == "slow":
                ev.vk = "truck" if random.random() < 0.5 else "sedan"
            else:
                ev.vk = "sedan"
            ev.v = (REL_SLOW[ev.vk] if kind == "slow" else REL_FAST) * jit
            ev.rest = 65 + random.random() * 45
        ev.vw = VEH[ev.vk][0][2]
        if kind == "slow":
            ev.lane = S.lane_tgt
            ev.x = 134.0
        else:
            ev.lane = 1 - S.lane_tgt
            ev.x = -float(ev.vw) - 4
        ev.x0 = ev.x
    S.ev = ev


def step_events(dt):
    ev = S.ev
    if ev is None:
        if (S.clk >= S.next_ev and S.clk - S.mv_t0 > LANE_MOVE + 0.5
                and S.tt < wd.TRIP - 45                  # keep the road clear for the gas stop
                and S.tun is None                        # ...and for the tunnel
                and (S.tun_done or S.tt < wd.TUN_AT[0] - 1.0)):
            spawn()
        elif S.lane_tgt != 0 and S.clk - S.free_since > 1.5:
            set_lane(0)   # back to the home lane once the road is clear
        return
    k = ev.k
    nose = CAR_X + 32 + LANE_DX * S.lane_f
    if k in HAZ_HW:
        ev.x -= wd.ROAD_SPEED * dt
        if not ev.trig and ev.lane == S.lane_tgt and ev.x - ev.hw <= nose + 44:
            ev.trig = True
            set_lane(1 - ev.lane)
        if ev.x + ev.hw < CAR_X - 8 and not ev.passed:
            ev.passed = True
            ev.pt = S.clk
        if ev.x + ev.hw < -4:
            finish()
    elif k == "slow":
        ev.x += ev.v * dt        # v is negative: it drifts back past us
        # the faster we close in, the earlier we have to start the lane change
        if not ev.trig and ev.lane == S.lane_tgt and ev.x <= nose + 16 - 1.35 * ev.v:
            ev.trig = True
            set_lane(1 - ev.lane)
        if ev.x + ev.vw < CAR_X - 4 and not ev.passed:
            ev.passed = True
            ev.pt = S.clk
        if ev.x + ev.vw < -6:
            finish()
    else:
        ev.x += ev.v * dt
        if ev.trail:             # a light-cycle: stay until its light-wall has faded
            if ev.te is None and ev.x > W + 8:
                ev.te = S.clk
            if ev.te is not None and S.clk - ev.te > TRAIL_FADE:
                finish()
        elif ev.x > W + 8:
            finish()
    if S.ev is not None and ev.passed and S.lane_tgt != 0 and S.clk - ev.pt > 1.0:
        set_lane(0)   # the hazard is behind us: head back to the home lane


def finish():
    ev = S.ev
    S.next_ev = S.clk + ev.rest
    S.ev = None
    S.free_since = S.clk
    if S.lane_tgt != 0:
        S.free_since = S.clk - 1.0   # head home promptly


# -------------------------------------------------------------- drawing ----
def vehicle_pos(ev):
    spr, hh, ground = VEH[ev.vk]
    lane = ev.lane
    xmid = ev.x + spr[2] / 2
    bottom = CAR_BOTTOM - LANE_DY * lane + int((xmid - (CAR_X + 14)) * SLOPE)
    return int(ev.x) + LANE_DX * lane, bottom - ground, bottom


def draw_trail(ev):
    """The light-wall a light-cycle lays down. It is part of the road: it scrolls
    away with it, and the older it gets the more it dissolves."""
    now = S.clk
    T = now - ev.t0                        # time since the cycle appeared
    Te = (ev.te - ev.t0) if ev.te is not None else T   # it laid light from 0 to Te
    k = 1.0 / (ev.v + wd.ROAD_SPEED)       # inverse of the cycle's speed over the ground
    a0 = ev.x0 + LANE_DX * ev.lane + 3     # screen x of the wall's very first point
    lane_y = CAR_BOTTOM - LANE_DY * ev.lane
    xm = ev.vw // 2 - 3 - LANE_DX * ev.lane - (CAR_X + 14)
    gph = int(now * wd.ROAD_SPEED)
    for x in range(W):
        u = (x - a0 + wd.ROAD_SPEED * T) * k    # when was this bit of wall laid?
        if u < 0 or u > Te:
            continue
        lvl = int(8 * (1 - (T - u) / TRAIL_FADE))
        if lvl <= 0:
            continue
        wx = x + gph                       # fixed to the road, so the dither sticks
        yb = lane_y + int((x + xm) * SLOPE)
        if ((wx * 5) & 7) < lvl:
            px(x, yb)                      # foot of the wall
        if lvl >= 2 and ((wx * 3 + 1) & 7) < lvl - 1:
            px(x, yb - 4)                  # top edge
        if lvl >= 5:
            if wx & 1 == 0:
                vline(x, yb - 3, yb - 1)   # fresh: a solid wall of light
            elif lvl >= 7:
                px(x, yb - 2)
        elif lvl >= 3 and wx & 3 == 0:
            vline(x, yb - 3, yb - 1)


def draw_vehicle(ev):
    vx, vy, vbottom = vehicle_pos(ev)
    cyc = ev.vk == "cycle"
    blit(VEH[ev.vk][0], vx, vy, True, cyc)
    return vbottom


def draw_puddle(ev):
    cx = int(ev.x)
    cy = gy(PUDDLE_REF[ev.lane], cx)
    flick = int(S.clk * 6) & 1
    hline(cx - 3, cy - 2, 7)
    px(cx - 6, cy - 1)
    px(cx + 6, cy - 1)
    px(cx - 5, cy - 1)
    px(cx + 5, cy - 1)
    px(cx - 7, cy)
    px(cx + 7, cy)
    px(cx - 6, cy)
    px(cx + 6, cy)
    px(cx - 6, cy + 1)
    px(cx + 6, cy + 1)
    px(cx - 5, cy + 1)
    px(cx + 5, cy + 1)
    hline(cx - 4, cy + 2, 9)
    for k in range(-4, 5):
        if (k + flick) & 1 == 0:
            px(cx + k, cy)
    px(cx - 2 + flick * 4, cy - 1)


def draw_snake(ev):
    age = S.clk - ev.t0
    cx = ev.x
    base_y = gy(PUDDLE_REF[ev.lane], int(cx))
    creep = age * 1.3
    for k in range(13):
        ox = 2.0 * math.sin(k * 0.8 - age * 9)
        x = int(cx + ox - k * 0.45 + 2)
        y = int(base_y - 5 + k * 0.85 + creep * 0.4)
        px(x, y)
        if k > 9:
            px(x + 1, y)
    hx = int(cx + 2 + 2.0 * math.sin(-age * 9))
    hy = int(base_y - 6 + creep * 0.4)
    hline(hx - 1, hy, 3)
    hline(hx - 1, hy - 1, 3)
    if int(S.clk * 5) & 1:
        px(hx - 2, hy - 2)   # flicking tongue


def draw_rock(ev):
    x = int(ev.x) - 4
    ry = gy(PUDDLE_REF[ev.lane], int(ev.x)) + 2
    hline(x + 1, ry - 4, 6)
    hline(x, ry - 3, 8)
    hline(x, ry - 2, 9)
    hline(x, ry - 1, 9)
    hline(x + 1, ry, 8)
    for k in range(0, 8, 2):    # shading on the lower-right
        hline(x + 2 + k % 3, ry - 2 + (k // 4), 1, False)
    px(x + 2, ry - 3)
    hline(x + 5, ry - 1, 3, False)


def draw_car():
    f = S.lane_f
    sx = CAR_X + int(LANE_DX * f + 0.5)
    sy = CAR_BOTTOM - (CAR_H - 1) - int(LANE_DY * f + 0.5)
    for xx in range(1, 29, 2):
        px(sx + xx, sy + 12)
    blit(CAR, sx, sy, True, wd.biome_at(S.tt + 2.4) == wd.GRID)
    spin = int(S.clk * 14) & 7
    for wx, wy in WHEELS:
        for j in (spin, (spin + 4) & 7):
            ox, oy = RING[j]
            hline(sx + wx + ox, sy + wy + oy, 1, False)
    frame = int(S.clk * 20)
    for k in range(1, 9):
        if (k + frame) % 2 == 0:
            px(sx + 31 + k, sy + 5 + int(k * 0.12))
    for k in range(3):
        d = (S.clk * 16 + k * 5) % 14
        px(sx - 1 - int(d), sy + 7 - int(d / 6))
    return sy + CAR_H - 1


def render_road(dt):
    wd.draw_scene(S.tt, S.clk, S.wk, S.wi)
    ev = S.ev
    if ev is not None:
        if ev.k == "puddle":
            draw_puddle(ev)
        elif ev.k == "snake":
            draw_snake(ev)
        elif ev.k == "rock":
            draw_rock(ev)
        elif ev.trail:
            draw_trail(ev)
    if ev is not None and ev.k in ("slow", "fast"):
        vbottom = vehicle_pos(ev)[2]
        cbottom = CAR_BOTTOM - int(LANE_DY * S.lane_f + 0.5)
        if vbottom < cbottom:
            draw_vehicle(ev)
            draw_car()
        else:
            draw_car()
            draw_vehicle(ev)
    else:
        draw_car()
    if S.tun is not None:
        tunnel.draw_mass(int(S.tun.x))
    wd.draw_weather(S.wk, S.wi, dt, S.clk)


def render(dt):
    clear()
    cut = S.cut
    if cut is not None and cut.mod.on_stage(cut):
        cut.mod.draw(cut, S.clk)
    else:
        render_road(dt)
    if cut is not None:
        gas.dim(cut.mod.blank(cut.t))              # fading out of / into a cut-scene
    elif S.cut_fin > 0:
        gas.dim(S.cut_fin / gas.FADE)              # fading back into the road


def step_tunnel(dt):
    """Approach -> car hidden for 2 s -> cut-scene -> car comes out of the far end."""
    t = S.tun
    if t is None:
        if (not S.tun_done and S.tt >= wd.TUN_AT[0] and S.ev is None
                and S.lane_tgt == 0 and S.lane_f == 0.0):
            t = S.tun = Trip()
            t.x = float(W + 12)      # left end of the mountain, screen x
            t.ph = 0
            t.th = 0.0
        return
    if t.ph == 2:
        return
    t.x -= wd.ROAD_SPEED * dt
    if t.ph == 0:
        if t.x <= CAR_X - 8:         # the car is completely inside the rock
            t.ph = 1
            t.th = 0.0
    elif t.ph == 1:
        t.th += dt
        if t.th >= 2.0:              # ...for a full 2 seconds: now the drive
            t.ph = 2
            begin_cut(tunnel, S.car_i)
    elif t.x + tunnel.LEN + 8 < 0:   # the far portal has rolled off the left
        S.tun = None
        S.next_ev = S.clk + 6.0


def end_tunnel():
    S.cut = None
    S.cut_fin = gas.FADE
    S.tun_done = True
    S.tun.ph = 3                     # back on the road, the far portal on the left half
    S.tun.x = float(tunnel.EXIT_XR - tunnel.LEN)
    S.free_since = S.clk


def new_trip(first):
    """The cut-scene is over: clean road, fresh weather, and (after the first
    gas stop) the next car from the garage."""
    S.cut = None
    S.cut_fin = gas.FADE
    S.tt = 0.0
    S.ev = None
    S.tun = None
    S.tun_done = False
    S.lane_tgt = 0
    S.lane_f = 0.0
    S.mv_from = 0.0
    S.mv_t0 = -10.0
    S.next_ev = S.clk + 25.0
    S.free_since = S.clk
    if not first:
        set_car((S.car_i + 1) % len(GARAGE))
    wd.build_weather()
    S.wk, S.wi = wd.weather_at(S.tt)


def step(dt):
    S.clk += dt
    cut = S.cut
    if cut is not None:
        m = cut.mod
        was = cut.t
        m.advance(cut, dt)
        if was < m.FADE:          # the road keeps rolling while it fades out
            S.tt = min(S.tt + dt, wd.TRIP - 0.001)
            S.wk, S.wi = wd.weather_at(S.tt)
            update_lane()
            step_events(dt)
        elif cut.t >= m.T_END:    # the cut-scene is over
            if m is gas:
                new_trip(cut.first)   # all fuelled up: off we go
            else:
                end_tunnel()          # out the other side of the mountain
        return
    if S.cut_fin > 0:
        S.cut_fin -= dt
    S.tt += dt
    S.wk, S.wi = wd.weather_at(S.tt)
    update_lane()
    step_events(dt)
    step_tunnel(dt)
    if S.tt >= wd.TRIP - gas.FADE:     # end of the road: back to the gas station
        begin_cut(gas)


def run():
    wd.build_weather()
    set_car(0)
    begin_cut(gas, True)          # the trip opens at the gas station
    last = time.monotonic()
    while True:
        now = time.monotonic()
        dt = now - last
        last = now
        if dt > MAX_DT:    # slow frame: the car just seems to slow down
            dt = MAX_DT
        step(dt)
        render(dt)
        show()


if __name__ == "__main__":
    run()
