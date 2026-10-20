"""Genera assets/mermaid-contrib.svg: el calendario de contribuciones de los
últimos 12 meses, donde una sirena sale de su concha, se come los días de menos
a más contribuciones y vuelve a casa. Entonces los cuadritos vuelven a crecer y
la animación empieza de nuevo.

Se ejecuta todos los días desde .github/workflows/mermaid.yml. Para probarlo:
    GITHUB_TOKEN=<token> python tools/mermaid_contrib.py
    python tools/mermaid_contrib.py --demo     # datos de ejemplo, sin token
"""
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


def catmull_rom(points, step=5.0):
    """Curva suave que pasa por todos los puntos. Devuelve las muestras y, para
    cada punto original, el índice de la muestra donde se llega a él."""
    samples, arrivals = [points[0]], [0]
    for i in range(len(points) - 1):
        p0 = points[max(i - 1, 0)]
        p1, p2 = points[i], points[i + 1]
        p3 = points[min(i + 2, len(points) - 1)]
        n = max(3, int(math.dist(p1, p2) / step))
        for s in range(1, n + 1):
            t = s / n
            t2, t3 = t * t, t * t * t
            x = 0.5 * (2 * p1[0] + (-p0[0] + p2[0]) * t
                       + (2 * p0[0] - 5 * p1[0] + 4 * p2[0] - p3[0]) * t2
                       + (-p0[0] + 3 * p1[0] - 3 * p2[0] + p3[0]) * t3)
            y = 0.5 * (2 * p1[1] + (-p0[1] + p2[1]) * t
                       + (2 * p0[1] - 5 * p1[1] + 4 * p2[1] - p3[1]) * t2
                       + (-p0[1] + 3 * p1[1] - 3 * p2[1] + p3[1]) * t3)
            samples.append((x, min(max(y, 40.0), H - 30.0)))
        arrivals.append(len(samples) - 1)
    return samples, arrivals


SKIN, HAIR, HAIR_DARK = "#F7CDB0", "#C4A1FF", "#9D7CF0"
TAIL_COLORS = ["#2DD4BF", "#7AA2F7", "#BB9AF7"]
FIN = "#5EF2FF"
MERMAID_SCALE = 1.6


def blend(colors, t):
    """Color en la posición t (0..1) de un degradado de varios colores."""
    t = min(max(t, 0.0), 1.0) * (len(colors) - 1)
    i = min(int(t), len(colors) - 2)
    a, b = colors[i], colors[i + 1]
    f = t - i
    return "#" + "".join(
        f"{round(int(a[k:k + 2], 16) * (1 - f) + int(b[k:k + 2], 16) * f):02X}" for k in (1, 3, 5))


