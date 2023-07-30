from dateutil.parser import parse
from Foundation import NSDate, NSURL
from CalendarStore import CalCalendarStore, CalEvent
from operator import itemgetter
from collections import defaultdict
import datetime
import things
import time

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

def check_if_in_calendar(task, predicate):
    store = CalCalendarStore.defaultCalendarStore()
    for event in store.eventsWithPredicate_(predicate):
        if task['uuid'] in event.url().absoluteString():
            return True
    return False
    


def add_to_calendar(tasks, calendar_name):
    store = CalCalendarStore.defaultCalendarStore()
    calendars = store.calendars()
    
    calendar = next((c for c in calendars if c.title() == calendar_name), None)
    if calendar is None:
        print('No calendar found')
        return
    
    # get all events in the calendar
    predicate = CalCalendarStore.eventPredicateWithStartDate_endDate_calendars_(NSDate.date(), NSDate.dateWithTimeIntervalSinceNow_(60*60*24*365), [calendar])
    # For now I will remove all events in the calendar, but in the future maybe I will add a check to see if the event is already in the calendar and if anything has changed
    for event in store.eventsWithPredicate_(predicate):
        store.removeEvent_span_error_(event, 0, None)

    for task in tasks:
        event = CalEvent.event()
        
        event.setCalendar_(calendar)
        # Because upcoming events will always have a start date
        if calendar_name == 'Things Upcoming':
            start_date = parse(task['start_date'])
        elif calendar_name == 'Things Logbook':
            start_date = parse(task['stop_date'])

        event.setStartDate_(NSDate.dateWithTimeIntervalSince1970_(start_date.timestamp()))
        if task['deadline']:
            deadline = parse(task['deadline'])
            event.setEndDate_(NSDate.dateWithTimeIntervalSince1970_(deadline.timestamp()))
        else:
            event.setEndDate_(NSDate.dateWithTimeIntervalSince1970_(start_date.timestamp()))

        url = f"things:///show?id={task['uuid']}"
        event.setTitle_(task['title'])
        event.setNotes_(task['notes'] if task['notes'] else None)
        event.setUrl_(NSURL.URLWithString_(url))

        event.setIsAllDay_(True)

        res, err = store.saveEvent_span_error_(event, 0, None)
        if not res:
            print(err.localizedDescription())
            return

def main_task():
    logbook = things.logbook()
    logbook_md = logbook_to_md(logbook)
    with open('logbook.md', 'w') as f:
        f.write(logbook_md)
    upcoming = things.upcoming()
    add_to_calendar(upcoming, 'Things Upcoming')

def execute_main_task_every_interval(interval):
    while True:
        main_task()
        time.sleep(interval)

if __name__ == "__main__":
    execute_main_task_every_interval(60)
