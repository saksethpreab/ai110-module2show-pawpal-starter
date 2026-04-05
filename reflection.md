# PawPal+ Project Reflection

## 1. System Design

**a. Initial design**

- Briefly describe your initial UML design.

The system has seven main classes: Owner, Pet, FoodPreference, Task, Scheduler, DailyPlan, and ScheduledTask, plus four enumerations (TaskCategory, Priority, TimeOfDay, TaskStatus).

1. An Owner owns one or more Pets. Each Pet holds a list of reusable Task templates and a FoodPreference object.
2. The Scheduler takes an Owner and a specific Pet, runs a two-pass algorithm (mandatory tasks first, then optional by priority), and produces a DailyPlan.
3. A DailyPlan contains ScheduledTask instances (each wrapping a Task with a time slot, status, and reason) plus a list of skipped tasks eligible for carry-over to the next day.

- What classes did you include, and what responsibilities did you assign to each?

1. Owner: stores name, wake time and time budget broken into morning/afternoon/evening windows (dict[TimeOfDay, int]); owns one or more Pet instances.

2. Pet: stores name, species, breed, and age; holds a FoodPreference and a list of Task templates; exposes get_pending_tasks() to surface carried-over tasks.

3. FoodPreference: stores food_name (brand/product), food_type (dry, wet, raw, etc.), portion_size_grams, feedings_per_day, and dietary_restrictions (list of allergies or special diet flags). FEEDING tasks reference this so the schedule can display exactly what and how much to feed.

4. Task: reusable template storing name, category, duration, priority, preferred time window, is_mandatory flag, and optional notes. Tasks are not consumed — they are referenced each day.

5. Scheduler: accepts an Owner and Pet; runs generate_plan() which schedules mandatory tasks first (with a warning if they exceed the budget), then greedily fills remaining window budgets with optional tasks sorted by priority.

6. DailyPlan: holds the ordered list of ScheduledTask objects, skipped tasks, per-window usage summary, and any warnings (e.g. mandatory task exceeded budget).

7. ScheduledTask: links a Task to a specific date and time slot; carries a TaskStatus (SCHEDULED, COMPLETED, SKIPPED, CARRIED_OVER) and a plain-language reason string explaining why it was chosen and when.

**b. Design changes**

- Did your design change during implementation?
- If yes, describe at least one change and why you made it.

Yes. The most significant change was converting all internal time values from `"H:MM"` strings to plain integers (minutes since midnight). The original design stored times like `"7:30"` as strings, which required dedicated helpers to parse, format, add, and compare them throughout the scheduler. During implementation it became clear this added unnecessary complexity — every arithmetic operation needed a parse/format round-trip. Switching to integers meant all time comparisons and arithmetic became plain `<`/`>`/`+`, and parsing only happens at input boundaries (e.g. a user typing a wake time), with formatting only at display. This made the scheduling logic easier to read and eliminated an entire class of string-manipulation bugs.

---

## 2. Scheduling Logic and Tradeoffs

**a. Constraints and priorities**

- What constraints does your scheduler consider (for example: time, priority, preferences)?
- How did you decide which constraints mattered most?

The scheduler considers three main constraints: 

(1) time budget per window — morning, afternoon, and evening each have independent minute caps set by the owner; 

(2) priority — four levels (EMERGENCY, HIGH, MEDIUM, LOW) that determine scheduling order within each pass; and 

(3) mandatory flag — a hard inclusion constraint separate from priority, so a critical task like medication is never displaced by a higher-priority optional task.

Mandatory status takes precedence over budget because skipping a health-critical task due to a full calendar is worse than exceeding the budget and warning the owner. Priority governs ordering within that framework; budget is a soft constraint for mandatory tasks and a hard constraint for optional ones.

**b. Tradeoffs**

- Describe one tradeoff your scheduler makes.
- Why is that tradeoff reasonable for this scenario?

Mandatory tasks are always scheduled even when they exceed the window's time budget. The system records a warning rather than skipping the task.

Pet care tasks like feeding and medication cannot safely be deferred because a window is over capacity. The plan stays medically correct, and the owner sees a warning that lets them decide how to adjust their day — rather than discovering a missed dose later.

---

## 3. AI Collaboration

**a. How you used AI**

- How did you use AI tools during this project (for example: design brainstorming, debugging, refactoring)?
- What kinds of prompts or questions were most helpful?

AI was used for initial brainstorming (identifying classes, responsibilities, and relationships) and generating code skeletons. After each generation, the output was reviewed for clarity and correctness before being accepted — treating AI as a fast first draft rather than a final answer.

