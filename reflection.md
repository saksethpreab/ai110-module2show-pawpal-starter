# PawPal+ Project Reflection

## 1. System Design

**a. Initial design**

- Briefly describe your initial UML design.

The system has seven main classes: Owner, Pet, FoodPreference, Task, Scheduler, DailyPlan, and ScheduledTask, plus four enumerations (TaskCategory, Priority, TimeOfDay, TaskStatus).

1. An Owner owns one or more Pets. Each Pet holds a list of reusable Task templates and a FoodPreference object.
2. The Scheduler takes an Owner and a specific Pet, runs a two-pass algorithm (mandatory tasks first, then optional by priority), and produces a DailyPlan.
3. A DailyPlan contains ScheduledTask instances (each wrapping a Task with a time slot, status, and reason) plus a list of skipped tasks eligible for carry-over to the next day.

- What classes did you include, and what responsibilities did you assign to each?

1. Owner: stores name, wake time, and time budget broken into morning/afternoon/evening windows (dict[TimeOfDay, int]); owns one or more Pet instances.

2. Pet: stores name, species, breed, and age; holds a FoodPreference and a list of Task templates; exposes get_pending_tasks() to surface carried-over tasks.

3. FoodPreference: stores food_name (brand/product), food_type (dry, wet, raw, etc.), portion_size_grams, feedings_per_day, and dietary_restrictions (list of allergies or special diet flags). FEEDING tasks reference this so the schedule can display exactly what and how much to feed.

4. Task: reusable template storing name, category, duration, priority, preferred time window, is_mandatory flag, and optional notes. Tasks are not consumed — they are referenced each day.

5. Scheduler: accepts an Owner and Pet; runs generate_plan() which schedules mandatory tasks first (with a warning if they exceed the budget), then greedily fills remaining window budgets with optional tasks sorted by priority.

6. DailyPlan: holds the ordered list of ScheduledTask objects, skipped tasks, per-window usage summary, and any warnings (e.g. mandatory task exceeded budget).

7. ScheduledTask: links a Task to a specific date and time slot; carries a TaskStatus (SCHEDULED, COMPLETED, SKIPPED, CARRIED_OVER) and a plain-language reason string explaining why it was chosen and when.

**b. Design changes**

- Did your design change during implementation?
- If yes, describe at least one change and why you made it.

---

## 2. Scheduling Logic and Tradeoffs

**a. Constraints and priorities**

- What constraints does your scheduler consider (for example: time, priority, preferences)?
- How did you decide which constraints mattered most?

1.  

**b. Tradeoffs**

- Describe one tradeoff your scheduler makes.
- Why is that tradeoff reasonable for this scenario?

---

## 3. AI Collaboration

**a. How you used AI**

- How did you use AI tools during this project (for example: design brainstorming, debugging, refactoring)?
- What kinds of prompts or questions were most helpful?

**b. Judgment and verification**

- Describe one moment where you did not accept an AI suggestion as-is.
- How did you evaluate or verify what the AI suggested?

---

## 4. Testing and Verification

**a. What you tested**

- What behaviors did you test?
- Why were these tests important?

**b. Confidence**

- How confident are you that your scheduler works correctly?
- What edge cases would you test next if you had more time?

---

## 5. Reflection

**a. What went well**

- What part of this project are you most satisfied with?

**b. What you would improve**

- If you had another iteration, what would you improve or redesign?

**c. Key takeaway**

- What is one important thing you learned about designing systems or working with AI on this project?
