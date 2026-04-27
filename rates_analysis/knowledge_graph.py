"""
可查询、可验证、可演化的知识图谱模块 v2.0
提供对因子本体库、因果图谱、观点原子的统一查询接口。
新增：反向溯源（trace_backward）、正向传导（trace_forward）、路径搜索、根因分析。
"""
import json
from pathlib import Path
from typing import List, Dict, Optional, Any, Tuple
from collections import deque

class KnowledgeGraph:
    def __init__(self, data_dir: str = "."):
        self.data_dir = Path(data_dir)
        self.ontology = None
        self.edges = None
        self.atoms = None
        self.nodes_map = None
        self.edges_map = None
        self.load_data()
    
    def load_data(self):
        """加载所有数据文件"""
        # 因子本体库
        ontology_path = self.data_dir / "factor_ontology.json"
        with open(ontology_path, 'r', encoding='utf-8') as f:
            self.ontology = json.load(f)
        # 构建节点映射
        self.nodes_map = {node['factor_id']: node for node in self.ontology.get('nodes', [])}
        
        # 因果图谱
        edges_path = self.data_dir / "factor_causal_edges_v2.json"
        with open(edges_path, 'r', encoding='utf-8') as f:
            edges_data = json.load(f)
        self.edges = edges_data.get('edges', [])
        # 构建边映射
        self.edges_map = {edge['edge_id']: edge for edge in self.edges}
        
        # 观点原子
        atoms_path = self.data_dir / "claim_atoms" / "all_claim_atoms.json"
        if atoms_path.exists():
            with open(atoms_path, 'r', encoding='utf-8') as f:
                atoms_data = json.load(f)
            self.atoms = atoms_data.get('claim_atoms', [])
        else:
            self.atoms = []
    
    def get_factor(self, factor_id: str) -> Optional[Dict]:
        """根据因子ID查询因子信息"""
        return self.nodes_map.get(factor_id)
    
    def search_factors(self, keyword: str) -> List[Dict]:
        """根据关键词搜索因子（标签、别名）"""
        results = []
        for node in self.ontology.get('nodes', []):
            if keyword in node.get('factor_label', ''):
                results.append(node)
                continue
            for alias in node.get('aliases', []):
                if keyword in alias:
                    results.append(node)
                    break
        return results
    
    def get_edges(self, source_factor_id: Optional[str] = None, 
                  target_factor_id: Optional[str] = None,
                  min_support: int = 0) -> List[Dict]:
        """查询因果边，可过滤源、目标因子，最小证据数量"""
        filtered = []
        for edge in self.edges:
            if source_factor_id and edge.get('source_factor_id') != source_factor_id:
                continue
            if target_factor_id and edge.get('target_factor_id') != target_factor_id:
                continue
            support_count = len(edge.get('supporting_atom_ids', []))
            if support_count < min_support:
                continue
            filtered.append(edge)
        return filtered
    
    def get_edge(self, edge_id: str) -> Optional[Dict]:
        """根据边ID查询边"""
        return self.edges_map.get(edge_id)
    
    def get_supporting_atoms(self, edge_id: str) -> List[Dict]:
        """获取支撑某条边的所有观点原子"""
        edge = self.get_edge(edge_id)
        if not edge:
            return []
        atom_ids = edge.get('supporting_atom_ids', [])
        # 构建原子ID到原子的映射
        atoms_map = {atom['atom_id']: atom for atom in self.atoms}
        return [atoms_map[aid] for aid in atom_ids if aid in atoms_map]
    
    def get_conflicting_atoms(self, edge_id: str) -> List[Dict]:
        """获取与某条边冲突的所有观点原子"""
        edge = self.get_edge(edge_id)
        if not edge:
            return []
        atom_ids = edge.get('conflicting_atom_ids', [])
        atoms_map = {atom['atom_id']: atom for atom in self.atoms}
        return [atoms_map[aid] for aid in atom_ids if aid in atoms_map]
    
    # ── v2.0 新增：反向溯源 / 正向传导 / 路径搜索 / 根因分析 ──
    
    def _build_adjacency(self):
        """构建邻接表（入边/出边），供图算法使用"""
        if hasattr(self, '_adj_in') and hasattr(self, '_adj_out'):
            return
        self._adj_out = {}  # source -> [(target, edge)]
        self._adj_in = {}   # target -> [(source, edge)]
        for edge in self.edges:
            s = edge['source_factor_id']
            t = edge['target_factor_id']
            self._adj_out.setdefault(s, []).append((t, edge))
            self._adj_in.setdefault(t, []).append((s, edge))
    
    def trace_backward(self, target_id: str, max_depth: int = 3) -> List[Dict]:
        """从目标因子反向溯源，沿入边向上追踪到根因（BFS）
        
        Args:
            target_id: 目标因子ID
            max_depth: 最大追溯深度
            
        Returns:
            路径列表，每条路径是从根因到目标的因子链
        """
        self._build_adjacency()
        if target_id not in self._adj_in:
            return [{'path': [target_id], 'path_labels': [self.nodes_map.get(target_id, {}).get('factor_label', target_id)], 'depth': 0, 'path_edges': [], 'cumulative_strength': 1.0}]
        
        # BFS 找所有路径
        results = []
        # queue: (current_id, current_path_ids, current_path_labels, current_edges, depth, cumulative_strength)
        queue = deque()
        queue.append((target_id, [target_id], 
                      [self.nodes_map.get(target_id, {}).get('factor_label', target_id)],
                      [], 0, 1.0))
        
        while queue:
            current, path_ids, path_labels, path_edges, depth, cum_strength = queue.popleft()
            
            # 如果当前节点没有入边（是根因）或达到最大深度，记录路径
            if current not in self._adj_in or depth >= max_depth:
                results.append({
                    'target_id': target_id,
                    'root_cause_id': current,
                    'root_cause_label': self.nodes_map.get(current, {}).get('factor_label', current),
                    'path_ids': path_ids,
                    'path_labels': path_labels,
                    'path_edges': path_edges,
                    'depth': depth,
                    'cumulative_strength': round(cum_strength, 3)
                })
                continue
            
            for src_id, edge in self._adj_in.get(current, []):
                if src_id in path_ids:  # 避免环路
                    results.append({
                        'target_id': target_id,
                        'root_cause_id': src_id,
                        'root_cause_label': self.nodes_map.get(src_id, {}).get('factor_label', src_id),
                        'path_ids': path_ids,
                        'path_labels': path_labels,
                        'path_edges': path_edges,
                        'depth': depth,
                        'cumulative_strength': round(cum_strength, 3)
                    })
                    continue
                strength = edge.get('strength_score', 0.5)
                sign = edge.get('sign', '?')
                new_cum_strength = cum_strength * strength
                queue.append((
                    src_id,
                    [src_id] + path_ids,
                    [self.nodes_map.get(src_id, {}).get('factor_label', src_id)] + path_labels,
                    [{
                        'edge_id': edge['edge_id'],
                        'source': src_id,
                        'source_label': self.nodes_map.get(src_id, {}).get('factor_label', src_id),
                        'target': current,
                        'target_label': self.nodes_map.get(current, {}).get('factor_label', current),
                        'sign': sign,
                        'strength': strength,
                        'mechanism': edge.get('mechanism', ''),
                        'lag': edge.get('lag', '')
                    }] + path_edges,
                    depth + 1,
                    new_cum_strength
                ))
        
        # 按累积强度降序排列
        results.sort(key=lambda r: -r['cumulative_strength'])
        return results
    
    def trace_forward(self, source_id: str, max_depth: int = 3) -> List[Dict]:
        """从源因子正向传导，沿出边追踪到末端影响因子（BFS）
        
        Args:
            source_id: 源因子ID
            max_depth: 最大传导深度
            
        Returns:
            路径列表，每条路径是从源因子到末端因子的传导链
        """
        self._build_adjacency()
        if source_id not in self._adj_out:
            return [{'path': [source_id], 'path_labels': [self.nodes_map.get(source_id, {}).get('factor_label', source_id)], 'depth': 0, 'path_edges': [], 'cumulative_strength': 1.0}]
        
        results = []
        queue = deque()
        queue.append((source_id, [source_id],
                      [self.nodes_map.get(source_id, {}).get('factor_label', source_id)],
                      [], 0, 1.0))
        
        while queue:
            current, path_ids, path_labels, path_edges, depth, cum_strength = queue.popleft()
            
            if current not in self._adj_out or depth >= max_depth:
                results.append({
                    'source_id': source_id,
                    'terminal_id': current,
                    'terminal_label': self.nodes_map.get(current, {}).get('factor_label', current),
                    'path_ids': path_ids,
                    'path_labels': path_labels,
                    'path_edges': path_edges,
                    'depth': depth,
                    'cumulative_strength': round(cum_strength, 3)
                })
                continue
            
            for tgt_id, edge in self._adj_out.get(current, []):
                if tgt_id in path_ids:
                    results.append({
                        'source_id': source_id,
                        'terminal_id': tgt_id,
                        'terminal_label': self.nodes_map.get(tgt_id, {}).get('factor_label', tgt_id),
                        'path_ids': path_ids,
                        'path_labels': path_labels,
                        'path_edges': path_edges,
                        'depth': depth,
                        'cumulative_strength': round(cum_strength, 3)
                    })
                    continue
                strength = edge.get('strength_score', 0.5)
                sign = edge.get('sign', '?')
                new_cum_strength = cum_strength * strength
                queue.append((
                    tgt_id,
                    path_ids + [tgt_id],
                    path_labels + [self.nodes_map.get(tgt_id, {}).get('factor_label', tgt_id)],
                    path_edges + [{
                        'edge_id': edge['edge_id'],
                        'source': current,
                        'source_label': self.nodes_map.get(current, {}).get('factor_label', current),
                        'target': tgt_id,
                        'target_label': self.nodes_map.get(tgt_id, {}).get('factor_label', tgt_id),
                        'sign': sign,
                        'strength': strength,
                        'mechanism': edge.get('mechanism', ''),
                        'lag': edge.get('lag', '')
                    }],
                    depth + 1,
                    new_cum_strength
                ))
        
        results.sort(key=lambda r: -r['cumulative_strength'])
        return results
    
    def find_strongest_path(self, source_id: str, target_id: str, max_depth: int = 4) -> Optional[Dict]:
        """找出两个因子之间累积强度最高的因果路径（加权BFS）
        
        Args:
            source_id: 源因子ID
            target_id: 目标因子ID
            max_depth: 搜索最大深度
            
        Returns:
            最强路径，含路径详情和累积强度
        """
        self._build_adjacency()
        if source_id == target_id:
            return {'path_ids': [source_id], 'path_labels': [self.nodes_map.get(source_id, {}).get('factor_label', source_id)], 'depth': 0, 'path_edges': [], 'cumulative_strength': 1.0}
        
        # Dijkstra 风格：权重取 -log(strength) 找最短路径
        import heapq
        INF = float('inf')
        dist = {source_id: 0}
        prev = {}
        pq = [(0, source_id)]
        
        while pq:
            d, current = heapq.heappop(pq)
            if d > dist.get(current, INF):
                continue
            if current == target_id:
                break
            if current not in self._adj_out:
                continue
            for tgt_id, edge in self._adj_out[current]:
                strength = edge.get('strength_score', 0.5)
                if strength <= 0:
                    weight = 100  # 极小强度近似无穷
                else:
                    import math
                    weight = -math.log(strength)
                nd = d + weight
                if nd < dist.get(tgt_id, INF):
                    dist[tgt_id] = nd
                    prev[tgt_id] = (current, edge)
                    heapq.heappush(pq, (nd, tgt_id))
        
        if target_id not in prev and source_id != target_id:
            return None
        
        # 回溯路径
        path_ids = [target_id]
        path_edges = []
        current = target_id
        while current in prev:
            src, edge = prev[current]
            path_ids.insert(0, src)
            path_edges.insert(0, {
                'edge_id': edge['edge_id'],
                'source': src,
                'source_label': self.nodes_map.get(src, {}).get('factor_label', src),
                'target': current,
                'target_label': self.nodes_map.get(current, {}).get('factor_label', current),
                'sign': edge.get('sign', '?'),
                'strength': edge.get('strength_score', 0.5),
                'mechanism': edge.get('mechanism', ''),
                'lag': edge.get('lag', '')
            })
            current = src
        
        cum_strength = 1.0
        for pe in path_edges:
            cum_strength *= pe['strength']
        
        return {
            'source_id': source_id,
            'target_id': target_id,
            'path_ids': path_ids,
            'path_labels': [self.nodes_map.get(nid, {}).get('factor_label', nid) for nid in path_ids],
            'path_edges': path_edges,
            'depth': len(path_edges),
            'cumulative_strength': round(cum_strength, 3)
        }
    
    def find_root_causes(self, target_id: str, max_depth: int = 3) -> List[Dict]:
        """找出影响目标因子的根因（入度为0的最上游节点）

        Args:
            target_id: 目标因子ID
            max_depth: 最大追溯深度

        Returns:
            根因列表，按累积强度降序
        """
        paths = self.trace_backward(target_id, max_depth=max_depth)
        # 筛选出真正到了根因的路径（当前节点没有入边）
        self._build_adjacency()
        root_paths = []
        seen_roots = set()
        for p in paths:
            root_id = p['root_cause_id']
            if root_id not in self._adj_in:
                if root_id not in seen_roots:
                    seen_roots.add(root_id)
                    root_paths.append(p)
        # 如果没有找到入度为0的根因，返回累积强度最高的路径
        if not root_paths:
            return paths[:5]
        return root_paths[:5]
    
    def get_causal_chain_summary(self, target_id: str, depth: int = 3) -> str:
        """生成目标因子的因果链汇总文本，适合直接阅读
        
        Args:
            target_id: 目标因子ID
            depth: 追溯深度
            
        Returns:
            格式化的因果链文本
        """
        paths = self.trace_backward(target_id, max_depth=depth)
        forward_paths = self.trace_forward(target_id, max_depth=depth)
        node = self.nodes_map.get(target_id, {})
        
        lines = []
        lines.append("=" * 60)
        lines.append(f"【因子分析】{node.get('factor_label', target_id)} ({target_id})")
        lines.append(f"  {node.get('description', '无描述')}")
        lines.append(f"  一级因子: {node.get('primary_factor', '未知')}")
        lines.append("=" * 60)
        
        # 反向溯源
        lines.append("\n→→ 反向溯源（谁影响它）")
        if paths:
            for i, p in enumerate(paths[:5]):
                labels = ' → '.join(p['path_labels'])
                edges_detail = []
                for e in p['path_edges']:
                    sign_symbol = '+' if e['sign'] == '+' else ('-' if e['sign'] == '-' else '?')
                    edges_detail.append(f"    {e['source_label']} {sign_symbol}{e['strength']:.1f}→ {e['target_label']} [{e['lag']}] {e['mechanism']}")
                lines.append(f"  路径 {i+1} (强度={p['cumulative_strength']}, 深度={p['depth']}): {labels}")
                for ed in edges_detail:
                    lines.append(ed)
        else:
            lines.append("  （无上游因子）")
        
        # 正向传导
        lines.append("\n→→ 正向传导（它影响谁）")
        if forward_paths:
            for i, p in enumerate(forward_paths[:5]):
                labels = ' → '.join(p['path_labels'])
                edges_detail = []
                for e in p['path_edges']:
                    sign_symbol = '+' if e['sign'] == '+' else ('-' if e['sign'] == '-' else '?')
                    edges_detail.append(f"    {e['source_label']} {sign_symbol}{e['strength']:.1f}→ {e['target_label']} [{e['lag']}] {e['mechanism']}")
                lines.append(f"  路径 {i+1} (强度={p['cumulative_strength']}, 深度={p['depth']}): {labels}")
                for ed in edges_detail:
                    lines.append(ed)
        else:
            lines.append("  （无下游因子）")
        
        # 直接关联边
        lines.append("\n→→ 直接关联边")
        factor_edges = self.get_factor_edges(target_id)
        if factor_edges.get('incoming') or factor_edges.get('outgoing'):
            for e in factor_edges.get('incoming', []):
                sign_symbol = '+' if e['sign'] == '+' else ('-' if e['sign'] == '-' else '?')
                lines.append(f"  受 {e.get('source_factor_label')} 影响 {sign_symbol} (强度={e.get('strength_score', '?')}, 滞后={e.get('lag', '?')}, 证据={len(e.get('supporting_atom_ids', []))}条)")
            for e in factor_edges.get('outgoing', []):
                sign_symbol = '+' if e['sign'] == '+' else ('-' if e['sign'] == '-' else '?')
                lines.append(f"  影响 {e.get('target_factor_label')} {sign_symbol} (强度={e.get('strength_score', '?')}, 滞后={e.get('lag', '?')}, 证据={len(e.get('supporting_atom_ids', []))}条)")
        else:
            lines.append("  （无直接关联边）")
        
        lines.append("\n" + "=" * 60)
        return '\n'.join(lines)
    
    def get_factor_edges(self, factor_id: str, direction: str = 'both') -> Dict[str, List]:
        """查询与某因子相关的所有边，方向可选 'in', 'out', 'both'"""
        incoming = []
        outgoing = []
        for edge in self.edges:
            if edge.get('source_factor_id') == factor_id:
                outgoing.append(edge)
            if edge.get('target_factor_id') == factor_id:
                incoming.append(edge)
        
        if direction == 'in':
            return {'incoming': incoming}
        elif direction == 'out':
            return {'outgoing': outgoing}
        else:
            return {'incoming': incoming, 'outgoing': outgoing}
    
    def validate_edge(self, edge_id: str) -> Dict[str, Any]:
        """验证单条边的完整性"""
        edge = self.get_edge(edge_id)
        if not edge:
            return {'valid': False, 'error': '边不存在'}
        
        issues = []
        # 检查源因子是否存在
        src_id = edge.get('source_factor_id')
        if not src_id or src_id not in self.nodes_map:
            issues.append(f"源因子ID无效: {src_id}")
        # 检查目标因子是否存在
        tgt_id = edge.get('target_factor_id')
        if not tgt_id or tgt_id not in self.nodes_map:
            issues.append(f"目标因子ID无效: {tgt_id}")
        # 检查sign
        sign = edge.get('sign')
        if sign not in ('+', '-', '?'):
            issues.append(f"符号无效: {sign}")
        # 检查lag
        lag = edge.get('lag')
        if not lag or lag.strip() == '':
            issues.append("时滞缺失")
        # 检查证据原子
        support_ids = edge.get('supporting_atom_ids', [])
        if not support_ids:
            issues.append("无证据原子支撑")
        else:
            # 验证证据原子是否存在
            atoms_map = {atom['atom_id']: atom for atom in self.atoms}
            missing = [aid for aid in support_ids if aid not in atoms_map]
            if missing:
                issues.append(f"证据原子缺失: {missing[:3]}")
        
        return {
            'valid': len(issues) == 0,
            'edge_id': edge_id,
            'issues': issues,
            'support_count': len(support_ids),
            'review_status': edge.get('review_status', '未知')
        }
    
    def validate_all_edges(self) -> Dict[str, Any]:
        """验证所有边的完整性"""
        results = []
        valid_count = 0
        for edge in self.edges:
            validation = self.validate_edge(edge['edge_id'])
            results.append(validation)
            if validation['valid']:
                valid_count += 1
        
        total = len(self.edges)
        return {
            'total_edges': total,
            'valid_edges': valid_count,
            'invalid_edges': total - valid_count,
            'validation_rate': valid_count / total if total > 0 else 0,
            'results': results
        }
    
    def add_edge(self, source_factor_id: str, target_factor_id: str, 
                 sign: str, lag: str, mechanism: str = '', 
                 edge_type: str = 'hierarchical', conditions: str = '',
                 supporting_atom_ids: List[str] = None) -> Dict:
        """添加一条新的因果边（演化功能）"""
        # 检查因子是否存在
        if source_factor_id not in self.nodes_map:
            raise ValueError(f"源因子不存在: {source_factor_id}")
        if target_factor_id not in self.nodes_map:
            raise ValueError(f"目标因子不存在: {target_factor_id}")
        
        # 生成edge_id
        edge_id = f"{source_factor_id}→{target_factor_id}"
        if edge_id in self.edges_map:
            raise ValueError(f"边已存在: {edge_id}")
        
        new_edge = {
            'edge_id': edge_id,
            'source_factor_id': source_factor_id,
            'source_factor_label': self.nodes_map[source_factor_id]['factor_label'],
            'target_factor_id': target_factor_id,
            'target_factor_label': self.nodes_map[target_factor_id]['factor_label'],
            'sign': sign,
            'strength_score': 0.5,  # 默认强度
            'lag': lag,
            'conditions': conditions,
            'mechanism': mechanism,
            'edge_type': edge_type,
            'internal_support_count': len(supporting_atom_ids) if supporting_atom_ids else 0,
            'recent_strength_delta': 0.0,
            'supporting_atom_ids': supporting_atom_ids or [],
            'conflicting_atom_ids': [],
            'period_validity': ['普遍成立'],
            'confidence': '低',
            'review_status': '待审核',
            'created_at': '2026-04-22',  # 应使用当前日期
            'updated_at': '2026-04-22'
        }
        
        # 添加到内存
        self.edges.append(new_edge)
        self.edges_map[edge_id] = new_edge
        
        return new_edge
    
    def save_edges(self):
        """保存更新后的因果图谱到文件"""
        edges_path = self.data_dir / "factor_causal_edges_v2.json"
        with open(edges_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        data['edges'] = self.edges
        data['metadata']['date'] = '2026-04-22'  # 更新日期
        data['metadata']['total_edges'] = len(self.edges)
        
        # 备份原文件
        backup_path = edges_path.with_suffix('.json.bak')
        import shutil
        shutil.copy2(edges_path, backup_path)
        
        # 写入新文件
        with open(edges_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        
        print(f"已保存因果图谱到 {edges_path}，备份在 {backup_path}")


def demo():
    """演示知识图谱的查询、验证、演化功能"""
    kg = KnowledgeGraph()
    
    print("=== 可查询功能演示 ===")
    # 1. 查询因子
    factor = kg.get_factor('FD_001')
    print(f"因子 FD_001: {factor['factor_label'] if factor else '未找到'}")
    
    # 2. 查询边
    edges = kg.get_edges(source_factor_id='FD_001', min_support=1)
    print(f"FD_001 作为源因子的边（有证据）: {len(edges)} 条")
    
    # 3. 查询因子相关边
    factor_edges = kg.get_factor_edges('FD_001', direction='both')
    print(f"FD_001 入边: {len(factor_edges.get('incoming', []))} 条")
    print(f"FD_001 出边: {len(factor_edges.get('outgoing', []))} 条")
    
    print("\n=== 可验证功能演示 ===")
    # 验证单条边
    if edges:
        validation = kg.validate_edge(edges[0]['edge_id'])
        print(f"边 {edges[0]['edge_id']} 验证结果: {'有效' if validation['valid'] else '无效'}")
        if not validation['valid']:
            print(f"  问题: {validation['issues']}")
    
    # 验证所有边
    all_validation = kg.validate_all_edges()
    print(f"所有边验证: {all_validation['valid_edges']}/{all_validation['total_edges']} 有效")
    
    print("\n=== 可演化功能演示 ===")
    # 尝试添加新边（示例，实际需要真实因子ID）
    try:
        # 这里使用已知存在的因子ID
        new_edge = kg.add_edge(
            source_factor_id='FD_001',
            target_factor_id='FD_002',
            sign='+',
            lag='1-3M',
            mechanism='经济评估影响通胀预期',
            supporting_atom_ids=[]
        )
        print(f"已添加新边: {new_edge['edge_id']}")
        # 保存更改（注释掉，避免意外保存）
        # kg.save_edges()
        print("（演化保存功能已注释，如需保存请取消注释）")
    except ValueError as e:
        print(f"添加边失败: {e}")
    
    print("\n=== 知识图谱统计 ===")
    print(f"因子节点数: {len(kg.nodes_map)}")
    print(f"因果边数: {len(kg.edges)}")
    print(f"观点原子数: {len(kg.atoms)}")


if __name__ == '__main__':
    demo()