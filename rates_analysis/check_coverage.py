#!/usr/bin/env python3
"""统计存量纪要与已处理纪要的差距"""
import json, os, re

batches_dir = r'C:\Users\123cy\WorkBuddy\20260407152918\minutes_batches'
all_meetings = {}

for bf in ['batch1_2025Q1.json','batch2_2025Q2.json','batch3_2025Q3.json','batch4_2025Q4.json','batch5_2025Q4to2026Q1.json']:
    fp = os.path.join(batches_dir, bf)
    with open(fp, 'r', encoding='utf-8') as f:
        data = json.load(f)
    for item in data:
        fn = item.get('filename','')
        text = item.get('text','')
        m = re.search(r'(\d{4})\.(\d{2})\.(\d{2})', text[:50])
        date = f'{m.group(1)}-{m.group(2)}-{m.group(3)}' if m else 'unknown'
        m2 = re.search(r'(\d{4})(\d{2})(\d{2})', fn)
        doc_id = f'{m2.group(1)}{m2.group(2)}{m2.group(3)}_B01' if m2 else fn[:30]
        all_meetings[doc_id] = {'date': date, 'filename': fn, 'batch': bf, 'char_count': item.get('char_count',0)}

print(f'=== 存量纪要总数: {len(all_meetings)} ===')

atoms_dir = r'c:\Users\123cy\WorkBuddy\20260408090957\rates_analysis\claim_atoms'
processed = set()
for af in os.listdir(atoms_dir):
    if af.endswith('_claim_atoms.json') and af != 'all_claim_atoms.json':
        parts = af.replace('_claim_atoms.json','').split('_',1)
        if len(parts) == 2:
            processed.add(parts[1])

print(f'=== 已处理: {len(processed)} ===')
for p in sorted(processed):
    m = all_meetings.get(p, {})
    print(f'  {p} | {m.get("date","?")} | {m.get("char_count",0)}字')

unprocessed = {k:v for k,v in all_meetings.items() if k not in processed}
print(f'\n=== 未处理: {len(unprocessed)} ===')
total_chars = 0
for doc_id in sorted(unprocessed.keys()):
    m = unprocessed[doc_id]
    total_chars += m['char_count']
    print(f'  {doc_id} | {m["date"]} | {m["batch"]} | {m["char_count"]}字')

print(f'\n未处理总字数: {total_chars:,}')
