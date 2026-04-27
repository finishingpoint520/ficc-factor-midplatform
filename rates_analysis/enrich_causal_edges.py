"""
因果图谱增量 enrichment 脚本 v2
================================
修复：support_count 精确匹配 source+target 双因子
- atom.secondary_factor == edge.target_factor_id
  AND atom.primary_factor 与 edge.source_factor_id 的一级类别一致
  OR atom 的 tertiary_factor 包含 source/target
"""
import json
import re
from datetime import datetime
from collections import defaultdict
import shutil

ATOMS_PATH = 'claim_atoms/all_claim_atoms.json'
EDGES_PATH = 'factor_causal_edges_v2.json'
ONTOLOGY_PATH = 'factor_ontology.json'
REPORT_PATH = 'causal_enrichment_report.md'
BACKUP_PATH = 'factor_causal_edges_v2.json.bak_pre_enrichment'

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


def extract_candidate_edges(atoms, existing_edges, nodes):
    """从因果链条观点提取候选新边"""
    causal_atoms = [a for a in atoms if a.get('claim_type') == '因果链条']
    existing_ids = {e['edge_id'] for e in existing_edges}

    negative_kws = ['收紧', '压制', '拖累', '下行', '减少', '降低', '负向', '抑制',
                    '走弱', '弱化', '下移', '压低', '背离', '反向']
    positive_kws = ['宽松', '补充', '增强', '支撑', '推动', '促进', '带来', '推高',
                    '上行', '增加', '提升', '强化', '正向', '有利', '助推', '推升']

    # 因子关键词索引（用于从 raw_text 推断 source）
    factor_kw_index = {
        'FD_005': ['增长动能', '经济动能', '内需', '内需修复', '经济增长', '经济增速'],
        'FD_007': ['通胀', 'CPI', 'PPI', '价格水平', '物价', '通缩'],
        'FD_003': ['修复斜率', '经济修复斜率', '修复节奏'],
        'PL_006': ['央行', '货币当局', '央行态度'],
        'PL_011': ['降准', '降息', '货币政策预期', '宽松预期', '降息预期'],
        'LQ_001': ['资金面', '流动性', '资金宽松', '资金条件', '资金利率'],
        'LQ_005': ['DR007', '资金价格中枢', '短端利率', '资金中枢'],
        'LQ_002': ['央行投放', '央行回笼', 'OMO', '逆回购', '买断式'],
        'MS_001': ['风险偏好', '避险', 'Risk off', '情绪', '风险情绪'],
        'MS_003': ['拥挤', '拥挤交易', '一致预期', '拥挤度'],
        'IB_012': ['配置盘', '机构配置', '理财', '保险', '委托人'],
        'IB_003': ['外资', '北向', '外资流入'],
    }

    candidate_edges = []
    seen_pairs = set()

    for atom in causal_atoms:
        raw = atom.get('raw_text', '')
        pf_label = atom.get('primary_factor', '')
        pf_code = PRIMARY_FACTOR_MAP.get(pf_label, '')
        tgt_id = atom.get('secondary_factor', '')
        tgt_label = atom.get('secondary_factor_label', '')
        tgt_code = get_code(tgt_id)

        if not pf_code or not tgt_id:
            continue

        # sign 判断
        neg_count = sum(1 for kw in negative_kws if kw in raw)
        pos_count = sum(1 for kw in positive_kws if kw in raw)
        sign = '+' if pos_count >= neg_count else '-'

        # 从 raw_text 里找有没有提到其他因子（作为 source）
        source_candidates = []
        for fid, kws in factor_kw_index.items():
            src_code = get_code(fid)
            if src_code == tgt_code:  # 同一级跳过
                continue
            for kw in kws:
                if kw in raw and fid != tgt_id:
                    lbl = nodes[fid]['factor_label'] if fid in nodes else kws[0]
                    source_candidates.append((fid, lbl))
                    break

        # 取第一个候选 source
        if not source_candidates:
            continue

        src_id, src_label = source_candidates[0]
        edge_id = f'{src_id}→{tgt_id}'

        if edge_id in existing_ids or edge_id in seen_pairs:
            # 已存在边：更新 supporting_atom_ids
            for e in existing_edges:
                if e['edge_id'] == edge_id:
                    if atom['atom_id'] not in e['supporting_atom_ids']:
                        e['supporting_atom_ids'].append(atom['atom_id'])
                        e['internal_support_count'] = len(e['supporting_atom_ids'])
            continue

        seen_pairs.add(edge_id)
        candidate_edges.append({
            'edge_id': edge_id,
            'source_factor_id': src_id,
            'source_factor_label': src_label,
            'target_factor_id': tgt_id,
            'target_factor_label': tgt_label,
            'sign': sign,
            'strength_score': 0.4,
            'lag': '即时',
            'conditions': '',
            'mechanism': f'由 claim_atom {atom["atom_id"]} 文本推断',
            'edge_type': 'cross_factor',
            'internal_support_count': 1,
            'recent_strength_delta': 0.0,
            'supporting_atom_ids': [atom['atom_id']],
            'conflicting_atom_ids': [],
            'period_validity': [atom.get('date', '')],
            'confidence': '低',
            'review_status': '候选-待人工审核',
            'created_at': datetime.now().strftime('%Y-%m-%d'),
            'updated_at': datetime.now().strftime('%Y-%m-%d'),
        })

    return candidate_edges


