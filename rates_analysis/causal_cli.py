"""
因果图谱交互式CLI查询工具 v1.0
债市五因子框架 - 知识图谱查询、溯源、传导分析

用法：
  python causal_cli.py                      # 交互式模式
  python causal_cli.py --factor FD_001      # 直接查询因子
  python causal_cli.py --trace LQ_001       # 反向溯源
  python causal_cli.py --forward FD_001     # 正向传导
  python causal_cli.py --path FD_001 LQ_001  # 最强路径
  python causal_cli.py --roots MS_003       # 根因分析
  python causal_cli.py --summary MS_001     # 因果链汇总
"""

import sys
import json
from knowledge_graph import KnowledgeGraph

# ── 一级因子 → 颜色映射（用于终端显示） ──
PRIMARY_COLORS = {
    '基本面因子': '\033[36m',   # 青色
    '政策面因子': '\033[32m',   # 绿色
    '流动性因子': '\033[34m',   # 蓝色
    '市场情绪因子': '\033[33m',  # 黄色
    '机构行为因子': '\033[35m',  # 紫色
    '市场数据输出': '\033[31m',  # 红色
}
RESET = '\033[0m'
BOLD = '\033[1m'
DIM = '\033[2m'

PRIMARY_ORDER = ['基本面因子', '政策面因子', '流动性因子', '市场情绪因子', '机构行为因子', '市场数据输出']


def color_factor(factor_id: str, node: dict) -> str:
    """给因子名加颜色"""
    pf = node.get('primary_factor', '') if node else ''
    c = PRIMARY_COLORS.get(pf, '')
    return f"{c}{factor_id}{RESET}"


def print_banner():
    """打印启动横幅"""
    print(f"""
{BOLD}╔══════════════════════════════════════════════╗
║    债市五因子因果图谱查询工具 v1.0          ║
║    51个因子 · 103条因果边 · 744个观点原子    ║
╚══════════════════════════════════════════════╝{RESET}
    """)


def print_help():
    """打印帮助菜单"""
    print(f"""
{BOLD}可用命令:{RESET}
  {BOLD}search <关键词>{RESET}     搜索因子
  {BOLD}info <因子ID>{RESET}      查看因子详情
  {BOLD}trace <因子ID>{RESET}     反向溯源（谁影响它）
  {BOLD}forward <因子ID>{RESET}   正向传导（它影响谁）
  {BOLD}path <源ID> <目标ID>{RESET}  最强因果路径
  {BOLD}roots <因子ID>{RESET}     根因分析
  {BOLD}summary <因子ID>{RESET}   完整因果链汇总
  {BOLD}edges <因子ID>{RESET}     查看直接关联边
  {BOLD}list [一级因子名]{RESET}  列出所有因子（可加筛选，如 list 基本面因子）
  {BOLD}stats{RESET}              因果图谱统计
  {BOLD}help{RESET}               显示此帮助
  {BOLD}quit{RESET}               退出

  一级因子: 基本面因子 | 政策面因子 | 流动性因子 | 市场情绪因子 | 机构行为因子
""")


def cmd_search(kg, keyword):
    """搜索因子"""
    results = kg.search_factors(keyword)
    if not results:
        print(f"  未找到包含关键词 '{keyword}' 的因子")
        return
    print(f"\n  {BOLD}搜索到 {len(results)} 个因子:{RESET}")
    for node in results:
        fid = node['factor_id']
        label = node['factor_label']
        pf = node.get('primary_factor', '未知')
        desc = node.get('description', '')
        c = PRIMARY_COLORS.get(pf, '')
        print(f"  {c}{fid}{RESET} {BOLD}{label}{RESET}  [{pf}]")
        if desc:
            print(f"    {desc}")
    print()


def cmd_info(kg, factor_id):
    """查看因子详情"""
    node = kg.get_factor(factor_id)
    if not node:
        print(f"  ⚠ 因子 '{factor_id}' 不存在")
        return
    
    fid = node['factor_id']
    label = node['factor_label']
    pf = node.get('primary_factor', '未知')
    desc = node.get('description', '')
    level = node.get('level', '?')
    aliases = node.get('aliases', [])
    c = PRIMARY_COLORS.get(pf, '')
    
    print(f"\n  {c}{BOLD}{fid}{RESET} {BOLD}{label}{RESET}")
    print(f"  级别: {level}   |   一级因子: {pf}")
    if desc:
        print(f"  描述: {desc}")
    if aliases:
        print(f"  别名: {', '.join(aliases)}")
    
    # 关联边统计
    fe = kg.get_factor_edges(factor_id)
    in_count = len(fe.get('incoming', []))
    out_count = len(fe.get('outgoing', []))
    print(f"  入边: {in_count} 条  |  出边: {out_count} 条")
    print()


