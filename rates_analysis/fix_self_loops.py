"""过滤自环边并更新 factor_causal_edges_v2.json"""
import json
from datetime import datetime

EDGES_PATH = 'factor_causal_edges_v2.json'

with open(EDGES_PATH, 'r', encoding='utf-8') as f:
    data = json.load(f)

before = len(data['edges'])
# 过滤掉 source == target 的边（自环）
data['edges'] = [e for e in data['edges'] if e.get('source_factor_id') != e.get('target_factor_id')]
after = len(data['edges'])
removed = before - after

data['metadata']['total_edges'] = after
data['metadata']['date'] = datetime.now().strftime('%Y-%m-%d')
if removed > 0:
    data['metadata']['note'] += f'；已移除 {removed} 条自环边'

with open(EDGES_PATH, 'w', encoding='utf-8') as f:
    json.dump(data, f, ensure_ascii=False, indent=2)

print(f'已移除 {removed} 条自环边，总边数：{after}')
# 打印 Top 10（排除候选边）
confirmed = [e for e in data['edges'] if e.get('review_status') != '候选-待人工审核']
top = sorted(confirmed, key=lambda x: x.get('internal_support_count', 0), reverse=True)[:10]
print('\nTop 10 高支撑因果边（确认边）：')
for e in top:
    print(f'  {e["edge_id"]:30s}  {e.get("source_factor_label",""):12s} → {e.get("target_factor_label",""):12s}  support={e["internal_support_count"]}  sign={e.get("sign","")}')
