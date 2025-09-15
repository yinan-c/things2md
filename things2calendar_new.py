#!/usr/bin/env python3
"""
Sync Things 3 tasks to Calendar app with intelligent update handling.
- Today & Upcoming: Combined in "Things Upcoming" calendar
- Logbook: "Things Logbook" calendar with date/time preservation
- Deadlines: "Things Deadlines" calendar as all-day events
"""

from Foundation import NSDate, NSURL
from dateutil.parser import parse
from CalendarStore import CalCalendarStore, CalEvent
import datetime
import things
import time


def get_calendar(calendar_name):
    """Get existing calendar."""
    store = CalCalendarStore.defaultCalendarStore()
    calendars = store.calendars()
    
    calendar = next((c for c in calendars if c.title() == calendar_name), None)
    if calendar is None:
        print(f'Calendar "{calendar_name}" not found. Please create it manually in the Calendar app.')
        return None
    
    return calendar


def get_existing_events(calendar, start_date, end_date):
    """Get all existing events in a date range, indexed by UUID."""
    store = CalCalendarStore.defaultCalendarStore()
    
    start = NSDate.dateWithTimeIntervalSince1970_(start_date.timestamp())
    end = NSDate.dateWithTimeIntervalSince1970_(end_date.timestamp())
    
    predicate = CalCalendarStore.eventPredicateWithStartDate_endDate_calendars_(
        start, end, [calendar]
    )
    
    events_by_uuid = {}
    for event in store.eventsWithPredicate_(predicate):
        if event.url():
            url_str = event.url().absoluteString()
            if 'id=' in url_str:
                uuid = url_str.split('id=')[1]
                events_by_uuid[uuid] = event
    
    return events_by_uuid


def update_event_if_changed(existing_event, task, event_type="upcoming"):
    """
    Update an existing event only if needed.
    Returns True if updated, False if no changes needed.
    """
    store = CalCalendarStore.defaultCalendarStore()
    needs_update = False
    
    # For logbook events, check if basic properties match
    if event_type == "logbook":
        # Logbook events are considered up-to-date if they exist
        # We only need to ensure the date/time is correct
        if task.get('stop_date'):
            stop_date = parse(task['stop_date'])
            existing_start = datetime.datetime.fromtimestamp(existing_event.startDate().timeIntervalSince1970())
            
            # Only update if date/time is different
            if abs((existing_start - stop_date).total_seconds()) > 60:  # More than 1 minute difference
                existing_event.setStartDate_(NSDate.dateWithTimeIntervalSince1970_(stop_date.timestamp()))
                end_date = stop_date + datetime.timedelta(minutes=30)
                existing_event.setEndDate_(NSDate.dateWithTimeIntervalSince1970_(end_date.timestamp()))
                needs_update = True
    
    elif event_type == "upcoming":
        # For upcoming/today, check if the date needs updating
        today = datetime.datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        
        # Determine what the date should be
        if task.get('_is_today'):  # We'll mark today tasks
            target_date = today
        elif task.get('start_date'):
            target_date = parse(task['start_date']).replace(hour=0, minute=0, second=0, microsecond=0)
        else:
            target_date = today + datetime.timedelta(days=1)
        
        existing_start_date = datetime.datetime.fromtimestamp(existing_event.startDate().timeIntervalSince1970())
        existing_end_date = datetime.datetime.fromtimestamp(existing_event.endDate().timeIntervalSince1970())
        
        # Check if on same day
        if existing_start_date.date() != target_date.date():
            # Date is different, need to move to correct date
            # But preserve time edits if event is on the same day and not all-day
            if not existing_event.isAllDay():
                # User has set specific times, preserve the duration
                duration = existing_end_date - existing_start_date
                # Combine target date with existing start time
                new_start = datetime.datetime.combine(target_date.date(), existing_start_date.time())
                new_end = new_start + duration
                existing_event.setStartDate_(NSDate.dateWithTimeIntervalSince1970_(new_start.timestamp()))
                existing_event.setEndDate_(NSDate.dateWithTimeIntervalSince1970_(new_end.timestamp()))
                existing_event.setIsAllDay_(False)
            else:
                # Was all-day, keep it all-day
                existing_event.setStartDate_(NSDate.dateWithTimeIntervalSince1970_(target_date.timestamp()))
                existing_event.setEndDate_(NSDate.dateWithTimeIntervalSince1970_(target_date.timestamp()))
                existing_event.setIsAllDay_(True)
            needs_update = True
        elif not existing_event.isAllDay():
            # Same day but user has edited to non-all-day - preserve their edit
            # No update needed for the time
            pass
        
        # Update title if changed (but preserve user edits)
        existing_title = existing_event.title() or ""
        if existing_title != task['title']:
            # Check if it's a user edit or just outdated
            if not existing_title or existing_title == task.get('_old_title', ''):
                existing_event.setTitle_(task['title'])
                needs_update = True
    
    elif event_type == "deadline":
        # For deadlines, ensure date matches
        if task.get('deadline'):
            deadline_date = parse(task['deadline']).replace(hour=0, minute=0, second=0, microsecond=0)
            existing_date = datetime.datetime.fromtimestamp(existing_event.startDate().timeIntervalSince1970())
            
            if existing_date.date() != deadline_date.date():
                existing_event.setStartDate_(NSDate.dateWithTimeIntervalSince1970_(deadline_date.timestamp()))
                existing_event.setEndDate_(NSDate.dateWithTimeIntervalSince1970_(deadline_date.timestamp()))
                existing_event.setIsAllDay_(True)
                needs_update = True
    
    if needs_update:
        res, err = store.saveEvent_span_error_(existing_event, 0, None)
        if not res:
            print(f"    Error updating event: {err.localizedDescription() if err else 'Unknown error'}")
            return False
    
    return needs_update


