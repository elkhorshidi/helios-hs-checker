"""Helios | HS Eligibility Checker V4.

Presentation redesign only. Eligibility and source interpretation remain in eligibility.py.
This is a historical-list membership checker, not a live trade license service.
"""
from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

import streamlit as st

from eligibility import (
    ROUTE_LABELS, ROUTE_SOURCE_IDS,
    assess, export_assessments_csv, format_assessment_row,
    load_companies, load_data, normalize_search, parse_uploaded_codes,
    split_codes, state_summary,
)
from ui_components import route_card, safe, section_header, source_card, stat_card

ROOT = Path(__file__).resolve().parent
st.set_page_config(
    page_title='Helios | HS Eligibility',
    page_icon='🔎',
    layout='wide',
    initial_sidebar_state='expanded',
)
st.markdown('<style>' + (ROOT / 'assets' / 'theme.css').read_text(encoding='utf-8') + '</style>', unsafe_allow_html=True)


@st.cache_data(show_spinner=False)
def bootstrap():
    records, sources, by_code = load_data()
    companies, by_company_id = load_companies()
    audit = json.loads((ROOT / 'data' / 'comparison_summary.json').read_text(encoding='utf-8'))
    return records, sources, by_code, companies, by_company_id, audit


records, sources, by_code, companies, by_company_id, audit = bootstrap()


def md(html: str) -> None:
    st.markdown(html, unsafe_allow_html=True)


def page_header(section: str, title: str, description: str = '') -> None:
    md(section_header(section, title, description))


def show_table(rows: list[dict], *, max_height: int = 440) -> None:
    st.dataframe(rows, hide_index=True, use_container_width=True, height=max_height)


with st.sidebar:
    md('''<div class="sidebar-brand"><span class="brand-icon">H</span>
        <strong>Helios Intelligence</strong><span>HS Eligibility · نسخه ۴</span></div>''')
    st.markdown('##### منابع و مراجع')
    for source in sources.values():
        md(source_card(source))
    md('''<div class="sidebar-footer">این ابزار اطلاعات فهرست‌های بارگذاری‌شده را بررسی می‌کند؛
        به سامانه جامع تجارت یا سامانه‌های بانک مرکزی متصل نیست.<br>
        <strong>Asha Speed · Internal Trade Intelligence</strong></div>''')

md('''<div class="helios-hero">
    <div><span class="hero-overline">HELIOS / TRADE INTELLIGENCE</span>
    <h1>مرکز استعلام تعرفه‌های وارداتی</h1>
    <p>تطبیق کد HS با دو مسیر مستقل «واردات در مقابل صادرات» و «زنجیره فولاد و فلزات»
    همراه با بررسی شناسه متقاضی در مسیر فلزات.</p></div>
    <div class="hero-emblem" aria-hidden="true">HS</div>
    </div>''')
md('''<div class="helios-note"><span class="note-icon">ⓘ</span><div>
    <b>محدوده اعتبار داده‌ها:</b> فهرست General پیشنهادی است و داده فلزات به ابلاغ سال ۱۴۰۳ مربوط می‌شود.
    این ابزار مجاز بودن قطعی امروز، تخصیص ارز یا وضعیت بند ۱/۲ را تأیید نمی‌کند.
    </div></div>''')

stats = [
    ('کل کدهای HS یکتا', f"{audit['total_codes']:,}", 'در مجموع دو فهرست', 'HS'),
    ('کدهای تازه افزوده‌شده', f"{audit['new_codes']:,}", 'نسبت به فهرست General', '+'),
    ('اشتراک دو مسیر', str(audit['both']), 'تعرفه مشترک', '↔'),
    ('ردیف فهرست شرکت‌ها', f"{audit['company_rows']:,}", 'مرجع زنجیره فلزات', '▤'),
    ('شناسه‌های نیازمند کنترل', f"{audit['missing_id11']+audit['suspicious_placeholder']:,}", 'کیفیت داده؛ نه رد شرکت', '!'),
]
md('<div class="stats-grid">' + ''.join(stat_card(*s) for s in stats) + '</div>')
md('''<div class="tiny-note">۳۴۸ شناسه کمتر از ۱۱ رقم و ۲ شناسه با ارقام تکراری در فایل تاریخی
     وجود دارد. شناسه‌ها بدون تغییر یا صفرگذاری خودکار نگهداری شده‌اند.</div>''')

