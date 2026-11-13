"""Genera assets/mermaid-contrib.svg: el calendario de contribuciones de los
últimos 12 meses, donde una sirena sale de su concha, se come los días de menos
a más contribuciones y vuelve a casa. Entonces los cuadritos vuelven a crecer y
la animación empieza de nuevo.

Se ejecuta todos los días desde .github/workflows/mermaid.yml. Para probarlo:
    GITHUB_TOKEN=<token> python tools/mermaid_contrib.py
    python tools/mermaid_contrib.py --demo     # datos de ejemplo, sin token
"""
import bisect
import datetime as dt
import json
import math
import os
import random
import sys
import urllib.request
from pathlib import Path

LOGIN = os.environ.get("USERNAME_GH", "HemsyCA")
OUT = Path(__file__).resolve().parent.parent / "assets" / "mermaid-contrib.svg"

BG_TOP, BG_BOTTOM, BORDER = "#0B1D33", "#060E1A", "#1B3550"
TEXT, MUTED = "#E6F1FF", "#7F9BB8"
EMPTY = "#10243A"
LEVELS = {
    "NONE": EMPTY,
    "FIRST_QUARTILE": "#0E4A5C",
    "SECOND_QUARTILE": "#13798A",
    "THIRD_QUARTILE": "#1FB5C4",
    "FOURTH_QUARTILE": "#5EF2FF",
}
FONT = "Fira Code, Consolas, Menlo, monospace"
MONTHS = ["Ene", "Feb", "Mar", "Abr", "May", "Jun",
          "Jul", "Ago", "Sep", "Oct", "Nov", "Dic"]

W, H = 1000, 240
CELL, PITCH = 12, 16
GX, GY = 112, 78
NEST = (58.0, GY + 3 * PITCH + CELL / 2)
REST = 4.0  # segundos que descansa en la concha antes de repetir


def fetch_calendar(token):
    query = """query($login: String!) { user(login: $login) {
      contributionsCollection { contributionCalendar {
        totalContributions
        weeks { contributionDays { date contributionCount contributionLevel weekday } }
      } } } }"""
    req = urllib.request.Request(
        "https://api.github.com/graphql",
        data=json.dumps({"query": query, "variables": {"login": LOGIN}}).encode(),
        headers={"Authorization": f"bearer {token}", "User-Agent": LOGIN},
    )
    with urllib.request.urlopen(req) as resp:
        data = json.load(resp)
    if "errors" in data:
        raise SystemExit(f"Error de la API de GitHub: {data['errors']}")
    return data["data"]["user"]["contributionsCollection"]["contributionCalendar"]


def demo_calendar():
    rng = random.Random(7)
    start = dt.date.today() - dt.timedelta(days=364)
    start -= dt.timedelta(days=(start.weekday() + 1) % 7)  # domingo
    weeks, total, day = [], 0, start
    while day <= dt.date.today():
        days = []
        for _ in range(7):
            if day > dt.date.today():
                break
            n = rng.choice([0] * 9 + [1, 2, 3, 5, 8])
            total += n
            level = ("NONE" if n == 0 else "FIRST_QUARTILE" if n < 2 else
                     "SECOND_QUARTILE" if n < 4 else
                     "THIRD_QUARTILE" if n < 6 else "FOURTH_QUARTILE")
            days.append({"date": day.isoformat(), "contributionCount": n,
                         "contributionLevel": level, "weekday": (day.weekday() + 1) % 7})
            day += dt.timedelta(days=1)
        weeks.append({"contributionDays": days})
    return {"totalContributions": total, "weeks": weeks}


