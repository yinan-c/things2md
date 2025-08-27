#!/usr/bin/env python3
"""
Export Things 3 data to Dida CSV format
Author: Claude
Date: 2025-08-26
"""

import csv
import things
from datetime import datetime
import sys
import os

def format_datetime(dt_string):
    """Convert Things datetime to Dida format (YYYY-MM-DDTHH:MM:SS+0000)"""
    if not dt_string:
        return ""
    
    try:
        # Try full datetime format first
        dt = datetime.strptime(dt_string, "%Y-%m-%d %H:%M:%S")
        return dt.strftime("%Y-%m-%dT%H:%M:%S+0000")
    except:
        try:
            # Try date-only format for start_date and deadline
            dt = datetime.strptime(dt_string, "%Y-%m-%d")
            return dt.strftime("%Y-%m-%dT00:00:00+0000")
        except:
            return ""

def get_status_code(status):
    """Convert Things status to Dida status code"""
    status_map = {
        'incomplete': '0',
        'completed': '2',
        'canceled': '-1'
    }
    return status_map.get(status, '0')

def get_priority(task):
    """Map Things task properties to Dida priority (0-5)"""
    # Things doesn't have explicit priority, but we can use start date
    start = task.get('start', '')
    if start == 'Today':
        return '5'
    elif task.get('deadline'):
        return '3'
    else:
        return '0'

def format_tags(tags):
    """Format tags list to comma-separated string"""
    if not tags:
        return ""
    return ", ".join(tags)

