import json
import time
import uuid
import re
import os
import hashlib

# Try to use curl-cffi for browser TLS fingerprint impersonation to bypass Google 1076/1099 blocks
try:
    from curl_cffi import requests
    HAS_CURL_CFFI = True
except ImportError:
    import requests
    HAS_CURL_CFFI = False

# Default backup version identifier if fetching fails
DEFAULT_BL_VERSION = "boq_assistant-bard-web-server_20260609.21_p0"
_cached_bl_version = None

# Paths resolved relative to this script's directory
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
COOKIES_FILE = os.path.join(BASE_DIR, "cookies.txt")
SESSION_CACHE_FILE = os.path.join(BASE_DIR, "session_cache.json")

def get_latest_bl_version() -> str:
    """Fetch the latest active backend build version (bl) from Gemini homepage."""
    global _cached_bl_version
    if _cached_bl_version:
        return _cached_bl_version
    try:
        headers = {"User-Agent": "Mozilla/5.0"}
        res = requests.get("https://gemini.google.com/app", headers=headers, timeout=10)
        match = re.search(r'boq_assistant-bard-web-server_[0-9\._p]+', res.text)
        if match:
            _cached_bl_version = match.group(0)
            return _cached_bl_version
    except Exception:
        pass
    return DEFAULT_BL_VERSION

def load_cookies() -> str:
    """Load session cookies from local file or environment variable."""
    if os.path.exists(COOKIES_FILE):
        try:
            with open(COOKIES_FILE, "r", encoding="utf-8") as f:
                return f.read().strip()
        except Exception:
            pass
    return os.environ.get("GEMINI_COOKIE", "")

def get_sapisid_from_cookies(cookies_str: str) -> str:
    """Extract the SAPISID cookie value from the cookies string."""
    if not cookies_str:
        return ""
    try:
        pairs = dict(p.split("=", 1) for p in cookies_str.split("; ") if "=" in p)
        return pairs.get("SAPISID", "")
    except Exception:
        return ""

def make_sapisidhash(sapisid: str) -> str:
    """Generate the SAPISIDHASH signature required by Google when cookies are present."""
    ts = int(time.time())
    h = hashlib.sha1(f"{ts} {sapisid} https://gemini.google.com".encode()).hexdigest()
    return f"SAPISIDHASH {ts}_{h}"

