import io
from typing import Dict
import pandas as pd


def generate_excel_report(result: Dict) -> bytes:
    """
    Generates a formatted multi-sheet Excel executive plan:
    - Schedule
    - KPI_Summary
    - Resource_Utilization
    - Bottlenecks
    """
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        schedule_df = result.get("schedule_df", pd.DataFrame())
        util_df = result.get("utilization_df", pd.DataFrame())
        bottlenecks = result.get("bottlenecks", [])

        kpi_df = pd.DataFrame([
            {"المؤشر": "حالة الحل", "القيمة": result.get("status", "N/A")},
            {"المؤشر": "زمن التنفيذ الكلي (ساعة)", "القيمة": result.get("makespan", 0)},
            {"المؤشر": "التكلفة التشغيلية الإجمالية", "القيمة": result.get("total_cost", 0)},
            {"المؤشر": "تكلفة الإنتاج", "القيمة": result.get("prod_cost", 0)},
            {"المؤشر": "تكلفة التجهيز", "القيمة": result.get("setup_cost", 0)},
            {"المؤشر": "تكلفة الخمول المقدرة", "القيمة": result.get("idle_cost", 0)},
            {"المؤشر": "الوفر التقديري", "القيمة": result.get("estimated_savings", 0)},
            {"المؤشر": "نسبة استغلال الموارد (%)", "القيمة": result.get("utilization", 0)},
        ])

        bn_df = pd.DataFrame({"التنبيهات ونقاط الاختناق": bottlenecks if bottlenecks else ["لا توجد اختناقات حرجة"]})

        schedule_df.to_excel(writer, sheet_name="Schedule", index=False)
        kpi_df.to_excel(writer, sheet_name="KPI_Summary", index=False)
        util_df.to_excel(writer, sheet_name="Resource_Utilization", index=False)
        bn_df.to_excel(writer, sheet_name="Bottlenecks", index=False)

    return output.getvalue()


def generate_html_report(result: Dict) -> str:
    """
    Generates a clean printable Arabic RTL HTML executive summary.
    """
    schedule_html = result.get("schedule_df", pd.DataFrame()).to_html(index=False, border=1)
    return f"""<!DOCTYPE html>
<html lang="ar" dir="rtl">
<head>
<meta charset="utf-8">
<title>تقرير قرار التنفيذي | Qarar AI</title>
<style>
  body {{ font-family: Tahoma, Arial, sans-serif; margin: 32px; color: #1e293b; }}
  h1 {{ color: #0f172a; border-bottom: 2px solid #2563eb; padding-bottom: 8px; }}
  .kpi-grid {{ display: flex; gap: 16px; margin: 20px 0; }}
  .kpi {{ background: #f8fafc; border: 1px solid #cbd5e1; border-radius: 8px; padding: 12px 18px; flex: 1; }}
  table {{ width: 100%; border-collapse: collapse; margin-top: 16px; font-size: 13px; }}
  th, td {{ padding: 8px; text-align: right; border: 1px solid #cbd5e1; }}
  th {{ background: #eff6ff; }}
</style>
</head>
<body>
  <h1>⚡ التقرير التنفيذي — قرار | Qarar AI</h1>
  <div class="kpi-grid">
    <div class="kpi"><strong>زمن التنفيذ الكلي:</strong><br>{result.get('makespan', 0)} ساعة</div>
    <div class="kpi"><strong>التكلفة الإجمالية:</strong><br>{result.get('total_cost', 0):,}</div>
    <div class="kpi"><strong>استغلال الموارد:</strong><br>{result.get('utilization', 0)}%</div>
    <div class="kpi"><strong>الوفر المقدر:</strong><br>{result.get('estimated_savings', 0):,}</div>
  </div>
  <h2>خطة التنفيذ التفصيلية</h2>
  {schedule_html}
</body>
</html>"""
