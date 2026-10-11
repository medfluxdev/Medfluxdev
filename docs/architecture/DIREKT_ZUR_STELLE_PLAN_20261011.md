# «مباشرة إلى المكان» – خطة: كل نقص في البرنامج يقود بضغطة إلى مكان إصلاحه

**التاريخ:** 2026-10-11 · **الأساس:** فحص كامل للواجهة (كل رسالة «ناقص / غير معروف / يحتاج إجراء») مقابل الكود على `feature/register-list-toolbar` @ `0e3385c`
**الحالة:** معتمدة، قيد التنفيذ على `feature/register-list-toolbar`.

**المثال من المستخدم:** في «Vertragsdaten» تظهر «Für „Gültig“ fehlen noch: Vertragsbeginn.» كنص فقط؛ على المستخدم أن يبحث عن زر «Vertragsdaten bearbeiten» ثم عن الحقل. المطلوب: الضغط على «Vertragsbeginn» يفتح التحرير ويضع المؤشر في الحقل مباشرة – ونفس المبدأ في البرنامج كله.

---

## 1. ما وجده الفحص

- **لا توجد آلية للوصول إلى حقل بعينه.** صفحة العقد تفهم `tab` و`subtab` فقط؛ لا `feld` ولا `abschnitt`. معرّفات الحقول `rg-<key>` موجودة **فقط في وضع التحرير**، ووضع التحرير حالة داخلية في `ContractRegisterPanel` لا يمكن فتحها من الخارج.
- **حوالي 45 موضعاً** تقول إن شيئاً ناقص دون رابط إلى مكان الإصلاح، موزعة على: صفحة العقد (Vertragsdaten، Finanzen، Fristen، Übersicht)، Mein Tag، Fristen & Aufgaben، الإشعارات، Analysen، قائمة العقود، الاستيراد، Verwaltung، الأجهزة.
- **روابط إلى العقد مكتوبة يدوياً في ~20 مكاناً** (`?tab=deadlines`، `?tab=register` …) دون دالة مشتركة؛ ورابط «العقود دون فترة قابلة للحساب» مكرّر في 3 ملفات؛ ودالتان مختلفتان باسم `registerLink`.
- **أخطاء توجيه قائمة:**
  - بطاقات «Handlungsbedarf» في «Übersicht» تنفّذ `setRoute("overview")` للمهام غير المراجِعة – أي لا شيء، لأن المستخدم في «Übersicht» أصلاً.
  - صف القائمة يفتح دائماً `?tab=register`، حتى عندما يكون الفلتر «تكلفة مجهولة» (المكان الصحيح «Finanzen»).
  - روابط الإشعارات تذهب دائماً إلى `?tab=deadlines` مهما كان نوع المهمة (`backend/app/api/routes/notifications.py:82`).
- **الخادم يرسل نصوصاً بلا مفاتيح** في أربعة أماكن، فلا تعرف الواجهة أين الإصلاح:
  - نتائج قواعد العقد (`rules/service.py:64`: `rule_id, label, outcome, detail` فقط)
  - تلميحات موجز التجديد (`reports/renewal.py:153-208`)
  - ملاحظات الملخص المالي (`finance/calc.py:171-200`، `finance/service.py:222`)
  - `costs.availability.missing_inputs`

## 2. الفكرة: «هدف إصلاح» واحد لكل نقص

كل نقص يُعبَّر عنه بهدف واحد مُحدَّد، والواجهة كلها تبني الرابط من نفس الدالة:

```text
FixTarget = { tab, subtab?, field?, section? }

contractHref(id, target)  →  /contracts/<id>?tab=register&feld=term_start_date
                           →  /contracts/<id>?tab=finance&abschnitt=entries
                           →  /contracts/<id>?tab=documents&subtab=review
```

- **`frontend/lib/fix-targets.ts`** (جديد، مصدر واحد):
  - `contractHref(id, target)` و`registerHref(filters)` (بدل `registerLink` المكرر والسلاسل اليدوية)
  - الخريطة الحتمية «حقل → مكان»: مفاتيح `_value` إلى المفتاح الأساسي (`notice_period_value` → `notice_period`)؛ حقول الفترة والتجديد والتذكير والسعر والصيانة والحذف → قسمها في «Vertragsdaten»؛ التكلفة → «Finanzen › Einträge»؛ المراجعة → «Dokumente › Prüfung»؛ المسؤول/القسم → «Zuständigkeit»
- **الخادم يعطي الهدف حين يعرفه** (القواعد، التجديد، المالية، الإشعارات) بحقل إضافي `target`؛ النص الألماني يبقى كما هو.

