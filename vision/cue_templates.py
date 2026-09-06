"""
cue_templates.py

Coaching cue and drill wording, keyed by stroke.

The backhand entries are byte-identical to the strings that used to live inline
in similarity.py, so a backhand report renders exactly as before. Every other
stroke overrides only the keys where the coaching language differs; anything
missing falls back to the backhand wording via get_cue().

Keys
    <metric>.<direction>      impact-metric cues (high/low, or low_abs/high_abs
                              for signed metrics such as hip rotation)
    knee_angle_avg.high/low   combined knee bend cue
    <phase>.<topic>           phase-specific cues
    fallback.N                generic cues used when fewer than three fire
    drill.<topic>             drill text for generate_drills()
"""
from __future__ import annotations

BACKHAND = {
    "left_elbow_angle.high": "**Bend your left elbow more** at contact. Your arm is too straight, reducing control and power transfer.",
    "left_elbow_angle.low": "**Extend your left elbow slightly more** through contact. A bit more extension will add reach and power.",
    "right_elbow_angle.high": "**Keep your right elbow closer to your body** for better stability. Think 'compact arms' through the stroke.",
    "right_elbow_angle.low": "**Allow your right elbow to extend more** through the hitting zone for better racquet speed.",
    "hip_rotation.low_abs": "**Rotate your hips more** into the shot. Your upper body is doing most of the work—engage those hips!",
    "hip_rotation.high_abs": "**Control your hip rotation**. Over-rotation can throw off your timing and balance.",
    "spine_lean.high": "**Stay more upright** through contact. You're leaning too much, which affects balance.",
    "spine_lean.low": "**Lean into the shot slightly more** for better weight transfer through the ball.",
    "stance_width_normalized.low": "**Widen your stance** for a more stable base. You'll generate more power from your legs.",
    "stance_width_normalized.high": "**Narrow your stance slightly**. Too wide limits your hip rotation and recovery speed.",
    "knee_angle_avg.high": "**Bend your knees more** throughout the stroke. Lower stance = more power from the ground up.",
    "knee_angle_avg.low": "**Don't over-crouch**. Your knees are bending too much, which can slow your recovery.",
    "preparation.shoulder": "**[Preparation]** Turn your shoulders earlier and more completely during the setup phase.",
    "preparation.stance": "**[Preparation]** Set up with a wider base from the start. Narrow stance limits power generation.",
    "load.hip": "**[Load]** Coil your hips more during the loading phase. This is where you store energy for the shot.",
    "load.knee": "**[Load]** Drop your center of gravity more in the loading phase. Bend those knees!",
    "follow_through.elbow": "**[Follow-through]** Extend your arms more through the finish. You're pulling back too early.",
    "follow_through.spine": "**[Follow-through]** Maintain better balance through your finish position.",
    "fallback.1": "**Keep your eye on the ball** through contact. Head still, watch the ball hit the strings.",
    "fallback.2": "**Follow through completely** toward your target. Don't cut the swing short.",
    "fallback.3": "**Relax your grip** slightly. A death-grip reduces racquet head speed.",
    "drill.knee": (
        "**Wall Sits with Shadow Swings**: Stand against a wall in a squat position (knees at 90°). "
        "Hold for 30 seconds while performing slow-motion backhand swings. "
        "This builds leg strength and muscle memory for proper knee bend. Do 3 sets."
    ),
    "drill.hip": (
        "**Medicine Ball Rotational Throws**: Stand sideways to a wall, holding a medicine ball (4-8 lbs). "
        "Rotate your hips and core explosively to throw the ball against the wall. "
        "Catch and repeat. Do 2 sets of 10 each side to build rotational power."
    ),
    "drill.stance": (
        "**Ladder Footwork Drill**: Use an agility ladder (or tape lines). "
        "Practice split-stepping into your backhand stance, focusing on consistent foot spacing. "
        "Hit shadow strokes at each stop. 5 minutes daily improves footwork consistency."
    ),
    "drill.general_1": (
        "**One-Arm Backhand Feeds**: Have a partner feed soft balls while you hit backhands with only your "
        "non-dominant hand on the racquet. This strengthens your lead arm and improves control. "
        "Do 20 balls, then switch back to two hands—you'll feel the difference immediately."
    ),
    "drill.general_2": (
        "**Contact Point Drill**: Set up a ball on a cone or have a partner hold one at your ideal contact point. "
        "Practice bringing your racquet to that exact spot with proper form, pausing at contact. "
        "This builds muscle memory for consistent contact. 50 reps before each practice session."
    ),
}

