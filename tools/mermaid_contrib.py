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


def mermaid():
    """La sirena vista desde arriba, mirando hacia +x, con la boca en el origen."""
    return """
    <g transform="scale(1.3)">
      <g>
        <animateTransform attributeName="transform" type="rotate"
          values="-14 -8 0;14 -8 0;-14 -8 0" dur="0.9s" repeatCount="indefinite"/>
        <path d="M-36,0 C-40,-2 -45,-8 -53,-12 C-50,-6 -47,-3 -45.5,0 C-47,3 -50,6 -53,12 C-45,8 -40,2 -36,0Z"
          fill="#5EF2FF" fill-opacity="0.8" stroke="#BFFAFF" stroke-width="0.6"/>
        <path d="M-7,-5.5 C-18,-6 -28,-3.5 -37,-1.2 L-37,1.2 C-28,3.5 -18,6 -7,5.5Z" fill="url(#tail)"/>
        <path d="M-13,-3.6 q2,3.6 0,7.2 M-19,-3.2 q2,3.2 0,6.4 M-25,-2.5 q1.6,2.5 0,5 M-30,-1.8 q1.2,1.8 0,3.6"
          stroke="#E6F1FF" stroke-opacity="0.4" stroke-width="0.8" fill="none"/>
      </g>
      <path d="M2,-6 L10,-12" stroke="#F5C9A8" stroke-width="2.4" stroke-linecap="round">
        <animate attributeName="d" values="M2,-6 L10,-12;M2,-6 L1,-14;M2,-6 L10,-12" dur="0.9s" repeatCount="indefinite"/>
      </path>
      <path d="M2,6 L10,12" stroke="#F5C9A8" stroke-width="2.4" stroke-linecap="round">
        <animate attributeName="d" values="M2,6 L10,12;M2,6 L1,14;M2,6 L10,12" dur="0.9s" repeatCount="indefinite"/>
      </path>
      <path d="M-8,-5 C-4,-7.5 3,-7.5 4,-4 C5,-1.5 5,1.5 4,4 C3,7.5 -4,7.5 -8,5Z" fill="#F5C9A8"/>
      <path d="M5,-3 C0,-3.5 -8,-2.5 -16,-1.5 C-12,0 -12,0 -16,1.5 C-8,2.5 0,3.5 5,3Z" fill="#BB9AF7">
        <animate attributeName="d" dur="1.2s" repeatCount="indefinite"
          values="M5,-3 C0,-3.5 -8,-2.5 -16,-1.5 C-12,0 -12,0 -16,1.5 C-8,2.5 0,3.5 5,3Z;
                  M5,-3 C0,-3.5 -8,-4 -17,-4 C-13,-2 -13,-1 -17,0 C-8,1.5 0,3.5 5,3Z;
                  M5,-3 C0,-3.5 -8,-2.5 -16,-1.5 C-12,0 -12,0 -16,1.5 C-8,2.5 0,3.5 5,3Z"/>
      </path>
      <circle cx="7.5" cy="0" r="4.6" fill="#9D7CF0"/>
      <path d="M7.5,-5.6 l0.8,1.4 1.6,0.1 -1.2,1 0.4,1.6 -1.6,-0.9 -1.5,0.9 0.4,-1.6 -1.2,-1 1.6,-0.1Z" fill="#FFD166"/>
    </g>"""


def shell(x, y):
    ridges = "".join(
        f'<path d="M{x:.1f},{y + 8:.1f} L{x + 17 * math.cos(a):.1f},{y + 8 - 17 * math.sin(a):.1f}" '
        f'stroke="#C9739A" stroke-width="1"/>'
        for a in [math.pi * k / 6 for k in range(1, 6)])
    return f"""
  <g>
    <circle cx="{x}" cy="{y}" r="24" fill="none" stroke="#5EF2FF" stroke-opacity="0.25" stroke-dasharray="3 4">
      <animateTransform attributeName="transform" type="rotate" from="0 {x} {y}" to="360 {x} {y}" dur="20s" repeatCount="indefinite"/>
    </circle>
    <path d="M{x - 18},{y + 8} A18,18 0 0 1 {x + 18},{y + 8} Z" fill="#F7A8C4"/>
    {ridges}
    <rect x="{x - 5}" y="{y + 7}" width="10" height="5" rx="2" fill="#E58FB2"/>
    <text x="{x}" y="{y + 38}" fill="{MUTED}" font-family="{FONT}" font-size="11" text-anchor="middle">concha</text>
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
    travel = min(max(total / 260, 12), 45)
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

    return f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" width="{W}" height="{H}">
  <defs>
    <linearGradient id="sea" x1="0" y1="0" x2="0" y2="1">
      <stop offset="0" stop-color="{BG_TOP}"/><stop offset="1" stop-color="{BG_BOTTOM}"/>
    </linearGradient>
    <linearGradient id="tail" x1="1" y1="0" x2="0" y2="0">
      <stop offset="0" stop-color="#2DD4BF"/><stop offset="0.6" stop-color="#7AA2F7"/><stop offset="1" stop-color="#BB9AF7"/>
    </linearGradient>
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
  {shell(*NEST)}
  <text x="{legend_x}" y="{H - 24}" fill="{MUTED}" font-family="{FONT}" font-size="11">Menos</text>
  {legend}
  <text x="{legend_x + 40 + 5 * 16 + 4}" y="{H - 24}" fill="{MUTED}" font-family="{FONT}" font-size="11">Más</text>
  <g>
    <animateMotion dur="{dur:.2f}s" repeatCount="indefinite" rotate="auto" calcMode="linear"
      keyPoints="0;1;1" keyTimes="0;{frac(home)};1" path="{path}"/>
    {mermaid()}
  </g>
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
