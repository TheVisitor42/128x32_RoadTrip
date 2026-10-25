# world.py - scenery for the road-trip demo: six biomes, parallax layers, weather
import math
import random

from gfx import (W, H, buf, px, hline, vline, line, gy, G, BASE, FAR_CURB,
                 DIV, NEAR_CURB, make_sprite, blit)

# ------------------------------------------------------------- the trip ----
CITY, DESERT, FARM, MOUNT, FOREST, METRO, GRID = range(7)
NB = 7
# Every run starts at the gas station in the desert (see gas.py), then drives this
# route in order; after the last stretch it is back to the gas station and the next
# car. Reorder ORDER to change the route (every biome must appear once).
ORDER = (DESERT, FARM, MOUNT, FOREST, METRO, GRID, CITY)
BIOME_LEN = (200.0, 200.0, 200.0, 200.0, 200.0, 200.0, 150.0)   # seconds, by biome
BLENS = tuple(BIOME_LEN[b] for b in ORDER)      # seconds of each leg of the route
_bs = []
_t = 0.0
for _l in BLENS:
    _bs.append(_t)
    _t += _l
BSTART = tuple(_bs)          # when each leg starts
TRIP = _t                    # 22.5 minutes of road, then the gas station again

ROAD_SPEED = 70              # px/s the road surface scrolls
V_FAR = 8                    # px/s skyline / mountains
V_GND = 22                   # px/s ground strip behind the road
V_SIDE = 56                  # px/s roadside objects (palms, cacti, trees...)

FARY = [int(FAR_CURB + g + 0.5) for g in G]
NEARY = [int(NEAR_CURB + g + 0.5) for g in G]
DIVY = [int(DIV + g + 0.5) for g in G]


def rnd(i):
    i &= 0xFFF
    return ((i * 1103 + 12345) * 75 + (i >> 1) * 331 + 17) & 0xFFFF


def slot_at(tt):
    """Which leg of the route (index into ORDER) we are on."""
    s = 0
    for i in range(NB):
        if tt >= BSTART[i]:
            s = i
    return s


def biome_at(tt):
    return ORDER[slot_at(tt)]


def segments(tt, v):
    """Biome segments visible on a layer scrolling at v px/s.
    Returns ((biome, x_from, x_to, offset), ...). Distant (slow) layers show
    the next biome earlier, like real scenery coming over the horizon."""
    s = slot_at(tt)
    tr = tt - BSTART[s]
    xb = int((BLENS[s] - tr) * v)
    if xb >= W:
        return ((ORDER[s], 0, W, tr * v),)
    if xb < 0:
        xb = 0
    return ((ORDER[s], 0, xb, tr * v), (ORDER[(s + 1) % NB], xb, W, (tr - BLENS[s]) * v))


def items(xa, xb, off, sp, margin):
    """Yield (n, screen_x) for items spaced ~sp px (with jitter) in [xa, xb)."""
    o = int(off)
    n0 = (xa + o - margin - sp) // sp
    n1 = (xb + o + margin) // sp + 1
    jit = sp // 2 + 1
    for n in range(n0, n1 + 1):
        x = n * sp + rnd(n) % jit - o
        if xa <= x < xb:
            yield n, x


# ------------------------------------------- far layer: skyline, mountains ----
def _mk(P):
    return [0] * P, [0] * P, [0] * P, [0] * P


def _bits(a, P, c, r0, r1):
    """Set rows r0..r1 (inclusive) in column c of mask array a."""
    if r1 < 0 or r0 > 15 or r1 < r0:
        return
    if r0 < 0:
        r0 = 0
    if r1 > 15:
        r1 = 15
    a[c % P] |= ((1 << (r1 + 1)) - 1) ^ ((1 << r0) - 1)


def build_buildings(blds, depth, wc, wr):
    """Iso buildings: lit front with windows, checkered right side, white roof."""
    P = 0
    for w, h in blds:
        P += w + depth
    clr, solid, wa, wb = _mk(P)
    start = 0
    for bi in range(len(blds)):
        w, h = blds[bi]
        top = BASE - h
        for c in range(w + depth):
            col = start + c
            if c < w:
                r0 = top - min(depth, c)
                _bits(clr, P, col, r0, BASE)
                _bits(solid, P, col, r0, top)
                if c == 0 or c == w - 1:
                    _bits(solid, P, col, top, BASE)
            else:
                j = c - w + 1
                _bits(clr, P, col, top - depth, BASE - j)
                _bits(solid, P, col, top - depth, top - j)
                for r in range(top - j + 1, BASE - j + 1):
                    if (col + r) & 1 == 0:
                        _bits(solid, P, col, r, r)
                _bits(solid, P, col, BASE - j, BASE - j)
                if j == depth:
                    _bits(solid, P, col, top - depth, BASE - j)
        ci = 0
        for c in range(2, w - 2, wc):
            ri = 0
            for r in range(top + 2, BASE - 1, wr):
                kind = (bi * 5 + ci * 3 + ri * 7) % 3
                arr = solid if kind == 0 else wa if kind == 1 else wb
                _bits(arr, P, start + c, r, r)
                ri += 1
            ci += 1
        start += w + depth
    for c in range(P):
        solid[c] |= 1 << BASE
    return P, clr, solid, wa, wb


