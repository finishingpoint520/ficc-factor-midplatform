"""
填充缺失的证据原子 - 仅更新现有边的 supporting_atom_ids
基于 enrich_causal_edges.py 的精确匹配逻辑，但跳过候选边提取
"""
import json
import re
from datetime import datetime
from collections import defaultdict
import shutil
import os

ATOMS_PATH = 'claim_atoms/all_claim_atoms.json'
EDGES_PATH = 'factor_causal_edges_v2.json'
ONTOLOGY_PATH = 'factor_ontology.json'
BACKUP_PATH = 'factor_causal_edges_v2.json.bak_pre_fill'

PRIMARY_FACTOR_MAP = {
    '基本面因子': 'FD',
    '政策面因子': 'PL',
    '流动性因子': 'LQ',
    '市场情绪因子': 'MS',
    '机构行为因子': 'IB',
}

def get_code(factor_id):
    return factor_id.split('_')[0] if factor_id else ''


def load_data():
    with open(ATOMS_PATH, 'r', encoding='utf-8') as f:
        atoms_data = json.load(f)
    atoms = atoms_data.get('claim_atoms', [])

    with open(EDGES_PATH, 'r', encoding='utf-8') as f:
        edges_data = json.load(f)

    with open(ONTOLOGY_PATH, 'r', encoding='utf-8') as f:
        ontology = json.load(f)
    nodes = {n['factor_id']: n for n in ontology.get('nodes', [])}
    return atoms, edges_data, nodes


def update_support_counts(atoms, edges_data):
    """
    精确匹配：
    support = atom.secondary_factor == edge.target_factor_id
              AND primary_factor code 与 edge.source_factor_id code 一致
    """
    support_types = {'方向判断', '因果链条', '验证指标', '条件触发判断'}
    conflict_types = {'反例/冲突观点'}

    # 索引：(src_code, tgt_factor_id) -> [atom_ids]
    support_index = defaultdict(list)
    conflict_index = defaultdict(list)

    for atom in atoms:
        sf = atom.get('secondary_factor', '')
        pf_label = atom.get('primary_factor', '')
        pf_code = PRIMARY_FACTOR_MAP.get(pf_label, '')
        ct = atom.get('claim_type', '')
        if sf and pf_code:
            key = (pf_code, sf)
            if ct in support_types:
                support_index[key].append(atom['atom_id'])
            elif ct in conflict_types:
                conflict_index[key].append(atom['atom_id'])

    updated_count = 0
    for edge in edges_data['edges']:
        src_id = edge.get('source_factor_id', '')
        tgt_id = edge.get('target_factor_id', '')
        src_code = get_code(src_id)
        tgt_code = get_code(tgt_id)

        # 精确匹配：source 的一级因子类别 + target 的精确 factor_id
        key = (src_code, tgt_id)
        new_support = support_index.get(key, [])
        new_conflict = conflict_index.get(key, [])

        old = edge.get('internal_support_count', 0)
        edge['internal_support_count'] = len(new_support)
        edge['supporting_atom_ids'] = new_support
        edge['conflicting_atom_ids'] = new_conflict
        edge['updated_at'] = datetime.now().strftime('%Y-%m-%d')

        if len(new_support) != old:
            updated_count += 1

    print(f'已更新 {updated_count} 条边的 support_count（精确双因子匹配）')
    return edges_data


def main():
    print('=== 填充缺失的证据原子（仅更新现有边）===')
    
    # 备份（已有备份则跳过）
    if not os.path.exists(BACKUP_PATH):
        shutil.copy2(EDGES_PATH, BACKUP_PATH)
        print(f'已备份: {BACKUP_PATH}')
    else:
        print(f'备份已存在，跳过: {BACKUP_PATH}')
    
    atoms, edges_data, nodes = load_data()
    original_edge_count = len(edges_data['edges'])
    print(f'原始总边数: {original_edge_count}')
    print(f'atoms 总数: {len(atoms)}')
    
    # 更新 support_count（精确匹配）
    print('\n--- 精确更新 support_count ---')
    edges_data = update_support_counts(atoms, edges_data)
    
    # 更新 metadata
    edges_data['metadata']['total_edges'] = len(edges_data['edges'])
    edges_data['metadata']['version'] = '2.1.1'
    edges_data['metadata']['date'] = datetime.now().strftime('%Y-%m-%d')
    edges_data['metadata']['note'] = (
        f'v2.1.1: 仅更新现有边的 supporting_atom_ids（双因子精确匹配），'
        f'未添加候选边；使用 {len(atoms)} 条 atoms 重算 support_count'
    )
    edges_data['metadata']['atoms_file'] = f'all_claim_atoms.json ({len(atoms)} atoms)'
    
    # 写回
    with open(EDGES_PATH, 'w', encoding='utf-8') as f:
        json.dump(edges_data, f, ensure_ascii=False, indent=2)
    print(f'\n已写入: {EDGES_PATH}')
    
    # 统计结果
    edges = edges_data['edges']
    empty_support = [e for e in edges if not e.get('supporting_atom_ids')]
    print(f'更新后总边数: {len(edges)}')
    print(f'有证据原子的边: {len(edges) - len(empty_support)}')
    print(f'无证据原子的边: {len(empty_support)}')
    
    # 输出前10条高支撑边
    confirmed_edges = [e for e in edges if e.get('review_status') != '候选-待人工审核']
    top = sorted(confirmed_edges, key=lambda x: x.get('internal_support_count', 0), reverse=True)[:10]
    print('\n=== Top 10 高支撑因果边（精确匹配）===')
    for e in top:
        print(f'  {e["edge_id"]}: {e.get("source_factor_label","")} → {e.get("target_factor_label","")} '
              f'support={e["internal_support_count"]} sign={e.get("sign","")}')


if __name__ == '__main__':
    main()