#!/usr/bin/env python3
"""
Telegram Group Moderator Bot (@astr1al_bot)
-------------------------------------------
Features:
1. Deletes "User joined the group" and "User left the group" service messages automatically.
2. Deletes links/URLs/Telegram invite links sent by regular members (both new and edited messages).
3. Allows group administrators and creator to freely send links.
4. Zero external dependencies - pure Python standard library.
"""

import sys
import os
import json
import time
import re
import urllib.request
import urllib.parse
import urllib.error
import threading
from datetime import datetime
from http.server import HTTPServer, BaseHTTPRequestHandler

# Regex pattern for link detection (URLs, domains, t.me invite links, www links)
LINK_REGEX = re.compile(
    r'(https?://[^\s]+)|'
    r'(\b[a-zA-Z0-9-]+\.(?:com|org|net|io|me|xyz|ph|co|vip|app|site|top|cc|online|pro|info|live|shop|club|store|tech|fun|space|link|ai|gg|dev|biz|tv)\b[^\s]*)'
    r'|(t\.me/[^\s]+)|(telegram\.me/[^\s]+)|(www\.[^\s]+)',
    re.IGNORECASE
)

def log(msg: str):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{timestamp}] {msg}", flush=True)

class AstrialModeratorBot:
    def __init__(self, token: str):
        self.token = token.strip()
        self.api_url = f"https://api.telegram.org/bot{self.token}"
        self.last_update_id = 0
        self.admin_cache = {}  # (chat_id, user_id) -> (is_admin, expire_timestamp)
        self.bot_username = ""
        self.bot_id = None

    def request(self, method: str, data: dict = None) -> dict:
        url = f"{self.api_url}/{method}"
        headers = {"Content-Type": "application/json"}
        req_data = json.dumps(data).encode("utf-8") if data else None

        req = urllib.request.Request(url, data=req_data, headers=headers)
        try:
            with urllib.request.urlopen(req, timeout=35) as response:
                return json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            try:
                err_resp = json.loads(e.read().decode("utf-8"))
                return err_resp
            except Exception:
                return {"ok": False, "description": str(e)}
        except Exception as e:
            return {"ok": False, "description": str(e)}

    def delete_message(self, chat_id: int, message_id: int) -> bool:
        res = self.request("deleteMessage", {
            "chat_id": chat_id,
            "message_id": message_id
        })
        return res.get("ok", False)

    def send_message(self, chat_id: int, text: str, parse_mode: str = "Markdown") -> dict:
        return self.request("sendMessage", {
            "chat_id": chat_id,
            "text": text,
            "parse_mode": parse_mode
        })

    def is_user_admin(self, chat_id: int, user_id: int) -> bool:
        cache_key = (chat_id, user_id)
        now = time.time()
        
        # Check cached admin status (valid for 60 seconds)
        if cache_key in self.admin_cache:
            is_adm, exp = self.admin_cache[cache_key]
            if now < exp:
                return is_adm

        res = self.request("getChatMember", {
            "chat_id": chat_id,
            "user_id": user_id
        })
        if res.get("ok"):
            status = res.get("result", {}).get("status", "")
            is_admin = status in ["creator", "administrator"]
            self.admin_cache[cache_key] = (is_admin, now + 60)
            return is_admin
        return False

    def message_contains_links(self, msg: dict) -> bool:
        text = msg.get("text") or msg.get("caption") or ""

        # 1. Check native Telegram message entities (hyperlinks and URLs)
        entities = msg.get("entities") or msg.get("caption_entities") or []
        for ent in entities:
            if ent.get("type") in ["url", "text_link"]:
                return True

        # 2. Check regex in text or caption
        if text and LINK_REGEX.search(text):
            return True

        return False

    def handle_message(self, msg: dict, is_edit: bool = False):
        chat = msg.get("chat", {})
        chat_id = chat.get("id")
        chat_type = chat.get("type", "")
        message_id = msg.get("message_id")

        if not chat_id or not message_id:
            return

        # Handle private chats (for /start and status checks)
        if chat_type == "private":
            text = (msg.get("text") or "").strip()
            if text in ["/start", "/help", "/status", "/ping"]:
                self.send_message(
                    chat_id,
                    f"👋 Hello! I am @{self.bot_username} — Group Moderator Bot.\n\n"
                    "🛡️ *Features:*\n"
                    "• Automatically deletes 'User joined' & 'User left' service messages.\n"
                    "• Automatically deletes links sent by regular members.\n"
                    "• Permits administrators to share links.\n\n"
                    "📌 *Setup:* Add me to your Telegram group and promote me to *Administrator* with 'Delete Messages' permission!"
                )
            return

        # Only process group and supergroup messages
        if chat_type not in ["group", "supergroup"]:
            return

        # -------------------------------------------------------------
        # 1. Clean service messages ("User joined" / "User left")
        # -------------------------------------------------------------
        if "new_chat_members" in msg or "new_chat_participant" in msg:
            log(f"[CLEANUP] Deleted 'user joined' message (ID: {message_id}) in group {chat_id}")
            self.delete_message(chat_id, message_id)
            return

        if "left_chat_member" in msg or "left_chat_participant" in msg:
            log(f"[CLEANUP] Deleted 'user left' message (ID: {message_id}) in group {chat_id}")
            self.delete_message(chat_id, message_id)
            return

        # -------------------------------------------------------------
        # 2. Check Sender Authority (Admin vs Member)
        # -------------------------------------------------------------
        sender_chat = msg.get("sender_chat")
        from_user = msg.get("from", {})
        user_id = from_user.get("id")
        username = from_user.get("username") or from_user.get("first_name") or f"User-{user_id}"

        # If sent as anonymous group admin or linked group channel, exempt
        is_sender_group_owner = sender_chat and (sender_chat.get("id") == chat_id)
        is_admin = is_sender_group_owner or (user_id and self.is_user_admin(chat_id, user_id))

        # Admin helper command: /status or /ping
        text = (msg.get("text") or "").strip()
        cmd_text = text.lower()
        bot_suffix = f"@{self.bot_username.lower()}" if self.bot_username else ""
        if is_admin and (cmd_text in ["/status", "/ping", f"/status{bot_suffix}", f"/ping{bot_suffix}"]):
            sent = self.send_message(
                chat_id,
                f"🛡️ *@{self.bot_username} is Active & Protecting this Group!*\n\n"
                "• *Join/Leave Service Messages:* Auto-removed\n"
                "• *Member Links:* Blocked & Removed\n"
                "• *Admin Links:* Allowed"
            )
            bot_msg_id = sent.get("result", {}).get("message_id") if sent.get("ok") else None
            # Clean up the command and response after 8 seconds
            def cleanup_command():
                if bot_msg_id:
                    self.delete_message(chat_id, bot_msg_id)
                self.delete_message(chat_id, message_id)
            threading.Timer(8.0, cleanup_command).start()
            return

        # Admins are allowed to post links freely!
        if is_admin:
            return

        # -------------------------------------------------------------
        # 3. Detect & Remove Links from Regular Members
        # -------------------------------------------------------------
        if self.message_contains_links(msg):
            deleted = self.delete_message(chat_id, message_id)
            action = "edited message" if is_edit else "message"
            if deleted:
                log(f"[BLOCKED] Deleted link from member @{username} in {action} (Chat ID: {chat_id}, Msg ID: {message_id})")
            else:
                log(f"[WARNING] Could not delete link from @{username}. Ensure @{self.bot_username} is an Admin with 'Delete Messages' permission!")

    def start_polling(self):
        log("==================================================")
        log(" 🛡️ Starting Astrial Group Moderator Bot...")
        log(" - Join/Leave Notice Removal: ACTIVE")
        log(" - Member Link Deletion: ACTIVE")
        log(" - Admin Link Exemption: ACTIVE")
        log("==================================================")

        me = self.request("getMe")
        if not me.get("ok"):
            log(f"❌ Failed to verify bot token: {me.get('description')}")
            sys.exit(1)

        result = me.get("result", {})
        self.bot_username = result.get("username", "")
        self.bot_id = result.get("id")
        log(f"✅ Successfully logged in as @{self.bot_username} (Name: {result.get('first_name')}, ID: {self.bot_id})")
        log("Listening for updates...")

        while True:
            try:
                updates = self.request("getUpdates", {
                    "offset": self.last_update_id + 1,
                    "timeout": 25,
                    "allowed_updates": ["message", "edited_message"]
                })

                if updates.get("ok"):
                    for update in updates.get("result", []):
                        self.last_update_id = update.get("update_id")
                        if "message" in update:
                            self.handle_message(update["message"], is_edit=False)
                        elif "edited_message" in update:
                            self.handle_message(update["edited_message"], is_edit=True)
                else:
                    time.sleep(2)
            except KeyboardInterrupt:
                log("Bot stopped by user.")
                break
            except Exception as e:
                log(f"Polling error: {e}")
                time.sleep(3)