def cmd_trace(kg, factor_id, depth=3):
    """反向溯源"""
    node = kg.get_factor(factor_id)
    label = node.get('factor_label', factor_id) if node else factor_id
    print(f"\n  {BOLD}反向溯源: {label} ({factor_id}){RESET}")
    print(f"  {DIM}追踪影响它的上游因子 (最大深度={depth}){RESET}\n")
    
    paths = kg.trace_backward(factor_id, max_depth=depth)
    if not paths:
        print("  (无上游因子 - 可能是根因)")
        return
    
    for i, p in enumerate(paths[:8]):
        labels = []
        for j, lid in enumerate(p['path_ids']):
            n = kg.nodes_map.get(lid, {})
            c = PRIMARY_COLORS.get(n.get('primary_factor', ''), '')
            labels.append(f"{c}{n.get('factor_label', lid)}{RESET}")
        
        chain = f"{DIM} → {RESET}".join(labels)
        strength_color = '\033[32m' if p['cumulative_strength'] >= 0.4 else ('\033[33m' if p['cumulative_strength'] >= 0.2 else '\033[31m')
        print(f"  路径{i+1}: {chain}")
        print(f"          {DIM}强度={strength_color}{p['cumulative_strength']}{RESET}{DIM}, 深度={p['depth']}{RESET}")
        
        # 显示路径中的边详情（只看第一条路径的完整详情）
        if i == 0 and p['path_edges']:
            for e in p['path_edges']:
                sign = '+' if e['sign'] == '+' else ('-' if e['sign'] == '-' else '?')
                src_c = PRIMARY_COLORS.get(kg.nodes_map.get(e['source'], {}).get('primary_factor', ''), '')
                tgt_c = PRIMARY_COLORS.get(kg.nodes_map.get(e['target'], {}).get('primary_factor', ''), '')
                print(f"          {DIM}├─ {src_c}{e['source_label']}{RESET} {BOLD}{sign}{RESET}{e['strength']} → {tgt_c}{e['target_label']}{RESET} [{e['lag']}]{RESET}")
                if e['mechanism']:
                    print(f"          {DIM}│  {e['mechanism']}{RESET}")
    
    if len(paths) > 8:
        print(f"  {DIM}... 还有 {len(paths)-8} 条路径未显示{RESET}")
    print()


def cmd_forward(kg, factor_id, depth=3):
    """正向传导"""
    node = kg.get_factor(factor_id)
    label = node.get('factor_label', factor_id) if node else factor_id
    print(f"\n  {BOLD}正向传导: {label} ({factor_id}){RESET}")
    print(f"  {DIM}追踪它影响的下游因子 (最大深度={depth}){RESET}\n")
    
    paths = kg.trace_forward(factor_id, max_depth=depth)
    if not paths:
        print("  (无下游因子 - 可能是末端节点)")
        return
    
    for i, p in enumerate(paths[:8]):
        labels = []
        for j, lid in enumerate(p['path_ids']):
            n = kg.nodes_map.get(lid, {})
            c = PRIMARY_COLORS.get(n.get('primary_factor', ''), '')
            labels.append(f"{c}{n.get('factor_label', lid)}{RESET}")
        
        chain = f"{DIM} → {RESET}".join(labels)
        strength_color = '\033[32m' if p['cumulative_strength'] >= 0.4 else ('\033[33m' if p['cumulative_strength'] >= 0.2 else '\033[31m')
        print(f"  路径{i+1}: {chain}")
        print(f"          {DIM}强度={strength_color}{p['cumulative_strength']}{RESET}{DIM}, 深度={p['depth']}{RESET}")
        
        if i == 0 and p['path_edges']:
            for e in p['path_edges']:
                sign = '+' if e['sign'] == '+' else ('-' if e['sign'] == '-' else '?')
                src_c = PRIMARY_COLORS.get(kg.nodes_map.get(e['source'], {}).get('primary_factor', ''), '')
                tgt_c = PRIMARY_COLORS.get(kg.nodes_map.get(e['target'], {}).get('primary_factor', ''), '')
                print(f"          {DIM}├─ {src_c}{e['source_label']}{RESET} {BOLD}{sign}{RESET}{e['strength']} → {tgt_c}{e['target_label']}{RESET} [{e['lag']}]{RESET}")
                if e['mechanism']:
                    print(f"          {DIM}│  {e['mechanism']}{RESET}")
    
    if len(paths) > 8:
        print(f"  {DIM}... 还有 {len(paths)-8} 条路径未显示{RESET}")
    print()


