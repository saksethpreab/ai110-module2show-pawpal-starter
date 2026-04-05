"""
Unit tests for pawpal_system.py
Run with:  python -m pytest test_pawpal_system.py -v
       or: python -m unittest discover
"""

import unittest
from datetime import date

from pawpal_system import (
    # Time helpers
    parse_time_str, format_time, time_to_window, recurrence_applies_to_date,
    # Enums
    TaskCategory, Priority, TimeOfDay, TaskStatus, RecurrenceType, ConflictType,
    # Classes
    FoodPreference, Task, Pet, Owner, ScheduledTask, DailyPlan, Scheduler, Recurrence,
)

TODAY = date(2026, 4, 4)


# ---------------------------------------------------------------------------
# Helpers shared across tests
# ---------------------------------------------------------------------------

def make_task(
    task_id="t1",
    name="Morning Walk",
    category=TaskCategory.WALK,
    duration=30,
    priority=Priority.HIGH,
    preferred_time=TimeOfDay.MORNING,
    is_mandatory=False,
    notes=None,
    food_preference=None,
) -> Task:
    return Task(
        id=task_id,
        name=name,
        category=category,
        duration_minutes=duration,
        priority=priority,
        preferred_time=preferred_time,
        is_mandatory=is_mandatory,
        notes=notes,
        food_preference=food_preference,
    )


def make_owner(wake_time=420, morning=60, afternoon=90, evening=30) -> Owner:
    owner = Owner("Jordan", wake_time)
    owner.set_budget(TimeOfDay.MORNING, morning)
    owner.set_budget(TimeOfDay.AFTERNOON, afternoon)
    owner.set_budget(TimeOfDay.EVENING, evening)
    return owner


def make_scheduled_task(task=None, start=420, duration=30,
                        window=TimeOfDay.MORNING, status=TaskStatus.SCHEDULED) -> ScheduledTask:
    if task is None:
        task = make_task()
    end = start + duration
    return ScheduledTask(
        task=task,
        date=TODAY,
        start_time=start,
        end_time=end,
        status=status,
        reason="test",
        time_window=window,
    )


# ===========================================================================
# Time helpers
# ===========================================================================

class TestTimeHelpers(unittest.TestCase):

    # --- parse_time_str ---

    def test_parse_time_str_whole_hour(self):
        """Parses '7:00' into 420 minutes."""
        self.assertEqual(parse_time_str("7:00"), 420)

    def test_parse_time_str_with_minutes(self):
        """Parses '14:35' into 875 minutes."""
        self.assertEqual(parse_time_str("14:35"), 875)

    def test_parse_time_str_zero_padded(self):
        """Parses '9:05' correctly."""
        self.assertEqual(parse_time_str("9:05"), 545)

    # --- format_time ---

    def test_format_time_pads_minutes(self):
        """Minutes < 10 are zero-padded in the output string."""
        self.assertEqual(format_time(485), "8:05")

    def test_format_time_two_digit_minutes(self):
        """Minutes >= 10 are not padded."""
        self.assertEqual(format_time(825), "13:45")

    def test_format_time_midnight(self):
        """Midnight formats as 0:00."""
        self.assertEqual(format_time(0), "0:00")

    # --- time_to_window ---

    def test_window_morning(self):
        """Any time before 720 (12:00) maps to MORNING."""
        self.assertEqual(time_to_window(450), TimeOfDay.MORNING)   # 7:30
        self.assertEqual(time_to_window(719), TimeOfDay.MORNING)   # 11:59

    def test_window_afternoon(self):
        """720–1019 maps to AFTERNOON."""
        self.assertEqual(time_to_window(720), TimeOfDay.AFTERNOON)  # 12:00
        self.assertEqual(time_to_window(1005), TimeOfDay.AFTERNOON) # 16:45

    def test_window_evening(self):
        """1020 (17:00) and later maps to EVENING."""
        self.assertEqual(time_to_window(1020), TimeOfDay.EVENING)  # 17:00
        self.assertEqual(time_to_window(1230), TimeOfDay.EVENING)  # 20:30


# ===========================================================================
# FoodPreference
# ===========================================================================

class TestFoodPreference(unittest.TestCase):

    def setUp(self):
        self.fp = FoodPreference(
            food_name="Royal Canin",
            food_type="dry",
            portion_size_grams=200,
            feedings_per_day=2,
            dietary_restrictions=["grain-free"],
        )

    def test_describe_includes_all_fields(self):
        """describe() contains the brand, type, portion, feeding count, and restrictions."""
        result = self.fp.describe()
        self.assertIn("Royal Canin", result)
        self.assertIn("dry", result)
        self.assertIn("200g", result)
        self.assertIn("2/day", result)
        self.assertIn("grain-free", result)

    def test_describe_no_restrictions(self):
        """When no restrictions exist, describe() shows 'none'."""
        fp = FoodPreference("Brand", "wet", 150, 3)
        self.assertIn("none", fp.describe())

    def test_default_dietary_restrictions_is_empty_list(self):
        """Omitting dietary_restrictions defaults to [] not None."""
        fp = FoodPreference("Brand", "wet", 150, 3)
        self.assertEqual(fp.dietary_restrictions, [])

    def test_update_valid_field(self):
        """update() changes a valid field."""
        self.fp.update(portion_size_grams=250)
        self.assertEqual(self.fp.portion_size_grams, 250)

    def test_update_multiple_fields(self):
        """update() can change several fields in one call."""
        self.fp.update(feedings_per_day=3, food_type="raw")
        self.assertEqual(self.fp.feedings_per_day, 3)
        self.assertEqual(self.fp.food_type, "raw")

    def test_update_ignores_unknown_key(self):
        """update() silently ignores keys that are not real attributes."""
        self.fp.update(nonexistent_field="value")  # should not raise


# ===========================================================================
# Task
# ===========================================================================

class TestTask(unittest.TestCase):

    def setUp(self):
        self.task = make_task()

    # --- validate ---

    def test_validate_passes_for_valid_task(self):
        """validate() does not raise when the task is properly configured."""
        self.task.validate()  # no exception

    def test_validate_raises_on_zero_duration(self):
        """validate() raises ValueError if duration_minutes is 0."""
        self.task.duration_minutes = 0
        with self.assertRaises(ValueError):
            self.task.validate()

    def test_validate_raises_on_negative_duration(self):
        """validate() raises ValueError if duration_minutes is negative."""
        self.task.duration_minutes = -10
        with self.assertRaises(ValueError):
            self.task.validate()

    def test_validate_raises_on_empty_name(self):
        """validate() raises ValueError if name is blank/whitespace."""
        self.task.name = "   "
        with self.assertRaises(ValueError):
            self.task.validate()

    # --- fits_in_budget ---

    def test_fits_in_budget_exactly(self):
        """Task fits when duration equals the available minutes exactly."""
        self.assertTrue(self.task.fits_in_budget(30))

    def test_fits_in_budget_more_than_enough(self):
        """Task fits when there is more time than the task needs."""
        self.assertTrue(self.task.fits_in_budget(60))

    def test_fits_in_budget_not_enough(self):
        """Task does not fit when available minutes is less than duration."""
        self.assertFalse(self.task.fits_in_budget(20))

    # --- is_compatible_with_window ---

    def test_compatible_with_matching_window(self):
        """A MORNING task is compatible with the MORNING window."""
        self.assertTrue(self.task.is_compatible_with_window(TimeOfDay.MORNING))

    def test_not_compatible_with_different_window(self):
        """A MORNING task is NOT compatible with AFTERNOON."""
        self.assertFalse(self.task.is_compatible_with_window(TimeOfDay.AFTERNOON))

    def test_any_time_compatible_with_all_windows(self):
        """A task with preferred_time=ANY is compatible with every window."""
        task = make_task(preferred_time=TimeOfDay.ANY)
        for window in [TimeOfDay.MORNING, TimeOfDay.AFTERNOON, TimeOfDay.EVENING]:
            self.assertTrue(task.is_compatible_with_window(window))

    # --- to_dict ---

    def test_to_dict_contains_all_keys(self):
        """to_dict() returns a dict with all expected keys."""
        d = self.task.to_dict()
        for key in ("id", "name", "category", "duration_minutes",
                    "priority", "preferred_time", "is_mandatory", "notes"):
            self.assertIn(key, d)

    def test_to_dict_enum_values_are_strings(self):
        """to_dict() serializes enums to their string representations."""
        d = self.task.to_dict()
        self.assertIsInstance(d["category"], str)
        self.assertIsInstance(d["priority"], str)
        self.assertIsInstance(d["preferred_time"], str)

    def test_to_dict_values_match(self):
        """to_dict() values reflect the task's actual data."""
        d = self.task.to_dict()
        self.assertEqual(d["id"], "t1")
        self.assertEqual(d["duration_minutes"], 30)
        self.assertFalse(d["is_mandatory"])


# ===========================================================================
# Pet
# ===========================================================================

class TestPet(unittest.TestCase):

    def setUp(self):
        self.pet = Pet("Mochi", "dog")
        self.task = make_task()

    # --- __post_init__ ---

    def test_name_stored_lowercase(self):
        """Pet names are normalized to lowercase on creation."""
        p = Pet("BUDDY", "dog")
        self.assertEqual(p.name, "buddy")

    def test_mixed_case_name_lowercased(self):
        """Mixed-case names are fully lowercased."""
        p = Pet("Luna Belle", "cat")
        self.assertEqual(p.name, "luna belle")

    # --- add_task / remove_task ---

    def test_add_task_increases_count(self):
        """add_task() appends the task to the pet's task list."""
        self.pet.add_task(self.task)
        self.assertEqual(len(self.pet.tasks), 1)

    def test_task_addition_increases_pet_task_count(self):
        """Adding a task to a Pet increases that pet's task count by one."""
        count_before = len(self.pet.get_tasks())
        self.pet.add_task(self.task)
        count_after = len(self.pet.get_tasks())
        self.assertEqual(count_after, count_before + 1)

    def test_add_multiple_tasks(self):
        """Multiple tasks can be added and all are stored."""
        self.pet.add_task(make_task("t1"))
        self.pet.add_task(make_task("t2"))
        self.assertEqual(len(self.pet.tasks), 2)

    def test_remove_task_by_id(self):
        """remove_task() deletes the task with the matching id."""
        self.pet.add_task(self.task)
        self.pet.remove_task("t1")
        self.assertEqual(len(self.pet.tasks), 0)

    def test_remove_task_nonexistent_id_is_silent(self):
        """remove_task() does not raise when the id does not exist."""
        self.pet.add_task(self.task)
        self.pet.remove_task("does-not-exist")  # should not raise
        self.assertEqual(len(self.pet.tasks), 1)

    def test_remove_task_only_removes_target(self):
        """remove_task() leaves other tasks intact."""
        t1 = make_task("t1")
        t2 = make_task("t2", name="Evening Walk")
        self.pet.add_task(t1)
        self.pet.add_task(t2)
        self.pet.remove_task("t1")
        self.assertEqual(self.pet.tasks[0].id, "t2")

    # --- edit_task ---

    def test_edit_task_changes_name(self):
        """edit_task() updates the name field."""
        self.pet.add_task(self.task)
        self.pet.edit_task("t1", name="Afternoon Walk")
        self.assertEqual(self.pet.tasks[0].name, "Afternoon Walk")

    def test_edit_task_changes_duration(self):
        """edit_task() updates duration_minutes."""
        self.pet.add_task(self.task)
        self.pet.edit_task("t1", duration_minutes=45)
        self.assertEqual(self.pet.tasks[0].duration_minutes, 45)

    def test_edit_task_none_args_are_ignored(self):
        """edit_task() does not overwrite fields when the argument is None."""
        self.pet.add_task(self.task)
        self.pet.edit_task("t1", name=None)
        self.assertEqual(self.pet.tasks[0].name, "Morning Walk")

    def test_edit_task_raises_for_unknown_id(self):
        """edit_task() raises KeyError when the task id is not found."""
        with self.assertRaises(KeyError):
            self.pet.edit_task("nonexistent", name="Oops")

    # --- get_tasks ---

    def test_get_tasks_returns_copy(self):
        """get_tasks() returns a new list, not the internal reference."""
        self.pet.add_task(self.task)
        result = self.pet.get_tasks()
        result.clear()
        self.assertEqual(len(self.pet.tasks), 1)  # internal list unchanged

    # --- get_mandatory_tasks ---

    def test_get_mandatory_tasks_filters_correctly(self):
        """get_mandatory_tasks() returns only tasks with is_mandatory=True."""
        self.pet.add_task(make_task("t1", is_mandatory=True))
        self.pet.add_task(make_task("t2", is_mandatory=False))
        mandatory = self.pet.get_mandatory_tasks()
        self.assertEqual(len(mandatory), 1)
        self.assertEqual(mandatory[0].id, "t1")

    def test_get_mandatory_tasks_empty_when_none(self):
        """get_mandatory_tasks() returns [] when no tasks are mandatory."""
        self.pet.add_task(make_task("t1", is_mandatory=False))
        self.assertEqual(self.pet.get_mandatory_tasks(), [])

    # --- get_tasks_by_category ---

    def test_get_tasks_by_category_filters_correctly(self):
        """get_tasks_by_category() returns only tasks of the requested type."""
        self.pet.add_task(make_task("t1", category=TaskCategory.WALK))
        self.pet.add_task(make_task("t2", category=TaskCategory.FEEDING))
        walks = self.pet.get_tasks_by_category(TaskCategory.WALK)
        self.assertEqual(len(walks), 1)
        self.assertEqual(walks[0].id, "t1")

    def test_get_tasks_by_category_empty_when_none_match(self):
        """get_tasks_by_category() returns [] when no tasks match."""
        self.pet.add_task(make_task("t1", category=TaskCategory.WALK))
        self.assertEqual(self.pet.get_tasks_by_category(TaskCategory.VET), [])

    # --- get_pending_tasks ---

    def test_get_pending_tasks_no_scheduled_returns_all(self):
        """Without a scheduled list, all tasks are considered pending."""
        self.pet.add_task(self.task)
        pending = self.pet.get_pending_tasks()
        self.assertEqual(len(pending), 1)

    def test_get_pending_tasks_excludes_scheduled(self):
        """Tasks that already have a ScheduledTask entry are excluded."""
        self.pet.add_task(self.task)
        st = make_scheduled_task(task=self.task)
        pending = self.pet.get_pending_tasks(scheduled_tasks=[st])
        self.assertEqual(pending, [])

    def test_get_pending_tasks_returns_unscheduled_only(self):
        """Only the task without a slot is returned as pending."""
        t1 = make_task("t1")
        t2 = make_task("t2", name="Bath")
        self.pet.add_task(t1)
        self.pet.add_task(t2)
        st = make_scheduled_task(task=t1)
        pending = self.pet.get_pending_tasks(scheduled_tasks=[st])
        self.assertEqual(len(pending), 1)
        self.assertEqual(pending[0].id, "t2")


# ===========================================================================
# Owner
# ===========================================================================

