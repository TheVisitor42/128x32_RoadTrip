# tunnel.py - the mountain tunnel.
#  * draw_mass(): in the side view, a long rock mass with a concrete portal at each
#    end. The car drives into the left portal and vanishes; after the cut-scene it
#    comes back out of the right portal, now on the left half of the screen.
#  * the cut-scene (start/advance/draw): ~30 s from the driver's seat, speeding down
#    a gently curving tunnel with lamps, ribs and road markings streaming past.
import math

from gfx import W, H, px, hline, vline, line
import world as wd
import gas

LEN = 250            # length of the mountain, px (long enough to hide the car for 2 s)
EXIT_XR = 74         # where the mountain's far end sits when the car comes back out

FADE = gas.FADE
T_END = 31.2         # the picture is up from 0.6 s to 30.6 s: 30 s behind the wheel
T_GLARE = 24.0       # the daylight at the end of the tunnel starts to show


# ------------------------------------------------------------ side view ----
def _portal(x0, x1, post):
    """A concrete arch mouth over columns x0..x1: a white post at x=post, a lintel
    on top, and a black opening in between."""
    for x in range(x0, x1 + 1):
        if 0 <= x < W:
            if x == post:
                vline(x, 11, H - 1)
            else:
                vline(x, 13, H - 1, False)
                px(x, 12)
                if abs(x - post) > 1:
                    px(x, 11)


def draw_mass(xl):
    """The mountain from screen column xl to xl + LEN, covering everything below
    its ridge line, so whatever drives into it disappears."""
    xr = xl + LEN
    for x in range(max(xl, 0), min(xr, W)):
        u = x - xl
        p = 4.0 * u * (LEN - u) / (LEN * LEN)          # 0 at the ends, 1 mid-way
        top = 10 - int(6 * p) - (wd.rnd(u >> 2) & 1)   # a ragged dome
        vline(x, top, H - 1, False)                    # solid rock...
        px(x, top)                                     # ...with a ridge line
        for r in range(top + 3, H, 5):                 # strata
            if ((u * 5 + r * 3) & 7) < 5:
                px(x, r + ((u >> 4) & 1))
        if wd.rnd(u) & 7 == 0:                         # speckles
            px(x, top + 2 + wd.rnd(u + 5) % (H - top - 4))
        if u % 31 < 2:                                 # lamp light leaking out
            px(x, 17)
    _portal(xl - 7, xl - 1, xl - 7)                    # entrance
    _portal(xr, xr + 6, xr + 6)                        # exit


# ------------------------------------------------------------- the drive ----
F = 48.0             # focal length, px
CX = 64              # screen column of the straight-ahead point
HY0 = 15             # horizon row
EYE = 1.1            # eye height above the road, m
SP = 7.0             # rib spacing, m
ZS = (2.6, 4.0, 6.2, 9.6, 15.0, 23.0, 37.0, 60.0)    # nodes of the long lines
HOODS = ((3.0, 0), (4.5, 0), (3.0, 3))               # fender hump, centre scoop (by car)


class Cut:
    pass


def start(style=0):
    c = Cut()
    c.t = 0.0
    c.dist = 0.0
    c.v = 18.0
    c.style = style
    return c


def speed(t):
    u = (t - FADE) / 7.0
    u = 0.0 if u < 0 else 1.0 if u > 1 else u
    v = 18.0 + 24.0 * u * u * (3 - 2 * u)              # floor it
    return v + 3.0 * math.sin(t * 0.7)


def curve(t):
    """Sideways bend of the tunnel at distance z is curve * z * z (metres)."""
    env = 0.3 + t / 5.0
    if env > 1.0:
        env = 1.0
    if t > 24.0:                                       # straightens out for the exit
        env *= max(0.0, 1.0 - (t - 24.0) / 5.0)
    return 0.0055 * math.sin((t - 2.0) * 0.4) * env


def advance(c, dt):
    c.t += dt
    c.v = speed(c.t)
    c.dist += c.v * dt


def on_stage(c):
    return c.t >= FADE


def blank(t):
    if t < FADE:
        return t / FADE
    if t < 2 * FADE:
        return 1 - (t - FADE) / FADE
    if t > T_END - FADE:
        return (t - (T_END - FADE)) / FADE
    return 0.0


def _seg(x0, y0, x1, y1, step=1):
    if (max(x0, x1) < 0 or min(x0, x1) >= W or max(y0, y1) < 0
            or min(y0, y1) >= H or abs(x1 - x0) > 160 or abs(y1 - y0) > 160):
        return
    line(x0, y0, x1, y1, step)


def _poly(X, Y, K, cam, hy, step=1):
    """A long line down the tunnel (road edge, wall stripe...) bending with it."""
    px0 = py0 = None
    for z in ZS:
        s = F / z
        x = int(CX + (X + K * z * z - cam) * s + 0.5)
        y = int(hy - Y * s + 0.5)
        if px0 is not None:
            _seg(px0, py0, x, y, step)
        px0, py0 = x, y


