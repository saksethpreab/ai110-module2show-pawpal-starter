# PawPal+ (Module 2 Project)

You are building **PawPal+**, a Streamlit app that helps a pet owner plan care tasks for their pet.

## Scenario

A busy pet owner needs help staying consistent with pet care. They want an assistant that can:

- Track pet care tasks (walks, feeding, meds, enrichment, grooming, etc.)
- Consider constraints (time available, priority, owner preferences)
- Produce a daily plan and explain why it chose that plan

Your job is to design the system first (UML), then implement the logic in Python, then connect it to the Streamlit UI.

## What you will build

Your final app should:

- Let a user enter basic owner + pet info
- Let a user add/edit tasks (duration + priority at minimum)
- Generate a daily schedule/plan based on constraints and priorities
- Display the plan clearly (and ideally explain the reasoning)
- Include tests for the most important scheduling behaviors

## Getting started

### Setup

```bash
python -m venv .venv # create an environment
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt # 
```

### Suggested workflow

1. Read the scenario carefully and identify requirements and edge cases.
2. Draft a UML diagram (classes, attributes, methods, relationships).
3. Convert UML into Python class stubs (no logic yet).
4. Implement scheduling logic in small increments.
5. Add tests to verify key behaviors.
6. Connect your logic to the Streamlit UI in `app.py`.
7. Refine UML so it matches what you actually built.

# Feature List

| Feature | What it does | Problem it solves |
|---|---|---|
| **4-pass priority scheduler** | Places pinned tasks first, then emergency, mandatory, and optional tasks in priority order | Ensures critical tasks (medication, feeding) are never displaced by lower-priority ones |
| **Per-window time budgets** | Morning, afternoon, and evening each have independent minute caps | Prevents over-scheduling a single part of the day while other windows sit empty |
| **Mandatory task enforcement** | Mandatory tasks are always scheduled even if they exceed the window budget; a warning is shown | Pet health tasks cannot be safely skipped — the owner is informed rather than the task silently dropped |
| **Pinned start times** | Tasks can be locked to an exact clock time, bypassing window-based placement | Lets owners schedule time-sensitive tasks (e.g. vet appointments) at a precise hour |
| **Recurring tasks** | Daily, weekly, interval, and monthly recurrence patterns; tasks only appear on matching dates | Eliminates manually re-adding routine tasks every day |
| **Carry-over** | Mandatory and emergency tasks that don't fit today are automatically promoted to tomorrow | Prevents critical tasks from being lost when a day is over-capacity |
| **Conflict detection** | Flags over-capacity days, budget overruns, same-category stacking, and pinned-task time overlaps | Surfaces scheduling problems before the owner discovers a missed task |
| **Feeding consolidation** | Consecutive same-window feeding tasks are merged into one time block | Reduces clutter in the schedule when multiple pets share a feeding window |
| **Task viewing with filters** | Scheduled tasks can be filtered by pet and status, and sorted by time or priority | Makes it easy to find what still needs to be done in a busy daily plan |
| **Completion tracking** | Each task has a to-do / done / skip status; a progress bar shows daily completion percentage | Gives the owner a clear view of how much of the day's care has been completed |
| **Index-based task removal** | Tasks are listed with a numeric index; entering the index removes the correct task immediately | Avoids typo errors from name-based deletion and reflects in the UI instantly |
| **Multi-pet support** | Multiple pets can be added and managed independently under one owner | Handles households with more than one animal without duplicate data entry |

# Smarter Scheduling

- **4-pass priority scheduler** — pinned tasks placed at exact times first, then emergency, mandatory, and optional tasks fill remaining windows in priority order
- **Per-window time budgets** — morning, afternoon, and evening each have independent minute budgets; optional tasks are skipped rather than over-scheduled
- **Conflict detection** — flags over-capacity days, mandatory tasks that exceed their window budget, same-category stacking, and pinned-task time overlaps
- **Carry-over** — mandatory and emergency tasks that don't fit today are automatically promoted to tomorrow's plan
- **Recurring tasks** — daily, weekly, interval, and monthly recurrence patterns; tasks only appear on matching dates
- **Pinned start times** — tasks can be locked to a specific clock time, bypassing window-based placement while still raising overlap warnings
