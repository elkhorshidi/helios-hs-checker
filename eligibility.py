"""Deterministic, source-aware matching of HS tariffs and company IDs.

Membership is NOT a legal approval, a current-rule check, or live government verification.
One tariff may belong to multiple source-specific pathways: never collapse them into one approval.
"""
from __future__ import annotations

import csv
import io
import json
import re
from collections import Counter
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent / 'data'
TARIFF_FILES = ('reference_codes.csv', 'metal_tariffs.csv')
COMPANIES_FILE = 'metal_companies.csv'
ROUTE_SOURCE_IDS = {
    'general': 'proposed-industry-general',
    'metals': 'metal-chain-hs-1403',
}
ROUTE_LABELS = {
    'all': 'بررسی همه مسیرها',
    'general': 'General — واردات در مقابل صادرات',
    'metals': 'Steel & Metals — زنجیره فولاد و فلزات',
}
DIGIT_MAP = str.maketrans('۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩', '01234567890123456789')
INVISIBLE = '\u200c\u200f\u200e\ufeff\u2060'


def normalize_digits(value: object) -> str:
    s = str(value if value is not None else '').translate(DIGIT_MAP).strip()
    for c in INVISIBLE:
        s = s.replace(c, '')
    if re.fullmatch(r'[0-9]+\.0+', s):
        s = s.split('.', 1)[0]
    return s.strip()


def normalize_hs(value: object) -> str:
    """Strict 8 digits, preserving leading zeroes; never pad/truncate."""
    s = normalize_digits(value)
    return s if re.fullmatch(r'[0-9]{8}', s) else ''


def normalize_identifier(value: object) -> str:
    """Accept exact, intact 8–11 digit entries from the supplied historical register.

    IDs of length <11 are flagged and never auto-padded. This is a lookup key,
    NOT an independent validation of an Iranian national/legal identifier.
    """
    s = normalize_digits(value)
    return s if re.fullmatch(r'[0-9]{8,11}', s) else ''


def normalize_search(value: object) -> str:
    return ' '.join(str(value if value is not None else '').replace('ي', 'ی').replace('ك', 'ک').replace('\u200c', ' ').split()).casefold()


def read_csv(path: Path) -> list[dict]:
    with path.open(encoding='utf-8-sig', newline='') as f:
        return list(csv.DictReader(f))


def load_data(data_dir: Path = DATA_DIR):
    """Return de-duplicated tariff records, source register and code→records index.

    Two duplicated metal HS values occur as Persian-digit trailing rows. They
    remain in the source CSV for audit but are collapsed for one-source matching.
    """
    with (data_dir / 'sources.json').open(encoding='utf-8') as f:
        sources = {s['source_id']: s for s in json.load(f)}
    by_code: dict[str, list[dict]] = {}
    records = []
    seen_source_code = set()
    for filename in TARIFF_FILES:
        path = data_dir / filename
        if not path.exists():
            continue
        for item in read_csv(path):
            code = normalize_hs(item.get('hs_code'))
            source_id = item.get('source_id')
            if not code or source_id not in sources:
                continue
            key = (source_id, code)
            if key in seen_source_code:
                continue
            seen_source_code.add(key)
            item = {**item, 'hs_code': code}
            records.append(item)
            by_code.setdefault(code, []).append(item)
    return records, sources, by_code


def load_companies(data_dir: Path = DATA_DIR):
    rows = read_csv(data_dir / COMPANIES_FILE)
    companies = []
    by_id: dict[str, list[dict]] = {}
    for row in rows:
        ident = normalize_identifier(row.get('national_id'))
        if not ident:
            continue
        item = {**row, 'national_id': ident}
        companies.append(item)
        by_id.setdefault(ident, []).append(item)
    return companies, by_id


def company_lookup(value: object, companies_by_id: dict) -> dict:
    original = str(value if value is not None else '').strip()
    if not original:
        return {'state': 'not_provided', 'label': 'شناسه متقاضی وارد نشده', 'companies': [], 'warning': ''}
    ident = normalize_identifier(original)
    if not ident:
        return {'state': 'invalid', 'label': 'شناسه باید ۸ تا ۱۱ رقم دقیق باشد (بدون صفرگذاری خودکار)', 'companies': [], 'warning': ''}
    hits = companies_by_id.get(ident, [])
    if not hits:
        return {'state': 'not_found', 'label': 'شناسه در فهرست تاریخی شرکت‌ها یافت نشد', 'companies': [], 'warning': ''}
    flags = [item['data_quality'] for item in hits if 'نیازمند بررسی' in item.get('data_quality','')]
    if flags:
        return {'state': 'needs_review', 'label': 'شناسه در فهرست ۱۴۰۳ وجود دارد، اما کیفیت شناسه نیازمند کنترل است', 'companies': hits, 'warning': '؛ '.join(dict.fromkeys(flags))}
    return {'state': 'found', 'label': 'شناسه در فهرست شرکت‌های مشمول ۱۴۰۳ ثبت شده', 'companies': hits, 'warning': 'صرف تطبیق با فهرست، اصالت شناسه یا مشمولیت جاری را اثبات نمی‌کند.'}