def cmd_path(kg, source_id, target_id):
    """最强路径"""
    node_s = kg.get_factor(source_id)
    node_t = kg.get_factor(target_id)
    label_s = node_s.get('factor_label', source_id) if node_s else source_id
    label_t = node_t.get('factor_label', target_id) if node_t else target_id
    
    print(f"\n  {BOLD}最强因果路径: {label_s} → {label_t}{RESET}\n")
    
    result = kg.find_strongest_path(source_id, target_id)
    if result is None:
        print("  ⚠ 两个因子之间不存在因果路径")
        return
    
    labels = []
    for lid in result['path_ids']:
        n = kg.nodes_map.get(lid, {})
        c = PRIMARY_COLORS.get(n.get('primary_factor', ''), '')
        labels.append(f"{c}{n.get('factor_label', lid)}{RESET}")
    
    chain = f" {BOLD}→{RESET} ".join(labels)
    strength_color = '\033[32m' if result['cumulative_strength'] >= 0.4 else ('\033[33m' if result['cumulative_strength'] >= 0.2 else '\033[31m')
    
    print(f"  路径: {chain}")
    print(f"  累积强度: {strength_color}{result['cumulative_strength']}{RESET}")
    print(f"  深度: {result['depth']} 跳")
    print()
    
    print(f"  {BOLD}路径详情:{RESET}")
    for i, e in enumerate(result['path_edges']):
        sign = '+' if e['sign'] == '+' else ('-' if e['sign'] == '-' else '?')
        src_c = PRIMARY_COLORS.get(kg.nodes_map.get(e['source'], {}).get('primary_factor', ''), '')
        tgt_c = PRIMARY_COLORS.get(kg.nodes_map.get(e['target'], {}).get('primary_factor', ''), '')
        print(f"  {i+1}. {src_c}{e['source_label']}{RESET} {BOLD}{sign}{RESET}{e['strength']} → {tgt_c}{e['target_label']}{RESET}  [{e['lag']}]")
        print(f"     机制: {e['mechanism']}")
    print()


def cmd_roots(kg, factor_id, depth=3):
    """根因分析"""
    node = kg.get_factor(factor_id)
    label = node.get('factor_label', factor_id) if node else factor_id
    print(f"\n  {BOLD}根因分析: {label} ({factor_id}){RESET}")
    print(f"  {DIM}找出影响该因子的最上游驱动因子{RESET}\n")
    
    roots = kg.find_root_causes(factor_id, max_depth=depth)
    if not roots:
        print("  (无根因 - 该因子可能是根因本身)")
        return
    
    for i, r in enumerate(roots[:6]):
        root_c = PRIMARY_COLORS.get(kg.nodes_map.get(r['root_cause_id'], {}).get('primary_factor', ''), '')
        strength_color = '\033[32m' if r['cumulative_strength'] >= 0.4 else ('\033[33m' if r['cumulative_strength'] >= 0.2 else '\033[31m')
        labels = []
        for lid in r['path_ids']:
            n = kg.nodes_map.get(lid, {})
            c = PRIMARY_COLORS.get(n.get('primary_factor', ''), '')
            labels.append(f"{c}{n.get('factor_label', lid)}{RESET}")
        chain = f"{DIM} → {RESET}".join(labels)
        
        print(f"  根因{i+1}: {root_c}{r['root_cause_label']}{RESET}")
        print(f"         路径: {chain}")
        print(f"         强度: {strength_color}{r['cumulative_strength']}{RESET}")
        print()
    
    if len(roots) > 6:
        print(f"  {DIM}... 还有 {len(roots)-6} 个根因未显示{RESET}")
    print()


def cmd_summary(kg, factor_id, depth=3):
    """生成完整因果链汇总文本"""
    print(kg.get_causal_chain_summary(factor_id, depth=depth))