page_header('01  /  ROUTE SELECTION', 'مسیر بررسی را انتخاب کنید', 'نتیجه هر مسیر مستقل است و حضور تعرفه در فهرست، به‌تنهایی مجوز واردات محسوب نمی‌شود.')
route_options = ['all', 'general', 'metals']
route_short = {'all': 'همه مسیرها', 'general': 'General — صادرات', 'metals': 'Steel & Metals — فلزات'}
if hasattr(st, 'segmented_control'):
    selected_route = st.segmented_control(
        'انتخاب مسیر استعلام',
        options=route_options,
        format_func=lambda x: route_short[x],
        default='all',
        selection_mode='single',
        key='eligibility_route',
        label_visibility='collapsed',
    ) or 'all'
else:
    selected_route = st.radio(
        'انتخاب مسیر استعلام', options=route_options,
        format_func=lambda x: route_short[x], horizontal=True,
        key='eligibility_route', label_visibility='collapsed',
    )
guidance = {
    'all': 'هر دو فهرست بررسی می‌شوند. در خروجی، نتیجه General و Steel & Metals جدا از یکدیگر نمایش داده می‌شود.',
    'general': 'فقط ۳۶۸ تعرفه پیشنهادشده صنایع عمومی بررسی می‌شود؛ در این منبع شرط مستقلی برای شناسه شرکت درج نشده است.',
    'metals': 'فقط ۲٬۰۵۱ کد ویژه زنجیره فلزات بررسی می‌شود؛ تطبیق شناسه متقاضی نیز لازم است.',
}
md(f'<div class="route-guidance">{safe(guidance[selected_route])}</div>')

one, many, browse_hs, browse_co, references = st.tabs([
    '🔎 استعلام تکی', '📋 استعلام گروهی', '▤ مرور تعرفه‌ها',
    '🏢 شرکت‌های مشمول', '📑 منابع و اعتبار',
])

