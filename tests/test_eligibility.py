import csv
import io
import unittest
from eligibility import (
    ROUTE_SOURCE_IDS, assess, assess_routes, format_assessment_row, company_lookup,
    export_assessments_csv, load_companies, load_data,
    normalize_hs, normalize_identifier, parse_uploaded_codes, split_codes,
    state_summary,
)

class HSTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.records, cls.sources, cls.index = load_data()
        cls.companies, cls.company_index = load_companies()

    def test_data_counts_and_deduplication(self):
        self.assertEqual(len(self.index), 2399)
        self.assertEqual(len(self.records), 368 + 2051)
        self.assertEqual(len(self.companies), 1996)
        self.assertEqual(len(self.index['84145920']), 1)
        self.assertEqual(len(self.index['85444900']), 1)
        self.assertEqual(len(self.index['35069900']), 2)

    def test_normalization(self):
        self.assertEqual(normalize_hs('۸۴۱۴۵۹۲۰'), '84145920')
        self.assertEqual(normalize_hs('  ۸۵۴۴۴۹۰۰'), '85444900')
        self.assertEqual(normalize_hs('٢٤٠١١٠٠٠'), '24011000')
        self.assertEqual(normalize_hs('24011000.0'), '24011000')
        self.assertEqual(normalize_hs('2401100'), '')
        self.assertEqual(normalize_hs('024011000'), '')
        self.assertEqual(normalize_identifier('14013029948'), '14013029948')
        self.assertEqual(normalize_identifier('99999999999'), '99999999999')
        self.assertEqual(normalize_identifier('12345'), '')

    def test_proposed_is_not_approved(self):
        r=assess('24011000',self.index,self.sources)
        self.assertEqual(r['_state'],'proposed_match')
        self.assertEqual(r['بند ۱/۲'],'نامشخص')
        self.assertIn('قطعی',r['نتیجه'])

    def test_general_restriction(self):
        r=assess('29054500',self.index,self.sources)
        self.assertEqual(r['_state'],'proposed_conditional')
        self.assertIn('دخانی',r['محدودیت'])

    def test_metal_tariff_needs_company(self):
        r=assess('25010020',self.index,self.sources)
        self.assertEqual(r['_state'],'company_required')
        self.assertIn('بررسی نشده',r['نتیجه'])

    def test_metal_company_pair_still_historical(self):
        r=assess('25010020',self.index,self.sources,'14013029948',self.company_index)
        self.assertEqual(r['_state'],'historical_pair')
        self.assertIn('جاری',r['نتیجه'])
        self.assertIn('فولاد الماس سبلان',r['_routes'][0]['company_names'])

    def test_company_not_in_historical_list(self):
        r=assess('25010020',self.index,self.sources,'14000000000',self.company_index)
        self.assertEqual(r['_state'],'company_not_found')

    def test_placeholder_flagged(self):
        l=company_lookup('99999999999',self.company_index)
        self.assertEqual(l['state'],'needs_review')
        self.assertIn('تکراری',l['warning'])

    def test_short_identifier_flagged_no_padding(self):
        l=company_lookup('84549866',self.company_index)
        self.assertEqual(l['state'],'needs_review')
        self.assertEqual(l['companies'][0]['national_id'],'84549866')

    def test_overlap_keeps_independent_routes(self):
        r=assess('35069900',self.index,self.sources,'14013029948',self.company_index)
        self.assertEqual(r['_state'],'multiple_sources')
        self.assertEqual(len(r['_routes']),2)
        self.assertEqual({x['state'] for x in r['_routes']},{'proposed','historical_pair'})

    def test_route_filters_do_not_leak_other_sources(self):
        both = assess('35069900', self.index, self.sources, '14013029948', self.company_index)
        general = assess('35069900', self.index, self.sources, '14013029948', self.company_index, route_filter='general')
        metals = assess('35069900', self.index, self.sources, '14013029948', self.company_index, route_filter='metals')
        self.assertEqual(len(both['_routes']), 2)
        self.assertEqual([r['source_id'] for r in general['_routes']], ['proposed-industry-general'])
        self.assertEqual([r['source_id'] for r in metals['_routes']], ['metal-chain-hs-1403'])
        self.assertEqual(general['_state'], 'proposed_conditional')
        self.assertEqual(metals['_state'], 'historical_pair')
        self.assertNotIn('فولاد', general['نتیجه'])

    def test_company_remains_required_in_metal_route(self):
        missing = assess('25010020', self.index, self.sources, route_filter='metals')
        matched = assess('25010020', self.index, self.sources, '14013029948', self.company_index, route_filter='metals')
        wrong = assess('25010020', self.index, self.sources, '14000000000', self.company_index, route_filter='metals')
        self.assertEqual(missing['_state'], 'company_required')
        self.assertEqual(matched['_state'], 'historical_pair')
        self.assertEqual(wrong['_state'], 'company_not_found')
        self.assertEqual(assess('25010020', self.index, self.sources, route_filter='general')['_state'], 'absent')

    def test_batch_results_independent_columns(self):
        row = assess('35069900', self.index, self.sources, '14013029948', self.company_index)
        formatted = format_assessment_row(row)
        self.assertIn('General — نتیجه', formatted)
        self.assertIn('Steel & Metals — نتیجه', formatted)
        self.assertIn('Steel & Metals — تطبیق شرکت', formatted)
        self.assertNotEqual(formatted['General — نتیجه'], formatted['Steel & Metals — نتیجه'])
        single = format_assessment_row(assess('35069900', self.index, self.sources, route_filter='general'), 'general')
        self.assertNotIn('General — نتیجه', single)
        self.assertNotIn('نتیجه ویژه فلزات', single)

    def test_batch_csv_keeps_independent_route_results(self):
        entries = [assess(code, self.index, self.sources, '14013029948', self.company_index)
                   for code in ('24011000', '25010020', '35069900', '99999999', '123')]
        rows = [format_assessment_row(x, 'all') for x in entries]
        self.assertIn('در فهرست این مسیر یافت نشد', rows[0]['Steel & Metals — نتیجه'])
        self.assertIn('در فهرست این مسیر یافت نشد', rows[1]['General — نتیجه'])
        self.assertIn('شناسه شرکت در فهرست ۱۴۰۳', rows[1]['Steel & Metals — نتیجه'])
        self.assertIn('پیشنهادی', rows[2]['General — نتیجه'])
        self.assertIn('شناسه شرکت در فهرست ۱۴۰۳', rows[2]['Steel & Metals — نتیجه'])
        self.assertIn('نامعتبر', rows[4]['General — نتیجه'])
        self.assertIn('نامعتبر', rows[4]['Steel & Metals — نتیجه'])
        csv_data = export_assessments_csv(rows).decode('utf-8-sig')
        parsed = list(csv.DictReader(io.StringIO(csv_data)))
        self.assertEqual(len(parsed), 5)
        self.assertIn('General — نتیجه', parsed[0])
        self.assertIn('Steel & Metals — تطبیق شرکت', parsed[0])

    def test_invalid_selected_route_rejected(self):
        with self.assertRaises(ValueError):
            assess('24011000', self.index, self.sources, route_filter='unknown')
        self.assertEqual(set(ROUTE_SOURCE_IDS), {'general', 'metals'})

    def test_absent_not_denial(self):
        r=assess('99999999',self.index,self.sources)
        self.assertEqual(r['_state'],'absent')

    def test_bulk_parsing_and_counts(self):
        self.assertEqual(split_codes('24011000, ۲۹۰۵۴۵۰۰\n99999999'),['24011000','۲۹۰۵۴۵۰۰','99999999'])
        self.assertEqual(parse_uploaded_codes('codes.csv',b'hs_code,company\n24011000,alpha\n25010020,beta\n'),['24011000','25010020'])
        results=[assess(c,self.index,self.sources) for c in ('24011000','25010020','99999999','123')]
        self.assertEqual(state_summary(results),{'total':4,'matched':2,'conditional':1,'absent':1,'invalid':1})

if __name__=='__main__':unittest.main()
