"""
migrate_speech_units_to_claim_atoms.py
Phase 2: 将存量 speech_units JSON 批次文件转换为 claim_atoms 格式

支持两种源格式:
  v1 (batch1/batch2/batch5): {metadata, speech_units: [{unit_id, speaker, primary_factor,
      secondary_factor(str), content_summary, key_quote, sentiment, time_phase}]}
  v2 (batch3/batch4): {metadata, speech_units: [{meeting_date, speaker, turn_id,
      primary_factor, secondary_factors(list), tertiary_factors, type_of_claim,
      time_horizon, evidence_types, logic_chain, validation_indicators, ...}]}
"""

import json
import os
import glob
import re
from datetime import datetime, date

# ── 路径配置 ────────────────────────────────────────────────────────────────
WORK_DIR   = os.path.dirname(os.path.abspath(__file__))
ONTOLOGY_PATH = os.path.join(WORK_DIR, "factor_ontology.json")
OUTPUT_DIR   = os.path.join(WORK_DIR, "claim_atoms")
SKILL_ASSETS_DIR = r"C:\Users\123cy\.workbuddy\skills\ficc-factor-midplatform\assets\claim_atoms"

# ── 加载因子本体库 ──────────────────────────────────────────────────────────
with open(ONTOLOGY_PATH, "r", encoding="utf-8") as f:
    ontology = json.load(f)

label2id = {}
for node in ontology.get("nodes", []):
    fid = node["factor_id"]
    fname = node.get("factor_name", "")
    if fname:
        label2id[fname] = fid
    for alias in node.get("aliases", []):
        label2id[alias] = fid

# 额外手动映射
EXTRA_MAPPINGS = {
    "策略建议": "MS_005", "策略应对": "MS_005", "市场情绪": "MS_001",
    "政策面": "PL_002", "流动性": "LQ_001", "市场观察": "MS_001",
    "风险管理": "IB_009", "杠杆策略": "LQ_007", "市场分歧": "MS_001",
    "趋势判断": "MS_010", "震荡观点": "MS_010", "买点寻找": "MS_005",
    "政策窗口观察": "PL_002", "政策窗口": "PL_002", "政策风险": "PL_002",
    "政策分析": "PL_002", "政策情景分析": "PL_002", "市场分析": "MS_001",
    "风险分析": "MS_001", "经济基本面评估": "FD_001", "经济展望": "FD_001",
    "消费数据": "FD_001", "出口评估": "FD_006", "出口分析": "FD_006",
    "关税冲击": "PL_004", "供给分析": "LQ_004", "基金行为": "IB_001",
    "银行负债行为": "IB_012", "银行行为": "IB_012", "ETF分析": "IB_004",
    "绝对收益理念": "IB_009", "赔率胜率分析": "MS_005", "右侧交易": "MS_004",
    "换券逻辑": "MS_004", "交易管理": "IB_005", "交易反思": "MS_004",
    "地方债分析": "LQ_002", "五因子框架": None,
    # batch3/batch4 extra labels
    "配置盘行为": "IB_012", "情绪化抛售": "MS_003", "基金赎回负反馈": "IB_003",
    "产品赎回风险": "IB_003", "基金赎回压力": "IB_003",
    "贸易战避险效应": "PL_004", "贸易战避险": "PL_004", "贸易战常态化": "PL_004",
    "央行国债买卖": "PL_006", "央行买债落地": "PL_006", "央行买债信号意义": "PL_006",
    "央行买债对品种影响": "PL_006", "费率新规博弈": "MS_013",
    "政策出台节奏": "PL_009", "供需矛盾缓解": "LQ_004",
    "利差收窄机会": "MS_009", "加仓信号": "MS_005",
    "观点下调": "MS_013", "灵活止盈": "MS_012",
    # non-research
    "平台建设": None, "会议总结": None, "工作要求": None,
    "团队建设": None, "投资框架": None,
}
label2id.update(EXTRA_MAPPINGS)

NON_RESEARCH = {"平台建设", "会议总结", "工作要求", "团队建设", "投资框架", "五因子框架"}

# ── 映射函数 ────────────────────────────────────────────────────────────────
SENTIMENT_MAP = {
    "偏多": "利多", "中性偏多": "利多", "多": "利多", "看多": "利多",
    "乐观": "利多", "利好": "利多", "偏空": "利空", "中性偏空": "利空",
    "空": "利空", "看空": "利空", "悲观": "利空", "利空": "利空",
    "中性": "中性", "中性观望": "中性", "观望": "中性", "平衡": "中性",
}

V2_CLAIM_TYPE = {"judgment": "推论", "signal": "信号", "fact": "事实",
                 "forecast": "预期", "correction": "修正", "conditional_judgment": "推论"}
V2_HORIZON = {"short_term": "短期(1M以内)", "medium_term": "中期(1-3M)",
              "long_term": "中长期(3-6M)", "very_long_term": "长期(6M+)"}
V2_CONFIDENCE = {"high": 0.85, "medium": 0.6, "low": 0.35}


