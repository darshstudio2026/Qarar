import io
from typing import Dict, Tuple

import openpyxl  # noqa: F401 - required for pandas Excel I/O
import pandas as pd
import plotly.express as px
import streamlit as st
from ortools.sat.python import cp_model

# -----------------------------------------------------------------------------
# Page Configuration & Arabic RTL Executive Styling
# -----------------------------------------------------------------------------
st.set_page_config(
    page_title="قرار | Qarar AI",
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
        padding: 8px 16px;
        border-radius: 6px;
    }
    div[data-testid="stMetric"] {
        background-color: #f8fafc;
        border: 1px solid #e2e8f0;
        padding: 14px 18px;
        border-radius: 10px;
        box-shadow: 0 1px 2px rgba(0, 0, 0, 0.04);
    }
    </style>
    """,
    unsafe_allow_html=True,
)


# -----------------------------------------------------------------------------
# Generic Sample Data (100% Domain-Agnostic)
# -----------------------------------------------------------------------------
def get_sample_data() -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    resources_df = pd.DataFrame(
        [
            {"resource_id": "R-01", "resource_name": "وحدة تشغيل أ", "capacity": 1, "hourly_cost": 120, "setup_time_hours": 1},
            {"resource_id": "R-02", "resource_name": "وحدة تشغيل ب", "capacity": 1, "hourly_cost": 95, "setup_time_hours": 1},
            {"resource_id": "R-03", "resource_name": "وحدة تشغيل ج", "capacity": 2, "hourly_cost": 150, "setup_time_hours": 2},
        ]
    )

    orders_df = pd.DataFrame(
        [
            {"order_id": "ORD-101", "order_name": "أمر عمل 101", "required_resource_id": "R-01", "duration_hours": 4, "deadline_hour": 14, "material_id": "MAT-01", "material_qty": 20, "priority": 1},
            {"order_id": "ORD-102", "order_name": "أمر عمل 102", "required_resource_id": "R-01", "duration_hours": 5, "deadline_hour": 18, "material_id": "MAT-02", "material_qty": 15, "priority": 2},
            {"order_id": "ORD-103", "order_name": "أمر عمل 103", "required_resource_id": "R-02", "duration_hours": 6, "deadline_hour": 16, "material_id": "MAT-01", "material_qty": 25, "priority": 1},
            {"order_id": "ORD-104", "order_name": "أمر عمل 104", "required_resource_id": "R-02", "duration_hours": 3, "deadline_hour": 20, "material_id": "MAT-03", "material_qty": 10, "priority": 3},
            {"order_id": "ORD-105", "order_name": "أمر عمل 105", "required_resource_id": "R-03", "duration_hours": 7, "deadline_hour": 22, "material_id": "MAT-02", "material_qty": 30, "priority": 2},
            {"order_id": "ORD-106", "order_name": "أمر عمل 106", "required_resource_id": "R-03", "duration_hours": 4, "deadline_hour": 15, "material_id": "MAT-03", "material_qty": 12, "priority": 1},
        ]
    )

    stock_df = pd.DataFrame(
        [
            {"material_id": "MAT-01", "material_name": "مادة أساسية 1", "available_qty": 100, "unit": "وحدة"},
            {"material_id": "MAT-02", "material_name": "مادة أساسية 2", "available_qty": 80, "unit": "وحدة"},
            {"material_id": "MAT-03", "material_name": "مادة أساسية 3", "available_qty": 60, "unit": "وحدة"},
        ]
    )
    return resources_df, orders_df, stock_df


def to_excel_bytes(resources_df: pd.DataFrame, orders_df: pd.DataFrame, stock_df: pd.DataFrame) -> bytes:
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        resources_df.to_excel(writer, sheet_name="Resources", index=False)
        orders_df.to_excel(writer, sheet_name="Orders", index=False)
        stock_df.to_excel(writer, sheet_name="Stock", index=False)
    return output.getvalue()


# -----------------------------------------------------------------------------
# Generic OR-Tools CP-SAT Optimization Engine
# -----------------------------------------------------------------------------
def solve_schedule(
    resources_df: pd.DataFrame,
    orders_df: pd.DataFrame,
    stock_df: pd.DataFrame,
    objective_mode: str,
) -> Dict:
    if resources_df.empty or orders_df.empty:
        return {"status": "ERROR", "message": "يجب توفر بيانات الموارد والطلبات لتشغيل المحرك."}

    res_map = resources_df.set_index("resource_id").to_dict(orient="index")
    stock_map = (
        stock_df.set_index("material_id")["available_qty"].to_dict()
        if not stock_df.empty and "material_id" in stock_df.columns
        else {}
    )

    # Validate material stock availability
    if "material_id" in orders_df.columns and "material_qty" in orders_df.columns:
        required_stock = orders_df.groupby("material_id")["material_qty"].sum().to_dict()
        shortages = []
        for mat_id, req_qty in required_stock.items():
            avail = stock_map.get(mat_id, 0)
            if req_qty > avail:
                shortages.append(f"{mat_id} (المطلوب: {req_qty}، المتاح: {avail})")
        if shortages:
            return {
                "status": "ERROR",
                "message": "عجز في المخزون للمواد التالية: " + " | ".join(shortages),
            }

    model = cp_model.CpModel()

    # Compute safe upper bound horizon
    total_horizon = 0
    for _, order in orders_df.iterrows():
        r_id = order["required_resource_id"]
        if r_id not in res_map:
            return {"status": "ERROR", "message": f"المورد '{r_id}' غير موجود في جدول الموارد."}
        setup = int(res_map[r_id].get("setup_time_hours", 0))
        dur = int(order["duration_hours"])
        total_horizon += dur + setup
    horizon = max(total_horizon, int(orders_df["deadline_hour"].max()) if not orders_df.empty else 100)

    intervals_by_resource: Dict[str, list] = {r_id: [] for r_id in res_map}
    order_vars = []
    total_cost_terms = []

    for idx, order in orders_df.iterrows():
        o_id = str(order["order_id"])
        o_name = str(order.get("order_name", o_id))
        r_id = str(order["required_resource_id"])
        res_info = res_map[r_id]

        dur = max(1, int(order["duration_hours"]))
        setup = max(0, int(res_info.get("setup_time_hours", 0)))
        effective_dur = dur + setup
        deadline = int(order["deadline_hour"])
        hourly_cost = int(res_info.get("hourly_cost", 0))

        start_var = model.NewIntVar(0, horizon, f"start_{o_id}_{idx}")
        end_var = model.NewIntVar(0, horizon, f"end_{o_id}_{idx}")
        interval_var = model.NewIntervalVar(start_var, effective_dur, end_var, f"interval_{o_id}_{idx}")

        # Deadline constraint
        model.Add(end_var <= deadline)

        intervals_by_resource[r_id].append(interval_var)
        order_cost = effective_dur * hourly_cost
        total_cost_terms.append(order_cost)

        order_vars.append(
            {
                "order_id": o_id,
                "order_name": o_name,
                "resource_id": r_id,
                "resource_name": str(res_info.get("resource_name", r_id)),
                "duration_hours": dur,
                "setup_time_hours": setup,
                "effective_duration": effective_dur,
                "deadline_hour": deadline,
                "hourly_cost": hourly_cost,
                "order_cost": order_cost,
                "start_var": start_var,
                "end_var": end_var,
            }
        )

    # Resource capacity & non-overlapping constraints
    for r_id, intervals in intervals_by_resource.items():
        if not intervals:
            continue
        cap = max(1, int(res_map[r_id].get("capacity", 1)))
        if cap == 1:
            model.AddNoOverlap(intervals)
        else:
            model.AddCumulative(intervals, [1] * len(intervals), cap)

    makespan = model.NewIntVar(0, horizon, "makespan")
    model.AddMaxEquality(makespan, [ov["end_var"] for ov in order_vars])

    if "Makespan" in objective_mode:
        model.Minimize(makespan)
    else:
        # Minimize Cost primary, Makespan secondary tie-breaker
        total_cost = sum(total_cost_terms)
        model.Minimize(total_cost * 1000 + makespan)

    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = 15.0
    status = solver.Solve(model)

    if status not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        return {
            "status": "INFEASIBLE",
            "message": "لم يتم العثور على جدول زمني يحقق جميع القيود والمواعيد النهائية. يرجى مراجعة السعات أو المواعيد النهائية.",
        }

    schedule_rows = []
    for ov in order_vars:
        s = solver.Value(ov["start_var"])
        e = solver.Value(ov["end_var"])
        schedule_rows.append(
            {
                "رقم الطلب": ov["order_id"],
                "اسم الطلب": ov["order_name"],
                "المورد": ov["resource_name"],
                "رمز المورد": ov["resource_id"],
                "وقت البدء (ساعة)": s,
                "وقت الانتهاء (ساعة)": e,
                "مدة التنفيذ (ساعة)": ov["duration_hours"],
                "وقت التجهيز (ساعة)": ov["setup_time_hours"],
                "المدة الإجمالية (ساعة)": ov["effective_duration"],
                "الموعد النهائي (ساعة)": ov["deadline_hour"],
                "التكلفة التشغيلية": ov["order_cost"],
            }
        )

    schedule_df = pd.DataFrame(schedule_rows).sort_values(by=["وقت البدء (ساعة)", "رقم الطلب"]).reset_index(drop=True)
    total_makespan = int(solver.Value(makespan))
    total_cost_val = int(sum(ov["order_cost"] for ov in order_vars))
    total_active_hours = int(sum(ov["effective_duration"] for ov in order_vars))
    total_available_capacity = sum(max(1, int(res_map[r]["capacity"])) * max(1, total_makespan) for r in res_map)
    utilization = round((total_active_hours / total_available_capacity) * 100, 1) if total_available_capacity > 0 else 0.0

    return {
        "status": "OPTIMAL" if status == cp_model.OPTIMAL else "FEASIBLE",
        "schedule_df": schedule_df,
        "makespan": total_makespan,
        "total_cost": total_cost_val,
        "utilization": utilization,
    }


# -----------------------------------------------------------------------------
# Main UI
# -----------------------------------------------------------------------------
st.title("⚡ قرار | Qarar AI")
st.caption("محرك دعم القرار وجدولة العمليات الذكي — Universal AI Decision & Resource Optimization Dashboard")

with st.sidebar:
    st.header("⚙️ إعدادات البيانات")
    use_sample = st.toggle("استخدام بيانات تجريبية جاهزة", value=True)

    sample_res, sample_ord, sample_stk = get_sample_data()
    template_bytes = to_excel_bytes(sample_res, sample_ord, sample_stk)

    st.download_button(
        label="📥 تحميل قالب Excel القياسي (3 أوراق)",
        data=template_bytes,
        file_name="qarar_template.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        use_container_width=True,
    )

    uploaded_file = st.file_uploader(
        "رفع ملف Excel مخصص (.xlsx)",
        type=["xlsx"],
        help="يجب أن يحتوي الملف على 3 أوراق: Resources, Orders, Stock",
    )

    st.divider()
    st.header("🎯 هدف التحسين")
    objective_choice = st.radio(
        "اختر معيار التحسين الأساسي:",
        options=[
            "أسرع وقت تسليم | Minimize Makespan",
            "أقل تكلفة تشغيلية | Minimize Cost",
        ],
    )

# Load Data
if uploaded_file is not None and not use_sample:
    try:
        excel_data = pd.read_excel(uploaded_file, sheet_name=None)
        resources_df = excel_data.get("Resources", sample_res)
        orders_df = excel_data.get("Orders", sample_ord)
        stock_df = excel_data.get("Stock", sample_stk)
    except Exception as exc:
        st.error(f"تعذر قراءة ملف Excel: {exc}")
        resources_df, orders_df, stock_df = sample_res, sample_ord, sample_stk
else:
    resources_df, orders_df, stock_df = sample_res, sample_ord, sample_stk

# Editable Data Tabs
st.subheader("📋 مدخلات النظام (قابلة للتعديل المباشر)")
tab_res, tab_ord, tab_stk = st.tabs(["الموارد | Resources", "الطلبات | Orders", "المخزون | Stock"])

with tab_res:
    edited_resources = st.data_editor(resources_df, num_rows="dynamic", use_container_width=True, key="res_editor")

with tab_ord:
    edited_orders = st.data_editor(orders_df, num_rows="dynamic", use_container_width=True, key="ord_editor")

with tab_stk:
    edited_stock = st.data_editor(stock_df, num_rows="dynamic", use_container_width=True, key="stk_editor")

st.divider()

# Run Optimization
if st.button("🚀 تشغيل محرك القرار الذكي (Optimize)", type="primary", use_container_width=True):
    with st.spinner("جاري حل نموذج الجدولة باستخدام Google OR-Tools..."):
        result = solve_schedule(edited_resources, edited_orders, edited_stock, objective_choice)

    if result["status"] in ("ERROR", "INFEASIBLE"):
        st.error(result["message"])
    else:
        st.success("✅ تم إيجاد الجدول الزمني الأمثل بنجاح!")

        # Executive KPI Cards
        k1, k2, k3, k4 = st.columns(4)
        k1.metric("إجمالي الطلبات المجدولة", f"{len(result['schedule_df'])}")
        k2.metric("زمن التنفيذ الكلي (Makespan)", f"{result['makespan']} ساعة")
        k3.metric("التكلفة التشغيلية المقدرة", f"{result['total_cost']:,}")
        k4.metric("نسبة استغلال الموارد", f"{result['utilization']}%")

        # Interactive Horizontal Gantt Chart (plotly.express.bar)
        st.subheader("📊 مخطط جانت التفاعلي (Gantt Chart)")
        df_plot = result["schedule_df"].copy()
        fig = px.bar(
            df_plot,
            base="وقت البدء (ساعة)",
            x="المدة الإجمالية (ساعة)",
            y="المورد",
            color="اسم الطلب",
            orientation="h",
            hover_data=["رقم الطلب", "وقت البدء (ساعة)", "وقت الانتهاء (ساعة)", "الموعد النهائي (ساعة)", "التكلفة التشغيلية"],
            title="الجدول الزمني لتوزيع العمليات على الموارد",
        )
        fig.update_layout(
            xaxis_title="الزمن (بالساعات)",
            yaxis_title="المورد",
            barmode="overlay",
            height=420,
            legend_title="الطلبات",
        )
        st.plotly_chart(fig, use_container_width=True)

        # Exportable Execution Plan Table
        st.subheader("📑 خطة التنفيذ التفصيلية")
        st.dataframe(df_plot, use_container_width=True)

        csv_bytes = df_plot.to_csv(index=False).encode("utf-8-sig")
        st.download_button(
            label="⬇️ تصدير خطة التنفيذ (CSV)",
            data=csv_bytes,
            file_name="qarar_execution_plan.csv",
            mime="text/csv",
        )