def assess_routes(input_code: object, by_code: dict, sources: dict, company_id: object = '', companies_by_id: dict | None = None, route_filter: str = 'all') -> list[dict]:
    if route_filter not in ROUTE_LABELS:
        raise ValueError('مسیر انتخاب‌شده تعریف نشده است')
    code = normalize_hs(input_code)
    if not code:
        return []
    company = company_lookup(company_id, companies_by_id or {})
    answer = []
    for record in by_code.get(code, []):
        if route_filter != 'all' and record['source_id'] != ROUTE_SOURCE_IDS[route_filter]:
            continue
        source = sources[record['source_id']]
        if record['source_id'] == 'metal-chain-hs-1403':
            states = {
                'not_provided': ('company_required', 'کد در فهرست فلزات ۱۴۰۳ است؛ شناسه شرکت واردکننده بررسی نشده'),
                'invalid': ('company_invalid', 'شناسه واردکننده نامعتبر است؛ انطباق توأمان قابل بررسی نیست'),
                'not_found': ('company_not_found', 'HS منطبق است، اما شناسه شرکت در فهرست ۱۴۰۳ یافت نشد'),
                'needs_review': ('company_needs_review', 'HS و شناسه در فهرست ۱۴۰۳ هستند؛ شناسه نیازمند راستی‌آزمایی است'),
                'found': ('historical_pair', 'HS و شناسه شرکت در فهرست ۱۴۰۳ هستند؛ صحت و اعتبار جاری احراز نشده'),
            }
            state, label = states[company['state']]
        else:
            state, label = ('proposed', 'تعرفه در فهرست پیشنهادی صنایع عمومی آمده؛ مجوز اجرایی اثبات نشده')
        answer.append({
            'source_id': record['source_id'], 'source_title': source['title'],
            'source_status': source['status'], 'source_date': source.get('date', ''),
            'hs_code': code, 'description': record.get('description',''),
            'department': record.get('department',''), 'restriction': record.get('restriction',''),
            'route': record.get('route',''), 'branch': record.get('branch','') or 'نامشخص',
            'state': state, 'label': label,
            'company_label': company['label'] if record['source_id'] == 'metal-chain-hs-1403' else 'برای این فهرست ملاک مستقلی ارائه نشده',
            'company_names': ' | '.join(x['company_name'] for x in company['companies']) if record['source_id'] == 'metal-chain-hs-1403' else '',
            'company_warning': company['warning'] if record['source_id'] == 'metal-chain-hs-1403' else '',
        })
    return answer


def assess(input_code: object, by_code: dict, sources: dict, company_id: object = '', companies_by_id: dict | None = None, route_filter: str = 'all') -> dict:
    if route_filter not in ROUTE_LABELS:
        raise ValueError('مسیر انتخاب‌شده تعریف نشده است')
    raw = str(input_code if input_code is not None else '').strip()
    code = normalize_hs(raw)
    base = {
        'ورودی': raw, 'کد استاندارد': code, 'نتیجه': '', 'شرح کالا': '',
        'اداره کل': '', 'بند ۱/۲': 'نامشخص', 'مسیر پیشنهادی': '',
        'محدودیت': '', 'فهرست منبع': '', 'وضعیت منبع': '',
        'شرکت متقاضی': str(company_id or ''), 'وضعیت تطبیق شرکت': '',
        'نتیجه ویژه فلزات': '',
    }
    if not code:
        return {**base, 'نتیجه': 'کد نامعتبر؛ باید دقیقاً ۸ رقم باشد', '_state': 'invalid', '_matches': [], '_routes': [], '_route_filter': route_filter}
    matches = [r for r in by_code.get(code, []) if route_filter == 'all' or r['source_id'] == ROUTE_SOURCE_IDS[route_filter]]
    if not matches:
        message = 'در فهرست‌های بارگذاری‌شده یافت نشد' if route_filter == 'all' else 'در فهرست مسیر انتخاب‌شده یافت نشد'
        return {**base, 'نتیجه': message, '_state': 'absent', '_matches': [], '_routes': [], '_route_filter': route_filter}
    routes = assess_routes(code, by_code, sources, company_id, companies_by_id, route_filter=route_filter)
    def distinct(field):
        return ' | '.join(dict.fromkeys(x.get(field, '').strip() for x in matches if x.get(field, '').strip()))
    if len(routes) > 1:
        state, message = 'multiple_sources', 'این کد در چند فهرست با شرایط مستقل ثبت شده؛ مسیرها را جداگانه بررسی کنید'
    elif routes[0]['state'] == 'proposed':
        state = 'proposed_conditional' if distinct('restriction') else 'proposed_match'
        message = 'در فهرست پیشنهادی وجود دارد؛ وضعیت مجاز بودن قطعی مشخص نیست'
    else:
        state = routes[0]['state']
        message = routes[0]['label']
    metals = next((x for x in routes if x['source_id'] == 'metal-chain-hs-1403'), None)
    return {
        **base, 'نتیجه': message, 'شرح کالا': distinct('description'),
        'اداره کل': distinct('department'), 'بند ۱/۲': distinct('branch') or 'نامشخص',
        'مسیر پیشنهادی': distinct('route'), 'محدودیت': distinct('restriction'),
        'فهرست منبع': ' | '.join(dict.fromkeys(sources[x['source_id']]['title'] for x in matches)),
        'وضعیت منبع': ' | '.join(dict.fromkeys(sources[x['source_id']]['status'] for x in matches)),
        'وضعیت تطبیق شرکت': metals['company_label'] if metals else 'وابسته به مسیر ویژه فلزات نیست',
        'نتیجه ویژه فلزات': metals['label'] if metals else 'تعرفه در فهرست ویژه فلزات موجود نیست',
        '_state': state, '_matches': matches, '_routes': routes, '_route_filter': route_filter,
    }


