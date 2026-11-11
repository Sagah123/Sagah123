"""Generate dynamic Neon Cyan CRT SVG cards for Sagah123 GitHub profile.

Reads:
- GitHub 30-day contribution counts (via GraphQL if GITHUB_TOKEN is set, else public calendar)
- WakaTime last 7 days coding activity (via WAKATIME_API_KEY env var)

Writes:
- assets/wakatime_clock.svg
- assets/commit_signal.svg
"""

from __future__ import annotations

import datetime as dt
import json
import os
import re
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
ASSETS_DIR = ROOT / "assets"
GITHUB_USER = os.environ.get("GITHUB_USER", "Sagah123")

FONT_STACK = "ui-monospace, 'Cascadia Mono', Consolas, 'Liberation Mono', Menlo, monospace"

SCANLINE_DEFS = """  <defs>
    <linearGradient id="tb" x1="0" y1="0" x2="1" y2="0">
      <stop offset="0%" stop-color="#1a233a"/>
      <stop offset="100%" stop-color="#0b0e18"/>
    </linearGradient>
    <pattern id="scan" width="4" height="4" patternUnits="userSpaceOnUse">
      <rect width="4" height="2" fill="none"/>
      <rect y="2" width="4" height="2" fill="#000000" fill-opacity="0.18"/>
    </pattern>
  </defs>"""


def win95_shell(width: int, height: int, title: str, right_label: str, extra_css: str = "") -> tuple[str, str]:
    """Return opening and closing SVG markup for a 2px-beveled Win95 Neon Cyan window."""
    iw = width - 20
    ih = height - 44
    head = f"""<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}" fill="none">
{SCANLINE_DEFS}
  <style>
    text {{ font-family: {FONT_STACK}; }}
{extra_css}
  </style>
  <!-- Window outer fill & 2px Win95 bevel -->
  <rect width="{width}" height="{height}" fill="#121320"/>
  <rect x="0" y="0" width="{width}" height="2" fill="#273047"/>
  <rect x="0" y="0" width="2" height="{height}" fill="#273047"/>
  <rect x="0" y="{height - 2}" width="{width}" height="2" fill="#06070c"/>
  <rect x="{width - 2}" y="0" width="2" height="{height}" fill="#06070c"/>

  <!-- Titlebar -->
  <rect x="2" y="2" width="{width - 4}" height="26" fill="url(#tb)"/>
  <rect x="2" y="27" width="{width - 4}" height="1" fill="#273047"/>
  <text x="12" y="19" fill="#cbd5e1" font-size="12" font-weight="700">{title}</text>
  <text x="{width - 12}" y="19" fill="#64748b" font-size="11" text-anchor="end">{right_label}</text>

  <!-- Inset panel -->
  <rect x="10" y="34" width="{iw}" height="{ih}" fill="#080a10"/>
  <rect x="10" y="34" width="{iw}" height="2" fill="#040508"/>
  <rect x="10" y="34" width="2" height="{ih}" fill="#040508"/>
  <rect x="10" y="{34 + ih - 2}" width="{iw}" height="2" fill="#273047"/>
  <rect x="{10 + iw - 2}" y="34" width="2" height="{ih}" fill="#273047"/>
"""
    tail = f"""  <rect x="12" y="36" width="{iw - 4}" height="{ih - 4}" fill="url(#scan)"/>
</svg>
"""
    return head, tail


def _default_week_days() -> list[tuple[str, float]]:
    today_idx = dt.date.today().weekday()
    letters = ["M", "T", "W", "T", "F", "S", "S"]
    return [(letters[(today_idx - 6 + i) % 7], 0.0) for i in range(7)]


