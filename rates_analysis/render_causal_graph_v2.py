# -*- coding: utf-8 -*-
"""
渲染五因子框架因果链条图 v4（升级版）
- 基于 factor_causal_edges_v2.json（包含审核状态、内部支撑计数）
- 新增审核状态视觉区分：已审核边 vs 待审核边
- 输出两张图：全量因果图 + 跨因子因果图
"""
import json
import math
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.font_manager import FontProperties
import networkx as nx
import numpy as np

# ── 中文字体：设置 rcParams 使用系统字体 ──
plt.rcParams['font.sans-serif'] = ['Microsoft YaHei', 'SimHei', 'SimSun']  # 优先使用雅黑
plt.rcParams['axes.unicode_minus'] = False
# 字体属性（不再指定 fname，使用默认字体）
FONT_PROP = FontProperties(size=12)
FONT_PROP_TITLE = FontProperties(size=22, weight="bold")
FONT_PROP_HEADER = FontProperties(size=16, weight="bold")
FONT_PROP_SMALL = FontProperties(size=11)
FONT_PROP_NODE = FontProperties(size=10, weight="bold")
FONT_PROP_NODE_SM = FontProperties(size=9, weight="bold")

# ── 配置 ──
BASE = Path(__file__).parent
OUT_PNG_ALL = BASE / "factor_causal_graph_all_v2.png"
OUT_PNG_CROSS = BASE / "factor_causal_graph_cross_v2.png"
DPI = 150

# ── 读取数据 ──
with open(BASE / "factor_causal_edges_v2.json", "r", encoding="utf-8") as f:
    causal_v2 = json.load(f)
with open(BASE / "factor_cooccurrence.json", "r", encoding="utf-8") as f:
    cooc = json.load(f)
with open(BASE / "factor_ontology.json", "r", encoding="utf-8") as f:
    ontology = json.load(f)

# 建立因子标签 → 一级因子映射
label_to_primary = {}
for node in ontology["nodes"]:
    label = node["factor_label"]
    primary = node["primary_factor"]
    label_to_primary[label] = primary

# 修复：统一"政策预期"归属为"政策面因子"
NODE_PRIMARY_OVERRIDE = {
    "政策预期": "政策面因子",
    "央行态度": "政策面因子",
}

# 转换 v2 边为 v1 兼容格式
edges_data = []
for e in causal_v2["edges"]:
    from_label = e["source_factor_label"]
    to_label = e["target_factor_label"]
    
    # 获取一级因子（优先使用映射，否则从 ontology 取）
    from_primary = label_to_primary.get(from_label)
    to_primary = label_to_primary.get(to_label)
    if from_primary is None:
        from_primary = NODE_PRIMARY_OVERRIDE.get(from_label, "未知")
    if to_primary is None:
        to_primary = NODE_PRIMARY_OVERRIDE.get(to_label, "未知")
    
    # 强度映射
    score = e.get("strength_score", 0.5)
    if score >= 0.7:
        strength = "strong"
    elif score >= 0.4:
        strength = "medium"
    else:
        strength = "weak"
    
    # 跨因子判断
    cross = (from_primary != to_primary)
    
    # 逻辑字段（保留 v1 的 logic）
    logic = e.get("mechanism", "")
    
    # 审核状态
    review_status = e.get("review_status", "待审核")
    internal_support_count = e.get("internal_support_count", 0)
    
    edge = {
        "from": from_label,
        "to": to_label,
        "strength": strength,
        "cross": cross,
        "logic": logic,
        "from_primary": from_primary,
        "to_primary": to_primary,
        "review_status": review_status,
        "internal_support_count": internal_support_count,
        "edge_id": e["edge_id"],
        "strength_score": score,
    }
    edges_data.append(edge)

print(f"Loaded {len(edges_data)} edges from v2")

