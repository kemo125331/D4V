# First Real Prototype Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Turn the current OCR diagnostics pipeline into a first testable prototype that produces session-level combat stats, shows them in a lightweight desktop panel, and supports a first live round test.

**Architecture:** Keep one shared processing pipeline for replay and live capture so we do not build two separate systems. The first milestone is replay aggregation and replay-preview UI, then we reuse that exact path for a live preview window and a controlled training-dummy test.

**Tech Stack:** Python, `Pillow`, `pytest`, current D4V replay OCR pipeline, lightweight desktop UI layer already planned under `src/d4v/overlay`

**Note:** Commit steps are intentionally omitted in this plan because the current workspace is not a Git repository.

---

### Task 1: Lock The Stable-Hit Contract

**Files:**
- Modify: `src/d4v/tools/analyze_replay_ocr.py`
- Modify: `src/d4v/domain/models.py`
- Test: `tests/tools/test_analyze_replay_ocr.py`

**Step 1: Define the stable-hit payload**

- Add a typed domain shape for deduped OCR hits.
- Required fields:
  - `frame_index`
  - `timestamp_ms`
  - `parsed_value`
  - `confidence`
  - `sample_text`
  - `center_x`
  - `center_y`

**Step 2: Add failing tests for the new shape**

Run: `uv run pytest tests/tools/test_analyze_replay_ocr.py -v`
Expected: FAIL once tests assert timestamped stable hits that do not exist yet

**Step 3: Make `analyze_replay_ocr.py` emit stable-hit domain data**

- Keep raw OCR results and stable hits separate.
- Infer `timestamp_ms` from replay frame index and recorded FPS metadata when available.

**Step 4: Re-run the focused tests**

Run: `uv run pytest tests/tools/test_analyze_replay_ocr.py -v`
Expected: PASS

### Task 2: Build Session Aggregation From Stable Hits

**Files:**
- Modify: `src/d4v/domain/session_stats.py`
- Create: `src/d4v/domain/session_aggregation.py`
- Create: `tests/domain/test_session_aggregation.py`
- Modify: `tests/domain/test_session_stats.py`

**Step 1: Write failing aggregation tests**

Cover:
- total damage
- hit count
- average hit
- biggest hit
- empty-session guards

Run: `uv run pytest tests/domain/test_session_stats.py tests/domain/test_session_aggregation.py -v`
Expected: FAIL because the aggregation API does not exist yet

**Step 2: Extend `SessionStats` with explicit session helpers**

- Add helpers for:
  - `reset()`
  - `hit_count`
  - `average_hit`
  - `biggest_hit`
- Keep rolling DPS behavior intact

**Step 3: Implement `session_aggregation.py`**

- Input: stable hits
- Output:
  - `total_damage`
  - `hit_count`
  - `average_hit`
  - `biggest_hit`
  - `dps_timeline`

**Step 4: Re-run the domain tests**

Run: `uv run pytest tests/domain/test_session_stats.py tests/domain/test_session_aggregation.py -v`
Expected: PASS

### Task 3: Add A Replay Summary Artifact

**Files:**
- Create: `src/d4v/domain/replay_summary.py`
- Modify: `src/d4v/tools/analyze_replay_ocr.py`
- Create: `tests/domain/test_replay_summary.py`

**Step 1: Write failing summary tests**

Cover:
- session name
- duration
- totals
- top hits
- DPS timeline buckets

Run: `uv run pytest tests/domain/test_replay_summary.py -v`
Expected: FAIL because replay summary formatting does not exist yet

**Step 2: Implement the summary model**

- Create a serializable replay summary object.
- Include:
  - `session_name`
  - `duration_ms`
  - `total_damage`
  - `hit_count`
  - `average_hit`
  - `biggest_hit`
  - `dps_timeline`
  - `top_hits`
  - OCR coverage counts

**Step 3: Write the artifact during replay OCR analysis**

- Save it under `analysis/combat-ocr/`.
- Keep it separate from the raw OCR debug summary.

**Step 4: Re-run the summary tests**

Run: `uv run pytest tests/domain/test_replay_summary.py tests/tools/test_analyze_replay_ocr.py -v`
Expected: PASS

### Task 4: Print The First Real Combat Output

**Files:**
- Modify: `src/d4v/app.py`
- Modify: `src/d4v/tools/analyze_replay_ocr.py`

**Step 1: Add CLI output assertions**

- Extend tests or add a focused tool test that checks printed replay metrics.

**Step 2: Update the command output**

- `uv run d4v analyze-replay-ocr fixtures/replays/second-round`
- Print:
  - total damage
  - hit count
  - average hit
  - biggest hit
  - simple DPS timeline summary

**Step 3: Run the real replay command**

Run: `uv run d4v analyze-replay-ocr fixtures/replays/second-round`
Expected: prints a readable combat summary plus OCR diagnostics

### Task 5: Extract A Shared Frame-Processing API

**Files:**
- Modify: `src/d4v/tools/analyze_replay_roi.py`
- Modify: `src/d4v/tools/analyze_replay_tokens.py`
- Modify: `src/d4v/tools/analyze_replay_ocr.py`
- Create: `src/d4v/tools/live_preview.py`
- Test: `tests/tools/test_live_preview.py`