FOREHAND = {
    "left_elbow_angle.high": "**Let your non-hitting arm relax** at contact. A rigid off arm stiffens the shoulders and slows rotation.",
    "left_elbow_angle.low": "**Use your off arm as a counterbalance**: extend it across your body as you unload so the shoulders stay level.",
    "right_elbow_angle.high": "**Keep a slight bend in your hitting elbow** at contact. A locked arm pushes the ball instead of brushing it.",
    "right_elbow_angle.low": "**Extend the hitting arm more through contact**. Reaching out front gives you leverage and racquet-head speed.",
    "hip_rotation.low_abs": "**Drive the hips open first.** The forehand is hips, then torso, then arm—right now the arm is leading.",
    "hip_rotation.high_abs": "**Don't spin out early.** Keep the hips slightly closed until the racquet drops, then release.",
    "spine_lean.high": "**Stay tall through contact.** Leaning too far forward drops the contact point and sends balls into the net.",
    "spine_lean.low": "**Load slightly forward** into the front foot so your weight moves through the ball.",
    "stance_width_normalized.low": "**Widen your base** so you can sit into the outside leg and push off it into the shot.",
    "stance_width_normalized.high": "**Bring your feet in slightly.** An over-wide base makes it hard to rotate and recover.",
    "knee_angle_avg.high": "**Sit lower on the outside leg** in your setup. The forehand's power comes from the ground up.",
    "knee_angle_avg.low": "**Don't crouch too deep**; you lose the ability to rise into the ball and recover.",
    "preparation.shoulder": "**[Preparation]** Complete the unit turn early: shoulders past 90° before the ball bounces.",
    "preparation.stance": "**[Preparation]** Set the outside foot wider as you turn so you can load into it.",
    "load.hip": "**[Load]** Coil the hips against the shoulders in the loading phase. Store the energy before you release it.",
    "load.knee": "**[Load]** Bend the outside knee more as you load. You should feel weight on the outside leg.",
    "follow_through.elbow": "**[Follow-through]** Extend out toward the target before the racquet wraps. You're pulling across early.",
    "follow_through.spine": "**[Follow-through]** Finish balanced over the front foot instead of falling off the shot.",
    "drill.knee": (
        "**Outside-Leg Load Shadow Swings**: Set up sideways, sit into the outside leg until the knee is clearly bent, "
        "then rotate through and finish on the front foot. 3 sets of 15 slow reps, then 15 at match tempo."
    ),
    "drill.hip": (
        "**Medicine Ball Forehand Throws**: Stand sideways to a wall with a 4-8 lb ball at your hip. "
        "Drive the hips open first, then the torso, and throw against the wall. 2 sets of 10 each side."
    ),
    "drill.stance": (
        "**Split-Step to Open Stance Drill**: Split step on a partner's feed, land with the outside foot wide, "
        "shadow a forehand, recover. 5 minutes daily builds a repeatable base."
    ),
    "drill.general_1": (
        "**Racquet-Drop Pause Drill**: Take the racquet back, pause at the drop position with the hips still closed, "
        "then swing. 20 balls from a partner feed to separate the load from the release."
    ),
    "drill.general_2": (
        "**Out-Front Contact Drill**: Have a partner hold a ball at your ideal forehand contact point, in front of "
        "the lead hip. Bring the racquet to that exact spot with a slight elbow bend, 50 reps before practice."
    ),
}

