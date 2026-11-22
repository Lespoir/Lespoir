"""Generate a PR-only activity chart. Fetch aggregate counts, never PR metadata."""
import argparse
from calendar import monthrange
from collections import defaultdict
from datetime import date, datetime, time, timedelta, timezone
from math import ceil
from html import escape
import json
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import time as clock
from zoneinfo import ZoneInfo

BOGOTA = ZoneInfo('America/Bogota')
ROOT = Path(__file__).resolve().parents[1]
LIGHT_COLORS = ['#ebedf0', '#9be9a8', '#40c463', '#30a14e', '#216e39']
DARK_COLORS = ['#161b22', '#0e4429', '#006d32', '#26a641', '#39d353']


def window(end):
    return [end - timedelta(days=i) for i in range(364, -1, -1)]


def search_for_day(owner, day):
    if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9-]{0,38}', owner):
        raise ValueError('Invalid GitHub username')
    start = datetime.combine(day, time.min, BOGOTA).astimezone(timezone.utc)
    end = start + timedelta(days=1) - timedelta(seconds=1)
    stamp = lambda dt: dt.strftime('%Y-%m-%dT%H:%M:%SZ')
    return f'is:pr is:merged author:{owner} merged:{stamp(start)}..{stamp(end)}'


def graphql(query):
    # gh uses an existing login locally and GH_TOKEN in Actions. Never extract a token.
    for attempt in range(3):
        result = subprocess.run(
            ['gh', 'api', 'graphql', '--input', '-'],
            input=json.dumps({'query': query}), text=True, capture_output=True,
            timeout=90,
        )
        if result.returncode == 0:
            payload = json.loads(result.stdout)
            if not payload.get('errors') and payload.get('data'):
                return payload['data']
        if attempt < 2:
            clock.sleep(3 * (attempt + 1))
    # Do not copy API responses into public Actions logs.
    raise RuntimeError('GitHub count lookup failed. Check token access and API limits. Existing charts were kept.')


def fetch_counts(owner, days, request=graphql, pause=clock.sleep):
    counts = {}
    for offset in range(0, len(days), 14):
        batch = days[offset:offset + 14]
        fields = [f'd{i}: search(query: {json.dumps(search_for_day(owner, day))}, type: ISSUE, first: 1) {{ issueCount }}'
                  for i, day in enumerate(batch)]
        data = request('query { viewer { login } ' + ' '.join(fields) + ' }')
        if data['viewer']['login'].lower() != owner.lower():
            raise RuntimeError('Use a token belonging to the profile owner, so private counts reflect their access.')
        for i, day in enumerate(batch):
            count = data.get(f'd{i}', {}).get('issueCount')
            if type(count) is not int or count < 0:
                raise RuntimeError('GitHub returned an incomplete count response. Existing charts were kept.')
            counts[day.isoformat()] = count
        if offset + len(batch) < len(days):
            pause(1)
    return counts


def shade(count):
    return 0 if count == 0 else 1 if count < 5 else 2 if count < 10 else 3 if count < 20 else 4


def readme_chart():
    return """<picture>
  <source media="(prefers-color-scheme: dark)" srcset="assets/merged-prs-dark.svg">
  <source media="(prefers-color-scheme: light)" srcset="assets/merged-prs-light.svg">
  <img alt="Monthly merged pull request totals over the last 365 days." src="assets/merged-prs-light.svg" width="100%">
</picture>"""


def replace_readme_chart(readme, chart):
    start, end = '<!-- PR-CHART:START -->', '<!-- PR-CHART:END -->'
    if readme.count(start) != 1 or readme.count(end) != 1 or readme.index(start) > readme.index(end):
        raise ValueError('README must contain exactly one ordered PR-CHART marker pair.')
    return readme.split(start)[0] + start + '\n' + chart + '\n' + end + readme.split(end)[1]