def cmd_edges(kg, factor_id):
    """查看直接关联边"""
    node = kg.get_factor(factor_id)
    label = node.get('factor_label', factor_id) if node else factor_id
    print(f"\n  {BOLD}直接关联边: {label} ({factor_id}){RESET}\n")
    
    fe = kg.get_factor_edges(factor_id)
    incoming = fe.get('incoming', [])
    outgoing = fe.get('outgoing', [])
    
    if incoming:
        print(f"  {BOLD}受以下因子影响（入边）:{RESET}")
        for e in sorted(incoming, key=lambda x: -x.get('strength_score', 0)):
            sign = '+' if e['sign'] == '+' else ('-' if e['sign'] == '-' else '?')
            src_node = kg.get_factor(e['source_factor_id'])
            src_c = PRIMARY_COLORS.get(src_node.get('primary_factor', ''), '') if src_node else ''
            support = len(e.get('supporting_atom_ids', []))
            print(f"    {src_c}{e['source_factor_label']}{RESET} {BOLD}{sign}{RESET} (强度={e['strength_score']}, 滞后={e['lag']}, 证据={support}条)")
            if e.get('mechanism'):
                print(f"      {DIM}{e['mechanism']}{RESET}")
    
    if outgoing:
        print(f"\n  {BOLD}影响以下因子（出边）:{RESET}")
        for e in sorted(outgoing, key=lambda x: -x.get('strength_score', 0)):
            sign = '+' if e['sign'] == '+' else ('-' if e['sign'] == '-' else '?')
            tgt_node = kg.get_factor(e['target_factor_id'])
            tgt_c = PRIMARY_COLORS.get(tgt_node.get('primary_factor', ''), '') if tgt_node else ''
            support = len(e.get('supporting_atom_ids', []))
            print(f"    {BOLD}{sign}{RESET} → {tgt_c}{e['target_factor_label']}{RESET} (强度={e['strength_score']}, 滞后={e['lag']}, 证据={support}条)")
            if e.get('mechanism'):
                print(f"      {DIM}{e['mechanism']}{RESET}")
    
    if not incoming and not outgoing:
        print("  (无直接关联边)")
    print()


def cmd_list(kg, filter_pf=None):
    """列出所有因子，可按一级因子筛选"""
    nodes = kg.ontology.get('nodes', [])
    
    if filter_pf:
        # 根据别名或全名匹配
        matched_pf = None
        for pf in PRIMARY_ORDER:
            if filter_pf in pf or pf in filter_pf:
                matched_pf = pf
                break
        if matched_pf:
            nodes = [n for n in nodes if n.get('primary_factor') == matched_pf]
            print(f"\n  {BOLD}{matched_pf} ({len(nodes)}个因子):{RESET}\n")
        else:
            print(f"\n  ⚠ 未找到一级因子 '{filter_pf}'")
            print(f"  可用: {' | '.join(PRIMARY_ORDER)}")
            return
    else:
        print(f"\n  {BOLD}全部因子 ({len(nodes)}个):{RESET}\n")
    
    current_pf = None
    for node in nodes:
        pf = node.get('primary_factor', '未知')
        if filter_pf is None and pf != current_pf:
            current_pf = pf
            c = PRIMARY_COLORS.get(pf, '')
            print(f"\n  {c}{BOLD}═══ {pf} ═══{RESET}")
        
        fid = node['factor_id']
        label = node['factor_label']
        level = node.get('level', '?')
        pf = node.get('primary_factor', '')
        c = PRIMARY_COLORS.get(pf, '')
        
        # 入边/出边统计
        fe = kg.get_factor_edges(fid)
        in_cnt = len(fe.get('incoming', []))
        out_cnt = len(fe.get('outgoing', []))
        edge_mark = f" {DIM}[→{in_cnt} ←{out_cnt}]{RESET}" if in_cnt or out_cnt else ""
        
        print(f"  {c}{fid}{RESET} {label}{edge_mark}")
    print()


def cmd_stats(kg):
    """因果图谱统计"""
    nodes = kg.ontology.get('nodes', [])
    edges = kg.edges
    atoms = kg.atoms
    
    print(f"""
  {BOLD}📊 因果图谱统计{RESET}
  ─────────────────────────────────────
  因子节点:   {len(nodes)} 个
  ├─ 基本面因子:    {len([n for n in nodes if n['primary_factor']=='基本面因子'])} 个
  ├─ 政策面因子:    {len([n for n in nodes if n['primary_factor']=='政策面因子'])} 个
  ├─ 流动性因子:    {len([n for n in nodes if n['primary_factor']=='流动性因子'])} 个
  ├─ 市场情绪因子:  {len([n for n in nodes if n['primary_factor']=='市场情绪因子'])} 个
  └─ 机构行为因子:  {len([n for n in nodes if n['primary_factor']=='机构行为因子'])} 个

  因果边:     {len(edges)} 条
  ├─ 已审核:     {len([e for e in edges if e.get('review_status')=='已审核'])} 条
  ├─ 待审核:     {len([e for e in edges if e.get('review_status')=='待审核'])} 条
  └─ 候选:       {len([e for e in edges if '候选' in e.get('review_status','')])} 条
  
  观点原子:   {len(atoms)} 个

  连通性:
  ├─ 有入边的因子: {len(set(e['target_factor_id'] for e in edges))} 个
  ├─ 有出边的因子: {len(set(e['source_factor_id'] for e in edges))} 个
  └─ 根因(入度=0): {len(set(n['factor_id'] for n in nodes) - set(e['target_factor_id'] for e in edges))} 个
""")