def write_report(edges_data, candidate_edges, original_edge_count, total_atoms):
    edges = edges_data['edges']
    today = datetime.now().strftime('%Y-%m-%d')
    confirmed_edges = [e for e in edges if e.get('review_status') != '候选-待人工审核']

    from collections import Counter
    support_dist = {'0': 0, '1-5': 0, '6-10': 0, '11+': 0}
    for e in confirmed_edges:
        cnt = e.get('internal_support_count', 0)
        if cnt == 0: support_dist['0'] += 1
        elif cnt <= 5: support_dist['1-5'] += 1
        elif cnt <= 10: support_dist['6-10'] += 1
        else: support_dist['11+'] += 1

    top_supported = sorted(confirmed_edges, key=lambda x: x.get('internal_support_count', 0), reverse=True)[:10]

    lines = [
        f'# 因果图谱增量 Enrichment 报告',
        f'',
        f'**生成时间**：{today}',
        f'',
        f'## 一、现有边 Support Count 更新（精确双因子匹配）',
        f'',
        f'- 原有因果边数：{original_edge_count}',
        f'- 参与统计的 claim_atoms：{total_atoms} 条',
        f'- 更新后 support_count > 0 的边：{sum(1 for e in confirmed_edges if e.get("internal_support_count", 0) > 0)} / {len(confirmed_edges)}',
        f'',
        f'> **匹配规则**：atom.secondary_factor == edge.target_factor_id AND atom.primary_factor 一级类别 == edge.source_factor_id 一级类别',
        f'',
        f'### Support Count 分布（仅已确认边）',
        f'',
        f'| support_count 区间 | 边数 |',
        f'|---|---|',
    ]
    for bucket in ['0', '1-5', '6-10', '11+']:
        lines.append(f'| {bucket} | {support_dist[bucket]} |')

    lines += [
        f'',
        f'### Top 10 高支撑因果边',
        f'',
        f'| edge_id | source | target | support_count | sign |',
        f'|---|---|---|---|---|',
    ]
    for e in top_supported:
        lines.append(
            f'| {e["edge_id"]} | {e.get("source_factor_label","")} | {e.get("target_factor_label","")} '
            f'| {e.get("internal_support_count", 0)} | {e.get("sign","")} |'
        )

    lines += [
        f'',
        f'## 二、候选新因果边（跨一级因子，需人工审核）',
        f'',
        f'共提取 **{len(candidate_edges)}** 条候选边：',
        f'',
        f'| edge_id | source | target | sign | 推断来源 atom |',
        f'|---|---|---|---|---|',
    ]
    for ce in candidate_edges:
        lines.append(
            f'| {ce["edge_id"]} | {ce.get("source_factor_label","")} | {ce.get("target_factor_label","")} '
            f'| {ce["sign"]} | {ce["supporting_atom_ids"][0] if ce["supporting_atom_ids"] else ""} |'
        )

    lines += [
        f'',
        f'## 三、更新说明',
        f'',
        f'- 现有 {original_edge_count} 条边：support_count / supporting_atom_ids / conflicting_atom_ids 已用 {total_atoms} 条 atoms 精确重算',
        f'- 候选新边：{len(candidate_edges)} 条（review_status = "候选-待人工审核"）',
        f'- 更新后总边数：{original_edge_count + len(candidate_edges)}',
        f'- 图谱版本：v2.1.0',
        f'- 备份路径：{BACKUP_PATH}',
    ]

    with open(REPORT_PATH, 'w', encoding='utf-8') as f:
        f.write('\n'.join(lines))
    print(f'报告已写入: {REPORT_PATH}')