# ── 一级因子定义与颜色 ──
PRIMARY_ORDER = ["基本面因子", "政策面因子", "流动性因子", "市场情绪因子", "机构行为因子", "市场数据输出", "未知"]
PRIMARY_COLORS = {
    "基本面因子":   {"bg": "#FFF3E0", "node": "#E65100", "edge": "#FF9800", "label": "#BF360C"},
    "政策面因子":   {"bg": "#E3F2FD", "node": "#1565C0", "edge": "#42A5F5", "label": "#0D47A1"},
    "流动性因子":   {"bg": "#E8F5E9", "node": "#2E7D32", "edge": "#66BB6A", "label": "#1B5E20"},
    "市场情绪因子": {"bg": "#FCE4EC", "node": "#C62828", "edge": "#EF5350", "label": "#B71C1C"},
    "机构行为因子": {"bg": "#F3E5F5", "node": "#6A1B9A", "edge": "#AB47BC", "label": "#4A148C"},
    "市场数据输出": {"bg": "#FFF8E1", "node": "#D84315", "edge": "#FF6E40", "label": "#BF360C"},
    "未知":        {"bg": "#F5F5F5", "node": "#757575", "edge": "#9E9E9E", "label": "#616161"},
}

# ── 构建有向图 ──
G = nx.DiGraph()

node_count = {}
for item in cooc.get("factor_counts", []):
    node_count[item["factor"]] = item["count"]

for e in edges_data:
    for node_key, primary_key in [("from", "from_primary"), ("to", "to_primary")]:
        node_name = e[node_key]
        primary = e[primary_key]
        if node_name not in G:
            G.add_node(node_name, primary=primary, count=node_count.get(node_name, 0))

for e in edges_data:
    G.add_edge(e["from"], e["to"],
               strength=e["strength"],
               cross=e["cross"],
               logic=e["logic"],
               from_primary=e["from_primary"],
               to_primary=e["to_primary"],
               review_status=e["review_status"],
               internal_support_count=e["internal_support_count"],
               edge_id=e["edge_id"],
               strength_score=e["strength_score"])

print(f"Nodes: {G.number_of_nodes()}, Edges: {G.number_of_edges()}")
cross_count = sum(1 for _, _, d in G.edges(data=True) if d["cross"])
print(f"Cross-factor edges: {cross_count}")

# 审核状态统计
reviewed_count = sum(1 for _, _, d in G.edges(data=True) if d["review_status"] == "已审核")
pending_count = sum(1 for _, _, d in G.edges(data=True) if d["review_status"] == "待审核")
candidate_count = sum(1 for _, _, d in G.edges(data=True) if d["review_status"] == "候选-待人工审核")
print(f"审核状态: 已审核={reviewed_count}, 待审核={pending_count}, 候选-待人工审核={candidate_count}")

# ── 布局：网格排布，拉开间距 ──
COLUMN_SPACING = 3.0   # 列间距
ROW_SPACING = 0.9       # 行间距
X_START = 0.0
Y_CENTER = 0.0

def compute_layout(G, primary_order):
    pos = {}
    groups = {p: [] for p in primary_order}
    for node, data in G.nodes(data=True):
        groups.setdefault(data["primary"], []).append(node)
    
    # 按影响力排序（跨因子连接多的排中间）
    for p_name, nodes in groups.items():
        scores = []
        for n in nodes:
            out_c = sum(1 for _, _, d in G.out_edges(n, data=True) if d.get("cross"))
            in_c = sum(1 for _, _, d in G.in_edges(n, data=True) if d.get("cross"))
            scores.append((n, out_c * 4 + in_c * 3 + G.degree(n)))
        scores.sort(key=lambda x: -x[1])
        groups[p_name] = [n for n, s in scores]
    
    pos = {}
    for p_name in primary_order:
        nodes = groups.get(p_name, [])
        if not nodes:
            continue
        col_idx = primary_order.index(p_name)
        cx = X_START + col_idx * COLUMN_SPACING
        n = len(nodes)
        
        # 均匀纵向分布
        y_start = Y_CENTER - (n - 1) * ROW_SPACING / 2
        for i, node in enumerate(nodes):
            pos[node] = (cx, y_start + i * ROW_SPACING)
    
    return pos, groups

pos, groups = compute_layout(G, PRIMARY_ORDER)

# ── 边样式（根据强度） ──
strength_styles = {
    "strong": {"lw": 2.5, "alpha": 0.70, "zorder": 2},
    "medium": {"lw": 1.5, "alpha": 0.45, "zorder": 1},
    "weak":   {"lw": 0.8, "alpha": 0.25, "zorder": 0},
}

