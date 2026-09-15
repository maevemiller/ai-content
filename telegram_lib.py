"""Shared helpers for sending/receiving Telegram bot messages.

Uses long-polling (getUpdates) rather than a webhook, since this runs on a
personal Mac with no public HTTPS endpoint to receive callbacks on.
"""
import json
import subprocess
import tempfile
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

KEYCHAIN_SERVICE = "ai-content-telegram"
OFFSET_FILE_DEFAULT = None  # set by caller


def get_secret(account):
    result = subprocess.run(
        ["security", "find-generic-password", "-s", KEYCHAIN_SERVICE, "-a", account, "-w"],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        return None
    return result.stdout.strip()


def get_credentials():
    token = get_secret("bot_token")
    chat_id = get_secret("chat_id")
    return token, chat_id


def send_message(text, parse_mode=None):
    token, chat_id = get_credentials()
    if not token or not chat_id:
        raise RuntimeError("Telegram not configured — see SETUP.md")

    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {"chat_id": chat_id, "text": text}
    if parse_mode:
        payload["parse_mode"] = parse_mode
    data = urllib.parse.urlencode(payload).encode()
    req = urllib.request.Request(url, data=data, method="POST")
    with urllib.request.urlopen(req, timeout=15) as resp:
        return json.load(resp)


def get_updates(offset=None, timeout=0):
    token, _chat_id = get_credentials()
    if not token:
        raise RuntimeError("Telegram not configured — see SETUP.md")

    params = {"timeout": timeout}
    if offset is not None:
        params["offset"] = offset
    url = f"https://api.telegram.org/bot{token}/getUpdates?{urllib.parse.urlencode(params)}"
    try:
        with urllib.request.urlopen(url, timeout=timeout + 15) as resp:
            return json.load(resp).get("result", [])
    except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, json.JSONDecodeError):
        return []


def download_file(file_id, dest_path):
    token, _chat_id = get_credentials()
    if not token:
        raise RuntimeError("Telegram not configured — see SETUP.md")

    info_url = f"https://api.telegram.org/bot{token}/getFile?file_id={file_id}"
    with urllib.request.urlopen(info_url, timeout=15) as resp:
        file_path = json.load(resp)["result"]["file_path"]

    download_url = f"https://api.telegram.org/file/bot{token}/{file_path}"
    urllib.request.urlretrieve(download_url, dest_path)
    return dest_path


def extract_text(message):
    """Return the text content of a Telegram message, transcribing voice
    notes locally via mlx-whisper if that's what was sent. Returns None if
    the message has neither text nor voice content."""
    text = message.get("text")
    if text:
        return text.strip()

    voice = message.get("voice") or message.get("audio")
    if not voice:
        return None

    import transcribe

    with tempfile.TemporaryDirectory() as tmp_dir:
        audio_path = Path(tmp_dir) / "voice.oga"
        download_file(voice["file_id"], audio_path)
        return transcribe.transcribe(audio_path)


def read_offset(offset_file):
    try:
        return int(offset_file.read_text().strip())
    except (FileNotFoundError, ValueError):
        return None


def write_offset(offset_file, update_id):
    offset_file.parent.mkdir(parents=True, exist_ok=True)
    offset_file.write_text(str(update_id))


def get_new_messages(offset_file):
    """Return a list of (update_id, text) pairs from the configured chat,
    since the offset stored in offset_file. Only messages from the
    configured chat_id are included. Voice messages are transcribed locally.

    Deliberately does NOT advance the offset for any actionable message —
    the caller must call write_offset(offset_file, update_id) only after
    actually finishing whatever that message triggers (a revision, a post,
    etc.), one message at a time. Advancing the offset any earlier (e.g.
    immediately after fetching) marks the message "delivered" from
    Telegram's perspective — permanently, it will never be returned again —
    even if processing it then fails, which previously caused real feedback
    to be silently lost. (Confirming one message's update_id also confirms
    everything before it, so irrelevant/empty updates mixed in get swept up
    for free once a later actionable one is confirmed; if a whole batch has
    nothing actionable at all, it's safe to skip past immediately since
    there's nothing there that could be lost.)"""
    _token, chat_id = get_credentials()
    offset = read_offset(offset_file)

    updates = get_updates(offset=offset + 1 if offset is not None else None)
    result = []
    highest_seen = offset

    for update in updates:
        update_id = update.get("update_id")
        if highest_seen is None or update_id > highest_seen:
            highest_seen = update_id
        message = update.get("message") or {}
        if str(message.get("chat", {}).get("id")) != str(chat_id):
            continue
        text = extract_text(message)
        if text:
            result.append((update_id, text))

    if not result and highest_seen is not None and highest_seen != offset:
        write_offset(offset_file, highest_seen)

    return result
