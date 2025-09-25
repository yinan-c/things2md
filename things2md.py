from operator import itemgetter
from collections import defaultdict
import datetime
import things


def build_heading_lookup():
    """Map heading UUIDs to their parent project and area metadata."""
    project_lookup = {
        project["uuid"]: project
        for project in things.projects(status=None)
    }

    heading_lookup = {}
    headings = things.tasks(type="heading", status=None)
    for heading in headings:
        project_id = heading.get("project")
        if not project_id:
            continue

        project_info = project_lookup.get(project_id, {})
        heading_lookup[heading["uuid"]] = {
            "project": project_id,
            "project_title": heading.get("project_title")
            or project_info.get("title", ""),
            "area": project_info.get("area"),
            "area_title": project_info.get("area_title"),
            "heading_title": heading.get("title", ""),
        }

    return heading_lookup


def inject_heading_context(entry, heading_lookup):
    """Ensure logbook entries under headings have project context."""
    if "project" in entry or "heading" not in entry:
        return

    meta = heading_lookup.get(entry["heading"])
    if not meta:
        return

    entry["project"] = meta.get("project")
    entry["project_title"] = meta.get("project_title")

    if meta.get("area") and "area" not in entry:
        entry["area"] = meta["area"]

    if meta.get("area_title") and "area_title" not in entry:
        entry["area_title"] = meta["area_title"]

    if (not entry.get("heading_title")) and meta.get("heading_title"):
        entry["heading_title"] = meta["heading_title"]


def format_entries_with_headings(entries, heading_level):
    """Render Markdown lines grouping entries beneath heading titles."""
    if not entries:
        return ""

    lines = []
    items_without_heading = []
    heading_sections = {}
    heading_order = []

    for entry in entries:
        heading_id = entry.get("heading")
        content = entry["content"]
        if heading_id:
            if heading_id not in heading_sections:
                heading_sections[heading_id] = {
                    "title": entry.get("heading_title") or "Untitled Heading",
                    "items": [],
                }
                heading_order.append(heading_id)
            heading_sections[heading_id]["items"].append(content)
        else:
            items_without_heading.append(content)

    lines.extend(items_without_heading)

    heading_prefix = "#" * heading_level

    for heading_id in heading_order:
        section = heading_sections[heading_id]
        if lines:
            lines.append("")
        lines.append(f"{heading_prefix} {section['title']}")
        lines.extend(section["items"])

    return '\n'.join(lines)


def logbook_to_md(data, heading_lookup=None):
    sorted_data = sorted(data, key = itemgetter('stop_date'), reverse=True)

    md_dict = defaultdict(lambda: defaultdict(list))

    heading_lookup = heading_lookup or build_heading_lookup()

    for entry in sorted_data:
        inject_heading_context(entry, heading_lookup)
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

        md_dict[stop_date][group_key].append({
            "heading": entry.get("heading"),
            "heading_title": entry.get("heading_title"),
            "content": md_str,
        })

    final_md = "# Things3 Logbook\n"
    for date, groups in md_dict.items():
        final_md += f"\n\n## [[{date}]]\n"
        for group, entries in groups.items():
            if group == 'No project or area':
                rendered = format_entries_with_headings(entries, heading_level=4)
                if rendered:
                    final_md += rendered
        for group, entries in groups.items():
            if group != 'No project or area':
                rendered = format_entries_with_headings(entries, heading_level=4)
                final_md += f"\n### {group}\n"
                if rendered:
                    final_md += rendered
    return final_md

if __name__ == "__main__":
    logbook = things.logbook()
    logbook_md = logbook_to_md(logbook)
    with open('logbook.md', 'w') as f:
        f.write(logbook_md)
