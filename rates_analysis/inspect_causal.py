import json
from collections import Counter

# 1. 读取因子本体库
with open('factor_ontology.json', 'r', encoding='utf-8') as f:
    ontology = json.load(f)

factors = {}
for item in ontology.get('factors', []):
    factors[item['id']] = item['label']
print(f'因子本体库节点数: {len(factors)}')

# 2. 读取现有因果图谱
with open('factor_causal_edges_v2.json', 'r', encoding='utf-8') as f:
    edges_data = json.load(f)
edges = edges_data.get('edges', [])
print(f'现有因果边数: {len(edges)}')
existing_ids = {e['edge_id'] for e in edges}

# 3. 读取 claim_atoms
with open('claim_atoms/all_claim_atoms.json', 'r', encoding='utf-8') as f:
    atoms_data = json.load(f)
atoms = atoms_data.get('claim_atoms', [])
print(f'claim_atoms 总数: {len(atoms)}')

type_counts = Counter(a.get('claim_type', '') for a in atoms)
print('\nclaim_type 分布:')
for ct, cnt in type_counts.most_common():
    print(f'  {ct}: {cnt}')

# 4. 因果链条类型观点
causal_atoms = [a for a in atoms if a.get('claim_type') == '因果链条']
print(f'\n因果链条类型观点数: {len(causal_atoms)}')

# 5. 检查 source/target 字段
has_both = [a for a in causal_atoms if a.get('source_factor_id') and a.get('target_factor_id')]
has_source_only = [a for a in causal_atoms if a.get('source_factor_id') and not a.get('target_factor_id')]
has_none = [a for a in causal_atoms if not a.get('source_factor_id')]
print(f'  有 source+target: {len(has_both)}')
print(f'  只有 source: {len(has_source_only)}')
print(f'  无 source: {len(has_none)}')

# 打印几条带双 factor 的示例
print('\n示例（带 source+target 的前5条）:')
for a in has_both[:5]:
    print(f'  [{a["atom_id"]}] {a.get("source_factor_id")}({a.get("source_factor_label","")}) -> {a.get("target_factor_id")}({a.get("target_factor_label","")})')
    print(f'  content: {a.get("content","")[:100]}')
    print()

# 6. 检查所有 atoms 的字段（不限 claim_type）
# 找 source_factor_id 和 target_factor_id 都有的
all_with_both = [a for a in atoms if a.get('source_factor_id') and a.get('target_factor_id')]
print(f'\n所有观点中同时有 source+target 的数量: {len(all_with_both)}')
print('这些观点的 claim_type 分布:')
both_types = Counter(a.get('claim_type','') for a in all_with_both)
for ct, cnt in both_types.most_common():
    print(f'  {ct}: {cnt}')

# 打印第一条观点的完整字段，了解结构
print('\n第一条 atom 的完整字段:')
if atoms:
    print(json.dumps(atoms[0], ensure_ascii=False, indent=2))