# 审核状态样式
reviewed_style = {"linestyle": "-", "dash_capstyle": "round"}
pending_style = {"linestyle": ":", "dash_capstyle": "round"}
candidate_style = {"linestyle": "--", "dash_capstyle": "round"}

# ── 画弧线边（增强版，支持审核状态） ──
def draw_edge(ax, x1, y1, x2, y2, color, style, is_cross, review_status, rad=0.3):
    """画一条贝塞尔曲线箭头，带审核状态样式"""
    ctrl_x = (x1 + x2) / 2
    ctrl_y = (y1 + y2) / 2 + rad
    t = np.linspace(0, 1, 60)
    bx = (1-t)**2 * x1 + 2*(1-t)*t * ctrl_x + t**2 * x2
    by = (1-t)**2 * y1 + 2*(1-t)*t * ctrl_y + t**2 * y2
    
    # 线型：跨因子实线，同因子虚线
    ls_base = "-" if is_cross else "--"
    # 审核状态叠加
    if review_status == "已审核":
        ls = "-"
    elif review_status == "待审核":
        ls = ":"
    elif review_status == "候选-待人工审核":
        ls = "--"
    else:
        ls = ls_base
    
    ax.plot(bx, by, color=color, linewidth=style["lw"],
            alpha=style["alpha"], linestyle=ls,
            zorder=style["zorder"], solid_capstyle="round")
    
    # 箭头
    ax.annotate("", xy=(x2, y2), xytext=(bx[-3], by[-3]),
                arrowprops=dict(
                    arrowstyle="->,head_width=0.35,head_length=0.18",
                    color=color, lw=style["lw"], alpha=style["alpha"],
                    connectionstyle="arc3,rad=0"),
                zorder=style["zorder"])

# ── 画节点 ──
def draw_nodes(ax, G, pos, PRIMARY_COLORS):
    for node, (x, y) in pos.items():
        primary = G.nodes[node]["primary"]
        count = G.nodes[node]["count"]
        color = PRIMARY_COLORS[primary]["node"]
        
        # 节点半径（scatter的s参数是面积）
        base_size = 1200 + count * 150
        
        # 外发光
        ax.scatter(x, y, s=base_size * 2.0, c=color, alpha=0.08, zorder=3, edgecolors="none")
        # 白底圆
        ax.scatter(x, y, s=base_size, c="white", edgecolors=color,
                   linewidths=2.5, zorder=5, alpha=0.95)
        # 内彩色圆（小一圈，做"环形"效果）
        ax.scatter(x, y, s=base_size * 0.25, c=color, alpha=0.70, zorder=6, edgecolors="none")
        
        # 标签 - 深色文字，白色背景上清晰可读
        if len(node) <= 4:
            fp = FONT_PROP_NODE
        else:
            fp = FONT_PROP_NODE_SM
        ax.text(x, y, node, ha="center", va="center",
                fontproperties=fp, color="#1A1A1A", zorder=7)

# ═══════════════════════════════════════
# 图1: 全量因果图（升级版）
# ═══════════════════════════════════════
fig, ax = plt.subplots(1, 1, figsize=(30, 18), facecolor="white")
ax.set_facecolor("white")

# 背景色块
for p_name in PRIMARY_ORDER:
    col_idx = PRIMARY_ORDER.index(p_name)
    cx = X_START + col_idx * COLUMN_SPACING
    nodes = groups.get(p_name, [])
    if not nodes:
        continue
    n = len(nodes)
    y_top = Y_CENTER + (n - 1) * ROW_SPACING / 2 + 0.6
    y_bot = Y_CENTER - (n - 1) * ROW_SPACING / 2 - 0.6
    
    rect = mpatches.FancyBboxPatch(
        (cx - 1.1, y_bot), 2.2, y_top - y_bot,
        boxstyle="round,pad=0.15",
        facecolor=PRIMARY_COLORS[p_name]["bg"],
        edgecolor=PRIMARY_COLORS[p_name]["node"],
        linewidth=1.8, alpha=0.30, zorder=0)
    ax.add_patch(rect)
    ax.text(cx, y_top + 0.35, p_name, ha="center", va="center",
            fontproperties=FONT_PROP_HEADER,
            color=PRIMARY_COLORS[p_name]["label"], zorder=10)

