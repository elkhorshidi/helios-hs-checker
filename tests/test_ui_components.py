"""Regression checks for V4 results, XSS-safe data rendering and font setup."""
import sys
import tomllib
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from eligibility import assess, load_companies, load_data
from ui_components import route_card, source_card, stat_card, status_meta


class PresentationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.records, cls.sources, cls.index = load_data()
        cls.companies, cls.company_index = load_companies()

    def test_vazirmatn_configured_for_base_heading_and_code(self):
        cfg = tomllib.loads((ROOT / '.streamlit' / 'config.toml').read_text('utf-8'))
        self.assertTrue(cfg['theme']['font'].startswith('Vazirmatn:https://fonts.googleapis.com/'))
        self.assertEqual(cfg['theme']['headingFont'], 'Vazirmatn')
        self.assertEqual(cfg['theme']['codeFont'], 'Vazirmatn')
        self.assertEqual(cfg['theme']['sidebar']['font'], 'Vazirmatn')
        css = (ROOT / 'assets' / 'theme.css').read_text('utf-8')
        self.assertIn('Vazirmatn', css)
        self.assertIn('@media(max-width:750px)', css)

    def test_general_is_never_styled_as_approved(self):
        route = assess('24011000', self.index, self.sources)['_routes'][0]
        token, caption, hint = status_meta(route)
        self.assertEqual(token, 'proposed')
        self.assertIn('پیشنهادی', caption)
        self.assertIn('مجوز', hint)

    def test_metals_keeps_company_check_in_card(self):
        scoped = assess('25010020', self.index, self.sources, '14013029948', self.company_index, route_filter='metals')
        route = scoped['_routes'][0]
        card = route_card('metals', route, self.sources[route['source_id']], '25010020')
        self.assertIn('result-historical', card)
        self.assertIn('کنترل هویت متقاضی', card)
        self.assertIn('1403/09/13', card)
        self.assertIn('فولاد الماس سبلان', card)
        self.assertNotIn('مجاز قطعی', card)

    def test_missing_company_is_attention_state(self):
        route = assess('25010020', self.index, self.sources, route_filter='metals')['_routes'][0]
        kind, badge, _ = status_meta(route)
        self.assertEqual(kind, 'attention')
        self.assertIn('شناسه', badge)

    def test_absent_route_is_neutral_not_banned(self):
        route = assess('24011000', self.index, self.sources, route_filter='metals')
        self.assertEqual(route['_routes'], [])
        html = route_card('metals', None, self.sources['metal-chain-hs-1403'], '24011000')
        self.assertIn('result-neutral', html)
        self.assertIn('ممنوعیت', html)

    def test_html_escapes_untrusted_text(self):
        hostile = '<script>alert("bad")</script>'
        fake = {
            'state': 'proposed', 'description': hostile,
            'restriction': '" onmouseover="X', 'route': '<b>unclean</b>',
            'branch': '', 'company_label': '', 'company_names': '', 'company_warning': ''
        }
        src = {'title': hostile, 'date': '1403/09/13', 'status': 'proposed', 'scope': hostile}
        html = route_card('general', fake, src, '24011000')
        self.assertNotIn(hostile, html)
        self.assertIn('&lt;script&gt;', html)
        self.assertIn('&quot;', html)
        self.assertNotIn('<b>unclean</b>', html)
        self.assertNotIn(hostile, source_card(src))
        self.assertNotIn(hostile, stat_card(hostile, '2', 'demo'))

    def test_cards_have_distinct_pathway_titles(self):
        g = route_card('general', None, self.sources['proposed-industry-general'], '99999999')
        m = route_card('metals', None, self.sources['metal-chain-hs-1403'], '99999999')
        self.assertIn('GENERAL', g)
        self.assertIn('STEEL &amp; METALS', m)
        self.assertNotEqual(g, m)


if __name__ == '__main__':
    unittest.main()