def _profile(P, tops):
    """Silhouette from a list of top rows; returns the four mask arrays."""
    clr, solid, wa, wb = _mk(P)
    for c in range(P):
        t = tops[c]
        _bits(clr, P, c, t, BASE)
        _bits(solid, P, c, t, t)
        tp = tops[c - 1]
        if t - tp > 1:
            _bits(solid, P, c, tp, t)
        elif tp - t > 1:
            _bits(solid, P, c, t, tp)
    for c in range(P):
        solid[c] |= 1 << BASE
    return clr, solid, wa, wb


def build_desert():
    P = 320
    tops = [BASE - 1 - int(1.2 * math.sin(c * 0.11) + 1.2) for c in range(P)]
    for cx, pw, sw, h in ((40, 9, 8, 7), (130, 5, 7, 5), (215, 12, 9, 8), (285, 4, 6, 4)):
        for c in range(P):
            d = abs(((c - cx + P // 2) % P) - P // 2)
            if d <= pw:
                hh = h
            elif d <= pw + sw:
                hh = h * (pw + sw - d) // sw
            else:
                hh = 0
            if BASE - hh < tops[c]:
                tops[c] = BASE - hh
    clr, solid, wa, wb = _profile(P, tops)
    for c in range(P):  # rock strata
        if BASE - tops[c] >= 5 and c & 1:
            _bits(solid, P, c, tops[c] + 2, tops[c] + 2)
            if BASE - tops[c] >= 7:
                _bits(solid, P, c, tops[c] + 4, tops[c] + 4)
    return P, clr, solid, wa, wb


def build_farm():
    P = 360
    tops = [BASE - 2 - int(1.4 * math.sin(c * 0.06) + 1.4 + 0.8 * math.sin(c * 0.17)) for c in range(P)]
    clr, solid, wa, wb = _profile(P, tops)
    # barn + silo
    x0 = 40
    for c in range(11):
        _bits(clr, P, x0 + c, BASE - 10, BASE)
        if c in (0, 10):
            _bits(solid, P, x0 + c, BASE - 5, BASE)
    for k in range(6):
        _bits(solid, P, x0 + 5 - k, BASE - 10 + k, BASE - 10 + k)
        _bits(solid, P, x0 + 5 + k, BASE - 10 + k, BASE - 10 + k)
    for c in range(4, 7):
        _bits(solid, P, x0 + c, BASE - 4, BASE - 4)
    _bits(solid, P, x0 + 4, BASE - 4, BASE)
    _bits(solid, P, x0 + 6, BASE - 4, BASE)
    _bits(solid, P, x0 + 5, BASE - 2, BASE - 2)
    x1 = x0 + 13
    for c in range(4):
        _bits(clr, P, x1 + c, BASE - 11, BASE)
        if c in (0, 3):
            _bits(solid, P, x1 + c, BASE - 9, BASE)
        else:
            _bits(solid, P, x1 + c, BASE - 10, BASE - 10)
        _bits(solid, P, x1 + c, BASE - 6, BASE - 6)
        _bits(solid, P, x1 + c, BASE - 3, BASE - 3)
    # farmhouse
    x2 = 200
    for c in range(9):
        _bits(clr, P, x2 + c, BASE - 9, BASE)
        if c in (0, 8):
            _bits(solid, P, x2 + c, BASE - 4, BASE)
    for k in range(5):
        _bits(solid, P, x2 + 4 - k, BASE - 8 + k, BASE - 8 + k)
        _bits(solid, P, x2 + 4 + k, BASE - 8 + k, BASE - 8 + k)
    _bits(solid, P, x2 + 6, BASE - 9, BASE - 6)   # chimney
    for r in (BASE - 3,):
        _bits(wa, P, x2 + 2, r, r)
        _bits(solid, P, x2 + 6, r, r)
    for c in range(P):
        solid[c] |= 1 << BASE
    return P, clr, solid, wa, wb


def build_mount():
    P = 400
    tops = [BASE for _ in range(P)]
    peaks = ((45, 34, 11), (120, 26, 8), (190, 38, 11), (265, 28, 9), (335, 34, 10))
    snow = [0] * P
    for cx, hw, h in peaks:
        for c in range(P):
            d = abs(((c - cx + P // 2) % P) - P // 2)
            if d < hw:
                t = BASE - h + (d * h) // hw + (rnd(c) & 1)
                if t < tops[c]:
                    tops[c] = t
                cap = 4 - (d * 8) // hw
                if cap > snow[c] and h >= 8:
                    snow[c] = cap
    clr, solid, wa, wb = _profile(P, tops)
    for c in range(P):
        if snow[c] > 0:
            _bits(solid, P, c, tops[c], tops[c] + snow[c] - 1 - (c & 1))
    for c in range(P):  # shaded face on the right of each peak
        if BASE - tops[c] >= 5 and (c % 7) in (2, 4):
            _bits(solid, P, c, tops[c] + 4, tops[c] + 6)
    return P, clr, solid, wa, wb


def build_forest():
    P = 280
    clr, solid, wa, wb = _mk(P)
    n = 0
    x = 2
    while x < P:
        ht = 5 + rnd(n) % 5
        for r in range(ht):
            y = BASE - ht + r
            hw = (r + 1) // 2
            _bits(clr, P, x - hw, y, y)
            _bits(clr, P, x + hw, y, y)
            _bits(solid, P, x - hw, y, y)
            _bits(solid, P, x + hw, y, y)
            for c in range(x - hw, x + hw + 1):
                _bits(clr, P, c, y, y)
        _bits(solid, P, x, BASE - 1, BASE)
        x += 5 + rnd(n + 50) % 3
        n += 1
    for c in range(P):
        solid[c] |= 1 << BASE
    return P, clr, solid, wa, wb


def _aline(arr, P, x0, y0, x1, y1):
    dx, dy = abs(x1 - x0), -abs(y1 - y0)
    sx = 1 if x0 < x1 else -1
    sy = 1 if y0 < y1 else -1
    err = dx + dy
    while True:
        _bits(arr, P, x0, y0, y0)
        if x0 == x1 and y0 == y1:
            return
        e2 = 2 * err
        if e2 >= dy:
            err += dy
            x0 += sx
        if e2 <= dx:
            err += dx
            y0 += sy


def build_grid():
    """Tron-style void: striped retro sun, wireframe pyramids, cubes, obelisks."""
    P = 420
    clr, solid, wa, wb = _mk(P)
    cx = 150
    for dx in range(-9, 10):                     # retro sun with slits
        h = int(math.sqrt(81 - dx * dx) + 0.5)
        c = cx + dx
        _bits(clr, P, c, BASE - h, BASE - 1)
        _bits(solid, P, c, BASE - h, BASE - 1)
        for r in (BASE - 1, BASE - 2, BASE - 4, BASE - 6):
            solid[c % P] &= ~(1 << r) & 0xFFFF
    for pc, h, hw in ((40, 8, 10), (250, 6, 8), (340, 9, 11)):   # pyramids
        for dx in range(-hw, hw + 1):
            _bits(clr, P, pc + dx, BASE - h + abs(dx) * h // hw, BASE)
        _aline(solid, P, pc, BASE - h, pc - hw, BASE)
        _aline(solid, P, pc, BASE - h, pc + hw, BASE)
        _aline(solid, P, pc, BASE - h, pc + hw // 3, BASE)
    for qx, qy in ((95, 4), (300, 4), (395, 5)):                 # floating cubes
        s = 5
        for c in range(qx, qx + s + 4):
            _bits(clr, P, c, qy - 3, qy + s)
        for ox, oy in ((0, 0), (3, -3)):
            _aline(solid, P, qx + ox, qy + oy, qx + ox + s, qy + oy)
            _aline(solid, P, qx + ox + s, qy + oy, qx + ox + s, qy + oy + s)
            _aline(solid, P, qx + ox + s, qy + oy + s, qx + ox, qy + oy + s)
            _aline(solid, P, qx + ox, qy + oy + s, qx + ox, qy + oy)
        for ex, ey in ((0, 0), (s, 0), (s, s), (0, s)):
            _aline(solid, P, qx + ex, qy + ey, qx + ex + 3, qy + ey - 3)
    for oc, h in ((205, 10), (375, 7)):                          # obelisks
        t = BASE - h
        for c in range(oc, oc + 6):
            _bits(clr, P, c, t, BASE)
        _aline(solid, P, oc, t + 2, oc, BASE)
        _aline(solid, P, oc + 3, t + 2, oc + 3, BASE)
        _aline(solid, P, oc, t + 2, oc + 1, t)
        _aline(solid, P, oc + 3, t + 2, oc + 2, t)
        _aline(solid, P, oc + 1, t, oc + 2, t)
        _aline(solid, P, oc + 3, t + 2, oc + 5, t + 1)
        _aline(solid, P, oc + 5, t + 1, oc + 5, BASE - 2)
        _aline(solid, P, oc + 3, BASE, oc + 5, BASE - 2)
    for c in range(P):
        solid[c] |= 1 << BASE
    return P, clr, solid, wa, wb


def build_all():
    city = build_buildings(((8, 7), (6, 5), (8, 8), (7, 6), (8, 7), (6, 8), (8, 5), (8, 8)), 3, 3, 2)
    metro = build_buildings(((7, 9), (6, 7), (8, 10), (6, 8), (7, 10), (8, 9), (6, 7), (7, 10), (9, 8)), 2, 2, 2)
    return (city, build_desert(), build_farm(), build_mount(), build_forest(), metro, build_grid())


FAR = build_all()


def draw_far(tt, clk):
    flick = int(clk / 0.9) & 1
    for b, xa, xb, off in segments(tt, V_FAR):
        P, clr, solid, wa, wb = FAR[b]
        fl = wa if flick else wb
        o = int(off)
        for x in range(xa, xb):
            i = (x + o) % P
            cm = clr[i]
            dm = solid[i] | fl[i]
            buf[x] = (buf[x] & ~cm & 0xFF) | (dm & 0xFF)
            buf[W + x] = (buf[W + x] & ~(cm >> 8) & 0xFF) | (dm >> 8)


def draw_far_at(b, off, clk):
    """One biome's far layer across the whole screen at a fixed offset (cut-scenes)."""
    P, clr, solid, wa, wb = FAR[b]
    fl = wa if int(clk / 0.9) & 1 else wb
    for x in range(W):
        i = (x + off) % P
        cm = clr[i]
        dm = solid[i] | fl[i]
        buf[x] = (buf[x] & ~cm & 0xFF) | (dm & 0xFF)
        buf[W + x] = (buf[W + x] & ~(cm >> 8) & 0xFF) | (dm >> 8)


# ------------------------------------------------------------------- sky ----
STARS = ((5, 1), (19, 4), (33, 0), (47, 2), (58, 6), (71, 1), (84, 3),
         (96, 0), (109, 2), (121, 5), (14, 7), (66, 5))
CLOUD = ((4, 0, 3), (2, 1, 6), (9, 1, 2), (1, 2, 11), (0, 3, 13), (1, 4, 11))
CLOUDS = ((6, 0, 0), (10, 70, 4))
CLOUDS_WET = ((5, 0, 0), (8, 40, 3), (11, 85, 0), (7, 130, 5))


# Stars shine steadily. Every 5-15 s ONE random star twinkles: it blinks out,
# flares into a little cross, blinks again, and settles.
_tw = [8.0, 0, -10.0]        # [time of the next twinkle, which star, when it began]


def draw_stars(clk, drift):
    if clk >= _tw[0]:
        _tw[1] = random.randint(0, len(STARS) - 1)
        _tw[2] = clk
        _tw[0] = clk + 5 + random.random() * 10
    ph = clk - _tw[2]
    for i in range(len(STARS)):
        sx, sy = STARS[i]
        x = (sx - drift) % W
        if i == _tw[1] and ph < 0.45:
            if ph < 0.12 or 0.30 <= ph < 0.38:
                continue
            if ph < 0.30:
                px(x - 1, sy)
                px(x + 1, sy)
                px(x, sy - 1)
                px(x, sy + 1)
        px(x, sy)


# One shooting star per trip: [trip time, start x, start y]. It lives in the sky,
# the farthest layer of all, so the skyline and mountains pass in front of it.
SHOOT = [-1.0, 100.0, 0.0]
SHOOT_VX, SHOOT_VY = -240.0, 13.0     # px/s: it crosses the sky in ~half a second
SHOOT_LEN = 0.6


def draw_shoot(tt):
    p = tt - SHOOT[0]
    if SHOOT[0] < 0 or p < 0 or p > SHOOT_LEN:
        return
    hx = SHOOT[1] + SHOOT_VX * p
    hy = SHOOT[2] + SHOOT_VY * p
    for k in range(12):
        if k > 4 and k & 1:
            continue                       # the tail breaks up as it fades
        x = int(hx + k * 0.998 + 0.5)
        y = int(hy - k * 0.054 + 0.5)
        if 0 <= x < W and y < BASE - 1:    # stays above the skyline
            px(x, y)
            if k == 0:
                px(x, y + 1)


# One UFO per trip, somewhere in the desert: it drops out of the sky, hovers back and
# forth with a flickering beam, then zips straight back up and out of frame. Like the
# shooting star it lives in the sky layer, so the mesas pass in front of it.
UFO = [-1.0, 64.0]            # [trip time it arrives, centre column of its hover]
UFO_D, UFO_H, UFO_R = 2.6, 10.0, 2.0     # seconds: descend, hover, rise away
UFO_SWAY = 26.0               # px it drifts either side of centre
UFO_HOVER_Y = 3               # top row of the saucer while hovering
UFO_ROWS = (
    "     ###     ",
    "    #.:.#    ",
    "  #########  ",
    "#############",
    " ########### ",
    "    #####    ",
)


def draw_ufo(tt, clk):
    p = tt - UFO[0]
    if UFO[0] < 0 or p < 0 or p > UFO_D + UFO_H + UFO_R:
        return
    x0 = UFO[1]
    beam = False
    if p < UFO_D:                                      # coming down from above
        u = p / UFO_D
        x = x0
        y = -8 + 11 * u * u * (3 - 2 * u)
    elif p < UFO_D + UFO_H:                            # hovering back and forth
        q = p - UFO_D
        x = x0 + UFO_SWAY * math.sin(q * 1.25)
        y = UFO_HOVER_Y + 1.2 * math.sin(q * 2.3)
        beam = True
    else:                                              # away, straight up
        u = (p - UFO_D - UFO_H) / UFO_R
        x = x0 + UFO_SWAY * math.sin(UFO_H * 1.25)
        y = UFO_HOVER_Y - 14 * u * u
    ix = int(x + 0.5) - 6
    iy = int(y + 0.5)
    if iy + 5 < 0 or iy > BASE:
        return
    if beam and iy + 6 < BASE:                         # faint, flickering tractor beam
        fr = int(clk * 8)
        for k in range(BASE - iy - 6):
            hw = 2 + k
            for bx in range(ix + 6 - hw, ix + 7 + hw):
                if (bx + k) & 1 == 0 and (fr + k) & 3:
                    px(bx, iy + 6 + k)
    for r in range(-1, 7):                             # clear the stars behind it
        hline(ix - 1, iy + r, 15, False)
    for r in range(6):
        row = UFO_ROWS[r]
        for c in range(13):
            ch = row[c]
            if ch == "#":
                px(ix + c, iy + r)
            elif ch == ":":
                if c & 1:
                    px(ix + c, iy + r)
    ph = int(clk * 6)                                  # rim lights chase round
    for j in range(5):
        if (j + ph) % 3 != 0:
            hline(ix + 2 + 2 * j, iy + 3, 1, False)


def draw_sky(clk, wk, wi, tt):
    grid = []
    for b, xa, xb, off in segments(tt, V_FAR):
        if b == GRID:
            grid.append((xa, xb, int(off)))
    if not (wk == "rain" and wi > 0.3):
        draw_stars(clk, int(clk * 2))
        draw_shoot(tt)
        draw_ufo(tt, clk)
    for xa, xb, o in grid:      # a denser starfield over the void
        for n, x in items(xa, xb, o, 7, 4):
            px(x, rnd(n + 9) % 7)
    cl = CLOUDS_WET if wk else CLOUDS
    for speed, off, y in cl:
        x = W - (int(clk * speed) + off) % (W + 30)
        hidden = False
        for xa, xb, o in grid:  # no clouds in the void
            if xa <= x + 6 < xb:
                hidden = True
        if hidden:
            continue
        for dx, dy, w in CLOUD:
            hline(x + dx, y + dy, w)


# ---------------------------------------------------------- ground strip ----
BOAT = make_sprite((
    "    #    ",
    "    ##   ",
    "    ###  ",
    "    #### ",
    "    #####",
    "    #    ",
    "#########",
    " ####### ",
))


def g_city(xa, xb, o, t, wk, wi):
    for n, x in items(xa, xb, o, 12, 12):
        h = rnd(n)
        y = BASE + 3 + (h >> 4) % 10
        if y < FARY[x] - 3:
            px(x, y)
            px(x + 1, y)
            if h & 1:
                px(x + 2, y)
    d = int(t * 16)  # boats sail slowly against the passing water
    k0 = (o + xa - d - 112) // 360
    k1 = (o + xb - d - 88) // 360 + 1
    for k in range(k0, k1 + 1):
        bx = k * 360 + 100 - o + d
        if xa <= bx < xb:
            by = BASE + 1 + (1 if (int(t * 1.5) + k) & 1 else 0)
            if gy(FAR_CURB, bx + 4) - 3 > by + 8:
                blit(BOAT, bx, by, False)
                px(bx - 2, by + 8)
                px(bx - 5, by + 8)


def g_desert(xa, xb, o, t, wk, wi):
    for n, x in items(xa, xb, o, 9, 9):
        h = rnd(n)
        y = FARY[x] - 3 - h % 9
        if y > BASE + 1:
            px(x, y)
            if h & 2:
                px(x + 1, y)
            if h % 7 == 0:
                hline(x, y + 1, 3)
                px(x + 1, y)


def g_farm(xa, xb, o, t, wk, wi):
    s = xa + ((-(xa + o)) & 3)
    for x in range(s, xb, 4):
        yf = FARY[x]
        for d in (3, 6, 9, 12):
            y = yf - d
            if y > BASE + 1:
                px(x, y)


def g_mount(xa, xb, o, t, wk, wi):
    snowy = wk == "snow"
    for n, x in items(xa, xb, o, 14, 8):
        h = rnd(n)
        y = FARY[x] - 3 - h % 8
        if y > BASE + 1:
            if snowy or h & 1:
                hline(x, y, 3 + h % 3)
            else:
                px(x, y)
                px(x + 1, y)
                px(x, y - 1)


def g_forest(xa, xb, o, t, wk, wi):
    for n, x in items(xa, xb, o, 8, 6):
        h = rnd(n)
        y = FARY[x] - 3 - h % 9
        if y > BASE + 1:
            px(x, y)
            px(x - 1, y - 1)
            px(x + 1, y - 1)


def g_metro(xa, xb, o, t, wk, wi):
    s = xa + ((-(xa + o)) & 5)
    for x in range(s, xb, 6):
        yf = FARY[x]
        for d in (4, 8, 12):
            y = yf - d
            if y > BASE + 1:
                px(x, y)
                px(x + 1, y)


GRID_REFS = (13, 17, 21, 27, 33, 40, 48)


def g_grid(xa, xb, o, t, wk, wi):
    """Neon grid over the whole ground plane; the kerbs become bright double lines."""
    for yref in GRID_REFS:
        edge = yref == 21 or yref == 33
        thin = yref != 21 and yref != 27 and yref != 33
        for x in range(xa, xb):
            y = int(yref + G[x] + 0.5)
            if BASE < y < H:
                if thin and (x + yref) & 1:
                    continue
                px(x, y)
                if edge:
                    px(x, y + 1)
    off = int(t * ROAD_SPEED) % 20
    for x0 in range(-off, W + 24, 20):          # cross lines streaming past
        for y in range(BASE + 1, H):
            if y < 18 and y & 1:
                continue
            x = x0 - ((y - BASE - 1) * 5) // 8
            if xa <= x < xb:
                px(x, y)


GROUND = (g_city, g_desert, g_farm, g_mount, g_forest, g_metro, g_grid)


def draw_ground(tt, clk, wk, wi):
    for b, xa, xb, off in segments(tt, V_GND):
        GROUND[b](xa, xb, int(off), clk, wk, wi)


# ------------------------------------------------------- roadside objects ----
def palm(x, ry, h):
    for k in range(-4, 5, 2):
        px(x + k, ry + 1)
    tx = x
    for k in range(h):
        tx = x + (k * 3) // (h * 2)
        y = ry - k
        px(tx, y)
        if k & 1 == 0:
            px(tx + 1, y)
    cx, cy = tx, ry - h
    for dx, dy in ((-5, -3), (5, -3), (0, -5)):
        line(cx, cy, cx + dx, cy + dy, 2)
    for dx, dy in ((-7, 0), (7, 0)):
        line(cx, cy, cx + dx, cy + dy)
        line(cx + dx, cy + dy, cx + dx + (1 if dx > 0 else -1), cy + dy + 2)
    line(cx, cy, cx - 4, cy + 3)
    line(cx, cy, cx + 4, cy + 3)
    line(cx - 4, cy + 2, cx - 8, cy + 3)
    line(cx + 4, cy + 2, cx + 8, cy + 3)
    px(cx, cy + 1)
    px(cx + 1, cy + 1)


def cactus(x, ry, h, v):
    for k in range(-3, 4, 2):
        px(x + k, ry + 1)
    vline(x, ry - h, ry)
    for y in range(ry - h + 1, ry + 1):
        if y & 1:
            px(x + 1, y)
    px(x + 1, ry - h)
    if v & 1:
        yl = ry - (h * 5) // 9
        hline(x - 3, yl, 3)
        vline(x - 3, yl - 3, yl)
    if v & 2:
        yr = ry - (h * 2) // 5
        hline(x + 2, yr, 3)
        vline(x + 4, yr - 4, yr)


def rock(x, ry):
    hline(x, ry, 6)
    hline(x + 1, ry - 1, 4)
    px(x + 2, ry - 2)
    px(x + 3, ry - 2)
    px(x + 2, ry)
    px(x + 4, ry - 1)
    hline(x + 6, ry + 1, 3)


def pine(x, ry, h, snow):
    px(x, ry)
    px(x, ry - 1)
    yt = ry - 1 - h
    for r in range(h):
        y = yt + r
        hw = 1 + r // 2 + (1 if r % 4 == 3 else 0)
        if hw > 5:
            hw = 5
        px(x - hw, y)
        px(x + hw, y)
        for xx in range(x + 1, x + hw):
            if (xx + y) & 1:
                px(xx, y)
        if snow and r % 4 < 2:
            px(x - hw + 1, y)
            px(x, y)
    px(x, yt - 1)


def _lump(cx, cy, r):
    for dy in range(-r, r + 1):
        dx = int(math.sqrt(r * r - dy * dy) + 0.5)
        hline(cx - dx, cy + dy, 2 * dx + 1, False)
        px(cx - dx, cy + dy)
        px(cx + dx, cy + dy)
        if dy > -1:                      # shaded underside, lit from the upper left
            for xx in range(cx, cx + dx):
                if (xx + dy) & 1:
                    px(xx, cy + dy)


def leafy(x, ry, h, v=0):
    """Broadleaf tree: forked trunk and a canopy of overlapping lumps."""
    vline(x, ry - 5, ry)
    px(x + 1, ry)
    px(x - 1, ry + 1)
    px(x - 1, ry - 4)
    px(x + 1, ry - 5)
    cy = ry - h
    if v & 1:
        lumps = ((2, 0, 3), (-3, 1, 3), (0, -3, 3))
    elif v & 2:
        lumps = ((-3, 1, 2), (3, 1, 3), (0, -2, 3), (-1, -4, 2))
    else:
        lumps = ((-3, 1, 3), (3, 0, 2), (0, -2, 4))
    for ox, oy, r in lumps:
        _lump(x + ox, cy + oy, r)


def lamp(x, ry, wet):
    vline(x, ry - 13, ry)
    hline(x + 1, ry - 13, 3)
    px(x + 3, ry - 12)
    px(x + 2, ry - 11)
    px(x + 4, ry - 11)
    if wet:
        px(x + 1, ry - 10)
        px(x + 5, ry - 10)
        px(x + 3, ry - 9)
    px(x - 1, ry)
    px(x + 1, ry)


def windmill(x, ry, t):
    line(x - 3, ry, x, ry - 15)
    line(x + 3, ry, x, ry - 15)
    hline(x - 2, ry - 6, 5)
    hline(x - 1, ry - 10, 3)
    ang = t * 1.2
    for k in range(4):
        a = ang + k * 1.5708
        line(x, ry - 15, x + int(6 * math.cos(a)), ry - 15 + int(6 * math.sin(a)))


def s_city(xa, xb, o, t, wk, wi):
    for n, x in items(xa, xb, o, 50, 12):
        palm(x, FARY[x] - 2, 10 + rnd(n) % 4)


def s_desert(xa, xb, o, t, wk, wi):
    for n, x in items(xa, xb, o, 34, 8):
        h = rnd(n)
        ry = FARY[x] - 2
        if h % 5 == 3:
            rock(x, ry)
        else:
            cactus(x, ry, 8 + h % 5, (h >> 3) % 4)


def s_farm(xa, xb, o, t, wk, wi):
    s = xa + ((-(xa + o)) % 10)
    for x in range(s, xb, 10):
        y = FARY[x] - 2
        vline(x, y - 4, y)
    for x in range(xa + ((xa + o) & 1), xb, 2):
        px(x, FARY[x] - 5)
    for n, x in items(xa, xb, o, 120, 12):
        if rnd(n) % 3:
            leafy(x, FARY[x] - 2, 9 + rnd(n) % 3, rnd(n) >> 3)
    for n, x in items(xa, xb, o, 480, 12):
        windmill(x, FARY[x] - 2, t)


def s_mount(xa, xb, o, t, wk, wi):
    snow = wk == "snow" and wi > 0.2
    for n, x in items(xa, xb, o, 26, 10):
        pine(x, FARY[x] - 2, 11 + rnd(n) % 5, snow or rnd(n) & 1)


def s_forest(xa, xb, o, t, wk, wi):
    for n, x in items(xa, xb, o, 14, 8):
        h = rnd(n)
        ry = FARY[x] - 2
        if h % 3:
            pine(x, ry, 9 + h % 6, False)
        else:
            leafy(x, ry, 9 + h % 3, h >> 3)


def s_metro(xa, xb, o, t, wk, wi):
    for n, x in items(xa, xb, o, 44, 8):
        lamp(x, FARY[x] - 2, wk == "rain")


def s_grid(xa, xb, o, t, wk, wi):
    for n, x in items(xa, xb, o, 64, 8):
        ry = FARY[x] - 2
        for k in range(0, 15, 2):
            px(x, ry - k)
        px(x - 1, ry - 15)
        px(x + 1, ry - 15)
        px(x, ry - 16)
        px(x, ry - 14)
        if (int(t * 3) + n) & 1:
            px(x, ry - 15)
        for k in (-3, -1, 1, 3):
            px(x + k, ry + 1)


SIDE = (s_city, s_desert, s_farm, s_mount, s_forest, s_metro, s_grid)


def draw_side(tt, clk, wk, wi):
    for b, xa, xb, off in segments(tt, V_SIDE):
        SIDE[b](xa, xb, int(off), clk, wk, wi)


# ------------------------------------------------------------------ road ----
def draw_road(tt):
    for x in range(W):
        y = FARY[x]
        buf[(y >> 3) * W + x] |= 1 << (y & 7)
        y = NEARY[x]
        if y < H:
            buf[(y >> 3) * W + x] |= 1 << (y & 7)
    off = int(tt * ROAD_SPEED) % 20
    for x0 in range(-off, W, 20):
        for x in range(max(x0, 0), min(x0 + 9, W)):
            y = DIVY[x]
            if y < H:
                buf[(y >> 3) * W + x] |= 1 << (y & 7)
    off = int(tt * ROAD_SPEED * 1.4) % 16
    for x0 in range(-off, W, 16):
        if 0 <= x0 < W:
            y = NEARY[x0] + 2
            vline(x0, y, y + 1)


def draw_scene(tt, clk, wk, wi):
    draw_sky(clk, wk, wi, tt)
    draw_far(tt, clk)
    draw_ground(tt, clk, wk, wi)
    draw_road(tt)
    draw_side(tt, clk, wk, wi)


# --------------------------------------------------------------- weather ----
RULES = ((0.6, "rain"), (0.0, None), (0.55, "rain"), (0.9, "snow"),
         (0.6, "rain"), (0.45, "rain"), (0.0, None))
WEATHER = []


def _window(s, kind):
    """Add a weather spell inside leg s of the route."""
    ln = 45 + random.random() * 40
    t0 = BSTART[s] + 14 + random.random() * (BLENS[s] - 28 - ln)
    WEATHER.append((t0, t0 + ln, kind))


def build_weather():
    while WEATHER:
        WEATHER.pop()
    rain = False
    for s in range(NB):
        p, kind = RULES[ORDER[s]]
        if kind and random.random() < p:
            _window(s, kind)
            if kind == "rain":
                rain = True
    if not rain:   # every trip gets at least one rainy stretch
        wet = [ORDER.index(b) for b in (CITY, FARM, FOREST, METRO)]
        _window(wet[random.randint(0, 3)], "rain")
    _plan_ufo()
    _plan_shooting_star()
    _plan_tunnel()


# When the car dives into the mountain tunnel this trip (see tunnel.py): somewhere in
# the middle of the mountain stretch, so the whole thing fits inside it.
TUN_AT = [0.0]


def _plan_tunnel():
    m = ORDER.index(MOUNT)
    TUN_AT[0] = BSTART[m] + 40 + random.random() * (BLENS[m] - 100)


def _plan_ufo():
    """One visit per trip, in the desert, early enough to be over before it ends."""
    d = ORDER.index(DESERT)
    UFO[0] = BSTART[d] + 20 + random.random() * (BLENS[d] - 20 - (UFO_D + UFO_H + UFO_R) - 15)
    UFO[1] = 48 + random.random() * 34


def _plan_shooting_star():
    """Pick one random moment in the open-sky desert / farmland stretch (the other
    biomes have skylines that would hide it), in a clear spell."""
    first = ORDER.index(DESERT)
    t = BSTART[first] + 30.0
    for _ in range(30):
        t = BSTART[first] + 15 + random.random() * (BLENS[first] + BLENS[ORDER.index(FARM)] - 30)
        clash = UFO[0] - 2 < t < UFO[0] + UFO_D + UFO_H + UFO_R + 2   # keep the sky uncluttered
        if weather_at(t)[0] is None and weather_at(t + 1.0)[0] is None and not clash:
            break
    SHOOT[0] = t
    SHOOT[1] = 70 + random.random() * 55
    SHOOT[2] = random.random() * 3


def weather_at(tt):
    for t0, t1, kind in WEATHER:
        if t0 <= tt <= t1:
            i = min((tt - t0) / 6.0, (t1 - tt) / 6.0, 1.0)
            if i > 0:
                return kind, i
    return None, 0.0


RAIN_N, SNOW_N = 24, 26
_rx = [random.random() * (W + 30) for _ in range(RAIN_N)]
_ry = [random.random() * H for _ in range(RAIN_N)]
_sx = [random.random() * W for _ in range(SNOW_N)]
_sy = [random.random() * H for _ in range(SNOW_N)]


def draw_weather(wk, wi, dt, clk):
    if wk == "rain":
        for i in range(int(RAIN_N * wi)):
            x = _rx[i] - 26 * dt
            y = _ry[i] + 85 * dt
            if y > H or x < 0:
                x = random.random() * (W + 30)
                y = -random.random() * 8
            _rx[i] = x
            _ry[i] = y
            px(int(x), int(y))
            px(int(x) - 1, int(y) + 2)
        for i in range(int(3 * wi)):  # splashes on the road
            x = random.randint(0, W - 1)
            y = FARY[x] + random.randint(3, 11)
            px(x, y)
            px(x + 2, y)
    elif wk == "snow":
        for i in range(int(SNOW_N * wi)):
            x = _sx[i] + (-10 + 5 * math.sin(clk * 1.7 + i)) * dt
            y = _sy[i] + (12 + (i % 3) * 4) * dt
            if y > H or x < 0:
                x = random.random() * (W + 10)
                y = -random.random() * 6
            _sx[i] = x
            _sy[i] = y
            px(int(x), int(y))
            if i % 5 == 0:
                px(int(x) + 1, int(y))
