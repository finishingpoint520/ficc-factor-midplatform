"""
因子清单与共现矩阵提取脚本 v2
处理三种 JSON 格式：
  - batch1-batch4: primary_factor + secondary_factors(数组) + tertiary_factors(数组)
  - batch5早期(1205-1226): primary_factor + secondary_factor(单值字符串)
  - batch5后期(0109+): 无因子字段，跳过
输出：factor_cooccurrence.json
"""

import json
import os
import re
from collections import Counter, defaultdict
from itertools import combinations

DATA_DIR = r"c:\Users\123cy\WorkBuddy\20260408090957\rates_analysis"
OUTPUT_FILE = os.path.join(DATA_DIR, "factor_cooccurrence.json")

# 归一化一级因子名称
PF_NORMALIZE = {
    "基本面因子": "基本面",
    "政策面因子": "政策面",
    "流动性因子": "流动性",
    "市场情绪因子": "市场情绪",
    "机构行为因子": "机构行为",
    "资金面因子": "资金面",
    "基本面": "基本面",
    "政策面": "政策面",
    "流动性": "流动性",
    "市场情绪": "市场情绪",
    "机构行为": "机构行为",
    "资金面": "资金面",
}

# 数据容器
primary_to_secondary = defaultdict(lambda: defaultdict(int))
secondary_counter = Counter()
primary_counter = Counter()
meeting_secondary_map = {}
meeting_primary_map = {}
secondary_to_primary = {}
secondary_meetings = defaultdict(set)
factor_speaker_map = defaultdict(lambda: defaultdict(set))

# 三级因子（涌现因子）容器
tertiary_counter = Counter()
tertiary_to_secondary = {}
tertiary_meetings = defaultdict(set)
meeting_tertiary_map = {}


def normalize_pf(raw):
    return PF_NORMALIZE.get(raw, raw.strip().replace("因子", ""))


def extract_meeting_key(filepath):
    basename = os.path.basename(filepath)
    match = re.search(r"(\d{8})", basename)
    return match.group(1) if match else basename


def process_batch1_to_batch4(data, meeting_key):
    """batch1-batch4: secondary_factors 是数组"""
    units = data.get("speech_units", [])
    local_sec = set()
    local_pri = set()
    local_ter = set()

    for unit in units:
        pf = normalize_pf(unit.get("primary_factor", ""))
        sec_list = unit.get("secondary_factors", [])
        ter_list = unit.get("tertiary_factors", [])
        speaker = unit.get("speaker", "")

        if not pf:
            continue

        primary_counter[pf] += 1

        if isinstance(sec_list, list):
            for sf in sec_list:
                sf = sf.strip()
                if sf:
                    secondary_counter[sf] += 1
                    primary_to_secondary[pf][sf] += 1
                    secondary_to_primary[sf] = pf
                    local_sec.add(sf)
                    secondary_meetings[sf].add(meeting_key)
                    if speaker:
                        factor_speaker_map[sf][meeting_key].add(speaker)

        if isinstance(ter_list, list):
            for tf in ter_list:
                tf = tf.strip()
                if tf and len(tf) > 2:
                    tertiary_counter[tf] += 1
                    local_ter.add(tf)
                    tertiary_meetings[tf].add(meeting_key)
                    # 映射到最近的二级因子
                    for sf in (sec_list if isinstance(sec_list, list) else []):
                        if sf.strip():
                            tertiary_to_secondary[tf] = sf.strip()
                            break

        local_pri.add(pf)

    return local_sec, local_pri, local_ter


