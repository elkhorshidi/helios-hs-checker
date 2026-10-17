"""Helios — route-specific HS and company checker (not a government live checker)."""
from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

import streamlit as st

from eligibility import (
    assess, assess_routes, format_assessment_row, company_lookup, export_assessments_csv,
    ROUTE_LABELS, ROUTE_SOURCE_IDS,
    load_companies, load_data, normalize_search, parse_uploaded_codes,
    split_codes, state_summary,
)

ROOT = Path(__file__).resolve().parent
st.set_page_config(page_title='Helios | HS & Companies', page_icon='🔎', layout='wide')
st.markdown('''<style>
html, body, [data-testid="stApp"], [data-testid="stAppViewContainer"] { direction:rtl; text-align:right; }
[data-testid="stSidebar"] { direction:rtl; text-align:right; }
.stTextInput input, .stTextArea textarea {direction:ltr;text-align:left;font-family:ui-monospace,monospace;}
.stMarkdown p, .stMarkdown li, .stMarkdown h1, .stMarkdown h2, .stMarkdown h3 {text-align:right;}
[data-testid="stMetricValue"] {direction:ltr;text-align:right;}
[data-testid="stDataFrame"] {direction:rtl;}
.hero {padding:20px 24px;border-radius:18px;background:linear-gradient(112deg,#0c2b47,#0e6072);color:#fff;margin-bottom:16px;}
.hero h2 {color:#fff;margin:0;font-size:1.6rem;} .hero p{color:#dcf7f7;margin:7px 0 0;}
</style>''', unsafe_allow_html=True)

@st.cache_data(show_spinner=False)
def bootstrap():
    records, sources, by_code = load_data()
    companies, by_company_id = load_companies()
    audit = json.loads((ROOT / 'data' / 'comparison_summary.json').read_text(encoding='utf-8'))
    return records, sources, by_code, companies, by_company_id, audit

records, sources, by_code, companies, by_company_id, audit = bootstrap()

st.markdown('<div class="hero"><h2>🔎 Helios | HS Eligibility & Metal Chain</h2><p>تطبیق کد تعرفه و شناسه متقاضی با فهرست‌های دارای منبع مشخص — بدون ادعای تأیید مجوز جاری</p></div>', unsafe_allow_html=True)
st.info('**حد اعتبار نتایج:** فهرست صنایع عمومی ماهیت پیشنهادی دارد؛ مسیر ویژه فلزات از نامه ۱۴۰۳ استخراج شده است. وضعیت روز ثبت سفارش و بند ۱/۲ از این داده‌ها احراز نمی‌شود.', icon='ℹ️')

with st.sidebar:
    st.markdown('### منابع داده')
    for source in sources.values():
        st.markdown('**'+source['title']+'**')
        if source['status'] == 'proposed':
            st.warning('پیشنهادی؛ اجرایی بودن تأیید نشده')
        else:
            st.caption('📄 مستند اداری تاریخی · '+source.get('date',''))
        st.caption(source.get('scope',''))
        st.divider()
    st.caption('Helios · Asha Speed | اطلاعات از فایل‌های آپلودشده؛ بدون اتصال به سامانه جامع تجارت')

stats = st.columns(5)
stats[0].metric('کل تعرفه‌های یکتا', f"{audit['total_codes']:,}")
stats[1].metric('تازه افزوده‌شده', f"{audit['new_codes']:,}")
stats[2].metric('کد مشترک در دو مسیر', audit['both'])
stats[3].metric('فهرست شرکت‌ها', f"{audit['company_rows']:,}")
stats[4].metric('شناسه نیازمند توجه', f"{audit['missing_id11']+audit['suspicious_placeholder']:,}")
st.caption('شناسه نیازمند توجه = ۳۴۸ مقدار کوتاه‌تر از ۱۱ رقم + ۲ شناسه ۱۱رقمی با ارقام کاملاً تکراری؛ ممکن است برخی موارد مربوط به اشخاص حقیقی باشند.')

st.markdown('#### انتخاب مسیر بررسی')
selected_route = st.radio(
    'مسیر واردات در مقابل صادرات',
    options=['all', 'general', 'metals'],
    format_func=lambda key: ROUTE_LABELS[key],
    horizontal=True,
    key='eligibility_route',
    label_visibility='collapsed',
)
if selected_route == 'all':
    st.caption('نتایج General و Steel & Metals جداگانه بررسی و نمایش داده می‌شوند؛ نبود تعرفه در یک مسیر، نتیجه مسیر دیگر را تغییر نمی‌دهد.')