def create_new_event(task, calendar, event_type="upcoming"):
    """Create a new calendar event for a task."""
    store = CalCalendarStore.defaultCalendarStore()
    event = CalEvent.event()
    event.setCalendar_(calendar)
    
    if event_type == "logbook":
        if not task.get('stop_date'):
            return False
        
        stop_date = parse(task['stop_date'])
        event.setStartDate_(NSDate.dateWithTimeIntervalSince1970_(stop_date.timestamp()))
        end_date = stop_date + datetime.timedelta(minutes=30)
        event.setEndDate_(NSDate.dateWithTimeIntervalSince1970_(end_date.timestamp()))
        event.setIsAllDay_(False)
        
        # Set title with status indicator
        status_prefix = ""
        if task['status'] == 'completed':
            status_prefix = "✓ "
        elif task['status'] == 'canceled':
            status_prefix = "✗ "
        
        event.setTitle_(f"{status_prefix}{task['title']}")
        
        # Build notes
        notes_parts = []
        if task.get('notes'):
            notes_parts.append(task['notes'])
        if task.get('project_title'):
            notes_parts.append(f"Project: {task['project_title']}")
        elif task.get('area_title'):
            notes_parts.append(f"Area: {task['area_title']}")
        
        event.setNotes_('\n'.join(notes_parts) if notes_parts else '')
        
    elif event_type == "upcoming":
        today = datetime.datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        
        if task.get('_is_today'):
            start_date = today
        elif task.get('start_date'):
            start_date = parse(task['start_date'])
        else:
            start_date = today + datetime.timedelta(days=1)
        
        event.setStartDate_(NSDate.dateWithTimeIntervalSince1970_(start_date.timestamp()))
        event.setEndDate_(NSDate.dateWithTimeIntervalSince1970_(start_date.timestamp()))
        event.setIsAllDay_(True)
        event.setTitle_(task['title'])
        event.setNotes_(task.get('notes', '') or '')
        
    elif event_type == "deadline":
        if not task.get('deadline'):
            return False
        
        deadline_date = parse(task['deadline'])
        event.setStartDate_(NSDate.dateWithTimeIntervalSince1970_(deadline_date.timestamp()))
        event.setEndDate_(NSDate.dateWithTimeIntervalSince1970_(deadline_date.timestamp()))
        event.setIsAllDay_(True)
        event.setTitle_(f"⚑ {task['title']}")
        
        # Build notes
        notes_parts = []
        if task.get('notes'):
            notes_parts.append(task['notes'])
        if task.get('project_title'):
            notes_parts.append(f"Project: {task['project_title']}")
        elif task.get('area_title'):
            notes_parts.append(f"Area: {task['area_title']}")
        
        event.setNotes_('\n'.join(notes_parts) if notes_parts else '')
    
    # Set URL for all event types
    url = f"things:///show?id={task['uuid']}"
    event.setUrl_(NSURL.URLWithString_(url))
    
    # Save the event
    res, err = store.saveEvent_span_error_(event, 0, None)
    if not res:
        print(f"    Error creating event for {task['title']}: {err.localizedDescription() if err else 'Unknown error'}")
        return False
    
    return True


