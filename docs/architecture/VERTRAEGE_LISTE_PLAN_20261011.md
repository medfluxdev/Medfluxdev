# صفحة «Verträge» – الخطة النهائية (مراجَعة مقابل الكود)

**التاريخ:** 2026-10-11 · **الأساس:** `Medflux-Vertraege-Claude-Code-Plan.md` (مبنية على صورة فقط) · **المرجع:** الفرع `feature/developer-hub-import-wizard` @ `74ea4c5`
**الحالة:** قيد التنفيذ على `feature/register-list-toolbar` – P0 ✅

---

## 1. مراجعة الخطة الأصلية

الخطة الأصلية سليمة في الهدف (ظهور البيانات مبكراً، حالة واحدة للفلاتر، عدم فقدان وظائف). لكنها كُتبت دون فحص المستودع، فبعض افتراضاتها لا تطابق الكود. التصحيحات:

| # | ما تفترضه الخطة | الواقع في الكود | التعديل في الخطة النهائية |
|---|---|---|---|
| 1 | الفلاتر وسلوكها مجهولان، وقد تحتاج محركاً أو حقولاً جديدة | يوجد محرك واحد: `GridSpec.filters` (`backend/app/reports/grid.py`) يُطبَّق **في الخادم** على كامل المجموعة المصرّح بها، 10 عمليات (`in`, `contains`, `range`, `within_days`, `due_within_days`, `overdue`, `empty`, `not_empty`, `me`, `is`) على 42 عموداً | **لا عمل في الخادم للفلاتر.** كل الفلاتر «المتقدمة» المطلوبة موجودة أصلاً (الجدول 3). العمل واجهة فقط |
| 2 | «Bearbeitungsstatus» يمثّل In Arbeit | `business_status` هو **حالة العقد** (`in_arbeit` → `gueltig` → `gekuendigt`/`beendet` → `geloescht`)، وحالة المعالجة/المراجعة شيء آخر (`review_pending`، تبويب «Zu prüfen») | التسمية تبقى **«Status»** كما في العمود الحالي؛ «Bearbeitungsstatus» مضلِّلة |
| 3 | فلتر الشريك يعتمد معرّف الشريك | المحرك يصفّي بالاسم المعروض (`partner` نصّي) | نُبقي الاسم (لا تغيير في المحرك لمجرد الواجهة)؛ الأسماء فريدة داخل المؤسسة في الكتالوج |
| 4 | محدد المستشفى العام قد يترك بيانات قديمة | تغيير النطاق يعيد تحميل الصفحة (`OrganizationScopePicker.tsx`)، فلا بيانات قديمة؛ **لكن الرابط يحتفظ بالفلاتر**، فقد يبقى فلتر قسم من المستشفى السابق ويُفرغ النتائج | خطوة صريحة: تحقّق من قيم Krankenhaus/Abteilung بعد التحميل مقابل الشجرة، وأزل غير الصالح مع إشعار |
| 5 | الملخص المالي يُنقل أسفل الجدول | المجاميع صحيحة أصلاً (الخادم، كامل النتائج المصفّاة، مع التغطية)؛ الصفحة 100 صف، فالملخص أسفلها لا يُرى عملياً | **نقترح العكس:** سطر نتائج واحد فوق الجدول: العدد + المجموعان مع التغطية عبر `CoverageValue` (القاعدة في CLAUDE.md)؛ لا شيء أسفل الجدول إلا الترقيم |
| 6 | «Kein Kostenwert erfasst» بدل الصفر | النص الحالي «— (keine gepflegten Kosten)»؛ الصفر المجهول غير ممكن أصلاً | توحيد النص مع `CoverageValue` فقط |
| 7 | حفظ الحالة عند العودة من العقد | البحث والفلاتر والفرز والتجميع والصفحة والعرض في الرابط؛ **الأعمدة و«Gelöschte einbeziehen» ليست في الرابط** فتضيع عند العودة إن لم تُحفظ كعرض | إضافة `spalten` و`geloescht` إلى الرابط (نفس آلية `writeUrlState`) |
| 8 | «Gelöschte einbeziehen» محمي في الخادم | **غير محمي**: أي قارئ (حتى viewer) يرى المحذوفات عبر `include_deleted` أو فلتر الحالة `geloescht`، ويوجد عرض نظامي عام «Gelöschte Verträge» لكل الأدوار | قرار المالك: حصرها بـ admin/contract_manager في الخادم (P0، القسم 6) |
| 9 | تصدير الصفحة/المحدد إن وُجد | يوجد تصدير Excel واحد لكل النتائج المطابقة، محمي بصلاحية `export` في الخادم ويُسجَّل في السجل | تسمية «Excel exportieren» تبقى؛ لا خيارات جديدة |
| 10 | إخفاء الشجرة الجانبية | الشجرة تعطي شيئين غير موجودين في غيرها: **الأعداد لكل مستشفى/قسم** و**«(ohne Krankenhaus/Abteilung)»** | فلتر «Abteilung» السريع يُبنى من بيانات الشجرة نفسها (`tree` في استجابة الشبكة): مجمَّع حسب المستشفى، مع الأعداد وقيم «ohne» |
| 11 | لا تُغيَّر الأعمدة المختارة للمستخدم | الأعمدة الافتراضية تأتي من `Column.default` في الخادم؛ العروض المحفوظة (ومنها النظامية المزروعة في القاعدة) تحمل أعمدتها | تغيير `default` يمسّ «Alle Verträge» فقط؛ العروض المحفوظة لا تتغير. زر «Standardspalten» للعودة |
| 12 | إغلاق القوائم بلوحة المفاتيح | لا يوجد مكوّن Popover/Menu في `components/ui/`؛ يوجد `Drawer` و`Dialog` | «Weitere Filter» في `Drawer` (التركيز وEsc مضمونان)؛ «Darstellung» قائمة منسدلة صغيرة مع Esc وإرجاع التركيز |
| 13 | معايير القبول على 1366×768 | اختبارات Playwright للتخطيط على 1440/900/390 | إضافة فحص: رأس الجدول وأول صف ظاهران على 1366×768 |