def load_session_data() -> dict:
    """Load cached session ID and XSRF token from session_cache.json."""
    if os.path.exists(SESSION_CACHE_FILE):
        try:
            with open(SESSION_CACHE_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                if "session_id" in data and "xsrf_token" in data:
                    return data
        except Exception:
            pass
    # Generate a fresh session ID if cache is empty or corrupt
    default_session = {"session_id": str(uuid.uuid4()), "xsrf_token": ""}
    save_session_data(default_session)
    return default_session

def save_session_data(data: dict):
    """Save session ID and XSRF token to session_cache.json."""
    try:
        with open(SESSION_CACHE_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=4)
    except Exception:
        pass

def clean_text(text: str) -> str:
    """Removes backend code execution metadata and googleusercontent links from response."""
    text = re.sub(
        r'```(?:python|javascript|text)\?code_(?:reference|stdout)&code_event_index=\d+\n.*?```\n?',
        '', text, flags=re.DOTALL
    )
    text = re.sub(r'http://googleusercontent\.com/card_content/\d+\n?', '', text)
    return text.strip()

def extract_texts_from_line(line: str) -> list:
    """Decode and extract text responses from Google's chunked 'wrb.fr' envelopes."""
    if '"wrb.fr"' not in line:
        return []
    try:
        # Find JSON array starting point to ignore protocol numbers
        start_idx = line.find('[')
        if start_idx == -1:
            return []
            
        arr = json.loads(line[start_idx:])
        texts = []
        for item in arr:
            if isinstance(item, list) and len(item) > 2 and item[0] == "wrb.fr":
                inner_str = item[2]
                if not inner_str:
                    continue
                inner = json.loads(inner_str)
                # Text content resides at index 4 of decoded inner list
                if len(inner) > 4 and inner[4]:
                    for part in inner[4]:
                        if isinstance(part, list) and len(part) > 1 and isinstance(part[1], list):
                            for segment in part[1]:
                                if isinstance(segment, str) and segment:
                                    texts.append(segment)
        return texts
    except (json.JSONDecodeError, IndexError, TypeError):
        return []

def ask_gemini_direct(prompt: str, model: str = "gemini-3.5-flash", think_level: int = 4) -> str:
    """Send a direct, self-healing request to the Google Gemini StreamGenerate endpoint."""
    model_map = {
        "gemini-3.5-flash": 1,
        "gemini-3.5-flash-thinking": 2,
        "gemini-3.1-pro": 3,
        "gemini-auto": 4,
        "gemini-3.5-flash-thinking-lite": 5,
        "gemini-flash-lite": 6
    }
    model_id = model_map.get(model, 1)

    session = load_session_data()

    # 1. Construct the Google protobuf-like nested JSON payload array
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
    inner[59] = session["session_id"]
    inner[61] = []
    inner[68] = 1
    inner[79] = model_id

    payload_data = {"f.req": json.dumps([None, json.dumps(inner)])}
    cookies_str = load_cookies()

    headers = {
        "Content-Type": "application/x-www-form-urlencoded",
        "Origin": "https://gemini.google.com",
        "Referer": "https://gemini.google.com/app",
        "X-Same-Domain": "1",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    }
    if cookies_str:
        headers["Cookie"] = cookies_str
        sapisid = get_sapisid_from_cookies(cookies_str)
        if sapisid:
            headers["Authorization"] = make_sapisidhash(sapisid)

    # Load cached XSRF token initially
    current_xsrf_token = session["xsrf_token"]

    def execute_post(bl_ver, use_cookies=True):
        reqid = int(time.time()) % 1000000
        url = f"https://gemini.google.com/_/BardChatUi/data/assistant.lamda.BardFrontendService/StreamGenerate?bl={bl_ver}&hl=en&_reqid={reqid}&rt=c"
        
        post_headers = headers.copy()
        if not use_cookies:
            post_headers.pop("Cookie", None)
            post_headers.pop("Authorization", None)
            
        post_data = payload_data.copy()
        if use_cookies and current_xsrf_token:
            post_data["at"] = current_xsrf_token
            
        print(f"[*] Querying '{model}' (bl: {bl_ver}, auth: {use_cookies and bool(cookies_str)}, xsrf: {bool(current_xsrf_token)})...")
        
        if HAS_CURL_CFFI:
            return requests.post(url, data=post_data, headers=post_headers, timeout=30, impersonate="chrome")
        else:
            return requests.post(url, data=post_data, headers=post_headers, timeout=30)

    # 2. Fire initial request (using cached XSRF token if available)
    bl_version = get_latest_bl_version()
    res = execute_post(bl_version, use_cookies=True)

    # 3. Handle XSRF protection challenge (HTTP 400 returns token to include as 'at' key)
    if res.status_code == 400:
        match = re.search(r'\["xsrf","([^"]+)"', res.text)
        if match:
            current_xsrf_token = match.group(1)
            session["xsrf_token"] = current_xsrf_token
            save_session_data(session)
            print("[*] XSRF mismatch/missing. Cached fresh token and retrying...")
            res = execute_post(bl_version, use_cookies=True)

    # 4. Handle invalid/expired cookie authentication failure (HTTP 401 fallback to guest mode)
    if res.status_code == 401 and cookies_str:
        print("[!] Warning: Got HTTP 401 Unauthorized (invalid/expired cookies). Retrying as guest...")
        res = execute_post(bl_version, use_cookies=False)

    if res.status_code != 200:
        if res.status_code == 401:
            return "Error HTTP 401: Unauthorized access. Check your cookies.txt session."
        return f"Error HTTP {res.status_code}: {res.text[:300]}"

    # 5. Handle outdated bl build version (empty response / BardErrorInfo)
    if "BardErrorInfo" in res.text or not any('"wrb.fr"' in line for line in res.text.split("\n")):
        print("[!] Warning: Rejected or empty response. Refreshing backend build version...")
        global _cached_bl_version
        old_bl = _cached_bl_version
        _cached_bl_version = None  # Clear cache to force a fresh fetch
        new_bl = get_latest_bl_version()
        
        if new_bl != old_bl:
            print(f"[*] Retrying request with updated version: {new_bl}...")
            res = execute_post(new_bl, use_cookies=bool(headers.get("Cookie")))
            if res.status_code != 200:
                return f"Error HTTP {res.status_code}: {res.text[:300]}"

    # 6. Parse and clean response text from chunks
    last_text = ""
    for line in res.text.split("\n"):
        for t in extract_texts_from_line(line):
            if len(t) > len(last_text):
                last_text = t

    if not last_text:
        if "BardErrorInfo" in res.text:
            err_match = re.search(r'\"type\.googleapis\.com/assistant\.boq\.bard\.application\.BardErrorInfo\",\[(\d+)\]', res.text)
            err_code = err_match.group(1) if err_match else "Unknown"
            return f"Error: Google Gemini returned error code {err_code} (rate limited or geographic block)."
        return "Error: Could not extract any text from response."

    return clean_text(last_text)

if __name__ == "__main__":
    if not HAS_CURL_CFFI:
        print("[*] Tip: Run 'pip install curl-cffi' to bypass Google rate limit blocks (1076/1099) completely.")
        
    prompt = "give me 10 anime movies like Makeine: Too Many Losing Heroin" 
    response = ask_gemini_direct(prompt, model="gemini-3.1-pro")
    try:
        print(response)
    except UnicodeEncodeError:
        print(response.encode('utf-8', errors='replace').decode('utf-8'))