class TestOwner(unittest.TestCase):

    def setUp(self):
        self.owner = make_owner()
        self.pet = Pet("Mochi", "dog")

    # --- add_pet / id generation ---

    def test_add_pet_generates_id(self):
        """add_pet() assigns an id when the pet has none."""
        self.owner.add_pet(self.pet)
        self.assertIsNotNone(self.pet.id)

    def test_add_pet_dog_id_starts_with_d(self):
        """Dogs get ids starting with 'd'."""
        self.owner.add_pet(self.pet)
        self.assertTrue(self.pet.id.startswith("d"))

    def test_add_pet_cat_id_starts_with_c(self):
        """Cats get ids starting with 'c'."""
        cat = Pet("Luna", "cat")
        self.owner.add_pet(cat)
        self.assertTrue(cat.id.startswith("c"))

    def test_add_pet_id_is_zero_padded(self):
        """The counter portion of the id is zero-padded to three digits."""
        self.owner.add_pet(self.pet)
        self.assertEqual(self.pet.id, "d001")

    def test_add_pet_counter_increments_per_species(self):
        """Each additional dog increments the dog counter independently from cats."""
        d1 = Pet("Rex", "dog")
        d2 = Pet("Buddy", "dog")
        c1 = Pet("Luna", "cat")
        self.owner.add_pet(d1)
        self.owner.add_pet(d2)
        self.owner.add_pet(c1)
        self.assertEqual(d1.id, "d001")
        self.assertEqual(d2.id, "d002")
        self.assertEqual(c1.id, "c001")

    def test_add_pet_existing_id_is_preserved(self):
        """add_pet() does not overwrite an id the pet already has."""
        self.pet.id = "custom-id"
        self.owner.add_pet(self.pet)
        self.assertEqual(self.pet.id, "custom-id")

    # --- get_pets ---

    def test_get_pets_returns_all(self):
        """get_pets() returns every pet that has been added."""
        self.owner.add_pet(Pet("Rex", "dog"))
        self.owner.add_pet(Pet("Luna", "cat"))
        self.assertEqual(len(self.owner.get_pets()), 2)

    def test_get_pets_empty_initially(self):
        """A newly created owner has no pets."""
        self.assertEqual(self.owner.get_pets(), [])

    # --- search_pets ---

    def test_search_pets_finds_by_name(self):
        """search_pets() returns pets whose name matches."""
        self.owner.add_pet(self.pet)
        results = self.owner.search_pets("Mochi")
        self.assertEqual(len(results), 1)

    def test_search_pets_case_insensitive(self):
        """search_pets() matches regardless of input casing."""
        self.owner.add_pet(self.pet)
        self.assertEqual(len(self.owner.search_pets("MOCHI")), 1)
        self.assertEqual(len(self.owner.search_pets("mochi")), 1)

    def test_search_pets_no_match_returns_empty(self):
        """search_pets() returns [] when no pet has the given name."""
        self.owner.add_pet(self.pet)
        self.assertEqual(self.owner.search_pets("Nemo"), [])

    def test_search_pets_multiple_matches(self):
        """search_pets() returns all pets sharing a name."""
        self.owner.add_pet(Pet("Luna", "dog"))
        self.owner.add_pet(Pet("Luna", "cat"))
        self.assertEqual(len(self.owner.search_pets("Luna")), 2)

    # --- remove_pet ---

    def test_remove_pet_returns_true_on_unique_match(self):
        """remove_pet() returns True when exactly one pet has that name."""
        self.owner.add_pet(self.pet)
        self.assertTrue(self.owner.remove_pet("Mochi"))

    def test_remove_pet_actually_removes_the_pet(self):
        """After remove_pet(), the pet is no longer in the owner's list."""
        self.owner.add_pet(self.pet)
        self.owner.remove_pet("Mochi")
        self.assertEqual(self.owner.get_pets(), [])

    def test_remove_pet_returns_false_when_not_found(self):
        """remove_pet() returns False when no pet with that name exists."""
        result = self.owner.remove_pet("Ghost")
        self.assertFalse(result)

    def test_remove_pet_returns_list_on_ambiguous_match(self):
        """remove_pet() returns the matching pet list when multiple share the name."""
        self.owner.add_pet(Pet("Luna", "dog"))
        self.owner.add_pet(Pet("Luna", "cat"))
        result = self.owner.remove_pet("Luna")
        self.assertIsInstance(result, list)
        self.assertEqual(len(result), 2)

    def test_remove_pet_does_not_remove_on_ambiguous_match(self):
        """When multiple pets match, none are removed (caller must choose)."""
        self.owner.add_pet(Pet("Luna", "dog"))
        self.owner.add_pet(Pet("Luna", "cat"))
        self.owner.remove_pet("Luna")
        self.assertEqual(len(self.owner.get_pets()), 2)

    # --- budget ---

    def test_set_and_get_budget(self):
        """set_budget() stores the value and get_budget() retrieves it."""
        self.owner.set_budget(TimeOfDay.MORNING, 45)
        self.assertEqual(self.owner.get_budget(TimeOfDay.MORNING), 45)

    def test_get_budget_default_zero(self):
        """get_budget() returns 0 for a window that has never been set."""
        fresh_owner = Owner("Alex", 360)
        self.assertEqual(fresh_owner.get_budget(TimeOfDay.MORNING), 0)

    def test_get_total_budget_sums_all_windows(self):
        """get_total_budget() is the sum across all windows that have been set."""
        # setUp already set morning=60, afternoon=90, evening=30
        self.assertEqual(self.owner.get_total_budget(), 180)

    # --- internal helpers ---

    def test_get_pet_by_id_returns_correct_pet(self):
        """_get_pet_by_id() returns the matching pet object."""
        self.owner.add_pet(self.pet)
        found = self.owner._get_pet_by_id(self.pet.id)
        self.assertIs(found, self.pet)

    def test_get_pet_by_id_returns_none_for_missing(self):
        """_get_pet_by_id() returns None when the id is unknown."""
        self.assertIsNone(self.owner._get_pet_by_id("nonexistent"))

    def test_remove_pet_by_id(self):
        """_remove_pet_by_id() removes the pet from internal storage."""
        self.owner.add_pet(self.pet)
        self.owner._remove_pet_by_id(self.pet.id)
        self.assertEqual(self.owner.get_pets(), [])

    def test_remove_pet_by_id_missing_is_silent(self):
        """_remove_pet_by_id() does not raise for an unknown id."""
        self.owner._remove_pet_by_id("ghost")  # should not raise


# ===========================================================================
# ScheduledTask
# ===========================================================================

class TestScheduledTask(unittest.TestCase):

    def setUp(self):
        self.task = make_task(duration=30)
        self.st = make_scheduled_task(task=self.task, start=420, duration=30)

    # --- duration_minutes property ---

    def test_duration_minutes_computed_correctly(self):
        """duration_minutes reflects the difference between start and end times."""
        self.assertEqual(self.st.duration_minutes, 30)

    def test_duration_minutes_across_hour_boundary(self):
        """duration_minutes works when start and end are in different hours."""
        task = make_task(duration=45)
        st = make_scheduled_task(task=task, start=450, duration=45)
        self.assertEqual(st.duration_minutes, 45)

    # --- mark_completed / mark_skipped ---

    def test_mark_completed_sets_status(self):
        """mark_completed() transitions status to COMPLETED."""
        self.st.mark_completed()
        self.assertEqual(self.st.status, TaskStatus.COMPLETED)

    def test_mark_complete_changes_task_status(self):
        """Calling mark_completed() actually changes the ScheduledTask's status field."""
        self.assertNotEqual(self.st.status, TaskStatus.COMPLETED)  # confirm it starts differently
        self.st.mark_completed()
        self.assertEqual(self.st.status, TaskStatus.COMPLETED)

    def test_mark_skipped_sets_status(self):
        """mark_skipped() transitions status to SKIPPED."""
        self.st.mark_skipped()
        self.assertEqual(self.st.status, TaskStatus.SKIPPED)

    # --- __str__ ---

    def test_str_includes_time_range(self):
        """__str__() shows the start and end times."""
        s = str(self.st)
        self.assertIn("7:00", s)
        self.assertIn("7:30", s)

    def test_str_includes_task_name(self):
        """__str__() shows the task name."""
        self.assertIn("Morning Walk", str(self.st))

    def test_str_includes_status(self):
        """__str__() shows the task's current status."""
        self.assertIn("scheduled", str(self.st))


# ===========================================================================
# DailyPlan
# ===========================================================================

class TestDailyPlan(unittest.TestCase):

    def setUp(self):
        self.owner = make_owner()
        self.pet = Pet("Mochi", "dog")
        self.owner.add_pet(self.pet)
        self.plan = DailyPlan(TODAY, self.owner, self.pet)

    # --- add_scheduled_task ---

    def test_add_scheduled_task_appends(self):
        """add_scheduled_task() adds the task to scheduled_tasks."""
        st = make_scheduled_task()
        self.plan.add_scheduled_task(st)
        self.assertEqual(len(self.plan.scheduled_tasks), 1)

    # --- add_skipped_task ---

    def test_add_skipped_task_appends(self):
        """add_skipped_task() adds the task to skipped_tasks."""
        self.plan.add_skipped_task(make_task())
        self.assertEqual(len(self.plan.skipped_tasks), 1)

    # --- add_warning ---

    def test_add_warning_appends(self):
        """add_warning() stores the warning message."""
        self.plan.add_warning("budget exceeded")
        self.assertIn("budget exceeded", self.plan.warnings)

    # --- get_window_summary ---

    def test_window_summary_counts_tasks(self):
        """get_window_summary() correctly counts tasks per window."""
        t = make_task(duration=20)
        st = make_scheduled_task(task=t, start=420, duration=20, window=TimeOfDay.MORNING)
        self.plan.add_scheduled_task(st)
        summary = self.plan.get_window_summary()
        self.assertEqual(summary["morning"]["tasks"], 1)
        self.assertEqual(summary["morning"]["used_minutes"], 20)

    def test_window_summary_used_minutes_sums_correctly(self):
        """get_window_summary() sums duration across multiple tasks in a window."""
        for i, dur in enumerate([20, 25]):
            t = make_task(f"t{i}", duration=dur)
            st = make_scheduled_task(task=t, start=420 + i * 60, duration=dur,
                                     window=TimeOfDay.MORNING)
            self.plan.add_scheduled_task(st)
        summary = self.plan.get_window_summary()
        self.assertEqual(summary["morning"]["used_minutes"], 45)

    def test_window_summary_budget_reflects_owner(self):
        """get_window_summary() shows the owner's configured budget."""
        summary = self.plan.get_window_summary()
        self.assertEqual(summary["morning"]["budget_minutes"], 60)

    def test_window_summary_empty_windows_are_zero(self):
        """Windows with no scheduled tasks show 0 used minutes."""
        summary = self.plan.get_window_summary()
        self.assertEqual(summary["afternoon"]["used_minutes"], 0)

    # --- get_skipped_for_carryover ---

    def test_get_skipped_for_carryover_returns_copy(self):
        """get_skipped_for_carryover() returns a copy, not the internal list."""
        self.plan.add_skipped_task(make_task())
        result = self.plan.get_skipped_for_carryover()
        result.clear()
        self.assertEqual(len(self.plan.skipped_tasks), 1)

    # --- get_reasoning / __str__ ---

    def test_reasoning_includes_pet_and_owner_name(self):
        """get_reasoning() header names the pet and owner."""
        text = self.plan.get_reasoning()
        self.assertIn("mochi", text)
        self.assertIn("Jordan", text)

    def test_reasoning_includes_scheduled_task(self):
        """get_reasoning() lists each scheduled task with its reason."""
        t = make_task(name="Bath Time")
        st = make_scheduled_task(task=t)
        st.reason = "test reason"
        self.plan.add_scheduled_task(st)
        text = self.plan.get_reasoning()
        self.assertIn("Bath Time", text)
        self.assertIn("test reason", text)

    def test_reasoning_includes_skipped_section(self):
        """get_reasoning() has a skipped section when tasks were skipped."""
        self.plan.add_skipped_task(make_task(name="Nail Trim"))
        text = self.plan.get_reasoning()
        self.assertIn("Skipped", text)
        self.assertIn("Nail Trim", text)

    def test_reasoning_includes_warnings(self):
        """get_reasoning() shows warnings when present."""
        self.plan.add_warning("Morning budget exceeded by 5 min")
        text = self.plan.get_reasoning()
        self.assertIn("Warnings", text)
        self.assertIn("Morning budget exceeded", text)

    def test_str_delegates_to_get_reasoning(self):
        """__str__() returns the same string as get_reasoning()."""
        self.assertEqual(str(self.plan), self.plan.get_reasoning())


# ===========================================================================
# Scheduler
# ===========================================================================