def format_assessment_row(result: dict, route_filter: str = 'all') -> dict:
    """Batch table/export: never collapse two independent eligibility routes.

    In all-routes mode, two distinct source-specific outcomes are always shown,
    including an explicit 'not in this list' outcome for nonmatching sources.
    """
    if route_filter not in ROUTE_LABELS:
        raise ValueError('مسیر انتخاب‌شده تعریف نشده است')
    if route_filter != 'all':
        row = {k: v for k, v in result.items() if not k.startswith('_')}
        if route_filter == 'general':
            for key in ('شرکت متقاضی', 'وضعیت تطبیق شرکت', 'نتیجه ویژه فلزات'):
                row.pop(key, None)
        return row

    outcome = {'ورودی': result['ورودی'], 'کد استاندارد': result['کد استاندارد']}
    route_by_source = {r['source_id']: r for r in result['_routes']}
    invalid = result['_state'] == 'invalid'
    for key, title in [('general', 'General'), ('metals', 'Steel & Metals')]:
        route = route_by_source.get(ROUTE_SOURCE_IDS[key])
        prefix = title + ' — '
        outcome[prefix + 'نتیجه'] = (
            route['label'] if route else
            'کد نامعتبر؛ باید دقیقاً ۸ رقم باشد' if invalid else
            'در فهرست این مسیر یافت نشد (نه به معنی ممنوعیت)'
        )
        outcome[prefix + 'شرح کالا'] = route['description'] if route else ''
        outcome[prefix + 'شرط'] = route['restriction'] if route else ''
        outcome[prefix + 'وضعیت منبع'] = route['source_status'] if route else ''
        outcome[prefix + 'تاریخ منبع'] = route['source_date'] if route else ''
        if key == 'metals':
            outcome[prefix + 'تطبیق شرکت'] = (
                route['company_label'] if route else
                'بررسی امکان‌پذیر نیست؛ کد HS در این فهرست یافت نشد'
            )
            outcome[prefix + 'نام شرکت'] = route['company_names'] if route else ''
    outcome['شناسه واردشده متقاضی'] = result['شرکت متقاضی']
    outcome['بند ۱/۲'] = 'نامشخص'
    return outcome


def split_codes(text: str) -> list[str]:
    return [x.strip() for x in re.split(r'[\s,;،؛]+', text or '') if x.strip()]


def decode_upload(data: bytes) -> str:
    for codec in ('utf-8-sig', 'utf-16', 'cp1256'):
        try:
            return data.decode(codec)
        except UnicodeError:
            continue
    raise ValueError('فایل متنی با کدگذاری قابل شناسایی نیست؛ آن را UTF-8 ذخیره کنید.')


def parse_uploaded_codes(filename: str, data: bytes) -> list[str]:
    text = decode_upload(data)
    if filename.lower().endswith('.txt'):
        return split_codes(text)
    if not filename.lower().endswith('.csv'):
        raise ValueError('فایل CSV یا TXT بارگذاری کنید.')
    table = list(csv.reader(io.StringIO(text)))
    if not table:
        return []
    headers = [re.sub(r'[ _\-\ufeff]', '', x).casefold() for x in table[0]]
    expected = {'hscode', 'hs', 'code', 'tariff', 'tariffcode', 'کدتعرفه', 'تعرفه', 'کدhs'}
    column = next((i for i, x in enumerate(headers) if x in expected), 0)
    starts = 1 if any(x in expected for x in headers) else 0
    return [str(row[column]).strip() for row in table[starts:] if len(row) > column and row[column].strip()]


def export_assessments_csv(results: list[dict]) -> bytes:
    fields = list(dict.fromkeys(k for row in results for k in row if not k.startswith('_')))
    out = io.StringIO()
    writer = csv.DictWriter(out, fieldnames=fields, extrasaction='ignore')
    writer.writeheader()
    writer.writerows(results)
    return out.getvalue().encode('utf-8-sig')


def state_summary(results: list[dict]) -> dict:
    c = Counter(x['_state'] for x in results)
    return {'total': len(results), 'matched': len(results)-c['invalid']-c['absent'],
            'conditional': sum(1 for x in results if any(r.get('restriction') for r in x.get('_routes',[])) or any(r.get('source_id') == 'metal-chain-hs-1403' for r in x.get('_routes', []))),
            'absent': c['absent'], 'invalid': c['invalid']}
