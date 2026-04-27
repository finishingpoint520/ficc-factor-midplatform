"""
upgrade_causal_edges_v2.py
因果图谱 v1 → v2 升级脚本（B1+B3 合并，零积分）

步骤：
1. 加载 ontology，建立 label→factor_id 映射
2. 加载 v1 的 96 条边
3. 为每条边计算：
   - edge_id, source_factor_id, source_factor_label, target_factor_id, target_factor_label
   - strength_score（strong→0.8, medium→0.5, weak→0.2）
   - edge_type（同一级因子→hierarchical，跨因子→cross_factor）
4. 加载 claim_atoms，为每条边统计 internal_support_count + supporting_atom_ids
5. 输出 factor_causal_edges_v2.json（不含 sign/lag/conditions/mechanism，这些由 B2 大模型补填）
"""
import json
import re
from datetime import datetime, date
from pathlib import Path
from collections import Counter

BASE = Path(__file__).parent
ONTOLOGY_FILE = BASE / "factor_ontology.json"
V1_EDGES_FILE = BASE / "factor_causal_edges.json"
ATOMS_FILE = BASE / "claim_atoms" / "all_claim_atoms.json"
V2_EDGES_FILE = BASE / "factor_causal_edges_v2.json"

# 一级因子简称 → 代码映射
PRIMARY_CODE = {
    "基本面": "FD",
    "基本面因子": "FD",
    "政策面": "PL",
    "政策面因子": "PL",
    "流动性": "LQ",
    "流动性因子": "LQ",
    "市场情绪": "MS",
    "市场情绪因子": "MS",
    "机构行为": "IB",
    "机构行为因子": "IB",
}

# strength 映射
STRENGTH_MAP = {
    "strong": 0.8,
    "medium": 0.5,
    "weak": 0.2,
}

# 未匹配节点的占位 ID（后续需补充到 ontology）
PLACEHOLDER_NODES = {
    "市场观察": "MS_014",   # 属于市场情绪因子
    "风险管理": "IB_013",   # 属于机构行为因子
}