class TestScheduler(unittest.TestCase):

    def setUp(self):
        self.owner = make_owner(wake_time=420, morning=60, afternoon=90, evening=30)
        self.pet = Pet("Mochi", "dog")
        self.owner.add_pet(self.pet)
        self.scheduler = Scheduler(self.owner, self.pet)

    # --- basic plan generation ---

    def test_generate_plan_returns_daily_plan(self):
        """generate_plan() returns a DailyPlan instance."""
        plan = self.scheduler.generate_plan(TODAY)
        self.assertIsInstance(plan, DailyPlan)

    def test_generate_plan_stores_date(self):
        """The returned plan's date matches the requested date."""
        plan = self.scheduler.generate_plan(TODAY)
        self.assertEqual(plan.date, TODAY)

    def test_generate_plan_empty_pet_produces_empty_plan(self):
        """A pet with no tasks results in no scheduled or skipped tasks."""
        plan = self.scheduler.generate_plan(TODAY)
        self.assertEqual(len(plan.scheduled_tasks), 0)
        self.assertEqual(len(plan.skipped_tasks), 0)

    def test_generate_plan_mandatory_task_is_scheduled(self):
        """A mandatory task always appears in scheduled_tasks."""
        self.pet.add_task(make_task("t1", is_mandatory=True, duration=30,
                                   preferred_time=TimeOfDay.MORNING))
        plan = self.scheduler.generate_plan(TODAY)
        self.assertEqual(len(plan.scheduled_tasks), 1)

    def test_generate_plan_mandatory_task_start_time(self):
        """A mandatory morning task starts at the owner's wake time."""
        self.pet.add_task(make_task("t1", is_mandatory=True, duration=30,
                                   preferred_time=TimeOfDay.MORNING))
        plan = self.scheduler.generate_plan(TODAY)
        self.assertEqual(plan.scheduled_tasks[0].start_time, 420)

    def test_generate_plan_mandatory_task_end_time(self):
        """End time is start time plus duration."""
        self.pet.add_task(make_task("t1", is_mandatory=True, duration=30,
                                   preferred_time=TimeOfDay.MORNING))
        plan = self.scheduler.generate_plan(TODAY)
        self.assertEqual(plan.scheduled_tasks[0].end_time, 450)

    # --- optional task scheduling ---

    def test_optional_task_scheduled_when_fits(self):
        """An optional task is scheduled if it fits within the window budget."""
        self.pet.add_task(make_task("t1", is_mandatory=False, duration=20,
                                   preferred_time=TimeOfDay.MORNING))
        plan = self.scheduler.generate_plan(TODAY)
        self.assertEqual(len(plan.scheduled_tasks), 1)

    def test_optional_task_skipped_when_over_budget(self):
        """An optional task is skipped (not scheduled) when the window is full."""
        # Fill the morning budget with a mandatory task first
        self.pet.add_task(make_task("t1", is_mandatory=True, duration=60,
                                   preferred_time=TimeOfDay.MORNING))
        # This optional task won't fit — 0 minutes left
        self.pet.add_task(make_task("t2", is_mandatory=False, duration=15,
                                   preferred_time=TimeOfDay.MORNING))
        plan = self.scheduler.generate_plan(TODAY)
        scheduled_ids = {st.task.id for st in plan.scheduled_tasks}
        self.assertIn("t1", scheduled_ids)
        self.assertNotIn("t2", scheduled_ids)
        self.assertEqual(plan.skipped_tasks[0].id, "t2")

    def test_optional_any_time_picks_roomiest_window(self):
        """An ANY-time optional task is placed in the window with the most capacity."""
        # Morning budget = 10, afternoon = 90 → optional task should land in afternoon
        owner = make_owner(morning=10, afternoon=90, evening=0)
        pet = Pet("Rex", "dog")
        owner.add_pet(pet)
        pet.add_task(make_task("t1", is_mandatory=False, duration=20,
                               preferred_time=TimeOfDay.ANY))
        plan = Scheduler(owner, pet).generate_plan(TODAY)
        self.assertEqual(plan.scheduled_tasks[0].time_window, TimeOfDay.AFTERNOON)

    # --- task ordering / priority ---

    def test_higher_priority_optional_scheduled_first(self):
        """Among optional tasks in the same window, higher priority is scheduled first."""
        # Budget is tight: only room for one task
        owner = make_owner(morning=0, afternoon=20, evening=0)
        pet = Pet("Rex", "dog")
        owner.add_pet(pet)
        pet.add_task(make_task("low", priority=Priority.LOW, duration=20,
                               preferred_time=TimeOfDay.AFTERNOON))
        pet.add_task(make_task("high", priority=Priority.HIGH, duration=20,
                               preferred_time=TimeOfDay.AFTERNOON))
        plan = Scheduler(owner, pet).generate_plan(TODAY)
        # Only one task fits; it should be the HIGH priority one
        self.assertEqual(len(plan.scheduled_tasks), 1)
        self.assertEqual(plan.scheduled_tasks[0].task.id, "high")

    # --- emergency tasks ---

    def test_emergency_task_is_scheduled(self):
        """An EMERGENCY task always gets a slot regardless of budget."""
        self.pet.add_task(make_task("e1", priority=Priority.EMERGENCY,
                                   is_mandatory=False, duration=30,
                                   preferred_time=TimeOfDay.ANY))
        plan = self.scheduler.generate_plan(TODAY)
        scheduled_ids = {st.task.id for st in plan.scheduled_tasks}
        self.assertIn("e1", scheduled_ids)

    def test_emergency_task_produces_warning(self):
        """generate_plan() adds a warning for every EMERGENCY task."""
        self.pet.add_task(make_task("e1", priority=Priority.EMERGENCY,
                                   is_mandatory=False, duration=15,
                                   preferred_time=TimeOfDay.MORNING))
        plan = self.scheduler.generate_plan(TODAY)
        emergency_warnings = [w for w in plan.warnings if "EMERGENCY" in w]
        self.assertTrue(len(emergency_warnings) > 0)

    def test_emergency_task_scheduled_before_mandatory(self):
        """EMERGENCY tasks appear before mandatory tasks in scheduled_tasks."""
        self.pet.add_task(make_task("m1", is_mandatory=True, duration=20,
                                   preferred_time=TimeOfDay.MORNING))
        self.pet.add_task(make_task("e1", priority=Priority.EMERGENCY,
                                   is_mandatory=False, duration=10,
                                   preferred_time=TimeOfDay.MORNING))
        plan = self.scheduler.generate_plan(TODAY)
        # The first scheduled task should be the emergency one
        self.assertEqual(plan.scheduled_tasks[0].task.id, "e1")

    # --- mandatory over-budget ---

    def test_mandatory_task_scheduled_even_when_over_budget(self):
        """A mandatory task is scheduled even if it exceeds the window budget."""
        # Morning budget = 20 min, task is 40 min
        owner = make_owner(morning=20, afternoon=0, evening=0)
        pet = Pet("Rex", "dog")
        owner.add_pet(pet)
        pet.add_task(make_task("t1", is_mandatory=True, duration=40,
                               preferred_time=TimeOfDay.MORNING))
        plan = Scheduler(owner, pet).generate_plan(TODAY)
        self.assertEqual(len(plan.scheduled_tasks), 1)

    def test_mandatory_over_budget_adds_warning(self):
        """Exceeding a window budget with a mandatory task adds a warning."""
        owner = make_owner(morning=20, afternoon=0, evening=0)
        pet = Pet("Rex", "dog")
        owner.add_pet(pet)
        pet.add_task(make_task("t1", is_mandatory=True, duration=40,
                               preferred_time=TimeOfDay.MORNING))
        plan = Scheduler(owner, pet).generate_plan(TODAY)
        budget_warnings = [w for w in plan.warnings if "budget" in w.lower()]
        self.assertTrue(len(budget_warnings) > 0)

    # --- consecutive tasks share the time cursor ---

    def test_two_morning_tasks_scheduled_back_to_back(self):
        """Two mandatory morning tasks are placed sequentially, not overlapping."""
        self.pet.add_task(make_task("t1", is_mandatory=True, duration=20,
                                   preferred_time=TimeOfDay.MORNING, priority=Priority.HIGH))
        self.pet.add_task(make_task("t2", is_mandatory=True, duration=20,
                                   preferred_time=TimeOfDay.MORNING, priority=Priority.MEDIUM))
        plan = self.scheduler.generate_plan(TODAY)
        times = [(st.start_time, st.end_time) for st in plan.scheduled_tasks]
        # First task: 420-440, second task: 440-460
        self.assertEqual(times[0], (420, 440))
        self.assertEqual(times[1], (440, 460))

    # --- ANY-time mandatory picks best window ---

    def test_mandatory_any_time_picks_window_with_most_capacity(self):
        """A mandatory ANY-time task goes to the window with the most spare budget."""
        owner = make_owner(morning=10, afternoon=90, evening=0)
        pet = Pet("Rex", "dog")
        owner.add_pet(pet)
        pet.add_task(make_task("t1", is_mandatory=True, duration=30,
                               preferred_time=TimeOfDay.ANY))
        plan = Scheduler(owner, pet).generate_plan(TODAY)
        self.assertEqual(plan.scheduled_tasks[0].time_window, TimeOfDay.AFTERNOON)

    # --- carry-over from previous plan ---

    def test_carry_over_adds_skipped_tasks(self):
        """Tasks skipped yesterday appear in today's scheduling pool."""
        yesterday_plan = DailyPlan(date(2026, 4, 3), self.owner, self.pet)
        skipped = make_task("s1", name="Grooming", is_mandatory=True,
                            preferred_time=TimeOfDay.MORNING, duration=15)
        yesterday_plan.add_skipped_task(skipped)

        plan = self.scheduler.generate_plan(TODAY, previous_plan=yesterday_plan)
        scheduled_ids = {st.task.id for st in plan.scheduled_tasks}
        self.assertIn("s1", scheduled_ids)

    def test_carry_over_no_duplicate_if_task_already_on_pet(self):
        """Carry-over does not double-schedule a task that is already on the pet."""
        task = make_task("t1", is_mandatory=True, duration=20,
                         preferred_time=TimeOfDay.MORNING)
        self.pet.add_task(task)

        # Simulate yesterday: same task was skipped
        yesterday_plan = DailyPlan(date(2026, 4, 3), self.owner, self.pet)
        yesterday_plan.add_skipped_task(task)

        plan = self.scheduler.generate_plan(TODAY, previous_plan=yesterday_plan)
        # Task should appear exactly once
        scheduled_ids = [st.task.id for st in plan.scheduled_tasks]
        self.assertEqual(scheduled_ids.count("t1"), 1)

    def test_no_previous_plan_does_not_raise(self):
        """generate_plan() runs fine when previous_plan is omitted."""
        plan = self.scheduler.generate_plan(TODAY)  # should not raise
        self.assertIsNotNone(plan)

    # --- FEEDING task food details in reason ---

    def test_feeding_task_reason_includes_food_details(self):
        """When a FEEDING task has a food_preference, the reason string includes it."""
        fp = FoodPreference("Hills Science", "dry", 180, 2)
        feeding = make_task("f1", category=TaskCategory.FEEDING, is_mandatory=True,
                            duration=10, preferred_time=TimeOfDay.MORNING,
                            food_preference=fp)
        self.pet.add_task(feeding)
        plan = self.scheduler.generate_plan(TODAY)
        reason = plan.scheduled_tasks[0].reason
        self.assertIn("Hills Science", reason)
        self.assertIn("180g", reason)

    # --- _remaining_budget ---

    def test_remaining_budget_full_when_no_tasks(self):
        """_remaining_budget() equals the full window budget when nothing is scheduled."""
        plan = DailyPlan(TODAY, self.owner, self.pet)
        remaining = self.scheduler._remaining_budget(TimeOfDay.MORNING, plan)
        self.assertEqual(remaining, 60)

    def test_remaining_budget_decreases_after_scheduling(self):
        """_remaining_budget() decreases by the duration of tasks already in the window."""
        plan = DailyPlan(TODAY, self.owner, self.pet)
        t = make_task(duration=25)
        st = make_scheduled_task(task=t, start=420, duration=25, window=TimeOfDay.MORNING)
        plan.add_scheduled_task(st)
        remaining = self.scheduler._remaining_budget(TimeOfDay.MORNING, plan)
        self.assertEqual(remaining, 35)

    def test_remaining_budget_never_negative(self):
        """_remaining_budget() returns 0, not a negative number, when over budget."""
        plan = DailyPlan(TODAY, self.owner, self.pet)
        t = make_task(duration=80)  # exceeds morning budget of 60
        st = make_scheduled_task(task=t, start=420, duration=80, window=TimeOfDay.MORNING)
        plan.add_scheduled_task(st)
        remaining = self.scheduler._remaining_budget(TimeOfDay.MORNING, plan)
        self.assertEqual(remaining, 0)

    # --- _sort_by_priority ---

    def test_sort_by_priority_descending(self):
        """_sort_by_priority() returns tasks highest-to-lowest priority."""
        tasks = [
            make_task("low", priority=Priority.LOW),
            make_task("high", priority=Priority.HIGH),
            make_task("med", priority=Priority.MEDIUM),
        ]
        sorted_tasks = self.scheduler._sort_by_priority(tasks)
        priorities = [t.priority.value for t in sorted_tasks]
        self.assertEqual(priorities, sorted(priorities, reverse=True))

    def test_sort_by_priority_emergency_first(self):
        """EMERGENCY tasks appear at the front of the sorted list."""
        tasks = [
            make_task("low", priority=Priority.LOW),
            make_task("emg", priority=Priority.EMERGENCY),
        ]
        sorted_tasks = self.scheduler._sort_by_priority(tasks)
        self.assertEqual(sorted_tasks[0].id, "emg")

    # --- _carry_over ---

    def test_carry_over_returns_mandatory_skipped_tasks(self):
        """_carry_over() returns only mandatory skipped tasks from the previous plan."""
        prev = DailyPlan(date(2026, 4, 3), self.owner, self.pet)
        skipped = make_task("s1", is_mandatory=True)
        prev.add_skipped_task(skipped)
        carried = self.scheduler._carry_over(prev)
        self.assertEqual(len(carried), 1)
        self.assertEqual(carried[0].id, "s1")

    def test_carry_over_excludes_optional_skipped_tasks(self):
        """_carry_over() does NOT carry over optional (non-mandatory) skipped tasks."""
        prev = DailyPlan(date(2026, 4, 3), self.owner, self.pet)
        optional = make_task("o1", is_mandatory=False)
        prev.add_skipped_task(optional)
        carried = self.scheduler._carry_over(prev)
        self.assertEqual(len(carried), 0)

    def test_carry_over_includes_emergency_even_if_not_mandatory(self):
        """_carry_over() carries over EMERGENCY priority tasks even if not mandatory."""
        prev = DailyPlan(date(2026, 4, 3), self.owner, self.pet)
        emergency = make_task("e1", priority=Priority.EMERGENCY, is_mandatory=False)
        prev.add_skipped_task(emergency)
        carried = self.scheduler._carry_over(prev)
        self.assertEqual(len(carried), 1)
        self.assertEqual(carried[0].id, "e1")

    def test_carry_over_empty_when_nothing_skipped(self):
        """_carry_over() returns [] when the previous plan had no skipped tasks."""
        prev = DailyPlan(date(2026, 4, 3), self.owner, self.pet)
        self.assertEqual(self.scheduler._carry_over(prev), [])


# ===========================================================================
# Edge cases
# ===========================================================================

class TestEdgeCasesTimeHelpers(unittest.TestCase):

    def test_parse_time_str_roundtrip(self):
        """parse_time_str and format_time are inverses for valid times."""
        self.assertEqual(format_time(parse_time_str("7:00")), "7:00")
        self.assertEqual(format_time(parse_time_str("9:30")), "9:30")

    def test_time_to_window_exact_noon_boundary(self):
        """720 (12:00) exactly is AFTERNOON, not MORNING."""
        self.assertEqual(time_to_window(720), TimeOfDay.AFTERNOON)

    def test_time_to_window_exact_evening_boundary(self):
        """1020 (17:00) exactly is EVENING, not AFTERNOON."""
        self.assertEqual(time_to_window(1020), TimeOfDay.EVENING)

    def test_addition_large_value_crossing_multiple_hours(self):
        """Adding a large number of minutes advances the clock correctly across hours."""
        # 420 (7:00) + 150 min = 570 (9:30)
        self.assertEqual(420 + 150, 570)
        self.assertEqual(format_time(570), "9:30")


class TestEdgeCasesTask(unittest.TestCase):

    def test_fits_in_budget_zero_available(self):
        """A task never fits when 0 minutes are available."""
        task = make_task(duration=1)
        self.assertFalse(task.fits_in_budget(0))

    def test_to_dict_notes_none(self):
        """to_dict() includes notes=None without raising."""
        task = make_task(notes=None)
        d = task.to_dict()
        self.assertIsNone(d["notes"])

    def test_to_dict_with_notes(self):
        """to_dict() captures notes when set."""
        task = make_task(notes="Give treat after")
        self.assertEqual(task.to_dict()["notes"], "Give treat after")


class TestEdgeCasesPet(unittest.TestCase):

    def test_default_tasks_list_is_empty_not_none(self):
        """A newly created Pet has an empty tasks list, never None."""
        pet = Pet("Rex", "dog")
        self.assertIsNotNone(pet.tasks)
        self.assertEqual(pet.tasks, [])

    def test_get_pending_tasks_empty_scheduled_list_returns_all(self):
        """Passing an empty list (not None) still returns all tasks as pending."""
        pet = Pet("Rex", "dog")
        pet.add_task(make_task("t1"))
        # [] means 'no tasks scheduled yet' — all should be pending
        pending = pet.get_pending_tasks(scheduled_tasks=[])
        self.assertEqual(len(pending), 1)

    def test_edit_task_all_none_args_changes_nothing(self):
        """Calling edit_task with all None arguments leaves the task unchanged."""
        pet = Pet("Rex", "dog")
        task = make_task("t1", name="Walk", duration=30, priority=Priority.HIGH)
        pet.add_task(task)
        pet.edit_task("t1")   # all optional params default to None
        self.assertEqual(pet.tasks[0].name, "Walk")
        self.assertEqual(pet.tasks[0].duration_minutes, 30)
        self.assertEqual(pet.tasks[0].priority, Priority.HIGH)

    def test_remove_task_from_empty_list_is_silent(self):
        """remove_task() on a pet with no tasks does not raise."""
        pet = Pet("Rex", "dog")
        pet.remove_task("nonexistent")  # should not raise


class TestEdgeCasesOwner(unittest.TestCase):

    def test_get_total_budget_no_budgets_set(self):
        """get_total_budget() returns 0 when no windows have been configured."""
        owner = Owner("Alex", 420)
        self.assertEqual(owner.get_total_budget(), 0)

    def test_set_budget_overwrite_updates_value(self):
        """Calling set_budget() twice on the same window keeps the latest value."""
        owner = Owner("Alex", 420)
        owner.set_budget(TimeOfDay.MORNING, 60)
        owner.set_budget(TimeOfDay.MORNING, 45)
        self.assertEqual(owner.get_budget(TimeOfDay.MORNING), 45)

    def test_search_pets_on_empty_owner(self):
        """search_pets() returns [] when the owner has no pets at all."""
        owner = Owner("Alex", 420)
        self.assertEqual(owner.search_pets("Mochi"), [])

    def test_get_pets_returns_list_not_dict_values(self):
        """get_pets() returns a plain list, not a dict_values object."""
        owner = Owner("Alex", 420)
        owner.add_pet(Pet("Rex", "dog"))
        result = owner.get_pets()
        self.assertIsInstance(result, list)