def load_token() -> str:
    # 1. Command-line argument
    if len(sys.argv) > 1 and sys.argv[1].strip():
        return sys.argv[1].strip()

    # 2. Environment variable
    if os.environ.get("TELEGRAM_BOT_TOKEN"):
        return os.environ.get("TELEGRAM_BOT_TOKEN").strip()

    # 3. .env file
    env_file = os.path.join(os.path.dirname(__file__), ".env")
    if os.path.isfile(env_file):
        with open(env_file, "r") as f:
            for line in f:
                line = line.strip()
                if line.startswith("TELEGRAM_BOT_TOKEN="):
                    return line.split("=", 1)[1].strip().strip('"').strip("'")

    # 4. Fallback provided token
    return "8873818882:AAGwrYDbVX2jwpeKZIFzXaQ-YlcfEXImydw"

class HealthCheckHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        payload = {
            "status": "online",
            "service": "Astrial Telegram Moderator Bot",
            "bot": "@astr1al_bot",
            "timestamp": datetime.now().isoformat()
        }
        self.wfile.write(json.dumps(payload).encode("utf-8"))

    def log_message(self, format, *args):
        # Silence routine HTTP health check logs
        pass

def run_http_server(port: int):
    try:
        server = HTTPServer(("0.0.0.0", port), HealthCheckHandler)
        log(f"🌐 HTTP health server listening on port {port} (Render / Cloud ready)")
        server.serve_forever()
    except Exception as e:
        log(f"HTTP health server notice: {e}")

def main():
    token = load_token()
    
    # Start HTTP health server for cloud deployment (e.g. Render)
    port = int(os.environ.get("PORT", "10000"))
    threading.Thread(target=run_http_server, args=(port,), daemon=True).start()

    bot = AstrialModeratorBot(token)
    bot.start_polling()

if __name__ == "__main__":
    main()

