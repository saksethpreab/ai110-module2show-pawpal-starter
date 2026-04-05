# This file contains the "logic layer" where all the backend classes live

from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum
from datetime import date
from typing import Optional


# ---------------------------------------------------------------------------
# Enumerations
# ---------------------------------------------------------------------------

class TaskCategory(Enum):
    WALK = "walk"
    FEEDING = "feeding"
    MEDICATION = "medication"
    ENRICHMENT = "enrichment"
    GROOMING = "grooming"
    VET = "vet"
    OTHER = "other"


class Priority(Enum):
    EMERGENCY = 4
    HIGH = 3
    MEDIUM = 2
    LOW = 1


class TimeOfDay(Enum):
    MORNING = "morning"
    AFTERNOON = "afternoon"
    EVENING = "evening"
    ANY = "any"


class TaskStatus(Enum):
    SCHEDULED = "scheduled"
    COMPLETED = "completed"
    SKIPPED = "skipped"
    CARRIED_OVER = "carried_over"


class RecurrenceType(Enum):
    DAILY = "daily"
    WEEKLY = "weekly"
    INTERVAL = "interval"
    MONTHLY = "monthly"


class SkipReason(Enum):
    BUDGET_EXCEEDED = "budget exceeded"
    NO_COMPATIBLE_WINDOW = "no compatible window"
    CARRIED_OVER_NO_FIT = "carried over — still no fit"


class ConflictType(Enum):
    OVER_CAPACITY = "over_capacity"
    MANDATORY_OVER_BUDGET = "mandatory_over_budget"
    CATEGORY_STACK = "category_stack"
    TIME_OVERLAP = "time_overlap"


@dataclass
class Conflict:
    conflict_type: ConflictType
    message: str
    task_id: Optional[str] = None


# ---------------------------------------------------------------------------
# Time helpers
#
# All times are stored internally as int (minutes since midnight, e.g. 450 for
# 7:30, 845 for 14:05).  The parse/format helpers below are used only at
# system boundaries (user input, display output, serialisation).
# ---------------------------------------------------------------------------

def parse_time_str(time_str: str) -> int:
    """Convert an 'H:MM' or 'HH:MM' string to minutes since midnight."""
    h, m = time_str.split(":")
    return int(h) * 60 + int(m)


def format_time(minutes: int) -> str:
    """Convert minutes since midnight to an 'H:MM' display string."""
    h, m = divmod(minutes, 60)
    return f"{h}:{m:02d}"


def time_to_window(minutes: int) -> TimeOfDay:
    """Map minutes-since-midnight to its day window.
    <720 (12:00) → MORNING, 720–1019 → AFTERNOON, 1020+ (17:00) → EVENING.
    """
    if minutes < 720:
        return TimeOfDay.MORNING
    elif minutes < 1020:
        return TimeOfDay.AFTERNOON
    return TimeOfDay.EVENING


def recurrence_applies_to_date(recurrence: "Recurrence", check_date: date) -> bool:
    """Check if a recurrence pattern applies to a given date.
    
    Args:
        recurrence: The Recurrence object defining the pattern.
        check_date: The date to check.
    
    Returns:
        True if the recurrence applies on check_date, False otherwise.
    """
    if recurrence is None:
        return False
    
    # Check if date is within start/end window
    if check_date < recurrence.start_date:
        return False
    if recurrence.end_date and check_date > recurrence.end_date:
        return False
    
    # Check based on recurrence type
    if recurrence.type == RecurrenceType.DAILY:
        return True
    
    elif recurrence.type == RecurrenceType.WEEKLY:
        # Monday=0, Sunday=6
        day_of_week = check_date.weekday()
        return day_of_week in recurrence.days_of_week
    
    elif recurrence.type == RecurrenceType.INTERVAL:
        # Check if (date - start_date) is a multiple of interval
        days_passed = (check_date - recurrence.start_date).days
        return days_passed % recurrence.interval == 0
    
    elif recurrence.type == RecurrenceType.MONTHLY:
        # Recurs on the same day of month as start_date.
        # For dates that don't exist (e.g., Feb 31), check if this date is the last day of check_date's month
        # and start_date.day is >= 28 (potential edge case day).
        target_day = recurrence.start_date.day
        if check_date.day == target_day:
            return True
        
        # Handle edge case: if target_day > 28 and check_date is the last day of its month,
        # it might still count as a match (e.g., start_date=Jan 31, check_date=Feb 28)
        from calendar import monthrange
        _, days_in_month = monthrange(check_date.year, check_date.month)
        if target_day > days_in_month and check_date.day == days_in_month:
            return True
        
        return False
    
    return False


