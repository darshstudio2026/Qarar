import io
import pandas as pd
import plotly.express as px
import streamlit as st

from core.ai_advisor import answer_question, generate_executive_summary
from core.data_adapter import get_industry_preset, load_uploaded_file
from core.solver_engine import solve_schedule
from utils.report_generator import generate_excel_report, generate_html_report

# -----------------------------------------------------------------------------
# Page Configuration & Executive Arabic RTL Styling
# -----------------------------------------------------------------------------
st.set_page_config(
    page_title="قرار | Qarar AI — منصة دعم القرار",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown(
    """
    <style>
    html, body, [class*="css"] {
        direction: rtl;
        text-align: right;
        font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
    }
    .stTabs [data-baseweb="tab-list"] {
        gap: 8px;
    }
    .stTabs [data-baseweb="tab"] {
        padding: 10px 18px;
        border-radius: 8px;
        font-weight: 600;
    }
    div[data-testid="stMetric"] {
        background-color: #f8fafc;
        border: 1px solid #e2e8f0;
        padding: 14px 18px;
        border-radius: 10px;
        box-shadow: 0 1px 3px rgba(0, 0, 0, 0.05);
    }
    </style>
    """,
    unsafe_allow_html=True,
)


def to_template_bytes(res_df: pd.DataFrame, ord_df: pd.DataFrame, stk_df: pd.DataFrame) -> bytes:
    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as writer:
        res_df.to_excel(writer, sheet_name="Resources", index=False)
        ord_df.to_excel(writer, sheet_name="Orders", index=False)
        stk_df.to_excel(writer, sheet_name="Stock", index=False)
    return buf.getvalue()


# -----------------------------------------------------------------------------
# Sidebar: AI Advisor Key & Global Settings
# -----------------------------------------------------------------------------
with st.sidebar:
    st.title("⚡ قرار | Qarar AI")
    st.caption("منصة دعم القرار وجدولة العمليات الذكية")
    st.divider()

    st.subheader("🤖 المستشار التنفيذي (AI)")
    ai_provider = st.selectbox("مزود الذكاء الاصطناعي (اختياري)", ["OpenAI", "Claude", "Gemini"])
    api_key = st.text_input("مفتاح API (اختياري)", type="password", help="في حال عدم الإدخال، يعمل المحرك الذكي المدمج تلقائياً.")

    st.divider()
    st.subheader("🎯 معيار التحسين الأساسي")
    objective_mode = st.radio(
        "اختر هدف المحرك:",
        [
            "أسرع وقت تسليم | Minimize Makespan",
            "أقل تكلفة تشغيلية | Minimize Cost",
            "توازن ذكي | Balanced",
        ],
    )

# Initialize session state with default preset
if "resources_df" not in st.session_state:
    r0, o0, s0 = get_industry_preset("مصنع تصنيع وتجميع")
    st.session_state["resources_df"] = r0
    st.session_state["orders_df"] = o0
    st.session_state["stock_df"] = s0

st.title("⚡ قرار | Qarar AI — منصة دعم القرار وجدولة العمليات")

tab1, tab2, tab3, tab4 = st.tabs([
    "1️⃣ مركز البيانات والربط الذكي",
    "2️⃣ غرفة العمليات والخطة المثلى",
    "3️⃣ محاكي السيناريوهات (What-If)",
    "4️⃣ التنبؤ المالي والتقارير التنفيذية",
])

# =============================================================================
# TAB 1: مركز البيانات والربط الذكي (Data & Smart Mapping)
# =============================================================================
with tab1:
    st.subheader("🔌 قوالب القطاعات الجاهزة (Plug & Play Presets)")
    p1, p2, p3, p4 = st.columns(4)
    with p1:
        if st.button("🏭 مصنع تصنيع وتجميع", use_container_width=True):
            r, o, s = get_industry_preset("مصنع تصنيع وتجميع")
            st.session_state["resources_df"], st.session_state["orders_df"], st.session_state["stock_df"] = r, o, s
            st.rerun()
    with p2:
        if st.button("🚚 شركة توزيع ولوجستيات", use_container_width=True):
            r, o, s = get_industry_preset("شركة توزيع ولوجستيات")
            st.session_state["resources_df"], st.session_state["orders_df"], st.session_state["stock_df"] = r, o, s
            st.rerun()
    with p3:
        if st.button("👥 إدارة مشاريع وفرق عمل", use_container_width=True):
            r, o, s = get_industry_preset("إدارة مشاريع وفرق عمل")
            st.session_state["resources_df"], st.session_state["orders_df"], st.session_state["stock_df"] = r, o, s
            st.rerun()
    with p4:
        tpl = to_template_bytes(
            st.session_state["resources_df"],
            st.session_state["orders_df"],
            st.session_state["stock_df"],
        )
        st.download_button(
            "📥 تحميل قالب Excel",
            data=tpl,
            file_name="qarar_template.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            use_container_width=True,
        )

    st.divider()
    st.subheader("📤 رفع ملفات الشركة (.xlsx / .csv) مع المطابقة الذكية للأعمدة")
    uploaded = st.file_uploader("اسحب وأفلت ملف Excel أو CSV هنا", type=["xlsx", "csv"])
    if uploaded is not None:
        try:
            r_up, o_up, s_up, map_report = load_uploaded_file(uploaded)
            st.session_state["resources_df"] = r_up
            st.session_state["orders_df"] = o_up
            st.session_state["stock_df"] = s_up
            st.success("✅ تم استيراد الملف ومطابقة الأعمدة تلقائياً!")
            with st.expander("عرض تفاصيل المطابقة الذكية للأعمدة (Auto-Column Mapping)"):
                st.json(map_report)
        except Exception as exc:
            st.error(f"تعذر قراءة الملف: {exc}")

    st.subheader("📋 الجداول الحية (قابلة للتعديل المباشر)")
    gt1, gt2, gt3 = st.tabs(["الموارد | Resources", "الطلبات | Orders", "المخزون | Stock"])
    with gt1:
        st.session_state["resources_df"] = st.data_editor(
            st.session_state["resources_df"], num_rows="dynamic", use_container_width=True, key="ed_res"
        )
    with gt2:
        st.session_state["orders_df"] = st.data_editor(
            st.session_state["orders_df"], num_rows="dynamic", use_container_width=True, key="ed_ord"
        )
    with gt3:
        st.session_state["stock_df"] = st.data_editor(
            st.session_state["stock_df"], num_rows="dynamic", use_container_width=True, key="ed_stk"
        )

# Run Baseline Optimization
baseline_result = solve_schedule(
    st.session_state["resources_df"],
    st.session_state["orders_df"],
    st.session_state["stock_df"],
    objective_mode=objective_mode,
)

# =============================================================================
# TAB 2: غرفة العمليات والخطة المثلى (Optimization & Action Plan)
# =============================================================================
with tab2:
    if baseline_result["status"] in ("ERROR", "INFEASIBLE"):
        st.error(baseline_result["message"])
        for b in baseline_result.get("bottlenecks", []):
            st.warning(f"⚠️ {b}")
    else:
        k1, k2, k3, k4 = st.columns(4)
        k1.metric("إجمالي الطلبات المجدولة", f"{len(baseline_result['schedule_df'])}")
        k2.metric("زمن التنفيذ الكلي (Makespan)", f"{baseline_result['makespan']} ساعة")
        k3.metric("التكلفة التشغيلية", f"{baseline_result['total_cost']:,}")
        k4.metric("نسبة استغلال الموارد", f"{baseline_result['utilization']}%")

        col_gantt, col_util = st.columns([2, 1])
        with col_gantt:
            st.subheader("📊 مخطط جانت التفاعلي (Gantt Chart)")
            df_plot = baseline_result["schedule_df"]
            fig_gantt = px.bar(
                df_plot,
                base="وقت البدء (ساعة)",
                x="المدة الإجمالية (ساعة)",
                y="المورد",
                color="اسم الطلب",
                orientation="h",
                hover_data=["رقم الطلب", "وقت البدء (ساعة)", "وقت الانتهاء (ساعة)", "الموعد النهائي (ساعة)"],
            )
            fig_gantt.update_layout(xaxis_title="الزمن (ساعة)", yaxis_title="المورد", barmode="overlay", height=380)
            st.plotly_chart(fig_gantt, use_container_width=True)

        with col_util:
            st.subheader("⚙️ استغلال الموارد (%)")
            util_df = baseline_result["utilization_df"]
            fig_util = px.bar(
                util_df,
                x="المورد",
                y="نسبة الاستغلال (%)",
                color="نسبة الاستغلال (%)",
                color_continuous_scale="Blues",
            )
            fig_util.update_layout(height=380)
            st.plotly_chart(fig_util, use_container_width=True)

        st.divider()
        col_ai, col_bn = st.columns([2, 1])
        with col_ai:
            summary_md = generate_executive_summary(baseline_result, api_key=api_key, provider=ai_provider)
            st.markdown(summary_md)
            user_q = st.text_input("💬 اسأل المستشار الذكي عن الخطة (مثال: ما هي التكلفة؟ أو ما هي الاختناقات؟)")
            if user_q:
                st.info(answer_question(user_q, baseline_result, api_key=api_key))

        with col_bn:
            st.subheader("🚨 كاشف الاختناقات")
            bns = baseline_result.get("bottlenecks", [])
            if bns:
                for b in bns:
                    st.warning(b)
            else:
                st.success("✅ لا توجد اختناقات حرجة.")

# =============================================================================
# TAB 3: محاكي السيناريوهات (What-If Simulator)
# =============================================================================
with tab3:
    st.subheader("🎛️ محاكاة الاضطرابات والنمو (What-If Simulator)")
    c_sim1, c_sim2, c_sim3, c_sim4 = st.columns(4)
    with c_sim1:
        demand_surge = st.slider("تغير حجم الطلب / المدة (%)", -30, 100, 0, step=10)
    with c_sim2:
        overtime = st.slider("ساعات العمل الإضافية (Overtime)", 0, 24, 0, step=2)
    with c_sim3:
        stock_pct = st.slider("توافر المخزون (%)", 20, 150, 100, step=10)
    with c_sim4:
        all_res_ids = st.session_state["resources_df"]["resource_id"].astype(str).tolist()
        disabled_res = st.multiselect("تعطيل موارد (صيانة/عطل)", options=all_res_ids)

    sim_result = solve_schedule(
        st.session_state["resources_df"],
        st.session_state["orders_df"],
        st.session_state["stock_df"],
        objective_mode=objective_mode,
        overtime_hours=overtime,
        disabled_resources=disabled_res,
        demand_multiplier=1.0 + (demand_surge / 100.0),
        stock_multiplier=stock_pct / 100.0,
    )

    st.divider()
    if sim_result["status"] in ("ERROR", "INFEASIBLE"):
        st.error(f"❌ السيناريو غير قابل للتنفيذ: {sim_result['message']}")
    elif baseline_result["status"] not in ("ERROR", "INFEASIBLE"):
        d_time = sim_result["makespan"] - baseline_result["makespan"]
        d_cost = sim_result["total_cost"] - baseline_result["total_cost"]
        d_util = round(sim_result["utilization"] - baseline_result["utilization"], 1)

        s1, s2, s3 = st.columns(3)
        s1.metric("زمن التنفيذ (السيناريو)", f"{sim_result['makespan']} ساعة", delta=f"{d_time:+} ساعة", delta_color="inverse")
        s2.metric("التكلفة (السيناريو)", f"{sim_result['total_cost']:,}", delta=f"{d_cost:+,}", delta_color="inverse")
        s3.metric("استغلال الموارد", f"{sim_result['utilization']}%", delta=f"{d_util:+}%")
        st.dataframe(sim_result["schedule_df"], use_container_width=True)

# =============================================================================
# TAB 4: التنبؤ المالي والتقارير التنفيذية (Financial Impact & Export)
# =============================================================================
with tab4:
    if baseline_result["status"] in ("ERROR", "INFEASIBLE"):
        st.warning("يرجى حل الخطة الأساسية أولاً لعرض التحليل المالي والتقارير.")
    else:
        f1, f2, f3, f4 = st.columns(4)
        f1.metric("تكلفة الإنتاج", f"{baseline_result['prod_cost']:,}")
        f2.metric("تكلفة التجهيز (Setup)", f"{baseline_result['setup_cost']:,}")
        f3.metric("تكلفة الخمول المقدرة", f"{baseline_result['idle_cost']:,}")
        f4.metric("الوفر التقديري (ROI)", f"{baseline_result['estimated_savings']:,}")

        cost_df = pd.DataFrame([
            {"البند": "تكلفة الإنتاج", "القيمة": baseline_result["prod_cost"]},
            {"البند": "تكلفة التجهيز", "القيمة": baseline_result["setup_cost"]},
            {"البند": "تكلفة الخمول المقدرة", "القيمة": baseline_result["idle_cost"]},
        ])
        fig_cost = px.pie(cost_df, names="البند", values="القيمة", title="توزيع هيكل التكاليف التشغيلية", hole=0.4)
        st.plotly_chart(fig_cost, use_container_width=True)

        st.subheader("📥 تصدير التقارير التنفيذية")
        e1, e2 = st.columns(2)
        with e1:
            excel_bytes = generate_excel_report(baseline_result)
            st.download_button(
                "📊 تحميل التقرير التنفيذي الكامل (Excel)",
                data=excel_bytes,
                file_name="qarar_executive_report.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                use_container_width=True,
            )
        with e2:
            html_report = generate_html_report(baseline_result)
            st.download_button(
                "📄 تحميل الملخص التنفيذي للطباعة (HTML)",
                data=html_report.encode("utf-8"),
                file_name="qarar_executive_summary.html",
                mime="text/html",
                use_container_width=True,
            )
