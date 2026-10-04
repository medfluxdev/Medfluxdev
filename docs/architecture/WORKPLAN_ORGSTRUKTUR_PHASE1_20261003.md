# MedFlux — خطة عمل: الهيكل التنظيمي + أساسيات المرحلة الأولى
**المصدر:** وثيقتا المتطلبات `first-doc 26.09.2026.docx` و`هيكل التنظيمي للمؤسسة.docx` (قُرئتا كاملتين)  
**مرجع الكود:** `Desktop\Medflux` @ `0f1ac9b` على الفرع `fix/frankfurt-contract-analysis-20261001`  
**تاريخ:** 2026-10-03 · **الحالة:** WP0+WP1 منفَّذان ومختبَران (2026-10-03)؛ WP2–WP6 قيد التنفيذ · **المسار المقترح في المستودع:** `docs/architecture/WORKPLAN_ORGSTRUKTUR_PHASE1_20261003.md`

> منهج الخطة: كل متطلب في الوثيقتين حصل على رمز (A-x للوثيقة الأولى، B-x لوثيقة الهيكل)، ثم قورن بما هو موجود فعلاً في المستودع، ثم جُمعت الفجوات في حزم عمل تتبع سلسلة DoD المعتمدة في `docs/INTEGRATION_BASELINE.md`:
> `model/migration → backend API → authorization/scope → frontend domain API → UI states → audit → tests → documentation → CI verification`.

---

## 1. المتطلبات المستخلصة

### الوثيقة A — «المرحلة الأولى: الأساس الضروري»

| الرمز | المتطلب | تفاصيل مهمة من النص |
|---|---|---|
| A1 | استخراج آلي لحقول العقد الأساسية | الشركة، البداية/النهاية، السعر، المدة، مهلة الإلغاء، التجديد التلقائي، **دورية الدفع (سنوي/شهري)**، **دفع مقدم؟**، **المبلغ مع/بدون ضريبة مع حساب الحالتين لتوحيد النتائج**، **زيادة سنوية أم قيمة ثابتة** |
| A2 | تأكيد بشري قبل الاعتماد | مراجعة يدوية افتراضياً، خيار «تثبيت تلقائي» قابل للتفعيل، **شارة تحت كل حقل: يدوي / ذكاء اصطناعي / كلاهما أكّد القيمة نفسها** |
| A3 | المواعيد والتنبيهات | عقد ينتهي قريباً، آخر موعد إلغاء، تجديد تلقائي، **دفعة أو صيانة قادمة**؛ المستلم: المسؤول عن العقد في قسمه + **تصعيد اختياري** (رئيس القسم / شخص محدد)؛ القنوات: **إشعار داخل التطبيق أو بريد إلى عنوان المؤسسة الذي يضبطه المستخدم** |
| A4 | صورة العقود والتكاليف (تحليلات) | عدد العقود الفعّالة/المنتهية/القريبة من الانتهاء، التكلفة السنوية لكل عقد، المجموع، **التوزيع حسب القسم ونوع العقد والمورّد**، أعلى العقود تكلفة، العقود التي تتجدد تلقائياً/تحتاج قراراً، **تنقّل مؤسسة ← قسم ← عقد**، **رسوم بيانية** و**مساحة مخصصة للتحليل في الفرونت إند**، مقارنة بالماضي وتوقّع مستقبلي (لاحقاً) |

### الوثيقة B — «Organisationsstruktur»

