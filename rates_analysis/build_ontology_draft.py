"""
build_ontology_draft.py  v2
基于 factor_cooccurrence.json 中的 secondary_factor_inventory（317条）
按频次排序、按一级因子分组，生成人工审核草稿。
"""

import json
import os
from collections import defaultdict

BASE_DIR = r"c:\Users\123cy\WorkBuddy\20260408090957\rates_analysis"

# ── 加载共现数据 ─────────────────────────────────────────────────────
with open(os.path.join(BASE_DIR, "factor_cooccurrence.json"), "r", encoding="utf-8") as f:
    cooc_data = json.load(f)

inventory = cooc_data.get("secondary_factor_inventory", [])
print(f"二级因子库共 {len(inventory)} 条")

# ── 一级因子标准化映射 ────────────────────────────────────────────────
# 现有数据中 primary_factor 的值可能是"市场情绪"，对应标准名"市场情绪因子"
NORMALIZE_PRIMARY = {
    "基本面": "基本面因子",
    "基本面因子": "基本面因子",
    "政策面": "政策面因子",
    "政策面因子": "政策面因子",
    "货币政策": "政策面因子",
    "流动性": "流动性因子",
    "流动性因子": "流动性因子",
    "市场情绪": "市场情绪因子",
    "市场情绪因子": "市场情绪因子",
    "机构行为": "机构行为因子",
    "机构行为因子": "机构行为因子",
}

PRIMARY_CODE = {
    "基本面因子": "FD",
    "政策面因子": "PL",
    "流动性因子": "LQ",
    "市场情绪因子": "MS",
    "机构行为因子": "IB",
}

# ── 关键词辅助归类（针对 primary_factor 缺失或异常的情况）────────────
KEYWORD_MAP = {
    "FD": ["经济", "增长", "通胀", "CPI", "PPI", "PMI", "GDP", "就业", "贸易", "出口", "进口",
           "信用", "企业", "盈利", "地产", "房地产", "消费", "制造", "工业"],
    "PL": ["政策", "货币", "央行", "降准", "降息", "MLF", "LPR", "OMO", "财政", "赤字",
           "监管", "信贷", "债务", "政府", "国债供给", "发行"],
    "LQ": ["流动性", "资金", "DR007", "R007", "银行间", "隔夜", "跨境", "外汇", "汇率",
           "存款", "缴税", "季末", "跨月", "跨季"],
    "MS": ["情绪", "风险偏好", "技术", "仓位", "持仓", "境外", "外资", "北向", "投资者",
           "预期", "信心", "避险", "利差", "信用利差", "策略"],
    "IB": ["机构", "配置", "保险", "银行", "基金", "理财", "申购", "赎回", "久期",
           "负债", "AUM", "规模"],
}

def normalize_primary(raw_name, factor_name):
    if raw_name in NORMALIZE_PRIMARY:
        return NORMALIZE_PRIMARY[raw_name]
    for code, keywords in KEYWORD_MAP.items():
        for kw in keywords:
            if kw in factor_name:
                # 找到对应的标准名
                for std_name, c in PRIMARY_CODE.items():
                    if c == code:
                        return std_name
    return "待分类"

# ── 整理 inventory ────────────────────────────────────────────────────
processed = []
for item in inventory:
    name = item.get("name", "").strip()
    raw_pf = item.get("primary_factor", "")
    total_mentions = item.get("total_mentions", 0)
    meeting_count = item.get("meeting_count", 0)
    speakers = item.get("speakers", [])

    std_pf = normalize_primary(raw_pf, name)
    code = PRIMARY_CODE.get(std_pf, "?")

    processed.append({
        "name": name,
        "primary_factor": std_pf,
        "primary_code": code,
        "total_mentions": total_mentions,
        "meeting_count": meeting_count,
        "speaker_count": len(speakers),
    })

# ── 按一级因子分组，再按 total_mentions 降序 ─────────────────────────
grouped = defaultdict(list)
for item in processed:
    grouped[item["primary_code"]].append(item)

for code in grouped:
    grouped[code].sort(key=lambda x: x["total_mentions"], reverse=True)

# ── 输出 Markdown 草稿 ────────────────────────────────────────────────
PRIMARY_ORDER = ["FD", "PL", "LQ", "MS", "IB", "?"]
CODE_TO_NAME = {v: k for k, v in PRIMARY_CODE.items()}
CODE_TO_NAME["?"] = "待分类"

