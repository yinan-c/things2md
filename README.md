# Things to Markdown


[Things](https://culturedcode.com/things/) is a to-do list app for macOS and iOS.

This script converts Things logbook into a Markdown file. Simply clone/download the code, install the requirements, and run the code.

```
pip3 install -r requirements
python3 things2md.py
```

You can view the output file in any Markdown editor. 
You can keep a copy of your completed tasks and projects in a plain-text format, and connect your tasks with notes using [Obsidian](https://Obsidian.md) or other note-taking apps.  It is good practice for keeping track of what you have done while writing your daily/weekly or study notes.

To-dos are sorted by completed dates, and grouped by projects or areas if they exist. Tags and notes are also included.

## NOTE

This script currently does not support auto-updates. You have to run the code to refresh the Markdown file. 

However, you can easily set up automation using [crontab](https://crontab.guru/), [Keyboard Maestro](http://www.keyboardmaestro.com/), or any other automation tools.

## Acknowledgments

- This script uses a powerful Python library [things.py](https://github.com/thingsapi/things.py).
- Inspired by [Obsidian Things Logbook](https://github.com/liamcain/obsidian-things-logbook) plugin.