# ---------------------------------------------------------------------------
# Recurrence
# ---------------------------------------------------------------------------

@dataclass
class Recurrence:
    """Defines a recurrence pattern for tasks.
    
    Attributes:
        type: RecurrenceType (DAILY, WEEKLY, INTERVAL, or MONTHLY).
        start_date: When the recurrence begins.
        end_date: Optional; when the recurrence ends. If None, recurs indefinitely.
        interval: For INTERVAL type only; every N days.
        days_of_week: For WEEKLY type only; list of day numbers (0=Mon, 6=Sun).
    """
    type: RecurrenceType
    start_date: date
    end_date: Optional[date] = None
    interval: int = 1
    days_of_week: list[int] = field(default_factory=list)
    
    def validate(self):
        """Raise ValueError if the recurrence data is logically invalid."""
        if self.end_date and self.start_date > self.end_date:
            raise ValueError("start_date must be <= end_date")
        if self.type == RecurrenceType.INTERVAL and self.interval <= 0:
            raise ValueError("interval must be positive for INTERVAL type")
        if self.type == RecurrenceType.WEEKLY:
            if not self.days_of_week or not all(0 <= d <= 6 for d in self.days_of_week):
                raise ValueError("days_of_week must contain values 0-6 for WEEKLY type")


# ---------------------------------------------------------------------------
# FoodPreference
# ---------------------------------------------------------------------------

class FoodPreference:
    def __init__(
        self,
        food_name: str,
        food_type: str,
        portion_size_grams: int,
        feedings_per_day: int,
        dietary_restrictions: Optional[list[str]] = None,
    ):
        self.food_name = food_name
        self.food_type = food_type
        self.portion_size_grams = portion_size_grams
        self.feedings_per_day = feedings_per_day
        # Default to empty list so callers can always iterate without a None check
        self.dietary_restrictions = dietary_restrictions or []

    def describe(self) -> str:
        """Return a human-readable summary of this food preference."""
        restrictions = ", ".join(self.dietary_restrictions) if self.dietary_restrictions else "none"
        return (
            f"{self.food_name} ({self.food_type}), "
            f"{self.portion_size_grams}g x {self.feedings_per_day}/day, "
            f"restrictions: {restrictions}"
        )

    def update(self, **kwargs):
        """Update any field by name. Unknown keys are silently ignored."""
        for key, value in kwargs.items():
            if hasattr(self, key):
                setattr(self, key, value)


# ---------------------------------------------------------------------------
# Task
# ---------------------------------------------------------------------------

@dataclass
class Task:
    id: str
    name: str
    category: TaskCategory
    duration_minutes: int
    priority: Priority
    preferred_time: TimeOfDay
    is_mandatory: bool = False
    notes: Optional[str] = None
    food_preference: Optional[FoodPreference] = None  # populated for FEEDING tasks only
    recurrence: Optional[Recurrence] = None  # populated for recurring tasks
    specific_time: Optional[int] = None  # minutes since midnight; overrides window-based placement

    def validate(self):
        """Raise ValueError if the task data is logically invalid."""
        if self.duration_minutes <= 0:
            raise ValueError(f"Task '{self.name}': duration_minutes must be positive")
        if not self.name.strip():
            raise ValueError("Task name cannot be empty")
        if self.specific_time is not None:
            if not (0 <= self.specific_time <= 1439):
                raise ValueError(f"Task '{self.name}': specific_time must be 0–1439 (minutes since midnight)")

    def fits_in_budget(self, available_minutes: int) -> bool:
        """True if this task's duration fits inside the given minute budget."""
        return self.duration_minutes <= available_minutes

    def is_compatible_with_window(self, window: TimeOfDay) -> bool:
        """True if the task can be placed in `window`.
        A task with preferred_time=ANY is compatible with every window.
        """
        return self.preferred_time in (TimeOfDay.ANY, window)

    def to_dict(self) -> dict:
        """Serialize the task to a plain dict (enum fields become their string values)."""
        return {
            "id": self.id,
            "name": self.name,
            "category": self.category.value,
            "duration_minutes": self.duration_minutes,
            "priority": self.priority.name,
            "preferred_time": self.preferred_time.value,
            "specific_time": format_time(self.specific_time) if self.specific_time is not None else None,
            "is_mandatory": self.is_mandatory,
            "notes": self.notes,
        }


# ---------------------------------------------------------------------------
# Pet
# ---------------------------------------------------------------------------

