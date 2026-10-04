# توحيد الفروع — 2026-10-04

**الفرع الموحّد:** `integration/unify-20261004`، ويُرفع إليه `main` بعد المراجعة (fast-forward).
**نقطة البداية:** `fix/frankfurt-contract-analysis-20261001` @ `adcd0c8`، وهو أحدث فرع والأقرب إلى الإصدار المستقر.
**`main` على GitHub قبل التوحيد:** `359b78b`. كان متأخراً بـ 519 commit عن نقطة البداية، ومتقدماً عليها بـ commit توثيق واحد.

## 1. النسخ الاحتياطية (قبل أي تغيير)

| الملف | المحتوى |
|---|---|
| `Desktop\Medflux-backups\medflux-all-refs-20261004.bundle` | كل الفروع المحلية والبعيدة والـ stash (`git bundle --all`، تم التحقق: complete history) |
| `Desktop\Medflux-backups\Medflux-Integrated-Test-uncommitted-20261004.patch` | التعديلات غير المحفوظة في Medflux-Integrated-Test |
| `Desktop\Medflux-backups\Medflux-Integrated-Test-untracked-20261004.tgz` | الملفات غير المتتبعة في Medflux-Integrated-Test |
| tags `archive/*` (39 tag) | مؤشر لكل فرع قبل حذفه، تحمل تاريخه كاملاً |

## 2. خطوات الدمج (بالترتيب)

| # | Commit | الفرع | القرار |
|---|---|---|---|
| 1 | `ab23280` | `main` (GitHub) | دمج commit توثيق HYDMedia |
| 2 | `44cd88b` | — | توحيد نهايات الأسطر: كان 459 ملفاً CRLF و9 ملفات مختلطة، فكان كل دمج يتعارض على ملفات كاملة. أُضيف `.gitattributes` (LF، ويبقى CRLF لملفات `.bat/.ps1`). المحتوى لم يتغير |
| 3 | `06c1363` | `codex/e2e-contracts-20261003` (11 إصلاحاً) | دمج مع حل التعارضات (انظر 2.1) |
| 4 | `8e0f681` | review/contract-analysis-json، optis-source-recovery، test-db-safety | محتواها مطابق لما دُمج في الخطوة 3 (نسخ rebase)، فسُجّلت فقط |
| 5 | `521d6bf` | `review/financial-evidence-cleanup` = `AHMAD` | موجود سابقاً بصيغة أحدث (`e20126e`)، فسُجّل فقط |
| 6 | `0bf6fac` | `review/source-region-pdf-content-415` | دمج: التحقق من بايتات PDF الفعلية بدل بيانات الامتداد |
| 7 | `30a363a` | `fix/migration-fixture-drift1` | أُبقيت نسخ الملفات الأحدث من الخط الرئيسي وأُضيفت الوثائق |
| 8–11 | `44dcfd8`، `23ca8f7`، `04e0a6e`، `d3d65fa` | github-cleanup، reports ×2، architecture | وثائق فقط |
| 12 | `2095ff0` | `review/ahmad-hospital` | **المتطلبات فقط** (`docs/pilot`). لم تُدمج نسخة "مراجعة أحمد" الموازية وواجهاتها المرشحة، التزاماً بتعليمات المالك في `docs/pilot/OPENCODE_HANDOFF.md` (لا تطبيق موازٍ) |
| 13 | `bdf2385` | `JAMAL-v1` | سُجّل بلا محتوى: الفرع نسخة كاملة من المشروع داخل مجلد `JAMAL v1/`، وقد انتقلت ميزاته إلى الخط الرئيسي عبر `JAMAL` |

### 2.1 قرارات حل التعارض في e2e-contracts

- **المالية:** اعتُمد `_financial_source_rejection`، ويشترط أن يظهر المبلغ ومرساة الفترة/الإجمالي في الاقتباس نفسه. صفوف الجداول السنوية مثل `2.Jahr` تُقبل كمرساة سنوية، اتساقاً مع إرشادات الـ pack. أُعيدت تسمية الـ regex إلى `_FINANCIAL_MONEY_LITERAL_RE`، لأن الاسم القديم كان يُحجب بتعريف آخر فيفشل التحليل بأكمله.
- **سياق النموذج:** بقي `HARNESS_CONTEXT_TOKENS=8192`، الافتراضي الأحدث المناسب لبطاقة 8 GB. قيمة 32768 من فرع e2e متاحة عبر `.env` عند الحاجة.
- **رفع نسخة مكررة:** يُتحقق من مرجع النسخة **قبل** استعادة الأصل المفقود.
- **الـ schema:** أُضيفت `strip_json_code_fence`، ويحتفظ الـ harness بآليته الخاصة.

## 3. خطط طُبقت أثناء التوحيد

