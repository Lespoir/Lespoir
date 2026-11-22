from datetime import date
from collections import defaultdict
import json
from pathlib import Path
import sys
import tempfile
import unittest
import xml.etree.ElementTree as ET
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from update_chart import fetch_counts, render_svg, render_daily_svg, search_for_day, update, window, readme_chart, replace_readme_chart

from build_page import build


class ChartTests(unittest.TestCase):
    def test_readme_uses_one_full_width_image_without_navigation(self):
        markup = readme_chart()
        self.assertEqual(markup.count('<img '), 1)
        self.assertIn('width="100%"', markup)
        self.assertNotIn('<a ', markup)
        self.assertNotIn('href=', markup)
        self.assertNotIn('Click to explore', markup)
        self.assertIn('assets/merged-prs-dark.svg', markup)
        self.assertNotIn('<pre>', markup)
        self.assertNotIn('Public + private', markup)

    def test_interactive_page_preserves_all_daily_counts_in_both_themes(self):
        with tempfile.TemporaryDirectory() as tmp:
            build(Path(tmp))
            page = (Path(tmp) / 'index.html').read_text()
            snapshot = json.loads((Path(__file__).resolve().parents[1] / 'assets/merged-prs.json').read_text())
            for day, count in snapshot['counts'].items():
                self.assertEqual(page.count(f'{day}: {count} merged PRs</title>'), 2)
            self.assertIn('id="title-light"', page)
            self.assertIn('id="title-dark"', page)
            self.assertNotIn('__LIGHT_CHART__', page)
            self.assertNotIn('Public + private', page)
            self.assertEqual({p.name for p in Path(tmp).iterdir()}, {'index.html', '.nojekyll'})

    def test_refresh_preserves_handwritten_profile_and_rejects_missing_markers(self):
        original = 'Personal introduction\n<!-- PR-CHART:START -->\nold\n<!-- PR-CHART:END -->\nPersonal footer'
        self.assertEqual(replace_readme_chart(original, 'new'), original.replace('old', 'new'))
        with self.assertRaises(ValueError):
            replace_readme_chart('Personal introduction without markers', 'new')

    def test_bogota_midnight_boundaries_and_leap_day(self):
        query = search_for_day('Lespoir', date(2024, 2, 29))
        self.assertIn('is:pr is:merged author:Lespoir', query)
        self.assertIn('2024-02-29T05:00:00Z..2024-03-01T04:59:59Z', query)
        days = window(date(2024, 3, 1))
        self.assertEqual(len(days), 365)
        self.assertEqual(len(set(days)), 365)
        self.assertIn(date(2024, 2, 29), days)

    def test_counts_above_search_pagination_cap_and_count_only_query(self):
        def request(query):
            self.assertNotIn('nodes', query)
            self.assertNotIn('repository', query)
            return {'viewer': {'login': 'Lespoir'}, 'd0': {'issueCount': 1400}}
        counts = fetch_counts('Lespoir', [date(2026, 11, 20)], request, lambda _: None)
        self.assertEqual(counts, {'2026-11-20': 1400})

    def test_partial_fetch_does_not_replace_existing_chart(self):
        calls = 0
        def request(query):
            nonlocal calls
            calls += 1
            if calls == 2:
                raise RuntimeError('API unavailable')
            return {'viewer': {'login': 'Lespoir'}, **{f'd{i}': {'issueCount': 1} for i in range(14)}}
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp)
            original = output / 'merged-prs-light.svg'
            original.write_text('last successful chart')
            with self.assertRaises(RuntimeError):
                update('Lespoir', output, date(2026, 11, 20), request, lambda _: None)
            self.assertEqual(original.read_text(), 'last successful chart')
            self.assertEqual(list(output.iterdir()), [original])

    def test_missing_day_is_not_silently_zero(self):
        with self.assertRaises(RuntimeError):
            fetch_counts('Lespoir', [date(2026, 11, 20)],
                         lambda _: {'viewer': {'login': 'Lespoir'}}, lambda _: None)

    def test_wrong_account_rejected(self):
        with self.assertRaises(RuntimeError):
            fetch_counts('Lespoir', [date(2026, 11, 20)],
                         lambda _: {'viewer': {'login': 'someone-else'}}, lambda _: None)

    def test_svg_carries_exact_daily_counts_in_both_themes(self):
        counts = {d.isoformat(): (i % 30) for i, d in enumerate(window(date(2026, 11, 20)))}
        for dark in (False, True):
            svg = render_daily_svg(counts, 'Nov 20, 2026 16:00', dark)
            root = ET.fromstring(svg)
            ns = {'s': 'http://www.w3.org/2000/svg'}
            titles = root.findall('.//s:rect/s:title', ns)
            self.assertEqual(len(titles), 365)
            self.assertEqual(titles[-1].text, '2026-11-20: 4 merged PRs')
            self.assertIn(f'{sum(counts.values()):,} merged pull requests', svg)
            for rect in root.findall('.//s:rect', ns):
                self.assertLessEqual(float(rect.attrib['x']) + float(rect.attrib['width']), 760)
            self.assertNotIn('http://github', svg)

    def test_monthly_bars_preserve_totals_zero_months_and_partial_boundaries(self):
        for end in (date(2026, 11, 22), date(2026, 11, 30), date(2024, 2, 29)):
            counts = {d.isoformat(): i % 31 if d.month != 4 else 0
                      for i, d in enumerate(window(end))}
            expected = defaultdict(int)
            for day, count in counts.items():
                expected[day[:7]] += count
            for dark in (False, True):
                svg = render_svg(dict(reversed(list(counts.items()))), 'Nov 22, 2026 13:34', dark)
                root = ET.fromstring(svg)
                bars = root.findall('.//{http://www.w3.org/2000/svg}rect[@data-month]')
                self.assertEqual({bar.get('data-month'): int(bar.get('data-count')) for bar in bars}, expected)
                self.assertEqual(sum(int(bar.get('data-count')) for bar in bars), sum(counts.values()))
                self.assertIn(f'{sum(counts.values()):,} merged pull requests', svg)
                self.assertEqual(bars[0].get('data-partial'), str(window(end)[0].day != 1).lower())
                self.assertEqual(bars[-1].get('data-partial'), str(end.day not in (29, 30)).lower())
                for bar in bars:
                    self.assertLessEqual(float(bar.get('x')) + float(bar.get('width')), 730)
                    self.assertGreaterEqual(float(bar.get('y')), 88)
                    self.assertGreaterEqual(float(bar.get('height')), 0)

    def test_empty_activity_keeps_month_labels_and_zero_baseline(self):
        counts = {d.isoformat(): 0 for d in window(date(2026, 11, 22))}
        svg = render_svg(counts, 'Nov 22, 2026 13:34')
        root = ET.fromstring(svg)
        bars = root.findall('.//{http://www.w3.org/2000/svg}rect[@data-month]')
        self.assertEqual(len(bars), 13)
        self.assertTrue(all(float(bar.get('height')) == 0 for bar in bars))
        self.assertIn('0 merged pull requests', svg)


if __name__ == '__main__':
    unittest.main()