def process_batch5_early(data, meeting_key):
    """batch5早期: secondary_factor 是一级因子交叉; batch1-batch2: secondary_factor 是真正的二级因子"""
    units = data.get("speech_units", [])
    local_sec = set()
    local_pri = set()

    for unit in units:
        pf = normalize_pf(unit.get("primary_factor", ""))
        sf = unit.get("secondary_factor", "")
        speaker = unit.get("speaker", "")

        if not pf:
            continue

        primary_counter[pf] += 1
        local_pri.add(pf)

        if isinstance(sf, str) and sf.strip():
            sf_stripped = sf.strip()
            sf_normalized = normalize_pf(sf_stripped)

            # 判断 sf 是一级因子名还是二级因子名
            # 如果 sf 归一化后恰好是五个标准一级因子之一，且与当前 pf 不同
            # → 这是一级因子交叉（batch5 early 格式）
            # 否则 → 这是真正的二级因子（batch1-batch2 格式）
            standard_primaries = {"基本面", "政策面", "流动性", "市场情绪", "机构行为"}
            if sf_normalized in standard_primaries:
                # 一级因子交叉 - 只记录交叉关系，不计入二级因子
                local_pri.add(sf_normalized)
            else:
                # 真正的二级因子
                secondary_counter[sf_stripped] += 1
                primary_to_secondary[pf][sf_stripped] += 1
                secondary_to_primary[sf_stripped] = pf
                local_sec.add(sf_stripped)
                secondary_meetings[sf_stripped].add(meeting_key)
                if speaker:
                    factor_speaker_map[sf_stripped][meeting_key].add(speaker)

    return local_sec, local_pri, set()