def export_to_dida_csv(output_file="Things_to_Dida_export.csv"):
    """Export Things data to Dida CSV format"""
    
    print("Fetching data from Things 3...")
    
    # Get all data from Things
    todos = things.todos()
    logbook = things.logbook()
    projects = things.projects()
    areas = things.areas()
    headings = things.tasks(type='heading', status=None)  # Get ALL headings including completed
    
    # Separate completed projects from regular tasks in logbook
    logbook_tasks = [t for t in logbook if t.get('type') != 'project']
    logbook_projects = [t for t in logbook if t.get('type') == 'project']
    
    all_tasks = todos + logbook_tasks
    all_projects = projects + logbook_projects  # Include completed projects
    
    print(f"Found {len(all_tasks)} tasks, {len(all_projects)} projects ({len(logbook_projects)} completed), {len(areas)} areas, {len(headings)} headings")
    
    # Create project and area lookup (include completed projects from logbook)
    project_lookup = {p['uuid']: p['title'] for p in all_projects}
    area_lookup = {a['uuid']: a['title'] for a in areas}
    
    # Create heading lookup with project info
    heading_lookup = {}
    for h in headings:
        heading_lookup[h['uuid']] = {
            'title': h.get('title', ''),
            'project': h.get('project', ''),
            'project_title': h.get('project_title', ''),
            'area': h.get('area', ''),
            'area_title': h.get('area_title', '')
        }
    
    # Prepare CSV rows
    rows = []
    
    # Add header rows (Dida format)
    with open(output_file, 'w', newline='', encoding='utf-8-sig') as csvfile:
        # Write BOM for UTF-8
        csvfile.write('\ufeff')
        
        # Write header information
        csvfile.write(f'"Date: {datetime.now().strftime("%Y-%m-%d")}+0000"\n')
        csvfile.write('"Version: 7.1"\n')
        csvfile.write('"Status: \n0 Normal\n1 Completed\n2 Archived"\n')
        
        # CSV Headers
        fieldnames = [
            "Folder Name", "List Name", "Title", "Kind", "Tags", "Content", 
            "Is Check list", "Start Date", "Due Date", "Reminder", "Repeat",
            "Priority", "Status", "Created Time", "Completed Time", "Order",
            "Timezone", "Is All Day", "Is Floating", "Column Name",
            "Column Order", "View Mode", "taskId", "parentId"
        ]
        
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        writer.writeheader()
        
        task_id = 1
        
        # Process all tasks
        for task in all_tasks:
            # Determine folder (area) and list (project)
            folder_name = ""
            list_name = "Inbox"
            
            # First check if task has a heading (heading -> project -> area)
            if 'heading' in task and task['heading'] and task['heading'] in heading_lookup:
                heading_info = heading_lookup[task['heading']]
                # Get project from heading
                if heading_info['project']:
                    list_name = heading_info['project_title'] or project_lookup.get(heading_info['project'], "Inbox")
                    # Find the area for this project
                    project_obj = next((p for p in all_projects if p['uuid'] == heading_info['project']), None)
                    if project_obj:
                        if 'area' in project_obj:
                            folder_name = area_lookup.get(project_obj['area'], "")
                        elif 'area_title' in project_obj:
                            folder_name = project_obj['area_title']
            # Then check if task has a project directly
            elif 'project' in task:
                list_name = project_lookup.get(task['project'], "Inbox")
                # Find the area for this project
                project_obj = next((p for p in all_projects if p['uuid'] == task['project']), None)
                if project_obj:
                    if 'area' in project_obj:
                        folder_name = area_lookup.get(project_obj['area'], "")
                    elif 'area_title' in project_obj:
                        folder_name = project_obj['area_title']
            elif 'project_title' in task:
                list_name = task['project_title']
                # Try to get area from task's area_title if available
                if 'area_title' in task:
                    folder_name = task['area_title']
            # If no project, check if task has an area directly
            elif 'area' in task:
                folder_name = area_lookup.get(task['area'], "")
                list_name = f"{folder_name} General" if folder_name else "Inbox"
            elif 'area_title' in task:
                folder_name = task['area_title']
                list_name = f"{folder_name} General" if folder_name else "Inbox"
            
            # Handle checklist items
            is_checklist = "N"
            content = task.get('notes', '')
            
            if 'checklist' in task:
                # checklist can be True (has checklist) or a list of items
                if isinstance(task['checklist'], list):
                    is_checklist = "Y"
                    checklist_items = []
                    for item in task['checklist']:
                        prefix = "▪" if item.get('status') == 'completed' else "▫"
                        checklist_items.append(f"{prefix}{item.get('title', '')}")
                    if checklist_items:
                        content = content + "\n" + "\n".join(checklist_items) if content else "\n".join(checklist_items)
                elif task['checklist'] == True:
                    is_checklist = "Y"
                    # Fetch actual checklist items using the API
                    checklist_items = []
                    try:
                        items = things.checklist_items(task['uuid'])
                        for item in items:
                            prefix = "▪" if item.get('status') == 'completed' else "▫"
                            checklist_items.append(f"{prefix}{item.get('title', '')}")
                        if checklist_items:
                            content = content + "\n" + "\n".join(checklist_items) if content else "\n".join(checklist_items)
                    except:
                        pass  # If fetching fails, continue without checklist items
            
            # Format dates
            start_date = ""
            if task.get('start_date'):
                start_date = format_datetime(task['start_date'])
            
            due_date = ""
            if task.get('deadline'):
                due_date = format_datetime(task['deadline'])
            
            completed_time = ""
            if task.get('stop_date'):
                completed_time = format_datetime(task['stop_date'])
            
            created_time = format_datetime(task.get('created', ''))
            
            # Get heading title for Column Name
            column_name = ""
            if 'heading_title' in task and task['heading_title']:
                column_name = task['heading_title']
            
            # Build row
            row = {
                "Folder Name": folder_name,
                "List Name": list_name,
                "Title": task.get('title', 'Untitled'),
                "Kind": "CHECKLIST" if is_checklist == "Y" else "TEXT",
                "Tags": format_tags(task.get('tags', [])),
                "Content": content,
                "Is Check list": is_checklist,
                "Start Date": start_date,
                "Due Date": due_date,
                "Reminder": "",
                "Repeat": "",
                "Priority": get_priority(task),
                "Status": get_status_code(task.get('status', 'incomplete')),
                "Created Time": created_time,
                "Completed Time": completed_time,
                "Order": str(task.get('index', 0)),
                "Timezone": "Europe/London",
                "Is All Day": "true" if due_date and not "T" in due_date else "false",
                "Is Floating": "false",
                "Column Name": column_name,
                "Column Order": "0",
                "View Mode": "list",
                "taskId": str(task_id),
                "parentId": ""
            }
            
            writer.writerow(row)
            task_id += 1
        
        # Add projects as lists (optional - Dida doesn't import these as separate entities)
        # But we can add them as placeholder tasks to preserve the project structure
        for project in all_projects:
            # Export all projects, including completed ones
            # Projects belong to areas (folders)
            folder_name = ""
            if 'area' in project:
                folder_name = area_lookup.get(project['area'], "")
            elif 'area_title' in project:
                folder_name = project['area_title']
            
            # Project itself becomes a list under its area
            row = {
                "Folder Name": folder_name,
                "List Name": project['title'],
                "Title": f"[PROJECT] {project['title']}",
                "Kind": "NOTE",
                "Tags": format_tags(project.get('tags', [])),
                "Content": project.get('notes', ''),
                "Is Check list": "N",
                "Start Date": format_datetime(project.get('start_date', '')),
                "Due Date": format_datetime(project.get('deadline', '')),
                "Reminder": "",
                "Repeat": "",
                "Priority": "0",
                "Status": get_status_code(project.get('status', 'incomplete')),
                "Created Time": format_datetime(project.get('created', '')),
                "Completed Time": format_datetime(project.get('stop_date', '')),
                "Order": str(project.get('index', 0)),
                "Timezone": "Europe/London",
                "Is All Day": "false",
                "Is Floating": "false",
                "Column Name": "",
                "Column Order": "0",
                "View Mode": "list",
                "taskId": str(task_id),
                "parentId": ""
            }
            
            writer.writerow(row)
            task_id += 1
    
    print(f"\nExport completed successfully!")
    print(f"Output file: {output_file}")
    print(f"Total items exported: {task_id - 1}")
    
    return output_file

if __name__ == "__main__":
    # Check if output filename is provided
    output_file = sys.argv[1] if len(sys.argv) > 1 else "Things_to_Dida_export.csv"
    
    try:
        export_to_dida_csv(output_file)
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)