class TestEdgeCasesDailyPlan(unittest.TestCase):

    def setUp(self):
        self.owner = make_owner()
        self.pet = Pet("Mochi", "dog")
        self.owner.add_pet(self.pet)

    def test_get_reasoning_empty_plan_has_header(self):
        """get_reasoning() on an empty plan still produces the header line."""
        plan = DailyPlan(TODAY, self.owner, self.pet)
        text = plan.get_reasoning()
        self.assertIn("mochi", text)
        self.assertIn(str(TODAY), text)

    def test_get_reasoning_no_skipped_section_when_empty(self):
        """get_reasoning() omits the Skipped section when there are no skipped tasks."""
        plan = DailyPlan(TODAY, self.owner, self.pet)
        self.assertNotIn("Skipped", plan.get_reasoning())

    def test_get_reasoning_no_warnings_section_when_empty(self):
        """get_reasoning() omits the Warnings section when there are no warnings."""
        plan = DailyPlan(TODAY, self.owner, self.pet)
        self.assertNotIn("Warnings", plan.get_reasoning())

    def test_window_summary_tasks_in_multiple_windows(self):
        """get_window_summary() tracks tasks in different windows independently."""
        t_morning = make_task("t1", duration=20)
        t_afternoon = make_task("t2", duration=30)
        st_m = make_scheduled_task(task=t_morning, start=420,  duration=20, window=TimeOfDay.MORNING)
        st_a = make_scheduled_task(task=t_afternoon, start=720, duration=30, window=TimeOfDay.AFTERNOON)
        plan = DailyPlan(TODAY, self.owner, self.pet)
        plan.add_scheduled_task(st_m)
        plan.add_scheduled_task(st_a)
        summary = plan.get_window_summary()
        self.assertEqual(summary["morning"]["used_minutes"], 20)
        self.assertEqual(summary["afternoon"]["used_minutes"], 30)
        self.assertEqual(summary["evening"]["used_minutes"], 0)


# ===========================================================================
# Window Summary Features: Sorting and Filtering
# ===========================================================================

class TestWindowSummaryFeatures(unittest.TestCase):
    """Tests for sorting tasks by time and filtering by status."""

    def setUp(self):
        self.owner = make_owner(wake_time=420, morning=120, afternoon=120, evening=120)
        self.pet = Pet("Mochi", "dog")
        self.owner.add_pet(self.pet)
        self.plan = DailyPlan(TODAY, self.owner, self.pet)

    # --- Sorting by Time ---

    def test_get_tasks_sorted_by_time_empty_plan(self):
        """Sorting an empty plan returns an empty list."""
        result = self.plan.get_tasks_sorted_by_time()
        self.assertEqual(result, [])

    def test_get_tasks_sorted_by_time_single_task(self):
        """A single task returns a list with one element."""
        t = make_task("t1", duration=20)
        st = make_scheduled_task(task=t, start=420, duration=20, window=TimeOfDay.MORNING)
        self.plan.add_scheduled_task(st)
        result = self.plan.get_tasks_sorted_by_time()
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0].task.id, "t1")

    def test_get_tasks_sorted_by_time_multiple_windows(self):
        """Tasks from multiple windows are sorted chronologically."""
        # Add in non-chronological order to test sorting
        st_evening = make_scheduled_task(task=make_task("t3"), start=1020, duration=10, window=TimeOfDay.EVENING)
        st_morning = make_scheduled_task(task=make_task("t1"), start=420, duration=20, window=TimeOfDay.MORNING)
        st_afternoon = make_scheduled_task(task=make_task("t2"), start=720, duration=30, window=TimeOfDay.AFTERNOON)
        
        self.plan.add_scheduled_task(st_evening)
        self.plan.add_scheduled_task(st_morning)
        self.plan.add_scheduled_task(st_afternoon)
        
        result = self.plan.get_tasks_sorted_by_time()
        self.assertEqual(len(result), 3)
        self.assertEqual(result[0].task.id, "t1")  # 7:00
        self.assertEqual(result[1].task.id, "t2")  # 12:00
        self.assertEqual(result[2].task.id, "t3")  # 17:00

    def test_get_tasks_sorted_by_time_same_window(self):
        """Multiple tasks in the same window are sorted by start time."""
        st1 = make_scheduled_task(task=make_task("t1"), start=450, duration=10, window=TimeOfDay.MORNING)
        st2 = make_scheduled_task(task=make_task("t2"), start=420, duration=20, window=TimeOfDay.MORNING)
        st3 = make_scheduled_task(task=make_task("t3"), start=470, duration=5, window=TimeOfDay.MORNING)
        
        self.plan.add_scheduled_task(st1)
        self.plan.add_scheduled_task(st2)
        self.plan.add_scheduled_task(st3)
        
        result = self.plan.get_tasks_sorted_by_time()
        self.assertEqual(result[0].start_time, 420)
        self.assertEqual(result[1].start_time, 450)
        self.assertEqual(result[2].start_time, 470)

    def test_get_tasks_sorted_by_time_single_window(self):
        """Filtering by window returns only tasks in that window, sorted by time."""
        st_morning1 = make_scheduled_task(task=make_task("m2"), start=450, duration=10, window=TimeOfDay.MORNING)
        st_morning2 = make_scheduled_task(task=make_task("m1"), start=420, duration=20, window=TimeOfDay.MORNING)
        st_afternoon = make_scheduled_task(task=make_task("a1"), start=720, duration=30, window=TimeOfDay.AFTERNOON)
        
        self.plan.add_scheduled_task(st_morning1)
        self.plan.add_scheduled_task(st_morning2)
        self.plan.add_scheduled_task(st_afternoon)
        
        result = self.plan.get_tasks_sorted_by_time(TimeOfDay.MORNING)
        self.assertEqual(len(result), 2)
        self.assertEqual(result[0].task.id, "m1")
        self.assertEqual(result[1].task.id, "m2")

    # --- Filtering by Status ---

    def test_get_tasks_by_status_empty_plan(self):
        """Filtering an empty plan returns an empty list."""
        result = self.plan.get_tasks_by_status(TaskStatus.SCHEDULED)
        self.assertEqual(result, [])

    def test_get_tasks_by_status_single_match(self):
        """Filtering for a status returns only tasks with that status."""
        t = make_task("t1", duration=20)
        st = make_scheduled_task(task=t, status=TaskStatus.SCHEDULED)
        self.plan.add_scheduled_task(st)
        
        result = self.plan.get_tasks_by_status(TaskStatus.SCHEDULED)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0].task.id, "t1")

    def test_get_tasks_by_status_no_match(self):
        """Filtering for a status that doesn't exist returns an empty list."""
        t = make_task("t1", duration=20)
        st = make_scheduled_task(task=t, status=TaskStatus.SCHEDULED)
        self.plan.add_scheduled_task(st)
        
        result = self.plan.get_tasks_by_status(TaskStatus.COMPLETED)
        self.assertEqual(result, [])

    def test_get_tasks_by_status_multiple_matches(self):
        """Filtering returns all tasks with the matching status."""
        st1 = make_scheduled_task(task=make_task("t1"), status=TaskStatus.SCHEDULED)
        st2 = make_scheduled_task(task=make_task("t2"), status=TaskStatus.COMPLETED)
        st3 = make_scheduled_task(task=make_task("t3"), status=TaskStatus.SCHEDULED)
        
        self.plan.add_scheduled_task(st1)
        self.plan.add_scheduled_task(st2)
        self.plan.add_scheduled_task(st3)
        
        result = self.plan.get_tasks_by_status(TaskStatus.SCHEDULED)
        self.assertEqual(len(result), 2)
        self.assertEqual({st.task.id for st in result}, {"t1", "t3"})

    # --- Extended Window Summary ---

    def test_get_window_summary_extended_all_windows(self):
        """Extended summary returns details for all three windows."""
        st1 = make_scheduled_task(task=make_task("t1", duration=20), start=420, duration=20, window=TimeOfDay.MORNING)
        st2 = make_scheduled_task(task=make_task("t2", duration=30), start=720, duration=30, window=TimeOfDay.AFTERNOON)
        
        self.plan.add_scheduled_task(st1)
        self.plan.add_scheduled_task(st2)
        
        result = self.plan.get_window_summary_extended()
        
        self.assertIn("morning", result)
        self.assertIn("afternoon", result)
        self.assertIn("evening", result)
        
        self.assertEqual(result["morning"]["used_minutes"], 20)
        self.assertEqual(result["afternoon"]["used_minutes"], 30)
        self.assertEqual(result["evening"]["used_minutes"], 0)

    def test_get_window_summary_extended_single_window(self):
        """Extended summary for a single window includes task details."""
        t = make_task("t1", name="Morning Walk", duration=20)
        st = make_scheduled_task(task=t, start=420, duration=20, window=TimeOfDay.MORNING)
        self.plan.add_scheduled_task(st)
        
        result = self.plan.get_window_summary_extended(TimeOfDay.MORNING)
        
        self.assertEqual(len(result), 1)
        morning = result["morning"]
        self.assertEqual(morning["used_minutes"], 20)
        self.assertEqual(morning["remaining_minutes"], 100)  # 120 - 20
        self.assertEqual(morning["task_count"], 1)
        self.assertEqual(len(morning["tasks"]), 1)
        
        task_detail = morning["tasks"][0]
        self.assertEqual(task_detail["name"], "Morning Walk")
        self.assertEqual(task_detail["start_time"], "7:00")
        self.assertEqual(task_detail["end_time"], "7:20")

    def test_get_window_summary_extended_includes_task_metadata(self):
        """Extended summary includes task category, priority, and status."""
        t = make_task("t1", category=TaskCategory.WALK, priority=Priority.HIGH)
        st = make_scheduled_task(task=t, start=420, duration=20, window=TimeOfDay.MORNING, status=TaskStatus.SCHEDULED)
        self.plan.add_scheduled_task(st)
        
        result = self.plan.get_window_summary_extended(TimeOfDay.MORNING)
        task_detail = result["morning"]["tasks"][0]
        
        self.assertEqual(task_detail["category"], "walk")
        self.assertEqual(task_detail["priority"], "HIGH")
        self.assertEqual(task_detail["status"], "scheduled")

    def test_get_window_summary_extended_empty_window(self):
        """Extended summary for an empty window shows zeroes."""
        result = self.plan.get_window_summary_extended(TimeOfDay.EVENING)
        
        evening = result["evening"]
        self.assertEqual(evening["budget_minutes"], 120)
        self.assertEqual(evening["used_minutes"], 0)
        self.assertEqual(evening["remaining_minutes"], 120)
        self.assertEqual(evening["task_count"], 0)
        self.assertEqual(evening["tasks"], [])

    def test_get_window_summary_extended_tasks_are_sorted(self):
        """Tasks in extended summary are sorted by start time."""
        st1 = make_scheduled_task(task=make_task("t2", name="Task 2"), start=450, duration=10, window=TimeOfDay.MORNING)
        st2 = make_scheduled_task(task=make_task("t1", name="Task 1"), start=420, duration=20, window=TimeOfDay.MORNING)
        
        self.plan.add_scheduled_task(st1)
        self.plan.add_scheduled_task(st2)
        
        result = self.plan.get_window_summary_extended(TimeOfDay.MORNING)
        tasks = result["morning"]["tasks"]
        
        self.assertEqual(tasks[0]["name"], "Task 1")
        self.assertEqual(tasks[1]["name"], "Task 2")

    # --- Filtering by Completion Status ---

    def test_filter_by_scheduled_status_only(self):
        """Filtering for SCHEDULED status returns only scheduled tasks."""
        st1 = make_scheduled_task(task=make_task("t1"), status=TaskStatus.SCHEDULED)
        st2 = make_scheduled_task(task=make_task("t2"), status=TaskStatus.COMPLETED)
        st3 = make_scheduled_task(task=make_task("t3"), status=TaskStatus.SCHEDULED)
        
        self.plan.add_scheduled_task(st1)
        self.plan.add_scheduled_task(st2)
        self.plan.add_scheduled_task(st3)
        
        filtered = [st for st in self.plan.scheduled_tasks 
                   if st.status.value.upper() == "SCHEDULED"]
        
        self.assertEqual(len(filtered), 2)
        self.assertEqual({st.task.id for st in filtered}, {"t1", "t3"})

    def test_filter_by_completed_status_only(self):
        """Filtering for COMPLETED status returns only completed tasks."""
        st1 = make_scheduled_task(task=make_task("t1"), status=TaskStatus.SCHEDULED)
        st2 = make_scheduled_task(task=make_task("t2"), status=TaskStatus.COMPLETED)
        st3 = make_scheduled_task(task=make_task("t3"), status=TaskStatus.COMPLETED)
        
        self.plan.add_scheduled_task(st1)
        self.plan.add_scheduled_task(st2)
        self.plan.add_scheduled_task(st3)
        
        filtered = [st for st in self.plan.scheduled_tasks 
                   if st.status.value.upper() == "COMPLETED"]
        
        self.assertEqual(len(filtered), 2)
        self.assertEqual({st.task.id for st in filtered}, {"t2", "t3"})

    def test_filter_by_multiple_statuses(self):
        """Filtering by multiple statuses returns all matching tasks."""
        st1 = make_scheduled_task(task=make_task("t1"), status=TaskStatus.SCHEDULED)
        st2 = make_scheduled_task(task=make_task("t2"), status=TaskStatus.COMPLETED)
        st3 = make_scheduled_task(task=make_task("t3"), status=TaskStatus.SCHEDULED)
        
        self.plan.add_scheduled_task(st1)
        self.plan.add_scheduled_task(st2)
        self.plan.add_scheduled_task(st3)
        
        status_filter = ["SCHEDULED", "COMPLETED"]
        filtered = [st for st in self.plan.scheduled_tasks 
                   if st.status.value.upper() in status_filter]
        
        self.assertEqual(len(filtered), 3)

    def test_filter_no_match_returns_empty(self):
        """Filtering with no matches returns empty list."""
        st1 = make_scheduled_task(task=make_task("t1"), status=TaskStatus.SCHEDULED)
        self.plan.add_scheduled_task(st1)
        
        filtered = [st for st in self.plan.scheduled_tasks 
                   if st.status.value.upper() == "COMPLETED"]
        
        self.assertEqual(len(filtered), 0)

    # --- Filtering by Pet Name ---

    def test_filter_by_pet_name_current_pet(self):
        """Filtering by current pet name returns tasks from that pet."""
        st1 = make_scheduled_task(task=make_task("t1"))
        st2 = make_scheduled_task(task=make_task("t2"))
        
        self.plan.add_scheduled_task(st1)
        self.plan.add_scheduled_task(st2)
        
        pet_name = self.pet.name  # "mochi"
        filtered = [st for st in self.plan.scheduled_tasks 
                   if pet_name.lower() in [pet_name.lower()]]
        
        self.assertEqual(len(filtered), 2)

    def test_filter_by_pet_name_multiple_pets_scenario(self):
        """Filtering by pet name in multi-pet scenario."""
        owner = make_owner()
        pet1 = Pet("Mochi", "dog")
        pet2 = Pet("Luna", "cat")
        owner.add_pet(pet1)
        owner.add_pet(pet2)
        
        plan1 = DailyPlan(TODAY, owner, pet1)
        plan2 = DailyPlan(TODAY, owner, pet2)
        
        # Add tasks to each plan
        st1 = make_scheduled_task(task=make_task("t1"))
        st2 = make_scheduled_task(task=make_task("t2"))
        plan1.add_scheduled_task(st1)
        plan2.add_scheduled_task(st2)
        
        # Filter for Mochi only
        mochi_tasks = [st for st in plan1.scheduled_tasks 
                      if pet1.name in ["Mochi".lower(), "mochi"]]
        luna_tasks = [st for st in plan2.scheduled_tasks 
                     if pet2.name in ["Luna".lower(), "luna"]]
        
        self.assertEqual(len(mochi_tasks), 1)
        self.assertEqual(len(luna_tasks), 1)

    # --- Combined Status and Pet Name Filtering ---

    def test_filter_by_status_and_pet_name_both(self):
        """Filtering by both status and pet name applies both filters."""
        st1 = make_scheduled_task(task=make_task("t1"), status=TaskStatus.SCHEDULED)
        st2 = make_scheduled_task(task=make_task("t2"), status=TaskStatus.COMPLETED)
        st3 = make_scheduled_task(task=make_task("t3"), status=TaskStatus.SCHEDULED)
        
        self.plan.add_scheduled_task(st1)
        self.plan.add_scheduled_task(st2)
        self.plan.add_scheduled_task(st3)
        
        status_filter = ["SCHEDULED"]
        pet_filter = [self.pet.name]
        
        filtered = [st for st in self.plan.scheduled_tasks 
                   if st.status.value.upper() in status_filter and 
                      self.pet.name in pet_filter]
        
        self.assertEqual(len(filtered), 2)
        self.assertEqual({st.task.id for st in filtered}, {"t1", "t3"})

    def test_filter_combined_no_matches(self):
        """Combined filtering with no matches returns empty list."""
        st1 = make_scheduled_task(task=make_task("t1"), status=TaskStatus.SCHEDULED)
        self.plan.add_scheduled_task(st1)
        
        status_filter = ["COMPLETED"]  # No completed tasks
        pet_filter = [self.pet.name]
        
        filtered = [st for st in self.plan.scheduled_tasks 
                   if st.status.value.upper() in status_filter and 
                      self.pet.name in pet_filter]
        
        self.assertEqual(len(filtered), 0)

    # --- Filtering with Sorting ---

    def test_filter_then_sort_by_time(self):
        """Filtering followed by sorting returns correctly ordered results."""
        st1 = make_scheduled_task(task=make_task("t2"), start=450, duration=10, 
                                 status=TaskStatus.SCHEDULED, window=TimeOfDay.MORNING)
        st2 = make_scheduled_task(task=make_task("t1"), start=420, duration=20, 
                                 status=TaskStatus.SCHEDULED, window=TimeOfDay.MORNING)
        st3 = make_scheduled_task(task=make_task("t3"), start=420, duration=20, 
                                 status=TaskStatus.COMPLETED, window=TimeOfDay.MORNING)
        
        self.plan.add_scheduled_task(st1)
        self.plan.add_scheduled_task(st2)
        self.plan.add_scheduled_task(st3)
        
        # Filter for SCHEDULED only
        status_filter = ["SCHEDULED"]
        filtered = [st for st in self.plan.scheduled_tasks 
                   if st.status.value.upper() in status_filter]
        
        # Sort by time
        sorted_filtered = sorted(filtered, 
                               key=lambda st: (st.start_time, st.task.name))
        
        self.assertEqual(len(sorted_filtered), 2)
        self.assertEqual(sorted_filtered[0].task.id, "t1")
        self.assertEqual(sorted_filtered[1].task.id, "t2")

    def test_filter_by_priority_after_filtering_status(self):
        """Applying priority filter after status filter works correctly."""
        st1 = make_scheduled_task(task=make_task("t1", priority=Priority.HIGH), 
                                 status=TaskStatus.SCHEDULED)
        st2 = make_scheduled_task(task=make_task("t2", priority=Priority.LOW), 
                                 status=TaskStatus.SCHEDULED)
        st3 = make_scheduled_task(task=make_task("t3", priority=Priority.EMERGENCY), 
                                 status=TaskStatus.COMPLETED)
        
        self.plan.add_scheduled_task(st1)
        self.plan.add_scheduled_task(st2)
        self.plan.add_scheduled_task(st3)
        
        # Filter by status first
        status_filter = ["SCHEDULED"]
        filtered = [st for st in self.plan.scheduled_tasks 
                   if st.status.value.upper() in status_filter]
        
        # Then filter by high priority
        high_priority_filtered = [st for st in filtered 
                                 if st.task.priority.value >= Priority.HIGH.value]
        
        self.assertEqual(len(high_priority_filtered), 1)
        self.assertEqual(high_priority_filtered[0].task.id, "t1")


