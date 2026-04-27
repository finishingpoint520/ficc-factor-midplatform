#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
weekly_research_pipeline.py - 周度研报增量学习端到端管线

工作流（每周执行一次，建议周一上午）：
  Step 1. 采集  → iFind search_news（6 个团队，每个 2 条查询 × 8 条 = 最多 96 条原始片段）
  Step 2. 整理  → 去重 + 格式化为机构研报文本（每团队一个 .txt 文件）
  Step 3. 学习  → research_learner.py prepare（生成 LLM prompt）
  Step 4. LLM   → 由 Agent 送入大模型，返回结构化 claim_atoms JSON
  Step 5. 写入  → research_learner.py save（合并到 all_claim_atoms.json）
  Step 6. 更新  → causal_updater.py enrich（增量更新因果图谱 support_count）
  Step 7. 报告  → decision_engine.py render（输出本周五因子决策摘要）

用法:
  # 生成本周采集计划（不执行采集）
  python weekly_research_pipeline.py plan --days 7

  # 执行完整 pipeline（Step 1-2，采集+整理，Agent 完成 Step 3-7）
  python weekly_research_pipeline.py run --days 7

  # 查看上次采集结果
  python weekly_research_pipeline.py status
"""

import json
import os
import sys
import argparse
from pathlib import Path
from datetime import datetime, timedelta
from collections import defaultdict

ASSETS_DIR = Path(r"c:\Users\123cy\WorkBuddy\20260408090957\rates_analysis")
RESEARCH_DIR = ASSETS_DIR / "external_research"
RAW_DIR = RESEARCH_DIR / "raw"
FORMATTED_DIR = RESEARCH_DIR / "formatted"
WEEKLY_REPORTS_DIR = RESEARCH_DIR / "weekly_reports"

for d in [RAW_DIR, FORMATTED_DIR, WEEKLY_REPORTS_DIR]:
    d.mkdir(parents=True, exist_ok=True)

# 六大团队配置（与 fetch_research.py 保持一致）
TEAMS = [
    {
        "id": "huatai_zhang",
        "name": "张继强",
        "institution": "华泰证券研究所",
        "queries": [
            "华泰固收 张继强 债市利率策略",
            "华泰证券固收 利率策略 债券市场",
        ]
    },
    {
        "id": "huaxi_liu",
        "name": "刘郁",
        "institution": "华西证券研究所",
        "queries": [
            "刘郁 华西证券 债券利率策略",
            "华西固收 刘郁 利率债",
        ]
    },
    {
        "id": "swhy_huang",
        "name": "黄伟平",
        "institution": "申银万国研究所",
        "queries": [
            "黄伟平 申万宏源 债市策略",
            "申万固收 黄伟平 利率债策略",
        ]
    },
    {
        "id": "zhongtai_lv",
        "name": "吕品",
        "institution": "中泰证券研究所",
        "queries": [
            "吕品 中泰证券 固收 债市策略",
            "中泰固收 吕品 利率债",
        ]
    },
    {
        "id": "changjiang_zhao",
        "name": "赵增辉",
        "institution": "长江证券研究所",
        "queries": [
            "赵增辉 长江证券 固收 债市策略",
            "长江固收 赵增辉 利率债",
        ]
    },
    {
        "id": "guojin_yin",
        "name": "尹睿哲",
        "institution": "国金证券研究所",
        "queries": [
            "尹睿哲 国金证券 固收 债市策略",
            "国金固收 尹睿哲 利率债",
        ]
    },
]


# ─────────────────────────────────────────────
# Step 1 输入：由 Agent 执行 iFind 采集后保存的 JSON
# 格式：{"team_id": str, "items": [{资讯标题, 资讯内容, 日期, URL}]}
# ─────────────────────────────────────────────

def load_raw_data(raw_file: Path) -> dict:
    """读取 Agent 采集后存储的原始 JSON"""
    with open(raw_file, "r", encoding="utf-8") as f:
        return json.load(f)


def format_team_text(team: dict, items: list) -> str:
    """将某团队的 news items 格式化为 research_learner 可消费的文本"""
    if not items:
        return ""

    today = datetime.now().strftime("%Y-%m-%d")
    lines = [
        f"# 外部研报聚合 - {team['institution']} {team['name']} 团队",
        f"# 数据来源：同花顺 iFind MCP search_news",
        f"# 采集日期：{today}",
        f"# 片段数量：{len(items)}",
        "",
    ]

    for i, item in enumerate(items, 1):
        title = item.get("资讯标题", "无标题")
        content = item.get("资讯内容", "")
        date = item.get("日期", "")
        url = item.get("URL", "")
        lines += [
            f"## [{i}] {title}",
            f"日期：{date}",
            f"来源：{url}",
            "",
            content,
            "",
            "---",
            "",
        ]

    return "\n".join(lines)


def step2_format(raw_file: Path, today_str: str) -> list:
    """Step 2：整理原始数据，按团队切分，输出格式化 .txt"""
    raw = load_raw_data(raw_file)
    items_by_team = defaultdict(list)

    for item in raw.get("items", []):
        tid = item.get("team_id")
        if tid:
            items_by_team[tid].append(item)

    formatted_files = []
    for team in TEAMS:
        tid = team["id"]
        items = items_by_team.get(tid, [])
        if not items:
            print(f"  [WARN] {team['institution']} {team['name']}: 无采集数据，跳过")
            continue

        # 去重
        seen_titles = set()
        deduped = []
        for it in items:
            key = it.get("资讯标题", "")
            if key not in seen_titles:
                seen_titles.add(key)
                deduped.append(it)
        items = deduped

        text = format_team_text(team, items)
        out_file = FORMATTED_DIR / f"{today_str}_{tid}.txt"
        with open(out_file, "w", encoding="utf-8") as f:
            f.write(text)
        print(f"  [OK] {team['institution']} {team['name']}: {len(items)} 条 → {out_file.name}")
        formatted_files.append({
            "team_id": tid,
            "institution": team["institution"],
            "author": team["name"],
            "file": str(out_file),
            "item_count": len(items),
        })

    return formatted_files


def step3_prepare(formatted_files: list, today_str: str) -> list:
    """Step 3：为每个格式化文件生成 LLM prompt（调用 research_learner.py prepare）"""
    skill_dir = Path(r"C:\Users\123cy\.workbuddy\skills\ficc-factor-midplatform")
    learner_script = skill_dir / "scripts" / "agents" / "research_learner.py"

    prompt_files = []
    for entry in formatted_files:
        txt_file = Path(entry["file"])
        if not txt_file.exists():
            print(f"  [SKIP] {txt_file} 不存在")
            continue

        out_prompt = RESEARCH_DIR / "prompts" / f"{today_str}_{entry['team_id']}_prompt.json"
        out_prompt.parent.mkdir(parents=True, exist_ok=True)

        cmd = f'python "{learner_script}" prepare --input "{txt_file}"'
        print(f"  [CMD] {cmd}")

        # 实际执行（在 Agent 环境中直接运行）
        ret = os.system(cmd)
        if ret == 0:
            # research_learner.py prepare 的输出固定在 ASSETS_DIR/_pending_research_learn_prompt.json
            pending = ASSETS_DIR / "_pending_research_learn_prompt.json"
            if pending.exists():
                # 复制到按团队命名的文件
                import shutil
                shutil.copy(pending, out_prompt)
                print(f"  [OK] prompt 已保存 → {out_prompt.name}")
                prompt_files.append({
                    "team_id": entry["team_id"],
                    "institution": entry["institution"],
                    "author": entry["author"],
                    "prompt_file": str(out_prompt),
                    "formatted_file": entry["file"],
                })
        else:
            print(f"  [ERR] prepare 失败，exit code: {ret}")

    return prompt_files


def generate_weekly_report(today_str: str, formatted_files: list) -> Path:
    """
    生成周度研报学习工作单（给 Agent 的操作清单）
    包含：各团队待处理文件路径、LLM 调用指令、保存指令
    """
    report = {
        "weekly_date": today_str,
        "generated_at": datetime.now().isoformat(),
        "summary": f"本周采集 {len(formatted_files)} 个团队的研报数据",
        "workflow_steps": [
            {
                "step": 3,
                "action": "LLM 标注",
                "description": "将每个格式化文本送入 research_learner_prompt，让 LLM 抽取 claim_atoms",
                "teams": [
                    {
                        "team_id": f["team_id"],
                        "institution": f["institution"],
                        "author": f["author"],
                        "input_file": f["file"],
                        "cmd_prepare": f'python "C:\\Users\\123cy\\.workbuddy\\skills\\ficc-factor-midplatform\\scripts\\agents\\research_learner.py" prepare --input "{f["file"]}"',
                    }
                    for f in formatted_files
                ]
            },
            {
                "step": 4,
                "action": "LLM 执行",
                "description": "Agent 读取 _pending_research_learn_prompt.json 中的 full_prompt，调用 LLM，保存返回 JSON",
                "note": "每个团队消耗约 1000-3000 token，6 个团队合计约 1-2 万 token"
            },
            {
                "step": 5,
                "action": "写入原子库",
                "description": "对每个团队的 LLM 返回结果执行 save 命令",
                "cmd_template": 'python "C:\\Users\\123cy\\.workbuddy\\skills\\ficc-factor-midplatform\\scripts\\agents\\research_learner.py" save --input <llm_response.json> --institution "<机构名>"'
            },
            {
                "step": 6,
                "action": "更新因果图谱",
                "description": "重新计算 support_count，更新 factor_causal_edges_v2.json",
                "cmd": 'python "c:\\Users\\123cy\\WorkBuddy\\20260408090957\\rates_analysis\\enrich_causal_edges.py"'
            },
            {
                "step": 7,
                "action": "生成本周决策摘要",
                "description": "运行 decision_engine render，输出本周五因子决策摘要",
                "cmd": f'python "C:\\Users\\123cy\\.workbuddy\\skills\\ficc-factor-midplatform\\scripts\\agents\\decision_engine.py" render --date {today_str}'
            }
        ],
        "formatted_files": formatted_files,
    }

    report_file = WEEKLY_REPORTS_DIR / f"weekly_plan_{today_str}.json"
    with open(report_file, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)

    # 同时生成 Markdown 版本
    md_lines = [
        f"# 周度研报学习工作单 - {today_str}",
        "",
        f"生成时间：{datetime.now().strftime('%Y-%m-%d %H:%M')}",
        "",
        "## 采集结果汇总",
        "",
    ]
    for f in formatted_files:
        md_lines.append(f"- **{f['institution']} {f['author']}**：{f['item_count']} 条 → `{Path(f['file']).name}`")

    md_lines += [
        "",
        "## 待执行步骤",
        "",
        "### Step 3 → LLM 标注（需积分）",
        "",
        "为每个团队运行 `prepare` 命令，生成 LLM prompt：",
        "",
    ]
    for f in formatted_files:
        md_lines.append(f"```bash")
        md_lines.append(f'# {f["institution"]} {f["author"]}')
        cmd = f'python "C:\\Users\\123cy\\.workbuddy\\skills\\ficc-factor-midplatform\\scripts\\agents\\research_learner.py" prepare --input "{f["file"]}"'
        md_lines.append(cmd)
        md_lines.append("```")
        md_lines.append("")

    md_lines += [
        "### Step 4 → Agent 执行 LLM",
        "",
        "读取 `_pending_research_learn_prompt.json`，送入大模型，将返回 JSON 保存为 `<team_id>_response.json`。",
        "",
        "### Step 5 → 写入原子库（零积分）",
        "",
        "```bash",
        f'python "C:\\Users\\123cy\\.workbuddy\\skills\\ficc-factor-midplatform\\scripts\\agents\\research_learner.py" save --input <response.json> --institution "<机构名>"',
        "```",
        "",
        "### Step 6 → 更新因果图谱（零积分）",
        "",
        "```bash",
        f'python "c:\\Users\\123cy\\WorkBuddy\\20260408090957\\rates_analysis\\enrich_causal_edges.py"',
        "```",
        "",
        "### Step 7 → 生成本周决策摘要（零积分）",
        "",
        "```bash",
        f'python "C:\\Users\\123cy\\.workbuddy\\skills\\ficc-factor-midplatform\\scripts\\agents\\decision_engine.py" render --date {today_str}',
        "```",
        "",
        "---",
        f"完整工作单 JSON：`weekly_plan_{today_str}.json`",
    ]

    md_file = WEEKLY_REPORTS_DIR / f"weekly_plan_{today_str}.md"
    with open(md_file, "w", encoding="utf-8") as f:
        f.write("\n".join(md_lines))

    return md_file


def cmd_plan(days: int):
    """仅打印本周采集计划，不执行"""
    today = datetime.now()
    start = today - timedelta(days=days)
    print(f"\n{'='*60}")
    print(f"  周度研报采集计划（最近 {days} 天）")
    print(f"  时间范围: {start.strftime('%Y-%m-%d')} → {today.strftime('%Y-%m-%d')}")
    print(f"{'='*60}\n")
    print("【Step 1】Agent 需用 iFind MCP search_news 采集以下查询:\n")
    for team in TEAMS:
        print(f"  >> {team['institution']} {team['name']}:")
        for q in team["queries"]:
            print(f"      query='{q}', time_start='{start.strftime('%Y-%m-%d')}', time_end='{today.strftime('%Y-%m-%d')}', size=8")
        print()
    print("【采集后】将结果按团队保存为 JSON，格式：")
    print('  {"team_id": "huatai_zhang", "items": [{资讯标题, 资讯内容, 日期, URL}...]}\n')
    print("然后运行: python weekly_research_pipeline.py run --raw <raw_file>\n")


def cmd_status():
    """查看已有采集历史"""
    print(f"\n{'='*60}")
    print("  研报学习数据资产状态")
    print(f"{'='*60}\n")

    # 检查原始数据
    raw_files = sorted(RAW_DIR.glob("raw_research_*.json"))
    print(f"原始采集文件（{len(raw_files)} 个）：")
    for f in raw_files[-5:]:  # 显示最近5个
        size = f.stat().st_size // 1024
        print(f"  {f.name}  ({size} KB)")

    # 检查格式化文件
    fmt_files = sorted(FORMATTED_DIR.glob("*.txt"))
    print(f"\n格式化文本（{len(fmt_files)} 个）：")
    for f in fmt_files[-12:]:  # 显示最近12个
        print(f"  {f.name}")

    # 检查已学习的 claim_atoms
    ca_dir = ASSETS_DIR / "claim_atoms"
    ext_atoms = list(ca_dir.glob("*external*.json"))
    print(f"\n已学习的外部研报 atoms 文件（{len(ext_atoms)} 个）：")
    for f in ext_atoms[-10:]:
        print(f"  {f.name}")

    # 检查 all_claim_atoms 外部来源统计
    all_file = ca_dir / "all_claim_atoms.json"
    if all_file.exists():
        with open(all_file, "r", encoding="utf-8") as f:
            all_data = json.load(f)
        atoms = all_data.get("claim_atoms", [])
        ext_count = sum(1 for a in atoms if a.get("source_type") == "外部研报")
        total = len(atoms)
        print(f"\nall_claim_atoms.json：{total} 条（其中外部研报 {ext_count} 条）")

    # 检查周报
    weekly_files = sorted(WEEKLY_REPORTS_DIR.glob("weekly_plan_*.md"))
    print(f"\n周度工作单（{len(weekly_files)} 个）：")
    for f in weekly_files[-5:]:
        print(f"  {f.name}")


def cmd_run(days: int, raw_file: str = None):
    """
    执行 Step 2（格式化）+ 生成工作单
    Step 1（iFind 采集）和 Step 3-7 需要 Agent 手动触发
    """
    today_str = datetime.now().strftime("%Y-%m-%d")

    if raw_file is None:
        # 寻找最新的原始数据文件
        raw_files = sorted(RAW_DIR.glob("raw_research_*.json"))
        if not raw_files:
            print(f"[ERROR] 未找到原始采集文件，请先让 Agent 执行 iFind 采集并保存到: {RAW_DIR}")
            print("  参考: python weekly_research_pipeline.py plan --days 7")
            sys.exit(1)
        raw_file = str(raw_files[-1])
        print(f"[INFO] 使用最新原始文件: {raw_file}")

    print(f"\n{'='*60}")
    print(f"  周度研报学习 Pipeline - {today_str}")
    print(f"{'='*60}\n")

    print("Step 2: 格式化原始采集数据...")
    formatted_files = step2_format(Path(raw_file), today_str)
    print(f"  → 格式化完成: {len(formatted_files)} 个团队\n")

    print("生成周度工作单...")
    md_file = generate_weekly_report(today_str, formatted_files)
    print(f"  → 工作单: {md_file}\n")

    print("─" * 60)
    print("Step 3-7 需要 Agent 手动执行（部分需积分）：")
    print(f"  请查看工作单: {md_file}")
    print("─" * 60)
    return md_file


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="周度研报增量学习 Pipeline")
    sub = parser.add_subparsers(dest="cmd")

    # plan 子命令
    p_plan = sub.add_parser("plan", help="打印本周采集计划")
    p_plan.add_argument("--days", type=int, default=7)

    # run 子命令
    p_run = sub.add_parser("run", help="执行格式化 + 生成工作单")
    p_run.add_argument("--days", type=int, default=7)
    p_run.add_argument("--raw", default=None, help="原始采集文件路径")

    # status 子命令
    p_status = sub.add_parser("status", help="查看数据资产状态")

    args = parser.parse_args()

    if args.cmd == "plan":
        cmd_plan(args.days)
    elif args.cmd == "run":
        cmd_run(args.days, args.raw)
    elif args.cmd == "status":
        cmd_status()
    else:
        parser.print_help()