def mermaid(dur, home, speed):
    """La sirena vista desde arriba, mirando hacia +x. Cada parte del cuerpo sigue
    la misma ruta que la cabeza con un pequeño retraso, así el cuerpo se curva en
    los giros como el de un pez de verdad, y además ondula al nadar."""

    def part(dist, body, wiggle=0.0, phase=0.0):
        lag = dist * MERMAID_SCALE / speed
        body = f'<g transform="scale({MERMAID_SCALE})">{body}</g>'
        motion = (f'<animateMotion dur="{dur:.2f}s" begin="{lag - dur:.3f}s" repeatCount="indefinite" '
                  f'rotate="auto" calcMode="linear" keyPoints="0;1;1" keyTimes="0;{home:.4f};1">'
                  f'<mpath href="#route" xlink:href="#route"/></animateMotion>')
        if wiggle:
            body = (f'<g><animateTransform attributeName="transform" type="translate" '
                    f'values="0,{-wiggle:.2f};0,{wiggle:.2f};0,{-wiggle:.2f}" dur="1.2s" '
                    f'begin="-{phase:.2f}s" repeatCount="indefinite"/>{body}</g>')
        return f"<g>{motion}{body}</g>"

    parts = []
    segments = 10
    tail_start, gap = 19.0, 3.4
    fin_dist = tail_start + segments * gap
    parts.append(part(fin_dist, f"""
      <path d="M1,0 C-3,-2 -7,-7 -14,-9.5 C-11.5,-4.5 -9.5,-1.8 -8.5,0 C-9.5,1.8 -11.5,4.5 -14,9.5 C-7,7 -3,2 1,0Z"
        fill="{FIN}" fill-opacity="0.55" stroke="#BFFAFF" stroke-width="0.5" stroke-opacity="0.9">
        <animateTransform attributeName="transform" type="rotate" values="-16;16;-16" dur="1.2s"
          begin="-{segments * 0.09:.2f}s" repeatCount="indefinite"/>
      </path>""", wiggle=0.3 + segments * 0.17, phase=segments * 0.09))
    for i in reversed(range(segments)):
        ry = 3.3 - i * 0.22
        color = blend(TAIL_COLORS, i / (segments - 1))
        parts.append(part(
            tail_start + i * gap,
            f'<ellipse rx="4.4" ry="{ry:.2f}" fill="{color}"/>'
            f'<ellipse cx="0.6" cy="{-ry * 0.4:.2f}" rx="1.3" ry="{ry * 0.22:.2f}" fill="#FFFFFF" fill-opacity="0.28"/>',
            wiggle=0.3 + i * 0.17, phase=i * 0.09))
    parts.append(part(0, f"""
      <path d="M-9,-2.6 C-6,-5 -2,-7 1,-8.5" stroke="{SKIN}" stroke-width="1.5" stroke-linecap="round" fill="none">
        <animate attributeName="d" dur="1.2s" repeatCount="indefinite"
          values="M-9,-2.6 C-6,-5 -2,-7 1,-8.5;M-9,-2.6 C-8,-6 -7,-8 -6,-10;M-9,-2.6 C-6,-5 -2,-7 1,-8.5"/>
      </path>
      <path d="M-9,2.6 C-6,5 -2,7 1,8.5" stroke="{SKIN}" stroke-width="1.5" stroke-linecap="round" fill="none">
        <animate attributeName="d" dur="1.2s" repeatCount="indefinite"
          values="M-9,2.6 C-6,5 -2,7 1,8.5;M-9,2.6 C-8,6 -7,8 -6,10;M-9,2.6 C-6,5 -2,7 1,8.5"/>
      </path>
      <path d="M-20,-2.6 C-16,-3.6 -12,-3.6 -9,-3.1 C-7,-2.6 -6.5,-1 -6.5,0 C-6.5,1 -7,2.6 -9,3.1 C-12,3.6 -16,3.6 -20,2.6 C-21,1 -21,-1 -20,-2.6Z"
        fill="{SKIN}"/>
      <circle cx="-3" cy="0" r="3.4" fill="{HAIR}"/>
      <path d="M-3,-3.4 C-1,-3 0.4,-1.6 0.4,0 C0.4,1.6 -1,3 -3,3.4" stroke="{HAIR_DARK}" stroke-width="0.6" fill="none"/>
      <path d="M-2.4,-4.4 l0.6,1 1.2,0.1 -0.9,0.75 0.3,1.2 -1.2,-0.7 -1.1,0.7 0.3,-1.2 -0.9,-0.75 1.2,-0.1Z" fill="#FFD166"/>"""))
    for k, (dist, ry) in enumerate([(7.5, 2.0), (11.5, 1.6), (15.5, 1.1)]):
        parts.append(part(
            dist,
            f'<ellipse rx="3.4" ry="{ry}" fill="{HAIR if k % 2 == 0 else HAIR_DARK}" fill-opacity="0.95"/>',
            wiggle=0.25 + k * 0.2, phase=0.3 + k * 0.12))
    return "\n  ".join(parts)


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
    samples, arrivals = catmull_rom(route)

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

    path = "M" + " L".join(f"{x:.1f},{y:.1f}" for x, y in samples)
    legend_x = W - 150
    legend = "".join(
        f'<rect x="{legend_x + 40 + i * 16}" y="{H - 34}" width="{CELL}" height="{CELL}" rx="2.5" fill="{col}"/>'
        for i, col in enumerate(LEVELS.values()))

    return f"""<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" viewBox="0 0 {W} {H}" width="{W}" height="{H}">
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
    <path id="route" d="{path}" fill="none"/>
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
  {mermaid(dur, home, total / travel)}
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
