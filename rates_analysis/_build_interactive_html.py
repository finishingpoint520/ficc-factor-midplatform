"""
构建交互式因果图 HTML（vis.js 动态网络）
将所有数据嵌入 HTML，单文件无依赖
"""
import json
from pathlib import Path

BASE = Path(__file__).parent

with open(BASE / "_interactive_data.json", "r", encoding="utf-8") as f:
    data = json.load(f)

nodes = data["nodes"]
edges = data["edges"]

# 颜色方案
COLORS = {
    "基本面因子":   {"bg": "#FFF3E0", "border": "#E65100", "highlight": "#BF360C", "text": "#333"},
    "政策面因子":   {"bg": "#E3F2FD", "border": "#1565C0", "highlight": "#0D47A1", "text": "#333"},
    "流动性因子":   {"bg": "#E8F5E9", "border": "#2E7D32", "highlight": "#1B5E20", "text": "#333"},
    "市场情绪因子": {"bg": "#FCE4EC", "border": "#C62828", "highlight": "#B71C1C", "text": "#333"},
    "机构行为因子": {"bg": "#F3E5F5", "border": "#6A1B9A", "highlight": "#4A148C", "text": "#333"},
    "市场数据输出": {"bg": "#FFF8E1", "border": "#D84315", "highlight": "#BF360C", "text": "#333"},
    "未知":        {"bg": "#F5F5F5", "border": "#757575", "highlight": "#616161", "text": "#333"},
}

# 检查哪些边引用了不存在的节点
all_edge_nodes = set()
for e in edges:
    all_edge_nodes.add(e["source"])
    all_edge_nodes.add(e["target"])
missing_nodes = all_edge_nodes - set(nodes.keys())
if missing_nodes:
    print(f"WARNING: 以下节点在边中存在但本体库中没有: {missing_nodes}")
    # 补充缺失节点
    for mn in missing_nodes:
        # 从边数据推断一级因子
        inferred_primary = "未知"
        for e in edges:
            if e["source"] == mn:
                inferred_primary = e["source_primary"]
                break
            if e["target"] == mn:
                inferred_primary = e["target_primary"]
                break
        nodes[mn] = {
            "label": mn.split("_")[-1] if "_" in mn else mn,
            "primary": inferred_primary,
            "appearance_count": 0,
            "meeting_count": 0,
            "cooccurrence_count": 0,
        }
    print(f"已补充 {len(missing_nodes)} 个缺失节点")

# 构建 FactorID -> visID 映射
FID_TO_VISID = {}
fid_order = list(nodes.keys())
for i, fid in enumerate(fid_order):
    FID_TO_VISID[fid] = str(i + 1)

# 构建 vis.js nodes
vis_nodes = []
node_id_map = {}  # 连续数字ID -> 原始factor_id
idx = 0
fid_order = list(nodes.keys())
for fid in fid_order:
    n = nodes[fid]
    idx += 1
    node_id_map[str(idx)] = fid
    pc = COLORS.get(n["primary"], COLORS["未知"])
    size = 15 + min(n.get("cooccurrence_count", 0) * 0.8, 35)
    vis_nodes.append({
        "id": str(idx),
        "label": n["label"],
        "title": f"<b>{n['label']}</b><br>ID: {fid}<br>一级因子: {n['primary']}<br>纪要出现: {n.get('cooccurrence_count',0)}次",
        "group": n["primary"],
        "color": {
            "background": pc["bg"],
            "border": pc["border"],
            "highlight": {"background": pc["highlight"], "border": pc["border"]}
        },
        "size": size,
        "font": {"size": 11, "face": "Microsoft YaHei, SimHei, sans-serif", "color": pc["text"]},
        "shape": "dot",
        "borderWidth": 2,
        "borderWidthSelected": 3,
    })