@dataclass
class Pet:
    name: str
    species: str
    breed: Optional[str] = None
    age_years: float = 0.0
    food_preference: Optional[FoodPreference] = None
    id: Optional[str] = None
    tasks: list[Task] = field(default_factory=list)

    def __post_init__(self):
        # Normalize name to lowercase so searches are always case-insensitive
        self.name = self.name.lower()

    def add_task(self, task: Task):
        self.tasks.append(task)

    def remove_task(self, task_id: str):
        # Rebuild the list excluding the target; no error if id not found
        self.tasks = [t for t in self.tasks if t.id != task_id]

    def edit_task(
        self,
        task_id: str,
        name: Optional[str] = None,
        duration_minutes: Optional[int] = None,
        priority: Optional[Priority] = None,
        preferred_time: Optional[TimeOfDay] = None,
        is_mandatory: Optional[bool] = None,
        notes: Optional[str] = None,
    ):
        """Update one or more fields on a task. Only non-None arguments are applied."""
        for task in self.tasks:
            if task.id == task_id:
                if name is not None:
                    task.name = name
                if duration_minutes is not None:
                    task.duration_minutes = duration_minutes
                if priority is not None:
                    task.priority = priority
                if preferred_time is not None:
                    task.preferred_time = preferred_time
                if is_mandatory is not None:
                    task.is_mandatory = is_mandatory
                if notes is not None:
                    task.notes = notes
                return
        raise KeyError(f"Task '{task_id}' not found on pet '{self.name}'")

    def get_tasks(self) -> list[Task]:
        # Return a copy so callers cannot mutate the internal list directly
        return list(self.tasks)

    def get_mandatory_tasks(self) -> list[Task]:
        return [t for t in self.tasks if t.is_mandatory]

    def get_tasks_by_category(self, category: TaskCategory) -> list[Task]:
        return [t for t in self.tasks if t.category == category]

    def get_pending_tasks(self, scheduled_tasks: Optional[list[ScheduledTask]] = None) -> list[Task]:
        """Return tasks that have not yet been given a scheduled slot today.

        If `scheduled_tasks` is None (no plan exists yet), all tasks are pending.
        Otherwise, a task is pending when its id does not appear in the scheduled list.
        """
        if scheduled_tasks is None:
            return list(self.tasks)
        scheduled_ids = {st.task.id for st in scheduled_tasks}
        return [t for t in self.tasks if t.id not in scheduled_ids]


# ---------------------------------------------------------------------------
# Owner
# ---------------------------------------------------------------------------

class Owner:
    def __init__(self, name: str, wake_time: int):
        # wake_time as minutes since midnight, e.g. 450 for 7:30
        self.name = name
        self.wake_time = wake_time
        self.time_budget: dict[TimeOfDay, int] = {}
        self._counters: dict[str, int] = {}   # tracks how many pets per species prefix
        self._pets: dict[str, Pet] = {}        # keyed by auto-generated pet id

    def add_pet(self, pet: Pet):
        """Add a pet, auto-generating a meaningful id if the pet has none yet.
        The id uses the first letter of the species + a zero-padded counter,
        e.g. the first dog gets "d001", the second cat gets "c002".
        """
        if pet.id is None:
            prefix = pet.species[0].lower()
            self._counters[prefix] = self._counters.get(prefix, 0) + 1
            pet.id = f"{prefix}{self._counters[prefix]:03d}"
        self._pets[pet.id] = pet

    def get_pets(self) -> list[Pet]:
        return list(self._pets.values())

    def search_pets(self, name: str) -> list[Pet]:
        """Return all pets whose name matches (case-insensitive)."""
        name_lower = name.lower()
        return [p for p in self._pets.values() if p.name == name_lower]

    def remove_pet(self, name: str) -> bool | list[Pet]:
        """Remove a pet by name.
        - Returns False if no pet with that name exists.
        - Returns True if exactly one match was found and removed.
        - Returns the list of matching pets if there are multiple (caller must choose).
        """
        matches = self.search_pets(name)
        if len(matches) == 0:
            return False
        if len(matches) == 1:
            self._remove_pet_by_id(matches[0].id)
            return True
        return matches  # ambiguous — let the caller decide which to remove

    def set_budget(self, window: TimeOfDay, minutes: int):
        self.time_budget[window] = minutes

    def get_budget(self, window: TimeOfDay) -> int:
        return self.time_budget.get(window, 0)

    def get_total_budget(self) -> int:
        return sum(self.time_budget.values())

    def _get_pet_by_id(self, pet_id: str) -> Optional[Pet]:
        return self._pets.get(pet_id)

    def _remove_pet_by_id(self, pet_id: str):
        self._pets.pop(pet_id, None)