def main():
    files = sorted([
        f for f in os.listdir(DATA_DIR)
        if f.endswith("_speech_units.json")
    ])

    print(f"找到 {len(files)} 份 speech_units.json 文件\n")

    stats = {"ok": 0, "no_factors": 0, "error": 0}

    for fname in files:
        filepath = os.path.join(DATA_DIR, fname)
        meeting_key = extract_meeting_key(filepath)

        try:
            with open(filepath, "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception as e:
            print(f"  [ERR] {meeting_key}: {e}")
            stats["error"] += 1
            continue

        units = data.get("speech_units", [])
        if not units:
            print(f"  [SKIP] {meeting_key}: 无 speech_units")
            continue

        # 检测格式
        has_secondary_factors_arr = False
        has_secondary_factor_str = False

        for unit in units:
            sf = unit.get("secondary_factors")
            if isinstance(sf, list) and len(sf) > 0:
                has_secondary_factors_arr = True
                break
            sf2 = unit.get("secondary_factor")
            if isinstance(sf2, str) and sf2.strip():
                has_secondary_factor_str = True

        if has_secondary_factors_arr:
            local_sec, local_pri, local_ter = process_batch1_to_batch4(
                data, meeting_key
            )
            if local_sec:
                meeting_secondary_map[meeting_key] = local_sec
                meeting_primary_map[meeting_key] = local_pri
            if local_ter:
                meeting_tertiary_map[meeting_key] = local_ter
            print(
                f"  [OK]   {meeting_key}: "
                f"{len(local_sec)} 二级因子, {len(local_ter)} 三级因子, "
                f"{len(units)} 发言单元"
            )
            stats["ok"] += 1

        elif has_secondary_factor_str:
            local_sec, local_pri, _ = process_batch5_early(data, meeting_key)
            if local_sec:
                meeting_secondary_map[meeting_key] = local_sec
                meeting_primary_map[meeting_key] = local_pri
            print(
                f"  [B5E]  {meeting_key}: "
                f"{len(local_sec)} 二级因子, {len(units)} 发言单元"
            )
            stats["ok"] += 1
        else:
            print(f"  [SKIP] {meeting_key}: 无因子标注字段")
            stats["no_factors"] += 1

    # ==================== 共现矩阵 ====================
    print(f"\n{'='*60}")
    print("共现矩阵构建")
    print(f"{'='*60}")

    # 二级因子共现
    cooccurrence = Counter()
    for meeting_key, factors in meeting_secondary_map.items():
        for f1, f2 in combinations(sorted(factors), 2):
            cooccurrence[(f1, f2)] += 1

    # 一级因子共现
    primary_cooccurrence = Counter()
    for meeting_key, factors in meeting_primary_map.items():
        for f1, f2 in combinations(sorted(factors), 2):
            primary_cooccurrence[(f1, f2)] += 1

    # ==================== 统计汇总 ====================
    all_secondary = sorted(secondary_counter.keys())
    all_primary = sorted(primary_counter.keys())

    print(f"\n一级因子 ({len(all_primary)} 个):")
    for pf in all_primary:
        subs = primary_to_secondary[pf]
        print(f"  {pf}: {primary_counter[pf]} 次 -> {len(subs)} 个二级因子")

    print(f"\n二级因子 ({len(all_secondary)} 个), TOP20:")
    for sf, cnt in secondary_counter.most_common(20):
        pf = secondary_to_primary.get(sf, "未知")
        meetings = len(secondary_meetings[sf])
        speakers = list(
            set().union(*factor_speaker_map[sf].values())
        )[:5]
        print(f"  [{pf}] {sf}: {cnt}次 / {meetings}场 / 发言人:{speakers}")

    print(f"\n三级因子(涌现): {len(tertiary_counter)} 个, TOP15:")
    for tf, cnt in tertiary_counter.most_common(15):
        parent = tertiary_to_secondary.get(tf, "无父级")
        meetings = len(tertiary_meetings[tf])
        print(f"  {tf}: {cnt}次 / {meetings}场 (父级: {parent})")

    print(f"\n共现边: {len(cooccurrence)} 对")
    print(f"\n--- TOP30 共现因子对 ---")
    for i, ((f1, f2), cnt) in enumerate(cooccurrence.most_common(30)):
        pf1 = secondary_to_primary.get(f1, "?")
        pf2 = secondary_to_primary.get(f2, "?")
        cross = " [跨一级]" if pf1 != pf2 else ""
        print(f"  {i+1:2d}. {f1}({pf1}) x {f2}({pf2}): {cnt}次{cross}")

    # ==================== 输出 ====================
    output = {
        "metadata": {
            "description": "五因子框架 - 二级/三级因子清单与会议级共现矩阵",
            "total_files_scanned": len(files),
            "files_processed": stats["ok"],
            "files_skipped_no_factors": stats["no_factors"],
            "files_error": stats["error"],
            "total_primary_mentions": sum(primary_counter.values()),
            "unique_primary_factors": len(all_primary),
            "unique_secondary_factors": len(all_secondary),
            "unique_tertiary_factors": len(tertiary_counter),
            "total_cooccurrence_pairs": len(cooccurrence),
        },
        "primary_factors": {
            pf: {
                "count": primary_counter[pf],
                "secondary_factors": dict(
                    sorted(primary_to_secondary[pf].items(), key=lambda x: -x[1])
                ),
            }
            for pf in all_primary
        },
        "secondary_factor_inventory": [
            {
                "name": sf,
                "primary_factor": secondary_to_primary.get(sf, "未知"),
                "total_mentions": secondary_counter[sf],
                "meeting_count": len(secondary_meetings[sf]),
                "speakers": sorted(
                    set().union(*factor_speaker_map[sf].values())
                )[:10],
            }
            for sf in sorted(
                all_secondary, key=lambda x: -secondary_counter[x]
            )
        ],
        "tertiary_factor_inventory": [
            {
                "name": tf,
                "parent_secondary": tertiary_to_secondary.get(tf, ""),
                "total_mentions": tertiary_counter[tf],
                "meeting_count": len(tertiary_meetings[tf]),
            }
            for tf in sorted(
                tertiary_counter.keys(), key=lambda x: -tertiary_counter[x]
            )
        ],
        "cooccurrence_matrix": {
            "description": "两个二级因子在同一会议中同时出现的频次",
            "total_pairs": len(cooccurrence),
            "pairs": [
                {
                    "factor1": f1,
                    "factor2": f2,
                    "count": cnt,
                    "factor1_primary": secondary_to_primary.get(f1, ""),
                    "factor2_primary": secondary_to_primary.get(f2, ""),
                    "cross_primary": secondary_to_primary.get(f1, "")
                    != secondary_to_primary.get(f2, ""),
                }
                for (f1, f2), cnt in cooccurrence.most_common()
            ],
        },
        "primary_cooccurrence": {
            "description": "两个一级因子在同一会议中同时出现的频次",
            "pairs": [
                {"factor1": f1, "factor2": f2, "count": cnt}
                for (f1, f2), cnt in primary_cooccurrence.most_common()
            ],
        },
        "meeting_factor_map": {
            k: sorted(v) for k, v in sorted(meeting_secondary_map.items())
        },
    }

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    print(f"\n输出文件: {OUTPUT_FILE}")
    print(f"\n[统计摘要]")
    print(f"  处理文件: {stats['ok']} / 跳过: {stats['no_factors']} / 错误: {stats['error']}")
    print(f"  一级因子: {len(all_primary)} 个")
    print(f"  二级因子: {len(all_secondary)} 个")
    print(f"  三级因子(涌现): {len(tertiary_counter)} 个")
    print(f"  共现边: {len(cooccurrence)} 对")


if __name__ == "__main__":
    main()
