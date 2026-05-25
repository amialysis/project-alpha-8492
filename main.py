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

nest_asyncio.apply()
init(autoreset=True)

TELEGRAM_BOT_TOKEN = os.environ.get("TG_TOKEN")
TELEGRAM_CHANNEL_ID = os.environ.get("TG_CHAT_ID")
TG_ADMIN_ID = os.environ.get("TG_ADMIN_ID")
MY_EMAIL = os.environ.get("MY_EMAIL")
MY_PASSWORD = os.environ.get("MY_PASSWORD")
TARGET_URL = os.environ.get("FJ_URL")

if not TELEGRAM_BOT_TOKEN or not MY_EMAIL or not TARGET_URL:
    print(f"{Fore.RED}Err: Config Missing.{Style.RESET_ALL}")
    sys.exit(1)

BLACKLIST_WORDS = [] 

SEEN_SIGNATURES = set()
START_TIME = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(minutes=2)
SEND_LOGS_TO_ADMIN = True
LAST_UPDATE_ID = 0

def send_to_telegram_direct(chat_id, text):
    if not TELEGRAM_BOT_TOKEN or not chat_id: return
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {"chat_id": chat_id, "text": text, "parse_mode": "HTML", "disable_web_page_preview": True}
    try:
        requests.post(url, json=payload, timeout=4)
    except:
        pass

def sys_log(msg, color=Fore.WHITE):
    ts = datetime.datetime.now().strftime("%H:%M:%S")
    clean_msg = f"[{ts}] {msg}"
    print(f"{Fore.CYAN}[{ts}]{color} {msg}{Style.RESET_ALL}")
    
    global SEND_LOGS_TO_ADMIN, TG_ADMIN_ID
    if SEND_LOGS_TO_ADMIN and TG_ADMIN_ID:
        if color in [Fore.RED, Fore.YELLOW, Fore.GREEN, Fore.CYAN, Fore.MAGENTA] or "CRITICAL" in msg or "Auth:" in msg:
            icon = "ℹ️"
            if color == Fore.RED: icon = "❌"
            elif color == Fore.YELLOW: icon = "⚠️"
            elif color == Fore.GREEN: icon = "✅"
            elif color == Fore.MAGENTA: icon = "📦"
            elif color == Fore.CYAN: icon = "🔷"
            
            formatted_msg = f"{icon} <b>[FJ Bot Log]:</b>\n<code>{clean_msg}</code>"
            if "Failed to send" not in msg:
                send_to_telegram_direct(TG_ADMIN_ID, formatted_msg)

def init_telegram_commands():
    global LAST_UPDATE_ID
    if not TELEGRAM_BOT_TOKEN: return
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/getUpdates"
        res = requests.get(url, params={"limit": 1, "offset": -1}, timeout=5).json()
        if res.get("ok") and res.get("result"):
            LAST_UPDATE_ID = res["result"][0]["update_id"]
    except:
        pass

def process_telegram_commands():
    global SEND_LOGS_TO_ADMIN, LAST_UPDATE_ID
    if not TELEGRAM_BOT_TOKEN or not TG_ADMIN_ID: return
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/getUpdates"
        params = {"offset": LAST_UPDATE_ID + 1, "timeout": 0}
        res = requests.get(url, params=params, timeout=5).json()
        if res.get("ok"):
            for update in res.get("result", []):
                LAST_UPDATE_ID = update["update_id"]
                message = update.get("message", {})
                from_id = message.get("from", {}).get("id")
                text = message.get("text", "").strip()
                if str(from_id) == str(TG_ADMIN_ID):
                    if text == "/log_on":
                        SEND_LOGS_TO_ADMIN = True
                        send_to_telegram_direct(TG_ADMIN_ID, "<b>Advanced Debug System Enabled.</b> Logs will be sent from now on.")
                    elif text == "/log_off":
                        SEND_LOGS_TO_ADMIN = False
                        send_to_telegram_direct(TG_ADMIN_ID, "<b>Advanced Debug System Disabled.</b> Logs will no longer be sent.")
    except Exception as e:
        print(f"Error checking commands: {e}")

def parse_iso_date(date_str):
    if not date_str: return None
    try:
        date_str = str(date_str).replace('Z', '+00:00')
        if '+' not in date_str and 'Z' not in date_str:
             date_str += '+00:00'
        if "." in date_str: 
            date_str = date_str.split(".")[0] + "+00:00"
        return datetime.datetime.fromisoformat(date_str)
    except: return None