def swim(points, step=2.0, keep_every=3):
    """Simula el nado: la sirena tiene una dirección y gira hacia el siguiente
    punto con un giro máximo por paso, así cada cambio de dirección es un arco
    suave y nunca una esquina. Devuelve las muestras de la ruta y, para cada
    punto original, el índice de la muestra donde se llega a él."""
    x, y = points[0]
    heading = 0.0
    raw, arrivals = [(x, y)], [0]
    for target in points[1:]:
        for _ in range(5000):
            dx, dy = target[0] - x, target[1] - y
            dist = math.hypot(dx, dy)
            if dist <= step:
                break
            diff = (math.atan2(dy, dx) - heading + math.pi) % (2 * math.pi) - math.pi
            # cerca del objetivo gira más fuerte para no quedarse dando vueltas
            max_turn = 0.09 + 0.5 * max(0.0, 1 - dist / 40)
            heading += max(-max_turn, min(max_turn, diff))
            x = min(max(x + step * math.cos(heading), 20.0), W - 20.0)
            y = min(max(y + step * math.sin(heading), 40.0), H - 30.0)
            raw.append((x, y))
        x, y = target
        raw.append((x, y))
        arrivals.append(len(raw) - 1)

    # menos puntos para que el SVG pese menos, conservando las llegadas
    keep = set(arrivals) | set(range(0, len(raw), keep_every))
    index, samples = {}, []
    for i, p in enumerate(raw):
        if i in keep:
            index[i] = len(samples)
            samples.append(p)
    return samples, [index[a] for a in arrivals]


SKIN, HAIR, HAIR_DARK = "#F7CDB0", "#C4A1FF", "#9D7CF0"
TAIL, TAIL_SHINE, FIN = "#6FA8F5", "#D2C2FF", "#5EF2FF"
MERMAID_SCALE = 1.6
FPS = 8          # cuadros por segundo; el navegador interpola entre ellos
SWIM = 1.2       # segundos que dura un aleteo

# Ancho (medio) del cuerpo según la distancia desde la cabeza, en unidades de dibujo
TORSO = [(6, 2.4), (7.5, 3.4), (9.5, 3.6), (12, 3.3), (14.5, 3.0), (17, 3.0)]
TAIL_SHAPE = [(15, 3.1), (19, 3.4), (24, 3.2), (30, 2.7), (36, 2.1), (42, 1.6), (47, 1.2), (52, 0.9)]
HAIR_SHAPE = [(4, 3.4), (8, 2.4), (12, 2.0), (16, 1.5), (21, 0.5)]
HEAD_AT, HEAD_R = 3.5, 3.6


