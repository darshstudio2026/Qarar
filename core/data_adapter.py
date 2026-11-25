from difflib import get_close_matches
from typing import Dict, List, Tuple
import pandas as pd

REQUIRED_SCHEMAS = {
    "Resources": ["resource_id", "resource_name", "capacity", "hourly_cost", "setup_time_hours"],
    "Orders": ["order_id", "order_name", "required_resource_id", "duration_hours", "deadline_hour", "material_id", "material_qty", "priority"],
    "Stock": ["material_id", "material_name", "available_qty", "unit"],
}

COLUMN_SYNONYMS: Dict[str, List[str]] = {
    "resource_id": ["resource_id", "res_id", "machine_id", "id", "رمز المورد", "كود المورد", "رقم المورد", "معرف المورد"],
    "resource_name": ["resource_name", "res_name", "machine_name", "name", "اسم المورد", "المورد", "الماكينة", "الفريق"],
    "capacity": ["capacity", "cap", "slots", "units", "السعة", "الطاقة الاستيعابية", "العدد"],
    "hourly_cost": ["hourly_cost", "cost_per_hour", "rate", "cost", "تكلفة الساعة", "التكلفة", "السعر"],
    "setup_time_hours": ["setup_time_hours", "setup_time", "setup", "prep_time", "وقت التجهيز", "زمن الإعداد"],
    "order_id": ["order_id", "job_id", "task_id", "id", "رقم الطلب", "كود الطلب", "رقم المهمة"],
    "order_name": ["order_name", "job_name", "task_name", "title", "اسم الطلب", "الطلب", "المهمة", "الوصف"],
    "required_resource_id": ["required_resource_id", "resource_id", "res_id", "assigned_to", "المورد المطلوب", "رمز المورد"],
    "duration_hours": ["duration_hours", "duration", "hours", "time", "المدة", "مدة التنفيذ", "الساعات"],
    "deadline_hour": ["deadline_hour", "deadline", "due_hour", "due", "الموعد النهائي", "تاريخ التسليم"],
    "material_id": ["material_id", "mat_id", "item_id", "sku", "رمز المادة", "كود الصنف", "المادة"],
    "material_qty": ["material_qty", "qty", "quantity", "amount", "الكمية المطلوبة", "الكمية"],
    "priority": ["priority", "prio", "urgency", "الأولوية", "الأهمية"],
    "material_name": ["material_name", "item_name", "name", "اسم المادة", "الصنف"],
    "available_qty": ["available_qty", "stock_qty", "on_hand", "qty", "الكمية المتاحة", "المخزون"],
    "unit": ["unit", "uom", "الوحدة", "وحدة القياس"],
}


def auto_map_columns(df: pd.DataFrame, target_sheet: str) -> Tuple[pd.DataFrame, Dict[str, str]]:
    """
    Intelligent Arabic/English Auto-Column Mapper using semantic synonyms + fuzzy matching.
    Returns (mapped_df, mapping_report).
    """
    target_cols = REQUIRED_SCHEMAS.get(target_sheet, [])
    source_cols = list(df.columns)
    lower_source_map = {str(c).strip().lower(): c for c in source_cols}

    mapping: Dict[str, str] = {}
    used_sources = set()

    for target in target_cols:
        # 1. Exact or synonym match
        matched_src = None
        for syn in COLUMN_SYNONYMS.get(target, [target]):
            syn_l = syn.lower()
            if syn_l in lower_source_map and lower_source_map[syn_l] not in used_sources:
                matched_src = lower_source_map[syn_l]
                break

        # 2. Fuzzy match fallback
        if not matched_src:
            candidates = [s for s in lower_source_map.keys() if lower_source_map[s] not in used_sources]
            close = get_close_matches(target.lower(), candidates, n=1, cutoff=0.55)
            if close:
                matched_src = lower_source_map[close[0]]

        if matched_src:
            mapping[target] = str(matched_src)
            used_sources.add(matched_src)

    mapped_df = df.copy()
    rename_dict = {v: k for k, v in mapping.items()}
    mapped_df = mapped_df.rename(columns=rename_dict)

    # Fill missing required columns with safe defaults
    for col in target_cols:
        if col not in mapped_df.columns:
            if col in ("capacity", "priority"):
                mapped_df[col] = 1
            elif col in ("hourly_cost", "setup_time_hours", "material_qty", "available_qty"):
                mapped_df[col] = 0
            elif col == "duration_hours":
                mapped_df[col] = 2
            elif col == "deadline_hour":
                mapped_df[col] = 24
            elif col == "unit":
                mapped_df[col] = "وحدة"
            else:
                mapped_df[col] = f"N/A"

    return mapped_df[target_cols], mapping