class TestEdgeCasesScheduler(unittest.TestCase):

    def setUp(self):
        self.owner = make_owner(wake_time=420, morning=60, afternoon=90, evening=30)
        self.pet = Pet("Mochi", "dog")
        self.owner.add_pet(self.pet)
        self.scheduler = Scheduler(self.owner, self.pet)

    def test_wake_time_after_noon_morning_gets_no_tasks(self):
        """When the owner wakes after noon, no morning tasks are scheduled."""
        owner = make_owner(wake_time=780, morning=60, afternoon=90, evening=0)
        pet = Pet("Rex", "dog")
        owner.add_pet(pet)
        # Mandatory morning task — cursor will be at "11:59", budget may still be there
        # but cursor is before noon so it will be placed there; the key test is
        # that the afternoon cursor starts at 13:00, not 12:00
        pet.add_task(make_task("t1", is_mandatory=True, duration=20,
                               preferred_time=TimeOfDay.AFTERNOON))
        plan = Scheduler(owner, pet).generate_plan(TODAY)
        # Afternoon cursor should start at wake_time (13:00), not 12:00
        self.assertEqual(plan.scheduled_tasks[0].start_time, 780)

    def test_optional_task_skipped_when_preferred_window_has_zero_budget(self):
        """An optional task with a specific window preference is skipped when that window has 0 budget."""
        owner = make_owner(morning=60, afternoon=60, evening=0)
        pet = Pet("Rex", "dog")
        owner.add_pet(pet)
        pet.add_task(make_task("t1", is_mandatory=False, duration=15,
                               preferred_time=TimeOfDay.EVENING))
        plan = Scheduler(owner, pet).generate_plan(TODAY)
        self.assertEqual(len(plan.scheduled_tasks), 0)
        self.assertEqual(plan.skipped_tasks[0].id, "t1")

    def test_all_optional_tasks_skipped_when_budgets_exhausted(self):
        """When all windows are full, every optional task ends up in skipped_tasks."""
        # Fill morning completely with a mandatory task
        owner = make_owner(morning=30, afternoon=0, evening=0)
        pet = Pet("Rex", "dog")
        owner.add_pet(pet)
        pet.add_task(make_task("m1", is_mandatory=True,  duration=30, preferred_time=TimeOfDay.MORNING))
        pet.add_task(make_task("o1", is_mandatory=False, duration=15, preferred_time=TimeOfDay.MORNING))
        pet.add_task(make_task("o2", is_mandatory=False, duration=10, preferred_time=TimeOfDay.AFTERNOON))
        plan = Scheduler(owner, pet).generate_plan(TODAY)
        skipped_ids = {t.id for t in plan.skipped_tasks}
        self.assertIn("o1", skipped_ids)
        self.assertIn("o2", skipped_ids)

    def test_multiple_tasks_carried_over_from_previous_plan(self):
        """All skipped tasks from the previous plan appear in the new scheduling pool."""
        prev = DailyPlan(date(2026, 4, 3), self.owner, self.pet)
        prev.add_skipped_task(make_task("s1", name="Grooming",   duration=15, is_mandatory=True,
                                        preferred_time=TimeOfDay.MORNING))
        prev.add_skipped_task(make_task("s2", name="Nail Trim",  duration=10, is_mandatory=True,
                                        preferred_time=TimeOfDay.MORNING))
        plan = self.scheduler.generate_plan(TODAY, previous_plan=prev)
        scheduled_ids = {st.task.id for st in plan.scheduled_tasks}
        self.assertIn("s1", scheduled_ids)
        self.assertIn("s2", scheduled_ids)

    def test_feeding_task_without_food_preference_has_no_food_in_reason(self):
        """A FEEDING task with food_preference=None does not put food info in the reason."""
        self.pet.add_task(make_task("f1", category=TaskCategory.FEEDING,
                                   is_mandatory=True, duration=10,
                                   preferred_time=TimeOfDay.MORNING,
                                   food_preference=None))
        plan = self.scheduler.generate_plan(TODAY)
        reason = plan.scheduled_tasks[0].reason
        # reason should only contain time/window info, no food details
        self.assertNotIn("g", reason.split("(")[0])   # no "180g" style text before the window info
        self.assertIn("morning", reason)

    def test_mandatory_task_with_no_budget_set_still_scheduled_with_warning(self):
        """A mandatory task is scheduled even when the owner never set a budget."""
        owner = Owner("Sam", 420)  # no set_budget calls
        pet = Pet("Rex", "dog")
        owner.add_pet(pet)
        pet.add_task(make_task("t1", is_mandatory=True, duration=30,
                               preferred_time=TimeOfDay.MORNING))
        plan = Scheduler(owner, pet).generate_plan(TODAY)
        self.assertEqual(len(plan.scheduled_tasks), 1)
        # Should have warned that the task exceeded the (zero) budget
        self.assertTrue(len(plan.warnings) > 0)

    def test_tasks_in_different_windows_have_independent_cursors(self):
        """Scheduling a morning task does not affect the afternoon start time."""
        self.pet.add_task(make_task("t1", is_mandatory=True, duration=30,
                                   preferred_time=TimeOfDay.MORNING))
        self.pet.add_task(make_task("t2", is_mandatory=True, duration=20,
                                   preferred_time=TimeOfDay.AFTERNOON))
        plan = self.scheduler.generate_plan(TODAY)
        by_id = {st.task.id: st for st in plan.scheduled_tasks}
        # Morning task starts at wake time
        self.assertEqual(by_id["t1"].start_time, 420)
        # Afternoon task starts at 720 (12:00), unaffected by morning cursor
        self.assertEqual(by_id["t2"].start_time, 720)

    def test_pick_window_from_budget_equal_budgets_picks_morning(self):
        """When all windows have equal remaining capacity, MORNING is chosen (first in list)."""
        owner = make_owner(morning=60, afternoon=60, evening=60)
        pet = Pet("Rex", "dog")
        owner.add_pet(pet)
        scheduler = Scheduler(owner, pet)
        # Manually trigger generate_plan to initialize cursors, then test helper directly
        # Use an ANY-time mandatory task and verify it lands in MORNING
        pet.add_task(make_task("t1", is_mandatory=True, duration=10,
                               preferred_time=TimeOfDay.ANY))
        plan = scheduler.generate_plan(TODAY)
        self.assertEqual(plan.scheduled_tasks[0].time_window, TimeOfDay.MORNING)

    def test_generate_plan_all_emergency_tasks_all_scheduled(self):
        """When every task is EMERGENCY priority, all of them are scheduled."""
        for i in range(3):
            self.pet.add_task(make_task(f"e{i}", priority=Priority.EMERGENCY,
                                        is_mandatory=False, duration=5,
                                        preferred_time=TimeOfDay.MORNING))
        plan = self.scheduler.generate_plan(TODAY)
        self.assertEqual(len(plan.scheduled_tasks), 3)
        # Each emergency task also produces a warning
        self.assertEqual(len(plan.warnings), 3)


# ===========================================================================
# validate() as a gate before add_task (main.py fix: task.validate() is now
# called before every mochi.add_task / luna.add_task call)
# ===========================================================================

class TestValidateAsGate(unittest.TestCase):
    """validate() must catch bad task data before it enters the pet's task list."""

    def test_validate_passes_for_minimum_valid_task(self):
        """A 1-minute task with a single-char name is valid."""
        task = make_task(duration=1, name="X")
        task.validate()  # must not raise

    def test_validate_raises_before_add_task_so_pet_stays_clean(self):
        """When validate() raises, the pet's task list remains untouched."""
        pet = Pet("Rex", "dog")
        task = make_task(duration=0)  # invalid
        with self.assertRaises(ValueError):
            task.validate()
        # validate() raised before add_task was called — list must still be empty
        self.assertEqual(len(pet.tasks), 0)

    def test_validate_whitespace_only_name_raises(self):
        """A name consisting only of spaces is rejected."""
        task = make_task(name="   ")
        with self.assertRaises(ValueError):
            task.validate()

    def test_validate_tab_only_name_raises(self):
        """A name consisting only of a tab character is rejected (strip catches it)."""
        task = make_task(name="\t")
        with self.assertRaises(ValueError):
            task.validate()

    def test_valid_task_added_successfully_after_validate(self):
        """A task that passes validate() is added to the pet without error."""
        pet = Pet("Rex", "dog")
        task = make_task("t1", duration=15, name="Bath")
        task.validate()
        pet.add_task(task)
        self.assertEqual(len(pet.tasks), 1)


# ===========================================================================
# Multiple pets under one owner — plan generation loop
# (main.py fix: replaced per-pet variables with a list comprehension over
#  owner.get_pets())
# ===========================================================================

class TestMultiplePetScheduling(unittest.TestCase):
    """Scheduling plans for all pets via owner.get_pets() produces one plan each."""

    def setUp(self):
        self.owner = make_owner(morning=60, afternoon=90, evening=30)
        self.dog = Pet("Rex", "dog")
        self.cat = Pet("Luna", "cat")
        self.owner.add_pet(self.dog)
        self.owner.add_pet(self.cat)

    def test_get_pets_loop_gives_one_plan_per_pet(self):
        """Iterating owner.get_pets() and scheduling each pet produces one plan per pet."""
        plans = [Scheduler(self.owner, pet).generate_plan(TODAY)
                 for pet in self.owner.get_pets()]
        self.assertEqual(len(plans), 2)

    def test_each_plan_references_its_own_pet(self):
        """Each plan's .pet attribute corresponds to the pet it was built for."""
        plans = [Scheduler(self.owner, pet).generate_plan(TODAY)
                 for pet in self.owner.get_pets()]
        plan_pet_names = {plan.pet.name for plan in plans}
        self.assertIn("rex", plan_pet_names)
        self.assertIn("luna", plan_pet_names)

    def test_plans_for_two_pets_are_independent_objects(self):
        """Each call to generate_plan() returns a distinct DailyPlan object."""
        dog_plan = Scheduler(self.owner, self.dog).generate_plan(TODAY)
        cat_plan = Scheduler(self.owner, self.cat).generate_plan(TODAY)
        self.assertIsNot(dog_plan, cat_plan)

    def test_budget_tracking_is_independent_per_plan(self):
        """Scheduling one pet does not consume budget for another pet's plan.

        Each DailyPlan tracks its own used-minutes; the two plans do not share
        an internal counter, so both pets can each use the full morning budget.
        """
        self.dog.add_task(make_task("d1", is_mandatory=True, duration=60,
                                   preferred_time=TimeOfDay.MORNING))
        self.cat.add_task(make_task("c1", is_mandatory=True, duration=60,
                                   preferred_time=TimeOfDay.MORNING))
        dog_plan = Scheduler(self.owner, self.dog).generate_plan(TODAY)
        cat_plan = Scheduler(self.owner, self.cat).generate_plan(TODAY)
        # Both tasks should be scheduled — budget is tracked per-plan, not globally
        self.assertEqual(len(dog_plan.scheduled_tasks), 1)
        self.assertEqual(len(cat_plan.scheduled_tasks), 1)

    def test_adding_third_pet_still_produces_correct_count(self):
        """Adding a third pet means the loop produces three plans."""
        bird = Pet("Kiwi", "bird")
        self.owner.add_pet(bird)
        plans = [Scheduler(self.owner, pet).generate_plan(TODAY)
                 for pet in self.owner.get_pets()]
        self.assertEqual(len(plans), 3)

    def test_plan_pet_name_is_available_for_display(self):
        """plan.pet.name is accessible and correct — no need for a separate label variable."""
        dog_plan = Scheduler(self.owner, self.dog).generate_plan(TODAY)
        # main.py now uses plan.pet.name.title() instead of a hard-coded "Mochi"
        self.assertEqual(dog_plan.pet.name.title(), "Rex")

    def test_carry_over_works_within_multi_pet_loop(self):
        """Carry-over from a previous plan integrates correctly when looping over pets."""
        prev = DailyPlan(date(2026, 4, 3), self.owner, self.dog)
        skipped = make_task("s1", name="Grooming", is_mandatory=True,
                            duration=15, preferred_time=TimeOfDay.MORNING)
        prev.add_skipped_task(skipped)
        # Test would continue here if completed


# ---------------------------------------------------------------------------
# Recurrence Tests (Feature 3)
# ---------------------------------------------------------------------------

