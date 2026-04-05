import streamlit as st
from datetime import date

from pawpal_system import (
    Owner, Pet, Task, Scheduler,
    TaskCategory, Priority, TimeOfDay, TaskStatus,
    Recurrence, RecurrenceType,
    SkipReason, ConflictType, Conflict,
    format_time, parse_time_str,
)

st.set_page_config(page_title="PawPal+", page_icon="🐾", layout="centered")
st.title("🐾 PawPal+")

# ---------------------------------------------------------------------------
# Helper function to format times with AM/PM
# ---------------------------------------------------------------------------

def format_time_12hr(minutes: int) -> str:
    """Convert minutes-since-midnight to 'h:MM AM/PM' format."""
    h, m = divmod(minutes, 60)
    period = 'AM' if h < 12 else 'PM'
    h_12 = h if h <= 12 else h - 12
    h_12 = 12 if h_12 == 0 else h_12  # midnight case
    return f"{h_12}:{m:02d} {period}"

# ---------------------------------------------------------------------------
# Session-state initialisation — once per browser session
# ---------------------------------------------------------------------------

if "owner" not in st.session_state:
    default_owner = Owner("Jordan", 420)  # 7:00
    default_owner.set_budget(TimeOfDay.MORNING, 60)
    default_owner.set_budget(TimeOfDay.AFTERNOON, 90)
    default_owner.set_budget(TimeOfDay.EVENING, 60)
    st.session_state.owner = default_owner

if "selected_pet_id" not in st.session_state:
    default_pet = Pet("Mochi", "dog")
    st.session_state.owner.add_pet(default_pet)
    st.session_state.selected_pet_id = default_pet.id

if "previous_plans" not in st.session_state:
    st.session_state.previous_plans = {}   # dict[pet_id, DailyPlan]

if "all_plans" not in st.session_state:
    st.session_state.all_plans = {}        # dict[pet_id, DailyPlan]

owner: Owner = st.session_state.owner

# ---------------------------------------------------------------------------
# Step 1 — Owner settings
# ---------------------------------------------------------------------------

st.header("1. Owner")

col1, col2 = st.columns(2)
with col1:
    owner_name = st.text_input("Owner name", value=owner.name)
    wake_time = st.text_input("Wake time (hr:min)", value=format_time(owner.wake_time))

st.caption("Daily time budget (minutes per window)")
bcol1, bcol2, bcol3 = st.columns(3)
with bcol1:
    morning_budget = st.number_input("Morning", min_value=0, max_value=480, value=owner.get_budget(TimeOfDay.MORNING))
with bcol2:
    afternoon_budget = st.number_input("Afternoon", min_value=0, max_value=480, value=owner.get_budget(TimeOfDay.AFTERNOON))
with bcol3:
    evening_budget = st.number_input("Evening", min_value=0, max_value=480, value=owner.get_budget(TimeOfDay.EVENING))

if st.button("Save owner"):
    owner.name = owner_name
    owner.wake_time = parse_time_str(wake_time)
    owner.set_budget(TimeOfDay.MORNING, int(morning_budget))
    owner.set_budget(TimeOfDay.AFTERNOON, int(afternoon_budget))
    owner.set_budget(TimeOfDay.EVENING, int(evening_budget))
    st.success(f"Saved owner '{owner_name}'")

st.divider()

# ---------------------------------------------------------------------------
# Step 2 — Pets
# ---------------------------------------------------------------------------

st.header("2. Pets")

# Pet list with selector
for p in owner.get_pets():
    pcol1, pcol2 = st.columns([4, 1])
    with pcol1:
        marker = " ← selected" if p.id == st.session_state.selected_pet_id else ""
        st.write(f"**{p.name}** ({p.species}) — {len(p.get_tasks())} task(s){marker}")
    with pcol2:
        if p.id != st.session_state.selected_pet_id:
            if st.button("Select", key=f"select_{p.id}"):
                st.session_state.selected_pet_id = p.id
                st.rerun()

