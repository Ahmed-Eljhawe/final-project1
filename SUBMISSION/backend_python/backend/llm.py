"""
Arabic Economic Advisory Report — generated via Ollama (local or cloud-routed LLM).

Default model: kimi-k2.6:cloud   (1T params, best Arabic quality)
Fallback:      qwen3.5:9b        (fully local)
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Dict, Optional

import requests


# ── Auto-load .env file from the project root (if present) ──────────
# No external dependency — minimal parser. Keys present in real env vars take
# precedence over .env (so a user's exported var overrides the bundled file).
def _load_env_file(path: Path) -> None:
    if not path.exists():
        return
    try:
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, value = line.partition("=")
            key   = key.strip()
            value = value.strip().strip('"').strip("'")
            if key and key not in os.environ:
                os.environ[key] = value
    except Exception:
        pass

# Look for .env in the project root (one level up from this file's parent)
_ENV_PATH = Path(__file__).resolve().parent.parent / ".env"
_load_env_file(_ENV_PATH)


OLLAMA_HOST    = os.environ.get("OLLAMA_HOST",  "http://localhost:11434")
DEFAULT_MODEL  = os.environ.get("OLLAMA_MODEL", "kimi-k2.6:cloud")
FALLBACK_MODEL = "qwen3.5:9b"
REQUEST_TIMEOUT = 180   # seconds — generation can take a while

# Groq — free cloud LLM API. Get a key at https://console.groq.com/keys
# Free tier: 30 req/min, 14,400 req/day. No credit card required.
GROQ_API_KEY     = os.environ.get("GROQ_API_KEY", "")
GROQ_DEFAULT_MODEL = os.environ.get("GROQ_MODEL", "llama-3.3-70b-versatile")
GROQ_URL         = "https://api.groq.com/openai/v1/chat/completions"

SYSTEM_PROMPT = (
    "أنت كبير المستشارين الاقتصاديين في منظمة العمل الدولية، خبير في تحليل تأثير "
    "الذكاء الاصطناعي على أسواق العمل والاقتصاد الكلي.\n\n"
    "مهمتك: تحليل نتائج محاكاة اقتصادية وتقديم تقرير استشاري احترافي شامل ومفصل.\n\n"
    "قواعد صارمة:\n"
    "1. اكتب الرد كاملاً باللغة العربية الفصحى فقط، دون أي كلمة بالإنجليزية.\n"
    "2. التزم بالأرقام الواردة في البيانات بدقة — لا تخترع أرقاماً جديدة.\n"
    "3. اربط استنتاجاتك بالبيانات الفعلية المُقدَّمة.\n"
    "4. استخدم لغة احترافية تليق بتقارير منظمات دولية كبرى.\n"
    "5. كن نقدياً وموضوعياً — لا تقدم تقريراً متفائلاً أو متشائماً بشكل مصطنع.\n\n"
    "هيكل التقرير الإلزامي:\n"
    "## 1. الملخص التنفيذي\n"
    "(فقرة مكثفة 3-5 أسطر تلخص أبرز النتائج)\n\n"
    "## 2. تحليل سوق العمل وتأثير الذكاء الاصطناعي\n"
    "(ناقش معدل البطالة، ذروة البطالة، تبنّي الذكاء الاصطناعي، الوظائف المفقودة والمخلوقة)\n\n"
    "## 3. التحليل الاقتصادي الكلي\n"
    "(الناتج المحلي، الأجور حسب المهارة، عدم المساواة، الإنفاق الاستهلاكي)\n\n"
    "## 4. التوقعات المستقبلية وسيناريوهات المخاطر\n"
    "(حدد المخاطر الرئيسية بناءً على الأرقام)\n\n"
    "## 5. التوصيات السياسية الاستراتيجية\n"
    "(قدم 5-7 توصيات عملية وملموسة، كل توصية في نقطة منفصلة)\n\n"
    "## 6. الخلاصة والرؤية المستقبلية\n"
    "(فقرة ختامية قوية)\n\n"
    "اجعل التقرير مفصلاً ومرتبطاً بالأرقام، مع تجنّب العموميات الفارغة."
)


def _format_simulation_summary(results: Dict[str, Any]) -> str:
    """Dense English summary of the simulation that the LLM can reason over."""
    summary = results.get("summary", {})
    report  = results.get("report",  {})

    unem  = results.get("unemployment", [])
    gdp   = results.get("gdp", [])
    wages = results.get("wages", {})
    sectors = results.get("sectors", {})

    unem_start  = unem[0]  if unem else 0
    unem_end    = unem[-1] if unem else 0
    unem_peak   = max(unem) if unem else 0
    gdp_start   = gdp[0]   if gdp else 0
    gdp_end     = gdp[-1]  if gdp else 0
    gdp_growth  = ((gdp_end - gdp_start) / gdp_start * 100) if gdp_start else 0

    wl_start = wages.get("L1_basic",  [0])[0]  if wages.get("L1_basic")  else 0
    wl_end   = wages.get("L1_basic",  [0])[-1] if wages.get("L1_basic")  else 0
    wh_start = wages.get("L5_expert", [0])[0]  if wages.get("L5_expert") else 0
    wh_end   = wages.get("L5_expert", [0])[-1] if wages.get("L5_expert") else 0

    lines = [
        f"SCENARIO: {results.get('scenario','moderate').upper()}",
        f"HORIZON: {report.get('start_year',2026)} – {report.get('end_year',2045)} "
        f"({len(results.get('years', []))} years)",
        f"AUTOMATION RATE: {report.get('automation_rate', 0.05)*100:.1f}% per year",
        "",
        "── LABOR MARKET ──",
        f"Unemployment: {unem_start:.2f}% → {unem_end:.2f}% (Δ {unem_end-unem_start:+.2f} pp)",
        f"Peak unemployment: {unem_peak:.2f}%",
        f"Final AI adoption: {report.get('final_ai_adoption_pct', 0):.1f}%",
        "",
        "── MACROECONOMY ──",
        f"GDP: ${gdp_start:.2f}T → ${gdp_end:.2f}T  ({gdp_growth:+.1f}%)",
        f"Gini Index: {report.get('final_gini', 0):.4f} (final year)",
        "",
        "── WAGE GAP ──",
        f"Lowest-skill (L1):  ${wl_start:,.0f} → ${wl_end:,.0f}",
        f"Highest-skill (L5): ${wh_start:,.0f} → ${wh_end:,.0f}",
        f"Wage ratio (L5/L1): {(wh_end/wl_end if wl_end else 0):.2f}x",
        "",
        "── SECTORS (final year, jobs) ──",
    ]
    for sec, jobs in sectors.items():
        final = jobs[-1] if jobs else 0
        lines.append(f"  {sec}: {final/1e6:.1f}M")

    lines.append("")
    lines.append("── SUMMARY STATISTICS ──")
    for metric, stats in summary.items():
        if isinstance(stats, dict):
            lines.append(
                f"{metric}: mean={stats.get('mean',0):.3f}, "
                f"std={stats.get('std',0):.3f}, "
                f"range=[{stats.get('min',0):.3f}, {stats.get('max',0):.3f}]"
            )
    return "\n".join(lines)


def generate_builtin_summary(results: Dict[str, Any]) -> Dict[str, Any]:
    """Deterministic Arabic economic advisory report generated from the simulation
    numbers — does NOT require Ollama or any external service. Always works."""
    scenario = (results.get("scenario") or "moderate").upper()
    sc_ar = {"SLOW": "البطيء", "MODERATE": "المعتدل", "RAPID": "السريع"}.get(scenario, scenario)
    sc_rate = {"SLOW": "3%", "MODERATE": "5%", "RAPID": "8%"}.get(scenario, "5%")

    years        = results.get("years", [])
    unem         = results.get("unemployment", [])
    gdp          = results.get("gdp", [])
    ai_adoption  = results.get("ai_adoption", [])
    gini         = results.get("gini", [])
    wages        = results.get("wages", {})
    sectors      = results.get("sectors", {})

    start_year   = years[0]  if years else 2026
    end_year     = years[-1] if years else 2046
    horizon      = len(years) or 20

    unem_start   = unem[0]  if unem else 0
    unem_end     = unem[-1] if unem else 0
    unem_peak    = max(unem) if unem else 0
    gdp_start    = gdp[0]   if gdp else 0
    gdp_end      = gdp[-1]  if gdp else 0
    gdp_growth   = ((gdp_end - gdp_start) / gdp_start * 100) if gdp_start else 0
    ai_end       = ai_adoption[-1] if ai_adoption else 0
    gini_start   = gini[0]  if gini else 0
    gini_end     = gini[-1] if gini else 0

    l1 = wages.get("L1_basic",  [0])
    l5 = wages.get("L5_expert", [0])
    l1_start, l1_end = (l1[0], l1[-1]) if l1 else (0, 0)
    l5_start, l5_end = (l5[0], l5[-1]) if l5 else (0, 0)
    l1_change = ((l1_end - l1_start) / l1_start * 100) if l1_start else 0
    l5_change = ((l5_end - l5_start) / l5_start * 100) if l5_start else 0
    wage_ratio_start = (l5_start / l1_start) if l1_start else 0
    wage_ratio_end   = (l5_end   / l1_end)   if l1_end   else 0

    # Sector final-year breakdown (in millions)
    sec_lines = []
    for name, vals in sectors.items():
        if vals:
            final_m = vals[-1] / 1e6
            sec_lines.append(f"  • {name}: {final_m:,.1f} مليون وظيفة")

    report = f"""## ١. الملخص التنفيذي