**إضافات لم تذكرها الخطة:**
- تبويبات **Zu prüfen** و**Archiv** تستعمل نفس `RegisterGrid` مع عرض ثابت ولا تُظهر «Ansicht»؛ التخطيط الجديد يجب أن يعمل فيها (عمود «Aktion»: Prüfen / Wiederherstellen).
- أعداد التبويبات **عامة للنطاق** (لا تتأثر بالفلاتر) و«Zu prüfen» **جزء من** «Bestand». يبقى ذلك ويُوضَّح في `title` للعدد؛ لا جمع.
- تغيير التبويب يمسح الفلاتر عمداً (تعليق في `app/register/page.tsx`) – يبقى.
- «Alle zurücksetzen» يعيد إلى فلاتر **العرض المختار** (مثلاً «Meine Verträge» تبقى `responsible = ich`)، كما يفعل `resetNarrowing` اليوم.
- البحث الحالي يشمل: Nr.، Kurzbeschreibung، Vertragspartner، Interne Nummer، Vertragstyp. الـ placeholder يذكر ذلك بدقة.
- أسماء الأقسام غير فريدة بين المستشفيات (الفلتر بالاسم): عند «Alle Krankenhäuser» يضيف اختيار قسم من الشجرة فلتر المستشفى معه (كما يفعل `pickTree` اليوم) فيبقى دقيقاً.

## 2. خريطة التنفيذ الفعلية (مخرج المرحلة الأولى)