def fetch_wakatime_7d(token: str) -> dict | None:
    """Fetch WakaTime 7-day summaries (OAuth token) or today's active time (API key)."""
    if not token:
        return None

    # 1) Full 7-day summaries require a Personal OAuth Token (wakatime.com/oauth)
    params = urllib.parse.urlencode({"range": "Last 7 Days"})
    url_7d = f"https://api.wakatime.com/api/v1/users/current/summaries?{params}"
    req_7d = urllib.request.Request(
        url_7d,
        headers={
            "Authorization": f"Bearer {token}",
            "User-Agent": "Sagah123-Profile-Updater",
        },
    )
    try:
        with urllib.request.urlopen(req_7d, timeout=15) as resp:
            payload = json.loads(resp.read().decode("utf-8"))
        days = payload.get("data") or []
        if days:
            daily = []
            for entry in days[-7:]:
                date_str = entry.get("range", {}).get("date", "")
                secs = float(entry.get("grand_total", {}).get("total_seconds", 0.0))
                try:
                    weekday = dt.date.fromisoformat(date_str).strftime("%a")[0]
                except ValueError:
                    weekday = "?"
                daily.append((weekday, secs))
            return {
                "days": daily,
                "today_secs": daily[-1][1],
                "total_secs": sum(s for _, s in daily),
                "today_only": False,
            }
    except (urllib.error.URLError, json.JSONDecodeError, TimeoutError):
        pass

    # 2) Fallback for write/plugin API keys (waka_...): status_bar/today works directly
    url_today = f"https://wakatime.com/api/v1/users/current/status_bar/today?{urllib.parse.urlencode({'api_key': token})}"
    req_today = urllib.request.Request(url_today, headers={"User-Agent": "Sagah123-Profile-Updater"})
    try:
        with urllib.request.urlopen(req_today, timeout=15) as resp:
            payload = json.loads(resp.read().decode("utf-8"))
        secs = float((payload.get("data") or {}).get("grand_total", {}).get("total_seconds", 0.0))
        daily = _default_week_days()
        daily[-1] = (daily[-1][0], secs)
        return {"days": daily, "today_secs": secs, "total_secs": None, "today_only": True}
    except (urllib.error.URLError, json.JSONDecodeError, TimeoutError):
        return None


def fmt_hhmm(seconds: float) -> tuple[str, str]:
    """Return (HH, MM) zero-padded strings from seconds."""
    mins = int(round(max(0.0, seconds) / 60.0))
    return f"{mins // 60:02d}", f"{mins % 60:02d}"


def build_wakatime_svg(stats: dict | None) -> str:
    """Render wakatime_clock.svg matching the 438x198 Neon Cyan Win95 card."""
    css = """    .blink { animation: blink 1.1s steps(1, end) infinite; }
    @keyframes blink { 0%, 49% { opacity: 1; } 50%, 100% { opacity: 0.25; } }"""
    head, tail = win95_shell(438, 198, "wakatime // daily_clock", "AUTO-UPDATED", css)

    if stats:
        th, tm = fmt_hhmm(stats["today_secs"])
        days = stats["days"]
        max_sec = max((s for _, s in days), default=0.0)
        if stats["today_only"] or stats["total_secs"] is None:
            tot_label = "--h --m"
            status_hint = '  <text x="414" y="92" fill="#64748b" font-size="10" text-anchor="end">TODAY OK // OAUTH FOR 7D</text>\n'
        else:
            tot_h, tot_m = fmt_hhmm(stats["total_secs"])
            tot_label = f"{int(tot_h)}h {tot_m}m"
            status_hint = ""
    else:
        th, tm = "--", "--"
        tot_label = "--h --m"
        days = _default_week_days()
        max_sec = 0.0
        status_hint = '  <text x="414" y="92" fill="#64748b" font-size="10" text-anchor="end">SET WAKATIME_API_KEY</text>\n'

    clock_svg = """  <g transform="translate(24, 48) scale(2)" shape-rendering="crispEdges">
    <rect x="3" y="1" width="8" height="12" fill="#00f0ff"/>
    <rect x="1" y="3" width="12" height="8" fill="#00f0ff"/>
    <rect x="3" y="3" width="8" height="8" fill="#080a10"/>
    <rect x="6" y="4" width="2" height="3" fill="#fcee0a"/>
    <rect x="6" y="7" width="4" height="2" fill="#ff2a6d" class="blink"/>
  </g>"""

    time_row = f"""{clock_svg}
  <text x="64" y="59" fill="#94a3b8" font-size="11">TODAY_ACTIVE</text>
  <text x="64" y="80" fill="#00f0ff" font-size="18" font-weight="700">{th}<tspan class="blink">:</tspan>{tm} <tspan fill="#64748b" font-size="12" font-weight="400">hrs</tspan></text>
  <text x="414" y="59" fill="#94a3b8" font-size="11" text-anchor="end">7D_TOTAL</text>
  <text x="414" y="79" fill="#fcee0a" font-size="14" font-weight="700" text-anchor="end">{tot_label}</text>
{status_hint}  <line x1="24" y1="98" x2="414" y2="98" stroke="#1e293b" stroke-dasharray="4 4"/>
"""

    bars_svg = []
    bar_w = 42
    gap = 16
    start_x = 24
    chart_bottom = 163
    max_bar_h = 54

    for idx, (label, secs) in enumerate(days):
        bx = start_x + idx * (bar_w + gap)
        if max_sec > 0 and secs > 0:
            bh = max(4, int(round((secs / max_sec) * max_bar_h)))
            if secs == max_sec:
                fill = "#ff2a6d"
            elif idx == len(days) - 1:
                fill = "#00f0ff"
            else:
                fill = "#00b4d8"
        else:
            bh = 4
            fill = "#1e293b"

        by = chart_bottom - bh
        label_color = "#00f0ff" if idx == len(days) - 1 else "#64748b"
        label_weight = "700" if idx == len(days) - 1 else "400"
        bars_svg.append(
            f'  <rect x="{bx}" y="{by}" width="{bar_w}" height="{bh}" fill="{fill}"/>\n'
            f'  <text x="{bx + bar_w // 2}" y="179" fill="{label_color}" font-size="11" font-weight="{label_weight}" text-anchor="middle">{label}</text>'
        )

    return head + time_row + "\n".join(bars_svg) + "\n" + tail


