"""verify_migration.py"""
import json, glob

d = json.load(open('claim_atoms/all_claim_atoms.json', encoding='utf-8'))
print("Total atoms:", d['total_claim_atoms'])
print("Match rate:", d['secondary_factor_match_rate'], '%')
print("Unmatched:", len(d['unmatched_secondary_factors']), 'labels')

# v1 vs v2
v1f = glob.glob('claim_atoms/*_claim_atoms.json')
v1 = v2 = 0
for f in v1f:
    r = json.load(open(f, encoding='utf-8'))
    fmt = r.get('metadata', {}).get('format', 'unknown')
    if fmt == 'v2':
        v2 += 1
    else:
        v1 += 1
print(f"v1 batches: {v1}, v2 batches: {v2}")

# sample v2 atom with causal chain
for atom in d['claim_atoms']:
    if atom.get('causal_chain_text'):
        print("\nSample v2 atom:")
        for k in ['atom_id', 'claim_type', 'secondary_factor', 'secondary_factor_label']:
            print(f"  {k}: {atom[k]}")
        print(f"  causal_chain: {atom['causal_chain_text'][:100]}")
        print(f"  validation_metrics: {len(atom.get('validation_metrics', []))}")
        print(f"  time_horizon: {atom.get('time_horizon')}")
        print(f"  confidence: {atom.get('confidence_score')}")
        break

# unmatched summary
print("\nRemaining unmatched (>1x):")
for lbl, cnt in sorted(d['unmatched_secondary_factors'].items(), key=lambda x: -x[1]):
    if cnt > 1:
        print(f"  {lbl}: {cnt}x")