def interactive_mode(kg):
    """交互式模式"""
    print_banner()
    print_help()
    
    while True:
        try:
            cmd_line = input(f"{BOLD}causal>{RESET} ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\n  再见！")
            break
        
        if not cmd_line:
            continue
        
        parts = cmd_line.split()
        cmd = parts[0].lower()
        args = parts[1:]
        
        if cmd in ('quit', 'exit', 'q'):
            print("  再见！")
            break
        
        elif cmd == 'help':
            print_help()
        
        elif cmd == 'search':
            if not args:
                print("  用法: search <关键词>")
                continue
            cmd_search(kg, ' '.join(args))
        
        elif cmd == 'info':
            if not args:
                print("  用法: info <因子ID>")
                continue
            cmd_info(kg, args[0])
        
        elif cmd == 'trace':
            depth = int(args[1]) if len(args) > 1 and args[1].isdigit() else 3
            fid = args[0]
            cmd_trace(kg, fid, depth)
        
        elif cmd == 'forward':
            depth = int(args[1]) if len(args) > 1 and args[1].isdigit() else 3
            fid = args[0]
            cmd_forward(kg, fid, depth)
        
        elif cmd == 'path':
            if len(args) < 2:
                print("  用法: path <源因子ID> <目标因子ID>")
                continue
            cmd_path(kg, args[0], args[1])
        
        elif cmd == 'roots':
            depth = int(args[1]) if len(args) > 1 and args[1].isdigit() else 3
            fid = args[0]
            cmd_roots(kg, fid, depth)
        
        elif cmd == 'summary':
            depth = int(args[1]) if len(args) > 1 and args[1].isdigit() else 2
            fid = args[0]
            cmd_summary(kg, fid, depth)
        
        elif cmd == 'edges':
            if not args:
                print("  用法: edges <因子ID>")
                continue
            cmd_edges(kg, args[0])
        
        elif cmd == 'list':
            cmd_list(kg, ' '.join(args) if args else None)
        
        elif cmd == 'stats':
            cmd_stats(kg)
        
        else:
            print(f"  未知命令: {cmd}")
            print("  输入 help 查看可用命令")
    
    # 恢复终端颜色
    print(f"{RESET}", end='')


def batch_mode(kg, args):
    """命令行参数模式"""
    if args[0] == '--help' or args[0] == '-h':
        print(__doc__)
        return
    
    if args[0] == '--search' or args[0] == '-s':
        cmd_search(kg, ' '.join(args[1:]))
    elif args[0] == '--factor' or args[0] == '-f':
        cmd_info(kg, args[1])
    elif args[0] == '--trace' or args[0] == '-t':
        depth = int(args[2]) if len(args) > 2 and args[2].isdigit() else 3
        cmd_trace(kg, args[1], depth)
    elif args[0] == '--forward' or args[0] == '-fw':
        depth = int(args[2]) if len(args) > 2 and args[2].isdigit() else 3
        cmd_forward(kg, args[1], depth)
    elif args[0] == '--path' or args[0] == '-p':
        if len(args) < 3:
            print("用法: python causal_cli.py --path <源ID> <目标ID>")
            return
        cmd_path(kg, args[1], args[2])
    elif args[0] == '--roots' or args[0] == '-r':
        depth = int(args[2]) if len(args) > 2 and args[2].isdigit() else 3
        cmd_roots(kg, args[1], depth)
    elif args[0] == '--summary' or args[0] == '-sm':
        depth = int(args[2]) if len(args) > 2 and args[2].isdigit() else 2
        cmd_summary(kg, args[1], depth)
    elif args[0] == '--edges' or args[0] == '-e':
        cmd_edges(kg, args[1])
    elif args[0] == '--list' or args[0] == '-l':
        cmd_list(kg, args[1] if len(args) > 1 else None)
    elif args[0] == '--stats':
        cmd_stats(kg)
    else:
        print(f"未知参数: {args[0]}")
        print(__doc__)


if __name__ == '__main__':
    kg = KnowledgeGraph()
    
    if len(sys.argv) > 1:
        batch_mode(kg, sys.argv[1:])
    else:
        interactive_mode(kg)