def draw(c, clk):
    t = c.t
    K = curve(t)
    cam = 0.28 * math.sin(t * 0.8)                     # lane-drift sway
    hy = HY0 + (1 if int(clk * 17) % 13 == 0 else 0)   # the odd bump in the road

    # glare of the way out: a white sun growing at the far end of the tunnel
    if t > T_GLARE:
        g = (t - T_GLARE) / (T_END - FADE - T_GLARE)
        if g > 1.0:
            g = 1.0
        r = 1 + int(g * g * 60)
        gx = CX - int(cam * F / 60)
        for y in range(max(0, hy - r), min(H, hy + r + 1)):
            dy = (y - hy) / r
            hw = int(1.7 * r * math.sqrt(max(0.0, 1 - dy * dy)))
            hline(gx - hw, y, 2 * hw + 1)

    # ribs of the tube, with the lamps that stream past
    base = c.dist % SP
    for i in range(7):
        z = 2.0 + i * SP - base
        if z < 1.4:
            continue
        s = F / z
        d = K * z * z - cam
        xl = int(CX + (-4.0 + d) * s + 0.5)
        xr = int(CX + (4.0 + d) * s + 0.5)
        yb = int(hy + EYE * s + 0.5)
        yw = int(hy - 0.7 * s + 0.5)
        yc = int(hy - 1.6 * s + 0.5)
        xcl = int(CX + (-2.6 + d) * s + 0.5)
        xcr = int(CX + (2.6 + d) * s + 0.5)
        vline(xl, yw, yb)
        vline(xr, yw, yb)
        hline(xcl, yc, xcr - xcl + 1)
        _seg(xl, yw, xcl, yc)
        _seg(xr, yw, xcr, yc)
        lw = 1 + int(0.8 * s)                          # ceiling lamps, both sides
        lh = 1 + int(0.18 * s)
        for sx in (-2.0, 2.0):
            lx = int(CX + (sx + d) * s + 0.5) - lw // 2
            for k in range(lh):
                hline(lx, yc + 1 + k, lw)
        if i & 1:                                      # wall lamps on every other rib
            y0 = int(hy - 0.6 * s + 0.5)
            y1 = int(hy - 0.1 * s + 0.5)
            for wx in (xl + 1, xr - 2):
                vline(wx, y0, y1)
                if s > 6:
                    vline(wx + 1, y0, y1)

    # lines on the road and walls
    _poly(-3.2, -EYE, K, cam, hy)
    _poly(3.2, -EYE, K, cam, hy)
    _poly(-4.0, 0.45, K, cam, hy)
    _poly(4.0, 0.45, K, cam, hy)
    _poly(-2.6, 1.6, K, cam, hy, 2)
    _poly(2.6, 1.6, K, cam, hy, 2)
    per = 9.0                                          # dashed centre line
    off = c.dist % per
    for k in range(8):
        za = 2.8 + k * per - off
        zb = za + 3.5
        if zb < 2.8:
            continue
        if za < 2.8:
            za = 2.8
        if za > 60:
            break
        sa = F / za
        sb = F / zb
        xa = int(CX + (K * za * za - cam) * sa + 0.5)
        xb = int(CX + (K * zb * zb - cam) * sb + 0.5)
        ya = int(hy + EYE * sa + 0.5)
        yb2 = int(hy + EYE * sb + 0.5)
        _seg(xa, ya, xb, yb2)
        if sa > 9:
            _seg(xa + 1, ya, xb + 1, yb2)
    for j in range(14):                                # asphalt specks rushing by
        zj = 2.8 + ((wd.rnd(j * 7 + 3) % 380) / 10.0 - c.dist) % 38.0
        xj = ((wd.rnd(j * 7 + 9) % 76) - 38) / 10.0
        sj = F / zj
        qx = int(CX + (xj + K * zj * zj - cam) * sj + 0.5)
        qy = int(hy + EYE * sj + 0.5)
        px(qx, qy)
        if sj > 8:
            px(qx + 1, qy)

    # windscreen corners, bonnet, mirror, speedo
    for y in range(10):
        hline(0, y, 10 - y, False)
        px(10 - y, y)
        hline(W - 10 + y, y, 10 - y, False)
        px(W - 11 + y, y)
    hh, scoop = HOODS[c.style]
    for x in range(W):
        yh = 29
        for hx in (18, 110):
            dd = (x - hx) / 24.0
            if dd * dd < 1:
                yh -= int(hh * (1 - dd * dd))
        if scoop:
            dd = (x - 64) / 9.0
            if dd * dd < 1:
                yh -= int(scoop * (1 - dd * dd) + 0.5)
        vline(x, yh + 1, H - 1, False)
        px(x, yh)
    for y in range(0, 6):                              # rear-view mirror
        hline(57, y, 15, False)
    hline(57, 5, 15)
    vline(57, 0, 5)
    vline(71, 0, 5)
    for j in range(3):                                 # lamps receding behind us
        q = (c.dist / SP * 0.5 + j / 3.0) % 1.0
        o = int(5 * (1 - q))
        px(64 - o, 2 + (o > 2))
        px(64 + o, 2 + (o > 2))
    mph = int(c.v * 2.237)
    for y in range(0, 7):                              # black plate behind the speedo
        hline(102, y, 17, False)
    x = 105
    for ch in str(mph):
        x += gas.glyph(ch, x, 1) + 1
