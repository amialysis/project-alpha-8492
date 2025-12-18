import sys
import time
import json
import re
import html
import requests
import nest_asyncio
import datetime
import hashlib
import os
import pytz 
from seleniumbase import Driver
from pyvirtualdisplay import Display
from colorama import Fore, Back, Style, init

# Init
nest_asyncio.apply()
init(autoreset=True)

# =================================================================
# Config & Secrets (Full Names)
# =================================================================
TELEGRAM_BOT_TOKEN = os.environ.get("TG_TOKEN")
TELEGRAM_CHANNEL_ID = os.environ.get("TG_CHAT_ID")
MY_EMAIL = os.environ.get("MY_EMAIL")
MY_PASSWORD = os.environ.get("MY_PASSWORD")
TARGET_URL = os.environ.get("FJ_URL")

# Validation
if not TELEGRAM_BOT_TOKEN or not MY_EMAIL or not TARGET_URL:
    print(f"{Fore.RED}Err: Config Missing.{Style.RESET_ALL}")
    sys.exit(1)

# Blacklist
BLACKLIST_WORDS = [] 

# =================================================================
# State Management
# =================================================================
SEEN_SIGNATURES = set()
START_TIME = datetime.datetime.utcnow() - datetime.timedelta(minutes=2)

# =================================================================
# Helpers
# =================================================================
def sys_log(msg, color=Fore.WHITE):
    ts = datetime.datetime.now().strftime("%H:%M:%S")
    print(f"{Fore.CYAN}[{ts}]{color} {msg}{Style.RESET_ALL}")

def parse_iso_date(date_str):
    if not date_str: return None
    try:
        date_str = date_str.replace('Z', '+00:00')
        if "." in date_str: date_str = date_str.split(".")[0] + "+00:00"
        return datetime.datetime.fromisoformat(date_str)
    except: return None

def convert_to_tehran(utc_dt):
    """Convert UTC datetime object to Tehran Time String (HH:MM:SS)"""
    if not utc_dt: return "N/A"
    try:
        tehran_tz = pytz.timezone('Asia/Tehran')
        tehran_dt = utc_dt.astimezone(tehran_tz)
        return tehran_dt.strftime("%H:%M:%S")
    except:
        return utc_dt.strftime("%H:%M:%S")

def sanitize_text(text):
    if not text: return ""
    text = html.unescape(str(text))
    text = re.sub(r'</p>', '\n', text)
    text = re.sub(r'<br\s*/?>', '\n', text)
    text = re.sub(r'<[^>]+>', '', text)
    lines = [line.strip() for line in text.split('\n') if line.strip()]
    return "\n".join(lines)

def generate_signature(title, date_str):
    raw = f"{title}_{date_str if date_str else 'ND'}"
    return hashlib.md5(raw.encode('utf-8')).hexdigest()

def dispatch_payload(data):
    if not TELEGRAM_BOT_TOKEN: return
    
    # Extract Title
    raw_title = data.get('Title', data.get('FJTitle', 'No Title'))
    title = sanitize_text(raw_title)
    publish_date = data.get('PublishedDate') or data.get('PublishDate')
    
    # 1. Blacklist Check
    for word in BLACKLIST_WORDS:
        if word.lower() in title.lower(): return

    # 2. Signature Check
    sig = generate_signature(title, publish_date)
    if sig in SEEN_SIGNATURES: return
    SEEN_SIGNATURES.add(sig)

    # 3. Time Check & Convert
    news_time_str = "N/A"
    if publish_date:
        dt = parse_iso_date(publish_date)
        if dt:
            if dt < START_TIME: return
            news_time_str = convert_to_tehran(dt)

    # Extract Details
    description = sanitize_text(data.get('Description', ''))
    tags = data.get('Tags', [])
    tags_str = ", ".join([t.get('Name') for t in tags]) if tags else "-"
    labels = data.get('Labels', [])
    labels_str = ", ".join(labels) if labels else "-"
    level = data.get('Level', '-')
    breaking = data.get('Breaking', False)
    
    # Financial Data
    actual = data.get('Actual')
    forecast = data.get('Forecast')
    previous = data.get('Previous')

    
    icon = "🚨 " if breaking else ""
    
    msg = f"{icon}<b>{title}</b>\n\n"
    
    if description: 
        msg += f"{description}\n\n"
    
    # Analysis Section
    msg += "<b>INFO:</b>\n"
    msg += f"Lvl: <code>{level}</code>\n"
    msg += f"Brk: <code>{breaking}</code>\n"
    msg += f"Tgs: {tags_str}\n"
    msg += f"Lbl: {labels_str}\n"
    
    if actual or forecast:
        msg += "\n<b>DATA:</b>\n"
        msg += f"Act: {actual} | Fcst: {forecast} | Prev: {previous}\n"

   
    msg += f"\nTime: {news_time_str}"

    # Telegram API Push
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {"chat_id": TELEGRAM_CHANNEL_ID, "text": msg, "parse_mode": "HTML", "disable_web_page_preview": True}
    
    try:
        requests.post(url, json=payload, timeout=5)
        sys_log(f"Packet: SENT ({len(title)}b)", Fore.MAGENTA)
    except Exception as e:
        sys_log(f"Net: Err", Fore.RED)