في إطار السيناريو {sc_ar} ({sc_rate} سنوياً) خلال الفترة {start_year}–{end_year} \
({horizon} سنة)، تكشف نتائج المحاكاة عن ارتفاع معدل البطالة من \
{unem_start:.2f}% إلى {unem_end:.2f}%، مع ذروة بلغت {unem_peak:.2f}%. \
يصاحب ذلك نمو الناتج المحلي الإجمالي من {gdp_start:.1f} إلى {gdp_end:.1f} تريليون دولار \
({gdp_growth:+.1f}%)، وتبني الذكاء الاصطناعي بنسبة {ai_end:.1f}% على مستوى الاقتصاد. \
هذه النتائج تكشف عن انفصال هيكلي بين النمو الاقتصادي وفرص العمل، يستدعي تدخلاً سياسياً عاجلاً.

## ٢. تحليل سوق العمل وتأثير الذكاء الاصطناعي

أظهرت المحاكاة الديناميكيات التالية في سوق العمل:

  • معدل البطالة: ارتفع من {unem_start:.2f}% إلى {unem_end:.2f}% (تغير {unem_end - unem_start:+.2f} نقطة مئوية)
  • ذروة البطالة: {unem_peak:.2f}% بلغت خلال فترة المحاكاة
  • تبني الذكاء الاصطناعي: {ai_adoption[0]:.1f}% → {ai_end:.1f}% (منحنى لوجستي بالنصف الزمني عند السنة العاشرة)
  • معدل خلق الوظائف: 0.6 وظيفة جديدة لكل وظيفة مفقودة (صافي سلبي)

