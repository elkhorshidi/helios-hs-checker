"""Pure, HTML-escaped presentation helpers for Helios V4.

No rules engine logic here: eligibility.py remains authoritative for route outcomes.
"""
from __future__ import annotations

from html import escape


def safe(value: object) -> str:
    return escape(str(value if value is not None else ''), quote=True)


def stat_card(label: str, value: str, note: str, symbol: str = '◆') -> str:
    return (
        '<div class="stat-card">'
        f'<div class="stat-top"><span class="stat-label">{safe(label)}</span>'
        f'<span class="stat-glyph" aria-hidden="true">{safe(symbol)}</span></div>'
        f'<div class="stat-number" dir="ltr">{safe(value)}</div>'
        f'<div class="stat-note">{safe(note)}</div>'
        '</div>'
    )


def section_header(eyebrow: str, title: str, subtitle: str = '') -> str:
    description = f'<p>{safe(subtitle)}</p>' if subtitle else ''
    return (
        '<div class="section-title">'
        f'<span class="eyebrow">{safe(eyebrow)}</span>'
        f'<h2>{safe(title)}</h2>{description}'
        '</div>'
    )


def status_meta(route: dict | None) -> tuple[str, str, str]:
    """Display classifications only, never a current-law 'approved' claim."""
    if route is None:
        return ('neutral', 'در این فهرست یافت نشد', 'نبودن کد در فهرست به معنای ممنوعیت واردات نیست.')
    state = route.get('state', '')
    if state == 'historical_pair':
        return ('historical', 'تطبیق تاریخی دوگانه', 'کد تعرفه و شناسه متقاضی در منابع ۱۴۰۳ دیده می‌شوند؛ اعتبار امروز احراز نشده است.')
    if state == 'proposed':
        return ('proposed', 'در فهرست پیشنهادی', 'این فهرست پیشنهادی است و مجوز اجرایی فعلی محسوب نمی‌شود.')
    if state == 'company_required':
        return ('attention', 'نیازمند شناسه متقاضی', 'تعرفه در فهرست فلزات وجود دارد؛ شناسه شرکت برای تطبیق دوم وارد نشده است.')
    if state == 'company_invalid':
        return ('attention', 'فرمت شناسه نامعتبر', 'شناسه واردشده با الگوی قابل جست‌وجوی فهرست همخوانی ندارد.')
    if state == 'company_not_found':
        return ('attention', 'شرکت در فهرست یافت نشد', 'کد تعرفه وجود دارد، اما این شناسه در فهرست تاریخی شرکت‌ها یافت نشده است.')
    if state == 'company_needs_review':
        return ('attention', 'شناسه نیازمند بررسی', 'تعرفه و شناسه ثبت شده‌اند، اما کیفیت شناسه باید کنترل شود.')
    return ('attention', 'نیازمند بررسی بیشتر', 'اطلاعات موجود برای نتیجه قطعی کافی نیست.')


def route_card(route_key: str, route: dict | None, source: dict, hs: str) -> str:
    """Build an independent result card; all source text is escaped."""
    is_metals = route_key == 'metals'
    accent, badge, hint = status_meta(route)
    title = 'زنجیره فولاد و فلزات' if is_metals else 'واردات در مقابل صادرات'
    latin_title = 'STEEL & METALS' if is_metals else 'GENERAL'
    marker = '02' if is_metals else '01'
    state = route.get('state', '') if route else 'absent'
    description = route.get('description') or 'شرح کالایی برای این مسیر در فهرست یافت نشد.' if route else 'کد در فهرست این مسیر ثبت نشده است.'
    restriction = route.get('restriction', '') if route else ''
    path = route.get('route', '') if route else ''
    company_label = route.get('company_label', '') if route else ''
    company_names = route.get('company_names', '') if route else ''
    company_warning = route.get('company_warning', '') if route else ''
    branch = route.get('branch', '') if route else ''
    source_title = source.get('title', '')
    source_date = source.get('date') or 'ثبت نشده'
    source_tag = 'پیشنهادی' if source.get('status') == 'proposed' else 'ابلاغ تاریخی'
    part = [
        f'<article class="result-card result-{safe(accent)}">',
        '<div class="result-head">',
        f'<div class="result-identity"><span class="result-index">{marker}</span><div>'
        f'<span class="result-overline">{safe(latin_title)}</span><h3>{safe(title)}</h3></div></div>',
        f'<span class="result-badge">{safe(badge)}</span>',
        '</div>',
        f'<div class="result-summary">{safe(hint)}</div>',
        '<div class="info-grid">',
        f'<div class="info-cell"><span>کد تعرفه</span><strong dir="ltr">{safe(hs)}</strong></div>',
        f'<div class="info-cell"><span>ماهیت منبع</span><strong>{safe(source_tag)}</strong></div>',
        '</div>',
        f'<div class="result-description"><span>شرح کالا</span><p>{safe(description)}</p></div>',
    ]
    if route is not None:
        if path:
            part.append(f'<div class="result-line"><b>مسیر منبع</b><span>{safe(path)}</span></div>')
        if branch and branch != 'نامشخص':
            part.append(f'<div class="result-line"><b>گروه درج‌شده</b><span>{safe(branch)}</span></div>')
        if restriction:
            part.append(f'<div class="inline-notice"><b>شرط اختصاصی تعرفه</b><span>{safe(restriction)}</span></div>')
        if is_metals:
            part.append(
                f'<div class="company-check"><span class="company-check-head">کنترل هویت متقاضی</span>'
                f'<p>{safe(company_label)}</p>'
                + (f'<small>نام در فهرست: {safe(company_names)}</small>' if company_names else '')
                + (f'<small>تذکر داده: {safe(company_warning)}</small>' if company_warning else '')
                + '</div>'
            )
    part += [
        f'<footer class="result-footer"><div><span>سند مرجع</span><strong>{safe(source_title)}</strong></div>'
        f'<span class="result-date">{safe(source_date)}</span></footer>',
        '</article>',
    ]
    return '\n'.join(part)


def source_card(source: dict) -> str:
    is_proposed = source.get('status') == 'proposed'
    badge = 'فهرست پیشنهادی' if is_proposed else 'مستند تاریخی ۱۴۰۳'
    tone = 'proposed' if is_proposed else 'historical'
    return (
        '<div class="source-card">'
        f'<span class="source-badge source-{tone}">{safe(badge)}</span>'
        f'<strong>{safe(source.get("title", ""))}</strong>'
        f'<p>{safe(source.get("scope", ""))}</p>'
        f'<span class="source-date">{safe(source.get("date", ""))}</span>'
        '</div>'
    )