| الرمز | المتطلب |
|---|---|
| B1 | شجرة: Einrichtung ← Krankenhaus (واحد أو أكثر) ← وحدات بعمق **غير محدود** |
| B2 | تسميات ألمانية لوصف الوحدة: Klinik / Abteilung / Bereich / Einheit / Station / Funktionsbereich / Kostenstelle (بدون فرض تسلسل موحّد) |
| B3 | قسم «Organisation» في شاشة الاستيراد: Krankenhaus، Verantwortlicher Bereich، Nutzender Bereich، Kostenstelle |
| B4 | بعد اختيار المستشفى تظهر وحداته فقط (قوائم متسلسلة) |
| B5 | أكثر من قسم مستفيد لنفس العقد + زر «+ Weiteren nutzenden Bereich hinzufügen» |
| B6 | عرض مسار الوحدة عند البحث: `Medizinische Klinik › Kardiologie › Herzkatheter` |
| B7 | ربط الوحدات بـ Kostenstellen، وأكثر من Kostenstelle للوحدة الواحدة |
| B8 | عند اختيار قسم تُعرض Kostenstellen المرتبطة به |
| B9 | البحث برقم Kostenstelle يُظهر القسم والمستشفى |
| B10 | صفحة `Einstellungen → Organisationsstruktur` بعرض شجري |
| B11 | إدارة: Einheit hinzufügen / Untereinheit hinzufügen / Kostenstelle hinzufügen / Bearbeiten / Aktivieren‑Deaktivieren |
| B12 | عرض المعلومات التنظيمية في تفاصيل العقد مع إمكانية التعديل |
| B13 | الأقسام مستقلة في الشجرة؛ **الدور (مسؤول/مستفيد) يُحدَّد على مستوى العقد فقط** |
| B14 | بساطة واجهة المستخدم: أربع قوائم اختيار فقط في الوضع الافتراضي |

---

## 2. تحليل الفجوة مقابل الكود الحالي

الحالة: ✅ منجز · 🟡 جزئي · ❌ مفقود · ❔ يحتاج تحققاً

| الرمز | الحالة | الدليل في المستودع | الفجوة المتبقية |
|---|---|---|---|
| B1 | ✅ | `backend/app/database/models/organization_structure.py`: `Hospital`, `Department(parent_id)`, `CostCenter`, `ContractDepartment(relation_role)`؛ ترحيلات `20260927_a1d3e5f70927_department_tree`, `20260928_a2b4c6d80928_contract_department_roles` | — |
| B2 | 🟡 | `Department` يحوي `name`, `code`, `is_active` فقط | لا يوجد حقل **نوع الوحدة** (`unit_type`: Klinik/Abteilung/Station…) |
| B3, B4, B5 | ✅ | `frontend/app/import/page.tsx` L216–240: قوائم Krankenhaus / Verantwortlicher Bereich / Nutzende Bereiche / Kostenstelle مع إعادة ضبط متسلسلة | تحقق من نص الزر الحرفي «+ Weiteren nutzenden Bereich hinzufügen» |
| B6 | ❔ | `frontend/lib/organization-tree.ts` موجود | التأكد من عرض المسار الكامل في القوائم ونتائج البحث |
| B7, B8 | 🟡 | `CostCenter.department_id` موجود؛ `cost_center_routes.py`: `GET` و`POST` فقط | لا `PATCH` (تعديل/تعطيل)، تصفية Kostenstellen حسب القسم المختار تحتاج تحققاً في الواجهة |
| B9 | ❌ | لا مسار بحث برقم Kostenstelle | API بحث + عرض القسم والمستشفى |
| B10 | ✅ | `frontend/app/settings/organization/page.tsx` + `components/settings/OrganizationStructureManager.tsx` | — |
| B11 | 🟡 | `organization_structure.py`: `POST/PATCH /hospitals`, `POST/PATCH /departments` | لا تعديل/تعطيل لـ Kostenstelle؛ التحقق من «Untereinheit hinzufügen» و«Aktivieren/Deaktivieren» في الواجهة |
| B12 | ✅ | `components/contracts/detail/ContractOwnershipPanel.tsx`؛ `ownership.py`: `GET/PUT /contracts/{id}/department-roles` | — |
| B13 | ✅ | الدور في `contract_department.relation_role` لا في الشجرة | — |
| B14 | 🟡 | الواجهة الحالية تطابق الأربع قوائم | مراجعة UX نهائية مع المستخدم |
| A1 | 🟡 | `docs/CONTRACT_SCHEMA.md`: `payment`, `costs`, `termination`, `period`؛ warnings تعرف `auto_renewal` | **غير موجود**: دورية الدفع صراحةً، دفع مقدم، صافي/إجمالي بحساب الحالتين، زيادة سنوية/تثبيت القيمة |
| A2 | 🟡 | `models/fact_review.py`, `models/review.py` (حقول `manual`, `reviewed`, `provenance`)؛ صفحة `/review` | **غير موجود**: خيار «تثبيت تلقائي» للمستخدم، شارة «كلاهما أكّد» عند تطابق اليدوي مع الذكاء الاصطناعي |
| A3 | 🟡 | محرك التحذيرات: `cancellation_deadline_{approaching,today,passed}`, `auto_renewal`, `renewal`؛ `/api/notifications` **إسقاط للقراءة فقط** من work items | **غير موجود**: تنبيهات دفعة/صيانة قادمة، قواعد المستلم والتصعيد، **البريد الإلكتروني (لا SMTP في الكود إطلاقاً)**، إعداد عنوان بريد المؤسسة |
| A4 | 🟡 | `dashboard.py` → `DashboardOverview` (kpis, deadlines, financial)؛ `reports.py /portfolio`؛ `intelligence_analytics.py` | **غير موجود**: التوزيع حسب القسم/النوع/المورّد، أعلى N تكلفة، التنقّل مؤسسة←قسم←عقد، **مكتبة رسوم بيانية** (غير موجودة في `package.json`)، صفحة `/analysen` مجرد هيكل (46 سطراً) |