تتمركز خسارة الوظائف بشكل أساسي في الفئات الأقل مهارة، حيث تواجه فئات L1 و L2 \
أعلى معدلات تعرض للأتمتة (75% و 55% على التوالي)، بينما تظل فئات الخبراء L4 و L5 \
في وضع أكثر استقراراً نسبياً.

## ٣. التحليل الاقتصادي الكلي

تكشف المؤشرات الاقتصادية الكلية عن نمط نمو غير شامل:

  • الناتج المحلي الإجمالي: {gdp_start:.1f} → {gdp_end:.1f} تريليون دولار ({gdp_growth:+.1f}%)
  • مؤشر جيني للتفاوت: {gini_start:.3f} → {gini_end:.3f} (تغير {gini_end - gini_start:+.3f})
  • أجور الفئة الأقل مهارة (L1): {l1_change:+.1f}% (من ${l1_start:,.0f} إلى ${l1_end:,.0f})
  • أجور الفئة الخبيرة (L5): {l5_change:+.1f}% (من ${l5_start:,.0f} إلى ${l5_end:,.0f})
  • نسبة الأجور (L5/L1): توسعت من {wage_ratio_start:.1f}× إلى {wage_ratio_end:.1f}×

التوزيع القطاعي النهائي للوظائف:

{chr(10).join(sec_lines)}

