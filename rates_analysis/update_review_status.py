import json
import sys

def update_review_status():
    # 加载因果边数据
    with open('factor_causal_edges_v2.json', 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    edges = data['edges']
    updated_count = 0
    target_edges = []
    
    for edge in edges:
        support = edge.get('internal_support_count', 0)
        status = edge.get('review_status', '')
        # 检查条件：support >= 3 且 status 为 "待审核"
        if support >= 3 and status == '待审核':
            target_edges.append(edge)
            edge['review_status'] = '已审核'
            updated_count += 1
    
    # 保存更新后的数据
    with open('factor_causal_edges_v2.json', 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    
    print(f'Total edges: {len(edges)}')
    print(f'Edges with internal_support_count >= 3 and review_status="待审核": {len(target_edges)}')
    print(f'Updated edges: {updated_count}')
    
    # 显示更新的边详情
    if target_edges:
        print('\nUpdated edges:')
        for edge in target_edges:
            print(f'  {edge["edge_id"]}: {edge["source_factor_label"]} → {edge["target_factor_label"]}, support={edge["internal_support_count"]}')
    
    return updated_count

if __name__ == '__main__':
    update_review_status()