**الخلاصة:** وثيقة B منجزة بنسبة تقارب 75% ويلزمها إكمال وتثبيت. وثيقة A منجزة في طبقة النماذج والتحذيرات، لكن **البريد الإلكتروني والتحليلات البصرية هما العملان الكبيران الباقيان**.

---

## 3. حزم العمل (Work Packages)

كل حزمة = فرع Git واحد، PR واحد، سطر في `docs/PROJECT_PROGRESS.md`، وتمرّ ببوابات CI (`pytest`, `npm run verify`, `release-gate`).

### WP0 — تثبيت الأرضية (يوم واحد) — **يسبق كل شيء**
| # | المهمة | الملفات | معيار القبول |
|---|---|---|---|
| 0.1 | اعتماد `backend/.env` المُستعاد والمُشغّل `START_MEDFLUX_PILOT.bat` (تم إنشاؤهما 2026-10-03) | `backend/.env` (غير متتبَّع)، `START_MEDFLUX_PILOT.bat` | نقرة واحدة تشغّل 55432 + 8000 + 3000 و`/ready` يعيد `database: ok` |
| 0.2 | تشغيل الحزمة الكاملة للاختبارات وتسجيل خط الأساس | `cd backend && pytest`؛ `cd frontend && npm run verify` | أرقام موثقة في PROJECT_PROGRESS (آخر مرجع: 1034 ناجح / 3 متخطى / 1 فشل بيئي موروث) |
| 0.3 | قرار الدفع: الـ 5 commits غير المرفوعة + حسم npm مقابل pnpm (تم في `d9c6f79`) | git | الفرع مرفوع بـ `git push -u origin` بقرار المالك |
| 0.4 | توثيق مصدر الحقيقة لقاعدة البيانات (55432 فقط للتجربة، 5432 لا يُلمس) | `docs/DATABASE_CONFIGURATION.md` | لا سكريبت يشير إلى 5432 بدون تحذير |

### WP1 — إكمال الهيكل التنظيمي (B2, B6–B9, B11) — 4 أيام — ✅ منفَّذ ومختبَر 2026-10-03 (انظر PROJECT_PROGRESS.md)
| # | المهمة | DoD stage | الملفات |
|---|---|---|---|
| 1.1 | إضافة `unit_type` (enum: einrichtung, krankenhaus, klinik, abteilung, bereich, einheit, station, funktionsbereich) إلى `department` + ترحيل Alembic جديد | model/migration | `models/organization_structure.py`, `alembic/versions/2026xxxx_<rev>_department_unit_type.py` |
| 1.2 | `PATCH /api/organization-structure/cost-centers/{id}` (تعديل، تفعيل/تعطيل) | backend API + authz | `api/routes/cost_center_routes.py` |
| 1.3 | `GET /api/organization-structure/search?q=471120` يعيد الوحدة + المسار الكامل + المستشفى (يبحث في اسم الوحدة ورقم Kostenstelle) | backend API | `api/routes/organization_structure.py`, خدمة جديدة `app/organization_structure/search.py` |
| 1.4 | عرض المسار `A › B › C` في كل قائمة اختيار وفي نتائج البحث | frontend domain API + UI | `lib/organization-tree.ts`, `app/import/page.tsx`, `ContractOwnershipPanel.tsx` |
| 1.5 | أزرار الإدارة الأربعة + حالات UI (فارغ/تحميل/خطأ) في مدير الهيكل | UI states | `components/settings/OrganizationStructureManager.tsx` |
| 1.6 | سجل نشاط لكل تغيير في الهيكل | audit | `models/activity_log.py` |
| 1.7 | اختبارات: شجرة بعمق 5، عزل المستشفيات، بحث برقم، تعطيل وحدة مرتبطة بعقد (يجب الرفض أو التحذير) | tests | `backend/tests/test_organization_structure_*.py`, `frontend/test/organization-*.test.tsx` |

