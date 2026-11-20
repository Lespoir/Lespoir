"""Publish only the chart page, built from the same SVG snapshots as the README."""
from pathlib import Path
import argparse

ROOT = Path(__file__).resolve().parents[1]


def build(output):
    page = (ROOT / 'site/template.html').read_text()
    for theme in ('light', 'dark'):
        svg = (ROOT / f'assets/merged-prs-{theme}.svg').read_text()
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