# Add pet form
with st.expander("Add a new pet"):
    apcol1, apcol2 = st.columns(2)
    with apcol1:
        new_pet_name = st.text_input("Pet name", key="new_pet_name")
    with apcol2:
        new_species = st.selectbox("Species", ["dog", "cat", "rabbit", "other"], key="new_species")
    if st.button("Add pet"):
        if new_pet_name.strip():
            new_pet = Pet(new_pet_name, new_species)
            owner.add_pet(new_pet)          # Owner.add_pet auto-generates the id
            st.session_state.selected_pet_id = new_pet.id
            st.session_state.all_plans = {}   # new pet added; regenerate to include it
            st.success(f"Added '{new_pet.name}' and selected.")
            st.rerun()
        else:
            st.error("Pet name cannot be empty.")

st.divider()

# ---------------------------------------------------------------------------
# Step 3 — Tasks for selected pet
# ---------------------------------------------------------------------------

st.header("3. Tasks")

selected_pet: Pet | None = owner._get_pet_by_id(st.session_state.selected_pet_id)

if selected_pet is None:
    st.warning("No pet selected. Add or select a pet above.")
else:
    st.write(f"Managing tasks for **{selected_pet.name}** ({selected_pet.species})")

    with st.expander("Add a new task", expanded=True):
        # Specific time toggle — rendered first so it controls the form below
        use_specific_time = st.checkbox("Pin to a specific start time", key="use_specific_time")

        tcol1, tcol2 = st.columns(2)
        with tcol1:
            task_name = st.text_input("Task name", value="Morning Walk")
            category = st.selectbox("Category", [c.value for c in TaskCategory])
            duration = st.number_input("Duration (minutes)", min_value=1, max_value=240, value=30)
        with tcol2:
            priority = st.selectbox("Priority", [p.name for p in Priority], index=1)
            if not use_specific_time:
                preferred_time = st.selectbox("Preferred time", [t.value for t in TimeOfDay], index=3)
            is_mandatory = st.checkbox("Mandatory (always scheduled)")

        # Specific time input + auto-derived preferred_time
        specific_time_val = None
        if use_specific_time:
            stcol_time, stcol_ampm, stcol_info = st.columns([2, 1, 3])
            with stcol_time:
                specific_time_str = st.text_input(
                    "Start time (h:MM)", value="8:00", key="specific_time_input"
                )
            with stcol_ampm:
                st.write("")   # nudge button down to align with input
                ampm = st.radio("", options=["AM", "PM"], horizontal=True, key="specific_time_ampm", label_visibility="collapsed")
            try:
                _h, _m = map(int, specific_time_str.strip().split(":"))
                if not (1 <= _h <= 12 and 0 <= _m <= 59):
                    raise ValueError()
                # Convert 12-hour → 24-hour
                if ampm == "AM":
                    _h24 = 0 if _h == 12 else _h
                else:
                    _h24 = 12 if _h == 12 else _h + 12
                specific_time_val = _h24 * 60 + _m
                # Auto-derive preferred_time from the 24-hour value
                if _h24 < 12:
                    preferred_time = TimeOfDay.MORNING.value
                elif _h24 < 17:
                    preferred_time = TimeOfDay.AFTERNOON.value
                else:
                    preferred_time = TimeOfDay.EVENING.value
                with stcol_info:
                    st.info(f"Auto-assigned to **{preferred_time}** window")
            except (ValueError, AttributeError):
                preferred_time = TimeOfDay.MORNING.value
                with stcol_info:
                    st.error("Invalid format — use h:MM (e.g. 8:30)")

        # Recurrence options
        st.write("**Recurrence**")
        is_recurring = st.checkbox("Make this task recurring?", value=False)
        
        recurrence_obj = None
        if is_recurring:
            recurrence_type = st.selectbox(
                "Recurrence type",
                options=["DAILY", "WEEKLY", "INTERVAL", "MONTHLY"],
                key="recurrence_type"
            )
            
            start_date = st.date_input("Start date", value=date.today())
            end_date_option = st.checkbox("Set an end date?", value=False, key="has_end_date")
            end_date = None
            if end_date_option:
                end_date = st.date_input("End date", value=start_date, key="end_date")
            
            # Conditionally show fields based on recurrence type
            if recurrence_type == "WEEKLY":
                st.write("Select days of week:")
                days_input = st.multiselect(
                    "Days",
                    options=["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"],
                    default=["Monday"],
                    key="weekly_days"
                )
                day_map = {"Monday": 0, "Tuesday": 1, "Wednesday": 2, "Thursday": 3, 
                          "Friday": 4, "Saturday": 5, "Sunday": 6}
                days_of_week = [day_map[d] for d in days_input]
                recurrence_obj = Recurrence(
                    type=RecurrenceType.WEEKLY,
                    start_date=start_date,
                    end_date=end_date,
                    days_of_week=days_of_week
                )
            
            elif recurrence_type == "INTERVAL":
                interval_days = st.number_input("Every N days", min_value=1, max_value=365, value=1)
                recurrence_obj = Recurrence(
                    type=RecurrenceType.INTERVAL,
                    start_date=start_date,
                    end_date=end_date,
                    interval=interval_days
                )
            
            elif recurrence_type == "MONTHLY":
                st.info(f"Recurs on day {start_date.day} of each month")
                recurrence_obj = Recurrence(
                    type=RecurrenceType.MONTHLY,
                    start_date=start_date,
                    end_date=end_date
                )
            
            elif recurrence_type == "DAILY":
                recurrence_obj = Recurrence(
                    type=RecurrenceType.DAILY,
                    start_date=start_date,
                    end_date=end_date
                )

        if st.button("Add task"):
            new_window = TimeOfDay(preferred_time)
            new_duration = int(duration)

            # --- Guard 1: specific_time exact overlap across all pets ---
            time_conflict_msg = None
            if specific_time_val is not None:
                new_s = specific_time_val
                new_e = new_s + new_duration
                for p in owner.get_pets():
                    for t in p.get_tasks():
                        if t.specific_time is not None:
                            t_s = t.specific_time
                            t_e = t_s + t.duration_minutes
                            if new_s < t_e and t_s < new_e:
                                time_conflict_msg = (
                                    f"Time conflict: **{task_name}** ({format_time(specific_time_val)}, {new_duration} min) "
                                    f"overlaps **{t.name}** ({format_time(t.specific_time)}, {t.duration_minutes} min) "
                                    f"for **{p.name}**."
                                )
                                break
                    if time_conflict_msg:
                        break

            # --- Guard 2: window capacity (only for non-pinned tasks) ---
            window_full_msg = None
            if not specific_time_val:
                window_budget = owner.get_budget(new_window)
                existing_duration = sum(
                    t.duration_minutes
                    for p in owner.get_pets()
                    for t in p.get_tasks()
                    if t.preferred_time == new_window
                )
                if window_budget > 0 and existing_duration + new_duration > window_budget:
                    occupied = [
                        f"{t.name} ({t.duration_minutes} min) — {p.name}"
                        for p in owner.get_pets()
                        for t in p.get_tasks()
                        if t.preferred_time == new_window
                    ]
                    window_full_msg = (
                        f"Cannot add **{task_name}** — the **{preferred_time}** window is full.\n\n"
                        f"Budget: **{window_budget} min** &nbsp;|&nbsp; "
                        f"Already scheduled: **{existing_duration} min** &nbsp;|&nbsp; "
                        f"This task: **{new_duration} min** &nbsp;→&nbsp; "
                        f"Would need **{existing_duration + new_duration} min**\n\n"
                        f"Tasks already in this window:\n" +
                        "\n".join(f"- {item}" for item in occupied)
                    )

            if time_conflict_msg:
                st.error(time_conflict_msg)
            elif window_full_msg:
                st.error(window_full_msg)
            else:
                task_id = f"t{len(selected_pet.get_tasks()) + 1}"
                task = Task(
                    id=task_id,
                    name=task_name,
                    category=TaskCategory(category),
                    duration_minutes=new_duration,
                    priority=Priority[priority],
                    preferred_time=new_window,
                    is_mandatory=is_mandatory,
                    recurrence=recurrence_obj,
                    specific_time=specific_time_val,
                )
                try:
                    task.validate()
                    if task.recurrence:
                        task.recurrence.validate()
                    selected_pet.add_task(task)
                    st.success(f"Added '{task_name}'" + (" (recurring)" if is_recurring else ""))
                except ValueError as e:
                    st.error(str(e))

    tasks = selected_pet.get_tasks()
    if tasks:
        st.write(f"**{len(tasks)} task(s):**")
        st.table(
            [
                {
                    "#": i + 1,
                    "Name": t.name,
                    "Category": t.category.value,
                    "Duration (min)": t.duration_minutes,
                    "Priority": t.priority.name,
                    "Start time": format_time_12hr(t.specific_time) if t.specific_time else "flexible",
                    "Window": t.preferred_time.value,
                    "Mandatory": t.is_mandatory,
                }
                for i, t in enumerate(tasks)
            ]
        )

        remove_index = st.number_input(
            "Remove task by index (1-based)",
            min_value=1, max_value=len(tasks), value=1, step=1,
            key="remove_index",
        )
        if st.button("Remove task"):
            target = tasks[int(remove_index) - 1]
            selected_pet.remove_task(target.id)
            st.success(f"Removed '{target.name}'")
            st.rerun()
    else:
        st.info("No tasks yet. Add one above.")