def load_uploaded_file(uploaded_file) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, Dict[str, Dict[str, str]]]:
    """
    Universal Data Ingestion Engine for .xlsx and .csv files.
    """
    name = uploaded_file.name.lower()
    mapping_report: Dict[str, Dict[str, str]] = {}

    if name.endswith(".csv"):
        raw_df = pd.read_csv(uploaded_file)
        ord_df, ord_map = auto_map_columns(raw_df, "Orders")
        mapping_report["Orders"] = ord_map
        res_df, ord_default, stk_df = get_industry_preset("مصنع تصنيع وتجميع")
        return res_df, ord_df, stk_df, mapping_report

    excel_data = pd.read_excel(uploaded_file, sheet_name=None)
    res_raw = excel_data.get("Resources", list(excel_data.values())[0])
    ord_raw = excel_data.get("Orders", list(excel_data.values())[min(1, len(excel_data) - 1)])
    stk_raw = excel_data.get("Stock", list(excel_data.values())[min(2, len(excel_data) - 1)])

    res_df, res_map = auto_map_columns(res_raw, "Resources")
    ord_df, ord_map = auto_map_columns(ord_raw, "Orders")
    stk_df, stk_map = auto_map_columns(stk_raw, "Stock")

    mapping_report = {"Resources": res_map, "Orders": ord_map, "Stock": stk_map}
    return res_df, ord_df, stk_df, mapping_report


def load_from_url(url: str) -> Tuple[pd.DataFrame, Dict[str, str]]:
    """
    Live Two-Way Sync: Loads Orders directly from a Google Sheets CSV export URL or any CSV URL.
    """
    clean_url = url.strip()
    if "docs.google.com/spreadsheets" in clean_url and "/edit" in clean_url:
        clean_url = clean_url.split("/edit")[0] + "/export?format=csv"
    raw_df = pd.read_csv(clean_url)
    return auto_map_columns(raw_df, "Orders")


