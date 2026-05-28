import sys
import time
import json
import nest_asyncio
from datetime import datetime
from seleniumbase import Driver
from pyvirtualdisplay import Display
from colorama import Fore, Back, Style, init

nest_asyncio.apply()
init(autoreset=True)

# =================================================================
# 🛠️ سیستم لاگ‌نویسی حرفه‌ای
# =================================================================
def get_time():
    return datetime.now().strftime("%H:%M:%S.%f")[:-3]

def log_info(msg):    print(f"[{get_time()}] {Fore.CYAN}[INFO] {msg}{Style.RESET_ALL}")
def log_success(msg): print(f"[{get_time()}] {Fore.GREEN}✅ [SUCCESS] {msg}{Style.RESET_ALL}")
def log_warn(msg):    print(f"[{get_time()}] {Fore.YELLOW}⚠️ [WARN] {msg}{Style.RESET_ALL}")
def log_error(msg, e=None): 
    err_details = f" | Details: {str(e)}" if e else ""
    print(f"[{get_time()}] {Fore.RED}❌ [ERROR] {msg}{err_details}{Style.RESET_ALL}")
def log_debug(msg):   print(f"[{get_time()}] {Fore.BLUE}[DEBUG] {msg}{Style.RESET_ALL}")

# =================================================================
# 🔴 تنظیمات اکانت
# =================================================================
MY_EMAIL = "alisalehniaai@gmail.com"
MY_PASSWORD = "S@ny_4010"

# =================================================================
# 💉 جاسوس چندکاناله اصلاح‌شده (بدون کاراکتر غیرمجاز)
# =================================================================
JS_OMNI_HOOK = """
window.ws_spy_active = true;
window.ws_captured_logs = window.ws_captured_logs || [];

try {
    // ۱. هوک همه‌جانبه وب‌سوکت
    if (!window.websocket_patched) {
        const nativeWebSocket = window.WebSocket;
        window.WebSocket = function(...args) {
            const socket = new nativeWebSocket(...args);
            socket.addEventListener('message', function(event) {
                if(window.ws_captured_logs) window.ws_captured_logs.push("WS:" + event.data);
            });
            return socket;
        };
        window.websocket_patched = true;
    }

    // ۲. هوک شریان postMessage (برای شکار دیتای ورکرها و آی‌فریم‌ها)
    if (!window.message_patched) {
        const originalAddEventListener = window.addEventListener;
        window.addEventListener = function(type, listener, options) {
            if (type === 'message') {
                return originalAddEventListener.call(this, type, function(event) {
                    try {
                        if (window.ws_captured_logs && event.data) {
                            let strData = typeof event.data === 'object' ? JSON.stringify(event.data) : String(event.data);
                            window.ws_captured_logs.push("POST:" + strData);
                        }
                    } catch(err){}
                    return listener.apply(this, arguments);
                }, options);
            }
            return originalAddEventListener.apply(this, arguments);
        };
        window.message_patched = true;
    }

    // ۳. هوک شریان BroadcastChannel (کانال‌های رادیویی بین تب‌ها و ورکرها)
    if (typeof BroadcastChannel !== 'undefined' && !window.broadcast_patched) {
        const originalBcAdd = BroadcastChannel.prototype.addEventListener;
        BroadcastChannel.prototype.addEventListener = function(type, listener, options) {
            if (type === 'message') {
                return originalBcAdd.call(this, type, function(event) {
                    try {
                        if (window.ws_captured_logs && event.data) {
                            let strData = typeof event.data === 'object' ? JSON.stringify(event.data) : String(event.data);
                            window.ws_captured_logs.push("BC:" + strData);
                        }
                    } catch(err){}
                    return originalBcAdd.apply(this, arguments);
                }, options);
            }
            return originalBcAdd.apply(this, arguments);
        };
        window.broadcast_patched = true;
    }
} catch(e) {}
"""