def mermaid(samples, lengths, travel, dur):
    """La sirena vista desde arriba. Para que el cuerpo nunca se separe, cada
    cuadro de la animación se calcula aquí completo: la columna sigue la ruta que
    dejó la cabeza y el contorno se dibuja alrededor. Todas las piezas usan los
    mismos cuadros y el mismo tiempo, así que se mueven siempre juntas."""
    S = MERMAID_SCALE
    total = lengths[-1]
    speed = total / travel

    def point_at(s):
        s = min(max(s, 0.0), total)
        i = min(max(bisect.bisect_right(lengths, s) - 1, 0), len(samples) - 2)
        span = lengths[i + 1] - lengths[i]
        f = (s - lengths[i]) / span if span else 0.0
        (x0, y0), (x1, y1) = samples[i], samples[i + 1]
        return x0 + (x1 - x0) * f, y0 + (y1 - y0) * f

    def frame(t):
        head = t * speed  # sigue "avanzando" al llegar a casa, así entra entera en la concha
        phase = 2 * math.pi * t / SWIM

        def spine(d):
            """Punto de la columna a d unidades de la cabeza y su dirección."""
            s = min(head - d * S, total)
            (ax, ay), (bx, by) = point_at(s - 3), point_at(s + 3)
            dx, dy = bx - ax, by - ay
            norm = math.hypot(dx, dy)
            tx, ty = (dx / norm, dy / norm) if norm > 1e-6 else (1.0, 0.0)
            x, y = point_at(s)
            wave = min(2.6, max(0.0, 0.06 * (d - 10))) * math.sin(phase - d / 9) * S
            return x - ty * wave, y + tx * wave, tx, ty

        def outline(shape, extra_wave=0.0):
            left, right = [], []
            for d, w in shape:
                x, y, tx, ty = spine(d)
                if extra_wave:
                    off = extra_wave * math.sin(phase * 1.3 - d / 4) * S
                    x, y = x - ty * off, y + tx * off
                left.append((x - ty * w * S, y + tx * w * S))
                right.append((x + ty * w * S, y - tx * w * S))
            return poly(left + right[::-1])

        def local(base, fwd, lat):
            x, y, tx, ty = base
            return x + (tx * fwd - ty * lat) * S, y + (ty * fwd + tx * lat) * S

        end = spine(TAIL_SHAPE[-1][0])
        flap = 0.28 * math.sin(phase - TAIL_SHAPE[-1][0] / 9)
        fx, fy, tx, ty = end
        c, s_ = math.cos(flap), math.sin(flap)
        fin_base = (fx, fy, tx * c - ty * s_, ty * c + tx * s_)
        fin = poly([local(fin_base, -b, l) for b, l in
                    [(0, 0), (4, -2.5), (13, -9.5), (8.5, 0), (13, 9.5), (4, 2.5)]])

        shine = "M" + " L".join(f"{x:.1f},{y:.1f}" for x, y, _, _ in (spine(d) for d in range(18, 49, 5)))

        shoulder = spine(8.5)
        arms = ""
        for side in (-1, 1):
            a = 0.6 + 0.9 * (0.5 + 0.5 * math.sin(phase))
            sx, sy = local(shoulder, 0, 3.3 * side)
            hx, hy = local(shoulder, 8.5 * math.cos(a), (3.3 + 8.5 * math.sin(a)) * side)
            arms += f"M{sx:.1f},{sy:.1f} L{hx:.1f},{hy:.1f} "

        hc = spine(HEAD_AT)
        head_ring = poly([local(hc, HEAD_R * math.cos(k * math.pi / 5), HEAD_R * math.sin(k * math.pi / 5))
                          for k in range(10)])
        return {
            "fin": fin,
            "tail": outline(TAIL_SHAPE),
            "shine": shine,
            "arms": arms.strip(),
            "torso": outline(TORSO),
            "hair": head_ring + " " + outline(HAIR_SHAPE, extra_wave=0.5),
        }

    count = max(1, round(dur * FPS))
    frames = [frame(i * dur / count) for i in range(count + 1)]

    def piece(name, attrs):
        values = ";".join(f[name] for f in frames)
        return (f'<path d="{frames[0][name]}" {attrs}>'
                f'<animate attributeName="d" dur="{dur:.2f}s" repeatCount="indefinite" values="{values}"/></path>')

    return "\n  ".join([
        piece("fin", f'fill="{FIN}" fill-opacity="0.6" stroke="#BFFAFF" stroke-width="0.8" stroke-linejoin="round"'),
        piece("tail", f'fill="{TAIL}"'),
        piece("shine", f'fill="none" stroke="{TAIL_SHINE}" stroke-opacity="0.45" stroke-width="{1.4 * MERMAID_SCALE:.1f}" stroke-linecap="round"'),
        piece("arms", f'fill="none" stroke="{SKIN}" stroke-width="{1.5 * MERMAID_SCALE:.1f}" stroke-linecap="round"'),
        piece("torso", f'fill="{SKIN}"'),
        piece("hair", f'fill="{HAIR}" stroke="{HAIR_DARK}" stroke-width="0.6"'),
    ])


def poly(points):
    return "M" + " L".join(f"{x:.1f},{y:.1f}" for x, y in points) + " Z"