| المجال | الملفات |
|---|---|
| الصفحة والتبويبات | `frontend/app/register/page.tsx` (تبويبات، أعداد `/api/register/grid/counts`، `AddContractMenu`) |
| القائمة كلها | `frontend/components/register/RegisterGrid.tsx` (540 سطراً: الحالة، الرابط، العروض، الشجرة، الأدوات، الجدول) |
| محرر الفلتر | `components/register/FilterEditor.tsx`، النصوص `components/register/filters.ts` |
| API الواجهة | `frontend/lib/domain-api/registerGrid.ts` |
| الأنماط | `frontend/app/contract-register.css` (`.reg-*`, `.rg-*`)، `app/styles/components.css:559` |
| الخادم | `backend/app/api/routes/register_grid.py` (grid, counts, values, tree, export)، `backend/app/reports/grid.py` (أعمدة، فلاتر، فرز، تجميع، مجاميع)، `backend/app/reports/views.py` (عروض نظامية/شخصية/عامة) |
| النطاق | `ScopeContext` middleware ← `scoped_contract_ids(org, hospital_id, department_id)` + الوثائق السرية؛ الواجهة تحقن النطاق عبر `scopedPath()` |
| الحالة | الرابط: `ansicht`, `sicht`, `q`, `filter` (JSON), `sort`, `gruppe`, `seite`؛ `localStorage` لآخر عرض (`medflux.register.lastView`) |
| الطلبات المتسابقة | علم `cancelled` في كل `useEffect` + تأخير 300ms للبحث – كافٍ |
| الاختبارات | `frontend/test/register-grid.test.tsx`، `restructure-register.test.tsx`، `e2e/journeys.spec.ts` (يستعمل «Filter hinzufügen»)، `backend/tests/test_register_grid.py` |

## 3. الفلاتر: موجود / يُعاد ترتيبه / ناقص

| الفلتر | الحالة | الشكل في الواجهة |
|---|---|---|
| Suche | موجود (خادم، 5 حقول) | حقل رئيسي في الشريط |
| Status (`business_status`, `in`) | موجود | فلتر سريع متعدد القيم |
| Vertragspartner (`partner`, `in`) | موجود، القيم من `/grid/values` (مع الأعداد، متتالية حسب باقي الفلاتر) | فلتر سريع مع بحث داخل القائمة |
| Abteilung (`hospital`+`department`, `in`) | موجود، القيم من الشجرة | فلتر سريع مجمّع حسب المستشفى، مع «ohne» |
| Verantwortlich (`responsible`: `me`/`in`/`empty`) | موجود | Weitere Filter (اختصار «Ich») |
| Vertragstyp (`in`) | موجود | Weitere Filter |
| Kündbar bis (`within_days`, `range`, `overdue`) | موجود | Weitere Filter، اختصار «nächste 30 Tage» = `within_days 30` |
| Jährliche Kosten (`range`; `empty` = unbekannt) | موجود؛ المجهول لا يدخل في `range` | Weitere Filter، خيار «Kosten unbekannt» منفصل |
| Fehlende Angaben (`empty` على hospital/department/partner/responsible/annual_cost) | موجود | Weitere Filter، قائمة اختصارات «ohne …» |
| Unbefristet ≠ fehlend | موجود: `term_status = Unbefristet`؛ «ohne Ende» ليس ضمن الاختصارات | — |
| Gelöschte einbeziehen | موجود، غير محمي (القسم 6) | داخل Weitere Filter → «Erweitert» |
| كل الأعمدة الأخرى | موجود عبر `FilterEditor` | Weitere Filter → «Weitere Bedingung» |
| **ناقص:** فلتر الشريك بالمعرّف | لا يُضاف (سبب: يتطلب تغيير المحرك والعروض المحفوظة) | — |

**قاعدة الحالة الواحدة:** كل المداخل تقرأ وتكتب `spec.filters` فقط. الفلتر السريع لعمود ما «يملك» أول فلتر `in` لذلك العمود؛ إن وُجد لنفس العمود شرط آخر (مثلاً `partner contains`) يظهر في الشرائح ويُعدّ مرة واحدة. عدد «Weitere Filter (n)» = عدد الشروط التي لا يعرضها فلتر سريع.

## 4. الشكل المستهدف