# ─────────────────────────────────────────────────────────────── single ──
with one:
    page_header('CHECK  /  01', 'استعلام کد تعرفه', 'کد هشت‌رقمی را وارد کنید؛ در مسیر فلزات شناسه متقاضی نیز بررسی خواهد شد.')
    with st.form('single_check_form', clear_on_submit=False, border=True):
        c1, c2 = st.columns([1, 1])
        with c1:
            query = st.text_input('کد تعرفه وارداتی (۸ رقم)', placeholder='مثال: 35069900', key='hs_single')
        with c2:
            if selected_route == 'general':
                st.caption('در فهرست General، شناسه شرکت شرط مستقلی در داده فعلی ندارد.')
                firm = ''
            else:
                firm = st.text_input(
                    'شناسه متقاضی واردکننده', placeholder='مثال: 14013029948',
                    help='برای تطبیق کامل مسیر فلزات لازم است؛ در حالت همه مسیرها می‌توان خالی گذاشت.',
                    key='company_single',
                )
        submitted = st.form_submit_button('🔍 بررسی کد تعرفه', type='primary', use_container_width=True)
    if submitted:
        st.session_state['single_search'] = {'hs': query.strip(), 'company': firm.strip()}

    saved = st.session_state.get('single_search')
    if saved and saved.get('hs'):
        query_value = saved['hs']
        company_value = saved['company'] if selected_route != 'general' else ''
        result = assess(query_value, by_code, sources, company_value, by_company_id, route_filter=selected_route)
        if result['_state'] == 'invalid':
            st.error('کد تعرفه باید دقیقاً ۸ رقم (فارسی، عربی یا انگلیسی) باشد؛ هیچ صفر یا رقم اضافی خودکار اعمال نمی‌شود.')
        else:
            page_header('CHECK  /  RESULTS', 'نتیجه استعلام', 'این نمایش، تطبیق با داده‌های مرجع است؛ نه تأیید مجوز به تاریخ روز.')
            route_keys = ('general', 'metals') if selected_route == 'all' else (selected_route,)
            cards = []
            for route_key in route_keys:
                route_result = assess(
                    query_value, by_code, sources,
                    company_value if route_key == 'metals' else '',
                    by_company_id, route_filter=route_key,
                )
                matched_route = route_result['_routes'][0] if route_result['_routes'] else None
                cards.append(route_card(route_key, matched_route, sources[ROUTE_SOURCE_IDS[route_key]], result['کد استاندارد']))
            layout_class = 'results-stack' + (' results-single' if len(cards) == 1 else '')
            md(f'<div class="{layout_class}">' + ''.join(cards) + '</div>')
            st.caption('اگر HS در فهرست نیامده باشد، صرفاً تطبیق آن با این فهرست ناموفق بوده و ممنوعیت واردات نتیجه نمی‌شود.')
    elif saved and not saved.get('hs'):
        st.warning('کد تعرفه را وارد کنید و سپس «بررسی کد تعرفه» را بزنید.')
    else:
        md('''<div class="empty-state"><span class="empty-illustration">⌕</span>
            <strong>هنوز استعلامی ثبت نشده است</strong>
            <p>کد تعرفه را وارد کنید تا وضعیت آن در مسیر یا مسیرهای انتخابی نمایش داده شود.</p></div>''')

# ─────────────────────────────────────────────────────────────── batch ──
with many:
    page_header('CHECK  /  02', 'استعلام گروهی تعرفه‌ها', 'کدها را از اکسل کپی کنید یا فایل CSV/TXT بارگذاری کنید؛ تا ۱۰٬۰۰۰ ردیف در هر نوبت.')
    with st.form('batch_check_form', clear_on_submit=False, border=True):
        if selected_route != 'general':
            firm_batch = st.text_input('شناسه متقاضی مشترک برای همه کدها (اختیاری)', key='firm_batch')
        else:
            firm_batch = ''
        pasted = st.text_area(
            'فهرست کدها (هر ردیف یک کد یا جداشده با کاما)',
            height=120, placeholder='24011000\n25010020\n35069900\n99999999',
            key='batch_codes',
        )
        uploaded = st.file_uploader('فایل CSV یا TXT', type=['csv', 'txt'], key='batch_file')
        run_batch = st.form_submit_button('📋 اجرای استعلام گروهی', type='primary', use_container_width=True)
    if run_batch:
        codes = split_codes(pasted)
        if uploaded is not None:
            try:
                codes += parse_uploaded_codes(uploaded.name, uploaded.getvalue())
            except ValueError as exc:
                st.error(f'فایل قابل پردازش نیست: {exc}')
                codes = []
        if len(codes) > 10_000:
            st.error('حداکثر ۱۰٬۰۰۰ کد در هر نوبت قابل بررسی است.')
        elif not codes:
            st.warning('ابتدا چند کد وارد یا یک فایل معتبر بارگذاری کنید.')
        else:
            st.session_state['batch_search'] = {'codes': codes, 'company': firm_batch}
    batch_saved = st.session_state.get('batch_search')
    if batch_saved:
        results = [assess(code, by_code, sources, batch_saved['company'] if selected_route != 'general' else '', by_company_id, route_filter=selected_route)
                   for code in batch_saved['codes']]
        if selected_route == 'all':
            general_hits = sum(any(r['source_id'] == ROUTE_SOURCE_IDS['general'] for r in x['_routes']) for x in results)
            metal_hits = sum(any(r['source_id'] == ROUTE_SOURCE_IDS['metals'] for r in x['_routes']) for x in results)
            both_hits = sum(len(x['_routes']) == 2 for x in results)
            values = [('کد بررسی‌شده', len(results)), ('General', general_hits), ('Steel & Metals', metal_hits), ('مشترک', both_hits)]
        else:
            summary = state_summary(results)
            values = [('کد بررسی‌شده', summary['total']), ('در فهرست', summary['matched']),
                      ('نیازمند بررسی', summary['conditional']), ('نیافت‌شده / نامعتبر', summary['absent'] + summary['invalid'])]
        st.markdown('##### خلاصه نتایج')
        cols = st.columns(4)
        for c, (name, value) in zip(cols, values):
            c.metric(name, f'{value:,}')
        table_rows = [format_assessment_row(x, selected_route) for x in results]
        show_table(table_rows, max_height=420)
        st.download_button(
            '⬇️ دریافت خروجی CSV', export_assessments_csv(table_rows),
            file_name=f'helios_hs_results_{selected_route}.csv', mime='text/csv',
            use_container_width=True,
        )
        st.caption('در حالت همه مسیرها نتایج دو مسیر در ستون‌های مستقل هستند. وجود کد در هر فهرست به معنی تأیید قطعی نیست.')
    else:
        md('''<div class="empty-state"><span class="empty-illustration">▤</span>
            <strong>استعلام گروهی آماده است</strong><p>یک یا چند HS وارد و دکمه بررسی گروهی را انتخاب کنید.</p></div>''')

