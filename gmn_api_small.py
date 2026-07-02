import json
import time
import uuid
import re
import requests

def clean_text(text: str) -> str:
    """Clean the extracted text by removing code execution blocks and card content links."""
    text = re.sub(
        r'```(?:python|javascript|text)\?code_(?:reference|stdout)&code_event_index=\d+\n.*?```\n?',
        '', text, flags=re.DOTALL
    )
    text = re.sub(r'http://googleusercontent\.com/card_content/\d+\n?', '', text)
    return text.strip()

def extract_texts_from_line(line: str) -> list:
    """Parse a single wrb.fr line and return a list of text strings found."""
    if '"wrb.fr"' not in line or len(line) < 200:
        return []
    try:
        arr = json.loads(line)
        inner_str = arr[0][2]
        if not inner_str or len(inner_str) < 50:
            return []
        inner = json.loads(inner_str)
        if not (isinstance(inner, list) and len(inner) > 4 and inner[4]):
            return []
        texts = []
        for part in inner[4]:
            if isinstance(part, list) and len(part) > 1 and part[1] and isinstance(part[1], list):
                for t in part[1]:
                    if isinstance(t, str) and t:
                        texts.append(t)
        return texts
    except (json.JSONDecodeError, IndexError, TypeError):
        return []

def ask_gemini_direct(prompt: str, model: str = "gemini-3.5-flash", think_level: int = 4) -> str:
    """Send a direct request to Gemini StreamGenerate endpoint without any local proxy server."""
    # Model mapping based on Gemini web JS MODE_CATEGORY:
    # 1=FAST (gemini-3.5-flash)
    # 2=THINKING (gemini-3.5-flash-thinking)
    # 3=PRO (gemini-3.1-pro)
    # 4=AUTO (gemini-auto)
    # 5=FAST_DYNAMIC_THINKING (gemini-3.5-flash-thinking-lite)
    # 6=FLASH_LITE (gemini-flash-lite)
    model_map = {
        "gemini-3.5-flash": 1,
        "gemini-3.5-flash-thinking": 2,
        "gemini-3.1-pro": 3,
        "gemini-auto": 4,
        "gemini-3.5-flash-thinking-lite": 5,
        "gemini-flash-lite": 6
    }
    model_id = model_map.get(model, 1)
    
    # 1. Build payload array
    inner = [None] * 102
    inner[0] = [prompt, 0, None, None, None, None, 0]
    inner[1] = ["en"]
    inner[2] = ["", "", "", None, None, None, None, None, None, ""]
    inner[6] = [0]
    inner[7] = 1
    inner[10] = 1
    inner[11] = 0
    inner[17] = [[think_level]]
    inner[18] = 0
    inner[27] = 1
    inner[30] = [4]
    inner[41] = [2]
    inner[53] = 0
    inner[59] = str(uuid.uuid4())
    inner[61] = []
    inner[68] = 1
    inner[79] = model_id

    # Package as nested JSON string format required by Google
    outer = [None, json.dumps(inner)]
    payload_data = {"f.req": json.dumps(outer)}
    
    # 2. Build HTTP headers
    headers = {
        "Content-Type": "application/x-www-form-urlencoded",
        "Origin": "https://gemini.google.com",
        "Referer": "https://gemini.google.com/app",
        "X-Same-Domain": "1",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    }

    # 3. Request URL
    bl_version = "boq_assistant-bard-web-server_20260608.13_p0"
    reqid = int(time.time()) % 1000000
    url = f"https://gemini.google.com/_/BardChatUi/data/assistant.lamda.BardFrontendService/StreamGenerate?bl={bl_version}&hl=en&_reqid={reqid}&rt=c"

    # 4. Send request
    print(f"[*] Sending request for: '{prompt}' using '{model}'...")
    res = requests.post(url, data=payload_data, headers=headers, timeout=30)
    
    if res.status_code != 200:
        return f"Error HTTP {res.status_code}: {res.text[:300]}"

    # 5. Extract response text by finding the longest matched chunk
    last_text = ""
    for line in res.text.split("\n"):
        for t in extract_texts_from_line(line):
            if len(t) > len(last_text):
                last_text = t

    return clean_text(last_text)

if __name__ == "__main__":
    prompt = "give me simple python code to read a file and print its content?"
    response = ask_gemini_direct(prompt, model="gemini-3.5-flash")
    try:
        print(response)
    except UnicodeEncodeError:
        print(response.encode('utf-8', errors='replace').decode('utf-8'))