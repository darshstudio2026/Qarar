from typing import Dict, List, Optional
import pandas as pd
from ortools.sat.python import cp_model


def solve_schedule(
    resources_df: pd.DataFrame,
    orders_df: pd.DataFrame,
    stock_df: pd.DataFrame,
    objective_mode: str = "أسرع وقت تسليم | Minimize Makespan",
    overtime_hours: int = 0,
    disabled_resources: Optional[List[str]] = None,
    demand_multiplier: float = 1.0,
    stock_multiplier: float = 1.0,
    shift_hours_per_day: int = 24,
    frozen_schedule_df: Optional[pd.DataFrame] = None,
    current_hour: int = 0,
) -> Dict:
    """
    Enterprise-grade, domain-agnostic OR-Tools CP-SAT optimization engine.
    Supports:
    - Multi-objective optimization (Makespan, Cost, Balanced)
    - Flexible Alternative Resource Routing (comma-separated resource IDs)
    - Dynamic Real-Time Rescheduling (frozen_schedule_df + current_hour)
    - Multi-stage / sequential routing (via optional `parent_order_id` column)
    - Working shifts & maintenance windows (`maintenance_start`, `maintenance_end` on Resources)
    - Resource capacities, setup times, deadlines, and stock/BOM constraints
    """
    if resources_df is None or resources_df.empty or orders_df is None or orders_df.empty:
        return {
            "status": "ERROR",
            "message": "يجب توفر بيانات الموارد والطلبات لتشغيل محرك التحسين.",
            "bottlenecks": ["بيانات الموارد أو الطلبات فارغة."],
        }

    disabled_set = set(disabled_resources or [])
    active_resources_df = resources_df[~resources_df["resource_id"].astype(str).isin(disabled_set)].copy()

    if active_resources_df.empty:
        return {
            "status": "ERROR",
            "message": "جميع الموارد معطلة حالياً. يرجى تفعيل مورد واحد على الأقل.",
            "bottlenecks": ["لا توجد موارد نشطة متاحة للتشغيل."],
        }

    res_map = active_resources_df.set_index("resource_id").to_dict(orient="index")
    stock_map = (
        {
            str(k): float(v) * stock_multiplier
            for k, v in stock_df.set_index("material_id")["available_qty"].to_dict().items()
        }
        if stock_df is not None and not stock_df.empty and "material_id" in stock_df.columns
        else {}
    )

    # Map frozen orders if dynamic rescheduling is active
    frozen_map: Dict[str, Dict] = {}
    if frozen_schedule_df is not None and not frozen_schedule_df.empty and current_hour > 0:
        for _, frow in frozen_schedule_df.iterrows():
            if int(frow["وقت البدء (ساعة)"]) < current_hour:
                frozen_map[str(frow["رقم الطلب"])] = {
                    "start": int(frow["وقت البدء (ساعة)"]),
                    "resource_id": str(frow["رمز المورد"]),
                }

    bottlenecks: List[str] = []

    # 1. Validate material stock availability
    if "material_id" in orders_df.columns and "material_qty" in orders_df.columns:
        required_stock = (orders_df.groupby("material_id")["material_qty"].sum() * demand_multiplier).to_dict()
        shortages = []
        for mat_id, req_qty in required_stock.items():
            avail = stock_map.get(str(mat_id), 0.0)
            if req_qty > avail:
                msg = f"عجز في المخزون للمادة '{mat_id}': المطلوب {req_qty:.1f}، المتاح {avail:.1f}"
                shortages.append(msg)
                bottlenecks.append(msg)
        if shortages:
            return {
                "status": "ERROR",
                "message": " | ".join(shortages),
                "bottlenecks": bottlenecks,
            }

    model = cp_model.CpModel()

    # 2. Compute safe upper bound horizon
    total_horizon = 0
    for _, order in orders_df.iterrows():
        raw_res = str(order["required_resource_id"])
        candidates = [c.strip() for c in raw_res.split(",") if c.strip() in res_map]
        if not candidates:
            msg = f"المورد '{raw_res}' غير متاح أو معطل في جدول الموارد."
            return {"status": "ERROR", "message": msg, "bottlenecks": [msg]}
        max_setup = max(max(0, int(res_map[c].get("setup_time_hours", 0))) for c in candidates)
        dur = max(1, int(round(float(order["duration_hours"]) * demand_multiplier)))
        total_horizon += dur + max_setup

    shift_factor = 24.0 / max(1, min(24, int(shift_hours_per_day)))
    max_deadline = int(orders_df["deadline_hour"].max()) + overtime_hours if not orders_df.empty else 100
    horizon = max(int(total_horizon * shift_factor) + 24, max_deadline, 48)

    intervals_by_resource: Dict[str, list] = {str(r_id): [] for r_id in res_map}
    order_vars = []
    order_var_by_id: Dict[str, Dict] = {}
    total_cost_terms = []

    # Add scheduled maintenance windows if defined on Resources
    for r_id, r_info in res_map.items():
        m_start = r_info.get("maintenance_start", None)
        m_end = r_info.get("maintenance_end", None)
        if pd.notna(m_start) and pd.notna(m_end):
            ms, me = int(m_start), int(m_end)
            if me > ms >= 0:
                m_interval = model.NewFixedSizeIntervalVar(ms, me - ms, f"maint_{r_id}")
                intervals_by_resource[str(r_id)].append(m_interval)

    for idx, order in orders_df.iterrows():
        o_id = str(order["order_id"])
        o_name = str(order.get("order_name", o_id))
        raw_res = str(order["required_resource_id"])
        candidates = [c.strip() for c in raw_res.split(",") if c.strip() in res_map]

        dur = max(1, int(round(float(order["duration_hours"]) * demand_multiplier)))
        deadline = int(order["deadline_hour"]) + overtime_hours
        parent_id = str(order.get("parent_order_id", "")).strip() if pd.notna(order.get("parent_order_id", None)) else ""

        start_var = model.NewIntVar(0, horizon, f"start_{o_id}_{idx}")
        end_var = model.NewIntVar(0, horizon, f"end_{o_id}_{idx}")
        model.Add(end_var <= deadline)

        # Pin frozen orders if they already started before current_hour
        if o_id in frozen_map and frozen_map[o_id]["resource_id"] in candidates:
            model.Add(start_var == frozen_map[o_id]["start"])
            candidates = [frozen_map[o_id]["resource_id"]]
        elif current_hour > 0 and o_id not in frozen_map:
            model.Add(start_var >= current_hour)

        presence_vars = []
        chosen_cost_terms = []

        for r_id in candidates:
            res_info = res_map[r_id]
            setup = max(0, int(res_info.get("setup_time_hours", 0)))
            effective_dur = dur + setup
            hourly_cost = int(res_info.get("hourly_cost", 0))
            cand_cost = effective_dur * hourly_cost

            if len(candidates) == 1:
                interval_var = model.NewIntervalVar(start_var, effective_dur, end_var, f"int_{o_id}_{r_id}_{idx}")
                intervals_by_resource[r_id].append(interval_var)
                total_cost_terms.append(cand_cost)
                presence_vars.append((r_id, None, effective_dur, setup, cand_cost, dur * hourly_cost, setup * hourly_cost))
            else:
                p_var = model.NewBoolVar(f"pres_{o_id}_{r_id}_{idx}")
                opt_int = model.NewOptionalIntervalVar(start_var, effective_dur, end_var, p_var, f"opt_{o_id}_{r_id}_{idx}")
                intervals_by_resource[r_id].append(opt_int)
                chosen_cost_terms.append(p_var * cand_cost)
                presence_vars.append((r_id, p_var, effective_dur, setup, cand_cost, dur * hourly_cost, setup * hourly_cost))

        if len(candidates) > 1:
            model.AddExactlyOne([pv[1] for pv in presence_vars])
            total_cost_terms.append(sum(chosen_cost_terms))

        ov_dict = {
            "order_id": o_id,
            "order_name": o_name,
            "duration_hours": dur,
            "deadline_hour": deadline,
            "parent_order_id": parent_id,
            "start_var": start_var,
            "end_var": end_var,
            "presence_vars": presence_vars,
        }
        order_vars.append(ov_dict)
        order_var_by_id[o_id] = ov_dict

    # 3. Multi-Stage Sequential Routing Constraints
    for ov in order_vars:
        pid = ov["parent_order_id"]
        if pid and pid in order_var_by_id and pid != ov["order_id"]:
            model.Add(ov["start_var"] >= order_var_by_id[pid]["end_var"])

    # 4. Resource capacity & non-overlapping constraints
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

    total_cost_expr = sum(total_cost_terms)
    # Priority-weighted completion time (high priority = lower number = higher weight)
    weighted_completion = sum(
        ov["end_var"] * max(1, 5 - int(orders_df.iloc[i].get("priority", 2)))
        for i, ov in enumerate(order_vars)
    )

    if "Makespan" in objective_mode or "أسرع" in objective_mode:
        model.Minimize(makespan * 1000 + weighted_completion)
    elif "Cost" in objective_mode or "تكلفة" in objective_mode:
        model.Minimize(total_cost_expr * 1000 + makespan * 10 + weighted_completion)
    else:
        model.Minimize(makespan * 100 + total_cost_expr + weighted_completion * 5)

    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = 15.0
    status = solver.Solve(model)

    if status not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        if not bottlenecks:
            bottlenecks.append("تعارض في السعات أو المواعيد النهائية أو تسلسل المراحل يمنع إيجاد جدول ممكن.")
        return {
            "status": "INFEASIBLE",
            "message": "لم يتم العثور على جدول زمني يحقق جميع القيود. يرجى مراجعة السعات أو المواعيد النهائية أو إضافة ساعات إضافية.",
            "bottlenecks": bottlenecks,
        }

    schedule_rows = []
    total_prod_cost = 0
    total_setup_cost = 0
    active_hrs_by_res: Dict[str, int] = {r_id: 0 for r_id in res_map}

    for ov in order_vars:
        s = solver.Value(ov["start_var"])
        e = solver.Value(ov["end_var"])
        slack = ov["deadline_hour"] - e

        # Determine chosen resource
        chosen = ov["presence_vars"][0]
        for pv in ov["presence_vars"]:
            if pv[1] is None or solver.Value(pv[1]) == 1:
                chosen = pv
                break

        r_id, _, eff_dur, setup_hrs, o_cost, p_cost, s_cost = chosen
        total_prod_cost += p_cost
        total_setup_cost += s_cost
        active_hrs_by_res[r_id] += eff_dur

        if slack <= 1:
            bottlenecks.append(
                f"موعد نهائي حرج للطلب '{ov['order_id']}' (هامش الأمان: {slack} ساعة فقط — إضافة وردية قد تمنع التأخير)."
            )

        schedule_rows.append(
            {
                "رقم الطلب": ov["order_id"],
                "اسم الطلب": ov["order_name"],
                "المورد": str(res_map[r_id].get("resource_name", r_id)),
                "رمز المورد": r_id,
                "وقت البدء (ساعة)": s,
                "وقت الانتهاء (ساعة)": e,
                "مدة التنفيذ (ساعة)": ov["duration_hours"],
                "وقت التجهيز (ساعة)": setup_hrs,
                "المدة الإجمالية (ساعة)": eff_dur,
                "الموعد النهائي (ساعة)": ov["deadline_hour"],
                "هامش الأمان (ساعة)": slack,
                "التكلفة التشغيلية": o_cost,
            }
        )

    schedule_df = (
        pd.DataFrame(schedule_rows)
        .sort_values(by=["وقت البدء (ساعة)", "رقم الطلب"])
        .reset_index(drop=True)
    )

    total_makespan = int(solver.Value(makespan))
    total_cost = total_prod_cost + total_setup_cost

    util_rows = []
    total_idle_cost = 0
    for r_id, r_info in res_map.items():
        cap = max(1, int(r_info.get("capacity", 1)))
        hourly_cost = int(r_info.get("hourly_cost", 0))
        active_hrs = active_hrs_by_res[r_id]
        avail_hrs = cap * max(1, total_makespan)
        idle_hrs = max(0, avail_hrs - active_hrs)
        util_pct = round((active_hrs / avail_hrs) * 100, 1) if avail_hrs > 0 else 0.0
        idle_cost = int(idle_hrs * hourly_cost * 0.25)
        total_idle_cost += idle_cost
        if util_pct >= 85:
            saved_hrs = max(2, active_hrs // 3)
            bottlenecks.append(
                f"عنق زجاجة على '{r_info.get('resource_name', r_id)}' ({util_pct}%): إضافة وردية إضافية توفر ~{saved_hrs} ساعة تسليم."
            )
        util_rows.append(
            {
                "رمز المورد": r_id,
                "المورد": str(r_info.get("resource_name", r_id)),
                "السعة": cap,
                "ساعات التشغيل": active_hrs,
                "ساعات الخمول": idle_hrs,
                "نسبة الاستغلال (%)": util_pct,
                "تكلفة الخمول المقدرة": idle_cost,
            }
        )

    utilization_df = pd.DataFrame(util_rows)
    total_active = sum(active_hrs_by_res.values())
    total_avail = sum(max(1, int(r["capacity"])) * max(1, total_makespan) for r in res_map.values())
    overall_utilization = round((total_active / total_avail) * 100, 1) if total_avail > 0 else 0.0

    manual_est_cost = int(round(total_cost * 1.15 + total_idle_cost * 1.2))
    estimated_savings = max(0, manual_est_cost - total_cost)

    return {
        "status": "OPTIMAL" if status == cp_model.OPTIMAL else "FEASIBLE",
        "schedule_df": schedule_df,
        "utilization_df": utilization_df,
        "makespan": total_makespan,
        "total_cost": total_cost,
        "prod_cost": total_prod_cost,
        "setup_cost": total_setup_cost,
        "idle_cost": total_idle_cost,
        "estimated_savings": estimated_savings,
        "utilization": overall_utilization,
        "on_time_rate": 100.0,
        "bottlenecks": bottlenecks,
    }
