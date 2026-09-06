"""
User profiles and session naming for the Coach AI dashboard.

Profiles are JSON files under users/<user_id>.json:

    {"user_id": "...", "name": "...", "sessions": {"<session_id>": {"name": ..., "date": ...}}}

Session ids are the timestamped output directory names (YYYY-MM-DD_HH-MM-SS).
This module is the only place that writes to users/.
"""
import json
from collections import defaultdict
from datetime import datetime
from pathlib import Path

DEFAULT_USER = "default_user"
SESSION_ID_LEN = 19  # len("2025-12-25_13-12-31")


def get_users_dir() -> Path:
    users_dir = Path("users")
    users_dir.mkdir(exist_ok=True)
    return users_dir


def get_user_profile(user_id: str) -> dict:
    profile_path = get_users_dir() / f"{user_id}.json"
    if profile_path.exists():
        with open(profile_path, "r", encoding="utf-8") as f:
            return json.load(f)
    return {"user_id": user_id, "name": user_id, "sessions": {}}


def save_user_profile(user_id: str, profile: dict) -> None:
    profile_path = get_users_dir() / f"{user_id}.json"
    with open(profile_path, "w", encoding="utf-8") as f:
        json.dump(profile, f, indent=2)


def get_all_users() -> list:
    users = sorted(f.stem for f in get_users_dir().glob("*.json"))
    return users if users else [DEFAULT_USER]


def create_user(user_id: str) -> None:
    save_user_profile(user_id, {"user_id": user_id, "name": user_id, "sessions": {}})


def link_session_to_user(user_id: str, session_id: str, session_name: str = None) -> None:
    profile = get_user_profile(user_id)
    sessions = profile.setdefault("sessions", {})
    sessions[session_id] = {
        "name": session_name or f"Session {len(sessions) + 1}",
        "date": session_id,
        "timestamp": datetime.now().isoformat(),
    }
    save_user_profile(user_id, profile)


def rename_session(user_id: str, session_id: str, new_name: str) -> bool:
    profile = get_user_profile(user_id)
    if session_id in profile.get("sessions", {}):
        profile["sessions"][session_id]["name"] = new_name
        save_user_profile(user_id, profile)
        return True
    return False


def _linked_session_ids() -> set:
    """Every session id claimed by any profile."""
    linked = set()
    for path in get_users_dir().glob("*.json"):
        try:
            with open(path, "r", encoding="utf-8") as f:
                linked.update(json.load(f).get("sessions", {}).keys())
        except (OSError, ValueError):
            continue
    return linked


def get_user_sessions(user_id: str, base_dir: str = "outputs") -> dict:
    """
    Sessions for this user, newest first.

    Output directories that no profile has claimed are adopted by this user, so
    analyses run from the CLI still show up. Sessions already claimed by another
    user are left alone.
    """
    outputs_path = Path(base_dir)
    if outputs_path.exists():
        linked = _linked_session_ids()
        for session_dir in outputs_path.iterdir():
            if (
                session_dir.is_dir()
                and len(session_dir.name) == SESSION_ID_LEN
                and session_dir.name not in linked
                and (session_dir / "report.md").exists()
            ):
                link_session_to_user(user_id, session_dir.name)

    sessions = get_user_profile(user_id).get("sessions", {})
    return dict(sorted(sessions.items(), key=lambda kv: kv[0], reverse=True))


def group_sessions_by_month(sessions: dict) -> dict:
    """{'December 2025': [(session_id, info), ...], ...} newest month first."""
    grouped = defaultdict(list)
    for session_id, info in sessions.items():
        try:
            month_key = datetime.strptime(session_id.split("_")[0], "%Y-%m-%d").strftime("%B %Y")
        except ValueError:
            month_key = "Unknown"
        grouped[month_key].append((session_id, info))

    def month_sort(key):
        return datetime.strptime(key, "%B %Y") if key != "Unknown" else datetime.min

    return {
        month: sorted(grouped[month], key=lambda kv: kv[0], reverse=True)
        for month in sorted(grouped, key=month_sort, reverse=True)
    }


def session_label(session_id: str, info: dict = None, score: float = None) -> str:
    """'Session 3 · 2025-12-27 17:56 · 71.2/100' for selectors."""
    parts = session_id.split("_")
    date_str = parts[0]
    time_str = parts[1][:5].replace("-", ":") if len(parts) > 1 else ""
    name = (info or {}).get("name") or session_id
    label = f"{name} · {date_str} {time_str}".strip()
    if score is not None:
        label += f" · {score:.1f}/100"
    return label
