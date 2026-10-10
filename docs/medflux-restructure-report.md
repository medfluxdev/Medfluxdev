# Medflux — التقرير النهائي لإعادة التنظيم (Restructure + Ruhe & Signal)

التاريخ: 10 أكتوبر 2026 · الفرع: `design/ruhe-signal` · الخطة: `docs/architecture/MEDFLUX_RESTRUCTURE_PLAN_20261010.md` (v2.0)
سجل التقدم المفصل لكل مرحلة: `docs/medflux-restructure-progress.md`.

القرارات D1–D12 طُبّقت بالقيم الافتراضية المقترحة في الخطة. طلب المستخدم تنفيذ كل المراحل دون توقف، لذلك لم يُطبّق التوقف بعد كل مرحلة (D3)، لكن كل مرحلة اختُبرت وحُفظت في commit مستقل.

## 1. الهيكل النهائي للتنقّل

**السايدبار — «Arbeit»:** Mein Tag · Verträge · Fristen & Aufgaben · Geräte · Analysen
**السايدبار — «Daten & Verwaltung»:** Aktivitäten & Protokoll (للمحررين) · Stammdaten · Verwaltung (للمسؤول) · Entwicklung (للمطوّر فقط)
**الشريط العلوي:** البحث، نطاق المستشفى، KI-Assistent، الجرس («Für mich» / «Arbeitsvorrat»)، قائمة الحساب.

| القديم | الجديد |
|---|---|
| Vertragsliste | Verträge → Bestand (`/register`) |
| Prüfungen (`/review`) | Verträge → Zu prüfen (`/register?ansicht=review`، إعادة توجيه بالمعاملات) |
| Archiv (`/archiv`) | Verträge → Archiv (`/register?ansicht=archive`) |
| Import | زر «Vertrag hinzufügen» → Aus Dokument (`/import`) / Manuell erfassen (`/contracts/new`) |
| Nachweise (`/nachweise`) | العقد → Dokumente → Nachweise (`/nachweise?contract=<id>` يعيد التوجيه؛ بدون عقد → Zu prüfen) |
| Postfach / Meine Wiedervorlage | Fristen & Aufgaben → Termine → Nur meine (`/fristen?ansicht=termine&nur=meine`) |
| Postfach / Benachrichtigungen | الجرس + `/postfach` = السجل الكامل «Benachrichtigungen» |
| Historie | Aktivitäten & Protokoll (`/audit` داخل تخطيط Verwaltung) |
| Entwicklung في AdminNav | مدخل واحد في السايدبار/Ctrl+K |

تبويبات ملف العقد (المفاتيح لم تتغير، الروابط القديمة صالحة): Übersicht · Vertragsdaten · Fristen & Aufgaben · Finanzen · Dokumente (Dokument · Nachweise · Prüfung · Anlagen · Korrekturen) · Verknüpfungen · Verlauf.

## 2. مصادر البيانات المشتركة (الملفات الفعلية)

| المفهوم | المصدر الواحد |
|---|---|
| المجاميع المالية مع التغطية | `backend/app/reports/grid.py` (`MoneyTotals`, `money_totals`) → القائمة، المجموعات، Excel، `reports/exports.py:portfolio` (Mein Tag، Analysen) |
| «laufend» | `backend/app/register/status.py:is_running` |
| حالة المدة / غير قابل للتقييم | عمود `term_status` في `grid.py`؛ `reports/renewal.py:not_evaluable` |
| اليوم المرجعي | `backend/app/core/clock.py:today_local` (`ORG_TIMEZONE`) |
| «مواعيدي» | `backend/app/deadlines/service.py:owned_deadline_condition` |
| عدد غير المقروء / Arbeitsvorrat | `deadlines.service.unread_count`، `api/routes/notifications.work_queue_count`، `GET /api/inbox/summary` |
| أعداد تبويبات العقود | `GET /api/register/grid/counts` |
| ربط المورّد بالشريك | `register/catalogs.unlinked_suppliers` + `POST /api/catalogs/partners/link-supplier` (عبر `update_register`) |
| تسميات الحقول في السجل | `history/service.field_labels` (من `register/fields.FIELDS`) |
| حماية الإرسال المزدوج | `contracts/review/service.record_fact_action`، `contracts/overrides/service.record_override` |
| واجهة: الإشارات | `frontend/components/ui/Signal.tsx`؛ المبالغ مع التغطية `CoverageValue.tsx`؛ إعادة التوجيه `lib/redirect-params.ts` |