SERVE = {
    "left_elbow_angle.high": "**Keep the tossing arm extended** up to the ball. Dropping it early collapses the shoulder tilt.",
    "left_elbow_angle.low": "**Tuck the tossing arm** into the body as you swing up so the torso can rotate freely.",
    "right_elbow_angle.high": "**Get more elbow bend at the trophy position.** A straight hitting arm can't whip up to the ball.",
    "right_elbow_angle.low": "**Reach full extension at contact.** Contact should be at the top of your reach, not below it.",
    "hip_rotation.low_abs": "**Turn the hips and shoulders away more** in the trophy position. The serve is a rotation, not a push.",
    "hip_rotation.high_abs": "**Don't over-rotate before the toss.** Too much turn makes the timing to the ball unreliable.",
    "spine_lean.high": "**Don't collapse forward** before contact. Stay tall and let the arch release upward into the ball.",
    "spine_lean.low": "**Arch the back slightly** in the trophy position so you can drive up and out.",
    "stance_width_normalized.low": "**Widen the starting stance** so you have a base to drive up from.",
    "stance_width_normalized.high": "**Bring the feet closer.** A very wide serve stance limits the leg drive.",
    "knee_angle_avg.high": "**Bend the knees deeper** in the trophy position. The leg drive starts the whole kinetic chain.",
    "knee_angle_avg.low": "**Don't sink too deep.** An excessive knee bend slows the drive up to the ball.",
    "preparation.shoulder": "**[Preparation]** Turn the shoulders away from the net more as you toss.",
    "preparation.stance": "**[Preparation]** Start with a wider, more stable base before the toss.",
    "load.hip": "**[Load]** Coil the hips under the shoulders at the trophy position. Load before you launch.",
    "load.knee": "**[Load]** Bend the knees more as the toss goes up. Drive from the legs, not the arm.",
    "follow_through.elbow": "**[Follow-through]** Extend fully up and out at contact before the arm pronates and drops.",
    "follow_through.spine": "**[Follow-through]** Land balanced inside the court instead of falling sideways.",
    "fallback.1": "**Watch the ball to the strings** at the top of the toss. Head up, eyes on contact.",
    "fallback.2": "**Finish across the body** after contact; don't stop the arm at the ball.",
    "fallback.3": "**Loosen the grip** on the racquet. A relaxed arm snaps up faster.",
    "drill.knee": (
        "**Trophy-Position Holds**: Toss, sink into the trophy position with knees bent and hold for two seconds, "
        "then serve. 3 sets of 10 to groove the leg load."
    ),
    "drill.hip": (
        "**Medicine Ball Overhead Throws**: Stand sideways to a wall, coil hips and shoulders, and throw a 4-6 lb ball "
        "up and forward against the wall. 2 sets of 10 to build the rotational drive."
    ),
    "drill.stance": (
        "**Platform Stance Reps**: Set the feet in your serving stance on tape marks, toss and serve without moving them. "
        "20 serves focusing on a consistent base."
    ),
    "drill.general_1": (
        "**Toss-and-Catch Drill**: Toss to your contact point and catch the ball at full extension without swinging. "
        "20 tosses; if you have to move your feet or bend the arm, the toss was off."
    ),
    "drill.general_2": (
        "**Continental Grip Shadow Serves**: Slow-motion serves stopping at the trophy position, racquet drop, and "
        "contact. 3 sets of 10 with a pause at each checkpoint."
    ),
}

VOLLEY = {
    "left_elbow_angle.high": "**Keep the off arm quiet and close** on the volley. It balances you; it shouldn't swing.",
    "left_elbow_angle.low": "**Use the off hand on the throat** of the racquet in the ready position for a faster set.",
    "right_elbow_angle.high": "**Keep the hitting elbow bent and in front.** A volley is a punch, not a swing.",
    "right_elbow_angle.low": "**Punch through the ball more.** Meet it out front with a short extension instead of just blocking.",
    "hip_rotation.low_abs": "**Turn the shoulders slightly** as you set. A little turn gives the punch direction.",
    "hip_rotation.high_abs": "**Don't rotate through the volley.** Too much turn becomes a swing and the ball flies long.",
    "spine_lean.high": "**Stay tall at the net.** Bending from the waist drops the racquet head below the ball.",
    "spine_lean.low": "**Lean into the volley** with the chest over the front foot so your weight moves forward.",
    "stance_width_normalized.low": "**Widen the ready position** so you can split step and push in either direction.",
    "stance_width_normalized.high": "**Narrow the ready stance slightly.** You need to move, not brace.",
    "knee_angle_avg.high": "**Bend the knees at the net.** Get down to low balls with the legs, not the wrist.",
    "knee_angle_avg.low": "**Don't crouch so deep** that you can't move to the next ball.",
    "preparation.shoulder": "**[Preparation]** Set the racquet with a small shoulder turn as soon as you read the ball.",
    "preparation.stance": "**[Preparation]** Split step into a wider base as your opponent hits.",
    "load.hip": "**[Load]** Step across with the front foot and turn the hips a touch as you set.",
    "load.knee": "**[Load]** Sink into the front leg as you step to the volley.",
    "follow_through.elbow": "**[Follow-through]** Keep the finish short and out front. The racquet stops where the ball was.",
    "follow_through.spine": "**[Follow-through]** Recover to balance immediately; the next ball is coming fast.",
    "fallback.1": "**Watch the ball onto the strings** and keep the head still through the punch.",
    "fallback.2": "**Firm wrist at contact**; let the step, not the wrist, supply the pace.",
    "fallback.3": "**Racquet head above the wrist** on every volley you can reach.",
    "drill.knee": (
        "**Low Volley Ladder**: Partner feeds balls progressively lower at the net. Get down with the knees, keep "
        "the racquet head up. 3 sets of 10 each side."
    ),
    "drill.hip": (
        "**Step-Across Volleys**: Feeds to alternate sides; step across with the front foot and turn the shoulders "
        "slightly before contact. 20 balls each side."
    ),
    "drill.stance": (
        "**Split-Step Reaction Volleys**: Partner hits at random; split step on their contact, then volley. "
        "5 minutes daily for a wider, quicker base."
    ),
    "drill.general_1": (
        "**Catch-the-Ball Drill**: Without a racquet, catch fed balls out front with the hitting hand at volley height. "
        "20 catches to train the contact point before adding the racquet."
    ),
    "drill.general_2": (
        "**Wall Punch Volleys**: Stand two metres from a wall and volley continuously with a short punch and no backswing. "
        "50 in a row without a swing."
    ),
}

