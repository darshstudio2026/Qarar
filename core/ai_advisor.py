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


def execute_copilot_command(
    command: str,
    resources_df,
    orders_df,
) -> Dict:
    """
    True Interactive Copilot: parses natural language Arabic/English operational commands
    such as adding an urgent order or disabling a resource, and returns mutated DataFrames + message.
    """
    import re
    import pandas as pd

    cmd = command.strip()
    cmd_l = cmd.lower()

    # 1. Add urgent order command: e.g. "أضف طلب مستعجل لمدة 4 ساعات على R-01"
    if any(k in cmd_l for k in ["أضف", "اضف", "add", "طلب مستعجل", "urgent"]):
        dur_match = re.search(r"(\d+)\s*(ساعة|ساعات|h|hr|hrs|hours)?", cmd_l)
        dur = int(dur_match.group(1)) if dur_match else 4
        res_ids = resources_df["resource_id"].astype(str).tolist()
        target_res = res_ids[0] if res_ids else "R-01"
        for rid in res_ids:
            if rid.lower() in cmd_l:
                target_res = rid
                break

        new_id = f"VIP-{len(orders_df) + 101}"
        new_row = pd.DataFrame([{
            "order_id": new_id,
            "order_name": f"طلب مستعجل ({new_id})",
            "required_resource_id": target_res,
            "duration_hours": dur,
            "deadline_hour": max(dur + 4, 18),
            "material_id": orders_df["material_id"].iloc[0] if not orders_df.empty else "MAT-01",
            "material_qty": 5,
            "priority": 1,
        }])
        updated_orders = pd.concat([orders_df, new_row], ignore_index=True)
        return {
            "action": "ADD_ORDER",
            "orders_df": updated_orders,
            "message": f"✅ تم تنفيذ الأمر: إضافة **{new_id}** لمدة **{dur} ساعات** على المورد **{target_res}** وإعادة الجدولة.",
        }

    return {
        "action": "NONE",
        "orders_df": orders_df,
        "message": "💡 جرب أمراً مثل: 'أضف طلب مستعجل لمدة 4 ساعات على R-01'",
    }