```text
Verträge                                              [Vertrag hinzufügen ▾]
Bestand 128 · Zu prüfen 12 · Archiv 4
[🔍 Nummer, Beschreibung, Partner, Typ …      ] [Ansicht: Alle Verträge ▾] [Weitere Filter (1)] [Darstellung ▾] [Excel exportieren]
[Status ▾] [Vertragspartner ▾] [Abteilung ▾]
Krankenhaus: Klinikum Nord ×  Status: Gültig ×  Kündbar bis in 30 Tagen ×   Alle zurücksetzen
128 Verträge · Jährliche Kosten 1.240.000 € (112 von 128 mit Kosten) · Kosten lfd. Jahr 980.000 €
┌ Vertrag ▲ / Nr. │ Vertragspartner │ Vertragstyp     │ Status │ Kündbar bis │ Jährliche Kosten (netto) ┐
│ Wartung MRT     │ Siemens         │ Wartungsvertrag │ Gültig │ 31.03.2027  │            12.000,00 €   │
│ 000004 (sekundär)                                                                                    │
└──────────────────────────────────────────────────────────────────────────────────────────────────────┘
                                           1–100 von 128   [Zurück] [Weiter]
```

- «Ansicht» قائمة واحدة: العروض + «Ansicht speichern» / «Speichern unter…» / «Ansicht löschen» في أسفلها.
- «Darstellung»: الأعمدة (مع «Standardspalten»)، التجميع بمستويين.
- العنوان المكرر «Alle Verträge» فوق الجدول يُحذف؛ يبقى عنوان مخفي للقارئات الشاشية.
- العرض على الهاتف: الشريط والفلاتر تلتف؛ التمرير الأفقي داخل `.reg-scroll` فقط.

## 5. حزم العمل

الفرع: `feature/register-list-toolbar` من الفرع الحالي. commit لكل حزمة. لا ترحيل، لا مكتبة جديدة.

**P0 – حماية المحذوفات في الخادم** (القرار 1 في القسم 6). تُنفَّذ أولاً لأنها تغيّر سلوك الصلاحيات وتُختبر مستقلة.

**P1 – تقسيم `RegisterGrid` دون تغيير السلوك**
استخراج `useRegisterState` (spec، الرابط، العروض، البحث، الصفحة) و`RegisterToolbar` و`RegisterTable` من الملف الحالي. الاختبارات الحالية تمرّ دون تعديل. هذا يجعل P2–P4 مراجَعة.

**P2 – الحالة الموحّدة والرابط**
- دوال صرفة في `components/register/filters.ts`: `quickFilterValue(spec, column)`, `setQuickFilter(spec, column, values)`, `advancedCount(spec)`, `resetToView(spec, view)`.
- الرابط: `spalten` (فقط إن اختلفت عن العرض) و`geloescht=1`.
- بعد تحميل الشجرة: إزالة قيم Krankenhaus/Abteilung غير الموجودة في النطاق الحالي مع رسالة «Filter … gilt im gewählten Bereich nicht und wurde entfernt.» (لا يُزال شيء إن فشل تحميل الشجرة).
- كل تغيير في البحث/الفلاتر/الفرز/التجميع يعود للصفحة الأولى (موجود في `update` – يُثبَّت باختبار).
- اختبارات Vitest للدوال الصرفة + سيناريوهات 3، 4، 5، 6، 11، 12.

**P3 – الشريط والفلاتر السريعة واللوحة**
- `QuickFilter` (زر + قائمة اختيار متعدد بمربعات، بحث داخلي للشريك، Esc وإرجاع التركيز).
- «Weitere Filter» في `Drawer`: الاختصارات (Verantwortlich، Vertragstyp، Kündbar bis 30 Tage، Kosten von–bis، Kosten unbekannt، «ohne …»)، `FilterEditor` الحالي لأي شرط آخر، و«Gelöschte einbeziehen».
- «Darstellung»: الأعمدة والتجميع و«Standardspalten».
- إزالة الشجرة الجانبية و`.reg-layout` بعمودين؛ الشرائح + «Alle zurücksetzen» + سطر النتائج.
- تحديث `e2e/journeys.spec.ts` ونصوص الاختبارات.

