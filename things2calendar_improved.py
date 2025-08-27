from Foundation import NSDate, NSURL
from dateutil.parser import parse
from CalendarStore import CalCalendarStore, CalEvent
from operator import itemgetter
from collections import defaultdict
import datetime
import things
import time
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def logbook_to_md(data):
    sorted_data = sorted(data, key = itemgetter('stop_date'), reverse=True)

    md_dict = defaultdict(lambda: defaultdict(list))

    for entry in sorted_data:
        todo_link = f"[{entry['title']}](things:///show?id={entry['uuid']})"
        stop_date = datetime.datetime.strptime(entry['stop_date'], '%Y-%m-%d %H:%M:%S').strftime('%Y-%m-%d')

        if entry['status'] == 'completed':
            md_str = f"- [x] {todo_link}"
        elif entry['status'] == 'canceled':
            md_str = f"- [-] {todo_link}"
         
        if 'tags' in entry:
            for tag in entry['tags']:
                md_str += f" #{tag}"

        if 'project' in entry:
            project_link = f"[{entry['project_title']}](things:///show?id={entry['project']})"
            group_key = project_link
        elif 'area' in entry:
            area_link = f"[{entry['area_title']}](things:///show?id={entry['area']})"
            group_key = area_link
        else:
            group_key = 'No project or area'


        if 'notes' in entry:
            if entry['notes'] == '':
                pass
            else:
                md_str += "\n"
                notes = '\n'.join('\t' + line for line in entry['notes'].splitlines())
                md_str += notes

        md_dict[stop_date][group_key].append(md_str)

    final_md = "# Things3 Logbook\n"
    for date, groups in md_dict.items():
        final_md += f"\n\n## [[{date}]]\n"
        for group, todos in groups.items():
            if group == 'No project or area':
                final_md += '\n'.join(todos)
        for group, todos in groups.items():
            if group != 'No project or area':
                final_md += f"\n### {group}\n"
                final_md += '\n'.join(todos)

    return final_md

def get_existing_events(calendar, start_date=None, end_date=None):
    """Get existing events from calendar within date range."""
    store = CalCalendarStore.defaultCalendarStore()
    
    if start_date is None:
        start_date = NSDate.dateWithTimeIntervalSinceNow_(-60*60*24*365)  # 1 year ago
    if end_date is None:
        end_date = NSDate.dateWithTimeIntervalSinceNow_(60*60*24*365)  # 1 year ahead
    
    predicate = CalCalendarStore.eventPredicateWithStartDate_endDate_calendars_(
        start_date, end_date, [calendar]
    )
    
    events = store.eventsWithPredicate_(predicate)
    
    # Create a dictionary of events by Things UUID
    events_dict = {}
    for event in events:
        url = event.url()
        if url:
            url_string = url.absoluteString()
            if 'things:///show?id=' in url_string:
                uuid = url_string.split('things:///show?id=')[1]
                events_dict[uuid] = event
    
    return events_dict

def task_to_event_dict(task, calendar_name, is_from_today=False):
    """Convert a Things task to event properties dictionary.
    
    Args:
        task: The Things task dictionary
        calendar_name: Name of the calendar to sync to
        is_from_today: Whether this task came from things.today()
    """
    event_dict = {}
    
    # Set dates based on calendar type
    if calendar_name == 'Things Upcoming':
        # Use start_date if available, otherwise use today for today's tasks
        if 'start_date' in task and task['start_date']:
            start_date = parse(task['start_date'])
            # If this is from today() and the start date is in the past, use today instead
            if is_from_today:
                today = datetime.datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
                if start_date < today:
                    start_date = today
        else:
            # This is a today task without a specific start date
            start_date = datetime.datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    elif calendar_name == 'Things Logbook':
        if 'stop_date' not in task or not task['stop_date']:
            return None
        start_date = parse(task['stop_date'])
    else:
        return None
    
    event_dict['start_date'] = start_date
    
    # Set end date
    if task.get('deadline'):
        deadline = parse(task['deadline'])
        event_dict['end_date'] = deadline
    else:
        event_dict['end_date'] = start_date
    
    # Set other properties
    event_dict['title'] = task.get('title', 'Untitled')
    event_dict['notes'] = task.get('notes', '')
    event_dict['uuid'] = task['uuid']
    event_dict['url'] = f"things:///show?id={task['uuid']}"
    
    return event_dict

def should_preserve_manual_edits(existing_event):
    """Check if an event has been manually edited and should be preserved.
    
    We preserve events that have been manually modified by checking:
    - If isAllDay property has been changed from True
    - This is a simple way to detect manual modifications
    """
    # If the event is no longer all-day, it was manually edited
    if not existing_event.isAllDay():
        return True
    
    return False

def events_are_different(existing_event, new_event_dict):
    """Check if an existing calendar event differs from new event data.
    
    Now preserves manually edited events by checking if they've been modified.
    """
    # Check if this event has been manually edited
    if should_preserve_manual_edits(existing_event):
        # Don't update manually edited events
        return False
    
    # For non-manually edited events, check if Things data has changed
    # Check title
    if existing_event.title() != new_event_dict['title']:
        return True
    
    # Check notes
    existing_notes = existing_event.notes() or ''
    new_notes = new_event_dict['notes'] or ''
    if existing_notes != new_notes:
        return True
    
    # Check dates (comparing timestamps to avoid timezone issues)
    existing_start = existing_event.startDate().timeIntervalSince1970()
    new_start = new_event_dict['start_date'].timestamp()
    if abs(existing_start - new_start) > 60:  # Allow 1 minute tolerance
        return True
    
    existing_end = existing_event.endDate().timeIntervalSince1970()
    new_end = new_event_dict['end_date'].timestamp()
    if abs(existing_end - new_end) > 60:  # Allow 1 minute tolerance
        return True
    
    return False