def shell(x, y):
    base = (x, y + 11)
    radius, lobes = 19.0, 7
    start, end = math.radians(168), math.radians(12)
    angles = [start + (end - start) * k / lobes for k in range(lobes + 1)]

    def at(a, r):
        return base[0] + r * math.cos(a), base[1] - r * math.sin(a)

    p0 = at(angles[0], radius)
    d = f"M{base[0] - 3:.1f},{base[1]:.1f} L{p0[0]:.1f},{p0[1]:.1f}"
    for a, b in zip(angles, angles[1:]):
        cx, cy = at((a + b) / 2, radius + 4)
        px, py = at(b, radius)
        d += f" Q{cx:.1f},{cy:.1f} {px:.1f},{py:.1f}"
    d += f" L{base[0] + 3:.1f},{base[1]:.1f} Z"
    ridges = "".join(
        f'<path d="M{base[0]:.1f},{base[1]:.1f} L{at(a, radius - 1.5)[0]:.1f},{at(a, radius - 1.5)[1]:.1f}" '
        f'stroke="#E37BA6" stroke-width="0.9" stroke-opacity="0.7"/>'
        for a in angles[1:-1])
    return f"""
  <g>
    <circle cx="{x}" cy="{y}" r="30" fill="url(#glow)">
      <animate attributeName="opacity" values="0.5;1;0.5" dur="4s" repeatCount="indefinite"/>
    </circle>
    <path d="{d}" fill="url(#shellfill)" stroke="#F48FB1" stroke-width="0.8" stroke-linejoin="round"/>
    {ridges}
    <path d="M{x - 8},{base[1]} L{x + 8},{base[1]} L{x + 4.5},{base[1] + 5} L{x - 4.5},{base[1] + 5} Z"
      fill="#F48FB1" stroke="#E37BA6" stroke-width="0.6" stroke-linejoin="round"/>
    <circle cx="{x}" cy="{base[1] - 3}" r="3.2" fill="url(#pearl)">
      <animate attributeName="r" values="3.2;3.6;3.2" dur="3s" repeatCount="indefinite"/>
    </circle>
    <text x="{x}" y="{y + 40}" fill="{MUTED}" font-family="{FONT}" font-size="11" text-anchor="middle">concha</text>
  </g>"""


def bubbles(rng):
    out = []
    for _ in range(14):
        x = rng.uniform(20, W - 20)
        r = rng.uniform(1.5, 3.5)
        dur = rng.uniform(6, 12)
        begin = rng.uniform(0, 10)
        out.append(
            f'<circle cx="{x:.1f}" cy="{H}" r="{r:.1f}" fill="none" stroke="#5EF2FF" stroke-opacity="0.35">'
            f'<animate attributeName="cy" values="{H + 5};-5" dur="{dur:.1f}s" begin="-{begin:.1f}s" repeatCount="indefinite"/>'
            f'<animate attributeName="cx" values="{x:.1f};{x + 6:.1f};{x - 4:.1f};{x:.1f}" dur="{dur / 2:.1f}s" repeatCount="indefinite"/>'
            f'</circle>')
    return "\n  ".join(out)