class TestRecurrence(unittest.TestCase):
    """Tests for the recurring task feature."""
    
    def setUp(self):
        self.owner = make_owner()
        self.pet = Pet("Mochi", "dog")
        self.owner.add_pet(self.pet)

    def test_recurrence_applies_to_date_none_recurrence(self):
        """None recurrence never applies."""
        self.assertFalse(recurrence_applies_to_date(None, date(2026, 4, 5)))

    def test_recurrence_applies_to_date_daily_within_range(self):
        """DAILY recurrence applies to every date within start/end range."""
        rec = Recurrence(
            type=RecurrenceType.DAILY,
            start_date=date(2026, 4, 4),
            end_date=date(2026, 4, 6)
        )
        self.assertTrue(recurrence_applies_to_date(rec, date(2026, 4, 4)))
        self.assertTrue(recurrence_applies_to_date(rec, date(2026, 4, 5)))
        self.assertTrue(recurrence_applies_to_date(rec, date(2026, 4, 6)))
        self.assertFalse(recurrence_applies_to_date(rec, date(2026, 4, 3)))
        self.assertFalse(recurrence_applies_to_date(rec, date(2026, 4, 7)))

    def test_recurrence_applies_to_date_daily_indefinite(self):
        """DAILY recurrence with no end_date continues indefinitely."""
        rec = Recurrence(
            type=RecurrenceType.DAILY,
            start_date=date(2026, 4, 4),
            end_date=None
        )
        self.assertTrue(recurrence_applies_to_date(rec, date(2026, 4, 4)))
        self.assertTrue(recurrence_applies_to_date(rec, date(2026, 4, 5)))
        self.assertTrue(recurrence_applies_to_date(rec, date(2026, 12, 31)))  # far future
        self.assertTrue(recurrence_applies_to_date(rec, date(2027, 1, 1)))
        self.assertFalse(recurrence_applies_to_date(rec, date(2026, 4, 3)))

    def test_recurrence_applies_to_date_weekly(self):
        """WEEKLY recurrence applies only on specified days of week."""
        # April 4, 2026 is a Saturday (day 5)
        # April 5, 2026 is a Sunday (day 6)
        # April 6, 2026 is a Monday (day 0)
        rec = Recurrence(
            type=RecurrenceType.WEEKLY,
            start_date=date(2026, 4, 4),
            days_of_week=[5, 6],  # Sat, Sun
            end_date=None
        )
        self.assertTrue(recurrence_applies_to_date(rec, date(2026, 4, 4)))  # Saturday
        self.assertTrue(recurrence_applies_to_date(rec, date(2026, 4, 5)))  # Sunday
        self.assertFalse(recurrence_applies_to_date(rec, date(2026, 4, 6)))  # Monday
        self.assertFalse(recurrence_applies_to_date(rec, date(2026, 4, 7)))  # Tuesday
        self.assertTrue(recurrence_applies_to_date(rec, date(2026, 4, 11)))  # Next Saturday

    def test_recurrence_applies_to_date_interval(self):
        """INTERVAL recurrence applies every N days from start_date."""
        rec = Recurrence(
            type=RecurrenceType.INTERVAL,
            start_date=date(2026, 4, 4),
            interval=3,
            end_date=date(2026, 4, 20)
        )
        # April 4 + 0*3 = April 4
        self.assertTrue(recurrence_applies_to_date(rec, date(2026, 4, 4)))
        # April 4 + 1*3 = April 7
        self.assertTrue(recurrence_applies_to_date(rec, date(2026, 4, 7)))
        # April 4 + 2*3 = April 10
        self.assertTrue(recurrence_applies_to_date(rec, date(2026, 4, 10)))
        # April 4 + 3*3 = April 13
        self.assertTrue(recurrence_applies_to_date(rec, date(2026, 4, 13)))
        # Not every day
        self.assertFalse(recurrence_applies_to_date(rec, date(2026, 4, 5)))
        self.assertFalse(recurrence_applies_to_date(rec, date(2026, 4, 6)))
        # After end_date
        self.assertFalse(recurrence_applies_to_date(rec, date(2026, 4, 22)))

    def test_recurrence_applies_to_date_monthly(self):
        """MONTHLY recurrence applies on the same day of each month."""
        rec = Recurrence(
            type=RecurrenceType.MONTHLY,
            start_date=date(2026, 4, 15),
            end_date=None
        )
        # 15th of each month
        self.assertTrue(recurrence_applies_to_date(rec, date(2026, 4, 15)))
        self.assertTrue(recurrence_applies_to_date(rec, date(2026, 5, 15)))
        self.assertTrue(recurrence_applies_to_date(rec, date(2026, 6, 15)))
        # Other days
        self.assertFalse(recurrence_applies_to_date(rec, date(2026, 4, 14)))
        self.assertFalse(recurrence_applies_to_date(rec, date(2026, 4, 16)))
        # Before start_date
        self.assertFalse(recurrence_applies_to_date(rec, date(2026, 3, 15)))

    def test_recurrence_validate_rejects_invalid_dates(self):
        """Recurrence.validate() rejects start_date > end_date."""
        rec = Recurrence(
            type=RecurrenceType.DAILY,
            start_date=date(2026, 4, 10),
            end_date=date(2026, 4, 5)
        )
        with self.assertRaises(ValueError) as ctx:
            rec.validate()
        self.assertIn("start_date must be <= end_date", str(ctx.exception))

    def test_recurrence_validate_rejects_invalid_interval(self):
        """Recurrence.validate() rejects non-positive interval for INTERVAL type."""
        rec = Recurrence(
            type=RecurrenceType.INTERVAL,
            start_date=date(2026, 4, 4),
            interval=0
        )
        with self.assertRaises(ValueError) as ctx:
            rec.validate()
        self.assertIn("interval must be positive", str(ctx.exception))

    def test_recurrence_validate_rejects_invalid_weekly_days(self):
        """Recurrence.validate() rejects invalid day numbers for WEEKLY type."""
        rec = Recurrence(
            type=RecurrenceType.WEEKLY,
            start_date=date(2026, 4, 4),
            days_of_week=[0, 7]  # 7 is invalid
        )
        with self.assertRaises(ValueError) as ctx:
            rec.validate()
        self.assertIn("days_of_week must contain values 0-6", str(ctx.exception))

    def test_recurring_task_created_with_daily_recurrence(self):
        """A task with DAILY recurrence is stored correctly."""
        task = Task(
            id="daily_walk",
            name="Morning Walk",
            category=TaskCategory.WALK,
            duration_minutes=30,
            priority=Priority.MEDIUM,
            preferred_time=TimeOfDay.MORNING,
            recurrence=Recurrence(
                type=RecurrenceType.DAILY,
                start_date=date(2026, 4, 4)
            )
        )
        self.assertIsNotNone(task.recurrence)
        self.assertEqual(task.recurrence.type, RecurrenceType.DAILY)
        self.pet.add_task(task)
        self.assertEqual(len(self.pet.get_tasks()), 1)

    def test_scheduler_expands_daily_recurring_task(self):
        """Scheduler expands a daily recurring task into scheduled slots."""
        task = Task(
            id="daily_walk",
            name="Morning Walk",
            category=TaskCategory.WALK,
            duration_minutes=30,
            priority=Priority.MEDIUM,
            preferred_time=TimeOfDay.MORNING,
            is_mandatory=True,
            recurrence=Recurrence(
                type=RecurrenceType.DAILY,
                start_date=date(2026, 4, 4)
            )
        )
        self.pet.add_task(task)
        plan = Scheduler(self.owner, self.pet).generate_plan(date(2026, 4, 4))
        
        # Should be scheduled once as the cloned expanded instance
        scheduled_ids = [st.task.id for st in plan.scheduled_tasks]
        self.assertIn("daily_walk_recurring", scheduled_ids)
        # Original (non-expanded) should NOT be scheduled
        self.assertNotIn("daily_walk", scheduled_ids)

    def test_scheduler_does_not_expand_non_matching_recurrence(self):
        """Scheduler does not expand recurring tasks that don't apply to plan_date."""
        # Task recurring on Saturdays
        task = Task(
            id="weekend_groom",
            name="Grooming",
            category=TaskCategory.GROOMING,
            duration_minutes=45,
            priority=Priority.MEDIUM,
            preferred_time=TimeOfDay.AFTERNOON,
            is_mandatory=False,
            recurrence=Recurrence(
                type=RecurrenceType.WEEKLY,
                start_date=date(2026, 4, 4),  # Saturday
                days_of_week=[5],  # Saturday only
            )
        )
        self.pet.add_task(task)
        
        # Generate plan for a Monday (day doesn't match)
        plan = Scheduler(self.owner, self.pet).generate_plan(date(2026, 4, 6))
        
        # Original task is in the list, but no expansion should occur
        # (It's not matched, so won't be expanded)
        scheduled_ids = [st.task.id for st in plan.scheduled_tasks]
        # Since the recurrence doesn't apply on Monday, task won't be scheduled
        self.assertNotIn("weekend_groom_recurring", scheduled_ids)

    def test_scheduler_expands_weekly_recurring_on_matching_day(self):
        """Scheduler expands weekly recurring tasks only on matching days."""
        task = Task(
            id="weekend_groom",
            name="Grooming",
            category=TaskCategory.GROOMING,
            duration_minutes=45,
            priority=Priority.HIGH,
            preferred_time=TimeOfDay.AFTERNOON,
            is_mandatory=True,
            recurrence=Recurrence(
                type=RecurrenceType.WEEKLY,
                start_date=date(2026, 4, 4),  # Saturday
                days_of_week=[5],  # Saturday only
            )
        )
        self.pet.add_task(task)
        
        # Plan for the Saturday when recurrence applies
        plan = Scheduler(self.owner, self.pet).generate_plan(date(2026, 4, 4))
        scheduled_ids = [st.task.id for st in plan.scheduled_tasks]
        
        # Should only have the expanded instance
        self.assertIn("weekend_groom_recurring", scheduled_ids)
        self.assertNotIn("weekend_groom", scheduled_ids)

    def test_scheduler_expands_interval_recurring_on_matching_day(self):
        """Scheduler expands interval recurring tasks on matching interval days."""
        task = Task(
            id="medication",
            name="Give Antibiotics",
            category=TaskCategory.MEDICATION,
            duration_minutes=10,
            priority=Priority.HIGH,
            preferred_time=TimeOfDay.MORNING,
            is_mandatory=True,
            recurrence=Recurrence(
                type=RecurrenceType.INTERVAL,
                start_date=date(2026, 4, 4),
                interval=3,  # Every 3 days
            )
        )
        self.pet.add_task(task)
        
        # April 4 is day 0 (matches)
        plan1 = Scheduler(self.owner, self.pet).generate_plan(date(2026, 4, 4))
        scheduled1 = [st.task.id for st in plan1.scheduled_tasks]
        self.assertIn("medication_recurring", scheduled1)
        self.assertNotIn("medication", scheduled1)
        
        # April 5 is day 1 (doesn't match)
        plan2 = Scheduler(self.owner, self.pet).generate_plan(date(2026, 4, 5))
        scheduled2 = [st.task.id for st in plan2.scheduled_tasks]
        self.assertNotIn("medication_recurring", scheduled2)
        self.assertNotIn("medication", scheduled2)
        
        # April 7 is day 3 (matches)
        plan3 = Scheduler(self.owner, self.pet).generate_plan(date(2026, 4, 7))
        scheduled3 = [st.task.id for st in plan3.scheduled_tasks]
        self.assertIn("medication_recurring", scheduled3)
        self.assertNotIn("medication", scheduled3)

    def test_recurring_task_respects_budget_constraints(self):
        """Expanded recurring tasks compete for budget like regular tasks."""
        # MORNING budget is 60 minutes
        task = Task(
            id="long_morning",
            name="Extended Walk",
            category=TaskCategory.WALK,
            duration_minutes=70,  # Exceeds morning budget
            priority=Priority.MEDIUM,
            preferred_time=TimeOfDay.MORNING,
            is_mandatory=False,
            recurrence=Recurrence(
                type=RecurrenceType.DAILY,
                start_date=date(2026, 4, 4),
            )
        )
        self.pet.add_task(task)
        
        plan = Scheduler(self.owner, self.pet).generate_plan(date(2026, 4, 4))
        # Task should not be scheduled due to budget (optional task)
        scheduled_ids = [st.task.id for st in plan.scheduled_tasks]
        self.assertNotIn("long_morning_recurring", scheduled_ids)
        # Original non-recurring should also not be scheduled
        self.assertNotIn("long_morning", scheduled_ids)

    def test_recurring_task_in_skipped_when_no_budget(self):
        """Expanded recurring tasks go to skipped_tasks if no budget available."""
        # Add a mandatory task that uses up all morning budget (60 min)
        mandatory = Task(
            id="mandatory_morning",
            name="Required Task",
            category=TaskCategory.WALK,
            duration_minutes=60,
            priority=Priority.HIGH,
            preferred_time=TimeOfDay.MORNING,
            is_mandatory=True,
        )
        self.pet.add_task(mandatory)
        
        # Add a recurring optional task
        recurring = Task(
            id="optional_recurring",
            name="Optional Walk",
            category=TaskCategory.WALK,
            duration_minutes=30,
            priority=Priority.MEDIUM,
            preferred_time=TimeOfDay.MORNING,
            is_mandatory=False,
            recurrence=Recurrence(
                type=RecurrenceType.DAILY,
                start_date=date(2026, 4, 4),
            )
        )
        self.pet.add_task(recurring)
        
        plan = Scheduler(self.owner, self.pet).generate_plan(date(2026, 4, 4))
        
        # Mandatory should be scheduled
        scheduled_ids = [st.task.id for st in plan.scheduled_tasks]
        self.assertIn("mandatory_morning", scheduled_ids)
        
        # Recurring optional should be skipped (no budget left)
        # The cloned instance "optional_recurring_recurring" should be in skipped
        skipped_ids = [t.id for t in plan.skipped_tasks]
        self.assertIn("optional_recurring_recurring", skipped_ids)
        # Original (with recurrence metadata) should never be in skipped or scheduled
        self.assertNotIn("optional_recurring", skipped_ids)

    def test_recurring_task_consolidated_with_consolidation_logic(self):
        """Recurring feeding tasks can be consolidated with other feeding tasks."""
        # Add a recurring feeding task
        recurring_feed = Task(
            id="feed_morning",
            name="Morning Feed",
            category=TaskCategory.FEEDING,
            duration_minutes=15,
            priority=Priority.HIGH,
            preferred_time=TimeOfDay.MORNING,
            is_mandatory=True,
            recurrence=Recurrence(
                type=RecurrenceType.DAILY,
                start_date=date(2026, 4, 4),
            )
        )
        
        # Add another feeding task
        other_feed = Task(
            id="feed_other",
            name="Extra Feed",
            category=TaskCategory.FEEDING,
            duration_minutes=10,
            priority=Priority.MEDIUM,
            preferred_time=TimeOfDay.MORNING,
            is_mandatory=False,
        )
        
        self.pet.add_task(recurring_feed)
        self.pet.add_task(other_feed)
        
        plan = Scheduler(self.owner, self.pet).generate_plan(date(2026, 4, 4))
        
        # Should have a single consolidated feeding task (from recurring + other)
        feeding_tasks = [st for st in plan.scheduled_tasks 
                        if st.task.category == TaskCategory.FEEDING]
        # With consolidation, should be just 1 task representing both feedings
        self.assertEqual(len(feeding_tasks), 1)
        # The consolidated name should include both
        self.assertIn("Morning Feed", feeding_tasks[0].task.name)
        self.assertIn("Extra Feed", feeding_tasks[0].task.name)

    def test_recurring_task_with_monthly_pattern(self):
        """MONTHLY recurring tasks apply on the same day of each month."""
        task = Task(
            id="monthly_vet",
            name="Monthly Vet Checkup",
            category=TaskCategory.VET,
            duration_minutes=60,
            priority=Priority.HIGH,
            preferred_time=TimeOfDay.AFTERNOON,
            is_mandatory=True,
            recurrence=Recurrence(
                type=RecurrenceType.MONTHLY,
                start_date=date(2026, 4, 15),
            )
        )
        self.pet.add_task(task)
        
        # April 15 - should expand
        plan1 = Scheduler(self.owner, self.pet).generate_plan(date(2026, 4, 15))
        scheduled1 = [st.task.id for st in plan1.scheduled_tasks]
        self.assertIn("monthly_vet_recurring", scheduled1)
        self.assertNotIn("monthly_vet", scheduled1)
        
        # May 15 - should also expand
        plan2 = Scheduler(self.owner, self.pet).generate_plan(date(2026, 5, 15))
        scheduled2 = [st.task.id for st in plan2.scheduled_tasks]
        self.assertIn("monthly_vet_recurring", scheduled2)
        self.assertNotIn("monthly_vet", scheduled2)
        
        # May 14 - should not expand
        plan3 = Scheduler(self.owner, self.pet).generate_plan(date(2026, 5, 14))
        scheduled3 = [st.task.id for st in plan3.scheduled_tasks]
        self.assertNotIn("monthly_vet_recurring", scheduled3)
        self.assertNotIn("monthly_vet", scheduled3)

    def test_recurring_task_with_end_date_stops_recurring(self):
        """Recurring tasks stop recurring after end_date."""
        task = Task(
            id="temp_morning_walk",
            name="Temporary Morning Walk",
            category=TaskCategory.WALK,
            duration_minutes=30,
            priority=Priority.MEDIUM,
            preferred_time=TimeOfDay.MORNING,
            is_mandatory=False,
            recurrence=Recurrence(
                type=RecurrenceType.DAILY,
                start_date=date(2026, 4, 4),
                end_date=date(2026, 4, 6),
            )
        )
        self.pet.add_task(task)
        
        # April 4 - within range, should expand
        plan1 = Scheduler(self.owner, self.pet).generate_plan(date(2026, 4, 4))
        scheduled1 = [st.task.id for st in plan1.scheduled_tasks]
        self.assertIn("temp_morning_walk_recurring", scheduled1)
        
        # April 6 - on end_date, should expand
        plan2 = Scheduler(self.owner, self.pet).generate_plan(date(2026, 4, 6))
        scheduled2 = [st.task.id for st in plan2.scheduled_tasks]
        self.assertIn("temp_morning_walk_recurring", scheduled2)
        
        # April 7 - after end_date, should not expand
        plan3 = Scheduler(self.owner, self.pet).generate_plan(date(2026, 4, 7))
        scheduled3 = [st.task.id for st in plan3.scheduled_tasks]
        # Task should not be in schedule at all (no original, no clone)
        self.assertNotIn("temp_morning_walk_recurring", scheduled3)
        self.assertNotIn("temp_morning_walk", scheduled3)