def sync_upcoming_and_today(calendar_name="Things Upcoming"):
    """Sync today and upcoming tasks to calendar."""
    store = CalCalendarStore.defaultCalendarStore()
    calendar = get_calendar(calendar_name)
    if not calendar:
        return
    
    print(f"  Getting tasks from Things...")
    # Get all tasks
    today_tasks = things.today()
    upcoming_tasks = things.upcoming()
    
    # Combine tasks, keeping track of which are from today
    all_tasks = []
    today_uuids = set()
    
    # Add today tasks with marker
    for task in today_tasks:
        task['_is_today'] = True
        all_tasks.append(task)
        today_uuids.add(task['uuid'])
    
    # Add upcoming tasks that aren't already in today
    for task in upcoming_tasks:
        if task['uuid'] not in today_uuids:
            task['_is_today'] = False
            all_tasks.append(task)
    
    print(f"  Processing {len(all_tasks)} tasks...")
    
    # Get existing events in relevant date range (-1 to +4 years)
    today = datetime.datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    past_date = today - datetime.timedelta(days=3)  # -1 year
    future_date = today + datetime.timedelta(days=365)  # +4 years
    existing_events = get_existing_events(calendar, past_date, future_date)
    
    processed_uuids = set()
    created_count = 0
    updated_count = 0
    
    for task in all_tasks:
        processed_uuids.add(task['uuid'])
        
        if task['uuid'] in existing_events:
            # Update existing event if needed
            if update_event_if_changed(existing_events[task['uuid']], task, "upcoming"):
                updated_count += 1
        else:
            # Create new event
            if create_new_event(task, calendar, "upcoming"):
                created_count += 1
    
    # Remove events no longer in Things
    removed_count = 0
    for uuid, event in existing_events.items():
        if uuid not in processed_uuids:
            store.removeEvent_span_error_(event, 0, None)
            removed_count += 1
    
    print(f"    Created: {created_count}, Updated: {updated_count}, Removed: {removed_count}")


def sync_logbook(calendar_name="Things Logbook"):
    """Sync logbook tasks to calendar with date/time preservation."""
    store = CalCalendarStore.defaultCalendarStore()
    calendar = get_calendar(calendar_name)
    if not calendar:
        return
    
    print(f"  Getting logbook from Things...")
    logbook_tasks = things.logbook()
    
    # Process entries from -4 to +1 years
    now = datetime.datetime.now()
    cutoff_date = now - datetime.timedelta(days=30)  # -4 years
    future_cutoff = now + datetime.timedelta(days=1)  # +1 year
    
    # Get existing events
    existing_events = get_existing_events(calendar, cutoff_date, future_cutoff)
    
    processed_uuids = set()
    created_count = 0
    updated_count = 0
    skipped_count = 0
    
    print(f"  Processing {len(logbook_tasks)} logbook entries...")
    
    for task in logbook_tasks:
        if not task.get('stop_date'):
            continue
        
        try:
            stop_date = parse(task['stop_date'])
            if not (cutoff_date <= stop_date <= future_cutoff):
                continue
        except:
            continue
        
        processed_uuids.add(task['uuid'])
        
        if task['uuid'] in existing_events:
            # For logbook, we generally skip existing events unless date needs fixing
            if update_event_if_changed(existing_events[task['uuid']], task, "logbook"):
                updated_count += 1
            else:
                skipped_count += 1
        else:
            # Create new event
            if create_new_event(task, calendar, "logbook"):
                created_count += 1
    
    # Remove events no longer in date range or Things
    removed_count = 0
    for uuid, event in existing_events.items():
        if uuid not in processed_uuids:
            store.removeEvent_span_error_(event, 0, None)
            removed_count += 1
    
    print(f"    Created: {created_count}, Updated: {updated_count}, Skipped: {skipped_count}, Removed: {removed_count}")