تشير هذه الأرقام إلى أن مكاسب الإنتاجية المدفوعة بالذكاء الاصطناعي تتركز في الفئات \
الأعلى مهارة، مما يعمق الفجوة الاقتصادية ويهدد التماسك الاجتماعي على المدى المتوسط.

## ٤. التوقعات المستقبلية وسيناريوهات المخاطر

استناداً إلى المعطيات السابقة، يمكن تحديد المخاطر التالية:

  • مخاطر اجتماعية: تفاوت متزايد في الدخل قد يؤدي إلى توترات اجتماعية وضعف الإنفاق الاستهلاكي
  • مخاطر اقتصادية: تراجع الطلب الكلي بسبب فقدان فئات واسعة لقدرتها الشرائية
  • مخاطر قطاعية: انكماش حاد في القطاع الصناعي (تعرض 8%) مقابل توسع التكنولوجيا
  • مخاطر تعليمية: تخلف منظومات التعليم والتدريب عن مواكبة المتطلبات المهنية الجديدة
  • مخاطر سياسية: ضغوط متزايدة على الحكومات لتوفير شبكات أمان اجتماعي مكلفة

## ٥. التوصيات السياسية الاستراتيجية

١. **إعادة التأهيل المهني**: إطلاق برامج وطنية موجهة للعمال في القطاعات عالية المخاطر \
(الصناعة، الكتابة المكتبية، النقل)، مع تمويل حكومي وشراكات مع القطاع الخاص.

٢. **إصلاح المنظومة التعليمية**: التركيز على المهارات المقاومة للأتمتة (الإبداع، التفكير النقدي، \
التعاطف، الذكاء العاطفي) إلى جانب المهارات التقنية في إدارة وتطوير أنظمة الذكاء الاصطناعي.

٣. **السياسة الضريبية التقدمية**: مراجعة هياكل الضرائب لإعادة توزيع الأرباح المتأتية من \
الإنتاجية المعززة بالذكاء الاصطناعي، مع دراسة ضرائب على الروبوتات والأنظمة الآلية.

٤. **شبكات الأمان الاجتماعي**: تطوير آليات مرنة مثل الدخل الأساسي الشامل المشروط، \
ضمان فرص العمل العامة، أو تأمين البطالة المعزز.

٥. **تنظيم التبني القطاعي**: وضع إطار تنظيمي لسرعة تبني الذكاء الاصطناعي في \
القطاعات الحساسة (الرعاية الصحية، التعليم، الخدمات الحكومية) لتجنب الصدمات.

٦. **دعم القطاعات الجديدة**: تحفيز ريادة الأعمال في المهن الناشئة (هندسة المطالبات، \
تدقيق أنظمة الذكاء الاصطناعي، أخصائيي الأخلاقيات، مدربي البيانات).

٧. **التعاون الدولي**: تنسيق السياسات مع الشركاء الدوليين لمنع سباق نحو القاع في \
معايير العمل، وتبادل أفضل الممارسات في إدارة التحول التكنولوجي.

## ٦. الخلاصة والرؤية المستقبلية

النتائج التي توصلت إليها هذه المحاكاة لا تمثل قدراً محتوماً، بل سلسلة من نقاط التحول \
التي تتطلب قرارات سياسية واعية. الذكاء الاصطناعي في جوهره أداة محايدة، لكن السرعة \
التي يُنشر بها، وآليات توزيع مكاسبه، ستحدد ما إذا كان سيخدم البشرية ككل أم سيُركز \
الثروة في يد فئة محدودة.