def main():
    print('=== 因果图谱增量 Enrichment v2 ===')

    # 备份（已有备份则跳过）
    import os
    if not os.path.exists(BACKUP_PATH):
        shutil.copy2(EDGES_PATH, BACKUP_PATH)
        print(f'已备份: {BACKUP_PATH}')
    else:
        print(f'备份已存在，跳过: {BACKUP_PATH}')

    atoms, edges_data, nodes = load_data()
    original_edge_count = len(edges_data['edges'])
    # 移除上次跑的候选边（重新计算）
    edges_data['edges'] = [e for e in edges_data['edges'] if e.get('review_status') != '候选-待人工审核']
    print(f'原始确认边数: {len(edges_data["edges"])} （已过滤候选边）')
    print(f'atoms 总数: {len(atoms)}')

    # Step 1: 更新 support_count（精确匹配）
    print('\n--- Step 1: 精确更新 support_count ---')
    edges_data = update_support_counts(atoms, edges_data)

    # Step 2: 提取候选边
    print('\n--- Step 2: 提取候选新边 ---')
    candidate_edges = extract_candidate_edges(atoms, edges_data['edges'], nodes)
    print(f'提取候选边: {len(candidate_edges)} 条')

    # Step 3: 追加候选边
    base_count = len(edges_data['edges'])
    edges_data['edges'].extend(candidate_edges)
    edges_data['metadata']['total_edges'] = len(edges_data['edges'])
    edges_data['metadata']['version'] = '2.1.0'
    edges_data['metadata']['date'] = datetime.now().strftime('%Y-%m-%d')
    edges_data['metadata']['note'] = (
        f'v2.1.0: support_count 已用 {len(atoms)} 条 atoms 精确重算（双因子匹配）；'
        f'新增 {len(candidate_edges)} 条候选边（review_status=候选-待人工审核）'
    )
    edges_data['metadata']['atoms_file'] = f'all_claim_atoms.json ({len(atoms)} atoms)'

    # Step 4: 写回
    with open(EDGES_PATH, 'w', encoding='utf-8') as f:
        json.dump(edges_data, f, ensure_ascii=False, indent=2)
    print(f'\n已写入: {EDGES_PATH}')
    print(f'总边数: {len(edges_data["edges"])} = 确认边 {base_count} + 候选边 {len(candidate_edges)}')

    # Step 5: 报告
    write_report(edges_data, candidate_edges, base_count, len(atoms))

    # Summary
    confirmed_edges = [e for e in edges_data['edges'] if e.get('review_status') != '候选-待人工审核']
    top = sorted(confirmed_edges, key=lambda x: x.get('internal_support_count', 0), reverse=True)[:10]
    print('\n=== Top 10 高支撑因果边（精确匹配）===')
    for e in top:
        print(f'  {e["edge_id"]}: {e.get("source_factor_label","")} → {e.get("target_factor_label","")} '
              f'support={e["internal_support_count"]} sign={e.get("sign","")}')


if __name__ == '__main__':
    main()