def build(cal):
    cells = []
    for col, week in enumerate(cal["weeks"]):
        for d in week["contributionDays"]:
            x, y = GX + col * PITCH, GY + d["weekday"] * PITCH
            cells.append({**d, "x": x, "y": y, "cx": x + CELL / 2, "cy": y + CELL / 2})

    food = sorted((c for c in cells if c["contributionCount"] > 0),
                  key=lambda c: (c["contributionCount"], c["date"]))
    route = [NEST] + [(c["cx"], c["cy"]) for c in food] + [NEST]
    if len(route) == 2:  # sin contribuciones: da un paseo y vuelve
        route = [NEST, (W / 2, GY + 3 * PITCH), NEST]
    samples, arrivals = swim(route)

    lengths = [0.0]
    for a, b in zip(samples, samples[1:]):
        lengths.append(lengths[-1] + math.dist(a, b))
    total = lengths[-1]
    travel = min(max(total / 170, 18), 70)
    dur = travel + REST
    home = travel / dur
    regrow = home + 0.6 / dur

    def frac(t):
        return f"{t:.4f}"

    rects, pops = [], []
    eat_at = {id(c): lengths[arrivals[i + 1]] / total * travel / dur for i, c in enumerate(food)}
    for c in cells:
        color = LEVELS.get(c["contributionLevel"], EMPTY)
        anim = ""
        if id(c) in eat_at:
            t = eat_at[id(c)]
            t2 = min(t + 0.25 / dur, home)
            anim = (f'<animate attributeName="fill" dur="{dur:.2f}s" repeatCount="indefinite" '
                    f'values="{color};{color};{EMPTY};{EMPTY};{color};{color}" '
                    f'keyTimes="0;{frac(t)};{frac(t2)};{frac(home)};{frac(regrow)};1"/>')
            pops.append(
                f'<circle cx="{c["cx"]}" cy="{c["cy"]}" r="0" fill="none" stroke="#5EF2FF" stroke-width="1.2">'
                f'<animate attributeName="r" dur="{dur:.2f}s" repeatCount="indefinite" '
                f'values="0;0;10;10" keyTimes="0;{frac(t)};{frac(min(t + 0.5 / dur, 1))};1"/>'
                f'<animate attributeName="stroke-opacity" dur="{dur:.2f}s" repeatCount="indefinite" '
                f'values="0;0.9;0;0" keyTimes="0;{frac(t)};{frac(min(t + 0.5 / dur, 1))};1"/>'
                f'</circle>')
        rects.append(f'<rect x="{c["x"]}" y="{c["y"]}" width="{CELL}" height="{CELL}" rx="2.5" fill="{color}">{anim}</rect>')

    months, last = [], None
    for col, week in enumerate(cal["weeks"]):
        first = dt.date.fromisoformat(week["contributionDays"][0]["date"])
        if first.month != last and col < len(cal["weeks"]) - 2:
            if last is not None or first.day <= 7:
                months.append(f'<text x="{GX + col * PITCH}" y="{GY - 10}" fill="{MUTED}" '
                              f'font-family="{FONT}" font-size="11">{MONTHS[first.month - 1]}</text>')
            last = first.month

    legend_x = W - 150
    legend = "".join(
        f'<rect x="{legend_x + 40 + i * 16}" y="{H - 34}" width="{CELL}" height="{CELL}" rx="2.5" fill="{col}"/>'
        for i, col in enumerate(LEVELS.values()))

    return f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" width="{W}" height="{H}">
  <defs>
    <linearGradient id="sea" x1="0" y1="0" x2="0" y2="1">
      <stop offset="0" stop-color="{BG_TOP}"/><stop offset="1" stop-color="{BG_BOTTOM}"/>
    </linearGradient>
    <radialGradient id="shellfill" cx="0.5" cy="0.9" r="0.9">
      <stop offset="0" stop-color="#FFE3EE"/><stop offset="0.6" stop-color="#F9B8D2"/><stop offset="1" stop-color="#F48FB1"/>
    </radialGradient>
    <radialGradient id="pearl" cx="0.35" cy="0.35" r="0.7">
      <stop offset="0" stop-color="#FFFFFF"/><stop offset="1" stop-color="#CFE8FF"/>
    </radialGradient>
    <radialGradient id="glow">
      <stop offset="0" stop-color="#5EF2FF" stop-opacity="0.22"/><stop offset="1" stop-color="#5EF2FF" stop-opacity="0"/>
    </radialGradient>
    <clipPath id="panel"><rect x="1" y="1" width="{W - 2}" height="{H - 2}" rx="14"/></clipPath>
  </defs>
  <rect x="1" y="1" width="{W - 2}" height="{H - 2}" rx="14" fill="url(#sea)" stroke="{BORDER}"/>
  <g clip-path="url(#panel)">
  {bubbles(random.Random(3))}
  <text x="40" y="38" fill="{MUTED}" font-family="{FONT}" font-size="14" letter-spacing="2">CONTRIBUCIONES · ÚLTIMOS 12 MESES</text>
  <text x="{W - 40}" y="38" fill="{MUTED}" font-family="{FONT}" font-size="13" text-anchor="end"><tspan fill="{TEXT}" font-weight="bold">{cal["totalContributions"]} contribuciones</tspan> · comidas de menos a más</text>
  {"".join(months)}
  {"".join(rects)}
  {"".join(pops)}
  <text x="{legend_x}" y="{H - 24}" fill="{MUTED}" font-family="{FONT}" font-size="11">Menos</text>
  {legend}
  <text x="{legend_x + 40 + 5 * 16 + 4}" y="{H - 24}" fill="{MUTED}" font-family="{FONT}" font-size="11">Más</text>
  {mermaid(samples, lengths, travel, dur)}
  {shell(*NEST)}
  </g>
</svg>
"""


def main():
    if "--demo" in sys.argv:
        cal = demo_calendar()
    else:
        token = os.environ.get("GITHUB_TOKEN")
        if not token:
            raise SystemExit("Falta GITHUB_TOKEN (o usa --demo)")
        cal = fetch_calendar(token)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(build(cal), encoding="utf-8")
    print(f"Escrito {OUT} ({cal['totalContributions']} contribuciones)")


if __name__ == "__main__":
    main()