elif selected_route == 'general':
    st.caption('فقط فهرست پیشنهادی ۳۶۸ تعرفه صنایع عمومی بررسی می‌شود؛ شناسه شرکت برای این مسیر شرط مستقل در داده‌های فعلی ندارد.')
else:
    st.caption('فقط فهرست ویژه فلزات بررسی می‌شود؛ تطبیق شناسه متقاضی علاوه بر کد تعرفه الزامی است. اعتبار کنونی منبع احراز نشده است.')

one, many, browse_hs, browse_co, references = st.tabs([
    '🔎 استعلام تعرفه و شرکت', '📋 استعلام چند تعرفه', '🗂️ مرور تعرفه‌ها',
    '🏢 فهرست شرکت‌ها', '📑 منابع و اعتبار داده',
])

with one:
    st.markdown('#### استعلام تکی HS در مسیر انتخابی')
    if selected_route == 'general':
        query = st.text_input('کد تعرفه وارداتی — ۸ رقم', placeholder='مثال: ۲۴۰۱۱۰۰۰', key='hs_single')
        firm = ''
    else:
        a, b = st.columns(2)
        with a:
            query = st.text_input('کد تعرفه وارداتی — ۸ رقم', placeholder='مثال: ۸۴۱۴۵۹۲۰', key='hs_single')
        with b:
            firm = st.text_input(
                'شناسه متقاضی برای مسیر فلزات — بدون صفرگذاری',
                placeholder='شناسه دقیق درج‌شده در فهرست (در حالت همه مسیرها اختیاری)',
                key='company_single',
            )
    if query.strip():
        result = assess(query, by_code, sources, firm, by_company_id, route_filter=selected_route)
        if result['_state'] == 'invalid':
            st.error(result['نتیجه'])
        else:
            st.markdown('##### کد استاندارد: `' + result['کد استاندارد'] + '`')
            # Show *every selected pathway*, even when only one of the two lists has the HS.
            route_keys = ('general', 'metals') if selected_route == 'all' else (selected_route,)
            for route_key in route_keys:
                source = sources[ROUTE_SOURCE_IDS[route_key]]
                scoped = assess(
                    query, by_code, sources,
                    firm if route_key == 'metals' else '',
                    by_company_id, route_filter=route_key,
                )
                with st.container(border=True):
                    st.markdown('##### ' + ROUTE_LABELS[route_key])
                    st.caption(
                        'منبع: ' + source['title'] + ' | تاریخ: ' + source.get('date', 'نامشخص') +
                        ' | ماهیت: ' + ('پیشنهادی' if source['status'] == 'proposed' else 'ابلاغ تاریخی')
                    )
                    if scoped['_state'] == 'absent':
                        st.info('کد در فهرست **این مسیر** یافت نشد؛ این به معنی ممنوعیت واردات یا رد دیگر مسیرهای تأمین ارز نیست.')
                        continue
                    route = scoped['_routes'][0]
                    if route['state'] == 'historical_pair':
                        st.info('کد HS و شناسه شرکت با فهرست‌های تاریخی ۱۴۰۳ تطبیق دارند؛ **مجوز جاری یا تأیید ثبت سفارش محسوب نمی‌شود.**')
                    elif route['state'] == 'proposed':
                        st.warning(route['label'])
                    else:
                        st.warning(route['label'])
                    st.markdown('**شرح کالا:** ' + (route['description'] or 'در منبع درج نشده'))
                    st.markdown('**مسیر ثبت‌شده در منبع:** ' + (route['route'] or 'نامشخص'))
                    if route['restriction']:
                        st.warning('شرط/محدودیت تعرفه: ' + route['restriction'])
                    if route_key == 'metals':
                        st.markdown('**نتیجه بررسی شناسه شرکت:** ' + route['company_label'])
                        if route['company_names']:
                            st.markdown('**نام در فهرست تاریخی:** ' + route['company_names'])
                        if route['company_warning']:
                            st.caption('⚠️ ' + route['company_warning'])
                        st.caption('شروط تکمیلی: مصرف مجاز کالا، هویت متقاضی، شرایط ثبت سفارش و اعتبار مقررات فعلی باید جداگانه احراز شوند.')
                    st.caption('بند ۱/۲: در منابع فعلی معلوم نیست.')
    elif firm.strip() and selected_route != 'general':
        lookup = company_lookup(firm, by_company_id)
        st.markdown('**وضعیت شناسه:** ' + lookup['label'])
        if lookup['companies']:
            st.dataframe(
                [{'نام': x['company_name'], 'شناسه': x['national_id'], 'کیفیت': x['data_quality']} for x in lookup['companies']],
                hide_index=True, use_container_width=True,
            )
        st.caption('بدون کد تعرفه نمی‌توان مسیر ویژه فلزات را بررسی کرد.')

