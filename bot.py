#!/usr/bin/env python3
import asyncio
import json
import os
import random
from telethon import TelegramClient, events, Button

# -----------------------------
# ENVIRONMENT VARIABLES
# -----------------------------
API_ID = int(os.getenv("API_ID", "0"))
API_HASH = os.getenv("API_HASH", "")
BOT_TOKEN = os.getenv("BOT_TOKEN", "")
ADMIN_ID = 8150987682
SESSION_NAME = "/tmp/forward_session"
CONFIG_FILE = "forward_config.json"

# -----------------------------
# CONFIG HANDLERS
# -----------------------------
def load_config():
    if not os.path.exists(CONFIG_FILE):
        save_config({})
        return {}
    with open(CONFIG_FILE, "r") as f:
        try:
            return json.load(f)
        except json.JSONDecodeError:
            save_config({})
            return {}

def save_config(config):
    with open(CONFIG_FILE, "w") as f:
        json.dump(config, f, indent=2)

# -----------------------------
# TELETHON CLIENT
# -----------------------------
client = TelegramClient(SESSION_NAME, API_ID, API_HASH)

# -----------------------------
# MESSAGE FORWARDING
# -----------------------------
@client.on(events.NewMessage)
async def forward_handler(event):
    config = load_config()
    for user_id, user_conf in config.items():
        source = user_conf.get("source")
        targets = user_conf.get("targets", [])
        if not source or not targets:
            continue

        # If source is username or id, handle both
        if str(event.chat_id) == str(source) or getattr(event.chat, 'username', None) == source.replace("@", ""):
            for target in targets:
                try:
                    await client.send_message(target, event.message)
                    delay = random.uniform(1, 3) + (len(targets) * 0.3)
                    print(f"✅ Forwarded to {target}. Waiting {delay:.2f}s...")
                    await asyncio.sleep(delay)
                except Exception as e:
                    print(f"❌ Failed to forward to {target}: {e}")
                    await asyncio.sleep(2)

# -----------------------------
# COMMANDS
# -----------------------------
@client.on(events.NewMessage(pattern="/start"))
async def start_handler(event):
    user_id = event.sender_id
    config = load_config()

    if user_id == ADMIN_ID:
        buttons = [
            [Button.inline("📡 Set Source", b"set_source")],
            [Button.inline("➕ Add Target", b"add_target")],
            [Button.inline("📋 View Channels", b"view")],
            [Button.inline("📢 Broadcast", b"broadcast")],
            [Button.inline("📊 Stats", b"stats")],
        ]
        await event.respond("👋 Admin Menu:", buttons=buttons)
    else:
        if str(user_id) not in config:
            config[str(user_id)] = {"source": None, "targets": []}
            save_config(config)
        buttons = [
            [Button.inline("📡 Set Source", b"user_set_source")],
            [Button.inline("➕ Add Target", b"user_add_target")],
            [Button.inline("📋 View Channels", b"user_view")],
        ]
        await event.respond("👋 Manage your forwarding setup:", buttons=buttons)

# -----------------------------
# BUTTON HANDLER
# -----------------------------
@client.on(events.CallbackQuery)
async def callback_handler(event):
    user_id = event.sender_id
    data = event.data.decode("utf-8")
    config = load_config()
    user_conf = config.get(str(user_id), {"source": None, "targets": []})

    if user_id == ADMIN_ID and data == "stats":
        await event.respond(f"📊 Total users: {len(config)}")
        return
    elif user_id == ADMIN_ID and data == "broadcast":
        client._broadcasting = True
        await event.respond("📢 Send your broadcast message now.")
        return

    if data in ["set_source", "user_set_source"]:
        await event.respond("📡 Send the @username or channel ID of your source.")
        client._awaiting_source = user_id
    elif data in ["add_target", "user_add_target"]:
        await event.respond("➕ Send the @username or channel ID to add as target.")
        client._awaiting_add = user_id
    elif data in ["view", "user_view"]:
        await event.respond(f"📋 Your setup:\n• Source: {user_conf.get('source')}\n• Targets: {user_conf.get('targets', [])}")

# -----------------------------
# TEXT HANDLER (SOURCE / TARGET / BROADCAST)
# -----------------------------
@client.on(events.NewMessage)
async def text_handler(event):
    user_id = event.sender_id
    message = event.raw_text.strip()
    config = load_config()
    user_conf = config.get(str(user_id), {"source": None, "targets": []})

    # --- Broadcast (admin) ---
    if getattr(client, "_broadcasting", False) and user_id == ADMIN_ID:
        for uid in config.keys():
            try:
                await client.send_message(int(uid), message)
            except:
                pass
        client._broadcasting = False
        await event.respond("✅ Broadcast sent to all users.")
        return

    # --- Source Setup ---
    if getattr(client, "_awaiting_source", None) == user_id:
        user_conf["source"] = message
        await event.respond(f"✅ Source set: {message}")
        client._awaiting_source = None

    # --- Add Target ---
    elif getattr(client, "_awaiting_add", None) == user_id:
        targets = user_conf.get("targets", [])
        if message not in targets:
            targets.append(message)
        user_conf["targets"] = targets
        await event.respond(f"✅ Added target: {message}")
        client._awaiting_add = None

    config[str(user_id)] = user_conf
    save_config(config)

# -----------------------------
# MAIN ENTRY
# -----------------------------
async def main():
    await client.start(bot_token=BOT_TOKEN)
    print("✅ Forward bot running...")
    await client.run_until_disconnected()

if __name__ == "__main__":
    asyncio.run(main())
