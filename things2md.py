from operator import itemgetter
from collections import defaultdict
import datetime
import things

def logbook_to_md(data):
    sorted_data = sorted(data, key = itemgetter('stop_date'), reverse=True)

    md_dict = defaultdict(list)

    for entry in sorted_data:
        todo_link = f"[{entry['title']}](things:///show?id={entry['uuid']})"
        stop_date = datetime.datetime.strptime(entry['stop_date'], '%Y-%m-%d %H:%M:%S').strftime('%Y-%m-%d')

        md_str = f"- [x] {todo_link}"
         
        if 'tags' in entry:
            for tag in entry['tags']:
                md_str += f" #{tag}"

        if 'project' in entry:
            project_link = f"[{entry['project_title']}](things:///show?id={entry['project']})"
            md_str += f" @{project_link}"

        if 'area' in entry:
            area_link = f"[{entry['area_title']}](things:///show?id={entry['area']})"
            md_str += f" ^{area_link}"

        if 'notes' in entry:
            md_str += "\n"
            notes = '\n'.join('\t\t' + line for line in entry['notes'].splitlines())
            md_str += notes

        md_str += "\n"
        md_dict[stop_date].append(md_str)

    final_md = ""
    for date, todos in md_dict.items():
        final_md += f"## [[{date}]]\n" + "\n".join(todos) + "\n"

    return final_md

if __name__ == "__main__":
    logbook = things.logbook()
    logbook_md = logbook_to_md(logbook)
    with open('logbook.md', 'w') as f:
        f.write(logbook_md)

