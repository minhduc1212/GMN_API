from playwright.sync_api import sync_playwright
import time

# Đường dẫn trang web
PAGE_URL = "https://aistudio.google.com/prompts/new_chat"

with sync_playwright() as p:
    # Khởi chạy trình duyệt với profile để giữ trạng thái đăng nhập
    browser = p.chromium.launch_persistent_context(
        user_data_dir="./ai_profile", 
        headless=False, 
        args=["--disable-blink-features=AutomationControlled"]
    )
    
    page = browser.pages[0] if browser.pages else browser.new_page()

    print("Đang tải trang web...")
    page.goto(PAGE_URL)
    
   
    print("Đang gửi yêu cầu...")
    prompt = "Who are you?"
    page.fill("textarea[placeholder='Start typing a prompt to see what our models can do']", prompt)

    print("Gửi lệnh Run (Ctrl+Enter)...")
    page.keyboard.press("Control+Enter")

    print("Đang chờ phản hồi...") 

    try:
        response_selector = "ms-text-chunk"
        page.wait_for_selector(response_selector, timeout=20000)
        time.sleep(10) 
        
        # Lấy tất cả các đoạn text từ các chunk
        chunks = page.query_selector_all(response_selector)
        full_response = "".join([chunk.inner_text() for chunk in chunks])
        
        print("-" * 30)
        print("Phản hồi từ AI:")
        print(full_response.replace(prompt, ""))
        print("-" * 30)
    except Exception as e:
        print(f"Lỗi khi lấy phản hồi: {e}")

    # Giữ trình duyệt để quan sát nếu cần
    print("Hoàn tất. Đóng sau 10 giây...")
    page.wait_for_timeout(10000)
    browser.close()