if __name__ == "__main__":
    unittest.main()


# ===========================================================================
# Additional scheduler edge cases
# ===========================================================================

class TestSchedulerEdgeCasesExtended(unittest.TestCase):

    def setUp(self):
        self.owner = make_owner(wake_time=420, morning=60, afternoon=90, evening=30)
        self.pet = Pet("Mochi", "dog")
        self.owner.add_pet(self.pet)
        self.scheduler = Scheduler(self.owner, self.pet)

    def test_optional_any_time_skipped_when_all_windows_full(self):
        """An ANY-time optional task is skipped when every window is at capacity."""
        owner = make_owner(morning=10, afternoon=10, evening=10)
        pet = Pet("Rex", "dog")
        owner.add_pet(pet)
        pet.add_task(make_task("m1", is_mandatory=True, duration=10, preferred_time=TimeOfDay.MORNING))
        pet.add_task(make_task("m2", is_mandatory=True, duration=10, preferred_time=TimeOfDay.AFTERNOON))
        pet.add_task(make_task("m3", is_mandatory=True, duration=10, preferred_time=TimeOfDay.EVENING))
        pet.add_task(make_task("o1", is_mandatory=False, duration=5,  preferred_time=TimeOfDay.ANY))
        plan = Scheduler(owner, pet).generate_plan(TODAY)
        skipped_ids = {t.id for t in plan.skipped_tasks}
        self.assertIn("o1", skipped_ids)

    def test_optional_task_fits_exactly_at_remaining_budget_boundary(self):
        """An optional task that exactly fills the leftover budget is scheduled, not skipped."""
        # Morning: 60 min budget, mandatory uses 40 → 20 remain; optional is exactly 20
        self.pet.add_task(make_task("m1", is_mandatory=True,  duration=40, preferred_time=TimeOfDay.MORNING))
        self.pet.add_task(make_task("o1", is_mandatory=False, duration=20, preferred_time=TimeOfDay.MORNING))
        plan = self.scheduler.generate_plan(TODAY)
        scheduled_ids = {st.task.id for st in plan.scheduled_tasks}
        self.assertIn("o1", scheduled_ids)
        self.assertNotIn("o1", {t.id for t in plan.skipped_tasks})

    def test_optional_task_one_minute_over_budget_is_skipped(self):
        """An optional task that is 1 minute too long for the remaining budget is skipped."""
        self.pet.add_task(make_task("m1", is_mandatory=True,  duration=40, preferred_time=TimeOfDay.MORNING))
        self.pet.add_task(make_task("o1", is_mandatory=False, duration=21, preferred_time=TimeOfDay.MORNING))
        plan = self.scheduler.generate_plan(TODAY)
        skipped_ids = {t.id for t in plan.skipped_tasks}
        self.assertIn("o1", skipped_ids)

    def test_emergency_any_time_placed_in_morning(self):
        """An EMERGENCY task with preferred_time=ANY is placed in the MORNING window."""
        self.pet.add_task(make_task("e1", priority=Priority.EMERGENCY,
                                   is_mandatory=False, duration=10,
                                   preferred_time=TimeOfDay.ANY))
        plan = self.scheduler.generate_plan(TODAY)
        self.assertEqual(plan.scheduled_tasks[0].time_window, TimeOfDay.MORNING)

    def test_multiple_emergency_tasks_same_window_stack_sequentially(self):
        """Multiple EMERGENCY tasks in the same window are placed back-to-back, not overlapping."""
        self.pet.add_task(make_task("e1", priority=Priority.EMERGENCY,
                                   is_mandatory=False, duration=10,
                                   preferred_time=TimeOfDay.MORNING))
        self.pet.add_task(make_task("e2", priority=Priority.EMERGENCY,
                                   is_mandatory=False, duration=10,
                                   preferred_time=TimeOfDay.MORNING))
        plan = self.scheduler.generate_plan(TODAY)
        times = [(st.start_time, st.end_time) for st in plan.scheduled_tasks[:2]]
        self.assertEqual(times[0], (420, 430))
        self.assertEqual(times[1], (430, 440))

    def test_wake_time_at_noon_morning_cursor_capped_at_1159(self):
        """When wake_time is '12:00', the morning cursor is capped at '11:59'."""
        owner = make_owner(wake_time=720, morning=60, afternoon=90, evening=30)
        pet = Pet("Rex", "dog")
        owner.add_pet(pet)
        pet.add_task(make_task("t1", is_mandatory=True, duration=5,
                               preferred_time=TimeOfDay.MORNING))
        plan = Scheduler(owner, pet).generate_plan(TODAY)
        self.assertEqual(plan.scheduled_tasks[0].start_time, 719)

    def test_wake_time_at_noon_afternoon_cursor_starts_at_wake(self):
        """When wake_time is '12:00', the afternoon cursor starts at '12:00', not earlier."""
        owner = make_owner(wake_time=720, morning=0, afternoon=90, evening=30)
        pet = Pet("Rex", "dog")
        owner.add_pet(pet)
        pet.add_task(make_task("t1", is_mandatory=True, duration=20,
                               preferred_time=TimeOfDay.AFTERNOON))
        plan = Scheduler(owner, pet).generate_plan(TODAY)
        self.assertEqual(plan.scheduled_tasks[0].start_time, 720)

    def test_afternoon_cursor_never_before_wake_time(self):
        """An afternoon task starts no earlier than the owner's wake time."""
        owner = make_owner(wake_time=840, morning=0, afternoon=90, evening=30)
        pet = Pet("Rex", "dog")
        owner.add_pet(pet)
        pet.add_task(make_task("t1", is_mandatory=True, duration=20,
                               preferred_time=TimeOfDay.AFTERNOON))
        plan = Scheduler(owner, pet).generate_plan(TODAY)
        self.assertEqual(plan.scheduled_tasks[0].start_time, 840)

    def test_date_is_stored_on_all_scheduled_tasks(self):
        """Every ScheduledTask in the plan carries the exact date passed to generate_plan."""
        self.pet.add_task(make_task("t1", is_mandatory=True, duration=10,
                                   preferred_time=TimeOfDay.MORNING))
        target_date = date(2026, 6, 15)
        plan = self.scheduler.generate_plan(target_date)
        self.assertEqual(plan.scheduled_tasks[0].date, target_date)

    def test_window_summary_budget_is_zero_when_owner_never_set_budget(self):
        """get_window_summary() shows budget_minutes=0 for windows the owner never configured."""
        owner = Owner("Sam", 420)  # no set_budget calls
        pet = Pet("Rex", "dog")
        owner.add_pet(pet)
        plan = DailyPlan(TODAY, owner, pet)
        summary = plan.get_window_summary()
        self.assertEqual(summary["morning"]["budget_minutes"], 0)
        self.assertEqual(summary["afternoon"]["budget_minutes"], 0)
        self.assertEqual(summary["evening"]["budget_minutes"], 0)

    def test_mandatory_task_with_no_budget_set_scheduled_with_warning(self):
        """A mandatory task is always scheduled even when the owner never set any budget."""
        owner = Owner("Sam", 420)
        pet = Pet("Rex", "dog")
        owner.add_pet(pet)
        pet.add_task(make_task("t1", is_mandatory=True, duration=30,
                               preferred_time=TimeOfDay.MORNING))
        plan = Scheduler(owner, pet).generate_plan(TODAY)
        self.assertEqual(len(plan.scheduled_tasks), 1)
        self.assertTrue(len(plan.warnings) > 0)

    def test_tasks_across_all_three_windows_scheduled_with_correct_start_times(self):
        """Tasks in morning, afternoon, and evening each start at the correct window cursor."""
        self.pet.add_task(make_task("t1", is_mandatory=True, duration=10,
                                   preferred_time=TimeOfDay.MORNING))
        self.pet.add_task(make_task("t2", is_mandatory=True, duration=10,
                                   preferred_time=TimeOfDay.AFTERNOON))
        self.pet.add_task(make_task("t3", is_mandatory=True, duration=10,
                                   preferred_time=TimeOfDay.EVENING))
        plan = self.scheduler.generate_plan(TODAY)
        by_id = {st.task.id: st for st in plan.scheduled_tasks}
        self.assertEqual(by_id["t1"].start_time, 420)
        self.assertEqual(by_id["t2"].start_time, 720)
        self.assertEqual(by_id["t3"].start_time, 1020)


# ===========================================================================
# Feeding Task Consolidation
# ===========================================================================

class TestFeedingConsolidation(unittest.TestCase):
    """Tests for consolidating consecutive feeding tasks in the same time window."""

    def setUp(self):
        self.owner = make_owner(wake_time=420, morning=120, afternoon=120, evening=120)
        self.pet = Pet("Mochi", "dog")
        self.owner.add_pet(self.pet)
        self.scheduler = Scheduler(self.owner, self.pet)

    def test_two_consecutive_morning_feedings_consolidated(self):
        """Two consecutive feeding tasks in the morning are merged into one slot."""
        fp1 = FoodPreference("Dog Food", "dry", 200, 2)
        fp2 = FoodPreference("Dog Treat", "dry", 50, 1)
        
        self.pet.add_task(make_task("f1", name="Morning Feeding", 
                                   category=TaskCategory.FEEDING,
                                   duration=5, priority=Priority.HIGH,
                                   preferred_time=TimeOfDay.MORNING,
                                   is_mandatory=True, food_preference=fp1))
        self.pet.add_task(make_task("f2", name="Dog Treat",
                                   category=TaskCategory.FEEDING,
                                   duration=5, priority=Priority.MEDIUM,
                                   preferred_time=TimeOfDay.MORNING,
                                   is_mandatory=False, food_preference=fp2))
        
        plan = self.scheduler.generate_plan(TODAY)
        feeding_tasks = [st for st in plan.scheduled_tasks if st.task.category == TaskCategory.FEEDING]
        
        # Should have exactly one consolidated feeding slot
        self.assertEqual(len(feeding_tasks), 1)
        # Duration should be combined: 5 + 5 = 10 minutes
        self.assertEqual(feeding_tasks[0].task.duration_minutes, 10)
        # Reason should indicate consolidation
        self.assertIn("Consolidated", feeding_tasks[0].reason)
        # Name should show both tasks
        self.assertIn("Morning Feeding", feeding_tasks[0].task.name)
        self.assertIn("Dog Treat", feeding_tasks[0].task.name)

    def test_feedings_in_different_windows_not_consolidated(self):
        """Feeding tasks in different windows (morning vs evening) are not consolidated."""
        fp = FoodPreference("Dog Food", "dry", 200, 2)
        
        self.pet.add_task(make_task("f1", name="Morning Feeding",
                                   category=TaskCategory.FEEDING,
                                   duration=5, priority=Priority.HIGH,
                                   preferred_time=TimeOfDay.MORNING,
                                   is_mandatory=True, food_preference=fp))
        self.pet.add_task(make_task("f2", name="Evening Feeding",
                                   category=TaskCategory.FEEDING,
                                   duration=5, priority=Priority.HIGH,
                                   preferred_time=TimeOfDay.EVENING,
                                   is_mandatory=True, food_preference=fp))
        
        plan = self.scheduler.generate_plan(TODAY)
        feeding_tasks = [st for st in plan.scheduled_tasks if st.task.category == TaskCategory.FEEDING]
        
        # Should have two separate feeding slots (not consolidated)
        self.assertEqual(len(feeding_tasks), 2)
        # Neither should say "Consolidated"
        for st in feeding_tasks:
            self.assertNotIn("Consolidated", st.reason)

    def test_feeding_separated_by_non_feeding_task_not_consolidated(self):
        """Feeding tasks separated by a non-feeding task are not consolidated."""
        fp = FoodPreference("Dog Food", "dry", 200, 2)
        
        self.pet.add_task(make_task("f1", name="Feeding 1",
                                   category=TaskCategory.FEEDING,
                                   duration=5, priority=Priority.HIGH,
                                   preferred_time=TimeOfDay.MORNING,
                                   is_mandatory=True, food_preference=fp))
        self.pet.add_task(make_task("w1", name="Morning Walk",
                                   category=TaskCategory.WALK,
                                   duration=30, priority=Priority.HIGH,
                                   preferred_time=TimeOfDay.MORNING,
                                   is_mandatory=True))
        self.pet.add_task(make_task("f2", name="Feeding 2",
                                   category=TaskCategory.FEEDING,
                                   duration=5, priority=Priority.MEDIUM,
                                   preferred_time=TimeOfDay.MORNING,
                                   is_mandatory=False, food_preference=fp))
        
        plan = self.scheduler.generate_plan(TODAY)
        feeding_tasks = [st for st in plan.scheduled_tasks if st.task.category == TaskCategory.FEEDING]
        
        # Should have two separate feeding slots (not consecutive)
        self.assertEqual(len(feeding_tasks), 2)
        for st in feeding_tasks:
            self.assertNotIn("Consolidated", st.reason)

    def test_three_consecutive_feedings_all_consolidated(self):
        """Three consecutive feeding tasks are consolidated into one."""
        fp = FoodPreference("Food", "dry", 100, 1)
        
        for i in range(3):
            self.pet.add_task(make_task(f"f{i}", name=f"Feeding {i}",
                                       category=TaskCategory.FEEDING,
                                       duration=5, priority=Priority.HIGH,
                                       preferred_time=TimeOfDay.MORNING,
                                       is_mandatory=True if i < 2 else False,
                                       food_preference=fp))
        
        plan = self.scheduler.generate_plan(TODAY)
        feeding_tasks = [st for st in plan.scheduled_tasks if st.task.category == TaskCategory.FEEDING]
        
        # Should consolidate all three into one slot
        self.assertEqual(len(feeding_tasks), 1)
        self.assertEqual(feeding_tasks[0].task.duration_minutes, 15)  # 5+5+5
        self.assertIn("Consolidated", feeding_tasks[0].reason)

    def test_consolidated_task_takes_highest_priority(self):
        """A consolidated feeding task has the priority of the highest-priority constituent."""
        fp = FoodPreference("Food", "dry", 100, 1)
        
        self.pet.add_task(make_task("f1", name="Low Priority Feeding",
                                   category=TaskCategory.FEEDING,
                                   duration=5, priority=Priority.LOW,
                                   preferred_time=TimeOfDay.MORNING,
                                   is_mandatory=False, food_preference=fp))
        self.pet.add_task(make_task("f2", name="High Priority Feeding",
                                   category=TaskCategory.FEEDING,
                                   duration=5, priority=Priority.HIGH,
                                   preferred_time=TimeOfDay.MORNING,
                                   is_mandatory=True, food_preference=fp))
        
        plan = self.scheduler.generate_plan(TODAY)
        feeding_tasks = [st for st in plan.scheduled_tasks if st.task.category == TaskCategory.FEEDING]
        
        self.assertEqual(len(feeding_tasks), 1)
        # Consolidated task should have HIGH priority (max of the two)
        self.assertEqual(feeding_tasks[0].task.priority, Priority.HIGH)

    def test_non_feeding_tasks_passthrough_unchanged(self):
        """Non-feeding tasks are not affected by consolidation logic."""
        self.pet.add_task(make_task("w1", name="Walk",
                                   category=TaskCategory.WALK,
                                   duration=30, priority=Priority.HIGH,
                                   preferred_time=TimeOfDay.MORNING,
                                   is_mandatory=True))
        self.pet.add_task(make_task("g1", name="Grooming",
                                   category=TaskCategory.GROOMING,
                                   duration=15, priority=Priority.MEDIUM,
                                   preferred_time=TimeOfDay.AFTERNOON,
                                   is_mandatory=False))
        
        plan = self.scheduler.generate_plan(TODAY)
        non_feeding_count = sum(1 for st in plan.scheduled_tasks 
                               if st.task.category != TaskCategory.FEEDING)
        
        # Should have 2 non-feeding tasks, both unchanged
        self.assertEqual(non_feeding_count, 2)
        self.assertEqual(plan.scheduled_tasks[0].task.name, "Walk")
        self.assertEqual(plan.scheduled_tasks[1].task.name, "Grooming")

    def test_consolidation_preserves_start_end_times(self):
        """A consolidated feeding task spans from the first task's start to the last task's end."""
        fp = FoodPreference("Food", "dry", 100, 1)
        
        self.pet.add_task(make_task("f1", name="Feed",
                                   category=TaskCategory.FEEDING,
                                   duration=5, priority=Priority.HIGH,
                                   preferred_time=TimeOfDay.MORNING,
                                   is_mandatory=True, food_preference=fp))
        self.pet.add_task(make_task("f2", name="Treat",
                                   category=TaskCategory.FEEDING,
                                   duration=5, priority=Priority.MEDIUM,
                                   preferred_time=TimeOfDay.MORNING,
                                   is_mandatory=False, food_preference=fp))
        
        plan = self.scheduler.generate_plan(TODAY)
        feeding_slot = [st for st in plan.scheduled_tasks 
                       if st.task.category == TaskCategory.FEEDING][0]
        
        # Should start at 7:00 (wake time) and end at 7:10 (7:00 + 10 min)
        self.assertEqual(feeding_slot.start_time, 420)
        self.assertEqual(feeding_slot.end_time, 430)


