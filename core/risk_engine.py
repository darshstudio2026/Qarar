import random
from typing import Dict
import pandas as pd
from core.solver_engine import solve_schedule


def run_monte_carlo_risk(
    resources_df: pd.DataFrame,
    orders_df: pd.DataFrame,
    stock_df: pd.DataFrame,
    objective_mode: str,
    shift_hours_per_day: int = 24,
    n_simulations: int = 30,
) -> Dict:
    """
    Runs N Monte Carlo simulations with stochastic duration jitter (+/- 20%)
    and stock fluctuations (-15% to +10%) to estimate On-Time Delivery Probability & P95 Cost.
    """
    feasible_count = 0
    makespans = []
    costs = []

    for _ in range(n_simulations):
        demand_mult = random.uniform(0.85, 1.20)
        stock_mult = random.uniform(0.85, 1.10)
        res = solve_schedule(
            resources_df,
            orders_df,
            stock_df,
            objective_mode=objective_mode,
            demand_multiplier=demand_mult,
            stock_multiplier=stock_mult,
            shift_hours_per_day=shift_hours_per_day,
        )
        if res.get("status") in ("OPTIMAL", "FEASIBLE"):
            feasible_count += 1
            makespans.append(res["makespan"])
            costs.append(res["total_cost"])

    on_time_prob = round((feasible_count / n_simulations) * 100, 1) if n_simulations > 0 else 0.0
    avg_makespan = round(sum(makespans) / len(makespans), 1) if makespans else 0.0
    avg_cost = int(sum(costs) / len(costs)) if costs else 0
    p95_cost = int(sorted(costs)[int(0.95 * (len(costs) - 1))]) if costs else 0

    return {
        "n_simulations": n_simulations,
        "feasible_count": feasible_count,
        "on_time_probability": on_time_prob,
        "avg_makespan": avg_makespan,
        "avg_cost": avg_cost,
        "p95_cost": p95_cost,
        "risk_level": "منخفض 🟢" if on_time_prob >= 85 else ("متوسط 🟡" if on_time_prob >= 60 else "مرتفع 🔴"),
    }
