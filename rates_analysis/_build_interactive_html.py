"""
构建交互式因果图 HTML（vis.js 动态网络）
将所有数据嵌入 HTML，单文件无依赖（包括 vis-network.js 也内嵌）
"""
import json
import urllib.request
from pathlib import Path

BASE = Path(__file__).parent

VIS_NETWORK_URL = "https://unpkg.com/vis-network@9.1.6/dist/vis-network.min.js"
VIS_NETWORK_LOCAL = BASE / "_vis_network_cache.js"


def get_vis_network_js() -> str:
    """获取 vis-network.min.js，优先用本地缓存，否则从 CDN 下载"""
    if VIS_NETWORK_LOCAL.exists():
        print(f"Using cached vis-network.js ({VIS_NETWORK_LOCAL.stat().st_size} bytes)")
        return VIS_NETWORK_LOCAL.read_text(encoding="utf-8")
    print(f"Downloading vis-network.min.js from {VIS_NETWORK_URL} ...")
    try:
        req = urllib.request.Request(VIS_NETWORK_URL, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=30) as resp:
            js = resp.read().decode("utf-8")
        VIS_NETWORK_LOCAL.write_text(js, encoding="utf-8")
        print(f"Downloaded and cached ({len(js)} bytes)")
        return js
    except Exception as e:
        raise RuntimeError(f"Failed to download vis-network.min.js: {e}\n"
                           "Please download manually and save to _vis_network_cache.js")


# 预加载 vis-network.js（构建时即下载/缓存）
VIS_JS_EMBED = get_vis_network_js()

# 加载因子图谱数据
with open(BASE / "_interactive_data.json", "r", encoding="utf-8") as f:
    data = json.load(f)

nodes = data["nodes"]
edges = data["edges"]

# 加载发言人画像数据
speaker_personas_raw = (BASE / "speaker_personas.js").read_text(encoding="utf-8").strip()
if speaker_personas_raw.startswith("const SPEAKER_PERSONAS = "):
    speaker_personas_raw = speaker_personas_raw[len("const SPEAKER_PERSONAS = "):]
speaker_personas = json.loads(speaker_personas_raw.rstrip(";").strip())
print(f"Loaded {speaker_personas['total_speakers']} speaker personas")

# 加载发言人→边数据（用于按发言人高亮因果链）
speaker_edge_raw = (BASE / "speaker_edge_data.js").read_text(encoding="utf-8").strip()
if speaker_edge_raw.startswith("const SPEAKER_EDGE_DATA = "):
    speaker_edge_raw = speaker_edge_raw[len("const SPEAKER_EDGE_DATA = "):]
speaker_edge_data = json.loads(speaker_edge_raw.rstrip(";").strip())
print(f"Loaded speaker-edge data for {len(speaker_edge_data)} speakers/groups")

# 加载边→发言人原文索引
edge_speaker_index = json.loads((BASE / "edge_speaker_index.json").read_text(encoding="utf-8"))
print(f"Loaded edge-speaker index with {len(edge_speaker_index)} edges")

# 加载因子的 visID 映射（后续填充）

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

