# cars.py - sporty alternatives to the stock car sprite. All are 32 x 12 with the same
# wheel centres as CAR_ROWS ((6, 8) and (21, 8)), so they drop straight into code.py:
#     from cars import WEDGE_ROWS as CAR_ROWS        # or PONY_ROWS / SPYDER_ROWS
# They are solid white silhouettes with black cut-outs, and the nose points right.
# Headlamp is at sprite column 30, row 7; headlights() draws the beam from there.

# WEDGE: a low cab-forward supercar with a big rear wing
WEDGE_ROWS = (
    '',
    '#########',
    ' #     #     ######',
    ' #     #   ##...#...#',
    ' # #.#.#.###....#.....#',
    ' ###.....###....#.......#',
    '..#..###..########..###..####',
    '###.#####.:::::::#.#####.###...',
    '###.##.##..:::::.#.##.##.:#:#:##',
    ' ##.#####.########.#####.#######',
    '    .###.          .###.',
    '',
)

# PONY: a long-hood fastback muscle coupe with a ducktail and hood stripe
PONY_ROWS = (
    '',
    '',
    '          #######',
    '###   #####...#...#',
    '#########.....#....##',
    '####.....##########.....#.#.#',
    '..#..###..########..###..#####',
    '###.#####.:::::::#.#####.####..',
    '###.##.##..:::::.#.##.##.:#:#:##',
    ' ##.#####.########.#####.#######',
    '    .###.          .###.',
    '',
)

# SPYDER: an open roadster with a helmeted driver and a roll hoop
SPYDER_ROWS = (
    '',
    '',
    '          ##',
    '          #  ###',
    '          #  ##.  #',
    '   #.....## #### ##.....',
    '###..###..#.#####...###..',
    '..#.#####.:::::::#.#####.###...',
    '###.##.##..:::::.#.##.##.:#:#:##',
    ' ##.#####.########.#####.#######',
    '    .###.          .###.',
    '',
)

def headlights(px, sx, sy, nose_dy=7, length=17):
    """Headlight cone ahead of the car: two dotted edge rays that follow the road
    tilt, a sparse centre ray and a glint on the lamp. px is gfx.px; (sx, sy) is the
    car's top-left corner, exactly as in draw_car()."""
    nx, ny = sx + 32, sy + nose_dy
    for k in range(1, length):
        x = nx + k
        tilt = int(k * 0.113)                       # same tilt as the road (SLOPE)
        if k % 2 == 0 and k < length - 2:
            px(x, ny - 1 + tilt - k // 9)           # upper edge
            px(x, ny + 1 + tilt + k // 4)           # lower edge
        if k % 4 == 1 and k < length - 5:
            px(x, ny + tilt + k // 8)               # centre ray
    px(nx, ny - 1)
    px(nx + 1, ny)