**P4 – الجدول والأعمدة الافتراضية**
- `backend/app/reports/grid.py`: `default=True` لـ `register_number`, `short_description`, `partner`, `contract_type`, `business_status`, `cancel_by`, `annual_cost` فقط (Mögliches Ende يبقى متاحاً). العروض المزروعة سابقاً لا تتأثر؛ يُتحقق من `test_register_grid.py`.
- عرض «Vertrag»: إن كان `short_description` و`register_number` ظاهرين يُدمجان في خلية واحدة (الوصف رابط، الرقم سطر ثانوي)؛ بدون وصف: «Vertrag 000004». رأس العمود يحمل زرّي فرز: «Vertrag» و«Nr.». البحث بالحقلين بلا تغيير.
- الرابط إلى العقد يبقى `<Link>` (فتح في تبويب جديد، لوحة المفاتيح)؛ المعاينة السريعة زر منفصل صغير.
- عرض الخلايا والتفاف النص في العرض الافتراضي قبل التمرير الأفقي.

**P5 – الملخص والتحقق والتوثيق**
- سطر النتائج بـ `CoverageValue` (القرار 2).
- Playwright: تخطيط 1366×768 و1920×1080 و390، axe فاتح/داكن/forced-colors، تحديث الصور المرجعية بعد المراجعة.
- Backend: `pytest` كاملاً (Docker Postgres المؤقت)؛ Frontend: `npm run verify`.
- تحديث `docs/PROJECT_PROGRESS.md` و`CLAUDE.md` (وصف `/register`) وهذا الملف.

## 6. قرارات المالك (2026-10-11)

1. **رؤية العقود المحذوفة (`geloescht`): `admin` و`contract_manager` فقط، مفروضة في الخادم.** حزمة إضافية **P0** قبل P1:
   - `register_grid.py`: لغير المحرّرين يُفرض `include_deleted=False`، وتُستبعد العقود المحذوفة من النتيجة بعد الفلترة في `grid` و`values` و`tree` و`export` (`_without_deleted`)؛ لا رفض 422 حتى لا تتعطل عروض محفوظة قديمة – فلتر الحالة «Gelöscht» يعطي ببساطة 0 نتائج. خيار «Gelöscht» لا يظهر في `/api/register/columns` لهم.
   - `views.py`: العرض النظامي «Gelöschte Verträge» (`system_key="deleted"`) لا يُعاد لغير المحرّرين.
   - الواجهة: الخيار في «Weitere Filter» يظهر فقط بصلاحية من `/api/permissions` (مفتاح جديد `contract.view_deleted` لـ `_EDITORS` في `permissions.py`، لا أدوار مكتوبة في الكود).
   - اختبارات خادم: viewer وreviewer لا يريان المحذوفات بأي مسار (خيار، فلتر حالة، عرض محفوظ قديم، رابط، تصدير)؛ admin وcontract_manager يرونها.
2. **المجاميع:** في سطر النتائج فوق الجدول، بـ `CoverageValue`.
3. **الأعمدة الافتراضية: ستة** – Vertrag (Kurzbeschreibung + Nr.)، Vertragspartner، Vertragstyp، Status، Kündbar bis، Jährliche Kosten (netto). Mögliches Ende يخرج من الافتراضي ويبقى في «Darstellung».

## 7. معايير القبول

السيناريوهات 1–18 من الخطة الأصلية تبقى، مع هذه التوضيحات:
- 6: يُختبر بإعادة تحميل الصفحة برابط يحمل قسماً من مستشفى آخر.
- 7 و15: تتبعان القرار 1؛ التصدير محمي اليوم بـ `export`.
- 8: «Kosten unbekannt» (`empty`) و`range 0–0` يعطيان مجموعتين مختلفتين.
- 9: عقد `Unbefristet` لا يظهر في أي اختصار «ohne …».
- 13: الأعداد لا تتغير بالفلاتر، و«Zu prüfen» ⊂ «Bestand».

خارج النطاق: بقية الصفحات، حالات العقود وقواعد الأرشفة، حساب التكلفة، فلترة الشريك بالمعرّف، أي push أو نشر.