st.divider()

# ---------------------------------------------------------------------------
# Step 4 — Generate schedule
# ---------------------------------------------------------------------------

st.header("4. Generate Schedule")

pets_with_tasks = [p for p in owner.get_pets() if p.get_tasks()]

if not owner.get_pets():
    st.info("Add at least one pet first.")
elif not pets_with_tasks:
    st.warning("Add at least one task to a pet before generating a schedule.")
else:
    plan_date = st.date_input("Plan date", value=date.today())

    if st.button("Generate schedule"):
        new_plans = {}
        for pet in pets_with_tasks:
            prev = st.session_state.previous_plans.get(pet.id)
            new_plans[pet.id] = Scheduler(owner, pet).generate_plan(plan_date, prev)
        st.session_state.previous_plans = new_plans
        st.session_state.all_plans = new_plans
        # Clear any stale per-task status keys from a previous plan
        for key in list(st.session_state.keys()):
            if key.startswith("task_status_"):
                del st.session_state[key]

    # Render outside the button block so the plan persists across interactions
    all_plans: dict = st.session_state.all_plans
    if all_plans:

        STATUS_OPTIONS = ["to-do", "done", "skip"]
        STATUS_MAP = {
            "to-do": TaskStatus.SCHEDULED,
            "done":  TaskStatus.COMPLETED,
            "skip":  TaskStatus.SKIPPED,
        }
        REVERSE_STATUS_MAP = {v: k for k, v in STATUS_MAP.items()}
        CONFLICT_LABELS = {
            ConflictType.OVER_CAPACITY:        "[OVER CAPACITY]",
            ConflictType.MANDATORY_OVER_BUDGET: "[BUDGET]",
            ConflictType.CATEGORY_STACK:        "[STACK]",
            ConflictType.TIME_OVERLAP:          "[TIME OVERLAP]",
        }

        # Collect all warnings across pets
        for plan in all_plans.values():
            for w in plan.warnings:
                st.warning(w)

        # -----------------------------------------------------------------------
        # Scheduled tasks table (all pets combined, with filters)
        # -----------------------------------------------------------------------
        any_scheduled = any(p.scheduled_tasks for p in all_plans.values())
        if any_scheduled:
            st.subheader("Scheduled tasks")

            # --- Completion progress bar ---
            all_scheduled = [s for p in all_plans.values() for s in p.scheduled_tasks]
            total_tasks = len(all_scheduled)
            completed_tasks = sum(
                1 for pid, p in all_plans.items()
                for s in p.scheduled_tasks
                if st.session_state.get(f"task_status_{pid}_{s.task.id}", "to-do") == "done"
            )
            skipped_tasks = sum(
                1 for pid, p in all_plans.items()
                for s in p.scheduled_tasks
                if st.session_state.get(f"task_status_{pid}_{s.task.id}", "to-do") == "skip"
            )
            done_pct  = int(completed_tasks / total_tasks * 100) if total_tasks else 0
            skip_pct  = int(skipped_tasks  / total_tasks * 100) if total_tasks else 0
            todo_tasks = total_tasks - completed_tasks - skipped_tasks
            st.markdown(
                f"<div style='margin-bottom:12px'>"
                f"<div style='display:flex;justify-content:space-between;font-size:13px;margin-bottom:4px'>"
                f"<span>Daily progress</span>"
                f"<span style='font-weight:600'>"
                f"<span style='color:#4a9eff'>{completed_tasks} done</span>"
                f"{'&nbsp;·&nbsp;<span style=\"color:#ffc107\">' + str(skipped_tasks) + ' skipped</span>' if skipped_tasks else ''}"
                f"{'&nbsp;·&nbsp;' + str(todo_tasks) + ' to-do' if todo_tasks else ''}"
                f"</span>"
                f"</div>"
                f"<div style='display:flex;background:#e9ecef;border-radius:6px;height:10px;overflow:hidden'>"
                f"<div style='background:#4a9eff;width:{done_pct}%;height:10px'></div>"
                f"<div style='background:#ffc107;width:{skip_pct}%;height:10px'></div>"
                f"</div>"
                f"</div>",
                unsafe_allow_html=True,
            )

            # --- Filter controls ---
            col_sort, col_filter_status, col_filter_pet = st.columns([2, 2, 3])

            with col_sort:
                sort_option = st.selectbox(
                    "Sort by",
                    options=["Order added", "Time", "Priority"],
                    key="task_sort",
                )
            with col_filter_status:
                status_filter = st.multiselect(
                    "Show statuses",
                    options=["All"] + STATUS_OPTIONS,
                    default=["All"],
                    key="status_filter",
                )
            with col_filter_pet:
                all_pet_names = [plan.pet.name.title() for plan in all_plans.values()]
                pet_filter = st.multiselect(
                    "Show pets",
                    options=["All"] + all_pet_names,
                    default=["All"],
                    key="pet_filter",
                )

            # Build flat list of (plan, scheduled_task) pairs for selected pets
            show_all_statuses = "All" in status_filter or not status_filter
            show_all_pets = "All" in pet_filter or not pet_filter
            selected_statuses = (
                {STATUS_MAP[l] for l in STATUS_OPTIONS}
                if show_all_statuses
                else {STATUS_MAP[l] for l in status_filter if l != "All"}
            )
            selected_pet_names = (
                {n.lower() for n in all_pet_names}
                if show_all_pets
                else {n.lower() for n in pet_filter if n != "All"}
            )

            rows: list[tuple] = []   # (plan, scheduled_task)
            for plan in all_plans.values():
                if plan.pet.name.lower() not in selected_pet_names:
                    continue
                tasks_in_plan = plan.scheduled_tasks
                if sort_option == "Time":
                    tasks_in_plan = plan.get_tasks_sorted_by_time()
                elif sort_option == "Priority":
                    tasks_in_plan = sorted(
                        plan.scheduled_tasks,
                        key=lambda s: s.task.priority.value,
                        reverse=True,
                    )
                for s in tasks_in_plan:
                    if s.status in selected_statuses:
                        rows.append((plan, s))

            # Secondary sort by time across all pets when "Time" is selected
            if sort_option == "Time" and rows:
                rows.sort(key=lambda ps: ps[1].start_time)

            if rows:
                # Build per-plan set of over-budget task IDs for badges
                over_budget_by_plan = {
                    pid: {
                        c.task_id for c in p.conflicts
                        if c.conflict_type == ConflictType.MANDATORY_OVER_BUDGET and c.task_id
                    }
                    for pid, p in all_plans.items()
                }

                # Column headers — mirror the [5, 2] column split used in each row
                hcol_info, hcol_status = st.columns([5, 2])
                hcol_info.markdown(
                    "<div style='display:flex; align-items:center; gap:16px; "
                    "padding:6px 10px; font-weight:bold; font-size:14px; margin:0'>"
                    "<span style='flex:2'>Task</span>"
                    "<span style='flex:1.5'>Pet</span>"
                    "<span style='flex:2'>Time</span>"
                    "<span style='flex:1'>Min</span>"
                    "<span style='flex:1'>Priority</span>"
                    "</div>",
                    unsafe_allow_html=True,
                )
                hcol_status.markdown(
                    "<p style='font-weight:bold; font-size:14px; "
                    "padding:6px 0; margin:0; line-height:1.4'>Status</p>",
                    unsafe_allow_html=True,
                )
                st.markdown(
                    "<hr style='margin:4px 0 6px 0; border-color:#dee2e6'>",
                    unsafe_allow_html=True,
                )

                for plan, s in rows:
                    # Unique key per pet+task to avoid clashes across pets
                    key = f"task_status_{plan.pet.id}_{s.task.id}"
                    if key not in st.session_state:
                        st.session_state[key] = REVERSE_STATUS_MAP.get(s.status, "to-do")

                    current_label = st.session_state.get(key, "to-do")
                    border_color = (
                        "#28a745" if current_label == "done"
                        else "#ffc107" if current_label == "skip"
                        else "#dee2e6"
                    )

                    over_budget_ids = over_budget_by_plan.get(plan.pet.id, set())
                    badge = (
                        "<span style='background:#dc3545;color:white;border-radius:3px;"
                        "padding:1px 5px;font-size:11px;margin-left:6px'>over budget</span>"
                        if s.task.id in over_budget_ids else ""
                    )

                    c_info, c_status = st.columns([5, 2])
                    c_info.markdown(
                        f"<div style='display:flex; gap:16px; "
                        f"border-left:4px solid {border_color}; "
                        f"border-radius:4px; padding:6px 10px; align-items:center'>"
                        f"<span style='flex:2'>{s.task.name}{badge}</span>"
                        f"<span style='flex:1.5; color:#aaa; font-size:12px'>{plan.pet.name.title()}</span>"
                        f"<span style='flex:2; color:#fff'>"
                        f"{format_time_12hr(s.start_time)} – {format_time_12hr(s.end_time)}"
                        f"</span>"
                        f"<span style='flex:1; color:#fff'>{s.task.duration_minutes} min</span>"
                        f"<span style='flex:1; color:#fff'>{s.task.priority.name}</span>"
                        f"</div>",
                        unsafe_allow_html=True,
                    )

                    chosen = c_status.selectbox(
                        label="status",
                        options=STATUS_OPTIONS,
                        index=STATUS_OPTIONS.index(st.session_state[key]),
                        key=key,
                        label_visibility="collapsed",
                    )

                    # Sync selection → model
                    new_status = STATUS_MAP[chosen]
                    if new_status != s.status:
                        s.status = new_status
                        if new_status == TaskStatus.SKIPPED:
                            if s.task not in plan.skipped_tasks:
                                plan.skipped_tasks.append(s.task)
                        else:
                            plan.skipped_tasks = [
                                t for t in plan.skipped_tasks if t.id != s.task.id
                            ]
            else:
                st.info("No tasks match the selected filters.")
        else:
            st.info("No tasks could be scheduled within the current budgets.")

        # -----------------------------------------------------------------------
        # Per-pet: skipped, window summary, conflicts, reasoning
        # -----------------------------------------------------------------------
        for plan in all_plans.values():
            st.divider()
            st.markdown(f"### {plan.pet.name.title()}")

            if plan.skipped_tasks:
                st.markdown("**Skipped (will carry over tomorrow)**")
                for t in plan.skipped_tasks:
                    reason = plan.skip_reasons.get(t.id)
                    reason_label = f" — *{reason.value}*" if reason else ""
                    st.write(f"- **{t.name}** [{t.priority.name}]{reason_label}")

            st.markdown("**Window summary**")
            summary = plan.get_window_summary()
            wcol1, wcol2, wcol3 = st.columns(3)
            for col, window_key in zip([wcol1, wcol2, wcol3], ["morning", "afternoon", "evening"]):
                s = summary[window_key]
                used = s["used_minutes"]
                budget = s["budget_minutes"]
                over = used > budget and budget > 0
                fill_pct = min(int(used / budget * 100), 100) if budget > 0 else 0
                bar_color = "#dc3545" if over else "#28a745"
                col.markdown(f"**{window_key.capitalize()}**")
                col.markdown(
                    f"<div style='background:#e9ecef;border-radius:4px;height:8px;margin:4px 0'>"
                    f"<div style='background:{bar_color};width:{fill_pct}%;height:8px;border-radius:4px'></div>"
                    f"</div>"
                    f"<span style='font-size:12px;color:#555'>{used} / {budget} min &nbsp;·&nbsp; {s['tasks']} task(s)"
                    f"{'&nbsp; <span style=\"color:#dc3545\">over by ' + str(used - budget) + ' min</span>' if over else ''}"
                    f"</span>",
                    unsafe_allow_html=True,
                )

            if plan.conflicts:
                with st.expander(f"Conflicts ({len(plan.conflicts)})"):
                    for c in plan.conflicts:
                        label = CONFLICT_LABELS.get(c.conflict_type, "[CONFLICT]")
                        st.markdown(f"`{label}` {c.message}")

            with st.expander("Full plan reasoning"):
                st.text(str(plan))