# ─────────────────────────────────────────────────────────── browse HS ──
with browse_hs:
    page_header('LIBRARY  /  TARIFFS', 'کتابخانه کدهای تعرفه', 'کد، شرح کالا و منبع هر ردیف را به صورت مستقل مرور کنید.')
    q = st.text_input('جست‌وجو در کد تعرفه یا شرح کالا', placeholder='کد یا قسمتی از شرح کالا', key='tariff_search')
    opts = {'همه منابع': 'all', 'General': 'proposed-industry-general',
            'Steel & Metals': 'metal-chain-hs-1403', 'کدهای مشترک': 'overlap'}
    mode = st.selectbox('نمایش از منبع', list(opts), key='browse_mode')
    chosen = opts[mode]

    def keep(row: dict) -> bool:
        if chosen == 'overlap':
            return len(by_code.get(row['hs_code'], [])) > 1
        return chosen == 'all' or row['source_id'] == chosen

    visible = [r for r in records if keep(r) and (
        not q.strip() or normalize_search(q) in normalize_search(r['hs_code'] + ' ' + r['description'])
    )]
    st.caption(f'نمایش {min(len(visible), 1000):,} ردیف از {len(visible):,} نتیجه؛ رکوردهای تکراری داخل هر منبع حذف شده‌اند.')
    show_table([
        {'کد HS': r['hs_code'], 'شرح کالا': r['description'],
         'منبع': sources[r['source_id']]['title'], 'شرط اختصاصی': r['restriction']}
        for r in visible[:1000]
    ], max_height=465)
    if len(visible) > 1000:
        st.caption('برای نمایش دقیق‌تر، جست‌وجو را محدود کنید.')
    chapters = Counter(r['hs_code'][:2] for r in visible)
    if chapters:
        st.markdown('##### بیشترین فراوانی بر اساس فصل HS')
        # Native Streamlit chart inherits the configured Vazirmatn theme.
        st.bar_chart(
            [{'فصل HS': ch, 'تعداد تعرفه': count} for ch, count in chapters.most_common(12)],
            x='فصل HS', y='تعداد تعرفه', horizontal=True, color='#137688',
        )

