#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
fetch_research.py - 从 iFind 采集六大债市研究团队的最新研报观点
用法:
  python fetch_research.py [--days 7] [--output raw_research_YYYYMMDD.json]

说明:
  依赖 iFind MCP search_news 接口（通过工作区 MCP client 调用）
  本脚本生成标准化的研报片段 JSON，供 weekly_research_pipeline.py 消费
"""

import json
import os
import sys
from datetime import datetime, timedelta
from pathlib import Path

# ─────────────────────────────────────────────
# 六大研究团队配置
# 每个 entry: name, institution, queries
# queries: 用于 iFind search_news 的关键词列表（多路覆盖）
# ─────────────────────────────────────────────
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
# 输出目录
# ─────────────────────────────────────────────
ASSETS_DIR = Path(r"c:\Users\123cy\WorkBuddy\20260408090957\rates_analysis")
RAW_DIR = ASSETS_DIR / "external_research" / "raw"
RAW_DIR.mkdir(parents=True, exist_ok=True)


def build_date_range(days_back: int = 7):
    """生成采集的时间范围（time_start, time_end）"""
    today = datetime.now()
    start = today - timedelta(days=days_back)
    return start.strftime("%Y-%m-%d"), today.strftime("%Y-%m-%d")


def fetch_team_news(team: dict, time_start: str, time_end: str, size: int = 8) -> list:
    """
    通过 iFind MCP search_news 采集单个团队的研报片段。

    注意：本函数在 AI Agent 环境中通过 MCP 调用工具执行。
    在独立 Python 环境中调用时，需要通过 MCP client 或 API wrapper 执行。
    
    返回: list of news_item dicts
    """
    results = []
    seen_titles = set()

    for query in team["queries"]:
        # 构建 MCP 调用参数
        call_params = {
            "query": query,
            "time_start": time_start,
            "time_end": time_end,
            "size": size
        }

        # ── 在 AI Agent 环境中，由 Agent 直接调用 iFind MCP ──
        # 这里记录调用意图，实际执行由 Agent 在 weekly_research_pipeline 中完成
        results.append({
            "_mcp_call": True,
            "tool": "hexin-ifind-ds-news-mcp/search_news",
            "params": call_params,
            "team_id": team["id"],
            "team_name": team["name"],
            "institution": team["institution"],
        })

    return results


def build_fetch_plan(days_back: int = 7) -> dict:
    """
    构建本周采集计划（不实际调用，输出调用清单供 Agent 执行）
    """
    time_start, time_end = build_date_range(days_back)
    today = datetime.now().strftime("%Y%m%d")

    plan = {
        "plan_date": datetime.now().isoformat(),
        "time_start": time_start,
        "time_end": time_end,
        "teams": [],
        "output_file": str(RAW_DIR / f"raw_research_{today}.json"),
    }

    for team in TEAMS:
        team_plan = {
            "team_id": team["id"],
            "name": team["name"],
            "institution": team["institution"],
            "queries": team["queries"],
            "time_start": time_start,
            "time_end": time_end,
            "size_per_query": 8,
        }
        plan["teams"].append(team_plan)

    return plan


def merge_and_deduplicate(all_items: list) -> list:
    """去重：按标题+日期去重，保留最丰富的版本"""
    seen = {}
    for item in all_items:
        key = (item.get("资讯标题", ""), item.get("日期", ""))
        if key not in seen:
            seen[key] = item
        else:
            # 保留内容更长的版本
            if len(item.get("资讯内容", "")) > len(seen[key].get("资讯内容", "")):
                seen[key] = item
    return list(seen.values())


def save_raw_research(items: list, team_meta: dict, output_file: str):
    """保存原始采集结果"""
    output_path = Path(output_file)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    data = {
        "fetch_date": datetime.now().isoformat(),
        "total_items": len(items),
        "team_meta": team_meta,
        "items": items,
    }

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    print(f"已保存 {len(items)} 条原始研报片段 → {output_path}")
    return str(output_path)


def format_for_learner(items: list, team_id: str, institution: str, author: str) -> str:
    """
    将 iFind 返回的 news_items 格式化为 research_learner.py 可消费的纯文本研报格式
    """
    lines = [
        f"# 外部研报 - {institution} {author}",
        f"# 来源：iFind 研报观点聚合",
        f"# 采集日期：{datetime.now().strftime('%Y-%m-%d')}",
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


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="生成 iFind 研报采集计划")
    parser.add_argument("--days", type=int, default=7, help="采集最近 N 天（默认 7）")
    parser.add_argument("--output", default=None, help="计划文件输出路径")
    args = parser.parse_args()

    plan = build_fetch_plan(args.days)

    # 输出采集计划
    plan_file = args.output or str(
        RAW_DIR / f"fetch_plan_{datetime.now().strftime('%Y%m%d')}.json"
    )
    with open(plan_file, "w", encoding="utf-8") as f:
        json.dump(plan, f, ensure_ascii=False, indent=2)

    print(f"采集计划已生成: {plan_file}")
    print(f"时间范围: {plan['time_start']} → {plan['time_end']}")
    print(f"涵盖团队 ({len(plan['teams'])} 个):")
    for t in plan["teams"]:
        print(f"  - {t['institution']} {t['name']}（{len(t['queries'])} 条查询）")
    print()
    print("下一步：运行 weekly_research_pipeline.py 执行采集 + 学习")