### WP2 — حقول الاستخراج المالية (A1) — 4 أيام
| # | المهمة | الملفات |
|---|---|---|
| 2.1 | توسيع مخطط الاستخراج: `payment.interval` (monthly/quarterly/yearly/one_time)، `payment.prepaid`، `payment.tax_mode` (net/gross/unknown)، `vat_rate`، `price_adjustment` (fixed / annual_increase_pct / index_linked) | `docs/CONTRACT_SCHEMA.md`, مخطط الـ harness في `app/ai/harness/` |
| 2.2 | حساب **الحالتين** دائماً: `amount_net` و`amount_gross` من أي مدخل، مع وسم أيهما مصدر | `app/contracts/finance/` (محرك حتمي، لا ذكاء اصطناعي) |
| 2.3 | إسقاط التكلفة السنوية الموحّدة `annualized_cost_net/gross` لكل عقد (أساس WP5) | `models/calculation.py` + ترحيل |
| 2.4 | تحديث الحقيقة الأرضية للعقود الستة في `data/benchmark/ground_truth.json` بالحقول الجديدة وإعادة `scripts/benchmark_extraction.py` | `data/benchmark/` |
| 2.5 | اختبارات: عقد صافي، عقد إجمالي، عقد بزيادة سنوية 3%، عقد بدون ضريبة مذكورة (unknown) | `backend/tests/test_finance_*.py` |

### WP3 — التأكيد البشري والمصدر (A2) — 3 أيام
| # | المهمة | الملفات |
|---|---|---|
| 3.1 | إعداد على مستوى المنظمة `review_mode = manual \| auto` في `application_setting` + واجهة في الإعدادات | `models/application_setting.py`, `app/settings/` |
| 3.2 | حالة المصدر لكل حقل: `ai` / `manual` / `confirmed_both` (تُحتسب تلقائياً عند تطابق القيمة اليدوية مع المستخرجة) | `models/fact_review.py` + ترحيل |
| 3.3 | شارة بصرية تحت كل حقل في `/review` وفي تفاصيل العقد | `frontend/app/review/page.tsx`, `components/contracts/detail/` |
| 3.4 | منع اعتماد عقد في الوضع اليدوي قبل تأكيد الحقول الحرجة (الموعد النهائي للإلغاء، المبلغ، التجديد) | authz/scope + tests |

### WP4 — المواعيد والتنبيهات والبريد (A3) — 5 أيام
| # | المهمة | الملفات |
|---|---|---|
| 4.1 | إضافة أنواع تحذير: `payment_due_approaching`, `maintenance_due_approaching` (مشتقة من دورية الدفع في WP2 وجدول الصيانة) | `app/contracts/warnings/` |
| 4.2 | نموذج `notification_rule`: المستلم الافتراضي = مالك العقد (موجود في ownership)، تصعيد اختياري (رئيس القسم / حساب محدد)، القناة (`in_app`, `email`) | model/migration جديد |
| 4.3 | نموذج `notification_outbox` + مرسِل بريد عبر SMTP بإعدادات المنظمة (`smtp_host/port/user/from`) — **كلمة السر في متغير بيئة فقط**، لا في DB ولا في الريبو | `app/notifications/` جديد، `core/config.py` |
| 4.4 | مجدول دوري (داخل التطبيق، لا cron خارجي) يحوّل التحذيرات إلى إشعارات ويرسل البريد مع إعادة المحاولة وسجل | `app/notifications/scheduler.py` |
| 4.5 | تحويل `/api/notifications` من إسقاط للقراءة إلى مصدر فعلي مع `read_at` | `api/routes/notifications.py` |
| 4.6 | واجهة: إعداد بريد المؤسسة ومستلمي التصعيد؛ مركز إشعارات | `frontend/app/settings/`, مكوّن جرس |
| 4.7 | اختبارات: لا إرسال لعقود منظمة أخرى (عزل)، إعادة المحاولة عند فشل SMTP، عدم التكرار اليومي | `backend/tests/test_notifications_*.py` |

