"""
build_ontology_final.py
根据人工审核结论，从草稿 JSON 构建正式 factor_ontology.json
规则：
1. 同义词合并（保留主名，alias 记录被合并项）
2. 删除/降级冗余因子
3. 修正归属（政策预期 MS→PL）
4. 输出到 assets/ 和 skill 目录两处
"""
import json, os, copy
from datetime import date

DRAFT_PATH  = "factor_ontology_draft.json"
OUTPUT_PATH = "factor_ontology.json"
SKILL_PATH  = r"C:\Users\123cy\.workbuddy\skills\ficc-factor-midplatform\assets\factor_ontology.json"

# ── 读草稿 ──────────────────────────────────────────────────────────────────
with open(DRAFT_PATH, encoding="utf-8") as f:
    draft = json.load(f)

# 草稿可能是 list 或 dict
if isinstance(draft, list):
    nodes_in = draft
else:
    nodes_in = draft.get("nodes", [])

# ── 操作指令 ────────────────────────────────────────────────────────────────

# 1. 删除（完全移除）
DELETE_IDS = {
    "五因子框架",       # PL — 方法本身
    "策略建议",         # MS — 输出结论
    "市场观察",         # MS — 太模糊
    "风险管理",         # IB — 太宽泛
    "政策预期管理",     # FD — 名称与 PL 重叠，内容迁入 PL 侧
}

# 2. 归属修正：MS → PL
MOVE_TO_PL = {
    "政策预期",         # 用户确认：归 PL
}

# 3. 同义词合并规则：{保留名: [被吸收的名称列表]}
MERGE_MAP = {
    # LQ
    "资金面判断":       ["资金面分析", "资金面预期"],
    "同业存单利率":     ["存单利率", "存单分析"],
    "杠杆套息策略":     ["杠杆策略", "套息策略", "杠杆套息环境"],
    # PL
    "货币政策取向":     ["货币政策预期"],
    "央行态度与信号":   ["央行态度"],   # 后者在草稿里归 MS，现迁入 PL
    # MS
    "股债关系":         ["股债跷跷板效应"],
    # IB
    "机构配置行为":     ["配置盘行为", "银行配置行为"],
}

# ── 构建 name→node 索引 ────────────────────────────────────────────────────
name2node = {}
for n in nodes_in:
    # 草稿用 factor_label，正式 schema 用 factor_name
    fname = n.get("factor_label", "") or n.get("factor_name", "")
    if fname:
        n["factor_name"] = fname   # 统一字段名
        name2node[fname] = copy.deepcopy(n)

# ── 归属修正 ─────────────────────────────────────────────────────────────────
for fname in MOVE_TO_PL:
    if fname in name2node:
        old_id = name2node[fname].get("factor_id", "")
        # 重建 ID：MS_xxx → PL_xxx
        new_id = old_id.replace("MS_", "PL_") if old_id.startswith("MS_") else old_id
        name2node[fname]["primary_factor"] = "政策面因子"
        name2node[fname]["primary_factor_code"] = "PL"
        name2node[fname]["factor_id"] = new_id
        name2node[fname]["归属说明"] = "用户确认：市场对政策的预期归属政策面因子PL"

# ── 同义词合并 ───────────────────────────────────────────────────────────────
absorbed = set()   # 被吸收的名称集合
for canonical, synonyms in MERGE_MAP.items():
    # 保留方的 aliases 列表
    if canonical in name2node:
        existing_aliases = name2node[canonical].get("aliases", [])
        # 把被合并项的出现次数加入权重（可选：累加 weight）
        for syn in synonyms:
            if syn not in existing_aliases:
                existing_aliases.append(syn)
            absorbed.add(syn)
        name2node[canonical]["aliases"] = existing_aliases
        # 累加 appearance_count
        for syn in synonyms:
            if syn in name2node:
                name2node[canonical]["appearance_count"] = (
                    name2node[canonical].get("appearance_count", 0)
                    + name2node[syn].get("appearance_count", 0)
                )
    else:
        # 保留方本身可能不存在于草稿（如 "资金面判断" 是新标准名），新建节点
        # 从第一个被合并项继承
        first_syn = synonyms[0] if synonyms else None
        if first_syn and first_syn in name2node:
            base = copy.deepcopy(name2node[first_syn])
            base["factor_name"] = canonical
            # 重建 ID
            pfx = base.get("factor_id", "XX_001")[:3]
            base["factor_id"] = f"{pfx}{canonical[:4]}"
            base["aliases"] = synonyms[1:] if len(synonyms) > 1 else []
            name2node[canonical] = base
        for syn in synonyms:
            absorbed.add(syn)

# ── 过滤：删除 DELETE_IDS 和 absorbed ──────────────────────────────────────
removed = DELETE_IDS | absorbed
nodes_out = [
    n for fname, n in name2node.items()
    if fname not in removed
]

# ── 重新分配规范 factor_id ────────────────────────────────────────────────
# 格式：{CODE}_{3位序号}  代码从 primary_factor_code 字段取
code2name = {
    "FD": "基本面因子", "PL": "政策面因子", "LQ": "流动性因子",
    "MS": "市场情绪因子", "IB": "机构行为因子"
}
counters = {k: 1 for k in code2name}
for n in sorted(nodes_out, key=lambda x: x.get("primary_factor_code", "XX")):
    code = n.get("primary_factor_code", "XX")
    n["factor_id"] = f"{code}_{counters.get(code, 1):03d}"
    if code in counters:
        counters[code] += 1

# ── 补充必要字段（schema 要求） ────────────────────────────────────────────
for n in nodes_out:
    n.setdefault("status", "active")
    n.setdefault("aliases", [])
    n.setdefault("description", "")
    n.setdefault("candidate_pool", [])
    n.setdefault("last_updated", str(date.today()))
    n.setdefault("created_by", "build_ontology_final.py")

# ── 构建最终结构 ──────────────────────────────────────────────────────────
ontology = {
    "version": "1.0.0",
    "created_at": str(date.today()),
    "description": "FICC 债市五因子本体库 — 正式版，经人工审核",
    "primary_factors": {
        "FD": "基本面因子",
        "PL": "政策面因子",
        "LQ": "流动性因子",
        "MS": "市场情绪因子",
        "IB": "机构行为因子"
    },
    "total_nodes": len(nodes_out),
    "nodes": nodes_out
}

# ── 写出 ──────────────────────────────────────────────────────────────────
with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
    json.dump(ontology, f, ensure_ascii=False, indent=2)
print(f"[OK] factor_ontology.json written  ({len(nodes_out)} nodes)")

# 同步写到 skill assets 目录
os.makedirs(os.path.dirname(SKILL_PATH), exist_ok=True)
with open(SKILL_PATH, "w", encoding="utf-8") as f:
    json.dump(ontology, f, ensure_ascii=False, indent=2)
print(f"[OK] Synced to skill assets: {SKILL_PATH}")

# ── 打印统计 ──────────────────────────────────────────────────────────────
from collections import Counter
dist = Counter(n.get("primary_factor_code") for n in nodes_out)
print("\n--- Factor Distribution ---")
for code in ["FD","PL","LQ","MS","IB"]:
    label = code2name.get(code, code)
    print(f"  {code} ({label}): {dist.get(code, 0)}")
print(f"  Total: {len(nodes_out)}")
print(f"\n已删除: {len(DELETE_IDS)} 个 | 已合并: {len(absorbed)} 个")
