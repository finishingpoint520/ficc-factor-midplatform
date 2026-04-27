import json

with open('factor_causal_edges.json', 'r', encoding='utf-8') as f:
    data = json.load(f)

meta = data['metadata']
edges = data['edges']

print(f"=== 因果链定义文件验证 ===")
print(f"总边数: {len(edges)}")
print(f"版本: {meta['version']}, 日期: {meta['date']}")

# Count by strength
strengths = {}
for e in edges:
    s = e['strength']
    strengths[s] = strengths.get(s, 0) + 1
print(f"\n按强度分布:")
for s in ['strong', 'medium', 'weak']:
    print(f"  {s}: {strengths.get(s, 0)}")

# Count cross-factor edges
cross = 0
same = 0
for e in edges:
    if e['from_primary'] != e['to_primary']:
        cross += 1
    else:
        same += 1
print(f"\n跨一级因子边: {cross}")
print(f"同一级因子边: {same}")

# Nodes
nodes = set()
for e in edges:
    nodes.add(e['from'])
    nodes.add(e['to'])
print(f"\n涉及的节点数: {len(nodes)}")

# Nodes per primary
from collections import defaultdict
node_primary = {}
for e in edges:
    node_primary[e['from']] = e['from_primary']
    node_primary[e['to']] = e['to_primary']

primary_nodes = defaultdict(set)
for node, pf in node_primary.items():
    primary_nodes[pf].add(node)

print(f"\n各一级因子下的节点数:")
for pf in ['基本面', '政策面', '流动性', '市场情绪', '机构行为']:
    nodes_in_pf = primary_nodes[pf]
    print(f"  {pf}: {len(nodes_in_pf)} 个 - {', '.join(sorted(nodes_in_pf))}")

# Check for strong cross-factor edges
print(f"\n=== Strong 跨因子因果边 (核心传导路径) ===")
for e in edges:
    if e['strength'] == 'strong' and e['from_primary'] != e['to_primary']:
        print(f"  {e['from']}({e['from_primary']}) -> {e['to']}({e['to_primary']})")