def resolve_sf(label: str) -> tuple:
    """secondary_factor label -> (factor_id or None, normalized_label or original)"""
    if not label:
        return (None, None)
    if label in label2id:
        fid = label2id[label]
        return (fid, label) if fid else (None, label)
    lc = label.replace("因子", "").strip()
    for lbl, fid in label2id.items():
        if fid is None:
            continue
        lbc = lbl.replace("因子", "").strip()
        if lbc == lc or lbc in label or lc in lbl:
            return (fid, lbl)
    return (None, label)


def map_direction(sentiment: str) -> str:
    if not sentiment:
        return "不明确"
    s = sentiment.strip()
    if s in SENTIMENT_MAP:
        return SENTIMENT_MAP[s]
    if "多" in s and "空" not in s:
        return "利多"
    if "空" in s and "多" not in s:
        return "利空"
    if "中性" in s:
        return "中性"
    return "不明确"


def infer_claim_type(content: str) -> str:
    if not content:
        return "推论"
    ct = content[:100]
    if re.search(r"\d+\.?\d*%", ct) or re.search(r"\d+bp", ct) or re.search(r"\d+万亿", ct):
        return "事实"
    if any(kw in ct for kw in ["预期", "预计", "可能", "大概率", "有望"]):
        return "预期"
    if any(kw in ct for kw in ["修正", "调整", "改变"]):
        return "修正"
    if any(kw in ct for kw in ["信号", "迹象", "苗头", "拐点"]):
        return "信号"
    return "推论"


def build_source_doc_id(batch_str: str, meeting_date: str) -> str:
    m = re.match(r"batch(\d+)", batch_str)
    if m:
        return f"{meeting_date.replace('-', '')}_B{int(m.group(1)):02d}"
    return f"{meeting_date.replace('-', '')}_B00"


# ── v1 / v2 转换 ────────────────────────────────────────────────────────────
def _convert_v1(unit: dict, idx: int, doc_id: str, mdate: str) -> dict:
    sec_label = unit.get("secondary_factor", "")
    if sec_label.strip() in NON_RESEARCH:
        return None
    sec_id, sec_norm = resolve_sf(sec_label)
    direction = map_direction(unit.get("sentiment", ""))
    ct = infer_claim_type(unit.get("content_summary", ""))
    return {
        "atom_id": f"{doc_id}_{idx+1:03d}",
        "source_doc_id": doc_id, "speaker": unit.get("speaker", ""),
        "speaker_institution": "", "speaker_role": "", "date": mdate,
        "raw_text": unit.get("key_quote", ""),
        "summary_text": unit.get("content_summary", ""),
        "primary_factor": unit.get("primary_factor", ""),
        "secondary_factor": sec_id,
        "secondary_factor_label": sec_norm or sec_label,
        "tertiary_factor": [],
        "claim_type": ct, "direction": direction,
        "magnitude": "不明确", "time_horizon": "不明确",
        "confidence_score": 0.5,
        "causal_chain_text": None, "causal_edge_ids": [],
        "trade_translation": None, "validation_metrics": [],
        "invalidation_condition": None, "related_atom_ids": [],
        "tags": [unit.get("time_phase", "")] if unit.get("time_phase") else [],
        "review_status": "待审核", "review_notes": "Phase2 v1",
        "created_at": datetime.now().isoformat(),
        "updated_at": datetime.now().isoformat(),
    }


def _convert_v2(unit: dict, idx: int, doc_id: str, mdate: str) -> dict:
    sec_list = unit.get("secondary_factors", [])
    if isinstance(sec_list, str):
        sec_list = [sec_list] if sec_list else []
    sec_id, sec_label = (resolve_sf(sec_list[0]) if sec_list else (None, None))[:2]

    logic = unit.get("logic_chain", [])
    causal = " -> ".join(logic) if logic else None
    vals = unit.get("validation_indicators", [])
    vm = [{"metric_name": v, "threshold_direction": ""} for v in vals] if vals else []
    ter = unit.get("tertiary_factors", [])
    mkt = unit.get("market_mapping", [])
    lang = unit.get("language_style_tags", [])
    tags = list(set((mkt or []) + (lang or [])))
    if unit.get("asset_focus"):
        tags.append(unit["asset_focus"])

    summary = unit.get("raw_text_summary", "")
    direction = "不明确"
    if summary:
        if any(k in summary for k in ["下行", "走低", "回落", "宽松", "利好", "机会"]):
            direction = "利多"
        elif any(k in summary for k in ["上行", "走高", "收紧", "利空", "风险"]):
            direction = "利空"

    return {
        "atom_id": f"{doc_id}_{idx+1:03d}",
        "source_doc_id": doc_id, "speaker": unit.get("speaker", ""),
        "speaker_institution": "", "speaker_role": "", "date": mdate,
        "raw_text": summary[:300] if summary else "",
        "summary_text": summary[:100] if summary else "",
        "primary_factor": unit.get("primary_factor", ""),
        "secondary_factor": sec_id,
        "secondary_factor_label": sec_label or (sec_list[0] if sec_list else ""),
        "tertiary_factor": ter[:5] if isinstance(ter, list) else [],
        "claim_type": V2_CLAIM_TYPE.get(unit.get("type_of_claim", ""), "推论"),
        "direction": direction, "magnitude": "不明确",
        "time_horizon": V2_HORIZON.get(unit.get("time_horizon", ""), "不明确"),
        "confidence_score": V2_CONFIDENCE.get(unit.get("confidence", ""), 0.5),
        "causal_chain_text": causal, "causal_edge_ids": [],
        "trade_translation": None, "validation_metrics": vm,
        "invalidation_condition": None, "related_atom_ids": [],
        "tags": tags[:10], "review_status": "待审核",
        "review_notes": "Phase2 v2 (rich source)",
        "created_at": datetime.now().isoformat(),
        "updated_at": datetime.now().isoformat(),
    }


