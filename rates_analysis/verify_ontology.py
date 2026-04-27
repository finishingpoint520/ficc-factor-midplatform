"""verify_ontology.py — 验证正式版因子本体库"""
import json
from collections import defaultdict

d = json.load(open('factor_ontology.json', encoding='utf-8'))
print("Version:", d['version'])
print("Total nodes:", d['total_nodes'])

# 1. ID 规范检查
bad_ids = []
for n in d['nodes']:
    fid = n['factor_id']
    ok = (len(fid) >= 5 and fid[:3].isalpha() and fid[3] == '_')
    if not ok:
        bad_ids.append(fid)
print("\nBad IDs:", len(bad_ids), bad_ids[:5] if bad_ids else 'None')

# 2. 别名检查
with_alias = [n['factor_name'] for n in d['nodes'] if n.get('aliases')]
print("Nodes with aliases:", len(with_alias), "/", d['total_nodes'])

# 3. 按分类打印
groups = defaultdict(list)
for n in d['nodes']:
    code = n['primary_factor_code']
    alias_str = " -> " + ",".join(n.get('aliases', [])) if n.get('aliases') else ""
    groups[code].append(n['factor_id'] + " " + n['factor_name'] + alias_str)

for code in ['FD', 'PL', 'LQ', 'MS', 'IB']:
    items = groups.get(code, [])
    print(f"\n{code} ({len(items)}):")
    for item in items:
        print(f"  {item}")

# 4. 政策预期归属验证
for n in d['nodes']:
    if '政策预期' in n['factor_name']:
        print(f"\n[VERIFY] {n['factor_name']}: code={n['primary_factor_code']}, id={n['factor_id']}")
