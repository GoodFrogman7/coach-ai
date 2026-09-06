"""
Migrate existing sessions to user profile system
"""

import json
from pathlib import Path

def migrate_sessions():
    """Link all existing sessions to default_user."""
    
    # Create users directory
    users_dir = Path("users")
    users_dir.mkdir(exist_ok=True)
    
    # Create default user profile
    default_user = {
        "user_id": "default_user",
        "name": "Default User",
        "sessions": {}
    }
    
    # Find all existing sessions
    outputs_dir = Path("outputs")
    if outputs_dir.exists():
        session_count = 0
        for session_dir in sorted(outputs_dir.iterdir(), reverse=True):
            if session_dir.is_dir() and len(session_dir.name) == 19:
                # Check if session has a report (is complete)
                has_report = (session_dir / "report.md").exists()
                
                session_id = session_dir.name
                default_user["sessions"][session_id] = {
                    "name": f"Session {session_count + 1}" if has_report else "Incomplete Session",
                    "date": session_id,
                    "complete": has_report
                }
                session_count += 1
        
        print(f"[OK] Found {session_count} sessions")
    
    # Save default user profile
    profile_path = users_dir / "default_user.json"
    with open(profile_path, 'w') as f:
        json.dump(default_user, f, indent=2)
    
    print(f"[OK] Created user profile: {profile_path}")
    print(f"[OK] Linked {len(default_user['sessions'])} sessions to default_user")
    print("\nMigration complete!")

if __name__ == "__main__":
    migrate_sessions()