## 3. السلوك عند الوصول (صفحة العقد)

1. `?feld=<key>` يفتح التبويب الصحيح، ثم يفتح **وضع التحرير** في «Vertragsdaten»، ويمرّر إلى الحقل ويضع المؤشر فيه، مع إبراز قصير للحقل (إطار بلون الإشارة لثانيتين، دون حركة لمن اختار تقليل الحركة).
2. **حقل مخفي:** حقول المدة تظهر حسب «Vertragsart». إن لم تُختر بعد، يذهب الرابط إلى «Vertragsart» مع تلميح «Erst die Vertragsart wählen – danach erscheint Vertragsbeginn.».
3. **دون صلاحية تحرير** (viewer/reviewer): لا يُفتح التحرير؛ يُمرَّر إلى الحقل ويُبرَز مع «Nur Lesen – Änderungen über das Vertragsmanagement.».
4. **تعديلات غير محفوظة:** إن كان التحرير مفتوحاً، لا تُفقد المسودة؛ يُنقل المؤشر فقط.
5. `?abschnitt=<id>` يمرّر إلى قسم (مثلاً `entries` في «Finanzen» ويفتح نموذج «Eintrag erstellen» إن كانت الصلاحية موجودة).
6. **داخل نفس اللوحة** (مثال المستخدم) لا يتغير الرابط: الضغط على «Vertragsbeginn» يفتح التحرير ويضع المؤشر مباشرة؛ ويُحدَّث العنوان بـ `feld` كي يعمل «رجوع» والمشاركة.

مكوّن مشترك **`MissingList`** يعرض «Für „Gültig“ fehlen noch: [Vertragsbeginn] [Vertragspartner]» – كل اسم زر/رابط حقيقي (لوحة المفاتيح، قارئ الشاشة: «Vertragsbeginn erfassen»).

## 4. المراحل

### المرحلة 1 – الآلية + مثال المستخدم (صفحة العقد، Vertragsdaten)

| الموضع | التغيير |
|---|---|
| `lib/fix-targets.ts` | جديد: `contractHref`, `registerHref`, خريطة الحقول، اختبارات وحدات |
| `ContractWorkspace.tsx` | قراءة `feld`/`abschnitt`، تمريرها إلى اللوحة، الإبقاء عليها عند تبديل التبويب الصحيح فقط |
| `ContractRegisterPanel.tsx` | `focusField(key)` (يفتح التحرير، يحترم المسودة والصلاحية والحقول المخفية)؛ معرّف `rg-field-<key>` في وضع العرض أيضاً |
| السطر 463 «Für Gültig fehlen noch» | `MissingList` قابلة للضغط |
| السطر 483 «Fristen noch nicht berechenbar. Es fehlen» | `MissingList` |
| «Nicht erfasst» لكل حقل | رابط صغير «Erfassen» بجانب القيمة الفارغة (للمحرّرين) |
| `AiFillSummary` «noch nicht bestätigt» | كل حقل يقود إلى مكانه (زر «Bestätigen» عنده) |
| «Aufbewahrung: Nicht festgelegt» | إلى `retention_years_after_end` أو إلى نوع العقد في Stammdaten |

### المرحلة 2 – باقي صفحة العقد (مع أهداف من الخادم)

- **قواعد العقد** («Angabe fehlt»): الخادم يضيف `rule_kind` و`target` لكل نتيجة (حتمي حسب نوع القاعدة: الحد الأدنى للإشعار → `notice_period`، الحد الأقصى للتكلفة → Finanzen، الحقل المطلوب → `field_key` نفسه).
- **Finanzen:** ملاحظات «Kein Vertragsende bekannt» → فترة العقد؛ «Anpassungsdatum angenommen» → `price_adjustment_next_date`؛ «Noch keine Finanzeinträge» → يفتح نموذج الإدخال؛ «Warum Kosten noch nicht vollständig» و«Keine akzeptierte Abrechnungsbasis» → الإدخالات/الاقتراحات.
- **Fristen:** تلميحات موجز التجديد (`target` من الخادم: التكلفة، مستلم التذكير، المراجعة، المستند)؛ «Frist unbekannt»؛ «Basiert auf ungeprüften KI-Werten» → المراجعة؛ «Keine offenen Termine…» → حقول المدة الناقصة الفعلية؛ المهام حسب `item_type`.
- **Übersicht:** إصلاح خطأ «Handlungsbedarf» (توجيه حسب `item_type`/`warning_type`)؛ حقائق الرأس الفارغة («Vertragsende –», «Kündbar bis –», «Jährliche Kosten –») تصبح روابط؛ «Prüfung erforderlich» → المراجعة.
- **بطاقة «Was fehlt noch?»** في «Übersicht»: قائمة واحدة بكل ما ينقص العقد (حقول «Gültig»، المدة، التكلفة، المسؤول، المراجعة، القواعد غير القابلة للتقييم)، كل بند رابط. تُبنى من بيانات موجودة (`missing_for_valid`, `terms.missing`, المالية، الملكية، `review_pending`، القواعد). تختفي حين لا ينقص شيء.
- **المعاينة السريعة في القائمة:** «KI-Werte noch nicht geprüft» والقيم «–» تقود إلى أماكنها.

