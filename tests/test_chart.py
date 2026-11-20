from datetime import date
from pathlib import Path
import sys
import tempfile
import unittest
import xml.etree.ElementTree as ET
from html.parser import HTMLParser
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from update_chart import fetch_counts, render_svg, search_for_day, update, window, hover_chart, replace_readme_chart


class ChartTests(unittest.TestCase):
    def test_hover_titles_include_every_date_and_exact_count(self):
        counts = {d.isoformat(): (i % 30) for i, d in enumerate(window(date(2026, 11, 20)))}
        class Titles(HTMLParser):
            def __init__(self):
                super().__init__()
                self.days = []
            def handle_starttag(self, tag, attrs):
                title = dict(attrs).get('title', '')
                if tag == 'img' and ' on ' in title:
                    self.days.append(title)
        parser = Titles()
        parser.feed(hover_chart(counts, 'Nov 20, 2026 16:24'))
        expected = {f'{count:,} merged {"PR" if count == 1 else "PRs"} on {date.fromisoformat(day).strftime("%B")} {date.fromisoformat(day).day}, {date.fromisoformat(day).year}'
                    for day, count in counts.items()}
        self.assertEqual(len(parser.days), 365)
        self.assertEqual(set(parser.days), expected)

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
            svg = render_svg(counts, 'Nov 20, 2026 16:00', dark)
            root = ET.fromstring(svg)
            ns = {'s': 'http://www.w3.org/2000/svg'}
            titles = root.findall('.//s:rect/s:title', ns)
            self.assertEqual(len(titles), 365)
            self.assertEqual(titles[-1].text, '2026-11-20: 4 merged PRs')
            self.assertIn(f'{sum(counts.values()):,} merged pull requests', svg)
            for rect in root.findall('.//s:rect', ns):
                self.assertLessEqual(float(rect.attrib['x']) + float(rect.attrib['width']), 760)
            self.assertNotIn('http://github', svg)


if __name__ == '__main__':
    unittest.main()