### WP5 — وحدة التحليلات (A4) — 7 أيام
| # | المهمة | الملفات |
|---|---|---|
| 5.1 | API تجميعي مقيّد بالمنظمة: `GET /api/analytics/overview` (الأعداد الثلاثة، المجموع السنوي)، `/by-department`, `/by-supplier`, `/by-type`, `/top-contracts?limit=10`, `/decisions-due` | `api/routes/analytics.py` جديد (أو توسيع `dashboard.py`) |
| 5.2 | يعتمد على `annualized_cost_*` من WP2 و`contract_department` من WP1 (التوزيع حسب القسم المستفيد **و** المسؤول، باختيار المستخدم) | `app/analytics/` |
| 5.3 | اختيار مكتبة رسوم: **Recharts** (React 18، MIT، بلا اتصال خارجي يناسب «fully local») وإضافتها عبر npm فقط | `frontend/package.json` |
| 5.4 | صفحة `/analysen` كاملة: بطاقات KPI، أعمدة حسب القسم، دائرة حسب المورّد، جدول أعلى 10، قائمة «يحتاج قراراً»، مسار تنقّل Einrichtung → Krankenhaus → Bereich → Vertrag | `frontend/app/analysen/page.tsx`, `components/analytics/` |
| 5.5 | تصدير CSV للجدول الظاهر (يحضّر للمقارنة مع الماضي لاحقاً) | `api/routes/reports.py` |
| 5.6 | اختبارات: صحة المجاميع مقابل بيانات التجربة (4 عقود في `klinik-trial`)، عزل المنظمات، أداء < 500ms على 1,000 عقد | `backend/tests/test_analytics_*.py`, Vitest للمكوّنات |

### WP6 — التصلّب والقبول (3 أيام)
| # | المهمة |
|---|---|
| 6.1 | مصفوفة الصلاحيات للمسارات الجديدة (Viewer / Reviewer / Contract Manager / Admin) حسب `docs/PRODUCTION_READINESS.md` + اختبارات سلبية عبر المستشفيات |
| 6.2 | UAT بالعقود الحقيقية: Abiomed Impella، OPTIS RAV-00074، Radiosurgery — مع قياس الزمن (المرجع السابق 66.8 ث) |
| 6.3 | تحديث `AGENTS.md` (المسار القانوني للتخزين، القاعدة 55432)، `docs/PROJECT_PROGRESS.md`، سجل الإصدار |
| 6.4 | بوابة الإصدار: `npm run verify` + `pytest` + `release-gate.yml` خضراء |

---

## 4. الجدول الزمني (5 أسابيع، مطوّر واحد بدوام كامل)

| الأسبوع | الحزم | المخرج القابل للعرض |
|---|---|---|
| 1 | WP0 + WP1 | الهيكل التنظيمي مكتمل: بحث برقم Kostenstelle، مسار الوحدة، إدارة كاملة |
| 2 | WP2 + بداية WP3 | العقود تُظهر صافي/إجمالي وتكلفة سنوية موحّدة |
| 3 | WP3 + WP4 (4.1–4.3) | شارات المصدر، وضع التثبيت التلقائي، أول بريد تنبيه يُرسل |
| 4 | WP4 (4.4–4.7) + WP5 (5.1–5.3) | مركز إشعارات كامل، API التحليلات جاهز |
| 5 | WP5 (5.4–5.6) + WP6 | صفحة Analysen بالرسوم البيانية، UAT، إصدار |

التبعيات الحرجة: WP5 ← WP2 (التكلفة السنوية) و WP1 (التوزيع حسب القسم)؛ WP4 ← WP2 (دورية الدفع). يمكن تنفيذ WP3 بالتوازي مع WP2 إن توفر مطوّر ثانٍ، فيختصر الجدول إلى 4 أسابيع.

---

## 5. الإدراج في أدوات المشروع