def load_ontology():
    with open(ONTOLOGY_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def load_v1_edges():
    with open(V1_EDGES_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def load_claim_atoms():
    with open(ATOMS_FILE, "r", encoding="utf-8") as f:
        return json.load(f)["claim_atoms"]


def build_label_to_id_map(ontology):
    """建立 label/alias → factor_id 映射"""
    mapping = {}
    for node in ontology["nodes"]:
        mapping[node["factor_label"]] = node["factor_id"]
        for alias in node.get("aliases", []):
            if alias not in mapping:
                mapping[alias] = node["factor_id"]
    # 加入占位节点
    for label, fid in PLACEHOLDER_NODES.items():
        mapping[label] = fid
    return mapping


def build_id_to_label_map(ontology):
    """建立 factor_id → label 映射"""
    mapping = {}
    for node in ontology["nodes"]:
        mapping[node["factor_id"]] = node["factor_label"]
    # 加入占位节点
    for label, fid in PLACEHOLDER_NODES.items():
        mapping[fid] = label
    return mapping


def resolve_factor_id(name, label_to_id):
    """将中文因子名解析为 factor_id"""
    if name in label_to_id:
        return label_to_id[name]
    # 模糊匹配：检查是否是子串关系
    for label, fid in label_to_id.items():
        if name in label or label in name:
            return fid
    return None


def determine_edge_type(from_primary, to_primary):
    """判断边类型"""
    from_code = PRIMARY_CODE.get(from_primary)
    to_code = PRIMARY_CODE.get(to_primary)
    if from_code == to_code:
        return "hierarchical"
    return "cross_factor"


def enrich_edges_with_atoms(edges_v2, claim_atoms, label_to_id):
    """从 claim_atoms 统计每条边的支持数和关联 atom IDs

    匹配逻辑：
    - 如果一条 atom 的 raw_text/summary_text 中同时包含 source_label 和 target_label
      （或其同义词），则认为该 atom 支持这条因果边
    - 额外：如果 atom 的 causal_chain_text 中包含类似的传导路径
    """
    # 预处理 atoms 的文本索引
    atom_texts = []
    for atom in claim_atoms:
        raw = (atom.get("raw_text") or "").strip()
        summary = (atom.get("summary_text") or "").strip()
        chain = (atom.get("causal_chain_text") or "").strip()
        combined = f"{raw} {summary} {chain}"
        atom_texts.append({
            "atom_id": atom["atom_id"],
            "text": combined,
            "date": atom.get("date", ""),
        })

    today_str = date.today().isoformat()
    ninety_days_ago = date.fromisoformat(today_str)
    from datetime import timedelta
    ninety_days_ago = ninety_days_ago - timedelta(days=90)
    ninety_days_ago_str = ninety_days_ago.isoformat()

    for edge in edges_v2:
        src_label = edge["source_factor_label"]
        tgt_label = edge["target_factor_label"]

        supporting = []
        for at in atom_texts:
            text = at["text"]
            # 检查文本中是否同时出现源因子和目标因子
            src_found = src_label in text
            tgt_found = tgt_label in text

            # 额外检查：同义词
            if not src_found:
                for label, fid in label_to_id.items():
                    if fid == edge["source_factor_id"] and label in text:
                        src_found = True
                        break
            if not tgt_found:
                for label, fid in label_to_id.items():
                    if fid == edge["target_factor_id"] and label in text:
                        tgt_found = True
                        break

            if src_found and tgt_found:
                supporting.append(at)

        # 统计
        edge["internal_support_count"] = len(supporting)
        # 按日期倒序，取最近 20 条
        supporting.sort(key=lambda x: x["date"], reverse=True)
        edge["supporting_atom_ids"] = [s["atom_id"] for s in supporting[:20]]

        # 计算近期强度变化（最近 90 天 vs 更早的支持数对比）
        recent = sum(1 for s in supporting if s["date"] >= ninety_days_ago_str)
        earlier = len(supporting) - recent
        if earlier > 0:
            edge["recent_strength_delta"] = round((recent - earlier) / earlier, 2)
        elif recent > 0:
            edge["recent_strength_delta"] = 0.1  # 新出现的边
        else:
            edge["recent_strength_delta"] = 0.0

        edge["conflicting_atom_ids"] = []  # TODO: 冲突检测需要更复杂的逻辑

    return edges_v2


def main():
    print("=== 因果图谱 v2 升级 (B1+B3) ===\n")

    # 1. 加载数据
    print("[1/4] 加载数据...")
    ontology = load_ontology()
    v1_data = load_v1_edges()
    claim_atoms = load_claim_atoms()

    label_to_id = build_label_to_id_map(ontology)
    id_to_label = build_id_to_label_map(ontology)

    print(f"  本体库: {ontology['total_nodes']} 节点")
    print(f"  v1 因果边: {len(v1_data['edges'])} 条")
    print(f"  claim_atoms: {len(claim_atoms)} 条")

    # 2. 转换边结构
    print("\n[2/4] 转换边结构 (B1)...")
    edges_v2 = []
    unmatched_nodes = []
    stats = Counter()

    for i, old_edge in enumerate(v1_data["edges"]):
        from_name = old_edge["from"]
        to_name = old_edge["to"]
        from_primary = old_edge["from_primary"]
        to_primary = old_edge["to_primary"]
        strength = old_edge["strength"]
        logic = old_edge.get("logic", "")

        # 解析 factor_id
        src_id = resolve_factor_id(from_name, label_to_id)
        tgt_id = resolve_factor_id(to_name, label_to_id)

        if src_id is None:
            unmatched_nodes.append(("from", from_name, i))
            src_id = f"UNK_{i:03d}"
        if tgt_id is None:
            unmatched_nodes.append(("to", to_name, i))
            tgt_id = f"UNK_{i:03d}"

        # 获取 label（从 id 反查，确保标准化）
        src_label = id_to_label.get(src_id, from_name)
        tgt_label = id_to_label.get(tgt_id, to_name)

        edge_type = determine_edge_type(from_primary, to_primary)
        stats[edge_type] += 1

        new_edge = {
            "edge_id": f"{src_id}\u2192{tgt_id}",
            "source_factor_id": src_id,
            "source_factor_label": src_label,
            "target_factor_id": tgt_id,
            "target_factor_label": tgt_label,
            "sign": "?",  # B2 填
            "strength_score": STRENGTH_MAP.get(strength, 0.5),
            "lag": "",  # B2 填
            "conditions": "",  # B2 填
            "mechanism": logic if logic else "",  # 已有 logic 字段，先填入
            "edge_type": edge_type,
            "internal_support_count": 0,  # B3 填
            "recent_strength_delta": 0.0,  # B3 填
            "supporting_atom_ids": [],  # B3 填
            "conflicting_atom_ids": [],
            "period_validity": ["普遍成立"],
            "confidence": "中",  # 默认中，B2 后可根据支持数调整
            "review_status": "待审核",
            "created_at": "2026-04-21",
            "updated_at": "2026-04-21",
        }
        edges_v2.append(new_edge)

    print(f"  hierarchical: {stats['hierarchical']}, cross_factor: {stats['cross_factor']}")

    if unmatched_nodes:
        print(f"\n  [WARNING] {len(unmatched_nodes)} 个节点未匹配:")
        for direction, name, idx in unmatched_nodes:
            print(f"    {direction}='{name}' (edge #{idx})")

    # 3. 从 claim_atoms enrich
    print("\n[3/4] 从 claim_atoms 统计支持数 (B3)...")
    edges_v2 = enrich_edges_with_atoms(edges_v2, claim_atoms, label_to_id)

    # 统计支持数分布
    support_dist = Counter(e["internal_support_count"] for e in edges_v2)
    print(f"  支持数分布: {dict(sorted(support_dist.items()))}")
    supported = sum(1 for e in edges_v2 if e["internal_support_count"] > 0)
    print(f"  有 claim_atoms 支持的边: {supported}/{len(edges_v2)}")

    # 4. 输出
    print("\n[4/4] 输出 v2 文件...")
    v2_data = {
        "metadata": {
            "description": "五因子框架 - 因果链定义 v2（中国债券市场利率策略）",
            "version": "2.0.0-draft",
            "date": "2026-04-21",
            "note": "B1+B3 完成：ID关联、strength_score、edge_type、claim_atoms 支持统计。sign/lag/conditions/mechanism 待 B2 大模型补填。",
            "total_edges": len(edges_v2),
            "source_file": "factor_causal_edges.json (v1, 96 edges)",
            "ontology_file": "factor_ontology.json (51 nodes)",
            "atoms_file": "all_claim_atoms.json (455 atoms)",
            "unmatched_nodes": list(set(n[1] for n in unmatched_nodes)),
        },
        "edges": edges_v2,
    }

    with open(V2_EDGES_FILE, "w", encoding="utf-8") as f:
        json.dump(v2_data, f, ensure_ascii=False, indent=2)

    print(f"  已写入: {V2_EDGES_FILE}")

    # 预览前 3 条
    print("\n=== 预览前 3 条 v2 边 ===")
    for e in edges_v2[:3]:
        print(json.dumps(e, ensure_ascii=False, indent=2))
        print()

    # 准备 B2 所需的输入清单
    print("=== B2 待大模型补填的字段 ===")
    print(f"  sign: 96 条 (全部为 '?')")
    print(f"  lag: 96 条 (全部为空)")
    print(f"  conditions: 96 条 (全部为空)")
    print(f"  mechanism: 已有 logic 字段预填 {sum(1 for e in edges_v2 if e.get('mechanism'))} 条，其余待补填/扩充")

    # 输出 B2 输入清单文件
    b2_input_file = BASE / "b2_enrichment_input.json"
    b2_input = []
    for e in edges_v2:
        b2_input.append({
            "edge_id": e["edge_id"],
            "source_factor_label": e["source_factor_label"],
            "target_factor_label": e["target_factor_label"],
            "source_primary": e["source_factor_id"][:2],
            "target_primary": e["target_factor_id"][:2],
            "old_logic": e.get("mechanism", ""),
            "strength_score": e["strength_score"],
            "edge_type": e["edge_type"],
        })
    with open(b2_input_file, "w", encoding="utf-8") as f:
        json.dump(b2_input, f, ensure_ascii=False, indent=2)
    print(f"  B2 输入清单已写入: {b2_input_file}")


if __name__ == "__main__":
    main()