def convert_to_tehran(utc_dt):
    if not utc_dt: return "N/A"
    try:
        tehran_tz = pytz.timezone('Asia/Tehran')
        if utc_dt.tzinfo is None:
            utc_dt = utc_dt.replace(tzinfo=datetime.timezone.utc)
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
    raw_title = data.get('Title', data.get('FJTitle', data.get('title', data.get('headline', data.get('text', 'No Title')))))
    title = sanitize_text(raw_title)
    sys_log(f"Trace: Processing '{title[:30]}...'", Fore.LIGHTBLACK_EX)
    publish_date = data.get('DatePublished') or data.get('PublishedDate') or data.get('PublishDate') or data.get('Date') or data.get('date')
    for word in BLACKLIST_WORDS:
        if word.lower() in title.lower(): 
            sys_log(f"Skip: Blacklisted word ({word})", Fore.LIGHTBLACK_EX)
            return
    sig = generate_signature(title, publish_date)
    if sig in SEEN_SIGNATURES: 
        sys_log(f"Skip: Duplicate Signature", Fore.LIGHTBLACK_EX)
        return
    SEEN_SIGNATURES.add(sig)
    news_time_str = "N/A"
    if publish_date:
        dt = parse_iso_date(publish_date)
        if dt:
            if dt < START_TIME: 
                sys_log(f"Skip: Too Old (Time: {convert_to_tehran(dt)})", Fore.LIGHTBLACK_EX)
                return
            news_time_str = convert_to_tehran(dt)
        else:
            sys_log("Warn: Date Parse Failed", Fore.YELLOW)
    else:
         sys_log("Warn: No Date Field", Fore.YELLOW)
    news_id = data.get('NewsID', data.get('Id', data.get('id', '-')))
    tags = data.get('Tags', [])
    tags_str = ", ".join([str(t.get('Name')) for t in tags]) if tags and isinstance(tags, list) else "-"
    breaking = data.get('Breaking', data.get('breaking', False))
    level = data.get('Level', data.get('level', '-'))
    r_link = data.get('RURL', '')
    e_link = data.get('EURL', '')
    if not r_link: r_link = "-"
    if not e_link: e_link = "-"
    labels = data.get('Labels', [])
    labels_str = ", ".join([str(l) for l in labels]) if labels and isinstance(labels, list) else "-"
    img_link = data.get('Img', '-')
    if not img_link: img_link = "-"
    description = sanitize_text(data.get('Description', data.get('description', '')))
    actual = data.get('Actual')
    forecast = data.get('Forecast')
    previous = data.get('Previous')
    icon = "🚨 " if breaking else ""
    msg = f"{icon}<b>{title}</b>\n\n"
    if description: msg += f"{description}\n\n"
    msg += "<b>INFO:</b>\n"
    msg += f"NewsID: {news_id}\n"
    msg += f"Tags: {tags_str}\n"
    msg += f"Breaking: {breaking}\n"
    msg += f"Level: {level}\n"
    msg += f"RURL: {r_link}\n"
    msg += f"EURL: {e_link}\n"
    msg += f"Labels: {labels_str}\n"
    msg += f"Img: {img_link}\n"
    msg += f"DatePublished: {news_time_str}\n"
    if actual or forecast:
        msg += "\n<b>DATA:</b>\n"
        msg += f"Act: {actual} | Fcst: {forecast} | Prev: {previous}\n"
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {"chat_id": TELEGRAM_CHANNEL_ID, "text": msg, "parse_mode": "HTML", "disable_web_page_preview": True}
    try:
        requests.post(url, json=payload, timeout=5)
        sys_log(f"Packet: SENT ({len(title)} chars) to Channel", Fore.MAGENTA)
    except Exception as e:
        sys_log(f"Net: Err sending to channel {e}", Fore.RED)

JS_PAYLOAD = """
window.net_spy_active = true;
window.net_captured_logs = [];
const nativeWebSocket = window.WebSocket;
window.WebSocket = function(...args) {
  const socket = new nativeWebSocket(...args);
  socket.addEventListener('message', function(event) {
    if(window.net_captured_logs && event.data && event.data !== '{}' && event.data !== '{"S":1,"M":[]}') {
        window.net_captured_logs.push({source: 'WS', data: event.data});
    }
  });
  return socket;
};
const nativeFetch = window.fetch;
window.fetch = async function(...args) {
  const response = await nativeFetch(...args);
  const clone = response.clone();
  try {
    const text = await clone.text();
    if (text && text.trim().length > 0) {
      window.net_captured_logs.push({source: 'FETCH', data: text});
    }
  } catch (e) {}
  return response;
};
const nativeOpen = XMLHttpRequest.prototype.open;
XMLHttpRequest.prototype.open = function(method, url, ...args) {
  this._url = url;
  return nativeOpen.call(this, method, url, ...args);
};
const nativeSend = XMLHttpRequest.prototype.send;
XMLHttpRequest.prototype.send = function(...args) {
  this.addEventListener('load', function() {
    try {
      const text = this.responseText;
      if (text && text.trim().length > 0) {
        window.net_captured_logs.push({source: 'XHR', data: text});
      }
    } catch (e) {}
  });
  return nativeSend.call(this, ...args);
};
const nativeEventSource = window.EventSource;
if (nativeEventSource) {
  window.EventSource = function(...args) {
    const source = new nativeEventSource(...args);
    source.addEventListener('message', function(event) {
      if (window.net_captured_logs && event.data) {
        window.net_captured_logs.push({source: 'SSE', data: event.data});
      }
    });
    return source;
  };
}
"""