# ---------------------------------------------------------------------------
# ScheduledTask
# ---------------------------------------------------------------------------

class ScheduledTask:
    def __init__(
        self,
        task: Task,
        date: date,
        start_time: int,
        end_time: int,
        status: TaskStatus,
        reason: str,
        time_window: TimeOfDay,
    ):
        # start_time and end_time are minutes since midnight
        self.task = task
        self.date = date
        self.start_time = start_time
        self.end_time = end_time
        self.status = status
        self.reason = reason
        self.time_window = time_window

    @property
    def duration_minutes(self) -> int:
        """Compute duration from the stored start/end ints."""
        return self.end_time - self.start_time

    def mark_completed(self):
        self.status = TaskStatus.COMPLETED

    def mark_skipped(self):
        self.status = TaskStatus.SKIPPED

    def __str__(self) -> str:
        return (
            f"[{format_time(self.start_time)}-{format_time(self.end_time)}] {self.task.name} "
            f"({self.task.duration_minutes} min) - {self.status.value}"
        )


# ---------------------------------------------------------------------------
# DailyPlan
# ---------------------------------------------------------------------------

class DailyPlan:
    def __init__(self, plan_date: date, owner: Owner, pet: Pet):
        self.date = plan_date
        self.owner = owner
        self.pet = pet
        self.scheduled_tasks: list[ScheduledTask] = []
        self.skipped_tasks: list[Task] = []
        self.warnings: list[str] = []
        self.skip_reasons: dict[str, SkipReason] = {}
        self.conflicts: list[Conflict] = []

    def add_scheduled_task(self, st: ScheduledTask):
        self.scheduled_tasks.append(st)

    def add_skipped_task(self, task: Task):
        self.skipped_tasks.append(task)

    def add_warning(self, msg: str):
        self.warnings.append(msg)

    def add_conflict(self, conflict: Conflict):
        self.conflicts.append(conflict)

    def add_skip_reason(self, task_id: str, reason: SkipReason):
        self.skip_reasons[task_id] = reason

    def get_window_summary(self) -> dict:
        """Return per-window usage stats: tasks scheduled, minutes used, budget available."""
        summary = {}
        for window in [TimeOfDay.MORNING, TimeOfDay.AFTERNOON, TimeOfDay.EVENING]:
            tasks_in_window = [st for st in self.scheduled_tasks if st.time_window == window]
            used = sum(st.task.duration_minutes for st in tasks_in_window)
            budget = self.owner.get_budget(window)
            summary[window.value] = {
                "tasks": len(tasks_in_window),
                "used_minutes": used,
                "budget_minutes": budget,
            }
        return summary

    def get_tasks_sorted_by_time(self, window: Optional[TimeOfDay] = None) -> list[ScheduledTask]:
        """Return scheduled tasks sorted chronologically by start time.
        
        Args:
            window: If provided, only return tasks from that time window (MORNING, AFTERNOON, EVENING).
                   If None, return all scheduled tasks sorted by time.
        
        Returns:
            List of ScheduledTask objects sorted by start_time.
        """
        if window:
            tasks = [st for st in self.scheduled_tasks if st.time_window == window]
        else:
            tasks = list(self.scheduled_tasks)
        
        return sorted(tasks, key=lambda st: st.start_time)

    def get_tasks_by_status(self, status: TaskStatus) -> list[ScheduledTask]:
        """Return all scheduled tasks with a specific status (SCHEDULED, COMPLETED, SKIPPED, CARRIED_OVER).
        
        Args:
            status: The TaskStatus to filter by.
        
        Returns:
            List of ScheduledTask objects matching the status.
        """
        return [st for st in self.scheduled_tasks if st.status == status]

    def get_window_summary_extended(self, window: Optional[TimeOfDay] = None) -> dict:
        """Return detailed window summary including sorted task information.
        
        Args:
            window: If provided, return details for only that window.
                   If None, return details for all three windows.
        
        Returns:
            Dictionary with per-window stats including sorted task lists.
            Format: {
                "morning": {
                    "budget_minutes": 60,
                    "used_minutes": 45,
                    "remaining_minutes": 15,
                    "task_count": 2,
                    "tasks": [{"name": "...", "start_time": "7:00", "end_time": "7:30", "status": "scheduled"}, ...]
                },
                ...
            }
        """
        windows = [window] if window else [TimeOfDay.MORNING, TimeOfDay.AFTERNOON, TimeOfDay.EVENING]
        summary = {}
        
        for w in windows:
            sorted_tasks = self.get_tasks_sorted_by_time(w)
            used = sum(st.task.duration_minutes for st in sorted_tasks)
            budget = self.owner.get_budget(w)
            remaining = max(0, budget - used)
            
            task_details = [
                {
                    "name": st.task.name,
                    "start_time": format_time(st.start_time),
                    "end_time": format_time(st.end_time),
                    "status": st.status.value,
                    "category": st.task.category.value,
                    "priority": st.task.priority.name,
                }
                for st in sorted_tasks
            ]
            
            summary[w.value] = {
                "budget_minutes": budget,
                "used_minutes": used,
                "remaining_minutes": remaining,
                "task_count": len(sorted_tasks),
                "tasks": task_details,
            }
        
        return summary

    def get_reasoning(self) -> str:
        """Build a human-readable explanation of every scheduling decision."""
        lines = [
            f"Plan for {self.pet.name} - {self.date} (owner: {self.owner.name})",
            "",
        ]
        for st in self.scheduled_tasks:
            lines.append(f"  {st}")
            lines.append(f"    -> {st.reason}")
        if self.skipped_tasks:
            lines.append("")
            lines.append("Skipped (eligible for carry-over tomorrow):")
            for t in self.skipped_tasks:
                reason = self.skip_reasons.get(t.id)
                reason_str = f" — {reason.value}" if reason else ""
                lines.append(f"  - {t.name} [{t.priority.name}]{reason_str}")
        if self.conflicts:
            lines.append("")
            lines.append("Conflicts:")
            for c in self.conflicts:
                lines.append(f"  [{c.conflict_type.value}] {c.message}")
        if self.warnings:
            lines.append("")
            lines.append("Warnings:")
            for w in self.warnings:
                lines.append(f"  ! {w}")
        return "\n".join(lines)

    def get_skipped_for_carryover(self) -> list[Task]:
        return list(self.skipped_tasks)

    def __str__(self) -> str:
        return self.get_reasoning()