# 构建 vis.js edges
vis_edges = []
for e in edges:
    # 找到连续ID
    src_idx = FID_TO_VISID.get(e["source"])
    tgt_idx = FID_TO_VISID.get(e["target"])
    if not src_idx or not tgt_idx:
        continue
    
    # 强度对应宽度
    if e["strength"] == "strong":
        width = 4
        opacity = "0.85"
    elif e["strength"] == "medium":
        width = 2.5
        opacity = "0.55"
    else:
        width = 1
        opacity = "0.30"
    
    # 颜色
    color = COLORS.get(e["source_primary"], COLORS["未知"])["border"]
    
    # 线型 - 已审核实线，待审核虚线
    dashes = False
    if e["review_status"] == "待审核":
        dashes = [6, 4]
    elif e["review_status"] == "候选-待人工审核":
        dashes = [10, 6]
    
    # 箭头符号表示sign
    sign_label = ""
    if e["sign"] == "+":
        sign_label = "pos +"
    elif e["sign"] == "-":
        sign_label = "neg -"
    
    title_parts = []
    title_parts.append(f"<b>{e['source_label']} → {e['target_label']}</b>")
    title_parts.append(f"强度: {e['strength_score']} ({e['strength']})")
    title_parts.append(f"符号: {e['sign']} | 时滞: {e['lag']}")
    title_parts.append(f"证据支撑: {e['support_count']}条")
    title_parts.append(f"审核状态: {e['review_status']}")
    title_parts.append(f"传导机制: {e['mechanism']}")
    if e.get("conditions"):
        title_parts.append(f"条件: {e['conditions']}")
    
    vis_edges.append({
        "from": str(src_idx),
        "to": str(tgt_idx),
        "width": width,
        "color": {
            "color": color,
            "opacity": float(opacity),
            "highlight": color,
        },
        "title": "<br>".join(title_parts),
        "dashes": dashes,
        "arrows": {
            "to": {
                "enabled": True,
                "type": "arrow",
                "scaleFactor": 0.8
            }
        },
        "label": sign_label,
        "font": {
            "size": 9,
            "color": "#888",
            "strokeWidth": 2,
            "strokeColor": "#fff",
            "face": "monospace"
        },
        "smooth": {
            "type": "curvedCW",
            "roundness": 0.15
        }
    })

# 构建 groups 配置
groups_config = {}
for p_name in ["基本面因子", "政策面因子", "流动性因子", "市场情绪因子", "机构行为因子", "未知"]:
    if p_name in COLORS:
        groups_config[p_name] = {
            "shape": "dot",
            "color": {
                "background": COLORS[p_name]["bg"],
                "border": COLORS[p_name]["border"],
                "highlight": {"background": COLORS[p_name]["highlight"], "border": COLORS[p_name]["border"]}
            },
            "borderWidth": 2,
        }

# 统计
total_nodes = len(vis_nodes)
total_edges = len(vis_edges)
reviewed = sum(1 for e in edges if e["review_status"] == "已审核")
pending = sum(1 for e in edges if e["review_status"] == "待审核")
candidate = sum(1 for e in edges if e["review_status"] == "候选-待人工审核")
strong = sum(1 for e in edges if e["strength"] == "strong")