def render_daily_svg(counts, updated, dark=False):
    days = [date.fromisoformat(d) for d in counts]
    start, end = days[0], days[-1]
    anchor = start - timedelta(days=(start.weekday() + 1) % 7)
    ink, soft, border, bg = ('#f0f6fc', '#9198a1', '#3d444d', '#0d1117') if dark else ('#1f2328', '#59636e', '#d1d9e0', '#ffffff')
    colors = DARK_COLORS if dark else LIGHT_COLORS
    total = sum(counts.values())
    label = f'{total:,} merged pull requests in the last 365 days'
    parts = [f'<svg xmlns="http://www.w3.org/2000/svg" width="760" height="205" viewBox="0 0 760 205" role="img" aria-labelledby="title desc">',
             f'<title id="title">{label}</title>',
             f'<desc id="desc">PRs authored by Lespoir, counted on their merge date in America/Bogota. {start} through {end}, including today. Counts include accessible public and private repositories. Updated {escape(updated)}. Daily counts appear in each square title.</desc>',
             f'<rect x=".5" y=".5" width="759" height="204" rx="6" fill="{bg}" stroke="{border}"/>',
             f'<g font-family="-apple-system,BlinkMacSystemFont,Segoe UI,sans-serif" fill="{soft}" font-size="10">',
             f'<text x="18" y="27" fill="{ink}" font-size="14" font-weight="600">{label}</text>']
    for day in days:
        column, row = divmod((day - anchor).days, 7)
        if day.day == 1:
            parts.append(f'<text x="{47 + column * 13}" y="53">{day.strftime("%b")}</text>')
        count = counts[day.isoformat()]
        parts.append(f'<rect x="{47 + column * 13}" y="{63 + row * 13}" width="10" height="10" rx="2" fill="{colors[shade(count)]}"><title>{day}: {count} merged PRs</title></rect>')
    for row, name in [(1, 'Mon'), (3, 'Wed'), (5, 'Fri')]:
        parts.append(f'<text x="17" y="{71 + row * 13}">{name}</text>')
    parts.append(f'<text x="18" y="171">{start.strftime("%b %d, %Y")} – {end.strftime("%b %d, %Y")}</text>')
    parts.append('<text x="630" y="171">Less</text>')
    for i, color in enumerate(colors):
        parts.append(f'<rect x="{657+i*12}" y="162" width="9" height="9" rx="2" fill="{color}"/>')
    parts.append('<text x="721" y="171">More</text>')
    parts.append(f'<text x="18" y="190">Updated {escape(updated)} · Bogotá time</text></g></svg>')
    return '\n'.join(parts) + '\n'



