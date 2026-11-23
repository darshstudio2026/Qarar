# قرار | Qarar AI
**محرك دعم القرار وجدولة العمليات الذكي**  
*Universal AI Decision & Resource Optimization Dashboard*

---

## نظرة عامة | Overview
**قرار (Qarar AI)** هو تطبيق ويب تفاعلي مبني بلغة Python و Streamlit، يعتمد على محرك **Google OR-Tools (CP-SAT)** لحل مسائل الجدولة وتخصيص الموارد بشكل عام (Plug & Play) دون التقيد بصناعة محددة.

**Qarar AI** is a universal, domain-agnostic decision support and operations scheduling dashboard powered by **Google OR-Tools (CP-SAT)**, **Streamlit**, and **Plotly**.

---

## المميزات الرئيسية | Key Features
- **واجهة عربية تنفيذية (RTL):** تصميم نظيف وسهل الاستخدام.
- **قالب Excel قياسي (3 أوراق):** `Resources`، `Orders`، `Stock` مع إمكانية التحميل والرفع والتعديل المباشر.
- **محرك تحسين ذكي (OR-Tools):** يدعم سعات الموارد، أوقات التجهيز (Setup Time)، المواعيد النهائية (Deadlines)، وتوافر المخزون.
- **أهداف متعددة:** تقليل زمن التسليم الكلي (Minimize Makespan) أو تقليل التكلفة التشغيلية (Minimize Cost).
- **مخطط جانت التفاعلي (Gantt Chart):** عرض مرئي تفاعلي باستخدام `plotly.express.bar` مع تصدير خطة التنفيذ.

---

## التشغيل السريع | Quick Start

```bash
pip install -r requirements.txt
streamlit run app.py
```