def fetch_github_commits_30d(token: str | None) -> list[tuple[str, int]]:
    """Return 30 daily (YYYY-MM-DD, count) points via GraphQL or public calendar fallback."""
    today = dt.date.today()
    start = today - dt.timedelta(days=29)

    if token:
        query = """
        query($login: String!, $from: DateTime!, $to: DateTime!) {
          user(login: $login) {
            contributionsCollection(from: $from, to: $to) {
              contributionCalendar {
                weeks {
                  contributionDays { date contributionCount }
                }
              }
            }
          }
        }"""
        body = json.dumps({
            "query": query,
            "variables": {
                "login": GITHUB_USER,
                "from": f"{start.isoformat()}T00:00:00Z",
                "to": f"{today.isoformat()}T23:59:59Z",
            },
        }).encode("utf-8")
        req = urllib.request.Request(
            "https://api.github.com/graphql",
            data=body,
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json",
                "User-Agent": "Sagah123-Profile-Updater",
            },
        )
        try:
            with urllib.request.urlopen(req, timeout=15) as resp:
                data = json.loads(resp.read().decode("utf-8"))
            weeks = data["data"]["user"]["contributionsCollection"]["contributionCalendar"]["weeks"]
            counts = {d["date"]: int(d["contributionCount"]) for w in weeks for d in w["contributionDays"]}
            return [( (start + dt.timedelta(days=i)).isoformat(), counts.get((start + dt.timedelta(days=i)).isoformat(), 0) ) for i in range(30)]
        except Exception:
            pass

    # Public HTML fallback maps GitHub data-level (0..4) for local/unauthenticated runs
    url = f"https://github.com/users/{GITHUB_USER}/contributions"
    req = urllib.request.Request(url, headers={"User-Agent": "Sagah123-Profile-Updater"})
    counts: dict[str, int] = {}
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            html = resp.read().decode("utf-8", "ignore")
        for m in re.finditer(r'data-date="(\d{4}-\d{2}-\d{2})"[^>]*data-level="(\d)"', html):
            counts[m.group(1)] = int(m.group(2))
    except Exception:
        pass

    return [((start + dt.timedelta(days=i)).isoformat(), counts.get((start + dt.timedelta(days=i)).isoformat(), 0)) for i in range(30)]