# ─────────────────────────────────────────────────────── browse companies ──
with browse_co:
    page_header('LIBRARY  /  COMPANIES', 'شرکت‌های زنجیره فولاد و فلزات', 'جست‌وجوی شناسه و نام متقاضیان در فهرست اعلام‌شده سال ۱۴۰۳.')
    st.info('فهرست شامل اطلاعات شرکت‌ها و برخی اشخاص حقیقی است؛ سطح دسترسی به این صفحه را برای انتشار عمومی بررسی کنید.')
    term = st.text_input('نام شرکت یا شناسه متقاضی', placeholder='نام یا شناسه ملی', key='company_search')
    only_review = st.checkbox('فقط شناسه‌های نیازمند بررسی کیفیت داده')
    digits_term = term.strip().translate(str.maketrans('۰۱۲۳۴۵۶۷۸۹', '0123456789'))
    filt = [x for x in companies if (
        not term.strip() or normalize_search(term) in normalize_search(x['company_name']) or digits_term in x['national_id']
    ) and (not only_review or 'نیازمند بررسی' in x['data_quality'])]
    st.caption(f'{len(filt):,} ردیف منطبق؛ نمایش حداکثر ۳۰۰ ردیف')
    show_table([
        {'ردیف منبع': x['row_number'], 'نام': x['company_name'],
         'شناسه': x['national_id'], 'کنترل داده': x['data_quality']}
        for x in filt[:300]
    ], max_height=475)
    st.caption('شناسه‌های کوتاه‌تر از ۱۱ رقم بدون حدس یا صفرگذاری تغییر داده نشده‌اند؛ بررسی اصالت جداگانه ضروری است.')

# ───────────────────────────────────────────────────────────── sources ──
with references:
    page_header('SOURCES  /  COMPLIANCE', 'منابع داده و محدودیت اعتبار', 'شفافیت درباره منبع و تاریخ داده، بخشی از نتیجه هر استعلام است.')
    st.markdown('''**مرجع تاریخی فلزات:** نامه سازمان توسعه تجارت ایران شماره **۴۱۲۹۱۷۷** مورخ **۱۴۰۳/۰۹/۱۳**
    درخصوص فهرست شناسه‌های ملی مشمول و کدتعرفه‌های مجاز واردات از محل صادرات زنجیره فلزات.

    **شروط اعلام‌شده در مکاتبات:** معرفی شناسه‌های مشمول توسط وزارت صمت، کد تعرفه‌های منتخب،
    کنترل ثبت سفارش مرتبط با برنامه توسعه، و در موارد مقرر نظارت بر فروش اقلام منتخب در بورس کالا.

    **منبع General:** فهرست پیشنهادی معاونت صنایع عمومی است و سند قطعی اجرا یا تغییرات بعدی در این داده موجود نیست.

    **اعتبار جاری:** هیچ اتصال زنده‌ای به بانک مرکزی یا سامانه جامع تجارت وجود ندارد.
    همچنین وضعیت مصوب «بند ۱/۲» از فایل‌های فعلی برای همه تعرفه‌ها قابل استخراج قطعی نیست.''')
    letter = next((p for p in (ROOT / 'source').glob('*.pdf')), None)
    if letter:
        st.download_button('📄 دریافت مکاتبه فلزات (PDF)', letter.read_bytes(),
                           file_name='metal_chain_reference_1403.pdf', mime='application/pdf')
    with st.expander('گزارش کنترل کیفیت و آمار پایه', expanded=False):
        st.json({
            'general_tariff_codes': audit['original_codes'],
            'metal_source_rows': 2053, 'metal_unique_codes': audit['metal_codes'],
            'metal_duplicates_after_normalization': 2,
            'overlapping_tariffs': audit['both'],
            'all_unique_hs_codes': audit['total_codes'],
            'company_rows': audit['company_rows'],
            'identifier_lengths': audit['id_length_distribution'],
            'suspicious_repeated_digit_identifiers': audit['suspicious_placeholder'],
        }, expanded=False)
    st.caption('V4 یک تغییر در طراحی، تجربه کاربری و فونت است. موتور تطبیق و داده‌های دو مسیر تغییر نکرده‌اند.')