### المرحلة 3 – القوائم والصفحات العامة

| الصفحة | التغيير |
|---|---|
| Mein Tag | إشارات «Lagebild» قابلة للضغط؛ «Kosten fehlen bei N» → العقود دون تكلفة؛ «N nicht bewertbar» → العقود دون فترة قابلة للحساب؛ عقد واحد → مباشرة إلى حقله |
| قائمة العقود | رابط الصف يتبع الفلتر النشط (تكلفة مجهولة → Finanzen، مدة ناقصة → حقول المدة)؛ ملخص التكلفة «fehlende anzeigen»؛ خلايا «Unvollständig» و«Angabe fehlt» روابط |
| Fristen & Aufgaben | «Nächster Schritt» زر حسب `item_type`؛ «Ungeprüfte KI-Werte» → المراجعة؛ «nicht berechenbar» → العقد مباشرة عند عقد واحد |
| الإشعارات (الجرس، Postfach) | الخادم يبني `href` حسب `item_type` بنفس الخريطة |
| Analysen | «Teilsumme…» و«Keine gepflegten Finanzposten» و«{n} ohne Kosten» → القائمة المصفّاة؛ `missingHref` في التنقّل حسب المستشفى/القسم؛ صفوف العقود → المكان الصحيح |
| الاستيراد | «N Verträge erfordern manuelle Prüfung» → «Zu prüfen»؛ الاستيراد الفاشل → مستندات العقد |
| Verwaltung | «Offene Aufgaben»، «Manuelle Prüfungen» روابط |
| Geräte | «Zu prüfen» لكل عقد مرتبط → المكان الصحيح |
| Stammdaten | «{n} ohne Vertrag» → قائمة الشركاء مصفّاة |

### المرحلة 4 – «دائماً ممكن»: الوصول من أي مكان

- لوحة الأوامر (Strg+K) على صفحة عقد: عناصر «Vertragsbeginn erfassen»، «Kosten erfassen»، «KI-Werte prüfen» من نفس قائمة «Was fehlt noch?».
- قاعدة في `docs/FRONTEND_CONVENTIONS.md`: **كل رسالة عن نقص تحمل هدف إصلاح** (`contractHref`/`registerHref`)، أو تشرح لماذا لا يوجد؛ وفحص في المراجعة.

## 5. الاختبارات

- **وحدات:**
  - خريطة الحقول، بما فيها مفاتيح `_value` والحقول المخفية
  - `contractHref`
  - `MissingList` (بلوحة المفاتيح وaxe)
- **صفحة العقد:**
  - `?feld=term_start_date` يفتح التحرير ويضع المؤشر في الحقل
  - دون «Vertragsart» يذهب إلى «Vertragsart»
  - viewer لا يحصل على وضع التحرير
  - المسودة غير المحفوظة لا تضيع
- **الخادم:** `target` في القواعد والتجديد والمالية والإشعارات (حتمي لكل نوع).
- **Playwright:** مسار جديد «من رسالة النقص إلى الحقل»: قائمة العقود → عقد «In Arbeit» → ضغط «Vertragsbeginn» → المؤشر في الحقل → حفظ → الرسالة تختفي.
- لكل مرحلة: `pytest` كامل، `npm run verify`، Playwright كامل.

## 6. قرارات المالك (2026-10-11)

1. **عند الضغط:** يُفتح نموذج «Vertragsdaten bearbeiten» كاملاً ويوضع المؤشر في الحقل.
2. **بطاقة «Was fehlt noch?»** في «Übersicht»: نعم.
3. **النطاق:** المراحل الأربع بالترتيب، commit لكل مرحلة، اختبارات كاملة بعد كل مرحلة.

**خارج النطاق:** تغيير قواعد «Gültig» أو الحقول المطلوبة، حساب الفترات أو التكاليف، أي ترحيل لقاعدة البيانات (لا حاجة له).