with many:
    st.markdown('#### استعلام گروهی — در مسیر انتخابی')
    st.caption('مسیر انتخاب‌شده در بالای داشبورد برای همه ردیف‌ها اعمال می‌شود؛ در حالت همه مسیرها، نتایج در ستون‌های مستقل گزارش می‌شوند.')
    if selected_route != 'general':
        st.caption('یک شناسه متقاضی برای تمام کدهای وارداتی اعمال می‌شود؛ برای متقاضیان متفاوت جداگانه استعلام بگیرید.')
        firm_batch = st.text_input('شناسه متقاضی برای تمام ردیف‌ها (اختیاری، اما برای تطبیق کامل فلزات ضروری)', key='firm_batch')
    else:
        firm_batch = ''
    pasted = st.text_area(
        'کدها (کپی از اکسل / جداشده با خط جدید یا ویرگول)',
        height=150, placeholder='24011000\n84145920\n85444900\n99999999',
    )
    f = st.file_uploader('آپلود CSV یا TXT', type=['csv', 'txt'], key='codes_csv')
    codes = split_codes(pasted)
    if f is not None:
        try:
            codes += parse_uploaded_codes(f.name, f.getvalue())
        except ValueError as err:
            st.error(str(err))
    if len(codes) > 10000:
        st.error('حداکثر ۱۰٬۰۰۰ ردیف در هر نوبت')
    elif codes:
        results = [
            assess(q, by_code, sources, firm_batch, by_company_id, route_filter=selected_route)
            for q in codes
        ]
        if selected_route == 'all':
            general_hits = sum(any(r['source_id'] == ROUTE_SOURCE_IDS['general'] for r in x['_routes']) for x in results)
            metal_hits = sum(any(r['source_id'] == ROUTE_SOURCE_IDS['metals'] for r in x['_routes']) for x in results)
            both_hits = sum(len(x['_routes']) == 2 for x in results)
            c = st.columns(4)
            c[0].metric('تعداد استعلام', len(results))
            c[1].metric('در فهرست General', general_hits)
            c[2].metric('در فهرست Steel & Metals', metal_hits)
            c[3].metric('در هر دو مسیر', both_hits)
        else:
            summary = state_summary(results)
            c = st.columns(4)
            c[0].metric('تعداد', summary['total'])
            c[1].metric('در فهرست انتخابی', summary['matched'])
            c[2].metric('نیازمند بررسی شرایط', summary['conditional'])
            c[3].metric('نیافت‌شده/نامعتبر', summary['absent'] + summary['invalid'])
        table_rows = [format_assessment_row(x, selected_route) for x in results]
        st.dataframe(table_rows, hide_index=True, use_container_width=True)
        st.download_button(
            '⬇️ خروجی CSV نتایج مستقل',
            export_assessments_csv(table_rows),
            file_name='helios_hs_results_' + selected_route + '.csv',
            mime='text/csv',
        )
        st.caption('تطبیق تاریخی و حضور در فهرست به معنی مجاز بودن قطعی نیست. نبود تعرفه نیز دلیل ممنوعیت نیست.')

with browse_hs:
    st.markdown('#### جست‌وجوی کدهای تعرفه در فهرست‌های مرجع')
    q=st.text_input('جستجو در کد یا شرح',key='tariff_search')
    opts={'همه':'all','فقط پیشنهاد صنایع عمومی':'proposed-industry-general','فقط زنجیره فلزات':'metal-chain-hs-1403','مشترک دو فهرست':'overlap'}
    mode=st.selectbox('فهرست / تطبیق',list(opts))
    chosen=opts[mode]
    def keep(x):
        if chosen=='overlap':return len(by_code.get(x['hs_code'],[]))>1
        return chosen=='all' or x['source_id']==chosen
    visible=[r for r in records if keep(r) and (not q.strip() or normalize_search(q) in normalize_search(r['hs_code']+' '+r['description']))]
    st.caption(f'{len(visible):,} ردیف از {len(records):,} ردیف پس از حذف تکراری‌های درون هر منبع')
    st.dataframe([{'کد HS':r['hs_code'],'شرح':r['description'],'منبع':sources[r['source_id']]['title'],'شرط ردیف':r['restriction']} for r in visible[:1000]],hide_index=True,use_container_width=True)
    if len(visible)>1000:st.caption('فقط ۱۰۰۰ ردیف نخست نشان داده شده‌اند؛ جستجو را محدود کنید.')
    c=Counter(r['hs_code'][:2] for r in visible)
    if c:
        st.markdown('##### فراوانی فصل‌های HS در نتایج جستجو')
        st.bar_chart([{'فصل':chapter,'تعداد':count} for chapter,count in c.most_common(15)],x='فصل',y='تعداد',horizontal=True)

