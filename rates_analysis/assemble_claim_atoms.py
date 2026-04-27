#!/usr/bin/env python3
"""
annotations_*.txt → claim_atoms/*.json 组装脚本
将 LLM 标注的纯文本观点清单转换为标准 claim_atoms JSON 格式。
零积分，纯脚本。
"""
import json
import os
import re
from datetime import datetime

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
SEGMENTS_DIR = os.path.join(BASE_DIR, "meeting_segments")
CLAIM_ATOMS_DIR = os.path.join(BASE_DIR, "claim_atoms")
ALL_ATOMS_PATH = os.path.join(BASE_DIR, "all_claim_atoms.json")

# source_doc_id 映射
DOC_MAP = {
    "2026-04-03": "20260403_B01",
    "2026-04-10": "20260410_B01",
    "2026-04-17": "20260417_B01",
}

# 一级因子 → 简称映射（用于兼容旧数据）
PRIMARY_FACTOR_SHORT = {
    "基本面因子": "基本面",
    "政策面因子": "政策面",
    "流动性因子": "流动性",
    "市场情绪因子": "市场情绪",
    "机构行为因子": "机构行为",
}


def parse_annotation_file(filepath, date_str):
    """解析单个 annotations txt 文件，返回 claim_atoms 列表。"""
    source_doc_id = DOC_MAP.get(date_str, f"{date_str.replace('-', '')}_B01")
    atoms = []
    global_idx = 0

    with open(filepath, "r", encoding="utf-8") as f:
        lines = f.readlines()

    for line in lines:
        line = line.strip()
        # 跳过空行、注释行、表头、分隔线
        if not line or line.startswith("#") or line.startswith("====") or line.startswith("SEGMENT_ID"):
            continue
        # 跳过元数据行（source_doc_id, 标注日期等）
        if line.startswith("source_doc_id") or line.startswith("标注"):
            continue

        # 按 | 分割
        parts = line.split("|")
        if len(parts) < 13:
            continue

        try:
            segment_id = parts[0].strip()
            seq = parts[1].strip()
            speaker = parts[2].strip()
            claim_type = parts[3].strip()
            primary_factor = parts[4].strip()
            secondary_factor_id = parts[5].strip()
            secondary_factor_label = parts[6].strip()
            direction = parts[7].strip()
            magnitude = parts[8].strip()
            time_horizon = parts[9].strip()
            confidence = float(parts[10].strip())
            summary = parts[11].strip()
            raw_text = parts[12].strip() if len(parts) > 12 else ""

            global_idx += 1
            atom_id = f"{source_doc_id}_{global_idx:03d}"

            # 解析日期
            meeting_date = date_str  # e.g. "2026-04-03"

            atom = {
                "atom_id": atom_id,
                "source_doc_id": source_doc_id,
                "speaker": speaker,
                "speaker_institution": "",
                "speaker_role": "",
                "date": meeting_date,
                "raw_text": raw_text,
                "summary_text": summary,
                "primary_factor": primary_factor,
                "secondary_factor": secondary_factor_id,
                "secondary_factor_label": secondary_factor_label,
                "tertiary_factor": [],
                "claim_type": claim_type,
                "direction": direction,
                "magnitude": magnitude,
                "time_horizon": time_horizon,
                "confidence_score": confidence,
                "causal_chain_text": None,
                "causal_edge_ids": [],
                "trade_translation": None,
                "validation_metrics": [],
                "invalidation_condition": None,
                "related_atom_ids": [],
                "tags": [f"segment:{segment_id}"],
                "review_status": "待审核",
                "review_notes": "Phase A+ v1",
                "created_at": datetime.now().isoformat(),
                "updated_at": datetime.now().isoformat(),
            }
            atoms.append(atom)
        except (ValueError, IndexError) as e:
            print(f"  [WARN] 跳过解析失败行: {e}")
            continue

    return atoms, source_doc_id


