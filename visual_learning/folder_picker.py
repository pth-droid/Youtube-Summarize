"""Native folder picker isolated from web-service threads."""
import json
import sys


def main():
    import tkinter as tk
    from tkinter import filedialog
    options = json.loads(sys.stdin.read())
    root = tk.Tk()
    root.withdraw()
    root.attributes("-topmost", True)
    try:
        folder = filedialog.askdirectory(parent=root, title="Choose your Visual Learning library folder", initialdir=options.get("initialdir") or None, mustexist=False)
        print(json.dumps({"path": folder or None}, ensure_ascii=True))
    finally:
        root.destroy()


if __name__ == "__main__":
    main()
