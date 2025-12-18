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
from seleniumbase import Driver
from pyvirtualdisplay import Display
from colorama import Fore, Back, Style, init

# Init
nest_asyncio.apply()
init(autoreset=True)

# =================================================================
# Config & Secrets
# =================================================================
TELEGRAM_BOT_TOKEN = os.environ.get("TG_TOKEN")
TELEGRAM_CHANNEL_ID = os.environ.get("TG_CHANNEL_ID")
MY_EMAIL = os.environ.get("FJ_EMAIL")
MY_PASSWORD = os.environ.get("FJ_PASSWORD")
TARGET_URL = os.environ.get("FJ_URL") # URL is now hidden

if not TELEGRAM_BOT_TOKEN or not MY_EMAIL or not TARGET_URL:
    print(f"{Fore.RED}❌ Error: Missing configuration (Check Secrets).{Style.RESET_ALL}")
    sys.exit(1)

# Blacklist
BLACKLIST_WORDS = [] 

# =================================================================
# State Management
# =================================================================
SEEN_SIGNATURES = set()
# Start time buffer (UTC)
START_TIME = datetime.datetime.utcnow() - datetime.timedelta(minutes=2)

# =================================================================
# Helpers
# =================================================================
def log(msg, color=Fore.WHITE):
    ts = datetime.datetime.now().strftime("%H:%M:%S")
    print(f"{Fore.CYAN}[{ts}]{color} {msg}{Style.RESET_ALL}")

def parse_date(date_str):
    if not date_str: return None
    try:
        date_str = date_str.replace('Z', '+00:00')
        if "." in date_str: date_str = date_str.split(".")[0] + "+00:00"
        return datetime.datetime.fromisoformat(date_str)
    except: return None

def clean_text(text):
    if not text: return ""
    text = html.unescape(str(text))
    text = re.sub(r'</p>', '\n', text)
    text = re.sub(r'<br\s*/?>', '\n', text)
    text = re.sub(r'<[^>]+>', '', text)
    lines = [line.strip() for line in text.split('\n') if line.strip()]
    return "\n".join(lines)

def get_hash(t, d):
    raw = f"{t}_{d if d else 'ND'}"
    return hashlib.md5(raw.encode('utf-8')).hexdigest()

def dispatch(data):
    if not TELEGRAM_BOT_TOKEN: return
    
    rt = data.get('Title', data.get('FJTitle', 'No Title'))
    title = clean_text(rt)
    p_date = data.get('PublishedDate') or data.get('PublishDate')
    
    # Check Blacklist
    for w in BLACKLIST_WORDS:
        if w.lower() in title.lower(): return

    # Check Signature
    sig = get_hash(title, p_date)
    if sig in SEEN_SIGNATURES: return
    SEEN_SIGNATURES.add(sig)

    # Check Time
    if p_date:
        dt = parse_date(p_date)
        if dt and dt < START_TIME: return

    # Extract
    desc = clean_text(data.get('Description', ''))
    tags = data.get('Tags', [])
    t_names = ", ".join([t.get('Name') for t in tags]) if tags else "None"
    lbls = data.get('Labels', [])
    l_str = ", ".join(lbls) if lbls else "None"
    lvl = data.get('Level', 'N/A')
    brk = data.get('Breaking', False)
    act = data.get('Actual')
    fcst = data.get('Forecast')
    prev = data.get('Previous')

    # Format
    icon = "🚨" if brk else "📰"
    if "Indices" in l_str or "Index" in l_str: icon = "📉"
    
    msg = f"{icon} <b>{title}</b>\n\n"
    if desc: msg += f"📝 <i>{desc}</i>\n\n"
    
    msg += "<b>🔍 INFO:</b>\n"
    msg += f"🔸 <b>Lvl:</b> <code>{lvl}</code>\n"
    msg += f"🔸 <b>Brk:</b> <code>{brk}</code>\n"
    msg += f"🔸 <b>Tgs:</b> {t_names}\n"
    msg += f"🔸 <b>Lbl:</b> {l_str}\n"
    
    if act or fcst:
        msg += "\n<b>📊 DATA:</b>\n"
        msg += f"Act: {act} | Fcst: {fcst} | Prev: {prev}\n"

    msg += "\n#Full_Analysis #FinancialJuice"

    # Send
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {"chat_id": TELEGRAM_CHANNEL_ID, "text": msg, "parse_mode": "HTML", "disable_web_page_preview": True}
    try:
        requests.post(url, json=payload, timeout=5)
        log(f"-> Sent: {title[:20]}...", Fore.MAGENTA)
    except Exception as e:
        log(f"err: {e}", Fore.RED)

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
def run():
    log(f"System Active.", Fore.CYAN)
    display = Display(visible=0, size=(1920, 1080))
    display.start()
    driver = Driver(uc=True, headless=False)

    try:
        # Use Secret URL
        driver.get(TARGET_URL)
        time.sleep(5)

        # Auth
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
            log("Auth sent.", Fore.GREEN)
            time.sleep(20)
        except: pass

        if any('.ASPXAUTH' in c['name'] for c in driver.get_cookies()):
            log("State: OK", Fore.GREEN)
        else:
            log("State: Unverified", Fore.RED)

        log("Listening...", Fore.GREEN)
        
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
                    for raw in logs:
                        if raw == "{}" or raw == '{"S":1,"M":[]}': continue
                        try:
                            d = json.loads(raw)
                            if 'M' in d:
                                for i in d['M']:
                                    if 'A' in i and len(i['A']) > 0:
                                        p_str = i['A'][0]
                                        try:
                                            if isinstance(p_str, str) and (p_str.startswith('[') or p_str.startswith('{')):
                                                in_lst = json.loads(p_str)
                                                if isinstance(in_lst, list):
                                                    for n in in_lst: dispatch(n)
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
    run()
