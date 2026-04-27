import json

with open('factor_cooccurrence.json', 'r', encoding='utf-8') as f:
    data = json.load(f)

pairs = data['cooccurrence_matrix']['pairs']
pairs_sorted = sorted(pairs, key=lambda x: x['count'], reverse=True)

print("=== TOP50 高频共现因子对 ===")
for i, p in enumerate(pairs_sorted[:50]):
    f1 = p['factor1']
    f2 = p['factor2']
    pf1 = p['factor1_primary']
    pf2 = p['factor2_primary']
    cnt = p['count']
    cross = ' [CROSS]' if pf1 != pf2 else ''
    print(f'{i+1:2d}. {f1}({pf1}) <-> {f2}({pf2}): {cnt}{cross}')

# Also get cross-factor pairs (most interesting for causal chain)
print("\n=== TOP30 跨一级因子共现对 (CROSS) ===")
cross_pairs = [p for p in pairs if p['factor1_primary'] != p['factor2_primary']]
cross_sorted = sorted(cross_pairs, key=lambda x: x['count'], reverse=True)
for i, p in enumerate(cross_sorted[:30]):
    f1 = p['factor1']
    f2 = p['factor2']
    pf1 = p['factor1_primary']
    pf2 = p['factor2_primary']
    cnt = p['count']
    print(f'{i+1:2d}. {f1}({pf1}) -> {f2}({pf2}): {cnt}')

# Count factors by frequency threshold
print("\n=== 因子频次分布 ===")
inventory = data['secondary_factor_inventory']
buckets = {'>=10': 0, '5-9': 0, '3-4': 0, '2': 0, '1': 0}
for f in inventory:
    c = f['total_mentions']
    if c >= 10:
        buckets['>=10'] += 1
    elif c >= 5:
        buckets['5-9'] += 1
    elif c >= 3:
        buckets['3-4'] += 1
    elif c >= 2:
        buckets['2'] += 1
    else:
        buckets['1'] += 1
for k, v in buckets.items():
    print(f'  出现{k}次: {v}个因子')

# List factors with >=3 mentions (meaningful factors)
print("\n=== 出现>=3次的二级因子清单 ===")
meaningful = [f for f in inventory if f['total_mentions'] >= 3]
meaningful_sorted = sorted(meaningful, key=lambda x: x['total_mentions'], reverse=True)
for f in meaningful_sorted:
    print(f'  [{f["total_mentions"]:2d}次, {f["meeting_count"]}场] {f["name"]} ({f["primary_factor"]})')