# ---------------------------------------------------------------------------
# Scheduler
# ---------------------------------------------------------------------------

class Scheduler:
    def __init__(self, owner: Owner, pet: Pet):
        self.owner = owner
        self.pet = pet

    def generate_plan(self, plan_date: date, previous_plan: Optional[DailyPlan] = None) -> DailyPlan:
        """Build a full DailyPlan using a three-pass algorithm:
          Pass 1: EMERGENCY tasks — placed immediately, bypassing budget limits
          Pass 2: Mandatory tasks — always scheduled, with a warning if over budget
          Pass 3: Optional tasks  — scheduled greedily by priority within budget
        """
        plan = DailyPlan(plan_date, self.owner, self.pet)
        self._plan_date = plan_date
        self._warnings: list[str] = []       # collected during passes, flushed into plan at the end
        self._conflicts: list[Conflict] = []
        self._skip_reasons: dict[str, SkipReason] = {}

        wake = self.owner.wake_time
        # Each window has an independent time cursor that advances as tasks are placed.
        # If the owner wakes after noon, the MORNING cursor is pushed to 719 (11:59) so
        # it holds no usable time; AFTERNOON and EVENING start no earlier than wake_time.
        self._cursors = {
            TimeOfDay.MORNING: wake if wake < 720 else 719,
            TimeOfDay.AFTERNOON: max(wake, 720),
            TimeOfDay.EVENING: max(wake, 1020),
        }

        # Merge pet's standing tasks with any tasks carried over from yesterday.
        # Carried-over tasks are only added if their id is not already in pet.tasks,
        # which prevents the same task from being double-counted.
        carried = self._carry_over(previous_plan) if previous_plan else []
        self._carried_ids = {t.id for t in carried}
        existing_ids = {t.id for t in self.pet.tasks}
        all_tasks = list(self.pet.tasks) + [t for t in carried if t.id not in existing_ids]
        
        # Expand recurring tasks that apply to this date
        all_tasks = self._expand_recurring_tasks(all_tasks, plan_date)

        # Over-capacity check: warn if all tasks can't possibly fit in the day's budget
        total_duration = sum(t.duration_minutes for t in all_tasks)
        total_budget = self.owner.get_total_budget()
        if total_duration > total_budget:
            self._conflicts.append(Conflict(
                ConflictType.OVER_CAPACITY,
                f"Total task time ({total_duration} min) exceeds daily budget ({total_budget} min) — some tasks will be skipped",
            ))

        # Separate pinned tasks (specific_time set) from window-based tasks
        pinned    = [t for t in all_tasks if t.specific_time]
        all_tasks = [t for t in all_tasks if not t.specific_time]

        # --- Pass 0: Pinned tasks — placed at their exact time, bypass budget ---
        for task in pinned:
            window = time_to_window(task.specific_time)
            st = self._assign_slot(task, task.specific_time)
            # Advance cursor only forward so later tasks don't overlap
            self._cursors[window] = max(st.end_time, self._cursors[window])
            plan.add_scheduled_task(st)

        # Split into the three scheduling pools
        emergency = [t for t in all_tasks if t.priority == Priority.EMERGENCY]
        mandatory = [t for t in all_tasks if t.is_mandatory and t.priority != Priority.EMERGENCY]
        optional  = [t for t in all_tasks if not t.is_mandatory and t.priority != Priority.EMERGENCY]

        # --- Pass 1: Emergency ---
        for st in self._schedule_emergency(emergency):
            plan.add_scheduled_task(st)

        # --- Pass 2: Mandatory ---
        for st in self._schedule_mandatory(mandatory, plan):
            plan.add_scheduled_task(st)

        # Recompute remaining budget after the first two passes before running optional
        remaining = {
            w: self._remaining_budget(w, plan)
            for w in [TimeOfDay.MORNING, TimeOfDay.AFTERNOON, TimeOfDay.EVENING]
        }

        # --- Pass 3: Optional ---
        for st in self._schedule_optional(optional, remaining):
            plan.add_scheduled_task(st)

        # Any task that still has no slot is skipped (eligible for tomorrow's carry-over)
        scheduled_ids = {st.task.id for st in plan.scheduled_tasks}
        for task in all_tasks:
            if task.id not in scheduled_ids:
                plan.add_skipped_task(task)
                # Attribute a skip reason if not already set by the optional pass
                if task.id not in self._skip_reasons:
                    if task.id in self._carried_ids:
                        self._skip_reasons[task.id] = SkipReason.CARRIED_OVER_NO_FIT

        # Move accumulated warnings, conflicts, and skip reasons into the plan object
        for warning in self._warnings:
            plan.add_warning(warning)
        for conflict in self._conflicts:
            plan.add_conflict(conflict)
        for task_id, reason in self._skip_reasons.items():
            plan.add_skip_reason(task_id, reason)

        # Consolidate consecutive feeding tasks in the same window
        self._consolidate_feeding_tasks(plan)
        self._detect_category_stacks(plan)
        self._detect_time_overlaps(plan)

        return plan

    def _schedule_emergency(self, tasks: list[Task]) -> list[ScheduledTask]:
        """Place EMERGENCY tasks first, in their preferred window (MORNING if ANY).
        Budget limits are intentionally ignored — emergencies always get a slot.
        A warning is always added so the owner sees each emergency in the plan summary.
        """
        result = []
        for task in self._sort_by_priority(tasks):
            window = task.preferred_time if task.preferred_time != TimeOfDay.ANY else TimeOfDay.MORNING
            st = self._assign_slot(task, self._cursors[window])
            self._cursors[window] = st.end_time  # advance cursor past this task
            self._warnings.append(f"EMERGENCY: '{task.name}' scheduled in {window.value}")
            result.append(st)
        return result

    def _schedule_mandatory(self, tasks: list[Task], plan: DailyPlan) -> list[ScheduledTask]:
        """Place mandatory tasks, always scheduling them even if the budget is exceeded.
        A warning is added for any task that pushes a window over its budget.
        Window selection for ANY-time tasks picks whichever window has the most spare capacity.
        """
        result = []
        for task in self._sort_by_priority(tasks):
            window = self._pick_window_from_budget(task, plan, result)
            budget = self.owner.get_budget(window)
            # Account for tasks from ALL prior passes (pinned, emergency) plus this pass
            used = (
                sum(st.task.duration_minutes for st in plan.scheduled_tasks if st.time_window == window)
                + sum(st.task.duration_minutes for st in result if st.time_window == window)
            )
            if task.duration_minutes > budget - used:
                msg = (
                    f"Mandatory task '{task.name}' exceeds {window.value} budget by "
                    f"{task.duration_minutes - (budget - used)} min"
                )
                self._warnings.append(msg)
                self._conflicts.append(Conflict(
                    ConflictType.MANDATORY_OVER_BUDGET, msg, task_id=task.id
                ))
            st = self._assign_slot(task, self._cursors[window])
            self._cursors[window] = st.end_time
            result.append(st)
        return result

    def _schedule_optional(self, tasks: list[Task], remaining: dict) -> list[ScheduledTask]:
        """Greedily fill remaining window capacity with optional tasks, highest priority first.
        A task is skipped (not scheduled) if its preferred window is full.
        For ANY-time tasks, the window with the most remaining capacity is chosen.
        """
        result = []
        for task in self._sort_by_priority(tasks):
            if task.preferred_time != TimeOfDay.ANY:
                window = task.preferred_time
                # Skip this task if it doesn't fit in the budget that's left
                if not task.fits_in_budget(remaining.get(window, 0)):
                    self._skip_reasons[task.id] = SkipReason.BUDGET_EXCEEDED
                    continue
            else:
                # Find all windows where the task fits, then pick the roomiest one
                windows = [TimeOfDay.MORNING, TimeOfDay.AFTERNOON, TimeOfDay.EVENING]
                viable = [w for w in windows if task.fits_in_budget(remaining.get(w, 0))]
                if not viable:
                    self._skip_reasons[task.id] = SkipReason.NO_COMPATIBLE_WINDOW
                    continue
                window = max(viable, key=lambda w: remaining.get(w, 0))

            st = self._assign_slot(task, self._cursors[window])
            self._cursors[window] = st.end_time
            remaining[window] = remaining.get(window, 0) - task.duration_minutes
            result.append(st)
        return result

    def _sort_by_priority(self, tasks: list[Task]) -> list[Task]:
        """Sort tasks descending by Priority value (EMERGENCY=4 first, LOW=1 last)."""
        return sorted(tasks, key=lambda t: t.priority.value, reverse=True)

    def _assign_slot(self, task: Task, current_time: int) -> ScheduledTask:
        """Create a ScheduledTask starting at `current_time` and lasting task.duration_minutes.
        The reason string explains when the task was placed and includes feeding details
        when the task is a FEEDING task with a linked FoodPreference.
        """
        end_time = current_time + task.duration_minutes
        window = time_to_window(current_time)
        reason = f"Scheduled at {format_time(current_time)} ({window.value})"
        if task.food_preference:
            fp = task.food_preference
            reason += f" | {fp.food_name} - {fp.portion_size_grams}g"
        return ScheduledTask(
            task=task,
            date=self._plan_date,
            start_time=current_time,
            end_time=end_time,
            status=TaskStatus.SCHEDULED,
            reason=reason,
            time_window=window,
        )

    def _remaining_budget(self, window: TimeOfDay, plan: DailyPlan) -> int:
        """Minutes still available in `window` after accounting for already-scheduled tasks."""
        budget = self.owner.get_budget(window)
        used = sum(
            st.task.duration_minutes
            for st in plan.scheduled_tasks
            if st.time_window == window
        )
        return max(0, budget - used)  # never return a negative number

    def _carry_over(self, previous_plan: DailyPlan) -> list[Task]:
        """Pull only MANDATORY and EMERGENCY skipped tasks from yesterday's plan.
        Optional tasks are not carried over automatically; the owner must re-add them if desired.
        """
        return [
            t for t in previous_plan.skipped_tasks
            if t.is_mandatory or t.priority == Priority.EMERGENCY
        ]

    def _expand_recurring_tasks(self, tasks: list[Task], plan_date: date) -> list[Task]:
        """Expand tasks with recurrence patterns into individual task instances for the given date.
        
        Non-recurring tasks pass through unchanged.
        Recurring tasks are replaced with cloned instances (without recurrence) only when they apply to this date.
        This ensures recurring tasks don't appear in the schedule on dates where they don't recur.
        """
        expanded = []
        for task in tasks:
            if task.recurrence:
                # Only add cloned instance if the recurrence applies to this date
                if recurrence_applies_to_date(task.recurrence, plan_date):
                    cloned_task = Task(
                        id=task.id + "_recurring",
                        name=task.name,
                        category=task.category,
                        duration_minutes=task.duration_minutes,
                        priority=task.priority,
                        preferred_time=task.preferred_time,
                        is_mandatory=task.is_mandatory,
                        notes=task.notes,
                        food_preference=task.food_preference,
                        recurrence=None,  # Clear recurrence so it doesn't expand again
                        specific_time=task.specific_time,
                    )
                    expanded.append(cloned_task)
                # If recurrence doesn't apply to this date, task is not included at all
            else:
                # Non-recurring tasks pass through unchanged
                expanded.append(task)
        
        return expanded

    def _consolidate_feeding_tasks(self, plan: DailyPlan):
        """Consolidate time-contiguous feeding tasks in the same time window into one slot.
        This reduces clutter and represents batched feeding operations (e.g., feeding all pets at once).

        Tasks are sorted by start time first so feedings from different scheduling
        passes (pinned, emergency, mandatory, optional) are properly adjacent.
        Only feedings whose times are truly contiguous (end == next start) are merged.
        """
        # Sort by start time so feedings from different passes are properly adjacent
        plan.scheduled_tasks.sort(key=lambda st: st.start_time)

        consolidated = []
        i = 0

        while i < len(plan.scheduled_tasks):
            st = plan.scheduled_tasks[i]

            # Non-feeding tasks pass through unchanged
            if st.task.category != TaskCategory.FEEDING:
                consolidated.append(st)
                i += 1
                continue

            # Collect time-contiguous feeding tasks in the same window
            feeding_group = [st]
            j = i + 1
            while j < len(plan.scheduled_tasks):
                st_next = plan.scheduled_tasks[j]
                if (st_next.task.category == TaskCategory.FEEDING
                        and st_next.time_window == st.time_window
                        and feeding_group[-1].end_time == st_next.start_time):
                    feeding_group.append(st_next)
                    j += 1
                else:
                    break

            if len(feeding_group) > 1:
                # Create a consolidated feeding task
                end_time = feeding_group[-1].end_time
                task_names = " + ".join(t.task.name for t in feeding_group)
                total_minutes = sum(t.task.duration_minutes for t in feeding_group)

                # Use highest priority among the group
                max_priority = max(feeding_group, key=lambda x: x.task.priority.value).task.priority

                # Preserve all original task IDs in a compound ID
                compound_id = "+".join(t.task.id for t in feeding_group)

                consolidated_task = Task(
                    id=compound_id,
                    name=task_names,
                    category=TaskCategory.FEEDING,
                    duration_minutes=total_minutes,
                    priority=max_priority,
                    preferred_time=st.task.preferred_time,
                )

                consolidated_st = ScheduledTask(
                    task=consolidated_task,
                    date=st.date,
                    start_time=st.start_time,
                    end_time=end_time,
                    status=st.status,
                    reason=f"Consolidated feeding: {task_names}",
                    time_window=st.time_window,
                )

                consolidated.append(consolidated_st)
                i = j
            else:
                # Only one feeding task in this sequence
                consolidated.append(st)
                i += 1

        plan.scheduled_tasks = consolidated

    def _pick_window_from_budget(self, task: Task, plan: DailyPlan, scheduled: list[ScheduledTask]) -> TimeOfDay:
        """Choose the best window for a task.
        If the task has a specific preferred_time, that window is used directly.
        If preferred_time is ANY, pick the window with the most remaining capacity
        accounting for all prior passes and the current pass.
        """
        if task.preferred_time != TimeOfDay.ANY:
            return task.preferred_time
        windows = [TimeOfDay.MORNING, TimeOfDay.AFTERNOON, TimeOfDay.EVENING]
        def remaining(w: TimeOfDay) -> int:
            used = (
                sum(st.task.duration_minutes for st in plan.scheduled_tasks if st.time_window == w)
                + sum(st.task.duration_minutes for st in scheduled if st.time_window == w)
            )
            return self.owner.get_budget(w) - used
        return max(windows, key=remaining)

    def _detect_category_stacks(self, plan: DailyPlan):
        """Emit a conflict when 2+ tasks of the same category land in the same window."""
        from collections import Counter
        for window in [TimeOfDay.MORNING, TimeOfDay.AFTERNOON, TimeOfDay.EVENING]:
            tasks_in_window = [st for st in plan.scheduled_tasks if st.time_window == window]
            category_counts = Counter(st.task.category for st in tasks_in_window)
            for category, count in category_counts.items():
                if count > 1:
                    plan.add_conflict(Conflict(
                        ConflictType.CATEGORY_STACK,
                        f"{count} {category.value} tasks in {window.value} — consider spreading them",
                    ))

    def _detect_time_overlaps(self, plan: DailyPlan):
        """Emit a conflict for every pair of scheduled tasks whose time ranges overlap."""
        tasks = plan.scheduled_tasks
        for i, a in enumerate(tasks):
            for b in tasks[i + 1:]:
                if a.start_time < b.end_time and b.start_time < a.end_time:
                    plan.add_conflict(Conflict(
                        ConflictType.TIME_OVERLAP,
                        f"'{a.task.name}' ({format_time(a.start_time)}–{format_time(a.end_time)}) overlaps "
                        f"'{b.task.name}' ({format_time(b.start_time)}–{format_time(b.end_time)})",
                    ))
