import io
import pandas as pd
import plotly.express as px
import streamlit as st
from streamlit_option_menu import option_menu

from core.ai_advisor import answer_question, generate_executive_summary
from core.data_adapter import get_industry_preset, load_uploaded_file
from core.database import (
    get_optimization_history,
    get_or_create_demo_company,
    init_db,
    load_company_data,
    load_optimization_run,
    login_company,
    register_company,
    save_company_data,
    save_optimization_run,
)
from core.solver_engine import solve_schedule
from utils.report_generator import generate_excel_report, generate_html_report

# -----------------------------------------------------------------------------
# Page Config & Cairo Glassmorphism Arabic RTL Styling
# -----------------------------------------------------------------------------
st.set_page_config(
    page_title="قرار | Qarar AI — منصة دعم القرار المؤسسية",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown(
    """
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Cairo:wght@400;600;700;800&display=swap');

    html, body, [class*="css"], .stApp {
        font-family: 'Cairo', sans-serif !important;
        direction: rtl;
        text-align: right;
    }
    .exec-header {
        background: linear-gradient(135deg, #0F172A 0%, #1E293B 100%);
        color: #FFFFFF;
        padding: 16px 24px;
        border-radius: 14px;
        margin-bottom: 20px;
        display: flex;
        justify-content: space-between;
        align-items: center;
        box-shadow: 0 8px 24px rgba(15, 23, 42, 0.15);
        border: 1px solid rgba(255, 255, 255, 0.08);
    }
    .exec-badge {
        background: rgba(16, 185, 129, 0.18);
        color: #10B981;
        border: 1px solid #10B981;
        padding: 4px 12px;
        border-radius: 20px;
        font-size: 0.85rem;
        font-weight: 700;
    }
    div[data-testid="stMetric"] {
        background: rgba(248, 250, 252, 0.9);
        backdrop-filter: blur(10px);
        border: 1px solid #E2E8F0;
        border-right: 4px solid #3B82F6;
        padding: 16px 20px;
        border-radius: 12px;
        box-shadow: 0 4px 12px rgba(15, 23, 42, 0.04);
    }
    .stButton > button {
        border-radius: 10px;
        font-family: 'Cairo', sans-serif !important;
        font-weight: 700;
        transition: all 0.2s ease;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

EXEC_PALETTE = ["#0F172A", "#3B82F6", "#10B981", "#F59E0B", "#6366F1", "#EC4899"]


def to_template_bytes(res_df: pd.DataFrame, ord_df: pd.DataFrame, stk_df: pd.DataFrame) -> bytes:
    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as writer:
        res_df.to_excel(writer, sheet_name="Resources", index=False)
        ord_df.to_excel(writer, sheet_name="Orders", index=False)
        stk_df.to_excel(writer, sheet_name="Stock", index=False)
    return buf.getvalue()


init_db()

# -----------------------------------------------------------------------------
# Multi-Tenant Auth Gate (Login / Register / Quick Demo Guest Mode)
# -----------------------------------------------------------------------------
if "company" not in st.session_state:
    st.markdown(
        """
        <div class="exec-header">
            <div>
                <h2 style="margin:0; color:#fff;">⚡ قرار | Qarar AI</h2>
                <span style="color:#94A3B8; font-size:0.95rem;">منصة دعم القرار وجدولة العمليات الذكية — Enterprise SaaS</span>
            </div>
            <span class="exec-badge">الإصدار المؤسسي 3.0</span>
        </div>
        """,
        unsafe_allow_html=True,
    )

    col_auth1, col_auth2 = st.columns([1.2, 1])
    with col_auth1:
        auth_tab1, auth_tab2 = st.tabs(["🔐 تسجيل الدخول", "🏢 تسجيل شركة جديدة"])
        with auth_tab1:
            email_in = st.text_input("البريد الإلكتروني", key="login_email")
            pass_in = st.text_input("كلمة المرور", type="password", key="login_pass")
            if st.button("دخول إلى مساحة العمل", type="primary", use_container_width=True):
                ok, msg, comp = login_company(email_in, pass_in)
                if ok:
                    st.session_state["company"] = comp
                    st.rerun()
                else:
                    st.error(msg)
        with auth_tab2:
            cname_in = st.text_input("اسم الشركة / المؤسسة", key="reg_name")
            remail_in = st.text_input("البريد الإلكتروني الرسمي", key="reg_email")
            rpass_in = st.text_input("كلمة المرور", type="password", key="reg_pass")
            if st.button("إنشاء حساب شركة جديد", type="primary", use_container_width=True):
                if cname_in and remail_in and rpass_in:
                    ok, msg, comp = register_company(cname_in, remail_in, rpass_in)
                    if ok:
                        st.session_state["company"] = comp
                        st.rerun()
                    else:
                        st.error(msg)
                else:
                    st.warning("يرجى تعبئة جميع الحقول.")

    with col_auth2:
        st.info("### 🚀 دخول سريع للتجربة (Quick Demo Mode)\nاستكشف كافة قدرات المنصة فوراً ببيانات نموذجية معزولة.")
        if st.button("⚡ دخول فوري كضيف (Demo Workspace)", use_container_width=True):
            st.session_state["company"] = get_or_create_demo_company()
            st.rerun()
    st.stop()

# -----------------------------------------------------------------------------
# Load Company Workspace Data from SQLite
# -----------------------------------------------------------------------------
company = st.session_state["company"]
cid = company["company_id"]

if "resources_df" not in st.session_state:
    loaded = load_company_data(cid)
    if loaded:
        st.session_state["resources_df"], st.session_state["orders_df"], st.session_state["stock_df"] = loaded
    else:
        r0, o0, s0 = get_industry_preset("مصنع تصنيع وتجميع")
        st.session_state["resources_df"], st.session_state["orders_df"], st.session_state["stock_df"] = r0, o0, s0
        save_company_data(cid, r0, o0, s0)

# -----------------------------------------------------------------------------
# Sidebar Navigation (streamlit-option-menu)
# -----------------------------------------------------------------------------
with st.sidebar:
    st.markdown(f"### 🏢 {company['company_name']}")
    st.caption(f"الخطة: **{company.get('plan_status', 'Enterprise')}**")
    st.divider()

    selected_nav = option_menu(
        menu_title="القائمة الرئيسية",
        options=[
            "مركز البيانات والربط",
            "غرفة العمليات المثلى",
            "محاكي السيناريوهات",
            "التنبؤ المالي والتقارير",
            "سجل القرارات السابقة",
        ],
        icons=["database", "cpu", "sliders", "graph-up-arrow", "clock-history"],
        menu_icon="lightning-charge",
        default_index=0,
        styles={
            "container": {"padding": "4px", "background-color": "#F8FAFC"},
            "icon": {"color": "#3B82F6", "font-size": "18px"},
            "nav-link": {"font-family": "Cairo", "font-size": "14px", "text-align": "right"},
            "nav-link-selected": {"background-color": "#0F172A", "color": "#FFFFFF"},
        },
    )

    st.divider()
    objective_mode = st.radio(
        "🎯 معيار التحسين:",
        [
            "أسرع وقت تسليم | Minimize Makespan",
            "أقل تكلفة تشغيلية | Minimize Cost",
            "توازن ذكي | Balanced",
        ],
    )
    shift_hours = st.select_slider("🕒 نظام الورديات (ساعة/يوم)", options=[8, 12, 16, 24], value=24)

    with st.expander("🤖 إعدادات المستشار الذكي (AI)"):
        ai_provider = st.selectbox("المزود", ["OpenAI", "Claude", "Gemini"])
        api_key = st.text_input("مفتاح API (اختياري)", type="password")

    if st.button("🚪 تسجيل الخروج", use_container_width=True):
        for k in ["company", "resources_df", "orders_df", "stock_df"]:
            st.session_state.pop(k, None)
        st.rerun()

# Top Executive Header Bar
st.markdown(
    f"""
    <div class="exec-header">
        <div>
            <h3 style="margin:0; color:#fff;">⚡ قرار | Qarar AI — {company['company_name']}</h3>
            <span style="color:#94A3B8; font-size:0.85rem;">نظام الورديات: {shift_hours} ساعة/يوم | الهدف: {objective_mode.split('|')[0].strip()}</span>
        </div>
        <span class="exec-badge">● متصل بقاعدة البيانات ({company.get('plan_status', 'Enterprise')})</span>
    </div>
    """,
    unsafe_allow_html=True,
)

# Run Baseline Optimization
baseline_result = solve_schedule(
    st.session_state["resources_df"],
    st.session_state["orders_df"],
    st.session_state["stock_df"],
    objective_mode=objective_mode,
    shift_hours_per_day=shift_hours,
)

# =============================================================================
# VIEW 1: مركز البيانات والربط الذكي
# =============================================================================
if selected_nav == "مركز البيانات والربط":
    st.subheader("🔌 قوالب القطاعات الجاهزة (Plug & Play Presets)")
    p1, p2, p3, p4 = st.columns(4)
    with p1:
        if st.button("🏭 مصنع تصنيع وتجميع", use_container_width=True):
            r, o, s = get_industry_preset("مصنع تصنيع وتجميع")
            st.session_state["resources_df"], st.session_state["orders_df"], st.session_state["stock_df"] = r, o, s
            save_company_data(cid, r, o, s)
            st.rerun()
    with p2:
        if st.button("🚚 شركة توزيع ولوجستيات", use_container_width=True):
            r, o, s = get_industry_preset("شركة توزيع ولوجستيات")
            st.session_state["resources_df"], st.session_state["orders_df"], st.session_state["stock_df"] = r, o, s
            save_company_data(cid, r, o, s)
            st.rerun()
    with p3:
        if st.button("👥 إدارة مشاريع وفرق عمل", use_container_width=True):
            r, o, s = get_industry_preset("إدارة مشاريع وفرق عمل")
            st.session_state["resources_df"], st.session_state["orders_df"], st.session_state["stock_df"] = r, o, s
            save_company_data(cid, r, o, s)
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
    uploaded = st.file_uploader("📤 رفع ملف الشركة (.xlsx / .csv) مع المطابقة الذكية للأعمدة", type=["xlsx", "csv"])
    if uploaded is not None:
        try:
            r_up, o_up, s_up, map_report = load_uploaded_file(uploaded)
            st.session_state["resources_df"], st.session_state["orders_df"], st.session_state["stock_df"] = r_up, o_up, s_up
            save_company_data(cid, r_up, o_up, s_up)
            st.success("✅ تم استيراد الملف وحفظه في قاعدة بيانات الشركة!")
            with st.expander("تفاصيل المطابقة الذكية للأعمدة"):
                st.json(map_report)
        except Exception as exc:
            st.error(f"تعذر قراءة الملف: {exc}")

    gt1, gt2, gt3 = st.tabs(["الموارد | Resources", "الطلبات | Orders", "المخزون | Stock"])
    with gt1:
        st.session_state["resources_df"] = st.data_editor(st.session_state["resources_df"], num_rows="dynamic", use_container_width=True, key="ed_res")
    with gt2:
        st.session_state["orders_df"] = st.data_editor(st.session_state["orders_df"], num_rows="dynamic", use_container_width=True, key="ed_ord")
    with gt3:
        st.session_state["stock_df"] = st.data_editor(st.session_state["stock_df"], num_rows="dynamic", use_container_width=True, key="ed_stk")

    if st.button("💾 حفظ التعديلات في قاعدة البيانات", type="primary"):
        save_company_data(cid, st.session_state["resources_df"], st.session_state["orders_df"], st.session_state["stock_df"])
        st.success("✅ تم حفظ بيانات الشركة بنجاح.")

# =============================================================================
# VIEW 2: غرفة العمليات المثلى
# =============================================================================
elif selected_nav == "غرفة العمليات المثلى":
    if baseline_result["status"] in ("ERROR", "INFEASIBLE"):
        st.error(baseline_result["message"])
        for b in baseline_result.get("bottlenecks", []):
            st.warning(f"⚠️ {b}")
    else:
        k1, k2, k3, k4 = st.columns(4)
        k1.metric("إجمالي الطلبات المجدولة", f"{len(baseline_result['schedule_df'])}")
        k2.metric("زمن التنفيذ الكلي", f"{baseline_result['makespan']} ساعة")
        k3.metric("التكلفة التشغيلية", f"{baseline_result['total_cost']:,}")
        k4.metric("استغلال الموارد", f"{baseline_result['utilization']}%")

        col_save1, col_save2 = st.columns([3, 1])
        with col_save1:
            run_label = st.text_input("اسم الخطة للحفظ في السجل:", value="خطة التشغيل القياسية")
        with col_save2:
            st.write("")
            if st.button("💾 حفظ في سجل القرارات", use_container_width=True):
                rid = save_optimization_run(cid, run_label, objective_mode, baseline_result)
                st.success(f"تم الحفظ برقم #{rid}")

        col_gantt, col_util = st.columns([2, 1])
        with col_gantt:
            st.subheader("📊 مخطط جانت التفاعلي (Gantt Chart)")
            fig_gantt = px.bar(
                baseline_result["schedule_df"],
                base="وقت البدء (ساعة)",
                x="المدة الإجمالية (ساعة)",
                y="المورد",
                color="اسم الطلب",
                orientation="h",
                color_discrete_sequence=EXEC_PALETTE,
                hover_data=["رقم الطلب", "وقت البدء (ساعة)", "وقت الانتهاء (ساعة)", "الموعد النهائي (ساعة)"],
            )
            fig_gantt.update_layout(
                font=dict(family="Cairo"),
                paper_bgcolor="rgba(0,0,0,0)",
                plot_bgcolor="rgba(0,0,0,0)",
                xaxis_title="الزمن (ساعة)",
                yaxis_title="المورد",
                barmode="overlay",
                height=380,
            )
            st.plotly_chart(fig_gantt, use_container_width=True)

        with col_util:
            st.subheader("⚙️ استغلال الموارد (%)")
            fig_util = px.bar(
                baseline_result["utilization_df"],
                x="المورد",
                y="نسبة الاستغلال (%)",
                color="نسبة الاستغلال (%)",
                color_continuous_scale=["#3B82F6", "#0F172A"],
            )
            fig_util.update_layout(
                font=dict(family="Cairo"),
                paper_bgcolor="rgba(0,0,0,0)",
                plot_bgcolor="rgba(0,0,0,0)",
                height=380,
            )
            st.plotly_chart(fig_util, use_container_width=True)

        st.divider()
        col_ai, col_bn = st.columns([2, 1])
        with col_ai:
            st.markdown(generate_executive_summary(baseline_result, api_key=api_key, provider=ai_provider))
            user_q = st.text_input("💬 اسأل المستشار الذكي عن الخطة:")
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
# VIEW 3: محاكي السيناريوهات
# =============================================================================
elif selected_nav == "محاكي السيناريوهات":
    st.subheader("🎛️ محاكاة الاضطرابات والنمو (What-If Simulator)")
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        demand_surge = st.slider("تغير حجم الطلب (%)", -30, 100, 0, step=10)
    with c2:
        overtime = st.slider("ساعات إضافية (Overtime)", 0, 24, 0, step=2)
    with c3:
        stock_pct = st.slider("توافر المخزون (%)", 20, 150, 100, step=10)
    with c4:
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
        shift_hours_per_day=shift_hours,
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
# VIEW 4: التنبؤ المالي والتقارير
# =============================================================================
elif selected_nav == "التنبؤ المالي والتقارير":
    if baseline_result["status"] in ("ERROR", "INFEASIBLE"):
        st.warning("يرجى حل الخطة الأساسية أولاً لعرض التحليل المالي.")
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
        fig_cost = px.pie(
            cost_df,
            names="البند",
            values="القيمة",
            title="توزيع هيكل التكاليف التشغيلية",
            hole=0.45,
            color_discrete_sequence=["#0F172A", "#3B82F6", "#F59E0B"],
        )
        fig_cost.update_layout(font=dict(family="Cairo"), paper_bgcolor="rgba(0,0,0,0)")
        st.plotly_chart(fig_cost, use_container_width=True)

        e1, e2 = st.columns(2)
        with e1:
            st.download_button(
                "📊 تحميل التقرير التنفيذي الكامل (Excel)",
                data=generate_excel_report(baseline_result),
                file_name="qarar_executive_report.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                use_container_width=True,
            )
        with e2:
            st.download_button(
                "📄 تحميل الملخص التنفيذي للطباعة (HTML)",
                data=generate_html_report(baseline_result).encode("utf-8"),
                file_name="qarar_executive_summary.html",
                mime="text/html",
                use_container_width=True,
            )

# =============================================================================
# VIEW 5: سجل القرارات السابقة | Decision History
# =============================================================================
elif selected_nav == "سجل القرارات السابقة":
    st.subheader("🕰️ سجل القرارات السابقة | Decision History")
    hist_df = get_optimization_history(cid)
    if hist_df.empty:
        st.info("لا توجد خطط محفوظة بعد. يمكنك حفظ أي خطة من تبويب 'غرفة العمليات المثلى'.")
    else:
        st.dataframe(hist_df, use_container_width=True)
        run_ids = hist_df["run_id"].tolist()
        selected_run = st.selectbox("اختر رقم الخطة لاستعراض تفاصيلها:", run_ids)
        if selected_run:
            loaded_run = load_optimization_run(selected_run)
            if loaded_run:
                st.write(f"**الخطة:** {loaded_run['run_name']} | **التاريخ:** {loaded_run['created_at']}")
                st.dataframe(loaded_run["schedule_df"], use_container_width=True)