| Commit | البند | المصدر |
|---|---|---|
| `9c30570` | **خطأ حرج:** كان `scripts/rebuild_document_index.py` يكتب صيغة لا يقرؤها `DocumentStorage`، فيعطّل كشف التكرار ويسبب أعطالاً. أصبح الآن بصيغة صحيحة، ويدعم `.docx`، ويأخذ نسخة احتياطية، ويعمل dry-run افتراضياً | PHASE_2 storage recovery |
| `88b8c10` | مسارات التخزين النسبية تُثبَّت على `backend/`، مع فحص للمخزن عند الإقلاع (تحذير فقط) | SESSION_SUMMARY، المرحلة الثالثة |
| `8e921b5` | رفض تعطيل وحدة مرتبطة بعقود حية (HTTP 409) | WORKPLAN WP1.7 |
| `bff8fcb` | أرشفة عمل Visual-First غير المحفوظ في `experiments/visual-first-20260926/` | — |

## 4. خطط ما زالت مفتوحة

| البند | الحالة | النوع |
|---|---|---|
| WP2.1 تصنيف `price_adjustment` المنظم | جزئي | كود M |
| WP2.3 `annualized_cost_net/gross` مخزن | غير منفذ | كود + ترحيل M |
| WP3.1 / 3.2 `review_mode` و`confirmed_both` | غير منفذ | كود M |
| WP4 الإشعارات (payment/maintenance due، SMTP، scheduler) | غير منفذ | كود L |
| WP5 التحليلات (API، رسوم بيانية، CSV) | غير منفذ | كود L |
| CONTRACT_IMPORT_WIZARD (أوضاع الإدخال الثلاثة، import-intents) | غير منفذ، والواجهة المرشحة محفوظة في `archive/review/ahmad-hospital-20260926` | كود L |
| COST_CENTER_INTELLIGENCE (budget/actual، forecast) | جزئي | كود L |
| أرشيف LlamaIndex (Stage 2) | في `experiments/` فقط | كود M |
| `scripts/sync_database_documents.py`، reconciliation دوري | غير منفذ | كود M |
| اختبار Docker Compose، كتلة 55432 على Windows، UAT، تشغيل الاسترجاع على المخزن الحقيقي | تشغيلي | ops |

هذه البنود ميزات كاملة تحتاج قرارات تصميم واختبار واجهة على Windows، فلم تُنفذ ضمن التوحيد.

## 5. التحقق

بيئة التحقق: PostgreSQL 16 مؤقت ومعزول في وضع CI (`127.0.0.1:5432/medflux`).

| | الفرع الأصلي `adcd0c8` | الفرع الموحد |
|---|---|---|
| Backend pytest — نجح | 1346 | **1388** |
| فشل | 31 | 31 (نفس الاختبارات تماماً) |
| فشل جديد | — | **0** |

الـ 31 فشلاً كلها من حدود بيئة الـ sandbox: مكتبة PyMuPDF غير متاحة (30)، وTesseract مثبت فيها (1). وقد سبق أن نجحت هذه الاختبارات على Windows (1377/0 في `adcd0c8`). **المطلوب قبل رفع `main`:** تشغيل `scripts\run_wp1_tests.bat` أو المجموعة الكاملة واختبارات الواجهة (`npm test`، `tsc`) على Windows.

## 6. المزامنة مع GitHub

انظر `Desktop\Medflux-backups\SYNC_UNIFIED_MAIN.ps1`. يجلب السكربت حالة GitHub الحالية، ويتوقف إن وُجد على GitHub أي commit غير موجود في الفرع الموحد. ثم يرفع الفرع الموحد ويحدّث `main` (fast-forward فقط، بلا force) ويرفع tags الأرشيف. ولا يحذف الفروع البعيدة إلا بعد تأكيد صريح، وبعد التحقق من أن كل فرع منها داخل `main`.

## 7. سجل الجلسة الثانية (التحقق والمزامنة)

| # | المشكلة | الحل |
|---|---|---|
| 1 | لا يستطيع Claude الكتابة في الطرفية ولا في مستكشف الملفات على Windows (صلاحية "click" فقط)، وبيئة Linux المساعدة لا تصل إلى npm أو PyPI أو GitHub | جُمعت الخطوات في ملفين يُشغَّلان بنقرة مزدوجة من `Desktop\Medflux-backups`: `RUN_VERIFY_UNIFIED_20261004.bat` (تبديل الفرع + PyMuPDF + الاختبارات الـ 31 + backend كامل + tsc + npm test) و `RUN_SYNC_GITHUB_20261004.bat`. النتائج تُكتب في ملفات يقرؤها Claude |
| 2 | كان `SYNC_UNIFIED_MAIN.ps1` يشغّل `git fetch --prune --tags`، وهذا الأمر يحذف محلياً كل tag غير موجود على GitHub، أي كل tags الأرشيف الـ 39 قبل رفعها | أُزيل `--tags` من الجلب، فتُرفع الـ tags صراحة في المرحلة B |
| 3 | `push_branch.bat` غير محفوظ في git | نُسخ إلى `Medflux-backups\push_branch-uncommitted-20261004.bat` قبل تبديل الفرع |
| 4 | فرق الواجهة بين الفرعين | الفرق في `package.json` و`package-lock.json` نهايات أسطر فقط، فلا حاجة إلى `npm install` |
