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

# Smarter Scheduling

- **4-pass priority scheduler** — pinned tasks placed at exact times first, then emergency, mandatory, and optional tasks fill remaining windows in priority order
- **Per-window time budgets** — morning, afternoon, and evening each have independent minute budgets; optional tasks are skipped rather than over-scheduled
- **Conflict detection** — flags over-capacity days, mandatory tasks that exceed their window budget, same-category stacking, and pinned-task time overlaps
- **Carry-over** — mandatory and emergency tasks that don't fit today are automatically promoted to tomorrow's plan
- **Recurring tasks** — daily, weekly, interval, and monthly recurrence patterns; tasks only appear on matching dates
- **Pinned start times** — tasks can be locked to a specific clock time, bypassing window-based placement while still raising overlap warnings