def save_claim_atoms_file(atoms, source_doc_id, date_str, output_dir):
    """保存单份纪要的 claim_atoms JSON。"""
    # 统计
    total = len(atoms)
    claim_types = {}
    primary_factors = {}
    directions = {}
    for a in atoms:
        ct = a["claim_type"]
        pf = a["primary_factor"]
        d = a["direction"]
        claim_types[ct] = claim_types.get(ct, 0) + 1
        primary_factors[pf] = primary_factors.get(pf, 0) + 1
        directions[d] = directions.get(d, 0) + 1

    speakers = {}
    for a in atoms:
        s = a["speaker"]
        speakers[s] = speakers.get(s, 0) + 1

    data = {
        "metadata": {
            "source_file": f"annotations_{date_str}.txt",
            "meeting_date": date_str,
            "source_doc_id": source_doc_id,
            "migration_date": datetime.now().strftime("%Y-%m-%d"),
            "total_atoms": total,
            "format": "v1",
        },
        "claim_atoms": atoms,
        "stats": {
            "total": total,
            "matched": total,
            "unmatched": [],
            "skipped": 0,
            "format": "v1",
        },
    }

    os.makedirs(output_dir, exist_ok=True)
    filename = f"{date_str.replace('-', '')}_{source_doc_id}_claim_atoms.json"
    filepath = os.path.join(output_dir, filename)
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    print(f"\n{filename}: {total} 条观点")
    print(f"  claim_type: {json.dumps(claim_types, ensure_ascii=False)}")
    print(f"  一级因子: {json.dumps(primary_factors, ensure_ascii=False)}")
    print(f"  方向: {json.dumps(directions, ensure_ascii=False)}")
    print(f"  发言人: {len(speakers)} 人")

    return filepath


def merge_all_claim_atoms(output_path):
    """合并所有 claim_atoms JSON 到 all_claim_atoms.json。"""
    all_atoms = []
    atom_id_set = set()

    for fname in sorted(os.listdir(CLAIM_ATOMS_DIR)):
        if not fname.endswith("_claim_atoms.json"):
            continue
        fpath = os.path.join(CLAIM_ATOMS_DIR, fname)
        with open(fpath, "r", encoding="utf-8") as f:
            data = json.load(f)
        for atom in data.get("claim_atoms", []):
            if atom["atom_id"] not in atom_id_set:
                all_atoms.append(atom)
                atom_id_set.add(atom["atom_id"])

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(all_atoms, f, ensure_ascii=False, indent=2)

    print(f"\n合并完成: {len(all_atoms)} 条观点 → {output_path}")
    return all_atoms


def main():
    os.makedirs(CLAIM_ATOMS_DIR, exist_ok=True)

    dates = ["2026-04-03", "2026-04-10", "2026-04-17"]
    total_atoms = 0

    for date_str in dates:
        ann_file = os.path.join(SEGMENTS_DIR, f"annotations_{date_str}.txt")
        if not os.path.exists(ann_file):
            print(f"[SKIP] {ann_file} 不存在")
            continue

        print(f"\n{'='*60}")
        print(f"处理: {date_str}")
        print(f"{'='*60}")

        atoms, source_doc_id = parse_annotation_file(ann_file, date_str)
        print(f"  解析: {len(atoms)} 条观点")

        if atoms:
            save_claim_atoms_file(atoms, source_doc_id, date_str, CLAIM_ATOMS_DIR)
            total_atoms += len(atoms)

    if total_atoms > 0:
        print(f"\n{'='*60}")
        print(f"合并全量数据...")
        print(f"{'='*60}")
        all_atoms = merge_all_claim_atoms(ALL_ATOMS_PATH)
        print(f"\n总计: {total_atoms} 条新观点 + 已有存量 = {len(all_atoms)} 条全量观点")
    else:
        print("\n没有新观点需要合并。")


if __name__ == "__main__":
    main()
