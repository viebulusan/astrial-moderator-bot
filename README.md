# Astrial Telegram Group Moderator Bot (@astr1al_bot)

A lightweight, dedicated Telegram moderation bot that keeps group chats clean from clutter and unauthorized links.

---

## 🚀 Features

1. **Auto-Remove Service Messages**:
   - Automatically detects and deletes "User joined the group" (`new_chat_members`).
   - Automatically detects and deletes "User left the group" (`left_chat_member`).

2. **Block Links Sent by Regular Members**:
   - Detects all links: `https://`, `http://`, `t.me/`, web domains, and formatted hyperlinks in both text messages and media captions.
   - Monitors new messages and edited messages.
   - Instantly deletes any detected link posted by non-admin members.

3. **Admin Exemption**:
   - Group administrators and the group owner/creator can freely share links.
   - Anonymous group admins posting as the chat or linked channel are also permitted.

4. **Zero External Dependencies**:
   - Built on pure Python 3 standard libraries (`urllib`, `json`, `re`, `threading`). No `pip install` required.

---

## ⚙️ Group Setup (Mandatory)

For the bot to work in your group:
1. Open your Telegram Group.
2. Tap the group header -> **Edit** (pencil icon) -> **Administrators** -> **Add Admin**.
3. Search for `@astr1al_bot`.
4. Enable the following permission:
   - ✅ **Delete Messages** (Required to remove service notifications and spam links).

---

## 🏃 Running the Bot

### Manual Execution:
```bash
cd /home/vie-arch.1/astrial-moderator-bot
python3 bot.py
```

### Background Service via Systemd:
To keep the bot running 24/7 in the background:
```bash
# Enable and start the service
systemctl --user enable --now astrial-moderator.service

# Check service status
systemctl --user status astrial-moderator.service

# Check live logs
journalctl --user -u astrial-moderator.service -f
```