# =================================================================
# Injection Script
# =================================================================
JS_PAYLOAD = """
window.ws_spy_active = true;
window.ws_captured_logs = [];
const nativeWebSocket = window.WebSocket;
window.WebSocket = function(...args) {
  const socket = new nativeWebSocket(...args);
  socket.addEventListener('message', function(event) {
    if(window.ws_captured_logs) {
        window.ws_captured_logs.push(event.data);
    }
  });
  return socket;
};
"""

# =================================================================
# Main Loop
# =================================================================
def run_service():
    sys_log(f"Core: Online", Fore.CYAN)
    display = Display(visible=0, size=(1920, 1080))
    display.start()
    driver = Driver(uc=True, headless=False)

    try:
        driver.get(TARGET_URL)
        time.sleep(5)

        try:
            btns = driver.find_elements("xpath", "//a[contains(text(), 'Sign In')]")
            if btns: btns[0].click()
            else:
                btns = driver.find_elements("xpath", "//div[contains(@class, 'login')]")
                if btns: btns[0].click()
            time.sleep(3)
            driver.find_element("css selector", "#ctl00_SignInSignUp_loginForm1_inputEmail").send_keys(MY_EMAIL)
            driver.find_element("css selector", "#ctl00_SignInSignUp_loginForm1_inputPassword").send_keys(MY_PASSWORD)
            driver.find_element("css selector", "#ctl00_SignInSignUp_loginForm1_btnLogin").click()
            sys_log("Auth: Payload Sent", Fore.GREEN)
            time.sleep(20)
        except: pass

        if any('.ASPXAUTH' in c['name'] for c in driver.get_cookies()):
            sys_log("Status: Verified", Fore.GREEN)
        else:
            sys_log("Status: Guest Mode", Fore.RED)

        sys_log("Link: Established", Fore.GREEN)
        
        while True:
            try: act = driver.execute_script("return window.ws_spy_active;")
            except: act = False

            if not act:
                driver.execute_script(JS_PAYLOAD)
                try: driver.execute_script("if($.connection && $.connection.hub){$.connection.hub.stop();setTimeout(()=>$.connection.hub.start(),1000);}")
                except: pass
                time.sleep(5)

            try:
                logs = driver.execute_script("""
                    if (typeof window.ws_captured_logs === 'undefined') return [];
                    return window.ws_captured_logs.splice(0, window.ws_captured_logs.length);
                """)
                if logs:
                    for raw_json in logs:
                        if raw_json == "{}" or raw_json == '{"S":1,"M":[]}': continue
                        try:
                            data_obj = json.loads(raw_json)
                            if 'M' in data_obj:
                                for item in data_obj['M']:
                                    if 'A' in item and len(item['A']) > 0:
                                        payload_str = item['A'][0]
                                        try:
                                            if isinstance(payload_str, str) and (payload_str.startswith('[') or payload_str.startswith('{')):
                                                inner_list = json.loads(payload_str)
                                                if isinstance(inner_list, list):
                                                    for news_item in inner_list: 
                                                        dispatch_payload(news_item)
                                        except: pass
                        except: pass
            except: pass
            time.sleep(1)

    except KeyboardInterrupt: pass
    finally:
        try: driver.quit()
        except: pass
        try: display.stop()
        except: pass

if __name__ == "__main__":
    run_service()
