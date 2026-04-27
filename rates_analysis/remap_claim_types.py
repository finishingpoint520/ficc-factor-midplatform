"""
remap_claim_types.py
将 455 个存量 claim_atoms 的 claim_type 从旧 5 类映射到新 8 类。

旧 5 类：推论、信号、事实、预期、修正
新 8 类：事实判断、方向判断、因果链条、验证指标、交易表达、风险提示、条件触发判断、反例/冲突观点

映射策略：
1. 事实 → 事实判断（直接）
2. 预期 → 方向判断（直接）
3. 信号 → 验证指标（直接）
4. 修正 → 反例/冲突观点（直接）
5. 推论 → 按内容特征细分：
   - 有 validation_metrics 且非空 → 验证指标
   - 有 trade_translation 且非空 → 交易表达
   - 包含风险关键词 → 风险提示
   - 包含条件/如果/假设/前提 → 条件触发判断
   - 有 causal_chain_text 且非空 → 因果链条
   - 默认 → 方向判断

零积分执行：纯 Python 字符串匹配，不调大模型。
"""
import json
import os
import re
from datetime import datetime
from pathlib import Path
from collections import Counter

# ====== 配置 ======
BASE_DIR = Path(__file__).parent
CLAIM_ATOMS_DIR = BASE_DIR / "claim_atoms"
ALL_ATOMS_FILE = CLAIM_ATOMS_DIR / "all_claim_atoms.json"

# ====== 关键词列表 ======
RISK_KEYWORDS = [
    "风险", "止损", "警惕", "谨慎", "不确定性", "尾部", "回撤", "亏损",
    "踩踏", "赎回", "流动性风险", "信用风险", "违约", "恐慌", "挤兑",
    "保本", "防御", "安全垫", "压力", "脆弱", "泡沫", "过热", "反向",
    "追高", "踩雷", "爆仓", "利空", "空头", "做空"
]

CONDITION_KEYWORDS = [
    "如果", "假设", "前提是", "条件", "若", "一旦", "只要", "除非",
    "取决于", "在...情况下", "当...时", "需要满足", "以...为条件",
    "前提", "触发", "情形", "情景", "路径"
]

# ====== 映射函数 ======
def contains_any(text, keywords):
    """检查文本是否包含任一关键词"""
    if not text:
        return False
    return any(kw in text for kw in keywords)


def remap_atom(atom):
    """对单个 atom 进行 claim_type 重新映射"""
    old_type = atom.get("claim_type", "")
    raw = atom.get("raw_text", "") or ""
    summary = atom.get("summary_text", "") or ""
    combined = raw + summary

    # 直接映射的 4 类
    direct_map = {
        "事实": "事实判断",
        "预期": "方向判断",
        "信号": "验证指标",
        "修正": "反例/冲突观点",
    }

    if old_type in direct_map:
        return direct_map[old_type], "direct"

    if old_type != "推论":
        # 未知旧类型，默认映射为方向判断
        return "方向判断", "fallback_unknown"

    # ====== 推论类的细分逻辑 ======
    # 优先级 1：有 validation_metrics 且非空 → 验证指标
    metrics = atom.get("validation_metrics", [])
    if metrics and len(metrics) > 0:
        return "验证指标", "inference→验证指标(metrics)"

    # 优先级 2：有 trade_translation 且非空 → 交易表达
    trade = atom.get("trade_translation", "")
    if trade and trade.strip():
        return "交易表达", "inference→交易表达(trade)"

    # 优先级 3：包含条件/假设关键词 → 条件触发判断
    if contains_any(combined, CONDITION_KEYWORDS):
        return "条件触发判断", "inference→条件触发(condition_kw)"

    # 优先级 4：包含风险关键词 → 风险提示
    if contains_any(combined, RISK_KEYWORDS):
        return "风险提示", "inference→风险提示(risk_kw)"

    # 优先级 5：有 causal_chain_text 且非空 → 因果链条
    chain = atom.get("causal_chain_text", "")
    if chain and chain.strip():
        return "因果链条", "inference→因果链条(causal)"

    # 默认：方向判断
    return "方向判断", "inference→方向判断(default)"


def main():
    # 读取汇总文件
    print(f"读取 {ALL_ATOMS_FILE} ...")
    with open(ALL_ATOMS_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)

    atoms = data["claim_atoms"]
    print(f"共 {len(atoms)} 个 claim_atoms")

    # 统计旧分布
    old_dist = Counter(a["claim_type"] for a in atoms)
    print(f"\n旧分布: {dict(old_dist.most_common())}")

    # 执行映射
    remap_reasons = Counter()
    now_str = datetime.now().isoformat()

    for atom in atoms:
        new_type, reason = remap_atom(atom)
        atom["claim_type"] = new_type
        atom["updated_at"] = now_str
        remap_reasons[reason] += 1

    # 统计新分布
    new_dist = Counter(a["claim_type"] for a in atoms)
    print(f"\n新分布: {dict(new_dist.most_common())}")
    print(f"\n映射原因分布: {dict(remap_reasons.most_common())}")

    # 检查是否覆盖所有 8 类
    expected_types = {"事实判断", "方向判断", "因果链条", "验证指标", "交易表达", "风险提示", "条件触发判断", "反例/冲突观点"}
    missing = expected_types - set(new_dist.keys())
    if missing:
        print(f"\n[WARNING] 未覆盖的类型: {missing}")

    # 写回汇总文件
    data["version"] = "1.1.0"
    data["remap_date"] = datetime.now().strftime("%Y-%m-%d")
    data["remap_notes"] = "claim_type 从 5 类(推论/信号/事实/预期/修正) 映射到 8 类(事实判断/方向判断/因果链条/验证指标/交易表达/风险提示/条件触发判断/反例/冲突观点)"

    with open(ALL_ATOMS_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print(f"\n已写入 {ALL_ATOMS_FILE}")

    # 更新 47 个单文件
    single_files = sorted(CLAIM_ATOMS_DIR.glob("batch*_claim_atoms.json"))
    print(f"\n更新 {len(single_files)} 个单文件...")
    updated_count = 0
    for sf in single_files:
        with open(sf, "r", encoding="utf-8") as f:
            batch = json.load(f)

        if isinstance(batch, list):
            batch_atoms = batch
        elif isinstance(batch, dict) and "claim_atoms" in batch:
            batch_atoms = batch["claim_atoms"]
        else:
            print(f"  跳过 {sf.name}（格式未知）")
            continue

        changed = 0
        for atom in batch_atoms:
            old_type = atom.get("claim_type", "")
            new_type, _ = remap_atom_from_old(atom) if hasattr(remap_atom_from_old, '__call__') else (old_type, "")
            if new_type != old_type:
                atom["claim_type"] = new_type
                atom["updated_at"] = now_str
                changed += 1

        with open(sf, "w", encoding="utf-8") as f:
            json.dump(batch, f, ensure_ascii=False, indent=2)
        updated_count += 1
        if changed > 0:
            print(f"  {sf.name}: {changed} 条已更新")
        else:
            print(f"  {sf.name}: 无需更新")

    print(f"\n完成！共更新 {updated_count} 个单文件。")

    # 输出详细映射报告
    print("\n" + "=" * 60)
    print("映射详细报告")
    print("=" * 60)
    for reason, count in remap_reasons.most_common():
        print(f"  {reason}: {count} 条")


def remap_atom_from_old(atom):
    """同 remap_atom，但用于单文件更新"""
    return remap_atom(atom)


if __name__ == "__main__":
    main()
