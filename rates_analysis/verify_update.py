import json

def verify_update():
    with open('factor_causal_edges_v2.json', 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    edges = data['edges']
    
    # 统计各类状态
    status_counts = {}
    support_counts = {}
    for edge in edges:
        status = edge.get('review_status', '')
        support = edge.get('internal_support_count', 0)
        status_counts[status] = status_counts.get(status, 0) + 1
        # 按 support 范围分类
        if support >= 3:
            support_counts['>=3'] = support_counts.get('>=3', 0) + 1
        else:
            support_counts['<3'] = support_counts.get('<3', 0) + 1
    
    print('=== Review status distribution ===')
    for status, count in status_counts.items():
        print(f'  {status}: {count}')
    
    print('\n=== Support count distribution ===')
    for cat, count in support_counts.items():
        print(f'  {cat}: {count}')
    
    # 检查是否还有 internal_support_count >= 3 且 review_status 为“待审核”的边
    pending_high_support = []
    for edge in edges:
        if edge.get('internal_support_count', 0) >= 3 and edge.get('review_status', '') == '待审核':
            pending_high_support.append(edge)
    
    print(f'\nEdges with support >=3 but still "待审核": {len(pending_high_support)}')
    if pending_high_support:
        print('These edges:')
        for edge in pending_high_support:
            print(f'  {edge["edge_id"]}: support={edge["internal_support_count"]}')
    
    # 检查更新是否正确：之前 internal_support_count >= 3 且 review_status 为“待审核”的边，现在应该是“已审核”
    updated_correctly = 0
    for edge in edges:
        if edge.get('internal_support_count', 0) >= 3:
            if edge.get('review_status', '') == '已审核':
                updated_correctly += 1
    
    print(f'\nEdges with support >=3 and status "已审核": {updated_correctly}')
    
    # 输出一些示例边
    print('\n=== Sample edges (first 5) ===')
    for i, edge in enumerate(edges[:5]):
        print(f'  {edge["edge_id"]}: support={edge.get("internal_support_count", 0)}, status={edge.get("review_status", "")}')

if __name__ == '__main__':
    verify_update()