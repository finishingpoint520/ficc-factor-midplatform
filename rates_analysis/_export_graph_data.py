"""
导出为前端可用的交互式数据格式
"""
import json
import sys
from pathlib import Path
from collections import Counter

BASE = Path(__file__).parent

# 读取
with open(BASE / "factor_causal_edges_v2.json", "r", encoding="utf-8") as f:
    causal = json.load(f)
with open(BASE / "factor_ontology.json", "r", encoding="utf-8") as f:
    onto = json.load(f)
with open(BASE / "factor_cooccurrence.json", "r", encoding="utf-8") as f:
    cooc = json.load(f)

# 构建节点标签→ID映射
label_to_id = {n["factor_label"]: n["factor_id"] for n in onto["nodes"]}
id_to_label = {n["factor_id"]: n["factor_label"] for n in onto["nodes"]}

# 节点基本信息
nodes_info = {}
for n in onto["nodes"]:
    nodes_info[n["factor_id"]] = {
        "label": n["factor_label"],
        "primary": n["primary_factor"],
        "appearance_count": n.get("appearance_count", 0),
        "meeting_count": n.get("meeting_count", 0),
    }

# 补全共现统计中的节点频次
factor_counts = {item["factor"]: item["count"] for item in cooc.get("factor_counts", [])}
for fid, info in nodes_info.items():
    label = info["label"]
    if label in factor_counts:
        info["cooccurrence_count"] = factor_counts[label]
    else:
        info["cooccurrence_count"] = 0

# 转换边
edges_out = []
for e in causal["edges"]:
    src_id = e["source_factor_id"]
    tgt_id = e["target_factor_id"]
    # 获取一级因子
    src_primary = nodes_info.get(src_id, {}).get("primary", "未知")
    tgt_primary = nodes_info.get(tgt_id, {}).get("primary", "未知")
    cross = (src_primary != tgt_primary)
    
    sc = e.get("strength_score", 0.5)
    if sc >= 0.7:
        strength = "strong"
    elif sc >= 0.4:
        strength = "medium"
    else:
        strength = "weak"
    
    edges_out.append({
        "edge_id": e["edge_id"],
        "source": src_id,
        "source_label": e["source_factor_label"],
        "target": tgt_id,
        "target_label": e["target_factor_label"],
        "source_primary": src_primary,
        "target_primary": tgt_primary,
        "strength": strength,
        "strength_score": sc,
        "cross": cross,
        "sign": e.get("sign", "?"),
        "lag": e.get("lag", "?"),
        "support_count": e.get("internal_support_count", 0),
        "review_status": e.get("review_status", "待审核"),
        "confidence": e.get("confidence", "低"),
        "mechanism": e.get("mechanism", ""),
        "conditions": e.get("conditions", ""),
    })

# 导出
output = {
    "metadata": {
        "generated_at": "2026-04-26",
        "total_nodes": len(nodes_info),
        "total_edges": len(edges_out),
    },
    "nodes": nodes_info,
    "edges": edges_out,
}

with open(BASE / "_interactive_data.json", "w", encoding="utf-8") as f:
    json.dump(output, f, ensure_ascii=False, indent=2)

print(f"Exported {len(nodes_info)} nodes, {len(edges_out)} edges to _interactive_data.json")
