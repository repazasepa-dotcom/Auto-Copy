#!/usr/bin/env python3
import asyncio, os, random, threading, json
from telethon import TelegramClient, events, Button
from flask import Flask
import requests

# -----------------------------
# ENV VARS
# -----------------------------
API_ID = int(os.getenv("API_ID", "0"))
API_HASH = os.getenv("API_HASH", "")
BOT_TOKEN = os.getenv("BOT_TOKEN", "")
ADMIN_ID = 8150987682

UP_URL = os.getenv("UPSTASH_REDIS_REST_URL")
UP_TOKEN = os.getenv("UPSTASH_REDIS_REST_TOKEN")

SESSION_NAME = "/tmp/forward_session"

# -----------------------------
# REDIS HELPERS
# -----------------------------
def redis_get(key):
    r = requests.get(f"{UP_URL}/get/{key}", headers={"Authorization": f"Bearer {UP_TOKEN}"})
    try:
        return json.loads(r.json().get("result", "{}"))
    except:
        return {}

def redis_set(key, value):
    requests.post(
        f"{UP_URL}/set/{key}",
        headers={"Authorization": f"Bearer {UP_TOKEN}"},
        json=value
    )

CONFIG_KEY = "forward_bot_config"

def load_config():
    return redis_get(CONFIG_KEY)

def save_config(cfg):
    redis_set(CONFIG_KEY, cfg)

# -----------------------------
# TELETHON CLIENT
# -----------------------------
client = TelegramClient(SESSION_NAME, API_ID, API_HASH)

# -----------------------------
# MESSAGE FORWARDING
# -----------------------------
@client.on(events.NewMessage(incoming=True))
async def forward_handler(event):
    if event.is_private: return

    config = load_config()
    for user_id, user_conf in config.items():
        source = user_conf.get("source")
        tgts = user_conf.get("targets", [])

        if not source or not tgts: continue

        if str(event.chat_id) == str(source) or getattr(event.chat, 'username', None) == source.replace("@", ""):
            for t in tgts:
                try:
                    if event.message.fwd_from:
                        await client.forward_messages(t, event.message, from_peer=event.chat_id)
                    else:
                        await client.send_message(t, event.message)

                    await asyncio.sleep(random.uniform(1,3) + len(tgts)*0.3)
                except:
                    await asyncio.sleep(2)

# -----------------------------
# START COMMAND
# -----------------------------
@client.on(events.NewMessage(pattern="/start"))
async def start(event):
    uid = event.sender_id
    cfg = load_config()
    if str(uid) not in cfg:
        cfg[str(uid)] = {"source": None, "targets": []}
        save_config(cfg)

    if uid == ADMIN_ID:
        btns = [
            [Button.inline("📡 Set Source", b"set_source")],
            [Button.inline("➕ Add Target", b"add_target")],
            [Button.inline("❌ Remove Source", b"remove_source")],
            [Button.inline("🗑 Remove Target", b"remove_target")],
            [Button.inline("📋 View Channels", b"view")],
            [Button.inline("📢 Broadcast", b"broadcast")],
            [Button.inline("📊 Stats", b"stats")],
        ]
        await event.respond("👑 Admin Panel:", buttons=btns)
    else:
        btns = [
            [Button.inline("📡 Set Source", b"user_set_source")],
            [Button.inline("➕ Add Target", b"user_add_target")],
            [Button.inline("❌ Remove Source", b"user_remove_source")],
            [Button.inline("🗑 Remove Target", b"user_remove_target")],
            [Button.inline("📋 View Channels", b"user_view")],
        ]
        await event.respond("👋 Forward Setup:", buttons=btns)

# -----------------------------
# BUTTONS
# -----------------------------
@client.on(events.CallbackQuery)
async def callback(event):
    uid = event.sender_id
    data = event.data.decode()
    cfg = load_config()
    user = cfg.get(str(uid), {"source": None, "targets": []})

    if uid == ADMIN_ID and data == "stats":
        await event.respond(f"📊 Total users: {len(cfg)}")
        return
    if uid == ADMIN_ID and data == "broadcast":
        client._broadcasting = True
        await event.respond("📢 Send broadcast:")
        return

    if data in ["set_source","user_set_source"]:
        client._awaiting_source = uid
        await event.respond("📡 Input source channel (@ or ID)")
        return

    if data in ["add_target","user_add_target"]:
        client._awaiting_add = uid
        await event.respond("➕ Send target channel (@ or ID)")
        return

    if data in ["remove_source","user_remove_source"]:
        src = user.get("source")
        if not src: return await event.respond("⚠️ No source")
        btn = [
            [Button.inline(f"✅ Remove {src}", b"confirm_remove_source")],
            [Button.inline("❌ Cancel", b"cancel")]
        ]
        await event.respond(f"Remove {src}?", buttons=btn)
        return

    if data == "confirm_remove_source":
        user["source"] = None
        cfg[str(uid)] = user
        save_config(cfg)
        return await event.respond("✅ Source removed")

    if data == "remove_target" or data=="user_remove_target":
        tg = user.get("targets", [])
        if not tg: return await event.respond("⚠️ No targets")
        btn = [[Button.inline(f"❌ {t}", f"del:{t}")] for t in tg]
        btn.append([Button.inline("Cancel", b"cancel")])
        return await event.respond("Remove which?", buttons=btn)

    if data.startswith("del:"):
        t = data[4:]
        tg = user.get("targets", [])
        if t in tg: tg.remove(t)
        user["targets"] = tg
        cfg[str(uid)] = user
        save_config(cfg)
        return await event.respond(f"✅ Removed {t}")

    if data in ["view","user_view"]:
        return await event.respond(f"📋 Source: {user.get('source')}\n🎯 Targets: {user.get('targets')}")

# -----------------------------
# TEXT HANDLER (DM ONLY)
# -----------------------------
@client.on(events.NewMessage(incoming=True))
async def text(event):
    if not event.is_private: return

    uid = event.sender_id
    msg = event.raw_text.strip()
    cfg = load_config()
    user = cfg.get(str(uid), {"source": None, "targets": []})

    if getattr(client, "_broadcasting", False) and uid == ADMIN_ID:
        for u in cfg.keys():
            try: await client.send_message(int(u), msg)
            except: pass
        client._broadcasting = False
        return await event.respond("✅ Sent")

    if getattr(client, "_awaiting_source", None) == uid:
        user["source"] = msg
        client._awaiting_source = None
        cfg[str(uid)] = user
        save_config(cfg)
        return await event.respond(f"✅ Source set: {msg}")

    if getattr(client, "_awaiting_add", None) == uid:
        tg = user.get("targets", [])
        if msg not in tg: tg.append(msg)
        user["targets"] = tg
        client._awaiting_add = None
        cfg[str(uid)] = user
        save_config(cfg)
        return await event.respond(f"✅ Target added: {msg}")

# -----------------------------
# KEEP ALIVE (RENDER)
# -----------------------------
app = Flask(__name__)

@app.route('/')
def home():
    return "✅ Redis Forward Bot Running"

def run_web():
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)

# -----------------------------
# START BOT
# -----------------------------
async def main():
    await client.start(bot_token=BOT_TOKEN)
    print("✅ Bot Live (Redis Mode)")
    await client.run_until_disconnected()

if __name__ == "__main__":
    threading.Thread(target=run_web, daemon=True).start()
    asyncio.run(main())