1. **هذا الملف** → `docs/architecture/WORKPLAN_ORGSTRUKTUR_PHASE1_20261003.md` (commit من نوع `docs:`).
2. **`docs/PROJECT_PROGRESS.md`** → إضافة قسم «Step 19 — Organisationsstruktur & Phase‑1 Foundation» يُحدَّث بعد كل WP (قاعدة `AGENTS.md`).
3. **الفروع**: `feat/wp1-orgstructure-completion`, `feat/wp2-finance-fields`, `feat/wp3-review-provenance`, `feat/wp4-notifications-email`, `feat/wp5-analytics`, متفرعة من `fix/frankfurt-contract-analysis-20261001` بعد دفعه.
4. **الترحيلات**: ملف واحد لكل WP بتسمية المستودع `YYYYMMDD_<rev>_<slug>.py`، ويُشغَّل `scripts/verify_migrated_fixture.py` بعده على قاعدة 55432 القابلة للتصرف (`medflux_drift1_*`) قبل أي شيء آخر.
5. **الاختبارات**: ملفات `backend/tests/test_<wp>_*.py` و`frontend/test/<feature>.test.tsx`؛ لا يُدمج PR دون زيادة التغطية ≥ 80% (Codecov).
6. **CI**: `.github/workflows/ci.yaml` و`release-gate.yml` كما هي؛ لا تُضاف أسرار SMTP إلى GitHub.
7. **بيانات التجربة**: الأمثلة الواردة في الوثيقة (Krankenhaus Heidelberg، Kostenstellen 471100/471110/471120/471130، عقد PACS بثلاثة أقسام مستفيدة) تُضاف كـ fixture في `backend/tests/fixtures/org_heidelberg.json` وتُستخدم في اختبارات WP1 وWP5.

---

## 6. معايير القبول النهائية (UAT بالألمانية كما يراها المستخدم)

- استيراد عقد «Wartungsvertrag Herzkatheteranlage» واختيار: Krankenhaus A → Verantwortlich: Medizintechnik → Nutzer: Medizinische Klinik › Kardiologie › Herzkatheter → Kostenstelle 472110، ثم ظهور ذلك كاملاً في تفاصيل العقد وإمكانية تعديله.
- كتابة `471120` في البحث تُظهر «471120 – CT / Radiologie / Krankenhaus Heidelberg».
- عقد بمبلغ صافي يعرض الإجمالي محسوباً والعكس، مع وسم المصدر.
- كل حقل في المراجعة يحمل شارة: KI / Manuell / Bestätigt (beide).
- تنبيه «Kündigungsfrist endet in 30 Tagen» يصل كإشعار داخلي وبريد إلى العنوان المضبوط، ونسخة لرئيس القسم عند تفعيل التصعيد.
- صفحة Analysen تعرض العقود الفعّالة/المنتهية/القريبة من الانتهاء، التوزيع حسب القسم والمورّد والنوع، أعلى 10 عقود، وقائمة القرارات المطلوبة، مع التنقّل حتى العقد.

---

## 7. المخاطر والأسئلة المفتوحة

| المخاطرة | الأثر | التخفيف |
|---|---|---|
| وكيل آخر يعمل على نفس الفرع (وثيقة التسليم §4) | تعارضات دمج | WP0.3: دفع الفرع وتجميد النطاق قبل WP1 |
| لا بنية بريد حالياً (لا SMTP، منتج «fully local») | WP4 قد يحتاج خادم بريد المؤسسة | قرار المالك: SMTP المؤسسة أم إشعار داخلي فقط في الإصدار الأول |
| 21 مجلد مستندات مقابل 3 سجلات (وثيقة التسليم §14) | التحليلات ستعرض أرقاماً ناقصة | مسار مستقل: استرجاع المستندات (الخطة السابقة Phase 2) قبل WP5 |
| مخزون النماذج قديم (`installed_models.json` ≠ Ollama) | اختيار نموذج خاطئ في UAT | تحديث المخزون في WP0 |
| الدقة الحقلية 48% في معيار أغسطس | حقول WP2 الجديدة قد تكون أضعف | قياس بعد كل تعديل للمخطط عبر `benchmark_extraction.py` |

**أسئلة تحتاج قرار المالك قبل البدء:** (1) هل البريد الإلكتروني ضمن الإصدار الأول أم إشعار داخلي فقط؟ (2) التوزيع حسب القسم في التحليلات: حسب القسم المسؤول أم المستفيد افتراضياً؟ (3) هل `unit_type` إلزامي لكل وحدة أم اختياري؟
