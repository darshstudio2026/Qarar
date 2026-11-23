from typing import Dict, Optional
import requests


def generate_executive_summary(result: Dict, api_key: Optional[str] = None, provider: str = "OpenAI") -> str:
    """
    Translates mathematical optimization results into clear Arabic executive insights.
    Uses LLM API if key is provided, otherwise falls back to a smart rule-based engine.
    """
    if result.get("status") in ("ERROR", "INFEASIBLE"):
        bottlenecks = result.get("bottlenecks", [])
        b_text = "\n".join(f"- {b}" for b in bottlenecks) if bottlenecks else result.get("message", "")
        return (
            f"⚠️ **تنبيه تشغيلي:** تعذر إيجاد جدول زمني ممكن.\n\n"
            f"**الأسباب المكتشفة:**\n{b_text}\n\n"
            f"**التوصية التنفيذية:** قم بتمديد المواعيد النهائية، أو إضافة ساعات عمل إضافية، أو تعزيز المخزون."
        )

    makespan = result.get("makespan", 0)
    total_cost = result.get("total_cost", 0)
    util = result.get("utilization", 0)
    savings = result.get("estimated_savings", 0)
    bottlenecks = result.get("bottlenecks", [])

    rule_based = (
        f"### 🧠 الملخص التنفيذي الذكي\n"
        f"- **الكفاءة الزمنية:** تم جدولة جميع الطلبات بنجاح خلال **{makespan} ساعة** كحد أقصى للتسليم.\n"
        f"- **الأثر المالي:** التكلفة التشغيلية الإجمالية **{total_cost:,}**، مع وفر تقديري يبلغ **{savings:,}** مقارنة بالجدولة اليدوية.\n"
        f"- **استغلال الموارد:** بلغ متوسط استغلال الموارد **{util}%**.\n"
    )
    if bottlenecks:
        rule_based += "\n**⚠️ نقاط الاختناق والتنبيهات:**\n" + "\n".join(f"- {b}" for b in bottlenecks[:5])
    else:
        rule_based += "\n✅ **لا توجد اختناقات حرجة:** جميع الطلبات ضمن هوامش أمان مريحة."

    if not api_key or not api_key.strip():
        return rule_based

    prompt = (
        f"أنت مستشار عمليات تنفيذية. لخص نتائج الجدولة التالية بالعربية في 4 نقاط موجزة وعملية:\n"
        f"- زمن التنفيذ الكلي: {makespan} ساعة\n"
        f"- التكلفة الإجمالية: {total_cost}\n"
        f"- نسبة استغلال الموارد: {util}%\n"
        f"- الوفر المقدر: {savings}\n"
        f"- التنبيهات: {bottlenecks}\n"
    )

    try:
        if provider == "OpenAI":
            resp = requests.post(
                "https://api.openai.com/v1/chat/completions",
                headers={"Authorization": f"Bearer {api_key.strip()}", "Content-Type": "application/json"},
                json={"model": "gpt-4o-mini", "messages": [{"role": "user", "content": prompt}], "max_tokens": 350},
                timeout=10,
            )
            if resp.status_code == 200:
                return resp.json()["choices"][0]["message"]["content"]
    except Exception:
        pass

    return rule_based


def answer_question(question: str, result: Dict, api_key: Optional[str] = None) -> str:
    """
    Natural Language Q&A over the optimization results.
    """
    q = question.strip()
    if not q:
        return "يرجى كتابة سؤالك حول الخطة المثلى."

    if result.get("status") in ("ERROR", "INFEASIBLE"):
        return f"لا توجد خطة مثلى حالياً بسبب: {result.get('message', 'قيود غير قابلة للحل')}."

    q_lower = q.lower()
    if any(w in q_lower for w in ["تكلفة", "سعر", "مالي", "وفر", "cost", "roi"]):
        return (
            f"💰 التكلفة التشغيلية الإجمالية هي **{result['total_cost']:,}** "
            f"(تكلفة إنتاج: {result.get('prod_cost', 0):,} + تكلفة تجهيز: {result.get('setup_cost', 0):,})، "
            f"والوفر التقديري مقارنة بالجدولة اليدوية هو **{result.get('estimated_savings', 0):,}**."
        )
    if any(w in q_lower for w in ["وقت", "زمن", "ساعة", "تسليم", "makespan", "time"]):
        return f"⏱️ إجمالي زمن التنفيذ الكلي (Makespan) هو **{result['makespan']} ساعة** بنسبة تسليم في الموعد 100%."
    if any(w in q_lower for w in ["اختناق", "مشكلة", "تحذير", "حرج", "bottleneck"]):
        b = result.get("bottlenecks", [])
        return "⚠️ **نقاط الاختناق:**\n" + "\n".join(f"- {x}" for x in b) if b else "✅ لا توجد اختناقات حرجة في الخطة الحالية."
    if any(w in q_lower for w in ["مورد", "استغلال", "كفاءة", "utilization", "resource"]):
        return f"📊 متوسط استغلال الموارد هو **{result['utilization']}%**."

    return (
        f"بناءً على الخطة المثلى: الزمن الكلي **{result['makespan']} ساعة**، "
        f"التكلفة **{result['total_cost']:,}**، واستغلال الموارد **{result['utilization']}%**."
    )
