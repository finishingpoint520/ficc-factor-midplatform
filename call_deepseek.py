import requests
import json
import sys
import os

def main():
    # Load prompt file
    prompt_file = r"c:\Users\123cy\WorkBuddy\20260408090957\rates_analysis\_pending_research_learn_prompt.json"
    if not os.path.exists(prompt_file):
        print(f"Error: {prompt_file} not found")
        sys.exit(1)
    
    with open(prompt_file, "r", encoding="utf-8") as f:
        data = json.load(f)
    
    full_prompt = data.get("full_prompt", "")
    input_file = data.get("input_file", "")
    
    # Extract team_id from input_file name
    # Example: c:\...\2026-04-22_zhongtai_lv.txt
    basename = os.path.basename(input_file)
    # Remove date prefix and .txt suffix
    # Format: 2026-04-22_huatai_zhang.txt
    if "_" in basename and basename.endswith(".txt"):
        team_id = basename.split("_", 2)[2].replace(".txt", "")
    else:
        team_id = "unknown"
    
    print(f"Processing team: {team_id}")
    
    # Call DeepSeek API
    api_key = "sk-8ac52c042b3044e482404c8e58831d19"
    url = "https://api.deepseek.com/chat/completions"
    
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }
    
    payload = {
        "model": "deepseek-chat",
        "messages": [
            {"role": "system", "content": "你是一个债市研报结构化分析专家，严格按照给定格式输出 JSON。"},
            {"role": "user", "content": full_prompt}
        ],
        "temperature": 0.1,
        "max_tokens": 8192
    }
    
    print("Sending request to DeepSeek API...")
    response = requests.post(url, headers=headers, json=payload, timeout=120)
    
    if response.status_code != 200:
        print(f"API call failed: {response.status_code}")
        print(response.text)
        sys.exit(1)
    
    result = response.json()
    content = result["choices"][0]["message"]["content"]
    
    # Try to parse JSON from content
    # The response might contain markdown code fences ```json ... ```
    if "```json" in content:
        # Extract JSON between ```json and ```
        start = content.find("```json") + 7
        end = content.find("```", start)
        json_str = content[start:end].strip()
    elif "```" in content:
        # Maybe just ```
        start = content.find("```") + 3
        end = content.find("```", start)
        json_str = content[start:end].strip()
    else:
        json_str = content.strip()
    
    # Clean up: remove leading/trailing whitespace, newlines
    json_str = json_str.strip()
    
    # Try to parse
    try:
        parsed = json.loads(json_str)
    except json.JSONDecodeError as e:
        print(f"Failed to parse JSON: {e}")
        print("Raw content:")
        print(content)
        sys.exit(1)
    
    # Save response
    output_dir = r"c:\Users\123cy\WorkBuddy\20260408090957\rates_analysis\external_research"
    os.makedirs(output_dir, exist_ok=True)
    output_file = os.path.join(output_dir, f"{team_id}_response.json")
    
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(parsed, f, ensure_ascii=False, indent=2)
    
    print(f"Response saved to: {output_file}")
    print("\nPreview of extracted claim_atoms:")
    atoms = parsed.get("claim_atoms", [])
    for i, atom in enumerate(atoms[:3]):
        print(f"  {i+1}. {atom.get('factor_label', '')} - {atom.get('claim_text', '')[:80]}...")
    if len(atoms) > 3:
        print(f"  ... and {len(atoms)-3} more")
    
    # Also print alignment summary
    alignment = parsed.get("alignment_summary", {})
    if alignment:
        print("\nAlignment Summary:")
        print(f"  New factor candidates: {alignment.get('new_factor_candidates', [])}")
        print(f"  Reinforced chains: {alignment.get('reinforced_chains', [])}")
        print(f"  Conflicting views: {alignment.get('conflicting_views', [])}")

if __name__ == "__main__":
    main()