القرارات التي تُتخذ في السنوات الخمس القادمة ستشكل ملامح العقود المقبلة. النموذج \
الناجح هو الذي يجمع بين الانفتاح على الابتكار التكنولوجي والحماية الاجتماعية القوية، \
ويضمن أن مكاسب الإنتاجية تُترجم إلى رفاه شامل بدلاً من تفاوت متعمق.

في السيناريو {sc_ar} الحالي، الوقت لا يزال متاحاً للتأثير على المسار، ولكن نافذة \
العمل ضيقة وتزداد ضيقاً مع مرور كل عام.

---
*تم إنشاء هذا التقرير تلقائياً بناءً على نتائج المحاكاة · النموذج v2.0 · الفترة {start_year}–{end_year}*
*المصدر: AI Labor Market Simulation Engine*"""

    return {
        "success": True,
        "report":  report,
        "model":   "built-in deterministic analyzer (no external service)",
        "input_tokens":  0,
        "output_tokens": len(report) // 4,  # rough token estimate
        "duration_sec":  0.0,
    }


def analyze_with_groq(results: Dict[str, Any],
                      model: Optional[str] = None) -> Dict[str, Any]:
    """Real cloud LLM via Groq's free API — gives variable, contextual output
    every time. Requires GROQ_API_KEY env var (free signup at console.groq.com).

    Models that work well for Arabic:
      - llama-3.3-70b-versatile   (default, best quality)
      - llama-3.1-8b-instant      (faster, lighter)
      - mixtral-8x7b-32768        (alternative)
    """
    api_key = GROQ_API_KEY or os.environ.get("GROQ_API_KEY", "")
    if not api_key:
        return {
            "success": False,
            "report":  ("لم يتم ضبط مفتاح Groq API.\n\n"
                       "للحصول على مفتاح مجاني:\n"
                       "1. سجّل في console.groq.com (بدون بطاقة ائتمان)\n"
                       "2. أنشئ مفتاحاً من قسم API Keys\n"
                       "3. اضبط متغيّر البيئة: GROQ_API_KEY=gsk_...\n"
                       "4. أعد تشغيل الخادم\n\n"
                       "أو استخدم المُحرّك الافتراضي (Built-in)."),
            "error":   "GROQ_API_KEY not set",
            "model":   "Groq (key missing)",
        }

    chosen = model or GROQ_DEFAULT_MODEL
    summary_text = _format_simulation_summary(results)
    user_message = (
        "فيما يلي نتائج المحاكاة الفعلية لتأثير الذكاء الاصطناعي على سوق العمل "
        "للسيناريو المختار:\n\n"
        f"```\n{summary_text}\n```\n\n"
        "يرجى تقديم التقرير الاستشاري الاقتصادي الشامل وفقاً للهيكل المحدد، "
        "مع التركيز على الأرقام الواردة أعلاه."
    )

    import time
    t0 = time.time()
    try:
        resp = requests.post(
            GROQ_URL,
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type":  "application/json",
            },
            json={
                "model":    chosen,
                "messages": [
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user",   "content": user_message},
                ],
                "temperature": 0.7,     # higher → more variation between runs
                "top_p":       0.9,
                "max_tokens":  3500,
            },
            timeout=60,
        )
        resp.raise_for_status()
        data = resp.json()
    except requests.exceptions.RequestException as e:
        return {
            "success": False,
            "report":  f"فشل الاتصال بخدمة Groq: {type(e).__name__}",
            "error":   str(e),
            "model":   f"Groq · {chosen}",
        }
    except Exception as e:
        return {
            "success": False,
            "report":  f"خطأ غير متوقّع: {type(e).__name__}",
            "error":   str(e),
            "model":   f"Groq · {chosen}",
        }

    duration = round(time.time() - t0, 2)
    content = (data.get("choices") or [{}])[0].get("message", {}).get("content", "").strip()
    usage = data.get("usage", {})
    return {
        "success":       True,
        "report":        content or "(empty response)",
        "model":         f"Groq · {chosen}",
        "input_tokens":  usage.get("prompt_tokens", 0),
        "output_tokens": usage.get("completion_tokens", 0),
        "duration_sec":  duration,
    }


def list_groq_models() -> Dict[str, Any]:
    """List available Groq models if the API key is set."""
    api_key = GROQ_API_KEY or os.environ.get("GROQ_API_KEY", "")
    if not api_key:
        return {"available": False, "error": "GROQ_API_KEY not set"}
    try:
        resp = requests.get(
            "https://api.groq.com/openai/v1/models",
            headers={"Authorization": f"Bearer {api_key}"},
            timeout=10,
        )
        resp.raise_for_status()
        models = [{"name": m.get("id"), "is_cloud": True}
                  for m in resp.json().get("data", [])]
        return {"available": True, "models": models, "default": GROQ_DEFAULT_MODEL}
    except Exception as e:
        return {"available": False, "error": str(e)}


def _call_ollama(model: str, user_message: str) -> Dict[str, Any]:
    resp = requests.post(
        f"{OLLAMA_HOST}/api/chat",
        json={
            "model":    model,
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user",   "content": user_message},
            ],
            "stream":  False,
            "options": {"temperature": 0.4, "top_p": 0.9, "num_predict": 3500},
        },
        timeout=REQUEST_TIMEOUT,
    )
    resp.raise_for_status()
    return resp.json()


def analyze_with_local_llm(results: Dict[str, Any], model: Optional[str] = None) -> Dict[str, Any]:
    chosen = model or DEFAULT_MODEL
    summary_text = _format_simulation_summary(results)
    user_message = (
        "فيما يلي نتائج المحاكاة الفعلية لتأثير الذكاء الاصطناعي على سوق العمل "
        "للسيناريو المختار:\n\n"
        f"```\n{summary_text}\n```\n\n"
        "يرجى تقديم التقرير الاستشاري الاقتصادي الشامل وفقاً للهيكل المحدد، "
        "مع التركيز على الأرقام الواردة أعلاه."
    )

    try:
        data = _call_ollama(chosen, user_message)
    except requests.exceptions.RequestException as e:
        if chosen != FALLBACK_MODEL:
            try:
                data = _call_ollama(FALLBACK_MODEL, user_message)
                chosen = FALLBACK_MODEL + " (fallback)"
            except Exception as e2:
                return {
                    "success": False,
                    "report":  f"تعذّر الاتصال بـ Ollama على {OLLAMA_HOST}.",
                    "error":   f"{type(e).__name__}: {e} | fallback: {e2}",
                }
        else:
            return {
                "success": False,
                "report":  f"تعذّر الاتصال بـ Ollama على {OLLAMA_HOST}.",
                "error":   f"{type(e).__name__}: {e}",
            }
    except Exception as e:
        return {"success": False, "report": f"خطأ غير متوقّع: {e}", "error": str(e)}

    msg = data.get("message", {})
    return {
        "success":       True,
        "report":        msg.get("content", "").strip() or "لا يوجد محتوى في الاستجابة.",
        "model":         chosen,
        "input_tokens":  data.get("prompt_eval_count", 0),
        "output_tokens": data.get("eval_count", 0),
        "duration_sec":  round(data.get("total_duration", 0) / 1e9, 2),
    }


def list_available_models() -> Dict[str, Any]:
    try:
        resp = requests.get(f"{OLLAMA_HOST}/api/tags", timeout=10)
        resp.raise_for_status()
        models = [
            {
                "name":     m["name"],
                "size_mb":  round(m.get("size", 0) / 1e6, 1),
                "is_cloud": "cloud" in m.get("name", "").lower(),
            }
            for m in resp.json().get("models", [])
        ]
        return {"available": True, "models": models, "default": DEFAULT_MODEL}
    except Exception as e:
        return {"available": False, "error": str(e)}
