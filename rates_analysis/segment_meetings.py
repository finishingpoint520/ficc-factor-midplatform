#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
segment_meetings.py - 按发言人切分纪要文本
零积分，纯脚本

用法：
  python segment_meetings.py
"""

import json
import re
from pathlib import Path

TEXTS_DIR = Path(r"c:\Users\123cy\WorkBuddy\20260408090957\rates_analysis\meeting_texts")
OUTPUT_DIR = Path(r"c:\Users\123cy\WorkBuddy\20260408090957\rates_analysis\meeting_segments")

# 已知的发言人姓名列表（从纪要中提取）
SPEAKERS = [
    "赵骥", "谢秋平", "张晶", "张迪", "杨义山", "李博良", "武玥",
    "姜之媛", "张帆", "高喆", "王本浩", "柴颖颖", "刘曼沁",
    "项墩伟", "沈文思", "徐天彤", "孔祥雨", "王俊华"
]

# 跳过的标记行（非发言内容）
SKIP_MARKERS = [
    "【参会人】", "【五因子打分】", "【会议达成共识】", "【总结】",
    "【研究员观点】", "【投资经理观点】", "市场核心矛盾：",
    "整体策略基调：", "具体品种操作建议："
]


def parse_date_from_filename(filename: str) -> str:
    """从文件名提取日期，如 weekly_2026-04-03.txt -> 2026-04-03"""
    m = re.search(r"(\d{4}-\d{2}-\d{2})", filename)
    return m.group(1) if m else "unknown"


def segment_text(text: str, meeting_date: str) -> list:
    """按发言人切分纪要文本，返回 segments 列表"""
    
    # 构建发言人正则：匹配 "姓名：" 或 "姓名:\n"（行首）
    speaker_pattern = re.compile(
        r"^(" + "|".join(re.escape(s) for s in SPEAKERS) + r")[:：]\s*$",
        re.MULTILINE
    )
    
    # 找到所有发言人位置
    matches = list(speaker_pattern.finditer(text))
    
    if not matches:
        print(f"  [WARN] 未找到发言人标记，跳过")
        return []
    
    segments = []
    for i, match in enumerate(matches):
        speaker = match.group(1)
        start = match.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        
        # 提取该发言人段落文本
        content = text[start:end].strip()
        
        # 跳过空段落
        if not content or len(content) < 20:
            continue
        
        # 进一步切分：按"结论："和"具体分析："拆分
        sub_segments = split_by_conclusion_analysis(content, speaker, meeting_date)
        segments.extend(sub_segments)
    
    return segments


def split_by_conclusion_analysis(content: str, speaker: str, meeting_date: str) -> list:
    """将发言内容按"结论"和"具体分析"拆分为独立段落"""
    
    segments = []
    
    # 检测是否有 结论/具体分析 结构
    conclusion_match = re.search(r"^(?:结论[：:]\s*)", content, re.MULTILINE)
    analysis_match = re.search(r"^(?:具体分析[：:]\s*)", content, re.MULTILINE)
    
    if conclusion_match and analysis_match:
        # 有明确的"结论"+"具体分析"结构
        conclusion_end = analysis_match.start()
        conclusion_text = content[conclusion_match.start():conclusion_end].strip()
        analysis_text = content[analysis_match.start():].strip()
        
        if len(conclusion_text) >= 20:
            segments.append({
                "speaker": speaker,
                "section": "结论",
                "text": conclusion_text,
                "char_count": len(conclusion_text),
                "meeting_date": meeting_date
            })
        if len(analysis_text) >= 20:
            segments.append({
                "speaker": speaker,
                "section": "具体分析",
                "text": analysis_text,
                "char_count": len(analysis_text),
                "meeting_date": meeting_date
            })
    elif conclusion_match:
        # 只有结论，没有具体分析
        conclusion_text = content[conclusion_match.start():].strip()
        if len(conclusion_text) >= 20:
            segments.append({
                "speaker": speaker,
                "section": "结论",
                "text": conclusion_text,
                "char_count": len(conclusion_text),
                "meeting_date": meeting_date
            })
    else:
        # 无明确结构，整段保留
        segments.append({
            "speaker": speaker,
            "section": "全文",
            "text": content,
            "char_count": len(content),
            "meeting_date": meeting_date
        })
    
    return segments


def main():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    
    txt_files = sorted(TEXTS_DIR.glob("weekly_*.txt"))
    
    stats = {}
    
    for txt_file in txt_files:
        date_str = parse_date_from_filename(txt_file.name)
        print(f"\n处理: {txt_file.name} (日期: {date_str})")
        
        text = txt_file.read_text(encoding="utf-8")
        
        # 去掉开头的会议标题行（第一行通常是日期+标题）
        lines = text.split("\n")
        # 找到第一个发言人之前的内容作为"会议共识"段落
        speaker_start = None
        for i, line in enumerate(lines):
            if any(line.startswith(s + "：") or line.startswith(s + ":") for s in SPEAKERS):
                speaker_start = i
                break
        
        # 提取共识部分（标题到第一个发言人之间）
        consensus_text = ""
        if speaker_start and speaker_start > 1:
            consensus_lines = []
            for line in lines[1:speaker_start]:
                line = line.strip()
                if line and not any(line.startswith(m) for m in SKIP_MARKERS):
                    consensus_lines.append(line)
            consensus_text = "\n".join(consensus_lines).strip()
        
        # 切分发言人段落
        segments = segment_text(text, date_str)
        
        # 如果有共识段落且足够长，添加为特殊段落
        if consensus_text and len(consensus_text) >= 30:
            segments.insert(0, {
                "speaker": "共识",
                "section": "会议共识",
                "text": consensus_text,
                "char_count": len(consensus_text),
                "meeting_date": date_str
            })
        
        # 添加序号
        for i, seg in enumerate(segments):
            seg["segment_id"] = f"{date_str}_{i+1:02d}"
        
        # 统计
        total_chars = sum(s["char_count"] for s in segments)
        print(f"  段落数: {len(segments)}, 总字符: {total_chars}")
        
        for seg in segments:
            marker = "*" if seg["char_count"] > 800 else ""
            print(f"    [{seg['segment_id']}] {seg['speaker']} - {seg['section']}: {seg['char_count']}字 {marker}")
        
        # 保存
        out_file = OUTPUT_DIR / f"segments_{date_str}.json"
        with open(out_file, "w", encoding="utf-8") as f:
            json.dump({
                "meeting_date": date_str,
                "source_file": txt_file.name,
                "total_segments": len(segments),
                "total_chars": total_chars,
                "segments": segments
            }, f, ensure_ascii=False, indent=2)
        
        stats[date_str] = {
            "segments": len(segments),
            "total_chars": total_chars,
            "output": str(out_file)
        }
    
    # 汇总
    print("\n" + "=" * 60)
    print("汇总:")
    total_segments = sum(s["segments"] for s in stats.values())
    total_chars = sum(s["total_chars"] for s in stats.values())
    print(f"  总纪要数: {len(stats)}")
    print(f"  总段落数: {total_segments}")
    print(f"  总字符数: {total_chars}")
    
    # 输出合并文件供后续标注使用
    all_segments = []
    for txt_file in txt_files:
        date_str = parse_date_from_filename(txt_file.name)
        seg_file = OUTPUT_DIR / f"segments_{date_str}.json"
        if seg_file.exists():
            with open(seg_file, "r", encoding="utf-8") as f:
                data = json.load(f)
            all_segments.extend(data["segments"])
    
    all_file = OUTPUT_DIR / "all_segments.json"
    with open(all_file, "w", encoding="utf-8") as f:
        json.dump({
            "total_segments": len(all_segments),
            "total_chars": sum(s["char_count"] for s in all_segments),
            "meetings": len(stats),
            "segments": all_segments
        }, f, ensure_ascii=False, indent=2)
    print(f"\n  合并文件: {all_file}")
    print(f"  产出目录: {OUTPUT_DIR}")


if __name__ == "__main__":
    main()
