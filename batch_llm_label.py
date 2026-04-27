#!/usr/bin/env python3
import json
import os
import requests
import subprocess
import sys
from pathlib import Path

ASSETS_DIR = Path(r"c:\Users\123cy\WorkBuddy\20260408090957\rates_analysis")
FORMATTED_DIR = ASSETS_DIR / "external_research" / "formatted"
OUTPUT_DIR = ASSETS_DIR / "external_research"
SKILL_DIR = Path(r"C:\Users\123cy\.workbuddy\skills\ficc-factor-midplatform")
RESEARCH_LEARNER = SKILL_DIR / "scripts" / "agents" / "research_learner.py"

DEEPSEEK_API_KEY = "sk-8ac52c042b3044e482404c8e58831d19"
DEEPSEEK_URL = "https://api.deepseek.com/chat/completions"

def call_deepseek(prompt_text, team_id):
    """调用 DeepSeek API，返回解析后的 JSON"""
    headers = {
        "Authorization": f"Bearer {DEEPSEEK_API_KEY}",
        "Content-Type": "application/json"
    }
    payload = {
        "model": "deepseek-chat",
        "messages": [
            {"role": "system", "content": "你是一个债市研报结构化分析专家，严格按照给定格式输出 JSON。"},
            {"role": "user", "content": prompt_text}
        ],
        "temperature": 0.1,
        "max_tokens": 8192
    }
    
    print(f"  Sending request to DeepSeek API for {team_id}...")
    resp = requests.post(DEEPSEEK_URL, headers=headers, json=payload, timeout=120)
    if resp.status_code != 200:
        raise RuntimeError(f"API call failed: {resp.status_code}\n{resp.text}")
    
    content = resp.json()["choices"][0]["message"]["content"]
    
    # 提取 JSON
    if "```json" in content:
        start = content.find("```json") + 7
        end = content.find("```", start)
        json_str = content[start:end].strip()
    elif "```" in content:
        start = content.find("```") + 3
        end = content.find("```", start)
        json_str = content[start:end].strip()
    else:
        json_str = content.strip()
    
    return json.loads(json_str)

def main():
    # 找到所有格式化文件
    files = list(FORMATTED_DIR.glob("2026-04-22_*.txt"))
    print(f"Found {len(files)} formatted files")
    
    for f in files:
        # 提取 team_id
        # 格式: 2026-04-22_huatai_zhang.txt
        basename = f.stem  # 2026-04-22_huatai_zhang
        team_id = basename.split("_", 2)[2]  # huatai_zhang
        print(f"\n--- Processing {team_id} ---")
        
        # Step 1: 运行 prepare 生成 prompt
        print(f"  Running prepare...")
        cmd = [sys.executable, str(RESEARCH_LEARNER), "prepare", "--input", str(f)]
        result = subprocess.run(cmd, cwd=ASSETS_DIR, capture_output=True, text=True, encoding="utf-8")
        if result.returncode != 0:
            print(f"  Prepare failed: {result.stderr}")
            continue
        
        # 读取生成的 prompt
        prompt_file = ASSETS_DIR / "_pending_research_learn_prompt.json"
        if not prompt_file.exists():
            print(f"  Prompt file not found")
            continue
        
        with open(prompt_file, "r", encoding="utf-8") as pf:
            prompt_data = json.load(pf)
        
        prompt_text = prompt_data.get("full_prompt", "")
        
        # Step 2: 调用 LLM
        try:
            response_json = call_deepseek(prompt_text, team_id)
        except Exception as e:
            print(f"  LLM call failed: {e}")
            continue
        
        # Step 3: 保存响应
        output_file = OUTPUT_DIR / f"{team_id}_response.json"
        with open(output_file, "w", encoding="utf-8") as out:
            json.dump(response_json, out, ensure_ascii=False, indent=2)
        
        print(f"  Saved response to {output_file.name}")
        
        # 打印摘要
        atoms = response_json.get("claim_atoms", [])
        alignment = response_json.get("alignment_summary", {})
        print(f"    Extracted {len(atoms)} claim atoms")
        if alignment.get("new_factor_candidates"):
            print(f"    New factor candidates: {alignment['new_factor_candidates']}")
        if alignment.get("reinforced_chains"):
            print(f"    Reinforced chains: {alignment['reinforced_chains']}")
    
    print("\n--- Batch processing complete ---")

if __name__ == "__main__":
    main()