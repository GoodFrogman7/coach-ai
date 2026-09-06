# Coach AI Build Plan

Drafted 2026-09-06. Phases are numbered fresh here because the existing docs use three
conflicting numbering schemes (PROJECT_SUMMARY phases 1-10, IMPLEMENTATION_COMPLETE
phases 1-4, feature docs 2.1-5.2). Each phase ends with a gate. We do not start the
next phase until the gate is green.

## Where we are today

- Pipeline: `vision/compare.py` (755 lines) orchestrates 16 vision modules. Pose via
  MediaPipe, biomechanics via `features.py`, scoring via `similarity.py`, six
  intelligence layers, markdown report via `report.py`.
- Reference: exactly one clip, `data/reference/djokovic_backhand.mp4`. Every stroke is
  scored against a backhand.
- Stroke abstraction: profiles for 5 strokes exist. Phase weights are wired into scoring
  (PR #3). Expected ranges (`get_stroke_aware_threshold`) are still dead code because cue
  generation compares user metrics to reference metrics directly.
- UI: two Streamlit apps. `streamlit_app.py` (1702 lines, 7 pages, all features) and
  `streamlit_app_v2.py` (472 lines, user profiles and session naming, fewer pages).
  `upload_page.py` already has a stroke selector.
- Users: one file, `users/default_user.json`, mapping session ids to names. Sessions live
  as about 30 timestamped directories under `outputs/`, discovered by directory scan.
- RAG: TF-IDF plus sentence-transformer ensemble, intent classifier, session memory,
  strict grounding policy. Knowledge base is 11 markdown files with no stroke tags.
  LLM backends: Ollama, OpenAI, Anthropic.
- Ball tracking: YOLO weights present (`models/best.pt`), `ultralytics` not installed in
  the venv, so the integration test is skipped and the Ball and Rally page is unverified.
- Tests: 51 passing, 1 skipped, via pytest in `venv`. No CI. System Python 3.8 has no
  pytest.
- Docs: 45 markdown files in the repo root.

## Phase 0: Hardening (about 1 week)

Goal: make every later phase cheap to verify and safe to merge.

Tasks
1. GitHub Actions workflow `.github/workflows/test.yml`: Python 3.10, pip cache,
   install both requirements files, run `pytest -q`. Make it a required check on main.
2. Install `ultralytics` in the venv and in CI so the ball tracking test runs instead of
   skipping. If CI becomes too slow, mark it `slow` and run it nightly.
3. Generate `requirements.lock` with `pip freeze`. Keep ranges in `requirements.txt`.
4. Consolidate the UI. Port user profiles and session naming from `streamlit_app_v2.py`
   into `streamlit_app.py`, then delete v2. Split `streamlit_app.py` into
   `ui/pages/*.py` (one file per `render_*` function) with `streamlit_app.py` as the
   router only.
5. Move the 45 root docs into `docs/` with a single `docs/INDEX.md`. Keep `README.md`
   and this file at root. Fold the `_SUMMARY`, `_COMPLETE`, and `_FIXED` duplicates into
   their primary doc and delete them.
6. Delete merged remote branches `feature/stroke-aware-scoring` and
   `test/pytest-harness`.
7. Add `ruff` to `requirements-dev.txt` and CI with a minimal rule set (F, E9). Fix
   what it reports.

Gate
- CI green on main, 52 tests passing, 0 skipped.
- One Streamlit entry point showing all 7 pages plus the user selector.
- Repo root holds README, BUILD_PLAN, LICENSE, code, and config only.

## Phase 1: Real multi-stroke analysis (2 to 3 weeks)

Goal: a forehand, serve, volley, or overhead video is scored against its own stroke,
with its own cues and drills. Today only the phase weights change.

Tasks
1. Reference library. New layout `data/reference/<stroke>/<clip>.mp4` plus
   `data/reference/manifest.yaml` listing each clip with stroke, player, handedness,
   camera angle, and fps. A loader in `vision/reference_library.py` returns the best
   clip for a stroke and handedness. The backhand clip moves to
   `data/reference/backhand/`.
2. Two comparison strategies in `vision/similarity.py`:
   - `ReferenceComparison` (current behaviour) when a reference clip exists.
   - `RangeComparison` that scores user metrics against `get_stroke_aware_threshold`
     expected ranges when no clip exists. Deviation is distance outside the range,
     zero inside. This finally uses the dead code.
   `run_pipeline` picks the strategy from the library lookup and records which one was
   used in the report metadata.
3. Stroke-specific cue templates. Move the hardcoded backhand cue text out of
   `rank_cues_by_deviation` and `generate_coaching_cues` into
   `vision/cue_templates.py` keyed by stroke, metric, and direction. Backhand text
   stays byte-identical so existing report snapshots do not change.
4. Stroke-tagged drills and knowledge base. Add a `strokes` list to the front matter of
   each `kb/*.md` and a `strokes` field to every drill in `vision/drills.py`. Drill
   selection filters by the session stroke. RAG retrieval boosts docs matching it.
5. Reference pose cache. Extracting pose from the 47 MB Djokovic clip on every run is
   the slowest step. Cache `ref_features.csv` under `data/reference/<stroke>/cache/`
   keyed by clip hash and feature-code version.
6. Handedness. Add `--handed left|right` and mirror x-coordinates for left-handers
   before feature computation. Expose it in the upload page.
7. Upload page wiring. The existing stroke selector must reach `run_pipeline`, and the
   handedness control sits next to it.

Tests
- Synthetic feature CSV fixtures per stroke in `tests/fixtures/` so pipeline tests do
  not need video.
- `RangeComparison` unit tests: inside range scores 100, outside range scales down.
- Snapshot test: the backhand report for `data/user/input.mp4` is unchanged after this
  phase apart from the new metadata field.
- One end-to-end test per stroke on a 3-second clip committed under `tests/clips/`.

Gate
- `python vision/compare.py --stroke forehand --handed left` produces a report with
  forehand cues and forehand drills, and states which comparison strategy was used.
- Backhand snapshot unchanged.

## Phase 2: Automatic stroke detection and rally sessions (3 to 4 weeks)

Goal: upload a two-minute rally clip and get one analysis per stroke plus a session
summary, without telling the system which stroke is which.

Tasks
1. Stroke event segmentation in `vision/stroke_events.py`. Reuse the wrist-speed
   impact detector to find candidate contacts, then window each contact with the
   existing phase segmenter. Output a list of start, contact, and end frames.
2. Stroke classifier in `vision/stroke_classifier.py`. Version 1 is heuristic:
   dominant wrist above shoulder at contact with both feet planted means serve or
   overhead; swing direction relative to torso facing separates forehand from
   backhand; a short arc near the net means volley. Version 2 trains a small
   scikit-learn gradient-boosted model on labelled windows once we have 200 or more
   labelled strokes. Labels come from a labelling page in Streamlit that shows the
   window and asks for the stroke.
3. Multi-stroke pipeline. `run_pipeline` gains an `--auto` mode: segment, classify,
   run the single-stroke analysis per event with the right reference, and write
   `outputs/<session>/strokes/<n>_<stroke>/` per event.
4. Session report. New section in `report.py`: stroke counts, per-stroke technique
   score, best and worst stroke, and cross-stroke patterns such as late preparation
   showing on both wings.
5. Fatigue and rally intelligence already exist for movement. Feed them the per-stroke
   timeline so fatigue is also measured as technique drift across strokes in one
   session.
6. Dashboard: the session page shows a stroke timeline. Clicking a stroke opens its
   report and overlay clip.

Tests
- Labelled clip set of at least 50 strokes across 5 types. Classifier accuracy gate
  at 85 percent for version 1 and 92 percent for version 2.
- Segmentation test: known number of contacts in each test clip, tolerance of one.

Gate
- A rally clip runs end to end with `--auto`, and the dashboard shows the stroke
  timeline with per-stroke reports.

## Phase 3: Ball and court fusion (3 to 4 weeks)

Goal: connect the YOLO ball tracker to the pose pipeline so contact, shot outcome, and
placement become part of technique feedback.

Tasks
1. Court homography in `vision/court.py`. Detect the baseline and sideline corners
   (the broadcast overlay already draws a court, so start from its assumptions) and
   map pixels to court metres. Manual four-click fallback in the upload page.
2. Contact verification. At each detected contact frame, check ball-to-wrist distance.
   Use it to refine the impact frame and reject false contacts from the wrist-speed
   detector. Report contact height and contact point relative to the body in metres.
3. Shot outcome. Project the landing point through the homography and classify it as
   in, out, or net, with depth and lateral placement bins.
4. Link technique to outcome. Store outcome next to the technique metrics per stroke.
   The adaptive coaching layer gains an outcome term: a deviation that correlates with
   errors is escalated.
5. Serve speed from ball displacement between consecutive frames after contact, using
   the homography scale.
6. The Ball and Rally page reads the fused per-stroke data instead of running its own
   separate analysis.

Tests
- Homography unit tests with synthetic corner sets.
- Contact verification on the Phase 2 labelled clips: false contact rate below 5
  percent.
- Outcome classification checked against 30 hand-labelled shots.

Gate
- A rally report includes contact height, landing placement, and an outcome line per
  stroke, and the drill list references outcome patterns.

## Phase 4: Player model and persistent store (2 to 3 weeks)

Goal: replace directory scanning and JSON files with a database so baselines,
narratives, readiness, and drill outcomes work across hundreds of sessions and more
than one player.

Tasks
1. SQLite via SQLModel at `data/coach.db`. Tables: player, session, stroke_event,
   metric, cue, drill_assignment, drill_outcome, qa_log. Session files under `outputs/`
   stay as artifacts. The database holds the structured data.
2. Migration. Extend `migrate_sessions_to_users.py` to import every existing report
   YAML header and metrics CSV into the store. Must be idempotent.
3. Repository layer `vision/store.py`. Baseline, narrative, readiness, and progress
   tracking read from it instead of parsing old reports. Keep the report-parsing path
   behind a flag for one release, then remove it.
4. Closed drill loop. A recommended drill is recorded. The next upload asks which
   drills were done. The following analysis computes the delta on the metric each
   drill targets and updates drill confidence. Drill confidence scoring already exists
   and is waiting for this data.
5. Multi-day planning. Training load gains a 7-day view from the store with a simple
   periodization rule: no more than two high-intensity days in a row, one recovery day
   after a match simulation.
6. Player profile page: baselines per metric over time, drill history with effect,
   readiness trend.

Tests
- Migration test on a copy of `outputs/` asserts row counts match session count.
- Store tests for each query the intelligence layers use.
- Drill loop test: recommend, mark done, next session shows the delta.

Gate
- Fresh clone plus migration reproduces today's dashboard numbers from the database.
- Two players in the store, each seeing only their own sessions and baselines.

## Phase 5: Coach RAG upgrade (about 2 weeks)

Goal: the Ask Coach page answers with the player's own numbers, per stroke, with an
evaluation harness that catches regressions.

Tasks
1. Structured context. Build a compact JSON context from the store (current stroke
   metrics, deltas, active drills, readiness) instead of pasting report text.
2. Tool use. Give the model two tools: get session metrics by session and stroke, and
   search the knowledge base by query and stroke. Implement on the Anthropic backend
   first with current Claude models. Keep Ollama on the existing prompt path.
3. Knowledge base growth. Fundamentals exist for three strokes. Add volley and
   overhead plus per-stroke drill explanations. Rebuild the index in CI when `kb/`
   changes.
4. Evaluation harness. Grow `test_rag_retrieval_quality.py` into a graded set of 40
   questions with expected source docs and must-mention facts. Retrieval hit rate and
   grounding checks run in CI. Answer quality runs nightly against Ollama.
5. Streaming answers in the UI and a sources panel linking to the KB file and session.

Gate
- Retrieval hit rate at 90 percent on the graded set.
- Strict grounding still blocks low-confidence retrievals, verified by test.

## Phase 6: Product surface (4 or more weeks, scope decided at the Phase 4 gate)

Goal: someone other than us can use it from a phone.

Tasks
1. Put the pipeline behind a FastAPI service with a job queue. Analysis takes minutes,
   so uploads return a job id and the client polls.
2. Auth. Replace the user selector with real accounts. Streamlit stays as the coach
   console. A minimal web client handles phone upload and report viewing.
3. Storage. Videos and overlays move to object storage. The store gets a Postgres
   option.
4. Deployment. Docker image for the worker with MediaPipe and YOLO, GPU optional, and
   a one-command compose file.

Gate
- Upload from a phone, get a report link, open it on the phone.

## Sequencing rationale

- Phase 0 first because every later phase adds tests and touches the UI. Two Streamlit
  apps and no CI would double the work.
- Phase 1 before Phase 2 because automatic detection is useless if the detected stroke
  is still scored against a backhand.
- Phase 3 depends on Phase 2's per-stroke events to attach outcomes to.
- Phase 4 comes after Phases 2 and 3 so the schema is designed once with stroke events
  and outcomes known, rather than migrated twice.
- Phase 5 depends on Phase 4's structured store for tool use.
- Phase 6 is last because it is the only phase that does not improve the analysis.

## Working agreements

- One PR per numbered task. Branch names `phase<N>/<short-name>`.
- Every PR adds or updates tests and keeps the backhand snapshot green.
- No push while a build or run session is active.
- Docs for a feature live in `docs/` and are updated in the same PR.
