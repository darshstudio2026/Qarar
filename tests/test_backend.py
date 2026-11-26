import unittest
import pandas as pd

from core.data_adapter import auto_map_columns, get_industry_preset
from core.database import (
    get_optimization_history,
    init_db,
    load_company_data,
    login_company,
    register_company,
    save_company_data,
    save_optimization_run,
)
from core.risk_engine import run_monte_carlo_risk
from core.solver_engine import solve_schedule
from utils.report_generator import generate_excel_report, generate_html_report


class TestQararBackend(unittest.TestCase):
    def setUp(self):
        self.r, self.o, self.s = get_industry_preset("مصنع تصنيع وتجميع")

    def test_solver_all_objectives(self):
        for mode in [
            "أسرع وقت تسليم | Minimize Makespan",
            "أقل تكلفة تشغيلية | Minimize Cost",
            "توازن ذكي | Balanced",
        ]:
            res = solve_schedule(self.r, self.o, self.s, objective_mode=mode)
            self.assertIn(res["status"], ("OPTIMAL", "FEASIBLE"))
            self.assertGreater(res["makespan"], 0)
            self.assertGreater(res["total_cost"], 0)

    def test_solver_nan_and_empty_rows(self):
        r_nan = pd.concat([self.r, pd.DataFrame([{"resource_id": None, "capacity": None}])], ignore_index=True)
        o_nan = pd.concat([self.o, pd.DataFrame([{"order_id": None, "duration_hours": "bad"}])], ignore_index=True)
        res = solve_schedule(r_nan, o_nan, self.s)
        self.assertIn(res["status"], ("OPTIMAL", "FEASIBLE"))

    def test_solver_stock_shortage(self):
        s_low = self.s.copy()
        s_low["available_qty"] = 1
        res = solve_schedule(self.r, self.o, s_low)
        self.assertEqual(res["status"], "ERROR")

    def test_solver_disabled_resources(self):
        all_ids = self.r["resource_id"].astype(str).tolist()
        res = solve_schedule(self.r, self.o, self.s, disabled_resources=all_ids)
        self.assertEqual(res["status"], "ERROR")

    def test_solver_multi_resource_routing(self):
        o_flex = self.o.copy()
        o_flex.loc[0, "required_resource_id"] = "R-01,R-02"
        res = solve_schedule(self.r, o_flex, self.s)
        self.assertIn(res["status"], ("OPTIMAL", "FEASIBLE"))

    def test_data_adapter_presets_and_mapping(self):
        for p in ["مصنع تصنيع وتجميع", "شركة توزيع ولوجستيات", "إدارة مشاريع وفرق عمل"]:
            r, o, s = get_industry_preset(p)
            self.assertFalse(r.empty)
            self.assertFalse(o.empty)
            self.assertFalse(s.empty)

        raw = pd.DataFrame([{"رقم الطلب": "X1", "اسم الطلب": "اختبار", "رمز المورد": "R-01", "المدة": 3}])
        mapped, report = auto_map_columns(raw, "Orders")
        self.assertIn("order_id", mapped.columns)
        self.assertEqual(mapped.iloc[0]["order_id"], "X1")

    def test_risk_engine_monte_carlo(self):
        mc = run_monte_carlo_risk(self.r, self.o, self.s, "Balanced", n_simulations=10)
        self.assertEqual(mc["n_simulations"], 10)
        self.assertGreaterEqual(mc["on_time_probability"], 0.0)
        self.assertLessEqual(mc["on_time_probability"], 100.0)

    def test_database_persistence(self):
        init_db()
        ok, _, comp = register_company("UnitTest Co", "unittest@qarar.ai", "secret")
        if not ok:
            ok, _, comp = login_company("unittest@qarar.ai", "secret")
        self.assertTrue(ok)
        cid = comp["company_id"]
        save_company_data(cid, self.r, self.o, self.s)
        lr, lo, ls = load_company_data(cid)
        self.assertEqual(len(lr), len(self.r))
        res = solve_schedule(lr, lo, ls)
        rid = save_optimization_run(cid, "UnitTest Run", "Makespan", res)
        self.assertGreater(rid, 0)
        hist = get_optimization_history(cid)
        self.assertFalse(hist.empty)

    def test_report_generator(self):
        res = solve_schedule(self.r, self.o, self.s)
        xlsx = generate_excel_report(res)
        html = generate_html_report(res)
        self.assertGreater(len(xlsx), 100)
        self.assertIn("<html", html)


if __name__ == "__main__":
    unittest.main()
