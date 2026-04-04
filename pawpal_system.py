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
        self.dietary_restrictions = dietary_restrictions or []

    def describe(self) -> str:
        pass

    def update(self, **kwargs):
        pass


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

    def validate(self):
        pass

    def fits_in_budget(self, available_minutes: int) -> bool:
        pass

    def is_compatible_with_window(self, window: TimeOfDay) -> bool:
        pass

    def to_dict(self) -> dict:
        pass


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
        self.name = self.name.lower()

    def add_task(self, task: Task):
        pass

    def remove_task(self, task_id: str):
        pass

    def edit_task(self, task_id: str, **kwargs):
        pass

    def get_tasks(self) -> list[Task]:
        pass

    def get_mandatory_tasks(self) -> list[Task]:
        pass

    def get_tasks_by_category(self, category: TaskCategory) -> list[Task]:
        pass

    def get_pending_tasks(self) -> list[Task]:
        pass


# ---------------------------------------------------------------------------
# Owner
# ---------------------------------------------------------------------------

class Owner:
    def __init__(self, name: str, wake_time: str):
        # wake_time entered as "hr:min" e.g. "7:30"
        self.name = name
        self.wake_time = wake_time
        self.time_budget: dict[TimeOfDay, int] = {}
        self._counters: dict[str, int] = {}
        self._pets: dict[str, Pet] = {}

    def add_pet(self, pet: Pet):
        pass

    def get_pets(self) -> list[Pet]:
        pass

    def search_pets(self, name: str) -> list[Pet]:
        pass

    def remove_pet(self, name: str):
        pass

    def set_budget(self, window: TimeOfDay, minutes: int):
        pass

    def get_budget(self, window: TimeOfDay) -> int:
        pass

    def get_total_budget(self) -> int:
        pass

    def _get_pet_by_id(self, pet_id: str) -> Optional[Pet]:
        pass

    def _remove_pet_by_id(self, pet_id: str):
        pass


# ---------------------------------------------------------------------------
# ScheduledTask
# ---------------------------------------------------------------------------

class ScheduledTask:
    def __init__(
        self,
        task: Task,
        date: date,
        start_time: str,
        end_time: str,
        status: TaskStatus,
        reason: str,
    ):
        # start_time and end_time stored as "hr:min" strings
        self.task = task
        self.date = date
        self.start_time = start_time
        self.end_time = end_time
        self.status = status
        self.reason = reason

    @property
    def duration_minutes(self) -> int:
        pass

    def mark_completed(self):
        pass

    def mark_skipped(self):
        pass

    def __str__(self) -> str:
        pass


# ---------------------------------------------------------------------------
# DailyPlan
# ---------------------------------------------------------------------------

class DailyPlan:
    def __init__(self, date: date):
        self.date = date
        self.scheduled_tasks: list[ScheduledTask] = []
        self.skipped_tasks: list[Task] = []
        self.warnings: list[str] = []

    def add_scheduled_task(self, st: ScheduledTask):
        pass

    def add_skipped_task(self, task: Task):
        pass

    def add_warning(self, msg: str):
        pass

    def get_window_summary(self) -> dict:
        pass

    def get_reasoning(self) -> str:
        pass

    def get_skipped_for_carryover(self) -> list[Task]:
        pass

    def __str__(self) -> str:
        pass


# ---------------------------------------------------------------------------
# Scheduler
# ---------------------------------------------------------------------------

class Scheduler:
    def __init__(self, owner: Owner, pet: Pet):
        self.owner = owner
        self.pet = pet

    def generate_plan(self, plan_date: date) -> DailyPlan:
        pass

    def _schedule_mandatory(self, tasks: list[Task]) -> list[ScheduledTask]:
        pass

    def _schedule_optional(self, tasks: list[Task], remaining: dict) -> list[ScheduledTask]:
        pass

    def _sort_by_priority(self, tasks: list[Task]) -> list[Task]:
        pass

    def _assign_slot(self, task: Task, current_time: str) -> ScheduledTask:
        pass

    def _remaining_budget(self, window: TimeOfDay, plan: DailyPlan) -> int:
        pass

    def _carry_over(self, previous_plan: DailyPlan) -> list[Task]:
        pass
