# 周度研报学习工作单 - 2026-04-22

生成时间：2026-04-22 09:04

## 采集结果汇总

- **华泰证券研究所 张继强**：3 条 → `2026-04-22_huatai_zhang.txt`
- **申银万国研究所 黄伟平**：3 条 → `2026-04-22_swhy_huang.txt`
- **中泰证券研究所 吕品**：2 条 → `2026-04-22_zhongtai_lv.txt`

## 待执行步骤

### Step 3 → LLM 标注（需积分）

为每个团队运行 `prepare` 命令，生成 LLM prompt：

```bash
# 华泰证券研究所 张继强
python "C:\Users\123cy\.workbuddy\skills\ficc-factor-midplatform\scripts\agents\research_learner.py" prepare --input "c:\Users\123cy\WorkBuddy\20260408090957\rates_analysis\external_research\formatted\2026-04-22_huatai_zhang.txt"
```

```bash
# 申银万国研究所 黄伟平
python "C:\Users\123cy\.workbuddy\skills\ficc-factor-midplatform\scripts\agents\research_learner.py" prepare --input "c:\Users\123cy\WorkBuddy\20260408090957\rates_analysis\external_research\formatted\2026-04-22_swhy_huang.txt"
```

```bash
# 中泰证券研究所 吕品
python "C:\Users\123cy\.workbuddy\skills\ficc-factor-midplatform\scripts\agents\research_learner.py" prepare --input "c:\Users\123cy\WorkBuddy\20260408090957\rates_analysis\external_research\formatted\2026-04-22_zhongtai_lv.txt"
```

### Step 4 → Agent 执行 LLM

读取 `_pending_research_learn_prompt.json`，送入大模型，将返回 JSON 保存为 `<team_id>_response.json`。

### Step 5 → 写入原子库（零积分）

```bash
python "C:\Users\123cy\.workbuddy\skills\ficc-factor-midplatform\scripts\agents\research_learner.py" save --input <response.json> --institution "<机构名>"
```

### Step 6 → 更新因果图谱（零积分）

```bash
python "c:\Users\123cy\WorkBuddy\20260408090957\rates_analysis\enrich_causal_edges.py"
```

### Step 7 → 生成本周决策摘要（零积分）

```bash
python "C:\Users\123cy\.workbuddy\skills\ficc-factor-midplatform\scripts\agents\decision_engine.py" render --date 2026-04-22
```

---
完整工作单 JSON：`weekly_plan_2026-04-22.json`