# 构建 HTML
html = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>债市五因子 - 因果图谱交互看板</title>
<script type="text/javascript" src="https://unpkg.com/vis-network@9.1.6/dist/vis-network.min.js"></script>
<link href="https://unpkg.com/vis-network@9.1.6/dist/dist/vis-network.min.css" rel="stylesheet" type="text/css" />
<style>
* {{ margin: 0; padding: 0; box-sizing: border-box; }}
body {{ font-family: 'Microsoft YaHei', 'PingFang SC', -apple-system, sans-serif; background: #f5f6fa; color: #333; }}
.header {{ background: linear-gradient(135deg, #1a237e 0%, #283593 100%); color: white; padding: 16px 28px; display: flex; align-items: center; justify-content: space-between; flex-wrap: wrap; gap: 10px; }}
.header h1 {{ font-size: 20px; font-weight: 600; letter-spacing: 1px; }}
.header .stats {{ font-size: 13px; opacity: 0.85; }}
.header .stats span {{ display: inline-block; margin-left: 16px; }}
.layout {{ display: flex; height: calc(100vh - 60px); }}
.toolbar {{ width: 300px; min-width: 300px; background: white; border-right: 1px solid #e0e0e0; padding: 16px; overflow-y: auto; display: flex; flex-direction: column; gap: 12px; }}
.toolbar-section {{ background: #fafafa; border-radius: 8px; padding: 14px; }}
.toolbar-section h3 {{ font-size: 14px; font-weight: 600; margin-bottom: 10px; color: #333; border-bottom: 2px solid #e8eaf6; padding-bottom: 6px; }}
.toolbar-section .btn-group {{ display: flex; gap: 6px; flex-wrap: wrap; }}
.toolbar-section button {{ padding: 6px 12px; border: 1px solid #ccc; border-radius: 4px; background: white; cursor: pointer; font-size: 12px; transition: all 0.2s; font-family: inherit; }}
.toolbar-section button:hover {{ background: #e8eaf6; border-color: #7986cb; }}
.toolbar-section button.active {{ background: #283593; color: white; border-color: #283593; }}
.toolbar-section select {{ width: 100%; padding: 6px; border: 1px solid #ccc; border-radius: 4px; font-size: 12px; font-family: inherit; }}
.toolbar-section input[type="text"] {{ width: 100%; padding: 6px 8px; border: 1px solid #ccc; border-radius: 4px; font-size: 12px; font-family: inherit; }}
.detail-panel {{ background: #fff; border-radius: 8px; padding: 14px; flex-grow: 1; overflow-y: auto; max-height: 300px; font-size: 13px; line-height: 1.6; }}
.detail-panel .empty {{ color: #999; text-align: center; padding: 30px 0; }}
.detail-panel .item {{ padding: 6px 0; border-bottom: 1px dashed #eee; }}
.detail-panel .item:last-child {{ border-bottom: none; }}
.detail-panel .item .label {{ color: #666; font-size: 11px; }}
.detail-panel .item .val {{ color: #333; font-weight: 500; }}
.graph-container {{ flex: 1; position: relative; background: #fafbfc; }}
#network {{ width: 100%; height: 100%; }}
.legend {{ position: absolute; bottom: 16px; left: 16px; background: rgba(255,255,255,0.95); border-radius: 8px; padding: 10px 14px; font-size: 12px; box-shadow: 0 2px 8px rgba(0,0,0,0.1); line-height: 1.8; }}
.legend .row {{ display: flex; align-items: center; gap: 8px; }}
.legend .dot {{ width: 12px; height: 12px; border-radius: 50%; display: inline-block; }}
.legend .line {{ width: 24px; height: 3px; display: inline-block; border-radius: 2px; }}
.legend .dash-line {{ border-top: 3px dashed #666; width: 24px; display: inline-block; }}
.badge {{ display: inline-block; padding: 1px 6px; border-radius: 3px; font-size: 11px; color: white; }}
.badge-strong {{ background: #283593; }}
.badge-reviewed {{ background: #2e7d32; }}
.badge-pending {{ background: #e65100; }}
@media (max-width: 768px) {{ .layout {{ flex-direction: column; }} .toolbar {{ width: 100%; min-width: auto; max-height: 40vh; border-right: none; border-bottom: 1px solid #e0e0e0; }} }}
</style>
</head>
<body>
<div class="header">
  <h1>五因子因果图谱交互看板</h1>
  <div class="stats">
    节点: <span class="badge" style="background:#283593">{total_nodes}</span>
    因果边: <span class="badge" style="background:#e65100">{total_edges}</span>
    强: <span class="badge badge-strong">{strong}</span>
    已审核: <span class="badge badge-reviewed">{reviewed}</span>
    待审: <span class="badge badge-pending">{pending}</span>
  </div>
</div>
<div class="layout">
  <div class="toolbar">
    <div class="toolbar-section">
      <h3>跳转至因子</h3>
      <select id="focusSelect" onchange="focusNode(this.value)">
        <option value="">-- 选择因子 --</option>
"""
# 按一级因子分组列出节点
grouped_nodes = {}
for fid, n in nodes.items():
    primary = n["primary"]
    grouped_nodes.setdefault(primary, []).append((fid, n["label"]))
for p in ["基本面因子", "政策面因子", "流动性因子", "市场情绪因子", "机构行为因子"]:
    if p in grouped_nodes:
        for fid, label in grouped_nodes[p]:
            idx = FID_TO_VISID.get(fid)
            if idx:
                html += f'        <option value="{idx}">[{p[:2]}] {label}</option>\n'

html += """      </select>
    </div>

    <div class="toolbar-section">
      <h3>搜索因子</h3>
      <input type="text" id="searchInput" placeholder="输入关键词搜索..." oninput="searchNode(this.value)">
    </div>

    <div class="toolbar-section">
      <h3>视图模式</h3>
      <div class="btn-group">
        <button onclick="setViewMode('all')" id="viewAll" class="active">全量</button>
        <button onclick="setViewMode('cross')" id="viewCross">仅跨因子</button>
        <button onclick="setViewMode('strong')" id="viewStrong">仅强关系</button>
        <button onclick="setViewMode('reviewed')" id="viewReviewed">仅已审核</button>
      </div>
    </div>

    <div class="toolbar-section">
      <h3>反向溯源</h3>
      <p style="font-size:12px;color:#666;margin-bottom:6px;">选择一个目标因子，追溯所有前置原因</p>
      <select id="traceSelect" onchange="traceBackward(this.value)">
        <option value="">-- 选择要溯源的因子 --</option>
"""
for p in ["基本面因子", "政策面因子", "流动性因子", "市场情绪因子", "机构行为因子"]:
    if p in grouped_nodes:
        for fid, label in grouped_nodes[p]:
            idx = FID_TO_VISID.get(fid)
            if idx:
                html += f'        <option value="{idx}">[{p[:2]}] {label}</option>\n'

html += """      </select>
    </div>

    <div class="toolbar-section">
      <h3>正向传导</h3>
      <p style="font-size:12px;color:#666;margin-bottom:6px;">选择一个起始因子，查看它影响的所有下游</p>
      <select id="forwardSelect" onchange="traceForward(this.value)">
        <option value="">-- 选择传导起点 --</option>
"""
for p in ["基本面因子", "政策面因子", "流动性因子", "市场情绪因子", "机构行为因子"]:
    if p in grouped_nodes:
        for fid, label in grouped_nodes[p]:
            idx = FID_TO_VISID.get(fid)
            if idx:
                html += f'        <option value="{idx}">[{p[:2]}] {label}</option>\n'

html += """      </select>
    </div>

    <div class="toolbar-section">
      <h3>图例</h3>
      <div style="font-size:12px;line-height:2;">
        <div class="row"><span class="dot" style="background:#E65100"></span> 基本面因子</div>
        <div class="row"><span class="dot" style="background:#1565C0"></span> 政策面因子</div>
        <div class="row"><span class="dot" style="background:#2E7D32"></span> 流动性因子</div>
        <div class="row"><span class="dot" style="background:#C62828"></span> 市场情绪因子</div>
        <div class="row"><span class="dot" style="background:#6A1B9A"></span> 机构行为因子</div>
        <hr style="margin:4px 0">
        <div class="row"><span class="line" style="background:#283593;width:24px;"></span> 强因果</div>
        <div class="row"><span class="line" style="background:#7986cb;width:18px;"></span> 中因果</div>
        <div class="row"><span class="line" style="background:#ccc;width:12px;"></span> 弱因果</div>
        <div class="row"><span class="dash-line"></span> 待审核</div>
        <div class="row"><span style="color:#888;font-size:11px;">箭头 = 因果方向 | pos+ / neg-</span></div>
      </div>
    </div>
  </div>

  <div class="graph-container">
    <div id="network"></div>
    <div class="legend" id="detailPanel">
      <div class="empty">点击任意节点查看详情</div>
    </div>
  </div>
</div>

<script>
// ========== 数据 ==========
// 每个节点的连续ID到原始factor_id的映射
const NODE_ID_MAP = """ + json.dumps(node_id_map, ensure_ascii=False) + """;

// 原始数据
const RAW_DATA = """ + json.dumps(data, ensure_ascii=False) + """;

// 节点列表（连续ID）
const NODES = """ + json.dumps(vis_nodes, ensure_ascii=False) + """;

// 边列表
const EDGES = """ + json.dumps(vis_edges, ensure_ascii=False) + """;

// 分组配置
const GROUPS = """ + json.dumps(groups_config, ensure_ascii=False) + """;

// ========== 初始化 ==========
const container = document.getElementById('network');
let currentView = 'all';

// 创建数据集
let nodesDataset = new vis.DataSet(NODES);
let edgesDataset = new vis.DataSet(EDGES);

const options = {
  nodes: {
    shape: 'dot',
    size: 20,
    font: { size: 11, face: 'Microsoft YaHei, SimHei, sans-serif' },
    borderWidth: 2,
    shadow: { enabled: true, size: 4 }
  },
  edges: {
    width: 2,
    shadow: { enabled: true, size: 2 },
    smooth: { type: 'curvedCW', roundness: 0.15 }
  },
  physics: {
    enabled: true,
    solver: 'barnesHut',
    barnesHut: {
      gravitationalConstant: -6000,
      centralGravity: 0.3,
      springLength: 200,
      springConstant: 0.04,
      damping: 0.5
    },
    stabilization: { iterations: 200 }
  },
  groups: GROUPS,
  interaction: {
    hover: true,
    tooltipDelay: 200,
    navigationButtons: true,
    keyboard: true
  },
  layout: {
    improvedLayout: true
  },
  manipulation: {
    enabled: false
  }
};

const network = new vis.Network(container, { nodes: nodesDataset, edges: edgesDataset }, options);

// ========== 交互事件 ==========
function updateDetail(nodeId) {
  const panel = document.getElementById('detailPanel');
  if (!nodeId) {
    panel.innerHTML = '<div class="empty">点击任意节点查看详情</div>';
    return;
  }
  const fid = NODE_ID_MAP[nodeId];
  const node = RAW_DATA.nodes[fid];
  if (!node) { panel.innerHTML = '<div class="empty">无法找到节点信息</div>'; return; }
  
  let html = `<div style="margin-bottom:6px;"><b style="font-size:15px;">${node.label}</b> <span style="color:#888;font-size:12px;">(${fid})</span></div>`;
  html += `<div class="item"><span class="label">一级因子</span><br><span class="val">${node.primary}</span></div>`;
  html += `<div class="item"><span class="label">纪要出现频次</span><br><span class="val">${node.cooccurrence_count || 0}次</span></div>`;
  html += `<div class="item"><span class="label">一级出现次数</span><br><span class="val">${node.appearance_count || 0}次</span></div>`;
  html += `<div class="item"><span class="label">涉及会议</span><br><span class="val">${node.meeting_count || 0}场</span></div>`;
  
  // 入边（被什么影响）
  const inEdges = RAW_DATA.edges.filter(e => e.target === fid);
  if (inEdges.length > 0) {
    html += `<div style="margin-top:8px;"><b>← 前置原因 (${inEdges.length}条)</b></div>`;
    inEdges.sort((a,b) => b.support_count - a.support_count).slice(0, 6).forEach(e => {
      const s = e.strength === 'strong' ? '强' : e.strength === 'medium' ? '中' : '弱';
      html += `<div class="item">${e.source_label} → (${s}/${e.sign}/${e.lag}/${e.support_count}条)`;
      if (e.mechanism) html += `<br><span style="color:#888;font-size:11px;">${e.mechanism}</span>`;
      html += `</div>`;
    });
    if (inEdges.length > 6) html += `<div style="color:#888;font-size:11px;">... 还有${inEdges.length - 6}条</div>`;
  }
  
  // 出边（影响什么）
  const outEdges = RAW_DATA.edges.filter(e => e.source === fid);
  if (outEdges.length > 0) {
    html += `<div style="margin-top:8px;"><b>→ 下游传导 (${outEdges.length}条)</b></div>`;
    outEdges.sort((a,b) => b.support_count - a.support_count).slice(0, 6).forEach(e => {
      const s = e.strength === 'strong' ? '强' : e.strength === 'medium' ? '中' : '弱';
      html += `<div class="item">→ ${e.target_label} (${s}/${e.sign}/${e.lag}/${e.support_count}条)`;
      if (e.mechanism) html += `<br><span style="color:#888;font-size:11px;">${e.mechanism}</span>`;
      html += `</div>`;
    });
    if (outEdges.length > 6) html += `<div style="color:#888;font-size:11px;">... 还有${outEdges.length - 6}条</div>`;
  }
  
  panel.innerHTML = html;
}

network.on('click', function(params) {
  if (params.nodes.length > 0) {
    updateDetail(params.nodes[0]);
  } else {
    updateDetail(null);
  }
});

// ========== 跳转 ==========
function focusNode(idx) {
  if (!idx) return;
  network.focus(idx, { scale: 1.8, animation: { duration: 500, easingFunction: 'easeInOutQuad' } });
  network.selectNodes([idx]);
  updateDetail(idx);
}

// ========== 搜索 ==========
function searchNode(keyword) {
  if (!keyword.trim()) {
    nodesDataset.forEach(function(n) { nodesDataset.update({ id: n.id, hidden: false }); });
    return;
  }
  const kw = keyword.toLowerCase();
  nodesDataset.forEach(function(n) {
    const fid = NODE_ID_MAP[n.id];
    const node = RAW_DATA.nodes[fid];
    const match = node.label.toLowerCase().includes(kw) || 
                  fid.toLowerCase().includes(kw) ||
                  node.primary.toLowerCase().includes(kw);
    nodesDataset.update({ id: n.id, hidden: !match });
  });
}

// ========== 视图模式 ==========
function setViewMode(mode) {
  currentView = mode;
  document.querySelectorAll('.btn-group button').forEach(b => b.classList.remove('active'));
  document.getElementById('view' + mode.charAt(0).toUpperCase() + mode.slice(1)).classList.add('active');
  
  let visibleNodes = new Set();
  let visibleEdges = [];
  
  if (mode === 'all') {
    // 显示所有
    nodesDataset.forEach(n => nodesDataset.update({ id: n.id, hidden: false }));
    edgesDataset.forEach(e => edgesDataset.update({ id: e.id, hidden: false }));
    network.setOptions({ physics: true });
    return;
  }
  
  edgesDataset.forEach(function(e) {
    let show = true;
    const edgeData = EDGES.find(ed => ed.from === e.from && ed.to === e.to);
    if (!edgeData) return;
    
    // 查找原始边数据
    const rawEdgeIdx = EDGES.indexOf(edgeData);
    const rawEdge = RAW_DATA.edges[rawEdgeIdx];
    if (!rawEdge) return;
    
    if (mode === 'cross' && !rawEdge.cross) show = false;
    if (mode === 'strong' && rawEdge.strength !== 'strong') show = false;
    if (mode === 'reviewed' && rawEdge.review_status !== '已审核') show = false;
    
    if (show) {
      visibleEdges.push(e);
      visibleNodes.add(e.from);
      visibleNodes.add(e.to);
    }
  });
  
  // 更新可见性
  nodesDataset.forEach(function(n) {
    nodesDataset.update({ id: n.id, hidden: !visibleNodes.has(n.id) });
  });
  edgesDataset.forEach(function(e) {
    edgesDataset.update({ id: e.id, hidden: true });
  });
  visibleEdges.forEach(function(e) {
    edgesDataset.update({ id: e.id, hidden: false });
  });
}

// ========== 反向溯源 ==========
function traceBackward(idx) {
  if (!idx) return;
  const fid = NODE_ID_MAP[idx];
  const targetLabel = RAW_DATA.nodes[fid].label;
  
  // BFS 找所有前置路径（最多3层）
  let visited = new Set();
  let queue = [[fid, 0, []]];  // [factor_id, depth, path]
  let paths = [];
  
  while (queue.length > 0) {
    const [cur, depth, path] = queue.shift();
    if (depth >= 3) continue;
    
    const inEdges = RAW_DATA.edges.filter(e => e.target === cur);
    for (const e of inEdges) {
      const newPath = [...path, e];
      const src = e.source;
      // 检查循环（用加入前的path检查，避免e自身被误判）
      if (path.some(p => p.source === src || p.target === src)) continue;
      paths.push(newPath);
      if (!visited.has(src)) {
        visited.add(src);
        queue.push([src, depth + 1, newPath]);
      }
    }
  }
  
  // 按支撑数排序
  paths.sort((a, b) => {
    const sa = a.reduce((s, e) => s + e.support_count, 0);
    const sb = b.reduce((s, e) => s + e.support_count, 0);
    return sb - sa;
  });
  
  // 聚焦目标节点，高亮路径
  network.focus(idx, { scale: 1.5, animation: { duration: 800, easingFunction: 'easeInOutQuad' } });
  
  // 显示结果
  const panel = document.getElementById('detailPanel');
  let html = `<div style="margin-bottom:8px;"><b style="font-size:15px;color:#283593;">反向溯源: ${targetLabel}</b></div>`;
  html += `<div style="color:#666;font-size:12px;margin-bottom:8px;">找到 ${paths.length} 条前置因果路径</div>`;
  
  if (paths.length === 0) {
    html += `<div class="empty">该因子没有前置原因（或已到达根节点）</div>`;
  } else {
    html += `<div style="max-height:200px;overflow-y:auto;">`;
    paths.slice(0, 10).forEach((path, pi) => {
      const totalSupport = path.reduce((s, e) => s + e.support_count, 0);
      html += `<div style="margin-bottom:6px;padding:6px;background:#f5f5ff;border-radius:4px;">`;
      html += `<span style="font-size:11px;color:#888;">路径${pi+1} (支撑${totalSupport}条)</span><br>`;
      const steps = path.map(e => `${e.source_label}<span style="color:#e65100;font-size:10px;">→</span>`);
      steps.push(targetLabel);
      html += `<span style="font-size:12px;">${steps.join('')}</span>`;
      path.forEach(e => {
        html += `<div style="font-size:11px;color:#888;padding-left:10px;">${e.mechanism || ''}</div>`;
      });
      html += `</div>`;
    });
    html += `</div>`;
  }
  
  panel.innerHTML = html;
}

// ========== 正向传导 ==========
function traceForward(idx) {
  if (!idx) return;
  const fid = NODE_ID_MAP[idx];
  const sourceLabel = RAW_DATA.nodes[fid].label;
  
  let visited = new Set();
  let queue = [[fid, 0, []]];
  let paths = [];
  
  while (queue.length > 0) {
    const [cur, depth, path] = queue.shift();
    if (depth >= 3) continue;
    
    const outEdges = RAW_DATA.edges.filter(e => e.source === cur);
    for (const e of outEdges) {
      const newPath = [...path, e];
      const tgt = e.target;
      if (path.some(p => p.source === tgt || p.target === tgt)) continue;
      paths.push(newPath);
      if (!visited.has(tgt)) {
        visited.add(tgt);
        queue.push([tgt, depth + 1, newPath]);
      }
    }
  }
  
  paths.sort((a, b) => {
    const sa = a.reduce((s, e) => s + e.support_count, 0);
    const sb = b.reduce((s, e) => s + e.support_count, 0);
    return sb - sa;
  });
  
  network.focus(idx, { scale: 1.5, animation: { duration: 800, easingFunction: 'easeInOutQuad' } });
  
  const panel = document.getElementById('detailPanel');
  let html = `<div style="margin-bottom:8px;"><b style="font-size:15px;color:#2e7d32;">正向传导: ${sourceLabel}</b></div>`;
  html += `<div style="color:#666;font-size:12px;margin-bottom:8px;">找到 ${paths.length} 条下游传导路径</div>`;
  
  if (paths.length === 0) {
    html += `<div class="empty">该因子没有下游传导路径</div>`;
  } else {
    html += `<div style="max-height:200px;overflow-y:auto;">`;
    paths.slice(0, 10).forEach((path, pi) => {
      const totalSupport = path.reduce((s, e) => s + e.support_count, 0);
      html += `<div style="margin-bottom:6px;padding:6px;background:#f0fff4;border-radius:4px;">`;
      html += `<span style="font-size:11px;color:#888;">路径${pi+1} (支撑${totalSupport}条)</span><br>`;
      const steps = [sourceLabel];
      path.forEach(e => steps.push(`<span style="color:#2e7d32;font-size:10px;">→</span>${e.target_label}`));
      html += `<span style="font-size:12px;">${steps.join('')}</span>`;
      path.forEach(e => {
        html += `<div style="font-size:11px;color:#888;padding-left:10px;">${e.mechanism || ''}</div>`;
      });
      html += `</div>`;
    });
    html += `</div>`;
  }
  
  panel.innerHTML = html;
}
</script>
</body>
</html>
"""

with open(BASE / "causal_interactive.html", "w", encoding="utf-8") as f:
    f.write(html)

print(f"Done! Saved to {BASE / 'causal_interactive.html'}")
print(f"File size: {len(html)} bytes")
