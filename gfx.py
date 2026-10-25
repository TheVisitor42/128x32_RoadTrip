# gfx.py - display setup and low-level drawing for the road-trip demo
# Adafruit 2.23" 128x32 SSD1305 OLED on a Pico: SDA = GP4, SCL = GP5, addr 0x3C
import board
import busio
import adafruit_ssd1305

W, H = 128, 32
NBYTES = W * H // 8

i2c = busio.I2C(board.GP5, board.GP4, frequency=400000)
oled = adafruit_ssd1305.SSD1305_I2C(W, H, i2c, addr=0x3C)

buf = bytearray(NBYTES)  # our own 1-bit canvas, same layout as the display
BLANK = bytes(NBYTES)

# ---- road plane geometry (rows at screen column x = 64) ----
SLOPE = 0.113    # road tilt: rows per pixel, descending to the right
BASE = 11        # ground line of the far skyline
FAR_CURB, DIV, NEAR_CURB = 21, 27, 33
G = [(x - 64) * SLOPE for x in range(W)]


def gy(ref, x):
    """Screen row of a road-plane line at screen column x."""
    if x < 0:
        x = 0
    elif x >= W:
        x = W - 1
    return int(ref + G[x] + 0.5)


def show():
    oled.buffer[1:1 + NBYTES] = buf  # byte 0 of the driver buffer is a command byte
    oled.show()


def clear():
    buf[:] = BLANK


def px(x, y):
    if 0 <= x < W and 0 <= y < H:
        buf[(y >> 3) * W + x] |= 1 << (y & 7)


def pxc(x, y):
    if 0 <= x < W and 0 <= y < H:
        buf[(y >> 3) * W + x] &= ~(1 << (y & 7)) & 0xFF


def hline(x, y, w, on=True):
    if not 0 <= y < H:
        return
    base = (y >> 3) * W
    bit = 1 << (y & 7)
    for xx in range(max(x, 0), min(x + w, W)):
        if on:
            buf[base + xx] |= bit
        else:
            buf[base + xx] &= ~bit & 0xFF


def vline(x, y0, y1, on=True):
    if not 0 <= x < W:
        return
    y0 = max(y0, 0)
    y1 = min(y1, H - 1)
    if y0 > y1:
        return
    for p in range(y0 >> 3, (y1 >> 3) + 1):
        lo = y0 - p * 8 if y0 > p * 8 else 0
        hi = y1 - p * 8 if y1 < p * 8 + 7 else 7
        m = ((1 << (hi + 1)) - 1) ^ ((1 << lo) - 1)
        i = p * W + x
        if on:
            buf[i] |= m
        else:
            buf[i] &= ~m & 0xFF


def line(x0, y0, x1, y1, step=1):
    """Bresenham line; step=2 draws only every other pixel (dotted)."""
    dx, dy = abs(x1 - x0), -abs(y1 - y0)
    sx = 1 if x0 < x1 else -1
    sy = 1 if y0 < y1 else -1
    err = dx + dy
    n = 0
    while True:
        if n % step == 0:
            px(x0, y0)
        n += 1
        if x0 == x1 and y0 == y1:
            return
        e2 = 2 * err
        if e2 >= dy:
            err += dy
            x0 += sx
        if e2 <= dx:
            err += dx
            y0 += sy


# ---- sprites: ASCII rows -> column bit masks ----
# '#' white, '.' black (opaque), ':' checkered (50%), ' ' transparent
def make_sprite(rows):
    width = 0
    for r in rows:
        if len(r) > width:
            width = len(r)
    white, solid = [], []
    for x in range(width):
        wm = sm = 0
        for y in range(len(rows)):
            r = rows[y]
            ch = r[x] if x < len(r) else " "
            if ch != " ":
                sm |= 1 << y
            if ch == "#" or (ch == ":" and (x + y) % 2 == 0):
                wm |= 1 << y
        white.append(wm)
        solid.append(sm)
    return white, solid, width


def blit(spr, sx, sy, halo=True, glow=False):
    """Draw a sprite. halo clears a 1-px border; glow turns it into a dotted
    neon outline instead."""
    white, solid, width = spr
    if halo:
        for c in range(-1, width + 1):
            x = sx + c
            if 0 <= x < W:
                m = 0
                for k in (c - 1, c, c + 1):
                    if 0 <= k < width:
                        m |= solid[k]
                own = (solid[c] if 0 <= c < width else 0) << sy
                m = (m | (m << 1) | (m >> 1)) << sy
                for p in range(4):
                    sh = p * 8
                    bits = (m >> sh) & 0xFF
                    if bits:
                        i = p * W + x
                        buf[i] &= ~bits & 0xFF
                        if glow:
                            ring = bits & ~((own >> sh) & 0xFF) & 0xFF
                            buf[i] |= ring & (0x55 if (x & 1) == 0 else 0xAA)
    for c in range(width):
        x = sx + c
        if 0 <= x < W:
            om = solid[c] << sy
            wm = white[c] << sy
            for p in range(4):
                sh = p * 8
                bits = (om >> sh) & 0xFF
                if bits:
                    i = p * W + x
                    buf[i] = (buf[i] & ~bits & 0xFF) | ((wm >> sh) & 0xFF)
