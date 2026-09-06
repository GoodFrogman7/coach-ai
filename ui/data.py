"""
Read-only session data helpers for the Coach AI dashboard.

Everything here reads from outputs/<session_id>/report.md. Nothing writes.
"""
import sys
import re
from pathlib import Path
from datetime import datetime

# The vision package lives one level up from ui/.
ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

# Intelligence helpers are optional so the dashboard still loads (read-only
# pages) when heavy pipeline dependencies are missing.
try:
    from vision.compare import (
        load_historical_sessions,
        compute_player_baseline,
        generate_progress_narrative,
        compute_drill_confidence_scores,
    )
except ImportError:
    load_historical_sessions = None
    compute_player_baseline = None
    generate_progress_narrative = None
    compute_drill_confidence_scores = None


def get_latest_session(base_dir: str = "outputs") -> str:
    """Get most recent session directory."""
    try:
        outputs_path = Path(base_dir)
        if not outputs_path.exists():
            return None
        
        sessions = [d.name for d in outputs_path.iterdir() if d.is_dir() and len(d.name) == 19]
        if not sessions:
            return None
        
        return sorted(sessions, reverse=True)[0]
    except:
        return None


def get_recent_sessions(base_dir: str = "outputs", n: int = 10) -> list:
    """Get N most recent session IDs."""
    try:
        outputs_path = Path(base_dir)
        if not outputs_path.exists():
            return []
        
        sessions = [d.name for d in outputs_path.iterdir() if d.is_dir() and len(d.name) == 19]
        return sorted(sessions, reverse=True)[:n]
    except:
        return []