with browse_co:
    st.markdown('#### فهرست مشمولین اعلامی زنجیره فولاد و فلزات — ۱۴۰۳')
    st.warning('این داده شامل شناسه‌های متعلق به واحدهای تولیدی و برخی نام‌های اشخاص حقیقی است. برای انتشار عمومی و دسترسی کاربران باید سیاست محرمانگی اعمال شود.')
    term=st.text_input('جست‌وجو با نام شرکت یا شناسه (فارسی/عربی همسان‌سازی می‌شود)',placeholder='بخشی از نام یا شناسه',key='company_search')
    only_review=st.checkbox('فقط ردیف‌های نیازمند بررسی کیفیت شناسه')
    filt=[x for x in companies if (not term.strip() or normalize_search(term) in normalize_search(x['company_name']) or term.strip().translate(str.maketrans('۰۱۲۳۴۵۶۷۸۹','0123456789')) in x['national_id']) and (not only_review or 'نیازمند بررسی' in x['data_quality'])]
    st.caption(f'{len(filt):,} نتیجه؛ نمایش حداکثر ۳۰۰ ردیف')
    st.dataframe([{'ردیف منبع':x['row_number'],'نام واحد':x['company_name'],'شناسه':x['national_id'],'کنترل داده':x['data_quality']} for x in filt[:300]],hide_index=True,use_container_width=True)
    st.caption('شناسه‌ها بدون صفرگذاری یا حدس اصلاح شده‌اند. ۸ تا ۱۰ رقمی بودن می‌تواند نشان‌دهنده شناسه اشخاص یا افتادن صفر ابتدایی در فایل باشد؛ بررسی جداگانه ضروری است.')

with references:
    st.markdown('#### منبع، تاریخ و منطق عملیاتی')
    st.markdown('''**نامه کلیدی:** سازمان توسعه تجارت ایران، شماره **۴۱۲۹۱۷۷**، تاریخ **۱۴۰۳/۰۹/۱۳**؛ اعلام فهرست مشمولین و کدتعرفه‌های مجاز واردات از محل صادرات زنجیره فلزات. بر اساس تصمیم کارگروه بازگشت ارز حاصل از صادرات و نامه بانک مرکزی.

**کنترل‌های مندرج در مکاتبه:** معرفی شناسه‌های مشمول توسط وزارت صمت، معرفی کدهای منتخب، کنترل ثبت سفارش بر مبنای برنامه توسعه مربوط، نظارت بر فروش کالاهای منتخب در بورس کالا در موارد مقرر و محدودیت تخصیص از منابع بانکی برای شرکت‌های اعلامی (موضوع تصمیم سال ۱۴۰۳).

**تفکیک وضعیت منبع:**
- فهرست صنایع عمومی: **پیشنهادی** و فاقد گواهی اجرای قطعی در فایل.
- زنجیره فلزات: **فهرست ابلاغی تاریخی ۱۴۰۳** با شروط مستقل تعرفه و شناسه. اعتباریابی به تاریخ روز انجام نشده.
- **بند ۱/۲:** در این فایل‌ها برای همه تعرفه‌ها قابل استخراج قطعی نیست و باید با مرجع مجزای مصوب تکمیل شود.

داشبورد اتصال زنده به سامانه جامع تجارت، بانک مرکزی یا سامانه‌های ثبت سفارش ندارد.''')
    letter=next((p for p in (ROOT/'source').glob('*.pdf')),None)
    if letter:
        st.download_button('📄 دانلود اصل مکاتبه مرجع (PDF)',data=letter.read_bytes(),file_name='metal_chain_letter_1403.pdf',mime='application/pdf')
    st.markdown('##### گزارش کنترل کیفیت ورودی‌ها')
    st.json({
        'original_tariff_codes':audit['original_codes'],
        'metal_source_rows':2053,'metal_unique_codes':audit['metal_codes'],
        'metal_duplicate_after_normalization':2,
        'overlapping_tariffs':audit['both'],'all_unique_hs_codes':audit['total_codes'],
        'company_rows':audit['company_rows'],
        'identifier_lengths':audit['id_length_distribution'],
        'suspicious_repeated_digit_identifiers':audit['suspicious_placeholder'],
    },expanded=False)