**b. Judgment and verification**

- Describe one moment where you did not accept an AI suggestion as-is.
- How did you evaluate or verify what the AI suggested?

When generating class implementations, the AI-produced code sometimes needed more detailed logic than what was initially suggested — particularly around method bodies and edge case handling. In those cases, a more specific prompt describing the exact expected behavior was provided, and the result was verified by reading through the implementation and running tests to confirm it behaved correctly.

---

## 4. Testing and Verification

**a. What you tested**

- What behaviors did you test?
- Why were these tests important?

The 246 tests cover eight main areas: 

(1) **core scheduling logic** — mandatory tasks always get placed, optional tasks are skipped when the budget is exhausted, emergency tasks are placed first and produce a warning, and tasks in different windows advance their cursors independently; 

(2) **budget tracking** — remaining budget decreases correctly after each scheduled task, over-budget mandatory tasks add a warning instead of being dropped, and the ANY-time window picker selects the roomiest window; 

(3) **recurrence** — daily, weekly, interval, and monthly patterns are expanded only on matching dates, tasks with an end date stop recurring after it passes; 

(4) **feeding consolidation** — consecutive same-window feedings are merged into one block, non-contiguous or cross-window feedings are not merged; 

(5) **data model invariants** — validation rejects zero/negative durations and blank names before a task can be added to a pet, and carry-over only promotes mandatory/emergency skipped tasks, not optional ones;

(6) **recurrence continuity** — a recurring daily task appears on consecutive days, marking a day's instance complete does not suppress the next day's expansion, and tasks stop appearing after their end date;

(7) **time-overlap conflict detection** — two pinned tasks at the same or overlapping times produce a `TIME_OVERLAP` conflict, adjacent tasks do not, and three mutually overlapping tasks produce exactly three pairwise conflicts;

(8) **index-based task removal** — `get_tasks()` returns tasks in insertion order, removing by index correctly targets the first, middle, and last positions, remaining tasks preserve their relative order after removal, and re-indexing after a removal is consistent.

These tests matter because the scheduler's correctness is invisible to the user — a missed medication or a silently skipped task would look the same as a successful run without a test suite catching it.

**b. Confidence**

- How confident are you that your scheduler works correctly?
- What edge cases would you test next if you had more time?

**Confidence: ★★★★☆ (4 / 5)**

The test suite covers priority ordering, budget enforcement, recurrence continuity, feeding consolidation, time-overlap conflict detection, and index-based task removal across 246 tests in 8 areas. Two originally identified gaps — recurring task continuity across days and pinned-task time-overlap detection — have since been closed. The remaining deductions: two edge cases are still untested (task duration exactly equal to remaining window budget; carry-over interacting with recurrence), the greedy scheduler's no-backtrack design means some valid schedules are never found, and there are no end-to-end UI tests to verify the Streamlit layer.

---

## 5. Reflection

**a. What went well**

- What part of this project are you most satisfied with?

The task viewing UI. Beyond just displaying a schedule, the app lets the user filter by status and pet, sort by time or priority, and track completion progress with a native progress bar. Tasks are listed with a numeric index for reliable removal, and the per-window summary uses `st.metric` to instantly show how much capacity remains or has been exceeded. These details — consistent use of native Streamlit components like `st.warning`, `st.error`, `st.metric`, and `st.progress` — turned what could have been a static list into something polished and interactive. The owner can mark tasks done, see how much of the day is complete, and quickly find what's left.

**b. What you would improve**

- If you had another iteration, what would you improve or redesign?

1. **Persistence** — all pets, tasks, and owner settings are lost on page reload. Adding save/load (JSON file or small database) would make the app actually usable day-to-day rather than requiring re-entry every session.

2. **Greedy scheduler can't backtrack** — the 4-pass algorithm commits to each placement and never revisits it. A task placed early in a window can block a later mandatory task from fitting. A constraint-satisfaction or backtracking approach would produce tighter, more optimal schedules.

3. **Manual task entry only** — there are no templates or presets for common routines. Adding defaults for common pet types (e.g. twice-daily feeding, daily walk) would reduce setup friction significantly.

**c. Key takeaway**

- What is one important thing you learned about designing systems or working with AI on this project?

AI is better at breadth than depth on first pass. It can generate a working skeleton quickly, but subtle correctness issues — like the scheduler silently ignoring tasks placed by earlier passes — require careful reasoning about the algorithm yourself. The most effective pattern was using AI to draft and then auditing the output critically, rather than trusting either alone.