# 画边
for u, v, data in G.edges(data=True):
    strength = data["strength"]
    cross = data["cross"]
    review_status = data["review_status"]
    style = strength_styles[strength]
    
    if cross:
        color = PRIMARY_COLORS[data["from_primary"]]["edge"]
    else:
        color = "#BBBBBB"
    
    x1, y1 = pos[u]
    x2, y2 = pos[v]
    dy = y2 - y1
    rad = 0.25 * (1 if dy >= 0 else -1) if cross else 0.08
    draw_edge(ax, x1, y1, x2, y2, color, style, cross, review_status, rad)

draw_nodes(ax, G, pos, PRIMARY_COLORS)

# 图例
legend_elements = [
    mpatches.Patch(facecolor=PRIMARY_COLORS[p]["node"], edgecolor="none",
                   label=p, alpha=0.8)
    for p in PRIMARY_ORDER
]
legend_elements += [
    mpatches.Patch(facecolor="none", edgecolor="#333", linewidth=2.5, label="Strong"),
    mpatches.Patch(facecolor="none", edgecolor="#333", linewidth=1.5, label="Medium"),
    mpatches.Patch(facecolor="none", edgecolor="#AAA", linewidth=0.8,
                   linestyle="--", label="Weak / 同因子"),
    mpatches.Patch(facecolor="none", edgecolor="#333", linewidth=1.5,
                   linestyle="-", label="已审核"),
    mpatches.Patch(facecolor="none", edgecolor="#333", linewidth=1.5,
                   linestyle=":", label="待审核"),
    mpatches.Patch(facecolor="none", edgecolor="#333", linewidth=1.5,
                   linestyle="--", label="候选边"),
]
ax.legend(handles=legend_elements, loc="upper left", fontsize=10,
          framealpha=0.9, edgecolor="#CCC", ncol=3,
          prop=FontProperties(size=10))

ax.set_title("中国债券市场利率策略 - 五因子框架因果链条图 (v2 升级版)",
             fontproperties=FONT_PROP_TITLE, pad=25)

# 计算布局范围
all_x = [p[0] for p in pos.values()]
all_y = [p[1] for p in pos.values()]
ax.text((min(all_x) + max(all_x)) / 2, min(all_y) - 1.5,
        f"节点大小 = 会议纪要出现频次 | 箭头 = 因果传导方向 | "
        f"共 {G.number_of_edges()} 条因果边, {G.number_of_nodes()} 个二级因子 | "
        f"已审核: {reviewed_count}, 待审核: {pending_count}, 候选: {candidate_count}",
        ha="center", va="center", fontproperties=FONT_PROP_SMALL, color="#666")

x_margin = 2.0
y_margin = 2.5
ax.set_xlim(min(all_x) - x_margin, max(all_x) + x_margin)
ax.set_ylim(min(all_y) - y_margin, max(all_y) + y_margin + 1.0)
ax.axis("off")
plt.tight_layout()
fig.savefig(OUT_PNG_ALL, dpi=DPI, bbox_inches="tight",
            facecolor="white", edgecolor="none")
print(f"Saved: {OUT_PNG_ALL}")
plt.close()

# ═══════════════════════════════════════
# 图2: 跨因子因果传导图（升级版）
# ═══════════════════════════════════════
fig2, ax2 = plt.subplots(1, 1, figsize=(28, 16), facecolor="white")
ax2.set_facecolor("white")

for p_name in PRIMARY_ORDER:
    col_idx = PRIMARY_ORDER.index(p_name)
    cx = X_START + col_idx * COLUMN_SPACING
    nodes = groups.get(p_name, [])
    if not nodes:
        continue
    n = len(nodes)
    y_top = Y_CENTER + (n - 1) * ROW_SPACING / 2 + 0.6
    y_bot = Y_CENTER - (n - 1) * ROW_SPACING / 2 - 0.6
    
    rect = mpatches.FancyBboxPatch(
        (cx - 1.1, y_bot), 2.2, y_top - y_bot,
        boxstyle="round,pad=0.15",
        facecolor=PRIMARY_COLORS[p_name]["bg"],
        edgecolor=PRIMARY_COLORS[p_name]["node"],
        linewidth=1.8, alpha=0.30, zorder=0)
    ax2.add_patch(rect)
    ax2.text(cx, y_top + 0.35, p_name, ha="center", va="center",
             fontproperties=FONT_PROP_HEADER,
             color=PRIMARY_COLORS[p_name]["label"], zorder=10)