def sync_deadlines(calendar_name="Things Deadlines"):
    """Sync tasks with deadlines to calendar as all-day events."""
    store = CalCalendarStore.defaultCalendarStore()
    calendar = get_calendar(calendar_name)
    if not calendar:
        return
    
    print(f"  Getting deadlines from Things...")
    deadline_tasks = things.deadlines()
    
    print(f"  Processing {len(deadline_tasks)} deadline tasks...")
    
    # Get existing events in relevant date range (-1 to +4 years)
    today = datetime.datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    past_date = today - datetime.timedelta(days=365)  # -1 year
    future_date = today + datetime.timedelta(days=365)  # +4 years
    existing_events = get_existing_events(calendar, past_date, future_date)
    
    processed_uuids = set()
    created_count = 0
    updated_count = 0
    
    for task in deadline_tasks:
        if not task.get('deadline'):
            continue
        
        processed_uuids.add(task['uuid'])
        
        if task['uuid'] in existing_events:
            # Update existing event if needed
            if update_event_if_changed(existing_events[task['uuid']], task, "deadline"):
                updated_count += 1
        else:
            # Create new event
            if create_new_event(task, calendar, "deadline"):
                created_count += 1
    
    # Remove events no longer in Things
    removed_count = 0
    for uuid, event in existing_events.items():
        if uuid not in processed_uuids:
            store.removeEvent_span_error_(event, 0, None)
            removed_count += 1
    
    print(f"    Created: {created_count}, Updated: {updated_count}, Removed: {removed_count}")


def main_sync(include_logbook=True):
    """Main sync function to update all calendars."""
    print(f"Starting sync at {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    try:
        print("Syncing Upcoming and Today tasks...")
        sync_upcoming_and_today()
        
        if include_logbook:
            print("Syncing Logbook...")
            sync_logbook()
        
        print("Syncing Deadlines...")
        sync_deadlines()
        
        print("Sync completed successfully!")
    except Exception as e:
        print(f"Error during sync: {e}")
        import traceback
        traceback.print_exc()


def run_continuous_sync(interval=60, logbook_interval=1800):
    """
    Run sync continuously at specified intervals.
    
    Args:
        interval: Seconds between syncing Upcoming/Deadlines (default 60 = 1 minute)
        logbook_interval: Seconds between syncing Logbook (default 1800 = 30 minutes)
    """
    last_logbook_sync = 0
    
    while True:
        current_time = time.time()
        
        # Check if it's time to sync logbook
        include_logbook = (current_time - last_logbook_sync) >= logbook_interval
        
        if include_logbook:
            print(f"Including logbook sync (every {logbook_interval/60:.0f} minutes)")
            last_logbook_sync = current_time
        
        main_sync(include_logbook=include_logbook)
        
        print(f"Waiting {interval} seconds until next sync...")
        if not include_logbook:
            next_logbook = logbook_interval - (current_time - last_logbook_sync)
            print(f"  (Next logbook sync in {next_logbook/60:.1f} minutes)")
        print()
        
        time.sleep(interval)


if __name__ == "__main__":
    # Run continuous sync: Upcoming/Deadlines every 60 seconds, Logbook every 30 minutes
    #run_continuous_sync(interval=60, logbook_interval=1800)
    
    # Run one-off sync
    main_sync(include_logbook=True)