def render_svg(counts, updated, dark=False):
    days = sorted(date.fromisoformat(day) for day in counts)
    start, end = days[0], days[-1]
    months = defaultdict(int)
    for day in days:
        months[day.replace(day=1)] += counts[day.isoformat()]
    ink, soft, border, bg, bar, current = (
        ('#f0f6fc', '#a5afbb', '#30363d', '#0d1117', '#79b8ff', '#c4a7ff') if dark else
        ('#1f2328', '#59636e', '#d8dee4', '#ffffff', '#376fba', '#7759b6')
    )
    total = sum(counts.values())
    maximum = max(months.values())
    # Leave room for value labels above the tallest bar, including an all-zero year.
    magnitude = 10 ** max(0, len(str(maximum)) - 1)
    ceiling = max(2, ceil(maximum * 1.15 / magnitude) * magnitude)
    label = f'{total:,} merged pull requests'
    period = f'{start.strftime("%b %d, %Y")} – {end.strftime("%b %d, %Y")}'
    parts = [
        '<svg xmlns="http://www.w3.org/2000/svg" width="760" height="300" viewBox="0 0 760 300" role="img" aria-labelledby="title desc">',
        f'<title id="title">{label} in the last 365 days</title>',
        f'<desc id="desc">PRs authored by Lespoir, grouped by merge month in America/Bogota. {period}. Asterisks mark partial months within this window. Updated {escape(updated)}.</desc>',
        f'<rect x=".5" y=".5" width="759" height="299" rx="6" fill="{bg}" stroke="{border}"/>',
        f'<g font-family="-apple-system,BlinkMacSystemFont,Segoe UI,sans-serif" font-size="11" fill="{soft}">',
        f'<text x="22" y="32" fill="{ink}" font-size="17" font-weight="600">{label}</text>',
        f'<text x="22" y="54">Monthly totals · {period}</text>',
    ]
    for value in (0, ceiling / 2, ceiling):
        y = 218 - value / ceiling * 130
        parts.extend([
            f'<path d="M48 {y:g}H730" stroke="{border}" fill="none"/>',
            f'<text x="39" y="{y + 4:g}" text-anchor="end">{value:,.0f}</text>',
        ])
    step = 676 / len(months)
    for index, (month, count) in enumerate(months.items()):
        last_day = month.replace(day=monthrange(month.year, month.month)[1])
        partial = month < start or last_day > end
        name = month.strftime('%b') + ('*' if partial else '')
        title = f'{month.strftime("%B %Y")}: {count:,} merged PRs'
        if partial:
            title += f' ({max(start, month):%b %d}–{min(end, last_day):%b %d}; partial month)'
        x = 56 + index * step
        height = count / ceiling * 130
        color = current if month == end.replace(day=1) else bar
        parts.extend([
            f'<rect x="{x:.2f}" y="{218 - height:.2f}" width="32" height="{height:.2f}" rx="3" fill="{color}" data-month="{month:%Y-%m}" data-count="{count}" data-partial="{str(partial).lower()}"><title>{title}</title></rect>',
            f'<text x="{x + 16:.2f}" y="{208 - height:.2f}" text-anchor="middle" fill="{ink}" font-size="12" font-weight="600">{count:,}</text>',
            f'<text x="{x + 16:.2f}" y="239" text-anchor="middle">{name}</text>',
        ])
    parts.extend([
        '<text x="22" y="266">* Partial months in this 365-day window.</text>',
        f'<text x="22" y="286">Updated {escape(updated)} · Bogotá time</text>',
        '</g></svg>',
    ])
    return '\n'.join(parts) + '\n'


def update(owner, output, end=None, request=graphql, pause=clock.sleep, readme_path=None):
    now = datetime.now(BOGOTA)
    days = window(end or now.date())
    counts = fetch_counts(owner, days, request, pause)
    updated = now.strftime('%b %d, %Y %H:%M')
    outputs = {
        'merged-prs-light.svg': render_svg(counts, updated),
        'merged-prs-dark.svg': render_svg(counts, updated, dark=True),
        'merged-prs.json': json.dumps({'timezone': 'America/Bogota', 'updated': now.isoformat(timespec='seconds'),
                                     'counts': counts}, indent=2) + '\n',
    }
    readme = replace_readme_chart(readme_path.read_text(), readme_chart()) if readme_path else None
    # Fetch and render everything before touching the last successful files.
    output.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=output) as staging:
        for name, content in outputs.items():
            Path(staging, name).write_text(content)
        for name in outputs:
            Path(staging, name).replace(output / name)
    if readme_path:
        with tempfile.NamedTemporaryFile(mode='w', dir=readme_path.parent, delete=False) as temporary:
            temporary.write(readme)
        Path(temporary.name).replace(readme_path)
    print(f'Updated {len(counts)} days: {sum(counts.values()):,} merged pull requests.')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--owner', default='Lespoir')
    parser.add_argument('--output', type=Path, default=ROOT / 'assets')
    args = parser.parse_args()
    try:
        update(args.owner, args.output, readme_path=ROOT / 'README.md')
    except (RuntimeError, ValueError, KeyError, OSError, subprocess.TimeoutExpired) as error:
        print(f'Chart update stopped: {error}', file=sys.stderr)
        sys.exit(1)