# 只画跨因子边
drawn_cross = 0
for u, v, data in G.edges(data=True):
    if not data["cross"]:
        continue
    drawn_cross += 1
    strength = data["strength"]
    review_status = data["review_status"]
    style = strength_styles[strength]
    color = PRIMARY_COLORS[data["from_primary"]]["edge"]
    
    x1, y1 = pos[u]
    x2, y2 = pos[v]
    dy = y2 - y1
    rad = 0.35 * (1 if dy >= 0 else -1)
    draw_edge(ax2, x1, y1, x2, y2, color, style, True, review_status, rad)

draw_nodes(ax2, G, pos, PRIMARY_COLORS)

strong_cross = sum(1 for _, _, d in G.edges(data=True) if d["strength"] == "strong" and d["cross"])
medium_cross = sum(1 for _, _, d in G.edges(data=True) if d["strength"] == "medium" and d["cross"])
weak_cross = sum(1 for _, _, d in G.edges(data=True) if d["strength"] == "weak" and d["cross"])

legend2 = [
    mpatches.Patch(facecolor=PRIMARY_COLORS[p]["node"], edgecolor="none",
                   label=p, alpha=0.8)
    for p in PRIMARY_ORDER
]
legend2 += [
    mpatches.Patch(facecolor="none", edgecolor="#333", linewidth=2.5,
                   label=f"Strong ({strong_cross})"),
    mpatches.Patch(facecolor="none", edgecolor="#333", linewidth=1.5,
                   label=f"Medium ({medium_cross})"),
    mpatches.Patch(facecolor="none", edgecolor="#333", linewidth=0.8,
                   label=f"Weak ({weak_cross})"),
    mpatches.Patch(facecolor="none", edgecolor="#333", linewidth=1.5,
                   linestyle="-", label="已审核"),
    mpatches.Patch(facecolor="none", edgecolor="#333", linewidth=1.5,
                   linestyle=":", label="待审核"),
    mpatches.Patch(facecolor="none", edgecolor="#333", linewidth=1.5,
                   linestyle="--", label="候选边"),
]
ax2.legend(handles=legend2, loc="upper left", fontsize=10,
           framealpha=0.9, edgecolor="#CCC", ncol=3,
           prop=FontProperties(size=10))

ax2.set_title("五因子框架 - 跨因子因果传导图 (v2 升级版)",
              fontproperties=FontProperties(size=20, weight="bold"), pad=25)
ax2.text((min(all_x) + max(all_x)) / 2, min(all_y) - 1.5,
         f"仅展示跨一级因子的因果边 ({drawn_cross} 条) | 节点大小 = 出现频次 | 箭头 = 因果方向 | "
         f"已审核: {reviewed_count}, 待审核: {pending_count}, 候选: {candidate_count}",
         ha="center", va="center", fontproperties=FONT_PROP_SMALL, color="#666")

ax2.set_xlim(min(all_x) - x_margin, max(all_x) + x_margin)
ax2.set_ylim(min(all_y) - y_margin, max(all_y) + y_margin + 1.0)
ax2.axis("off")
plt.tight_layout()
fig2.savefig(OUT_PNG_CROSS, dpi=DPI, bbox_inches="tight",
             facecolor="white", edgecolor="none")
print(f"Saved: {OUT_PNG_CROSS}")
plt.close()

print(f"\nDone! Output:")
print(f"  1. {OUT_PNG_ALL.name} - Full causal graph v2 ({G.number_of_edges()} edges)")
print(f"  2. {OUT_PNG_CROSS.name} - Cross-factor causal graph v2 ({drawn_cross} edges)")
print(f"审核状态: 已审核={reviewed_count}, 待审核={pending_count}, 候选={candidate_count}")