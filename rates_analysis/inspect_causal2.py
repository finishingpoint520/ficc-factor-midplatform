import json
from collections import Counter

# 读取因子本体库 - 检查实际结构
with open('factor_ontology.json', 'r', encoding='utf-8') as f:
    ontology = json.load(f)

print('factor_ontology.json 顶层 keys:', list(ontology.keys()))
# 找因子列表
if isinstance(ontology, list):
    print('顶层是 list, 第一条:', json.dumps(ontology[0], ensure_ascii=False)[:200])
elif isinstance(ontology, dict):
    for k, v in ontology.items():
        if isinstance(v, list):
            print(f'key={k} list_len={len(v)}, 第一条:', json.dumps(v[0], ensure_ascii=False)[:200] if v else '[]')
        else:
            print(f'key={k}: {str(v)[:100]}')

print('\n')

# 读取 claim_atoms
with open('claim_atoms/all_claim_atoms.json', 'r', encoding='utf-8') as f:
    atoms_data = json.load(f)
atoms = atoms_data.get('claim_atoms', [])

# 打印所有 因果链条 类型的观点
causal_atoms = [a for a in atoms if a.get('claim_type') == '因果链条']
print(f'因果链条观点 ({len(causal_atoms)} 条):')
print('-' * 80)
for i, a in enumerate(causal_atoms):
    print(f'[{i+1}] atom_id={a["atom_id"]} date={a.get("date","")}')
    print(f'    primary={a.get("primary_factor","")} secondary={a.get("secondary_factor","")} ({a.get("secondary_factor_label","")})')
    print(f'    tertiary={a.get("tertiary_factor",[])}')
    print(f'    raw_text: {a.get("raw_text","")[:150]}')
    print(f'    causal_chain_text: {a.get("causal_chain_text","")}')
    print()