**Step 1: Write a failing integration test for replay-preview processing**

- The test should feed a tiny synthetic replay or fixture frame set through one shared processor function.

Run: `uv run pytest tests/tools/test_live_preview.py -v`
Expected: FAIL because there is no shared processing entry point yet

**Step 2: Extract reusable processing functions**

- Shared functions should accept one frame or one frame path and return:
  - OCR-ready line candidates
  - parsed hits
  - stable-hit candidates for aggregation

**Step 3: Make replay analysis call the shared processing path**

- No duplicate replay-only OCR logic should remain in the command layer.

**Step 4: Re-run the focused test**

Run: `uv run pytest tests/tools/test_live_preview.py tests/tools/test_analyze_replay_ocr.py -v`
Expected: PASS

### Task 6: Build The Preview View Model

**Files:**
- Create: `src/d4v/overlay/__init__.py`
- Create: `src/d4v/overlay/view_model.py`
- Create: `tests/overlay/test_view_model.py`

**Step 1: Write failing view-model tests**

Cover formatted labels for:
- total damage
- rolling DPS
- biggest hit
- last hit
- status text

Run: `uv run pytest tests/overlay/test_view_model.py -v`
Expected: FAIL because the view model does not exist yet

**Step 2: Implement the minimal view model**

- Keep it pure and UI-agnostic.
- It should only format state from `SessionStats` and preview controller output.

**Step 3: Re-run the view-model tests**

Run: `uv run pytest tests/overlay/test_view_model.py -v`
Expected: PASS

### Task 7: Build Replay Preview First

**Files:**
- Create: `src/d4v/overlay/window.py`
- Modify: `src/d4v/tools/live_preview.py`
- Modify: `src/d4v/app.py`
- Modify: `tests/tools/test_live_preview.py`

**Step 1: Add a failing replay-preview controller test**

Cover:
- start replay
- tick through frames
- update totals
- stop/reset cleanly

Run: `uv run pytest tests/tools/test_live_preview.py -v`
Expected: FAIL because replay-preview control flow does not exist yet

**Step 2: Implement the preview controller**

- Replay frames should be fed on a timer.
- Session stats should update incrementally.
- The controller should expose:
  - current totals
  - last hit
  - last processed frame
  - error/status text

**Step 3: Build the lightweight desktop panel**

- Normal desktop window only.
- No true in-game overlay behavior yet.
- Show:
  - total visible damage
  - rolling DPS
  - biggest hit
  - last hit
  - mode/status
  - start/stop/reset

**Step 4: Re-run replay-preview tests**

Run: `uv run pytest tests/tools/test_live_preview.py tests/overlay/test_view_model.py -v`
Expected: PASS

### Task 8: Add Live Preview Mode

**Files:**
- Modify: `src/d4v/tools/live_preview.py`
- Modify: `src/d4v/tools/capture_round.py`
- Modify: `src/d4v/capture/recorder.py`
- Modify: `src/d4v/app.py`

**Step 1: Write a failing start/stop live-preview test**

- Use a fake frame source or callback-driven recorder hook.

Run: `uv run pytest tests/tools/test_live_preview.py -v`
Expected: FAIL because live-preview hooks do not exist yet

**Step 2: Add a live frame callback path**

- Reuse the same processing pipeline as replay-preview.
- Keep FPS conservative for the first live test.

**Step 3: Expose live mode in the preview controller**

- Start live capture
- update the panel continuously
- allow reset/stop without crashing

**Step 4: Re-run the focused tests**

Run: `uv run pytest tests/tools/test_live_preview.py tests/tools/test_capture_round.py -v`
Expected: PASS

### Task 9: Prepare The First Live Test Checklist

**Files:**
- Create: `docs/testing/first-live-test.md`
- Modify: `docs/README.md`

**Step 1: Document the operator checklist**

- Game language English
- HDR off
- stable resolution
- training dummy first
- record expected FPS
- what success looks like
- what failure looks like

**Step 2: Add the replay-vs-live comparison checklist**

- compare visible total trend
- compare biggest-hit plausibility
- watch for frozen UI
- watch for repeated overcounting

**Step 3: Review the doc**

Run: manual review in the repo
Expected: short, operator-friendly instructions

### Task 10: Run The First Real Prototype Pass

**Files:**
- No code changes required unless issues are found

**Step 1: Run replay summary on `second-round`**

Run: `uv run d4v analyze-replay-ocr fixtures/replays/second-round`
Expected: readable combat summary artifact and CLI output

**Step 2: Launch replay-preview UI**

Run: `uv run d4v live-preview --replay fixtures/replays/second-round`
Expected: panel updates over time and resets cleanly

**Step 3: Launch live-preview UI**

Run: `uv run d4v live-preview --live`
Expected: panel stays responsive and updates while capturing

**Step 4: Record one new training-dummy round**

- Use the live-preview window
- keep the round short and controlled

**Step 5: Evaluate trustworthiness**

- If totals are obviously unstable, stop and inspect OCR/debug output before building any true overlay behavior.
- If totals are directionally believable, the next milestone is an actual overlay shell and experimental kill tracking.
