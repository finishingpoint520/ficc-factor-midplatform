#!/usr/bin/env python3
"""Batch generate prompts for all 3 teams and create a review file."""
import json
import sys
from pathlib import Path

sys.path.insert(0, r"C:\Users\123cy\.workbuddy\skills\ficc-factor-midplatform\scripts\agents")
from research_learner import cmd_prepare

BASE = Path(r"c:\Users\123cy\WorkBuddy\20260408090957\rates_analysis")

teams = [
    ("external_research/formatted/2026-04-22_huatai_zhang.txt", "华泰 张继强"),
    ("external_research/formatted/2026-04-22_swhy_huang.txt", "申万 黄伟平"),
    ("external_research/formatted/2026-04-22_zhongtai_lv.txt", "中泰 吕品"),
]

all_prompts = []
for rel_path, name in teams:
    fpath = str(BASE / rel_path)
    cmd_prepare(fpath)
    p = json.load(open(BASE / "_pending_research_learn_prompt.json", encoding="utf-8"))
    all_prompts.append({
        "team": name,
        "file": rel_path,
        "prompt": p["full_prompt"],
        "created_at": p["created_at"]
    })

# Save combined review file
out_path = BASE / "external_research" / "weekly_reports" / "phase_a_prompt_review_2026-04-22.md"
with open(out_path, "w", encoding="utf-8") as f:
    f.write("# Phase A - LLM Prompt 审阅稿 (2026-04-22)\n\n")
    f.write("> 零积分生成。审阅确认后进入 Phase B 送入大模型标注。\n\n")
    for item in all_prompts:
        f.write("---\n\n")
        f.write("## " + item["team"] + "\n\n")
        f.write("**源文件**: `" + item["file"] + "`  \n")
        f.write("**生成时间**: " + item["created_at"] + "\n\n")
        prompt = item["prompt"]
        f.write("### Prompt 内容\n\n")
        f.write("<details><summary>点击展开完整 prompt</summary>\n\n")
        f.write("```text\n")
        f.write(prompt)
        f.write("\n```\n\n</details>\n\n")

print(f"Review file saved to: {out_path}")
print(f"Total teams: {len(all_prompts)}")
for item in all_prompts:
    print(f"  {item['team']}: {len(item['prompt'])} chars")