def load_report_data(session_id: str, base_dir: str = "outputs") -> dict:
    """Load all relevant data from session report."""
    try:
        report_path = Path(base_dir) / session_id / "report.md"
        if not report_path.exists():
            return None
        
        with open(report_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        data = {'session_id': session_id, 'raw_content': content}
        
        # Extract technique score (updated format)
        match = re.search(r'Overall Technique Score:\s*(\d+\.?\d*)/100', content)
        if match:
            data['technique_score'] = float(match.group(1))
        else:
            # Fallback to old format
            match = re.search(r'Overall Similarity:\s*\*\*(\d+\.?\d*)%\*\*', content)
            if match:
                data['technique_score'] = float(match.group(1))
        
        # Extract readiness score (use technique score if readiness not found)
        match = re.search(r'## 🎯 Match Readiness Assessment.*?Score\*\*:\s*(\d+\.?\d*)/100', content, re.DOTALL)
        if match:
            data['readiness_score'] = float(match.group(1))
            
            # Extract readiness level
            level_match = re.search(r'Overall Readiness:.*?(Excellent|Good|Fair|Poor)', content)
            if level_match:
                data['readiness_level'] = level_match.group(1)
            
            # Extract readiness confidence
            conf_match = re.search(r'Confidence:\s*(\d+)%', content)
            if conf_match:
                data['readiness_confidence'] = int(conf_match.group(1))
        else:
            # Use technique score as fallback readiness score
            if 'technique_score' in data:
                data['readiness_score'] = data['technique_score']
                # Determine level based on score
                score = data['technique_score']
                if score >= 80:
                    data['readiness_level'] = 'Excellent'
                elif score >= 65:
                    data['readiness_level'] = 'Good'
                elif score >= 45:
                    data['readiness_level'] = 'Fair'
                else:
                    data['readiness_level'] = 'Poor'
                data['readiness_confidence'] = int(min(score, 80))  # Confidence based on score
        
        # Extract training load recommendation
        match = re.search(r'Recommended Session:\s*(\w+)', content)
        if match:
            data['session_type'] = match.group(1)
        else:
            # Infer from technique score
            if 'technique_score' in data:
                score = data['technique_score']
                if score < 50:
                    data['session_type'] = 'Technique'
                elif score < 70:
                    data['session_type'] = 'Refinement'
                else:
                    data['session_type'] = 'Maintenance'
        
        match = re.search(r'Intensity\*\*:.*?(Low|Moderate|High)', content)
        if match:
            data['intensity'] = match.group(1)
        else:
            # Infer intensity
            if 'technique_score' in data:
                score = data['technique_score']
                if score < 60:
                    data['intensity'] = 'Moderate'
                else:
                    data['intensity'] = 'Low'
        
        # Extract focus areas from "Today's Focus" section
        focus_section = re.search(r'## Today\'s Focus.*?Your Top.*?:\s*\n(.*?)\n##', content, re.DOTALL)
        if focus_section:
            focus_text = focus_section.group(1)
            # Extract numbered priorities
            priorities = re.findall(r'\d+\.\s*\*\*\[?([^\]]*?)\]?\*\*\s*(.*?)(?=\n\d+\.|\n\n|\*Primary)', focus_text, re.DOTALL)
            data['focus_areas'] = []
            for phase, description in priorities:
                clean_desc = description.strip().split('\n')[0]  # Get first line only
                data['focus_areas'].append(f"{phase}: {clean_desc}")
        
        # Extract suggested drills
        drill_section = re.search(r'## Suggested Drills.*?\n(.*?)\n---', content, re.DOTALL)
        if drill_section:
            drill_text = drill_section.group(1)
            # Extract drill titles and descriptions
            drills = re.findall(r'### Drill \d+\s*\n\s*\*\*(.*?)\*\*:\s*(.*?)(?=\n\n|### Drill|\Z)', drill_text, re.DOTALL)
            data['drills'] = []
            for title, description in drills:
                data['drills'].append({
                    'title': title.strip(),
                    'description': description.strip()
                })
        
        # Extract avoid areas
        avoid_section = re.search(r'### ⚠️ Areas to Avoid.*?\n(.*?)\n\n', content, re.DOTALL)
        if avoid_section:
            avoid_text = avoid_section.group(1)
            data['avoid_areas'] = [line.strip('- ').strip() for line in avoid_text.split('\n') if line.strip().startswith('-')]
        
        # Extract progress narrative
        narrative_section = re.search(r'### Progress Summary.*?\n\n(.*?)\n\n', content, re.DOTALL)
        if narrative_section:
            data['progress_summary'] = narrative_section.group(1).strip()
        
        # Extract coach's take
        coach_section = re.search(r"### 🎓 Coach's Take\n\n(.*?)\n\n", content, re.DOTALL)
        if coach_section:
            data['coach_take'] = coach_section.group(1).strip()
        
        # Extract baseline comparisons
        baseline_section = re.search(r"Today's Session vs Your Baseline(.*?)###", content, re.DOTALL)
        if baseline_section:
            baseline_text = baseline_section.group(1)
            data['baseline_comparisons'] = []
            
            for line in baseline_text.split('\n'):
                if '📈' in line or '📉' in line or '➡️' in line:
                    data['baseline_comparisons'].append(line.strip('*').strip())
        
        return data
    except:
        return None


def calculate_streak(base_dir: str = "outputs") -> int:
    """Calculate training streak (consecutive days with sessions)."""
    try:
        sessions = get_recent_sessions(base_dir, n=30)
        if not sessions:
            return 0
        
        # Parse dates
        dates = []
        for session_id in sessions:
            try:
                date_str = session_id.split('_')[0]
                date = datetime.strptime(date_str, '%Y-%m-%d').date()
                dates.append(date)
            except:
                continue
        
        if not dates:
            return 0
        
        dates = sorted(set(dates), reverse=True)  # Unique dates, newest first
        
        # Calculate streak
        streak = 1
        current_date = dates[0]
        
        for i in range(1, len(dates)):
            next_date = dates[i]
            diff = (current_date - next_date).days
            
            if diff == 1:
                streak += 1
                current_date = next_date
            elif diff > 1:
                break
        
        return streak
    except:
        return 0


def calculate_achievements(base_dir: str = "outputs") -> dict:
    """Calculate achievement badges."""
    try:
        sessions = get_recent_sessions(base_dir, n=30)
        streak = calculate_streak(base_dir)
        
        # Load historical data for improvement tracking
        historical = None
        baseline = None
        
        if load_historical_sessions and compute_player_baseline:
            historical = load_historical_sessions(base_dir, max_sessions=10)
            if historical and len(historical) >= 3:
                baseline = compute_player_baseline(historical, min_sessions=3)
        
        achievements = {
            'consistency': [],
            'improvement': [],
            'discipline': []
        }
        
        # Consistency badges
        if streak >= 7:
            achievements['consistency'].append({
                'name': 'Week Warrior',
                'description': '7-day training streak',
                'icon': '🔥',
                'unlocked': True
            })
        else:
            achievements['consistency'].append({
                'name': 'Week Warrior',
                'description': f'{streak}/7 days',
                'icon': '🔒',
                'unlocked': False
            })
        
        if streak >= 14:
            achievements['consistency'].append({
                'name': 'Fortnight Fighter',
                'description': '14-day training streak',
                'icon': '⚡',
                'unlocked': True
            })
        else:
            achievements['consistency'].append({
                'name': 'Fortnight Fighter',
                'description': f'{streak}/14 days',
                'icon': '🔒',
                'unlocked': False
            })
        
        if streak >= 30:
            achievements['consistency'].append({
                'name': 'Monthly Master',
                'description': '30-day training streak',
                'icon': '👑',
                'unlocked': True
            })
        else:
            achievements['consistency'].append({
                'name': 'Monthly Master',
                'description': f'{streak}/30 days',
                'icon': '🔒',
                'unlocked': False
            })
        
        # Improvement badges
        if baseline and baseline.get('has_baseline'):
            # Check if technique improved vs baseline
            latest_data = load_report_data(sessions[0]) if sessions else None
            
            if latest_data and 'technique_score' in latest_data:
                baseline_tech = baseline.get('baseline_technique_score', 0)
                current_tech = latest_data['technique_score']
                
                if current_tech > baseline_tech * 1.05:  # 5% improvement
                    achievements['improvement'].append({
                        'name': 'Technique Boost',
                        'description': '5% above baseline',
                        'icon': '📈',
                        'unlocked': True
                    })
                else:
                    achievements['improvement'].append({
                        'name': 'Technique Boost',
                        'description': 'Reach 5% above baseline',
                        'icon': '🔒',
                        'unlocked': False
                    })
                
                if current_tech > baseline_tech * 1.10:  # 10% improvement
                    achievements['improvement'].append({
                        'name': 'Breakthrough',
                        'description': '10% above baseline',
                        'icon': '🌟',
                        'unlocked': True
                    })
                else:
                    achievements['improvement'].append({
                        'name': 'Breakthrough',
                        'description': 'Reach 10% above baseline',
                        'icon': '🔒',
                        'unlocked': False
                    })
        
        # Discipline badges
        if len(sessions) >= 5:
            achievements['discipline'].append({
                'name': 'Committed',
                'description': '5+ sessions logged',
                'icon': '🎯',
                'unlocked': True
            })
        else:
            achievements['discipline'].append({
                'name': 'Committed',
                'description': f'{len(sessions)}/5 sessions',
                'icon': '🔒',
                'unlocked': False
            })
        
        if len(sessions) >= 10:
            achievements['discipline'].append({
                'name': 'Dedicated',
                'description': '10+ sessions logged',
                'icon': '💪',
                'unlocked': True
            })
        else:
            achievements['discipline'].append({
                'name': 'Dedicated',
                'description': f'{len(sessions)}/10 sessions',
                'icon': '🔒',
                'unlocked': False
            })
        
        return achievements
    except Exception:
        return {'consistency': [], 'improvement': [], 'discipline': []}
