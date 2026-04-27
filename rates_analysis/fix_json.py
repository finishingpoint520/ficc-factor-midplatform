"""修复 JSON 文件中的未转义双引号和控制字符 v2"""
import json
import re
import os

DATA_DIR = r"c:\Users\123cy\WorkBuddy\20260408090957\rates_analysis"
FILES = [
    'batch5_20260213_speech_units.json',
    'batch5_20260306_speech_units.json',
    'batch5_20260403_speech_units.json',
    'batch3_20250822_speech_units.json',
]


def fix_json_file(fpath):
    """读取原始字节，清除所有问题字符，修复未转义引号"""
    with open(fpath, 'rb') as f:
        raw = f.read()

    # Step 1: Remove all control characters (0x00-0x1F except 0x0A, 0x0D, 0x09)
    cleaned = bytearray()
    for b in raw:
        if b < 0x20 and b not in (0x0A, 0x0D, 0x09):
            continue
        cleaned.append(b)
    text = cleaned.decode('utf-8', errors='replace')

    # Step 2: Fix unescaped double quotes inside string values using state machine
    result = []
    i = 0
    in_string = False

    while i < len(text):
        ch = text[i]

        if not in_string:
            result.append(ch)
            if ch == '"':
                in_string = True
            i += 1
            continue

        # Inside a string
        if ch == '\\' and i + 1 < len(text):
            result.append(ch)
            result.append(text[i + 1])
            i += 2
            continue

        if ch == '"':
            # Check if this ends the string
            j = i + 1
            while j < len(text) and text[j] in ' \t':
                j += 1
            if j >= len(text) or text[j] in ':,]}':
                result.append(ch)
                in_string = False
            else:
                result.append('\\"')
            i += 1
            continue

        result.append(ch)
        i += 1

    text = ''.join(result)

    # Step 3: Fix trailing commas
    text = re.sub(r',(\s*[}\]])', r'\1', text)

    # Step 4: Parse and re-serialize
    data = json.loads(text)
    with open(fpath, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    return True


def main():
    for fname in FILES:
        fpath = os.path.join(DATA_DIR, fname)
        print(f"Processing: {fname}")
        try:
            fix_json_file(fpath)
            print(f"  FIXED OK")
        except Exception as e:
            print(f"  FAILED: {e}")


if __name__ == '__main__':
    main()
