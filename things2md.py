from operator import itemgetter
from collections import defaultdict
import datetime
import things

def logbook_to_md(data):
    sorted_data = sorted(data, key = itemgetter('stop_date'), reverse=True)

    md_dict = defaultdict(lambda: defaultdict(list))

    for entry in sorted_data:
        todo_link = f"[{entry['title']}](things:///show?id={entry['uuid']})"
        stop_date = datetime.datetime.strptime(entry['stop_date'], '%Y-%m-%d %H:%M:%S').strftime('%Y-%m-%d')

        md_str = f"- [x] {todo_link}"
         
        if 'tags' in entry:
            for tag in entry['tags']:
                md_str += f" #{tag}"

        group_key = 'No project or area'
        if 'project' in entry:
            project_link = f"[{entry['project_title']}](things:///show?id={entry['project']})"
            group_key = project_link

        if 'area' in entry:
            area_link = f"[{entry['area_title']}](things:///show?id={entry['area']})"
            group_key = area_link

        if 'notes' in entry:
            md_str += "\n"
            notes = '\n'.join('\t' + line for line in entry['notes'].splitlines())
            md_str += notes

        md_dict[stop_date][group_key].append(md_str)

    final_md = "# Things3 Logbook\n"
    for date, groups in md_dict.items():
        final_md += f"\n\n## [[{date}]]\n"
        for group, todos in groups.items():
            if group != 'No project or area':
                final_md += f"### {group}\n"
            final_md += "\n".join(todos) 

    return final_md

if __name__ == "__main__":
    logbook = things.logbook()
    logbook_md = logbook_to_md(logbook)
    with open('logbook.md', 'w') as f:
        f.write(logbook_md)