output_md = "# 因子本体库候选草稿（供人工审核）\n\n"
output_md += f"> 数据来源：factor_cooccurrence.json，共 {len(inventory)} 条二级因子  \n"
output_md += f"> 目标：从中保留 40-50 个稳定、清晰的二级因子作为本体库核心\n\n"
output_md += "## 操作说明\n\n"
output_md += "每行是一个候选二级因子，请在「审核意见」列填写：\n"
output_md += "- `✓` 保留（纳入本体库）\n"
output_md += "- `✗` 删除（太细/太宽/不标准）\n"
output_md += "- `~合并→XXX` 与另一个因子合并，XXX 是目标标准名\n"
output_md += "- 一级因子归属如有误，请在备注说明\n\n"
output_md += "---\n\n"

total_shown = 0
for code in PRIMARY_ORDER:
    items = grouped.get(code, [])
    if not items:
        continue
    section_name = CODE_TO_NAME.get(code, "待分类")
    # 为方便审核，只展示 meeting_count >= 2 的（在2份及以上纪要中出现过）
    # 及 total_mentions >= 3 的，其余归入「长尾候选」
    core = [x for x in items if x["meeting_count"] >= 2 or x["total_mentions"] >= 3]
    tail = [x for x in items if x["meeting_count"] < 2 and x["total_mentions"] < 3]

    output_md += f"## {section_name}（{code}）\n\n"
    output_md += f"核心候选 {len(core)} 个 | 长尾候选 {len(tail)} 个（建议优先从核心候选中选取）\n\n"

    output_md += "### 核心候选\n\n"
    output_md += "| 序号 | 二级因子名称 | 总提及次数 | 覆盖纪要数 | 发言人数 | 审核意见 |\n"
    output_md += "|------|------------|---------|----------|--------|--------|\n"
    for i, item in enumerate(core, 1):
        output_md += f"| {i} | {item['name']} | {item['total_mentions']} | {item['meeting_count']} | {item['speaker_count']} | |\n"
    total_shown += len(core)

    if tail:
        output_md += f"\n<details><summary>长尾候选（{len(tail)} 个，点击展开）</summary>\n\n"
        output_md += "| 序号 | 二级因子名称 | 总提及次数 | 覆盖纪要数 | 审核意见 |\n"
        output_md += "|------|------------|---------|----------|--------|\n"
        for i, item in enumerate(tail, 1):
            output_md += f"| {i} | {item['name']} | {item['total_mentions']} | {item['meeting_count']} | |\n"
        output_md += "\n</details>\n\n"

    output_md += "\n"

output_md += f"---\n\n**核心候选合计：{total_shown} 个**（建议从中保留 40-50 个）\n"

# ── 同时输出 JSON 结构化草稿 ──────────────────────────────────────────
# JSON 只包含核心候选，分配临时 factor_id
json_draft = []
id_counters = {code: 1 for code in PRIMARY_CODE.values()}
id_counters["?"] = 1

for code in PRIMARY_ORDER:
    items = grouped.get(code, [])
    core = [x for x in items if x["meeting_count"] >= 2 or x["total_mentions"] >= 3]
    for item in core:
        actual_code = code if code in id_counters else "FD"
        fid = f"{actual_code}_{id_counters[actual_code]:02d}"
        id_counters[actual_code] += 1
        json_draft.append({
            "factor_id": fid,
            "factor_label": item["name"],
            "primary_factor": item["primary_factor"],
            "primary_factor_code": actual_code,
            "level": 2,
            "aliases": [],
            "definition": "",
            "key_metrics": [],
            "typical_direction": "视情境而定",
            "appearance_count": item["total_mentions"],
            "meeting_count": item["meeting_count"],
            "speaker_count": item["speaker_count"],
            "status": "candidate",
        })

# ── 写出文件 ────────────────────────────────────────────────────────
md_path = os.path.join(BASE_DIR, "factor_ontology_draft.md")
json_path = os.path.join(BASE_DIR, "factor_ontology_draft.json")

with open(md_path, "w", encoding="utf-8") as f:
    f.write(output_md)

with open(json_path, "w", encoding="utf-8") as f:
    json.dump(json_draft, f, ensure_ascii=False, indent=2)

print(f"\n✅ 草稿已生成：")
print(f"   Markdown（供人工审核）: {md_path}")
print(f"   JSON（结构化草稿）: {json_path}")
print(f"\n各一级因子核心候选数量：")
for code in PRIMARY_ORDER:
    items = grouped.get(code, [])
    core = [x for x in items if x["meeting_count"] >= 2 or x["total_mentions"] >= 3]
    name = CODE_TO_NAME.get(code, "待分类")
    print(f"   {code} {name}: 核心{len(core)}个 / 长尾{len(items)-len(core)}个")
print(f"\n核心候选合计: {sum(len([x for x in grouped.get(c,[]) if x['meeting_count']>=2 or x['total_mentions']>=3]) for c in PRIMARY_ORDER)} 个")