OVERHEAD = {
    "left_elbow_angle.high": "**Point the off arm at the ball** and keep it up until the racquet comes through.",
    "left_elbow_angle.low": "**Pull the off arm in** as you swing so the shoulders rotate through.",
    "right_elbow_angle.high": "**Bend the elbow more in the set position.** The racquet should scratch your back before it goes up.",
    "right_elbow_angle.low": "**Extend fully at contact.** Hit the overhead at the top of your reach.",
    "hip_rotation.low_abs": "**Turn sideways more** as you set up. The overhead is a serve motion, not a facing-forward slap.",
    "hip_rotation.high_abs": "**Don't over-rotate.** Too much turn makes it hard to line up under the ball.",
    "spine_lean.high": "**Don't fall forward** into the overhead. Stay tall and let the swing come over the top.",
    "spine_lean.low": "**Arch slightly** as you set so you can drive up into the ball.",
    "stance_width_normalized.low": "**Widen the base** as you get under the ball so you're stable at contact.",
    "stance_width_normalized.high": "**Bring the feet in** so you can adjust under a drifting lob.",
    "knee_angle_avg.high": "**Bend the knees** as you set. You'll get more height and power from the legs.",
    "knee_angle_avg.low": "**Don't sink too deep**; a deep crouch delays getting up to the ball.",
    "preparation.shoulder": "**[Preparation]** Turn sideways immediately when you read the lob and get the racquet up.",
    "preparation.stance": "**[Preparation]** Shuffle back with a wide base rather than running backwards.",
    "load.hip": "**[Load]** Coil the hips under you as the racquet drops behind your back.",
    "load.knee": "**[Load]** Bend the knees before you launch up to the ball.",
    "follow_through.elbow": "**[Follow-through]** Extend fully up at contact before the racquet comes down across the body.",
    "follow_through.spine": "**[Follow-through]** Land balanced and move forward, not sideways.",
    "fallback.1": "**Keep your eyes on the ball** all the way up; don't look at the target early.",
    "fallback.2": "**Finish the swing** across the body instead of stopping at contact.",
    "fallback.3": "**Loose arm, quick wrist**: relax the grip until just before contact.",
    "drill.knee": (
        "**Set-and-Hold Overheads**: Partner lobs; turn, set with knees bent, hold one second, then hit. "
        "3 sets of 10 to groove the leg load."
    ),
    "drill.hip": (
        "**Sideways Shuffle Overheads**: Start facing the net, turn sideways and shuffle under the lob before hitting. "
        "20 balls to make the turn automatic."
    ),
    "drill.stance": (
        "**Backpedal-Free Footwork**: Cross-step and shuffle back to lobs with a wide base; no running backwards. "
        "5 minutes daily."
    ),
    "drill.general_1": (
        "**Catch-the-Lob Drill**: Without a racquet, get under lobs and catch them at full reach with the off hand pointing. "
        "20 catches to train positioning."
    ),
    "drill.general_2": (
        "**Serve-Motion Overheads**: Self-feed a toss and hit overheads with the full serve motion, pausing at the "
        "racquet-drop position. 3 sets of 10."
    ),
}

CUES = {
    "backhand": BACKHAND,
    "forehand": FOREHAND,
    "serve": SERVE,
    "volley": VOLLEY,
    "overhead": OVERHEAD,
}


def normalize_stroke(stroke: str) -> str:
    stroke = (stroke or "backhand").lower().strip()
    return stroke if stroke in CUES else "backhand"


def get_cue(stroke: str, key: str) -> str:
    """Wording for `key` in the given stroke, falling back to the backhand text."""
    stroke = normalize_stroke(stroke)
    text = CUES[stroke].get(key)
    return text if text is not None else BACKHAND[key]
