from playwright.sync_api import sync_playwright
import time

# Đường dẫn trang web
PAGE_URL = "https://aistudio.google.com/prompts/1bIRQQRXhifAbX8C15Ic8pLafkDIVOB1n"

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
    prompt = "Explain this code snippet in detail:\n\n```python\ndef greet(name):\n    return f'Hello, {name}!'\n```"
    page.fill("textarea[placeholder='Start typing a prompt to see what our models can do']", prompt)

    print("Gửi lệnh Run (Ctrl+Enter)...")
    page.keyboard.press("Control+Enter")

    print("Đang chờ phản hồi...") 
    page.wait_for_timeout(5000)

    #click vào giữa màn hình để xác định vùng response
    page.mouse.click(500, 500)
    print("Đã click vào giữa màn hình.")

    # Thêm một chút thời gian chờ cứng cho chắc ăn nếu web render quá chậm
    page.wait_for_timeout(3000) 

    try:
        # 1. Tìm và click vào button cuối cùng bằng Locator (Auto-wait)
        # Sử dụng .last để lấy phần tử cuối cùng
        menu_button = page.locator("button.mat-mdc-menu-trigger.ms-button-borderless.ms-button-icon").last
        
        # Ép Playwright chờ đến khi nút này thực sự nhìn thấy được trên màn hình
        menu_button.wait_for(state="visible", timeout=10000)
        menu_button.click()
        print("Đã click vào button menu cuối cùng.")

        # 2. Tìm và click vào "Copy as text"
        # Thay vì loop qua từng thẻ span, dùng get_by_text rất nhanh và tự động chờ animation của menu thả xuống
        copy_option = page.locator("span.mat-mdc-menu-item-text", has_text="Copy as text")
        
        # Hoặc có thể dùng gọn hơn: copy_option = page.get_by_text("Copy as text", exact=True)
        
        copy_option.click()
        print("Đã click vào 'Copy as text'.")

    except Exception as e:
        print(f"Xảy ra lỗi: {e}")

    # Giữ trình duyệt để quan sát
    print("Đóng trình duyệt sau 5 giây...")
    page.wait_for_timeout(5000)
    browser.close()