def perform_login(driver):
    try:
        driver.get(TARGET_URL)
        time.sleep(7)
        sys_log(f"Debug: Page Title -> {driver.title}", Fore.CYAN)
        try:
            btns = driver.find_elements("xpath", "//a[contains(text(), 'Sign In')]")
            if btns: btns[0].click()
            else:
                btns = driver.find_elements("xpath", "//div[contains(@class, 'login')]")
                if btns: btns[0].click()
        except: 
            sys_log("Login btn skipped/not found", Fore.YELLOW)
        time.sleep(3)
        driver.find_element("css selector", "#ctl00_SignInSignUp_loginForm1_inputEmail").clear()
        driver.find_element("css selector", "#ctl00_SignInSignUp_loginForm1_inputEmail").send_keys(MY_EMAIL)
        driver.find_element("css selector", "#ctl00_SignInSignUp_loginForm1_inputPassword").clear()
        driver.find_element("css selector", "#ctl00_SignInSignUp_loginForm1_inputPassword").send_keys(MY_PASSWORD)
        driver.find_element("css selector", "#ctl00_SignInSignUp_loginForm1_btnLogin").click()
        sys_log("Auth: Credentials Sent... Waiting...", Fore.GREEN)
        time.sleep(20)
        cookies = driver.get_cookies()
        if any('.ASPXAUTH' in c['name'] for c in cookies):
            sys_log("Debug: Auth Token (.ASPXAUTH) DETECTED! ✅", Fore.GREEN)
            return True
        sys_log("Debug: Auth Token MISSING. Checking page for errors...", Fore.RED)
        try:
            body_text = driver.find_element("tag name", "body").text
            if "Invalid login" in body_text or "failed" in body_text:
                sys_log("Debug: Detected Login Error Message on page.", Fore.RED)
        except: pass
        return False
    except Exception as e:
        sys_log(f"Auth Err: {e}", Fore.RED)
        return False

def run_service():
    sys_log(f"Core: Online (Advanced Debug Mode)", Fore.CYAN)
    display = Display(visible=0, size=(1920, 1080))
    display.start()
    driver = Driver(uc=True, headless=False)
    try:
        init_telegram_commands()
        logged_in = False
        for attempt in range(1, 4):
            sys_log(f"Auth: Attempt {attempt}/3...", Fore.YELLOW)
            if perform_login(driver):
                sys_log("Status: Verified ✅", Fore.GREEN)
                logged_in = True
                break
            else:
                sys_log("Status: Failed ❌ (Retrying...)", Fore.RED)
                time.sleep(5)
        if not logged_in:
            sys_log("CRITICAL: Login failed 3 times. Exiting.", Fore.RED)
            driver.quit()
            display.stop()
            sys.exit(1)
        sys_log("Link: Established", Fore.GREEN)
        last_msg_time = time.time()
        last_cmd_check = 0
        while True:
            if time.time() - last_cmd_check > 10:
                process_telegram_commands()
                last_cmd_check = time.time()
            try: act = driver.execute_script("return window.net_spy_active;")
            except: act = False
            if not act:
                sys_log("Spy: Injecting Network Sniffer...", Fore.YELLOW)
                driver.execute_script(JS_PAYLOAD)
                time.sleep(5)
            try:
                logs = driver.execute_script("""
                    if (typeof window.net_captured_logs === 'undefined') return [];
                    return window.net_captured_logs.splice(0, window.net_captured_logs.length);
                """)
                if logs:
                    last_msg_time = time.time()
                    for packet in logs:
                        src = packet.get("source", "UNKNOWN")
                        raw_json = packet.get("data", "")
                        sys_log(f"Captured non-empty packet from {src}.", Fore.CYAN)
                        sys_log(f"Debug Raw Packet Data: {raw_json[:150]}...", Fore.MAGENTA)
                        try:
                            data_obj = json.loads(raw_json)
                            if isinstance(data_obj, list):
                                for item in data_obj:
                                    if isinstance(item, dict):
                                        dispatch_payload(item)
                            elif isinstance(data_obj, dict):
                                if 'M' in data_obj:
                                    for item in data_obj['M']:
                                        if 'A' in item and len(item['A']) > 0:
                                            payload_str = item['A'][0]
                                            if isinstance(payload_str, str) and (payload_str.startswith('[') or payload_str.startswith('{')):
                                                inner_list = json.loads(payload_str)
                                                if isinstance(inner_list, list):
                                                    for news_item in inner_list: 
                                                        dispatch_payload(news_item)
                                                else:
                                                    dispatch_payload(inner_list)
                                else:
                                    dispatch_payload(data_obj)
                        except:
                            pass
            except Exception as e_script:
                 sys_log(f"Spy script execution error: {e_script}", Fore.RED)
            if time.time() - last_msg_time > 1800:
                sys_log("Heartbeat Lost (30m). Restarting...", Fore.RED)
                break 
            time.sleep(1)
    except KeyboardInterrupt: pass
    finally:
        try: driver.quit()
        except: pass
        try: display.stop()
        except: pass

if __name__ == "__main__":
    run_service()