# 因子ID前缀 → 一级因子映射
PREFIX_TO_PRIMARY = {
    "FD": "基本面因子", "PL": "政策面因子", "LQ": "流动性因子",
    "MS": "市场情绪因子", "IB": "机构行为因子", "MD": "市场数据输出",
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
        # 从因子ID前缀推断一级因子
        prefix = mn.split("_")[0] if "_" in mn else "XX"
        inferred_primary = PREFIX_TO_PRIMARY.get(prefix, "未知")
        # 从边数据中获取正确的 label
        inferred_label = mn  # 默认用 factor_id
        for e in edges:
            if e["source"] == mn and e.get("source_label"):
                inferred_label = e["source_label"]
                break
            if e["target"] == mn and e.get("target_label"):
                inferred_label = e["target_label"]
                break
        nodes[mn] = {
            "label": inferred_label,
            "primary": inferred_primary,
            "appearance_count": 0,
            "meeting_count": 0,
            "cooccurrence_count": 0,
        }
        print(f"  补充节点 {mn}: label={inferred_label}, primary={inferred_primary}")
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
<script type="text/javascript">
// vis-network@9.1.6 (embedded for offline use, no CDN dependency)
{VIS_JS_EMBED}
</script>
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
/* 发言人画像相关 */
.persona-card {{ background: #fff; border: 1px solid #e0e0e0; border-radius: 8px; padding: 14px; margin-top: 6px; font-size: 12px; line-height: 1.7; }}
.persona-card h4 {{ font-size: 14px; font-weight: 600; margin-bottom: 8px; color: #1a237e; border-bottom: 1px solid #e8eaf6; padding-bottom: 4px; }}
.persona-card .persona-stat {{ display: inline-block; margin-right: 12px; margin-bottom: 4px; }}
.persona-card .persona-stat .label {{ color: #888; font-size: 11px; }}
.persona-card .persona-stat .val {{ font-weight: 600; color: #333; }}
.persona-bar {{ height: 8px; border-radius: 4px; background: #e8eaf6; overflow: hidden; margin: 2px 0; }}
.persona-bar-fill {{ height: 100%; border-radius: 4px; transition: width 0.3s; }}
.speaker-select {{ width: 100%; padding: 6px 8px; border: 1px solid #ccc; border-radius: 4px; font-size: 12px; font-family: inherit; cursor: pointer; }}
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
      <h3>发言人视角</h3>
      <p style="font-size:12px;color:#666;margin-bottom:6px;">选择发言人，高亮其因果链条与画像</p>
      <select id="speakerSelect" class="speaker-select" onchange="selectSpeaker(this.value)">
        <option value="">-- 选择发言人 --</option>
""" + "".join(
    f'        <option value="{s["speaker"]}">{s["speaker"]} ({s["total_claims"]}条观点, {s.get("top_factor","")})</option>\n'
    for s in sorted(speaker_personas["personas"], key=lambda x: -x["total_claims"])
) + """      </select>
      <button style="width:100%;margin-top:6px;" onclick="clearSpeakerView()">清除发言人筛选</button>
      <div id="personaCardContainer"></div>
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

// 发言人画像数据
const SPEAKER_PERSONAS = """ + json.dumps(speaker_personas, ensure_ascii=False) + """;

// 发言人→因果边映射（visID 格式，可直接用于网络高亮）
const SPEAKER_EDGE_DATA = """ + json.dumps(speaker_edge_data, ensure_ascii=False) + """;

// 因果边→发言人原文索引（key 格式: "source_factor_id→target_factor_id"）
const EDGE_SPEAKER_INDEX = """ + json.dumps(edge_speaker_index, ensure_ascii=False) + """;

// 因子ID→visID 映射（方便查找）
const FID_TO_VISID = """ + json.dumps(FID_TO_VISID, ensure_ascii=False) + """;
const VISID_TO_FID = """ + json.dumps({v: k for k, v in FID_TO_VISID.items()}, ensure_ascii=False) + """;
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

// ========== 发言人视角 ==========
const FACTOR_COLORS = {"基本面因子":"#E65100","政策面因子":"#1565C0","流动性因子":"#2E7D32","市场情绪因子":"#C62828","机构行为因子":"#6A1B9A","市场数据输出":"#D84315"};
let activeSpeaker = null;
let speakerEdgeKeySet = new Set();  // 当前发言人高亮的边 key 集合 "visFrom-visTo"

function selectSpeaker(speakerName) {
  if (!speakerName) { clearSpeakerView(); return; }
  activeSpeaker = speakerName;

  // 1. 构建该发言人关联的边集合
  const speakerEdges = SPEAKER_EDGE_DATA[speakerName] || [];
  speakerEdgeKeySet = new Set();
  const visibleNodeIds = new Set();

  speakerEdges.forEach(se => {
    const key = String(se.from) + '-' + String(se.to);
    speakerEdgeKeySet.add(key);
    visibleNodeIds.add(String(se.from));
    visibleNodeIds.add(String(se.to));
  });

  // 2. 更新节点可见性（高亮的节点增强边框，其他隐藏）
  nodesDataset.forEach(n => {
    const inSet = visibleNodeIds.has(n.id);
    nodesDataset.update({
      id: n.id,
      hidden: !inSet,
      borderWidth: inSet ? 4 : 2,
      size: inSet ? (n.size || 20) + 4 : (n.size || 20),
    });
  });

  // 3. 更新边可见性与样式（高亮边加粗变色，其他隐藏）
  edgesDataset.forEach(e => {
    const key = e.from + '-' + e.to;
    const isHighlight = speakerEdgeKeySet.has(key);
    edgesDataset.update({
      id: e.id,
      hidden: !isHighlight,
      width: isHighlight ? 5 : 2,
      color: isHighlight ? {
        color: '#6A1B9A',
        opacity: 0.95,
        highlight: '#6A1B9A',
      } : (e.color || {}),
    });
  });

  // 4. 渲染发言人画像卡
  renderPersonaCard(speakerName, speakerEdges);

  // 5. 更新右下角 detail panel
  renderSpeakerSummary(speakerName, speakerEdges, visibleNodeIds);
}

function renderPersonaCard(speakerName, speakerEdges) {
  const persona = SPEAKER_PERSONAS.personas.find(p => p.speaker === speakerName);
  const container = document.getElementById('personaCardContainer');

  if (!persona) {
    container.innerHTML = '<div style="color:#999;font-size:12px;padding:8px;">该发言人无画像数据</div>';
    return;
  }

  let card = '<div class="persona-card">';
  card += '<h4>' + speakerName + '</h4>';

  // 基本统计行
  card += '<div style="display:flex;gap:12px;margin-bottom:10px;flex-wrap:wrap;">';
  card += '<div class="persona-stat"><span class="label">观点总数</span><br><span class="val">' + persona.total_claims + '</span></div>';
  card += '<div class="persona-stat"><span class="label">擅长因子</span><br><span class="val" style="color:' + (FACTOR_COLORS[persona.top_factor]||'#333') + ';font-size:12px;">' + persona.top_factor + '</span></div>';
  if (persona.direction_label) {
    const dColors = {"偏利多":"#2e7d32","偏利空":"#c62828","偏中性":"#1565c0","均衡":"#555"};
    card += '<div class="persona-stat"><span class="label">判断倾向</span><br><span class="val" style="color:' + (dColors[persona.direction_label]||'#333') + '">' + persona.direction_label + '</span></div>';
  }
  card += '</div>';

  // 因子偏好分布条（带点击跳转）
  if (persona.factor_preference) {
    card += '<div style="font-size:11px;color:#888;margin-bottom:4px;">因子偏好分布</div>';
    const sorted = Object.entries(persona.factor_preference).sort((a,b) => b[1].count - a[1].count);
    sorted.forEach(([factor, info]) => {
      const color = FACTOR_COLORS[factor] || '#999';
      const pct = info.pct || 0;
      card += '<div style="display:flex;align-items:center;gap:6px;margin-bottom:3px;">';
      card += '<span style="width:50px;font-size:11px;color:#555;flex-shrink:0;">' + factor.slice(0,4) + '</span>';
      card += '<div class="persona-bar" style="flex:1;"><div class="persona-bar-fill" style="width:' + Math.min(pct, 100) + '%;background:' + color + ';"></div></div>';
      card += '<span style="font-size:10px;color:#888;width:42px;text-align:right;">' + info.count + '(' + pct + '%)</span>';
      card += '</div>';
    });
  }

  // 观点类型分布
  if (persona.claim_type_dist && persona.dominant_claim_type) {
    card += '<div style="font-size:11px;color:#888;margin-top:8px;margin-bottom:4px;">观点类型（主打: ' + persona.dominant_claim_type + '）</div>';
    const types = Object.entries(persona.claim_type_dist).sort((a,b) => b[1].count - a[1].count);
    types.slice(0, 5).forEach(([type, info]) => {
      const isDom = type === persona.dominant_claim_type;
      card += '<span style="display:inline-block;margin-right:6px;font-size:11px;padding:1px 4px;border-radius:3px;' +
        (isDom ? 'background:#6A1B9A;color:#fff;' : 'background:#f5f5f5;color:#555;') + '">' +
        type + ' ' + info.count + '</span>';
    });
  }

  // 方向判断偏好
  if (persona.direction_dist) {
    card += '<div style="font-size:11px;color:#888;margin-top:8px;margin-bottom:4px;">方向判断偏好</div>';
    const dColors = {"利多":"#2e7d32","利空":"#c62828","中性":"#1565c0","不明确":"#999"};
    card += '<div style="display:flex;gap:8px;">';
    Object.entries(persona.direction_dist).sort((a,b) => b[1] - a[1]).forEach(([dir, cnt]) => {
      card += '<span style="font-size:12px;font-weight:600;color:' + (dColors[dir]||'#333') + ';">' + dir + ' ' + cnt + '</span>';
    });
    card += '</div>';
  }

  // 因果边数量
  if (persona.causal_edges) {
    const ce = persona.causal_edges;
    card += '<div style="font-size:11px;color:#888;margin-top:8px;">';
    card += '因果链: <b>' + (ce.as_source || 0) + '</b>条作为源头 / <b>' + (ce.as_target || 0) + '</b>条作为目标</div>';
  }

  // 关联因果边列表（可点击跳转）
  if (speakerEdges.length > 0) {
    card += '<div style="font-size:11px;color:#888;margin-top:8px;margin-bottom:4px;">关联因果边（点击跳转）</div>';
    card += '<div style="max-height:160px;overflow-y:auto;">';
    speakerEdges.forEach(se => {
      const srcFid = VISID_TO_FID[String(se.from)] || '';
      const tgtFid = VISID_TO_FID[String(se.to)] || '';
      const srcLabel = srcFid ? (RAW_DATA.nodes[srcFid] || {}).label || srcFid : String(se.from);
      const tgtLabel = tgtFid ? (RAW_DATA.nodes[tgtFid] || {}).label || tgtFid : String(se.to);
      const sLabel = se.label || (srcLabel + '→' + tgtLabel);
      const sColor = se.strength >= 0.7 ? '#283593' : se.strength >= 0.4 ? '#e65100' : '#999';
      card += '<div style="font-size:11px;padding:3px 4px;border-bottom:1px dashed #eee;cursor:pointer;" ' +
        'onclick="focusOnEdge(' + se.from + ',' + se.to + ')" ' +
        'onmouseenter="this.style.background=\'#f0e6f6\'" onmouseleave="this.style.background=\'transparent\'">' +
        '<span style="color:' + sColor + ';font-weight:600;">' + sLabel + '</span>' +
        '</div>';
    });
    card += '</div>';
  }

  // 关键观点（代表性原文）
  if (persona.key_claims && persona.key_claims.length > 0) {
    card += '<div style="font-size:11px;color:#888;margin-top:8px;margin-bottom:4px;">代表性观点</div>';
    card += '<div style="max-height:120px;overflow-y:auto;">';
    persona.key_claims.slice(0, 5).forEach(claim => {
      const text = (claim.text || '').slice(0, 100);
      const truncated = (claim.text || '').length > 100;
      card += '<div style="font-size:11px;color:#444;padding:3px 0;border-bottom:1px dashed #eee;">';
      card += text + (truncated ? '...' : '');
      if (claim.factor) card += ' <span style="color:#888;font-size:10px;">[' + claim.factor + ']</span>';
      if (claim.type) card += ' <span style="color:#aaa;font-size:10px;">(' + claim.type + ')</span>';
      card += '</div>';
    });
    card += '</div>';
  }

  card += '</div>';
  container.innerHTML = card;
}

function renderSpeakerSummary(speakerName, speakerEdges, visibleNodeIds) {
  const persona = SPEAKER_PERSONAS.personas.find(p => p.speaker === speakerName);
  const panel = document.getElementById('detailPanel');

  let summary = '<div style="margin-bottom:8px;"><b style="font-size:15px;color:#6A1B9A;">' + speakerName + '</b></div>';
  summary += '<div style="color:#666;font-size:12px;margin-bottom:6px;">高亮 <b>' + speakerEdges.length + '</b> 条因果边，涉及 <b>' + visibleNodeIds.size + '</b> 个因子节点</div>';

  // 标签
  if (persona && persona.tags && persona.tags.length > 0) {
    summary += '<div style="font-size:12px;margin-bottom:6px;">';
    persona.tags.forEach(t => {
      summary += '<span class="badge" style="background:#6A1B9A;margin-right:4px;margin-bottom:2px;">' + t + '</span>';
    });
    summary += '</div>';
  }

  // 该发言人在哪些因子间建立了因果链（按因子分组展示）
  const factorGroups = {};
  speakerEdges.forEach(se => {
    const srcFid = VISID_TO_FID[String(se.from)] || '';
    const tgtFid = VISID_TO_FID[String(se.to)] || '';
    if (srcFid && tgtFid) {
      const srcPrimary = (RAW_DATA.nodes[srcFid] || {}).primary || '未知';
      const tgtPrimary = (RAW_DATA.nodes[tgtFid] || {}).primary || '未知';
      const pairKey = srcPrimary + ' → ' + tgtPrimary;
      if (!factorGroups[pairKey]) factorGroups[pairKey] = 0;
      factorGroups[pairKey]++;
    }
  });
  if (Object.keys(factorGroups).length > 0) {
    summary += '<div style="font-size:11px;color:#888;margin-bottom:4px;">跨因子因果链分布</div>';
    const sorted = Object.entries(factorGroups).sort((a,b) => b[1] - a[1]);
    sorted.slice(0, 6).forEach(([pair, cnt]) => {
      summary += '<div style="font-size:11px;padding:2px 0;">' + pair + ': <b>' + cnt + '</b>条</div>';
    });
  }

  // 发言人原文支撑（从 EDGE_SPEAKER_INDEX 中提取该发言人的原文）
  const speakerQuotes = [];
  for (const [edgeKey, entries] of Object.entries(EDGE_SPEAKER_INDEX)) {
    entries.forEach(entry => {
      if (entry.speaker === speakerName) {
        speakerQuotes.push({ ...entry, edge: edgeKey });
      }
    });
  }
  // 去重并取最新5条
  const uniqueQuotes = [];
  const seenTexts = new Set();
  speakerQuotes.sort((a,b) => (b.date || '').localeCompare(a.date || ''));
  speakerQuotes.forEach(q => {
    if (!seenTexts.has(q.text) && uniqueQuotes.length < 5) {
      seenTexts.add(q.text);
      uniqueQuotes.push(q);
    }
  });
  if (uniqueQuotes.length > 0) {
    summary += '<div style="font-size:11px;color:#888;margin-top:8px;margin-bottom:4px;">最新支撑观点</div>';
    uniqueQuotes.forEach(q => {
      const text = (q.text || '').slice(0, 80);
      const truncated = (q.text || '').length > 80;
      summary += '<div style="font-size:11px;color:#555;padding:2px 0;border-bottom:1px dashed #eee;">';
      summary += text + (truncated ? '...' : '');
      summary += ' <span style="color:#aaa;font-size:10px;">(' + (q.date || '') + ')</span>';
      summary += '</div>';
    });
  }

  summary += '<div style="font-size:11px;color:#aaa;margin-top:8px;">← 左侧工具栏查看完整画像卡</div>';
  panel.innerHTML = summary;
}

// 点击因果边列表项，跳转并聚焦该边
function focusOnEdge(fromId, toId) {
  // 先选中两个端点节点，让 vis.js 高亮连边
  network.selectNodes([String(fromId), String(toId)]);
  // 聚焦到两点中心
  network.focus(String(fromId), { scale: 1.5, animation: { duration: 400 } });
  // 显示该边的详情（从 EDGE_SPEAKER_INDEX 查找）
  const srcFid = VISID_TO_FID[String(fromId)] || '';
  const tgtFid = VISID_TO_FID[String(toId)] || '';
  const edgeKey = srcFid + '→' + tgtFid;
  const entries = EDGE_SPEAKER_INDEX[edgeKey] || [];

  const panel = document.getElementById('detailPanel');
  const srcLabel = srcFid ? (RAW_DATA.nodes[srcFid] || {}).label || srcFid : '';
  const tgtLabel = tgtFid ? (RAW_DATA.nodes[tgtFid] || {}).label || tgtFid : '';

  let html = '<div style="margin-bottom:6px;"><b style="font-size:14px;">' + srcLabel + ' → ' + tgtLabel + '</b></div>';
  html += '<div style="color:#666;font-size:12px;margin-bottom:6px;">(' + edgeKey + ')</div>';

  // 原始因果边详情
  const rawEdge = RAW_DATA.edges.find(e => e.source === srcFid && e.target === tgtFid);
  if (rawEdge) {
    html += '<div style="font-size:12px;margin-bottom:4px;">强度: ' + rawEdge.strength + ' (' + rawEdge.strength_score + ') | 符号: ' + rawEdge.sign + ' | 时滞: ' + rawEdge.lag + '</div>';
    html += '<div style="font-size:12px;color:#555;margin-bottom:6px;">机制: ' + (rawEdge.mechanism || '-') + '</div>';
  }

  // 该发言人对这条边的支撑原文
  if (activeSpeaker) {
    const speakerEntries = entries.filter(e => e.speaker === activeSpeaker);
    if (speakerEntries.length > 0) {
      html += '<div style="font-size:11px;color:#6A1B9A;margin-bottom:4px;">' + activeSpeaker + ' 的支撑观点 (' + speakerEntries.length + '条)</div>';
      speakerEntries.forEach(entry => {
        html += '<div style="font-size:11px;color:#444;padding:3px 0;border-bottom:1px dashed #eee;">';
        html += (entry.text || '').slice(0, 120) + ((entry.text||'').length > 120 ? '...' : '');
        html += ' <span style="color:#aaa;font-size:10px;">(' + (entry.date || '') + ')</span>';
        html += '</div>';
      });
    }
    // 也显示其他发言人的支撑
    const otherEntries = entries.filter(e => e.speaker !== activeSpeaker);
    if (otherEntries.length > 0) {
      html += '<div style="font-size:11px;color:#888;margin-top:6px;margin-bottom:4px;">其他发言人支撑 (' + otherEntries.length + '条)</div>';
      otherEntries.slice(0, 3).forEach(entry => {
        html += '<div style="font-size:11px;color:#888;padding:2px 0;">';
        html += '<b>' + entry.speaker + '</b>: ' + (entry.text || '').slice(0, 60) + '...';
        html += ' <span style="color:#aaa;font-size:10px;">(' + (entry.date || '') + ')</span>';
        html += '</div>';
      });
      if (otherEntries.length > 3) {
        html += '<div style="font-size:10px;color:#aaa;">...还有 ' + (otherEntries.length - 3) + ' 条</div>';
      }
    }
  } else {
    // 没有激活发言人，显示所有支撑
    if (entries.length > 0) {
      html += '<div style="font-size:11px;color:#888;margin-bottom:4px;">支撑观点 (' + entries.length + '条)</div>';
      entries.slice(0, 5).forEach(entry => {
        html += '<div style="font-size:11px;color:#444;padding:2px 0;border-bottom:1px dashed #eee;">';
        html += '<b>' + entry.speaker + '</b>: ' + (entry.text || '').slice(0, 80) + '...';
        html += '</div>';
      });
    }
  }

  panel.innerHTML = html;
}

function clearSpeakerView() {
  activeSpeaker = null;
  speakerEdgeKeySet = new Set();

  // 恢复所有节点和边的可见性（重置到当前视图模式）
  setViewMode(currentView);

  // 重置发言人的样式修改（恢复节点大小和边样式）
  nodesDataset.forEach(n => {
    const origSize = NODES.find(nd => nd.id === n.id);
    nodesDataset.update({
      id: n.id,
      borderWidth: origSize ? 2 : 2,
    });
  });
  edgesDataset.forEach(e => {
    const origEdge = EDGES.find(ed => ed.from === e.from && ed.to === e.to);
    if (origEdge) {
      edgesDataset.update({
        id: e.id,
        width: origEdge.width || 2,
        color: origEdge.color || {},
      });
    }
  });

  document.getElementById('speakerSelect').value = '';
  document.getElementById('personaCardContainer').innerHTML = '';
  document.getElementById('detailPanel').innerHTML = '<div class="empty">点击任意节点查看详情</div>';
}

// ========== 点击节点时的增强：显示该节点的发言人维度 ==========
const origUpdateDetail = updateDetail;
updateDetail = function(nodeId) {
  origUpdateDetail(nodeId);
  if (!nodeId || !activeSpeaker) return;
  // 如果有激活的发言人，在节点详情中追加该发言人对此节点的观点
  const fid = NODE_ID_MAP[nodeId];
  const panel = document.getElementById('detailPanel');
  if (!panel) return;

  // 从 EDGE_SPEAKER_INDEX 查找该发言人关于此节点的原文
  const speakerQuotes = [];
  for (const [edgeKey, entries] of Object.entries(EDGE_SPEAKER_INDEX)) {
    const [src, tgt] = edgeKey.split('→');
    if (src === fid || tgt === fid) {
      entries.forEach(entry => {
        if (entry.speaker === activeSpeaker) {
          speakerQuotes.push({ ...entry, edge: edgeKey, role: src === fid ? '源头' : '目标' });
        }
      });
    }
  }

  if (speakerQuotes.length > 0) {
    speakerQuotes.sort((a,b) => (b.date || '').localeCompare(a.date || ''));
    let extra = '<div style="margin-top:10px;padding-top:8px;border-top:1px solid #e0e0e0;">';
    extra += '<b style="font-size:12px;color:#6A1B9A;">' + activeSpeaker + ' 的相关观点 (' + speakerQuotes.length + '条)</b>';
    extra += '<div style="max-height:100px;overflow-y:auto;margin-top:4px;">';
    speakerQuotes.slice(0, 4).forEach(q => {
      extra += '<div style="font-size:11px;color:#555;padding:2px 0;border-bottom:1px dashed #eee;">';
      extra += '<span style="color:#aaa;">[' + q.role + ' ' + q.edge + ']</span> ';
      extra += (q.text || '').slice(0, 80) + ((q.text||'').length > 80 ? '...' : '');
      extra += ' <span style="color:#aaa;font-size:10px;">(' + (q.date || '') + ')</span>';
      extra += '</div>';
    });
    extra += '</div></div>';
    panel.innerHTML += extra;
  }
};
</script>
</body>
</html>
"""

with open(BASE / "causal_interactive.html", "w", encoding="utf-8") as f:
    f.write(html)

print(f"Done! Saved to {BASE / 'causal_interactive.html'}")
print(f"File size: {len(html)} bytes")
