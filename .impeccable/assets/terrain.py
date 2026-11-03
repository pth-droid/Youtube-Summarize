"""Draw contour lines of a seeded fractal height field as an SVG (used as a CSS mask, so strokes are plain white)."""
import math
import random
import sys

W, H = 1600, 1000          # viewBox
GX, GY = 200, 125          # sample grid
LEVELS = 22
SEED = 23

rng = random.Random(SEED)
LATTICE = 64
values = [[rng.random() for _ in range(LATTICE)] for _ in range(LATTICE)]


def smooth(t):
    return t * t * t * (t * (t * 6 - 15) + 10)


def value_noise(x, y):
    x0, y0 = math.floor(x), math.floor(y)
    fx, fy = smooth(x - x0), smooth(y - y0)
    a = values[y0 % LATTICE][x0 % LATTICE]
    b = values[y0 % LATTICE][(x0 + 1) % LATTICE]
    c = values[(y0 + 1) % LATTICE][x0 % LATTICE]
    d = values[(y0 + 1) % LATTICE][(x0 + 1) % LATTICE]
    return (a + (b - a) * fx) + ((c + (d - c) * fx) - (a + (b - a) * fx)) * fy


def fbm(x, y, octaves=4):
    total, amp, freq, norm = 0.0, 1.0, 1.0, 0.0
    for _ in range(octaves):
        total += amp * value_noise(x * freq, y * freq)
        norm += amp
        amp *= 0.5
        freq *= 2.03
    return total / norm


def height(u, v):
    # A gentle domain warp makes ridges and valleys instead of round blobs.
    wx = fbm(u * 1.6 + 11.3, v * 1.6 + 4.7, 3)
    wy = fbm(u * 1.6 + 2.1, v * 1.6 + 17.9, 3)
    return fbm(u * 1.7 + wx * 0.9, v * 1.7 + wy * 0.9)


field = [[height(i / GX * (W / H), j / GY) for i in range(GX + 1)] for j in range(GY + 1)]
lo = min(map(min, field))
hi = max(map(max, field))


def contour(level):
    """Marching squares: segments in viewBox units, then joined into chains."""
    sx, sy = W / GX, H / GY
    segments = []
    for j in range(GY):
        for i in range(GX):
            corners = [field[j][i], field[j][i + 1], field[j + 1][i + 1], field[j + 1][i]]
            pts = [(i, j), (i + 1, j), (i + 1, j + 1), (i, j + 1)]
            crossings = []
            for k in range(4):
                a, b = corners[k], corners[(k + 1) % 4]
                if (a < level) != (b < level):
                    t = (level - a) / (b - a)
                    (x0, y0), (x1, y1) = pts[k], pts[(k + 1) % 4]
                    crossings.append((round((x0 + (x1 - x0) * t) * sx, 2), round((y0 + (y1 - y0) * t) * sy, 2)))
            if len(crossings) == 2:
                segments.append((crossings[0], crossings[1]))
            elif len(crossings) == 4:
                segments.append((crossings[0], crossings[1]))
                segments.append((crossings[2], crossings[3]))
    ends = {}
    for index, (a, b) in enumerate(segments):
        ends.setdefault(a, []).append(index)
        ends.setdefault(b, []).append(index)
    used = [False] * len(segments)
    chains = []
    for start in range(len(segments)):
        if used[start]:
            continue
        used[start] = True
        chain = list(segments[start])
        for direction in (1, -1):
            while True:
                tip = chain[-1] if direction == 1 else chain[0]
                nxt = next((k for k in ends.get(tip, []) if not used[k]), None)
                if nxt is None:
                    break
                used[nxt] = True
                a, b = segments[nxt]
                point = b if a == tip else a
                if direction == 1:
                    chain.append(point)
                else:
                    chain.insert(0, point)
        if len(chain) > 6:
            chains.append(chain)
    return chains


def chaikin(points, rounds=2):
    for _ in range(rounds):
        out = [points[0]]
        for (x0, y0), (x1, y1) in zip(points, points[1:]):
            out.append((0.75 * x0 + 0.25 * x1, 0.75 * y0 + 0.25 * y1))
            out.append((0.25 * x0 + 0.75 * x1, 0.25 * y0 + 0.75 * y1))
        out.append(points[-1])
        points = out
    return points


def thin(points, gap=4.5):
    kept = [points[0]]
    for point in points[1:-1]:
        if math.dist(point, kept[-1]) >= gap:
            kept.append(point)
    kept.append(points[-1])
    return kept


def path(points):
    head, *rest = points
    return f"M{head[0]:.0f} {head[1]:.0f}" + "".join(f"L{x:.0f} {y:.0f}" for x, y in rest)


minor, index_lines = [], []
for n in range(1, LEVELS):
    level = lo + (hi - lo) * n / LEVELS
    target = index_lines if n % 5 == 0 else minor
    for chain in contour(level):
        target.append(path(thin(chaikin(chain))))

svg = (
    f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" preserveAspectRatio="xMidYMid slice">'
    f'<g fill="none" stroke="#fff" stroke-linecap="round" stroke-linejoin="round">'
    f'<path stroke-width="1" d="{"".join(minor)}"/>'
    f'<path stroke-width="2" d="{"".join(index_lines)}"/>'
    f"</g></svg>\n"
)
open(sys.argv[1], "w", encoding="utf-8").write(svg)
print(len(svg), "bytes", len(minor), "minor", len(index_lines), "index")
