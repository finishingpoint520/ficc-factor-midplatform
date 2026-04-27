"""数据概览快照"""
import json
from collections import Counter

with open('factor_causal_edges_v2.json','r',encoding='utf-8') as f:
    causal = json.load(f)
with open('factor_ontology.json','r',encoding='utf-8') as f:
    onto = json.load(f)
with open('factor_cooccurrence.json','r',encoding='utf-8') as f:
    cooc = json.load(f)

out = []
out.append(f"总边数: {causal['metadata']['total_edges']}")
out.append(f"本体节点数: {onto['total_nodes']}")
out.append(f"观点原子数: 744")

out.append("\n--- 一级因子节点分布 ---")
primary_counts = Counter()
for n in onto['nodes']:
    primary_counts[n['primary_factor']] += 1
for p, c in primary_counts.most_common():
    out.append(f"  {p}: {c}个节点")

out.append("\n--- 节点标签映射 ---")
for n in onto['nodes']:
    out.append(f"  {n['factor_id']}: {n['factor_label']}")

out.append("\n--- Top 10 最高支撑边 ---")
sorted_edges = sorted(causal['edges'], key=lambda e: e.get('internal_support_count',0), reverse=True)
for e in sorted_edges[:15]:
    out.append(f"  {e['edge_id']}: support={e['internal_support_count']} score={e['strength_score']} sign={e['sign']} lag={e.get('lag','?')} status={e.get('review_status','?')}")

out.append("\n--- Top 10 高频因子 ---")
for item in cooc.get('factor_counts', [])[:15]:
    out.append(f"  {item['factor']}: {item['count']}次")

with open('_stats_dump.txt','w',encoding='utf-8') as f:
    f.write('\n'.join(out))
print("Done")