def convert_batch(filepath: str) -> dict:
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            raw = f.read()
        raw = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f]', ' ', raw)
        data = json.loads(raw)
    except json.JSONDecodeError as e:
        return {"error": str(e), "file": os.path.basename(filepath), "claim_atoms": [], "stats": {}}

    meta = data.get("metadata", {})
    units = data.get("speech_units", [])
    if not isinstance(units, list):
        units = []

    is_v2 = bool(units and isinstance(units[0], dict) and "secondary_factors" in units[0])
    mdate = meta.get("meeting_date", "unknown")
    if mdate == "unknown" and units:
        mdate = units[0].get("meeting_date", "unknown")
    batch = meta.get("batch", "unknown")
    doc_id = build_source_doc_id(batch, mdate)

    atoms = []
    stats = {"total": len(units), "matched": 0, "unmatched": [], "skipped": 0, "format": "v2" if is_v2 else "v1"}

    for idx, unit in enumerate(units):
        atom = _convert_v2(unit, idx, doc_id, mdate) if is_v2 else _convert_v1(unit, idx, doc_id, mdate)
        if atom is None:
            stats["skipped"] += 1
            continue
        if atom.get("secondary_factor"):
            stats["matched"] += 1
        elif atom.get("secondary_factor_label"):
            stats["unmatched"].append(atom["secondary_factor_label"])
        atoms.append(atom)

    return {
        "metadata": {"source_file": os.path.basename(filepath), "meeting_date": mdate,
                     "batch": batch, "source_doc_id": doc_id,
                     "migration_date": str(date.today()), "total_atoms": len(atoms),
                     "format": "v2" if is_v2 else "v1"},
        "claim_atoms": atoms, "stats": stats,
    }


# ── 执行 ────────────────────────────────────────────────────────────────────
batch_files = sorted(glob.glob(os.path.join(WORK_DIR, "*_speech_units.json")))
print(f"Found {len(batch_files)} batch files\n")

all_atoms = []
all_stats = {"total_files": 0, "total_atoms": 0, "matched": 0, "unmatched_labels": {}}

os.makedirs(OUTPUT_DIR, exist_ok=True)
os.makedirs(SKILL_ASSETS_DIR, exist_ok=True)

for fpath in batch_files:
    result = convert_batch(fpath)
    if "error" in result:
        print(f"[SKIP] {result['file']}: {result['error']}")
        continue

    atoms = result["claim_atoms"]
    st = result["stats"]
    all_atoms.extend(atoms)
    all_stats["total_files"] += 1
    all_stats["total_atoms"] += len(atoms)
    all_stats["matched"] += st["matched"]
    for lbl in st["unmatched"]:
        all_stats["unmatched_labels"][lbl] = all_stats["unmatched_labels"].get(lbl, 0) + 1

    out_name = os.path.basename(fpath).replace("_speech_units.json", "_claim_atoms.json")
    with open(os.path.join(OUTPUT_DIR, out_name), "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    pct = st["matched"] / max(len(atoms), 1) * 100
    print(f"[OK] {result['metadata']['source_file']}: {len(atoms)} atoms "
          f"({st['format']}), match {st['matched']}/{len(atoms)} ({pct:.0f}%)")

summary = {
    "version": "1.0.0", "migration_date": str(date.today()),
    "source_batch_count": all_stats["total_files"],
    "total_claim_atoms": len(all_atoms),
    "secondary_factor_match_rate": round(all_stats["matched"] / max(len(all_atoms), 1) * 100, 1),
    "unmatched_secondary_factors": all_stats["unmatched_labels"],
    "claim_atoms": all_atoms,
}

for p in [os.path.join(OUTPUT_DIR, "all_claim_atoms.json"), os.path.join(SKILL_ASSETS_DIR, "all_claim_atoms.json")]:
    with open(p, "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)

print(f"\n{'='*60}")
print(f"Total: {all_stats['total_files']} files -> {len(all_atoms)} claim atoms")
print(f"Match rate: {all_stats['matched']}/{len(all_atoms)} "
      f"({all_stats['matched']/max(len(all_atoms),1)*100:.1f}%)")
if all_stats["unmatched_labels"]:
    print(f"\nUnmatched ({len(all_stats['unmatched_labels'])}):")
    for lbl, cnt in sorted(all_stats["unmatched_labels"].items(), key=lambda x: -x[1]):
        print(f"  {lbl}: {cnt}x")
