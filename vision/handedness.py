"""
handedness.py

Mirror pose landmarks so a left-handed player can be compared against a
right-handed reference (and vice versa).

MediaPipe labels landmarks by the player's anatomical side. A left-hander's
backhand is the mirror image of a right-hander's, so to compare them we flip
the x axis and swap every left/right landmark pair. After that, the lefty's
dominant (left) arm occupies the role the righty's right arm plays, and all
downstream features (elbow angles, hip rotation sign, wrist speeds) line up.
"""
from __future__ import annotations

import pandas as pd

# MediaPipe Pose landmark ids: (left, right) pairs.
LEFT_RIGHT_PAIRS = [
    (1, 4), (2, 5), (3, 6),      # eyes
    (7, 8),                      # ears
    (9, 10),                     # mouth
    (11, 12),                    # shoulders
    (13, 14),                    # elbows
    (15, 16),                    # wrists
    (17, 18), (19, 20), (21, 22),  # pinky, index, thumb
    (23, 24),                    # hips
    (25, 26),                    # knees
    (27, 28),                    # ankles
    (29, 30),                    # heels
    (31, 32),                    # foot index
]
_SWAP = {}
for _l, _r in LEFT_RIGHT_PAIRS:
    _SWAP[_l] = _r
    _SWAP[_r] = _l

HANDEDNESS_OPTIONS = ("right", "left")


def normalize_handedness(value: str) -> str:
    value = (value or "right").lower().strip()
    return value if value in HANDEDNESS_OPTIONS else "right"


def mirror_landmarks(landmarks_df: pd.DataFrame) -> pd.DataFrame:
    """
    Return a mirrored copy of a landmarks DataFrame (frame, landmark_id, x, y, ...).

    x is flipped in normalized image space (x -> 1 - x) and left/right landmark
    ids are swapped. Rows are re-sorted by frame and landmark id so the result
    has the same layout as the input.
    """
    if landmarks_df is None or landmarks_df.empty:
        return landmarks_df
    df = landmarks_df.copy()
    df["x"] = 1.0 - df["x"]
    df["landmark_id"] = df["landmark_id"].map(lambda i: _SWAP.get(int(i), int(i)))
    return df.sort_values(["frame", "landmark_id"]).reset_index(drop=True)


def needs_mirroring(user_handed: str, reference_handed: str) -> bool:
    """True when the user and the reference clip have different dominant hands."""
    return normalize_handedness(user_handed) != normalize_handedness(reference_handed)