## 3. تفسير الملاحظات المرئية وما أُصلح

| الملاحظة | السبب في الكود | الإصلاح |
|---|---|---|
| Impella 8.000 € في التفاصيل، 0 € في القائمة/التحليلات | الرأس يعرض قيمة الاستخراج كأنها معتمدة؛ القائمة والمؤشرات تعتمد فقط على البنود المالية المُدخلة؛ المجهول يُجمع كصفر | الرأس يفصل «Gepflegt» عن «KI-Vorschlag» مع «In Finanzen übernehmen»؛ كل مجموع يحمل التغطية؛ المجهول «—» |
| 3 عقود بلا نهاية مع «Alles entschieden» | `renewal.py` يتجاهل العقود بلا موعد إلغاء؛ `no_end` يعدّ غير محدد المدة أيضاً | `not_evaluable` ولافتات صريحة؛ `no_end` = بيانات مدة ناقصة فقط |
| الجرس 1، Postfach 0 | العداد يجمع Arbeitsvorrat المؤسسة (بلا حالة قراءة) مع غير المقروء الشخصي | الشارة = غير المقروء الشخصي فقط بنفس الاستعلام والنطاق؛ Arbeitsvorrat قسم مستقل |
| ABIOMED/GE مع 0 شركاء | الاستخراج يكتب اسم المورّد نصاً، ولا شيء يربطه بسجل شريك | قائمة «Lieferanten zuordnen» باقتراحات وربط جماعي عند الطلب فقط |
| In Arbeit مقابل Laufende Verträge | المؤشر كان يعدّ in_arbeit والعقود المنتهية | تعريف واحد للسريان؛ in_arbeit يُعرض منفصلاً |
| Konfidenz 100% وموضع غير محدد | الثقة والموضع والاعتماد البشري غير مسماة بوضوح | «KI-Konfidenz»، «Lage»، والاعتماد البشري في «Prüfung» منفصلة |
| Verwaltung: 0 مستخدمين | العد = عضويات المؤسسة؛ حساب المطوّر بلا عضوية | التسمية «Mitglieder dieser Organisation» مع توضيح (لا تغيير في الصلاحيات) |
| Historie تقنية | `context_data` خام ومفاتيح إنجليزية | تسميات ألمانية من حقول السجل والتفاصيل التقنية قابلة للفتح |
| صفحات مكررة | ثلاث صفحات حول نفس المكوّن؛ Nachweise نسخة من ملف العقد | تبويبات + إعادة توجيه؛ حذف `SourceLink` (لم يعد مستخدماً) |

## 4. التعريفات وتغييرات السلوك المقصودة

- **Laufend:** gueltig أو gekuendigt وضمن مدة العقد في اليوم المرجعي. in_arbeit لا يُعدّ ساريّاً (يظهر «N in Arbeit»).
- **المجاميع:** مجموع القيم المعروفة باليورو فقط؛ null إن لم يُعرف شيء؛ العملات الأخرى منفصلة (لم تعد تُجمع كيورو)؛ التغطية «bekannt für N von M».
- **اليوم المرجعي:** بتوقيت `Europe/Berlin` بدل توقيت الخادم.
- **«Nur meine»:** مُسند إليّ، أو بلا إسناد وأنا المسؤول، بما في ذلك النيابة (كان: الإسناد فقط).
- **«Alle als gelesen»:** ضمن النطاق الظاهر فقط.
- **الإرسال المزدوج:** نفس الإجراء من نفس الشخص خلال 30 ثانية لا يُكرر؛ `expected_reviewed_at` القديم → 409.
- **الاستيراد:** مستشفى فعلي مطلوب عند وجود مستشفيات.
- **الإشارات:** حالة العمل والحالات الطبيعية رمادية؛ الأخضر للمؤكَّد فقط؛ كل إشارة لون + شكل + كلمة.

