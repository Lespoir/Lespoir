"""Build daily details from the same aggregate snapshot as the monthly README chart."""
from pathlib import Path
import argparse
from datetime import datetime
import json

from update_chart import render_daily_svg

ROOT = Path(__file__).resolve().parents[1]


def build(output):
    page = (ROOT / 'site/template.html').read_text()
    snapshot = json.loads((ROOT / 'assets/merged-prs.json').read_text())
    updated = datetime.fromisoformat(snapshot['updated']).strftime('%b %d, %Y %H:%M')
    for theme in ('light', 'dark'):
        svg = render_daily_svg(snapshot['counts'], updated, dark=theme == 'dark')
        # Every inline SVG needs its own accessible-name IDs.
        svg = svg.replace('id="title"', f'id="title-{theme}"').replace('id="desc"', f'id="desc-{theme}"')
        svg = svg.replace('aria-labelledby="title desc"', f'aria-labelledby="title-{theme} desc-{theme}"')
        page = page.replace(f'__{theme.upper()}_CHART__', svg)
    output.mkdir(parents=True, exist_ok=True)
    (output / 'index.html').write_text(page)
    (output / '.nojekyll').touch()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=ROOT / '_site')
    build(parser.parse_args().output)