def start_self_healing_listener():
    log_info("Initializing Virtual Display Context...")
    display = Display(visible=0, size=(1920, 1080))
    display.start()
    log_success("Virtual Display created successfully.")

    log_info("Booting Undetected Chromedriver (uc=True)...")
    driver = Driver(uc=True, headless=False)
    log_success("Chrome Browser instance is up.")

    try:
        # مسلح کردن لایه CDP
        log_info("Arming Omni-Channel CDP Interception layer...")
        driver.execute_cdp_cmd('Page.addScriptToEvaluateOnNewDocument', {'source': JS_OMNI_HOOK})
        log_success("CDP Layer armed successfully.")

        # ورود به صفحه هوم
        target_url = "https://www.financialjuice.com/home"
        log_info(f"Navigating to exact home gateway: {target_url}")
        driver.get(target_url)
        
        log_info("Holding 5s for DOM stability...")
        time.sleep(5)

        # لاگین
        try:
            log_info("Searching for 'Sign In' triggers...")
            btns = driver.find_elements("xpath", "//a[contains(text(), 'Sign In')]")
            if btns: btns[0].click()
            else:
                btns = driver.find_elements("xpath", "//div[contains(@class, 'login')]")
                if btns: btns[0].click()

            time.sleep(3)
            driver.find_element("css selector", "#ctl00_SignInSignUp_loginForm1_inputEmail").send_keys(MY_EMAIL)
            driver.find_element("css selector", "#ctl00_SignInSignUp_loginForm1_inputPassword").send_keys(MY_PASSWORD)
            try: driver.find_element("css selector", "small.zed-login").click()
            except: pass
            driver.find_element("css selector", "#ctl00_SignInSignUp_loginForm1_btnLogin").click()
            log_success("Form submission event dispatched.")
            time.sleep(10)
        except Exception as e:
            log_error("Failure during Authentication flow", e)

        # رفرش استراتژیک صفحه برای فعال‌سازی سشن روی تمام کانال‌ها
        log_info("Executing Page Refresh to bind authenticated sessions across all pipes...")
        driver.refresh()
        log_info("Holding 8 seconds for cross-pipe handshake stabilization...")
        time.sleep(8)

        log_info("Starting Pipeline Loop: Omni Monitoring active.")
        last_pulse_time = time.time()

        while True:
            spy_status = driver.execute_script("return window.ws_spy_active;")

            if not spy_status:
                log_warn("Pipeline Breach: Context reset detected. Re-injecting omni-collector...")
                driver.execute_script(JS_OMNI_HOOK)
                time.sleep(1)
                continue

            if time.time() - last_pulse_time > 10:
                buffer_size = driver.execute_script("return window.ws_captured_logs ? window.ws_captured_logs.length : -1;")
                log_debug(f"[PULSE] Omni Net Active | Intercepted Queue Buffer: {buffer_size} elements")
                last_pulse_time = time.time()

            try:
                # خواندن و تخلیه بافر کلاینت
                logs = driver.execute_script("""
                    if (typeof window.ws_captured_logs === 'undefined') return null;
                    return window.ws_captured_logs.splice(0, window.ws_captured_logs.length);
                """)

                if logs is None:
                    time.sleep(1)
                    continue

                if logs:
                    for prefixed_msg in logs:
                        # جداسازی برچسب کانال ورودی
                        channel = "UNKNOWN"
                        raw_msg = prefixed_msg
                        if ":" in prefixed_msg:
                            channel, raw_msg = prefixed_msg.split(":", 1)

                        # فیلتر پکت‌های زنده نگهدارنده عمومی
                        if raw_msg in ["{}", "[]", "h", "3", "2", "1", "0", "null", "undefined"] or '{"type":"ping"}' in raw_msg.replace(" ", ""):
                            print(f"{Fore.MAGENTA}💓{Style.RESET_ALL}", end="", flush=True)
                            continue

                        # لاگ تشخصیی برای ورود دیتا از هر کانال
                        log_info(f"Incoming Interception [Channel: {Fore.YELLOW}{channel}{Style.RESET_ALL}] | Length: {len(raw_msg)} chars.")

                        try:
                            data = json.loads(raw_msg)
                            news_found = False

                            # جستجوی فیلدهای متنی درون دیتای ساختاریافته کانال‌ها
                            for key in ['Text', 'text', 'Title', 'title', 'Headline', 'headline', 'content', 'data']:
                                if isinstance(data, dict) and key in data and isinstance(data[key], str) and len(data[key]) > 0:
                                    print("\n" + "="*70)
                                    print(f"{Fore.WHITE}{Back.RED} 🔥 NEWS DETECTED VIA [{channel}] {Style.RESET_ALL}")
                                    print(f"{Fore.YELLOW}TEXT: {data[key]}{Style.RESET_ALL}")
                                    print("="*70 + "\n")
                                    news_found = True
                                    break

                            if not news_found:
                                log_debug(f"RAW JSON [{channel}]: {raw_msg[:200]}...")
                        except Exception:
                            # اگر دیتا متن خام خارج از فرمت JSON بود
                            print("\n" + "="*70)
                            print(f"{Fore.WHITE}{Back.BLUE} 📨 TEXT STREAM [{channel}]: {raw_msg[:200]}... {Style.RESET_ALL}")
                            print("="*70 + "\n")

            except Exception as loop_e:
                log_error("Polling extraction failure", loop_e)

            time.sleep(1)

    except KeyboardInterrupt:
        log_warn("Suspended by user.")
    except Exception as e:
        log_error("FATAL RUNTIME ERROR", e)
    finally:
        log_info("Cleaning resources...")
        try: driver.quit()
        except: pass
        try: display.stop()
        except: pass

if __name__ == "__main__":
    start_self_healing_listener()