## 5. الاختبارات والأوامر المنفذة فعلاً

- **Backend:** pytest على Postgres 18 مؤقت في Docker (لا يوجد WSL cluster على هذا الجهاز). خط الأساس: 1577 ناجحاً + 8 حالات بيئية. النهائي، بعد نسخ `.github` و `scripts` إلى الحاوية المؤقتة كي تجد الاختبارات ملفات المستودع: **1603 ناجحاً، 3 متخطاة، 0 فاشلة** (الحزمة كاملة دون استثناء).
- **اختبارات جديدة:** `test_restructure_data_truth.py`، `test_restructure_notifications.py`، `test_restructure_review_idempotency.py`، `test_restructure_supplier_link.py`؛ Vitest: `coverage-value`، `signal`، `restructure-register`، `restructure-deadlines`، `review-queue`، `nachweise-redirect`، `my-day` (مُعاد).
- **Frontend:** `npm run verify` (lint + stylelint + Vitest + build) أخضر بعد كل مرحلة.
- **Playwright:** 174/174 (القسم 7).
- **مصفوفة T01–T30:** مغطاة في الاختبارات المذكورة في سجل التقدم؛ T04 (الضرائب/الدورية) و T06 (حدود الأشهر) تغطيها اختبارات `test_finance_calc.py` و `test_register_terms.py` الموجودة؛ T18 (تبديل النطاق) محلولة بإعادة تحميل الصفحة عند التبديل ولم يُضف اختبار جديد لها؛ T11 (دفعة بفشل جزئي) مغطاة باختبارات الاستيراد الحالية دون تعديل.

## 6. الترحيلات والمحافظة على البيانات

- **لا ترحيلات جديدة.** رأس Alembic ما زال `n5c7d9e01006`. حماية الإرسال المزدوج تمت دون تغيير المخطط.
- لم تُحذف أي بيانات أو حقول أو أحداث تدقيق. الأرشيف والاسترجاع والحذف بالآليات القائمة. معرّفات العقود والمستندات والعلاقات دون تغيير.
- إعداد جديد اختياري: `ORG_TIMEZONE` (افتراضي `Europe/Berlin`، يُتحقق منه عند الإقلاع، موثق في `.env.example`).
- الرجوع: كل مرحلة commit مستقل على `design/ruhe-signal`؛ `git revert <commit>` لمرحلة بعينها.

## 7. التحقق في المتصفح

Playwright على قاعدة مؤقتة (`medflux-e2e-pg`، المنفذ 55499): **174/174 ناجحاً** — فحص axe (فاتح/داكن/تباين Windows)، التخطيط على 1440/900/390 بكسل دون تمرير أفقي للصفحة، مسارات المستخدم، ومقارنة الصور (المراجع حُدّثت عمداً). اكتشف اختبار 390 بكسل تمدد الصفحة بسبب الجداول العريضة وأُصلح في `shell.css`.

## 8. قيود وملاحظات متبقية

- حُذف `components/SettingsNavigation.tsx` غير المستخدم (مع اختباره و CSS الخاص به) في المتابعة.
- محاكاة عمى الألوان (Protanopia/Deuteranopia/Achromatopsia) لم تُجرَ يدوياً في DevTools؛ التمييز مضمون بالشكل والكلمة لكل إشارة (اختبار `signal.test.tsx` يتحقق من اختلاف الأشكال الستة).
- استُبدلت الأسماء المستعارة القديمة `--accent`/`--muted` بالرموز الدلالية وحُذفت من `tokens.css`.
- لم يُنفذ push أو دمج.
