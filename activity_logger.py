import json
import os
from collections import Counter
from datetime import datetime, timezone


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _safe_iso_to_datetime(value: str):
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except Exception:
        return None


def _ensure_parent_directory(file_path: str) -> None:
    directory = os.path.dirname(file_path)
    if directory:
        os.makedirs(directory, exist_ok=True)


def _safe_write_jsonl(file_path: str, entry: dict) -> None:
    _ensure_parent_directory(file_path)
    with open(file_path, "a", encoding="utf-8") as file_handle:
        file_handle.write(json.dumps(entry, ensure_ascii=False) + "\n")


def log_activity(
    file_path: str,
    event_type: str,
    user_id: str,
    chat_id: str,
    route: str,
    username: str = "",
    display_name: str = "",
) -> None:
    entry = {
        "timestamp": _now_iso(),
        "event_type": event_type,
        "route": route,
        "telegram_user_id": str(user_id),
        "chat_id": str(chat_id),
        "username": username or "",
        "display_name": display_name or "",
    }
    try:
        _safe_write_jsonl(file_path, entry)
    except Exception as error:
        print(f"Activity log write error: {error}")


def _read_entries(file_path: str, max_entries: int = 10000):
    if not os.path.exists(file_path):
        return []

    entries = []
    try:
        with open(file_path, "r", encoding="utf-8") as file_handle:
            for line in file_handle:
                stripped_line = line.strip()
                if not stripped_line:
                    continue
                try:
                    entries.append(json.loads(stripped_line))
                except json.JSONDecodeError:
                    continue
    except Exception as error:
        print(f"Activity log read error: {error}")
        return []

    if len(entries) > max_entries:
        entries = entries[-max_entries:]
    return entries


def get_recent_user_activity(file_path: str, limit: int = 20):
    entries = _read_entries(file_path)
    user_map = {}

    for entry in entries:
        user_id = str(entry.get("telegram_user_id", "")).strip()
        if not user_id:
            continue

        timestamp = str(entry.get("timestamp", ""))
        existing = user_map.get(user_id)
        if not existing:
            user_map[user_id] = {
                "telegram_user_id": user_id,
                "username": entry.get("username", ""),
                "display_name": entry.get("display_name", ""),
                "count": 1,
                "first_seen": timestamp,
                "last_seen": timestamp,
            }
            continue

        existing["count"] += 1
        if timestamp and (not existing["first_seen"] or timestamp < existing["first_seen"]):
            existing["first_seen"] = timestamp
        if timestamp and (not existing["last_seen"] or timestamp > existing["last_seen"]):
            existing["last_seen"] = timestamp
        if entry.get("username"):
            existing["username"] = entry.get("username")
        if entry.get("display_name"):
            existing["display_name"] = entry.get("display_name")

    users = list(user_map.values())
    users.sort(key=lambda item: item.get("last_seen", ""), reverse=True)
    return users[:limit]


def get_activity_stats(file_path: str):
    entries = _read_entries(file_path)
    now_utc = datetime.now(timezone.utc)
    event_counter = Counter()
    unique_users = set()
    today_users = set()
    today_events = 0

    for entry in entries:
        user_id = str(entry.get("telegram_user_id", "")).strip()
        if user_id:
            unique_users.add(user_id)

        event_type = str(entry.get("event_type", "unknown"))
        event_counter[event_type] += 1

        dt = _safe_iso_to_datetime(str(entry.get("timestamp", "")))
        if not dt:
            continue

        if dt.date() == now_utc.date():
            today_events += 1
            if user_id:
                today_users.add(user_id)

    return {
        "total_events": len(entries),
        "total_unique_users": len(unique_users),
        "today_events": today_events,
        "today_unique_users": len(today_users),
        "event_breakdown": dict(event_counter),
    }