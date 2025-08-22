#!/usr/bin/env python3
import os
import things
import hashlib
from collections import defaultdict
from datetime import datetime

def compute_md5(text):
    """Compute MD5 hash of the given text."""
    return hashlib.md5(text.encode('utf-8')).hexdigest()

def sanitize_filename(filename):
    """Sanitize the filename by removing or replacing special characters."""
    invalid_chars = ['<', '>', ':', '"', '/', '\\', '|', '?', '*']
    for char in invalid_chars:
        filename = filename.replace(char, '_')
    return filename[:200]  # Limit filename length

def format_note_as_blockquote(note):
    """Format the note text as a Markdown blockquote."""
    if not note:
        return ""
    return '\n'.join([f"> {line}" if line.strip() else '>' for line in note.split('\n')])

def get_all_tasks():
    """Get all tasks including completed ones from Things 3."""
    # Get active tasks
    active_tasks = things.todos()
    
    # Get completed/canceled tasks from logbook
    logbook_tasks = things.logbook()
    
    return active_tasks + logbook_tasks

def group_tasks_by_project(all_tasks):
    """Group tasks by their project."""
    projects = defaultdict(lambda: {
        'info': {},
        'active_tasks': [],
        'completed_tasks': []
    })
    
    # Also get standalone projects
    project_list = things.projects()
    for project in project_list:
        project_id = project['uuid']
        projects[project_id]['info'] = {
            'title': project.get('title', 'Untitled'),
            'uuid': project_id,
            'status': project.get('status', 'open'),
            'notes': project.get('notes', ''),
            'tags': project.get('tags', [])
        }
    
    # Group tasks by project
    for task in all_tasks:
        if 'project' in task:
            project_id = task['project']
            project_title = task.get('project_title', 'Untitled')
            
            # Update project info if not already set
            if not projects[project_id]['info']:
                projects[project_id]['info'] = {
                    'title': project_title,
                    'uuid': project_id,
                    'status': 'open',
                    'notes': '',
                    'tags': []
                }
            
            # Categorize task
            if task.get('status') == 'completed':
                projects[project_id]['completed_tasks'].append(task)
            elif task.get('status') == 'canceled':
                projects[project_id]['completed_tasks'].append(task)
            else:
                projects[project_id]['active_tasks'].append(task)
    
    # Handle tasks without projects (Inbox)
    inbox_tasks = []
    for task in all_tasks:
        if 'project' not in task and 'area' not in task:
            inbox_tasks.append(task)
    
    if inbox_tasks:
        projects['__inbox__'] = {
            'info': {
                'title': 'Inbox',
                'uuid': '__inbox__',
                'status': 'open',
                'notes': '',
                'tags': []
            },
            'active_tasks': [t for t in inbox_tasks if t.get('status') not in ['completed', 'canceled']],
            'completed_tasks': [t for t in inbox_tasks if t.get('status') in ['completed', 'canceled']]
        }
    
    return projects

def format_task_as_markdown(task):
    """Format a single task as markdown checkbox item."""
    title = task.get('title', 'Untitled')
    uuid = task.get('uuid', '')
    status = task.get('status', 'open')
    notes = task.get('notes', '')
    tags = task.get('tags', [])
    
    # Determine checkbox state
    if status == 'completed':
        checkbox = "- [x]"
    elif status == 'canceled':
        checkbox = "- [-]"
    else:
        checkbox = "- [ ]"
    
    # Build task line
    task_line = f"{checkbox} [{title}](things:///show?id={uuid})"
    
    # Add tags
    if tags:
        task_line += " " + " ".join(f"#{tag}" for tag in tags)
    
    # Add notes as indented content
    if notes:
        formatted_notes = '\n'.join('\t' + line for line in notes.splitlines())
        task_line += "\n" + formatted_notes
    
    return task_line

def generate_project_markdown(project_data):
    """Generate markdown content for a project."""
    info = project_data['info']
    active_tasks = project_data['active_tasks']
    completed_tasks = project_data['completed_tasks']
    
    # Generate metadata
    metadata = []
    metadata.append("---")
    metadata.append(f"status: {info['status']}")
    if info['uuid'] == '__inbox__':
        metadata.append("url: things:///show?id=inbox")
    else:
        metadata.append(f"url: things:///show?id={info['uuid']}")
    if info['tags']:
        metadata.append(f"tags: {', '.join(info['tags'])}")
    metadata.append("---")
    
    # Generate content
    content = []
    content.extend(metadata)
    content.append("")
    
    # Project title
    if info['uuid'] == '__inbox__':
        content.append(f"# {info['title']}")
    else:
        content.append(f"# [{info['title']}](things:///show?id={info['uuid']})")
    
    # Project notes
    if info['notes']:
        content.append("")
        content.append(format_note_as_blockquote(info['notes']))
    
    # Active tasks
    if active_tasks:
        content.append("")
        content.append("## Active Tasks")
        content.append("")
        # Sort by creation date if available
        active_tasks.sort(key=lambda x: x.get('created', ''), reverse=False)
        for task in active_tasks:
            content.append(format_task_as_markdown(task))
    
    # Completed tasks
    if completed_tasks:
        content.append("")
        content.append("## Completed Tasks")
        content.append("")
        # Sort by completion date if available
        completed_tasks.sort(key=lambda x: x.get('stop_date', ''), reverse=True)
        for task in completed_tasks:
            content.append(format_task_as_markdown(task))
    
    return '\n'.join(content)

def create_markdown_files(projects, output_directory="things3_projects"):
    """Create markdown files for each project."""
    os.makedirs(output_directory, exist_ok=True)
    
    files_created = 0
    files_updated = 0
    files_unchanged = 0
    
    for project_id, project_data in projects.items():
        info = project_data['info']
        
        # Generate filename
        sanitized_name = sanitize_filename(info['title'])
        if project_id == '__inbox__':
            filename = "Inbox.md"
        else:
            filename = f"{sanitized_name}_{project_id[:8]}.md"
        
        file_path = os.path.join(output_directory, filename)
        
        # Generate content
        new_content = generate_project_markdown(project_data)
        
        # Check if file exists and compare content
        if os.path.exists(file_path):
            with open(file_path, 'r') as f:
                existing_content = f.read()
            
            if compute_md5(existing_content) == compute_md5(new_content):
                files_unchanged += 1
                continue
            else:
                files_updated += 1
        else:
            files_created += 1
        
        # Write file
        with open(file_path, 'w') as f:
            f.write(new_content)
    
    return files_created, files_updated, files_unchanged

def main():
    """Main function to export Things 3 projects to markdown."""
    print("Fetching tasks from Things 3...")
    all_tasks = get_all_tasks()
    print(f"Found {len(all_tasks)} total tasks")
    
    print("Grouping tasks by project...")
    projects = group_tasks_by_project(all_tasks)
    print(f"Found {len(projects)} projects")
    
    print("Creating markdown files...")
    created, updated, unchanged = create_markdown_files(projects)
    
    print(f"\nExport complete:")
    print(f"  Files created: {created}")
    print(f"  Files updated: {updated}")
    print(f"  Files unchanged: {unchanged}")
    print(f"  Output directory: things3_projects/")

if __name__ == "__main__":
    main()