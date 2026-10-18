# انتقال نسخه V4 به Streamlit Cloud

آدرس فعلی اپ: https://helios-import-hs.streamlit.app/

## روش پیشنهادی با GitHub

1. ZIP نسخه V4 را Extract کنید.
2. فایل‌ها و پوشه‌های **داخل** `helios-hs-checker/` را در ریشه Repository فعلی جایگزین کنید. مخزن جدید لازم نیست.
3. مهم‌ترین فایل‌های تغییریافته: `app.py`، `ui_components.py`، `assets/theme.css`، `.streamlit/config.toml`، `README.md`، `requirements.txt`، `tests/test_ui_components.py` و `DEPLOY_V4.md`.
4. فایل‌های `data/` و `source/` باید باقی بمانند. نسخه V4 آن‌ها را عوض نکرده است.
5. Commit کنید (مثلاً پیام `Redesign Helios HS dashboard V4`).
6. وارد https://share.streamlit.io شوید و اپ فعلی را باز کنید. اگر به‌صورت خودکار آپدیت نشد، از Manage app، reboot/redeploy را اجرا کنید.
7. `Main file path` باید `app.py` باشد.

### اگر با git محلی کار می‌کنید

```bash
# داخل مخزن اصلی (همان مخزنی که به Streamlit متصل است)
git add app.py ui_components.py assets .streamlit requirements.txt tests README.md AGENTS.md DEPLOY_V4.md
git commit -m "Redesign Helios HS dashboard V4"
git push origin main
```

در صورت استفاده از شاخه‌ای غیر از `main`، نام شاخه را مطابق تنظیمات اپ اصلاح کنید.

## چک‌لیست پس از انتشار

- متن هدر، دکمه‌ها، تب‌ها، ورودی‌ها و کارت‌ها با Vazirmatn دیده شوند (دسترسی به Google Fonts لازم است).
- در حالت همه مسیرها کد `35069900` دو کارت مستقل نمایش دهد.
- کد `24011000` در General ثبت شده و در فلزات «یافت نشد» باشد.
- کد `25010020` در فلزات وجود داشته باشد ولی بدون شناسه، تطبیق شرکت کامل نباشد.
- همراه شناسه `14013029948` برای `25010020`، تطبیق تاریخی شرکت نشان داده شود، **نه تأیید مجوز جاری**.
- بخش CSV استعلام گروهی، نتیجه دو مسیر را در ستون‌های مستقل خروجی دهد.

## نکات عملیاتی

- تغییرات V4 مربوط به ظاهر و تجربه کاربری هستند، نه اصلاح داده‌ها یا مقررات جاری.
- برای محدودکردن دسترسی، از تنظیمات Streamlit / مخزن خصوصی و سیاست اشتراک مناسب استفاده کنید؛ Private کردن مخزن به‌تنهایی به معنی Private شدن اپ نیست.
- Google Fonts یک خدمت خارجی است و در صورت مسدودشدن، فونت جایگزین نمایش داده می‌شود.
