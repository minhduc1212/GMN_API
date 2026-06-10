import os
import time
from playwright.sync_api import sync_playwright

# Paths resolved relative to this script's directory
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
COOKIES_FILE = os.path.join(BASE_DIR, "cookies.txt")
PROFILE_DIR = os.path.join(BASE_DIR, "ai_profile")

# Core Google authentication cookie names required for Gemini
CORE_GOOGLE_COOKIES = {
    "__Secure-1PSID", "__Secure-1PSIDTS", 
    "__Secure-3PSID", "__Secure-3PSIDTS", 
    "SID", "HSID", "SSID", "APISID", "SAPISID"
}

def has_active_session(cookies: list) -> bool:
    """Returns True if the primary Google session identifier __Secure-1PSID is present."""
    return any(c["name"] == "__Secure-1PSID" for c in cookies)

def save_cookies(cookies: list) -> int:
    """Filters, deduplicates, and saves Google session cookies to cookies.txt."""
    filtered = {}
    for c in cookies:
        domain = c.get("domain", "")
        # Only process cookies from Google domains
        if not domain.endswith("google.com"):
            continue
            
        name = c["name"]
        if name not in CORE_GOOGLE_COOKIES:
            continue
            
        # Prioritize cookies mapped to primary/canonical domains
        if name in filtered:
            if domain in (".google.com", "gemini.google.com", ".gemini.google.com"):
                filtered[name] = c
        else:
            filtered[name] = c

    # Build the Cookie header string format: name=value; name2=value2
    cookie_str = "; ".join([f"{name}={c['value']}" for name, c in filtered.items()])
    
    with open(COOKIES_FILE, "w", encoding="utf-8") as f:
        f.write(cookie_str)
        
    return len(filtered)

def main():
    profile_dir = PROFILE_DIR
    print("[*] Launching browser to check Gemini session...")
    
    with sync_playwright() as p:
        try:
            # Open browser in non-headless mode using the shared profile
            context = p.chromium.launch_persistent_context(
                user_data_dir=profile_dir,
                headless=False,
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
                args=["--disable-blink-features=AutomationControlled"]
            )
            
            page = context.pages[0] if context.pages else context.new_page()
            print("[*] Opening Gemini app...")
            page.goto("https://gemini.google.com/app")
            
            print("[*] Checking for login session (waiting up to 3 minutes)...")
            cookies_saved = 0
            
            # Poll for session cookies every 0.5 seconds
            for _ in range(360):
                time.sleep(0.5)
                if not context.pages:
                    break
                try:
                    cookies = context.cookies()
                    if has_active_session(cookies):
                        cookies_saved = save_cookies(cookies)
                        break
                except Exception:
                    break
            
            if cookies_saved > 0:
                print(f"[+] Success! Saved {cookies_saved} session cookies to cookies.txt.")
            else:
                print("[-] Failed: Browser closed or login timed out before finding session.")
                
            context.close()
        except Exception as e:
            print(f"[!] Error: {e}")

if __name__ == "__main__":
    main()