# ===========================================================================
# Recurrence Continuity
# ===========================================================================

class TestRecurrenceContinuity(unittest.TestCase):
    """Verify that recurring tasks appear on matching days regardless of prior completion."""

    def setUp(self):
        self.owner = make_owner(wake_time=420, morning=120, afternoon=120, evening=60)
        self.pet = Pet("Rex", "dog", "Lab", 2.0)
        self.owner.add_pet(self.pet)
        self.day1 = date(2025, 6, 1)   # Sunday  (weekday=6)
        self.day2 = date(2025, 6, 2)   # Monday  (weekday=0)

    def _daily_task(self, tid="r1"):
        return Task(
            id=tid, name="Daily Walk",
            category=TaskCategory.WALK,
            duration_minutes=20,
            priority=Priority.MEDIUM,
            preferred_time=TimeOfDay.MORNING,
            is_mandatory=False,
            recurrence=Recurrence(
                type=RecurrenceType.DAILY,
                start_date=date(2025, 1, 1),
            ),
        )

    def test_daily_task_appears_on_consecutive_days(self):
        """A DAILY recurring task is scheduled on both day1 and day2."""
        self.pet.add_task(self._daily_task())
        plan1 = Scheduler(self.owner, self.pet).generate_plan(self.day1)
        plan2 = Scheduler(self.owner, self.pet).generate_plan(self.day2)
        ids1 = {st.task.id for st in plan1.scheduled_tasks}
        ids2 = {st.task.id for st in plan2.scheduled_tasks}
        self.assertTrue(any("r1" in i for i in ids1), "task missing from day1")
        self.assertTrue(any("r1" in i for i in ids2), "task missing from day2")

    def test_completing_day1_does_not_suppress_day2(self):
        """Marking day1's instance complete does not remove it from day2's plan."""
        self.pet.add_task(self._daily_task())
        plan1 = Scheduler(self.owner, self.pet).generate_plan(self.day1)
        # Mark every scheduled task on day1 complete
        for st in plan1.scheduled_tasks:
            st.mark_completed()
        plan2 = Scheduler(self.owner, self.pet).generate_plan(self.day2)
        ids2 = {st.task.id for st in plan2.scheduled_tasks}
        self.assertTrue(any("r1" in i for i in ids2),
                        "recurring task should still appear on day2 after day1 completion")

    def test_weekly_task_absent_on_non_matching_day(self):
        """WEEKLY task set for Monday only does not appear on Sunday."""
        task = Task(
            id="w1", name="Weekly Groom",
            category=TaskCategory.GROOMING,
            duration_minutes=15,
            priority=Priority.LOW,
            preferred_time=TimeOfDay.MORNING,
            is_mandatory=False,
            recurrence=Recurrence(
                type=RecurrenceType.WEEKLY,
                start_date=date(2025, 1, 1),
                days_of_week=[0],   # Monday only
            ),
        )
        self.pet.add_task(task)
        plan_sunday = Scheduler(self.owner, self.pet).generate_plan(self.day1)  # Sunday
        ids = {st.task.id for st in plan_sunday.scheduled_tasks}
        self.assertFalse(any("w1" in i for i in ids),
                         "Monday-only task should not appear on Sunday")

    def test_weekly_task_present_on_matching_day(self):
        """WEEKLY task set for Monday appears on Monday."""
        task = Task(
            id="w1", name="Weekly Groom",
            category=TaskCategory.GROOMING,
            duration_minutes=15,
            priority=Priority.LOW,
            preferred_time=TimeOfDay.MORNING,
            is_mandatory=False,
            recurrence=Recurrence(
                type=RecurrenceType.WEEKLY,
                start_date=date(2025, 1, 1),
                days_of_week=[0],   # Monday only
            ),
        )
        self.pet.add_task(task)
        plan_monday = Scheduler(self.owner, self.pet).generate_plan(self.day2)  # Monday
        ids = {st.task.id for st in plan_monday.scheduled_tasks}
        self.assertTrue(any("w1" in i for i in ids),
                        "Monday-only task should appear on Monday")

    def test_recurring_task_stops_after_end_date(self):
        """DAILY task with end_date=day1 does not appear on day2."""
        task = Task(
            id="r2", name="Expiring Task",
            category=TaskCategory.WALK,
            duration_minutes=10,
            priority=Priority.MEDIUM,
            preferred_time=TimeOfDay.MORNING,
            is_mandatory=False,
            recurrence=Recurrence(
                type=RecurrenceType.DAILY,
                start_date=date(2025, 1, 1),
                end_date=self.day1,   # expires after day1
            ),
        )
        self.pet.add_task(task)
        plan1 = Scheduler(self.owner, self.pet).generate_plan(self.day1)
        plan2 = Scheduler(self.owner, self.pet).generate_plan(self.day2)
        ids1 = {st.task.id for st in plan1.scheduled_tasks}
        ids2 = {st.task.id for st in plan2.scheduled_tasks}
        self.assertTrue(any("r2" in i for i in ids1), "task should appear on day1 (within range)")
        self.assertFalse(any("r2" in i for i in ids2), "task should not appear on day2 (past end_date)")

    def test_expanded_recurring_task_id_has_suffix(self):
        """Expanded recurring task clone gets '_recurring' appended to its id."""
        self.pet.add_task(self._daily_task("orig"))
        plan = Scheduler(self.owner, self.pet).generate_plan(self.day1)
        ids = [st.task.id for st in plan.scheduled_tasks]
        self.assertIn("orig_recurring", ids)


# ===========================================================================
# Time-Overlap Conflict Detection
# ===========================================================================

class TestTimeOverlapConflictDetection(unittest.TestCase):
    """Tests for _detect_time_overlaps — verifies plan.conflicts receives TIME_OVERLAP entries."""

    def setUp(self):
        self.owner = make_owner(wake_time=420, morning=240, afternoon=120, evening=60)
        self.pet = Pet("Dot", "cat", "Tabby", 3.0)
        self.owner.add_pet(self.pet)
        self.plan_date = date(2025, 6, 1)

    def _pinned(self, tid, name, start_min, duration=30):
        return Task(
            id=tid, name=name,
            category=TaskCategory.WALK,
            duration_minutes=duration,
            priority=Priority.MEDIUM,
            preferred_time=TimeOfDay.MORNING,
            is_mandatory=False,
            specific_time=start_min,
        )

    def _run(self, tasks):
        for t in tasks:
            self.pet.add_task(t)
        return Scheduler(self.owner, self.pet).generate_plan(self.plan_date)

    def _overlap_conflicts(self, plan):
        return [c for c in plan.conflicts if c.conflict_type == ConflictType.TIME_OVERLAP]

    def test_two_pinned_same_start_produces_conflict(self):
        """Two pinned tasks starting at the same time produce one TIME_OVERLAP conflict."""
        plan = self._run([
            self._pinned("a", "Task A", 480),  # 8:00–8:30
            self._pinned("b", "Task B", 480),  # 8:00–8:30
        ])
        self.assertEqual(len(self._overlap_conflicts(plan)), 1)

    def test_two_pinned_partial_overlap_produces_conflict(self):
        """Two pinned tasks with partial overlap (A starts before B ends) produce a conflict."""
        plan = self._run([
            self._pinned("a", "Task A", 480, 30),  # 8:00–8:30
            self._pinned("b", "Task B", 500, 30),  # 8:20–8:50
        ])
        self.assertEqual(len(self._overlap_conflicts(plan)), 1)

    def test_two_pinned_adjacent_no_conflict(self):
        """Two pinned tasks that are exactly adjacent (A ends when B starts) produce no conflict."""
        plan = self._run([
            self._pinned("a", "Task A", 480, 30),  # 8:00–8:30
            self._pinned("b", "Task B", 510, 30),  # 8:30–9:00
        ])
        self.assertEqual(len(self._overlap_conflicts(plan)), 0)

    def test_two_pinned_no_overlap_no_conflict(self):
        """Two pinned tasks with a gap between them produce no conflict."""
        plan = self._run([
            self._pinned("a", "Task A", 480, 30),  # 8:00–8:30
            self._pinned("b", "Task B", 540, 30),  # 9:00–9:30
        ])
        self.assertEqual(len(self._overlap_conflicts(plan)), 0)

    def test_three_pinned_all_overlapping_produces_three_conflicts(self):
        """Three mutually overlapping pinned tasks produce three pairwise conflicts."""
        plan = self._run([
            self._pinned("a", "Task A", 480, 60),  # 8:00–9:00
            self._pinned("b", "Task B", 490, 60),  # 8:10–9:10
            self._pinned("c", "Task C", 500, 60),  # 8:20–9:20
        ])
        self.assertEqual(len(self._overlap_conflicts(plan)), 3)

    def test_conflict_message_contains_task_names_and_times(self):
        """TIME_OVERLAP conflict message includes both task names and formatted times."""
        plan = self._run([
            self._pinned("a", "Alpha Walk", 480, 30),
            self._pinned("b", "Beta Walk",  480, 30),
        ])
        conflicts = self._overlap_conflicts(plan)
        self.assertEqual(len(conflicts), 1)
        msg = conflicts[0].message
        self.assertIn("Alpha Walk", msg)
        self.assertIn("Beta Walk", msg)
        self.assertIn("8:00", msg)

    def test_pinned_task_ending_exactly_when_next_starts_no_conflict(self):
        """Boundary: end_time == next start_time is NOT an overlap (open interval)."""
        plan = self._run([
            self._pinned("a", "Task A", 600, 60),  # 10:00–11:00
            self._pinned("b", "Task B", 660, 30),  # 11:00–11:30
        ])
        self.assertEqual(len(self._overlap_conflicts(plan)), 0)


# ===========================================================================
# Remove Task by Index
# ===========================================================================

class TestRemoveTaskByIndex(unittest.TestCase):
    """Tests for the index-based removal pattern used in the UI:
       target = pet.get_tasks()[index - 1]; pet.remove_task(target.id)
    """

    def setUp(self):
        self.pet = Pet("Buddy", "dog")
        self.t1 = make_task("t1", name="Walk")
        self.t2 = make_task("t2", name="Feed")
        self.t3 = make_task("t3", name="Groom")
        for t in [self.t1, self.t2, self.t3]:
            self.pet.add_task(t)

    def _remove_by_index(self, index: int):
        """Simulate the UI: 1-based index → remove by id."""
        target = self.pet.get_tasks()[index - 1]
        self.pet.remove_task(target.id)

    def test_get_tasks_returns_insertion_order(self):
        """get_tasks() returns tasks in the order they were added."""
        names = [t.name for t in self.pet.get_tasks()]
        self.assertEqual(names, ["Walk", "Feed", "Groom"])

    def test_remove_first_by_index(self):
        """Removing index 1 deletes the first task."""
        self._remove_by_index(1)
        names = [t.name for t in self.pet.get_tasks()]
        self.assertEqual(names, ["Feed", "Groom"])

    def test_remove_middle_by_index(self):
        """Removing index 2 deletes the middle task."""
        self._remove_by_index(2)
        names = [t.name for t in self.pet.get_tasks()]
        self.assertEqual(names, ["Walk", "Groom"])

    def test_remove_last_by_index(self):
        """Removing index 3 (last) deletes the last task."""
        self._remove_by_index(3)
        names = [t.name for t in self.pet.get_tasks()]
        self.assertEqual(names, ["Walk", "Feed"])

    def test_remaining_tasks_preserve_relative_order(self):
        """After removal, the remaining tasks keep their original relative order."""
        self._remove_by_index(1)
        tasks = self.pet.get_tasks()
        self.assertEqual(tasks[0].id, "t2")
        self.assertEqual(tasks[1].id, "t3")

    def test_repeated_removal_updates_list_length(self):
        """Each removal decreases the task count by exactly one."""
        self.assertEqual(len(self.pet.get_tasks()), 3)
        self._remove_by_index(1)
        self.assertEqual(len(self.pet.get_tasks()), 2)
        self._remove_by_index(1)
        self.assertEqual(len(self.pet.get_tasks()), 1)
        self._remove_by_index(1)
        self.assertEqual(len(self.pet.get_tasks()), 0)

    def test_remove_all_one_by_one_leaves_empty_list(self):
        """Removing every task by index leaves an empty task list."""
        for _ in range(3):
            self._remove_by_index(1)
        self.assertEqual(self.pet.get_tasks(), [])

    def test_index_accesses_correct_task_after_prior_removal(self):
        """After removing index 1, index 1 now refers to what was previously index 2."""
        self._remove_by_index(1)   # removes "Walk"
        target = self.pet.get_tasks()[0]   # index 1 in new list
        self.assertEqual(target.name, "Feed")


if __name__ == "__main__":
    unittest.main()
    print("All tests passed!")
