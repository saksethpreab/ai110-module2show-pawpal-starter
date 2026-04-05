import sys
from datetime import date

from pawpal_system import (
    Owner, Pet, Task, FoodPreference, Scheduler,
    TaskCategory, Priority, TimeOfDay, format_time,
)

# ---------------------------------------------------------------------------
# Owner setup
# ---------------------------------------------------------------------------

jordan = Owner(name="Jordan", wake_time=420)  # 7:00 = 7*60
jordan.set_budget(TimeOfDay.MORNING,   60)   # 60 min available in the morning
jordan.set_budget(TimeOfDay.AFTERNOON, 90)   # 90 min available in the afternoon
jordan.set_budget(TimeOfDay.EVENING,   30)   # 30 min available in the evening

# ---------------------------------------------------------------------------
# Pet 1 — Mochi the dog
# ---------------------------------------------------------------------------

mochi = Pet(name="Mochi", species="dog", breed="Shiba Inu", age_years=3.0)
jordan.add_pet(mochi)

mochi_food = FoodPreference(
    food_name="Royal Canin Medium Adult",
    food_type="dry",
    portion_size_grams=180,
    feedings_per_day=2,
    dietary_restrictions=["no grain"],
)

for task in [
    Task(
        id="m1",
        name="Morning Walk",
        category=TaskCategory.WALK,
        duration_minutes=30,
        priority=Priority.HIGH,
        preferred_time=TimeOfDay.MORNING,
        is_mandatory=True,
        notes="Loop around the park",
    ),
    Task(
        id="m2",
        name="Morning Feeding",
        category=TaskCategory.FEEDING,
        duration_minutes=10,
        priority=Priority.HIGH,
        preferred_time=TimeOfDay.MORNING,
        is_mandatory=True,
        food_preference=mochi_food,
    ),
    Task(
        id="m3",
        name="Enrichment Puzzle",
        category=TaskCategory.ENRICHMENT,
        duration_minutes=20,
        priority=Priority.MEDIUM,
        preferred_time=TimeOfDay.AFTERNOON,
        is_mandatory=False,
        notes="Snuffle mat or Kong toy",
    ),
    Task(
        id="m4",
        name="Evening Feeding",
        category=TaskCategory.FEEDING,
        duration_minutes=10,
        priority=Priority.HIGH,
        preferred_time=TimeOfDay.EVENING,
        is_mandatory=True,
        food_preference=mochi_food,
    ),
]:
    task.validate()
    mochi.add_task(task)

# ---------------------------------------------------------------------------
# Pet 2 — Luna the cat
# ---------------------------------------------------------------------------

luna = Pet(name="Luna", species="cat", breed="Domestic Shorthair", age_years=5.0)
jordan.add_pet(luna)

luna_food = FoodPreference(
    food_name="Hills Science Diet Indoor",
    food_type="wet",
    portion_size_grams=85,
    feedings_per_day=2,
)

for task in [
    Task(
        id="l1",
        name="Morning Feeding",
        category=TaskCategory.FEEDING,
        duration_minutes=5,
        priority=Priority.HIGH,
        preferred_time=TimeOfDay.MORNING,
        is_mandatory=True,
        food_preference=luna_food,
    ),
    Task(
        id="l2",
        name="Grooming Session",
        category=TaskCategory.GROOMING,
        duration_minutes=15,
        priority=Priority.MEDIUM,
        preferred_time=TimeOfDay.AFTERNOON,
        is_mandatory=False,
        notes="Brush and check ears",
    ),
    Task(
        id="l3",
        name="Evening Feeding",
        category=TaskCategory.FEEDING,
        duration_minutes=5,
        priority=Priority.HIGH,
        preferred_time=TimeOfDay.EVENING,
        is_mandatory=True,
        food_preference=luna_food,
    ),
    Task(
        id="l4",
        name="Playtime",
        category=TaskCategory.ENRICHMENT,
        duration_minutes=20,
        priority=Priority.LOW,
        preferred_time=TimeOfDay.EVENING,
        is_mandatory=False,
        notes="Wand toy or laser pointer",
    ),
]:
    task.validate()
    luna.add_task(task)

# ---------------------------------------------------------------------------
# Generate schedules
# ---------------------------------------------------------------------------

# Accept an optional date argument: python main.py 2025-12-25
plan_date = date.fromisoformat(sys.argv[1]) if len(sys.argv) > 1 else date.today()

plans = [Scheduler(jordan, pet).generate_plan(plan_date) for pet in jordan.get_pets()]

# ---------------------------------------------------------------------------
# Print Today's Schedule
# ---------------------------------------------------------------------------

SEPARATOR = "=" * 55

print(SEPARATOR)
print("  PAWPAL+ - Today's Schedule")
print(f"  {plan_date.strftime('%A, %B %d %Y')}  |  Owner: {jordan.name}")
print(SEPARATOR)

for plan in plans:
    print()
    print(f"  {plan.pet.name.upper()}  ({plan.pet.breed})")
    print("-" * 55)

    if plan.scheduled_tasks:
        for st in plan.scheduled_tasks:
            print(f"  {format_time(st.start_time):>5} - {format_time(st.end_time):<5}  {st.task.name}")
            print(f"               -> {st.reason}")
    else:
        print("  (no tasks scheduled)")

    if plan.skipped_tasks:
        print()
        print("  Skipped (carry over tomorrow):")
        for t in plan.skipped_tasks:
            print(f"    - {t.name} [{t.priority.name}]")

    if plan.warnings:
        print()
        print("  Warnings:")
        for w in plan.warnings:
            print(f"    ! {w}")

print()
print(SEPARATOR)

# Budget summary across all pets
print("  Budget summary")
print("-" * 55)
for plan in plans:
    summary = plan.get_window_summary()
    parts = [
        f"{window}: {summary[window]['used_minutes']}/{summary[window]['budget_minutes']} min"
        for window in ("morning", "afternoon", "evening")
    ]
    print(f"  {plan.pet.name.title():<8}  {' | '.join(parts)}")

print(SEPARATOR)