def sync_to_calendar(tasks, calendar_name, today_task_uuids=None):
    """Intelligently sync tasks to calendar, only updating what's changed.
    
    Args:
        tasks: List of task dictionaries
        calendar_name: Name of the calendar to sync to
        today_task_uuids: Set of UUIDs for tasks that came from things.today()
    """
    if today_task_uuids is None:
        today_task_uuids = set()
    
    store = CalCalendarStore.defaultCalendarStore()
    calendars = store.calendars()
    
    calendar = next((c for c in calendars if c.title() == calendar_name), None)
    if calendar is None:
        logger.error(f'Calendar "{calendar_name}" not found')
        return
    
    # Get existing events
    existing_events = get_existing_events(calendar)
    logger.info(f"Found {len(existing_events)} existing events in {calendar_name}")
    
    # Track which events we've processed
    processed_uuids = set()
    events_added = 0
    events_updated = 0
    events_unchanged = 0
    events_preserved = 0
    
    for task in tasks:
        try:
            # Convert task to event dictionary
            is_from_today = task['uuid'] in today_task_uuids
            event_dict = task_to_event_dict(task, calendar_name, is_from_today)
            if event_dict is None:
                continue
            
            uuid = task['uuid']
            processed_uuids.add(uuid)
            
            # Check if event exists
            if uuid in existing_events:
                existing_event = existing_events[uuid]
                
                # Check if update is needed
                if should_preserve_manual_edits(existing_event):
                    # This event was manually edited, preserve it
                    events_preserved += 1
                    logger.debug(f"Preserving manually edited event: {existing_event.title()}")
                elif events_are_different(existing_event, event_dict):
                    # Update the event
                    existing_event.setTitle_(event_dict['title'])
                    existing_event.setNotes_(event_dict['notes'] if event_dict['notes'] else None)
                    existing_event.setStartDate_(NSDate.dateWithTimeIntervalSince1970_(event_dict['start_date'].timestamp()))
                    existing_event.setEndDate_(NSDate.dateWithTimeIntervalSince1970_(event_dict['end_date'].timestamp()))
                    
                    res, err = store.saveEvent_span_error_(existing_event, 0, None)
                    if res:
                        events_updated += 1
                    else:
                        logger.error(f"Failed to update event for {event_dict['title']}: {err.localizedDescription()}")
                else:
                    events_unchanged += 1
            else:
                # Create new event
                event = CalEvent.event()
                event.setCalendar_(calendar)
                event.setTitle_(event_dict['title'])
                event.setNotes_(event_dict['notes'] if event_dict['notes'] else None)
                event.setStartDate_(NSDate.dateWithTimeIntervalSince1970_(event_dict['start_date'].timestamp()))
                event.setEndDate_(NSDate.dateWithTimeIntervalSince1970_(event_dict['end_date'].timestamp()))
                event.setUrl_(NSURL.URLWithString_(event_dict['url']))
                event.setIsAllDay_(True)
                
                res, err = store.saveEvent_span_error_(event, 0, None)
                if res:
                    events_added += 1
                else:
                    logger.error(f"Failed to add event for {event_dict['title']}: {err.localizedDescription()}")
                    
        except Exception as e:
            logger.error(f"Error processing task {task.get('title', 'Unknown')}: {e}")
    
    # Remove events that no longer exist in Things
    events_removed = 0
    for uuid, event in existing_events.items():
        if uuid not in processed_uuids:
            res, err = store.removeEvent_span_error_(event, 0, None)
            if res:
                events_removed += 1
            else:
                logger.error(f"Failed to remove event: {err.localizedDescription()}")
    
    logger.info(f"{calendar_name}: Added {events_added}, Updated {events_updated}, Unchanged {events_unchanged}, Removed {events_removed}, Preserved (manually edited): {events_preserved}")

def main_task():
    """Main synchronization task."""
    try:
        # Sync upcoming tasks (includes scheduled tasks)
        logger.info("Syncing upcoming tasks...")
        upcoming = things.upcoming()
        
        # Also get today's tasks and merge them with upcoming
        logger.info("Getting today's tasks...")
        today_tasks = things.today()
        
        # Track which tasks came from today()
        today_task_uuids = {task['uuid'] for task in today_tasks}
        
        # Combine both lists, removing duplicates by UUID
        all_tasks = {task['uuid']: task for task in upcoming}
        for task in today_tasks:
            if task['uuid'] not in all_tasks:
                all_tasks[task['uuid']] = task
        
        # Sync combined tasks to the single calendar
        combined_tasks = list(all_tasks.values())
        logger.info(f"Syncing {len(combined_tasks)} total tasks (upcoming + today)...")
        sync_to_calendar(combined_tasks, 'Things Upcoming', today_task_uuids)
        
        # Optionally sync logbook (uncomment if needed)
        # logger.info("Syncing logbook...")
        # logbook = things.logbook()
        # sync_to_calendar(logbook, 'Things Logbook')
        
    except Exception as e:
        logger.error(f"Error in main task: {e}")

def execute_main_task_every_interval(interval):
    """Execute the main task at regular intervals."""
    logger.info(f"Starting Things to Calendar sync, running every {interval} seconds")
    
    while True:
        try:
            main_task()
            logger.info(f"Sync completed. Next sync in {interval} seconds")
        except KeyboardInterrupt:
            logger.info("Sync stopped by user")
            break
        except Exception as e:
            logger.error(f"Unexpected error: {e}")
        
        time.sleep(interval)

if __name__ == "__main__":
    # Run every 60 seconds (adjust as needed)
    execute_main_task_every_interval(60)