def build_commit_signal_svg(series: list[tuple[str, int]]) -> str:
    """Render commit_signal.svg oscilloscope 30-day activity graph (438x198)."""
    css = """    .pulse { animation: pulse 1.4s ease-in-out infinite; }
    @keyframes pulse { 0%, 100% { opacity: 1; } 50% { opacity: 0.35; } }"""
    head, tail = win95_shell(438, 198, "signal_monitor // commits", "30 DAYS", css)

    x0, x1 = 26, 412
    y_top, y_bot = 58, 166
    grid = (
        f'  <line x1="{x0}" y1="68" x2="{x1}" y2="68" stroke="#1e293b" stroke-dasharray="3 3"/>\n'
        f'  <line x1="{x0}" y1="100" x2="{x1}" y2="100" stroke="#1e293b" stroke-dasharray="3 3"/>\n'
        f'  <line x1="{x0}" y1="132" x2="{x1}" y2="132" stroke="#1e293b" stroke-dasharray="3 3"/>\n'
        f'  <line x1="{x0}" y1="166" x2="{x1}" y2="166" stroke="#1e293b"/>\n'
    )

    vals = [c for _, c in series]
    max_v = max(vals) if vals else 0
    step_x = (x1 - x0) / max(1, len(series) - 1)

    pts = []
    for i, val in enumerate(vals):
        px = round(x0 + i * step_x, 1)
        if max_v > 0:
            py = round(y_bot - (val / max_v) * (y_bot - y_top), 1)
        else:
            py = y_bot
        pts.append((px, py, val))

    poly_str = " ".join(f"{px},{py}" for px, py, _ in pts)
    area_str = f"{x0},{y_bot} " + poly_str + f" {x1},{y_bot}"

    nodes = []
    for i, (px, py, val) in enumerate(pts):
        if i == len(pts) - 1:
            nodes.append(f'  <rect x="{px - 3:.1f}" y="{py - 3:.1f}" width="6" height="6" fill="#00f0ff" class="pulse"/>')
        elif max_v > 0 and val == max_v:
            nodes.append(f'  <rect x="{px - 2.5:.1f}" y="{py - 2.5:.1f}" width="5" height="5" fill="#ff2a6d"/>')
        elif max_v > 0 and val >= max_v * 0.65:
            nodes.append(f'  <rect x="{px - 2:.1f}" y="{py - 2:.1f}" width="4" height="4" fill="#fcee0a"/>')

    footer = (
        f'  <text x="{x0}" y="180" fill="#64748b" font-size="10">-30D</text>\n'
        f'  <text x="219" y="180" fill="#94a3b8" font-size="10" text-anchor="middle">SIGNAL_LEVEL</text>\n'
        f'  <text x="{x1}" y="180" fill="#00f0ff" font-size="10" text-anchor="end">NOW</text>\n'
    )

    body = (
        grid
        + f'  <polygon points="{area_str}" fill="#00f0ff" fill-opacity="0.08"/>\n'
        + f'  <polyline points="{poly_str}" stroke="#00f0ff" stroke-width="2" stroke-linejoin="round" stroke-linecap="round"/>\n'
        + "\n".join(nodes)
        + "\n"
        + footer
    )
    return head + body + tail


def main() -> None:
    ASSETS_DIR.mkdir(parents=True, exist_ok=True)
    waka_key = os.environ.get("WAKATIME_API_KEY", "").strip()
    gh_token = os.environ.get("GITHUB_TOKEN", "").strip()

    waka_stats = fetch_wakatime_7d(waka_key)
    (ASSETS_DIR / "wakatime_clock.svg").write_text(build_wakatime_svg(waka_stats), encoding="utf-8")

    commits = fetch_github_commits_30d(gh_token)
    (ASSETS_DIR / "commit_signal.svg").write_text(build_commit_signal_svg(commits), encoding="utf-8")
    print("Generated wakatime_clock.svg and commit_signal.svg")


if __name__ == "__main__":
    main()
