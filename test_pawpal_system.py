"""
Unit tests for pawpal_system.py
Run with:  python -m pytest test_pawpal_system.py -v
       or: python -m unittest discover
"""

import unittest
from datetime import date

from pawpal_system import (
    # Time helpers
    _parse_time, _format_time, _add_minutes, _time_to_window, _max_time,
    # Enums
    TaskCategory, Priority, TimeOfDay, TaskStatus,
    # Classes
    FoodPreference, Task, Pet, Owner, ScheduledTask, DailyPlan, Scheduler,
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


def make_owner(wake_time="7:00", morning=60, afternoon=90, evening=30) -> Owner:
    owner = Owner("Jordan", wake_time)
    owner.set_budget(TimeOfDay.MORNING, morning)
    owner.set_budget(TimeOfDay.AFTERNOON, afternoon)
    owner.set_budget(TimeOfDay.EVENING, evening)
    return owner


def make_scheduled_task(task=None, start="7:00", duration=30,
                        window=TimeOfDay.MORNING) -> ScheduledTask:
    if task is None:
        task = make_task()
    end = _add_minutes(start, duration)
    return ScheduledTask(
        task=task,
        date=TODAY,
        start_time=start,
        end_time=end,
        status=TaskStatus.SCHEDULED,
        reason="test",
        time_window=window,
    )


# ===========================================================================
# Time helpers
# ===========================================================================

class TestTimeHelpers(unittest.TestCase):

    # --- _parse_time ---

    def test_parse_time_whole_hour(self):
        """Parses "7:00" into (7, 0)."""
        self.assertEqual(_parse_time("7:00"), (7, 0))

    def test_parse_time_with_minutes(self):
        """Parses "14:35" into (14, 35)."""
        self.assertEqual(_parse_time("14:35"), (14, 35))

    def test_parse_time_zero_padded_minutes(self):
        """Parses "9:05" correctly without dropping the leading zero."""
        self.assertEqual(_parse_time("9:05"), (9, 5))

    # --- _format_time ---

    def test_format_time_pads_minutes(self):
        """Minutes < 10 are zero-padded in the output string."""
        self.assertEqual(_format_time(8, 5), "8:05")

    def test_format_time_two_digit_minutes(self):
        """Minutes >= 10 are not padded."""
        self.assertEqual(_format_time(13, 45), "13:45")

    # --- _add_minutes ---

    def test_add_minutes_no_overflow(self):
        """Adding minutes within the same hour."""
        self.assertEqual(_add_minutes("7:00", 30), "7:30")

    def test_add_minutes_crosses_hour_boundary(self):
        """Adding minutes that push past the hour boundary."""
        self.assertEqual(_add_minutes("7:45", 30), "8:15")

    def test_add_minutes_crosses_noon(self):
        """Adding minutes that push from morning into afternoon."""
        self.assertEqual(_add_minutes("11:50", 20), "12:10")

    def test_add_minutes_zero(self):
        """Adding zero minutes returns the same time."""
        self.assertEqual(_add_minutes("10:00", 0), "10:00")

    # --- _time_to_window ---

    def test_window_morning(self):
        """Any time before 12:00 maps to MORNING."""
        self.assertEqual(_time_to_window("7:30"), TimeOfDay.MORNING)
        self.assertEqual(_time_to_window("11:59"), TimeOfDay.MORNING)

    def test_window_afternoon(self):
        """12:00–16:59 maps to AFTERNOON."""
        self.assertEqual(_time_to_window("12:00"), TimeOfDay.AFTERNOON)
        self.assertEqual(_time_to_window("16:45"), TimeOfDay.AFTERNOON)

    def test_window_evening(self):
        """17:00 and later maps to EVENING."""
        self.assertEqual(_time_to_window("17:00"), TimeOfDay.EVENING)
        self.assertEqual(_time_to_window("20:30"), TimeOfDay.EVENING)

    # --- _max_time ---

    def test_max_time_returns_later(self):
        """Returns the later of two times."""
        self.assertEqual(_max_time("12:00", "7:30"), "12:00")

    def test_max_time_equal_returns_first(self):
        """When times are equal, the first argument is returned."""
        self.assertEqual(_max_time("12:00", "12:00"), "12:00")

    def test_max_time_second_is_later(self):
        """Returns second argument when it is later."""
        self.assertEqual(_max_time("7:00", "12:00"), "12:00")


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
        fresh_owner = Owner("Alex", "6:00")
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
        self.st = make_scheduled_task(task=self.task, start="7:00", duration=30)

    # --- duration_minutes property ---

    def test_duration_minutes_computed_correctly(self):
        """duration_minutes reflects the difference between start and end times."""
        self.assertEqual(self.st.duration_minutes, 30)

    def test_duration_minutes_across_hour_boundary(self):
        """duration_minutes works when start and end are in different hours."""
        task = make_task(duration=45)
        st = make_scheduled_task(task=task, start="7:30", duration=45)
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
        st = make_scheduled_task(task=t, start="7:00", duration=20, window=TimeOfDay.MORNING)
        self.plan.add_scheduled_task(st)
        summary = self.plan.get_window_summary()
        self.assertEqual(summary["morning"]["tasks"], 1)
        self.assertEqual(summary["morning"]["used_minutes"], 20)

    def test_window_summary_used_minutes_sums_correctly(self):
        """get_window_summary() sums duration across multiple tasks in a window."""
        for i, dur in enumerate([20, 25]):
            t = make_task(f"t{i}", duration=dur)
            st = make_scheduled_task(task=t, start=f"{7+i}:00", duration=dur,
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
        self.owner = make_owner(wake_time="7:00", morning=60, afternoon=90, evening=30)
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
        self.assertEqual(plan.scheduled_tasks[0].start_time, "7:00")

    def test_generate_plan_mandatory_task_end_time(self):
        """End time is start time plus duration."""
        self.pet.add_task(make_task("t1", is_mandatory=True, duration=30,
                                   preferred_time=TimeOfDay.MORNING))
        plan = self.scheduler.generate_plan(TODAY)
        self.assertEqual(plan.scheduled_tasks[0].end_time, "7:30")

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
        # First task: 7:00-7:20, second task: 7:20-7:40
        self.assertEqual(times[0], ("7:00", "7:20"))
        self.assertEqual(times[1], ("7:20", "7:40"))

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
        st = make_scheduled_task(task=t, start="7:00", duration=25, window=TimeOfDay.MORNING)
        plan.add_scheduled_task(st)
        remaining = self.scheduler._remaining_budget(TimeOfDay.MORNING, plan)
        self.assertEqual(remaining, 35)

    def test_remaining_budget_never_negative(self):
        """_remaining_budget() returns 0, not a negative number, when over budget."""
        plan = DailyPlan(TODAY, self.owner, self.pet)
        t = make_task(duration=80)  # exceeds morning budget of 60
        st = make_scheduled_task(task=t, start="7:00", duration=80, window=TimeOfDay.MORNING)
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

    def test_carry_over_returns_skipped_tasks(self):
        """_carry_over() returns the skipped_tasks list from the previous plan."""
        prev = DailyPlan(date(2026, 4, 3), self.owner, self.pet)
        skipped = make_task("s1")
        prev.add_skipped_task(skipped)
        carried = self.scheduler._carry_over(prev)
        self.assertEqual(len(carried), 1)
        self.assertEqual(carried[0].id, "s1")

    def test_carry_over_empty_when_nothing_skipped(self):
        """_carry_over() returns [] when the previous plan had no skipped tasks."""
        prev = DailyPlan(date(2026, 4, 3), self.owner, self.pet)
        self.assertEqual(self.scheduler._carry_over(prev), [])


# ===========================================================================
# Edge cases
# ===========================================================================

class TestEdgeCasesTimeHelpers(unittest.TestCase):

    def test_add_minutes_large_value_crossing_multiple_hours(self):
        """Adding a large number of minutes advances the clock correctly across hours."""
        # 7:00 + 150 min = 9:30
        self.assertEqual(_add_minutes("7:00", 150), "9:30")

    def test_time_to_window_exact_noon_boundary(self):
        """12:00 exactly is AFTERNOON, not MORNING."""
        self.assertEqual(_time_to_window("12:00"), TimeOfDay.AFTERNOON)

    def test_time_to_window_exact_evening_boundary(self):
        """17:00 exactly is EVENING, not AFTERNOON."""
        self.assertEqual(_time_to_window("17:00"), TimeOfDay.EVENING)

    def test_max_time_with_same_hour_different_minutes(self):
        """_max_time() correctly compares times within the same hour."""
        self.assertEqual(_max_time("7:45", "7:30"), "7:45")


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
        owner = Owner("Alex", "7:00")
        self.assertEqual(owner.get_total_budget(), 0)

    def test_set_budget_overwrite_updates_value(self):
        """Calling set_budget() twice on the same window keeps the latest value."""
        owner = Owner("Alex", "7:00")
        owner.set_budget(TimeOfDay.MORNING, 60)
        owner.set_budget(TimeOfDay.MORNING, 45)
        self.assertEqual(owner.get_budget(TimeOfDay.MORNING), 45)

    def test_search_pets_on_empty_owner(self):
        """search_pets() returns [] when the owner has no pets at all."""
        owner = Owner("Alex", "7:00")
        self.assertEqual(owner.search_pets("Mochi"), [])

    def test_get_pets_returns_list_not_dict_values(self):
        """get_pets() returns a plain list, not a dict_values object."""
        owner = Owner("Alex", "7:00")
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
        st_m = make_scheduled_task(task=t_morning, start="7:00",  duration=20, window=TimeOfDay.MORNING)
        st_a = make_scheduled_task(task=t_afternoon, start="12:00", duration=30, window=TimeOfDay.AFTERNOON)
        plan = DailyPlan(TODAY, self.owner, self.pet)
        plan.add_scheduled_task(st_m)
        plan.add_scheduled_task(st_a)
        summary = plan.get_window_summary()
        self.assertEqual(summary["morning"]["used_minutes"], 20)
        self.assertEqual(summary["afternoon"]["used_minutes"], 30)
        self.assertEqual(summary["evening"]["used_minutes"], 0)


class TestEdgeCasesScheduler(unittest.TestCase):

    def setUp(self):
        self.owner = make_owner(wake_time="7:00", morning=60, afternoon=90, evening=30)
        self.pet = Pet("Mochi", "dog")
        self.owner.add_pet(self.pet)
        self.scheduler = Scheduler(self.owner, self.pet)

    def test_wake_time_after_noon_morning_gets_no_tasks(self):
        """When the owner wakes after noon, no morning tasks are scheduled."""
        owner = make_owner(wake_time="13:00", morning=60, afternoon=90, evening=0)
        pet = Pet("Rex", "dog")
        owner.add_pet(pet)
        # Mandatory morning task — cursor will be at "11:59", budget may still be there
        # but cursor is before noon so it will be placed there; the key test is
        # that the afternoon cursor starts at 13:00, not 12:00
        pet.add_task(make_task("t1", is_mandatory=True, duration=20,
                               preferred_time=TimeOfDay.AFTERNOON))
        plan = Scheduler(owner, pet).generate_plan(TODAY)
        # Afternoon cursor should start at wake_time (13:00), not 12:00
        self.assertEqual(plan.scheduled_tasks[0].start_time, "13:00")

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
        owner = Owner("Sam", "7:00")  # no set_budget calls
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
        self.assertEqual(by_id["t1"].start_time, "7:00")
        # Afternoon task starts at 12:00, unaffected by morning cursor
        self.assertEqual(by_id["t2"].start_time, "12:00")

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


if __name__ == "__main__":
    unittest.main()