def get_industry_preset(preset_name: str) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """
    1-Click Industry Presets demonstrating universal Plug & Play versatility.
    """
    if "توزيع" in preset_name or "لوجستيات" in preset_name:
        resources_df = pd.DataFrame([
            {"resource_id": "TRK-01", "resource_name": "شاحنة نقل ثقيل 1", "capacity": 1, "hourly_cost": 180, "setup_time_hours": 1},
            {"resource_id": "TRK-02", "resource_name": "شاحنة مبردة 2", "capacity": 1, "hourly_cost": 220, "setup_time_hours": 1},
            {"resource_id": "VAN-03", "resource_name": "أسطول توصيل سريع", "capacity": 2, "hourly_cost": 110, "setup_time_hours": 0},
        ])
        orders_df = pd.DataFrame([
            {"order_id": "SHP-201", "order_name": "شحنة المنطقة الشمالية", "required_resource_id": "TRK-01", "duration_hours": 5, "deadline_hour": 16, "material_id": "PKG-A", "material_qty": 40, "priority": 1},
            {"order_id": "SHP-202", "order_name": "شحنة المنطقة الشرقية", "required_resource_id": "TRK-01", "duration_hours": 4, "deadline_hour": 18, "material_id": "PKG-B", "material_qty": 25, "priority": 2},
            {"order_id": "SHP-203", "order_name": "توريد مبرد مركزي", "required_resource_id": "TRK-02", "duration_hours": 6, "deadline_hour": 15, "material_id": "PKG-A", "material_qty": 30, "priority": 1},
            {"order_id": "SHP-204", "order_name": "توزيع نقاط البيع 1", "required_resource_id": "VAN-03", "duration_hours": 3, "deadline_hour": 12, "material_id": "PKG-C", "material_qty": 15, "priority": 1},
            {"order_id": "SHP-205", "order_name": "توزيع نقاط البيع 2", "required_resource_id": "VAN-03", "duration_hours": 4, "deadline_hour": 14, "material_id": "PKG-B", "material_qty": 20, "priority": 2},
        ])
        stock_df = pd.DataFrame([
            {"material_id": "PKG-A", "material_name": "طبليات قياسية أ", "available_qty": 120, "unit": "طبلية"},
            {"material_id": "PKG-B", "material_name": "صناديق تغليف ب", "available_qty": 90, "unit": "صندوق"},
            {"material_id": "PKG-C", "material_name": "حاويات سريعة ج", "available_qty": 60, "unit": "حاوية"},
        ])
        return resources_df, orders_df, stock_df

    if "مشاريع" in preset_name or "فرق" in preset_name:
        resources_df = pd.DataFrame([
            {"resource_id": "TM-DEV", "resource_name": "فريق التطوير البرمجي", "capacity": 2, "hourly_cost": 250, "setup_time_hours": 1},
            {"resource_id": "TM-QA", "resource_name": "فريق الجودة والاختبار", "capacity": 1, "hourly_cost": 160, "setup_time_hours": 1},
            {"resource_id": "TM-OPS", "resource_name": "فريق البنية والتشغيل", "capacity": 1, "hourly_cost": 200, "setup_time_hours": 0},
        ])
        orders_df = pd.DataFrame([
            {"order_id": "TSK-301", "order_name": "بناء واجهة برمجة التطبيقات", "required_resource_id": "TM-DEV", "duration_hours": 6, "deadline_hour": 18, "material_id": "LIC-01", "material_qty": 2, "priority": 1},
            {"order_id": "TSK-302", "order_name": "تطوير لوحة التحكم", "required_resource_id": "TM-DEV", "duration_hours": 5, "deadline_hour": 20, "material_id": "LIC-01", "material_qty": 2, "priority": 2},
            {"order_id": "TSK-303", "order_name": "اختبار التكامل والأداء", "required_resource_id": "TM-QA", "duration_hours": 4, "deadline_hour": 16, "material_id": "ENV-01", "material_qty": 1, "priority": 1},
            {"order_id": "TSK-304", "order_name": "تهيئة السحابة والنشر", "required_resource_id": "TM-OPS", "duration_hours": 3, "deadline_hour": 14, "material_id": "ENV-01", "material_qty": 1, "priority": 1},
        ])
        stock_df = pd.DataFrame([
            {"material_id": "LIC-01", "material_name": "تراخيص تطوير سحابية", "available_qty": 10, "unit": "رخصة"},
            {"material_id": "ENV-01", "material_name": "بيئات اختبار معزولة", "available_qty": 5, "unit": "بيئة"},
        ])
        return resources_df, orders_df, stock_df

    # Default: "مصنع تصنيع وتجميع"
    resources_df = pd.DataFrame([
        {"resource_id": "R-01", "resource_name": "خط التجميع الرئيسي أ", "capacity": 1, "hourly_cost": 120, "setup_time_hours": 1},
        {"resource_id": "R-02", "resource_name": "وحدة التشغيل الدقيقة ب", "capacity": 1, "hourly_cost": 95, "setup_time_hours": 1},
        {"resource_id": "R-03", "resource_name": "محطة التغليف والفحص ج", "capacity": 2, "hourly_cost": 150, "setup_time_hours": 2},
    ])
    orders_df = pd.DataFrame([
        {"order_id": "ORD-101", "order_name": "أمر إنتاج 101", "required_resource_id": "R-01", "duration_hours": 4, "deadline_hour": 14, "material_id": "MAT-01", "material_qty": 20, "priority": 1},
        {"order_id": "ORD-102", "order_name": "أمر إنتاج 102", "required_resource_id": "R-01", "duration_hours": 5, "deadline_hour": 18, "material_id": "MAT-02", "material_qty": 15, "priority": 2},
        {"order_id": "ORD-103", "order_name": "أمر إنتاج 103", "required_resource_id": "R-02", "duration_hours": 6, "deadline_hour": 16, "material_id": "MAT-01", "material_qty": 25, "priority": 1},
        {"order_id": "ORD-104", "order_name": "أمر إنتاج 104", "required_resource_id": "R-02", "duration_hours": 3, "deadline_hour": 20, "material_id": "MAT-03", "material_qty": 10, "priority": 3},
        {"order_id": "ORD-105", "order_name": "أمر إنتاج 105", "required_resource_id": "R-03", "duration_hours": 7, "deadline_hour": 22, "material_id": "MAT-02", "material_qty": 30, "priority": 2},
        {"order_id": "ORD-106", "order_name": "أمر إنتاج 106", "required_resource_id": "R-03", "duration_hours": 4, "deadline_hour": 15, "material_id": "MAT-03", "material_qty": 12, "priority": 1},
    ])
    stock_df = pd.DataFrame([
        {"material_id": "MAT-01", "material_name": "مادة أساسية 1", "available_qty": 100, "unit": "وحدة"},
        {"material_id": "MAT-02", "material_name": "مادة أساسية 2", "available_qty": 80, "unit": "وحدة"},
        {"material_id": "MAT-03", "material_name": "مادة أساسية 3", "available_qty": 60, "unit": "وحدة"},
    ])
    return resources_df, orders_df, stock_df
