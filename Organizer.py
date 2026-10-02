from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

from pathlib import Path

import time

import tkinter as tk

import pystray

from PIL import Image

import threading

import queue

import json

import sys

def get_base_path():
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    else:
        return Path(__file__).resolve().parent

def load_config():
    base_path = get_base_path()

    config_path = base_path / "config.json"

    with open(config_path, "r") as folder:
        config = json.load(folder)

    value = config.get("folder")
    path = Path(value)

    return path

folder = load_config()

file_categories = {
    "Images": [".jpg", ".jpeg", ".png", ".gif", ".bmp", ".webp", ".tif", ".tiff", ".svg", ".heic", ".avif"],
    "Documents": [".pdf", ".doc", ".docx", ".txt", ".rtf", ".odt", ".md", ".tex", ".epub"],
    "Videos": [".mp4", ".mov", ".avi", ".mkv", ".wmv", ".webm", ".flv"],
    "Archives": [".zip", ".rar", ".7z", ".tar", ".gz", ".bz2", ".xz"],
    "Programs": [".exe", ".msi", ".apk", ".dmg", ".app", ".bat", ".sh", ".jar"],
    "Audio": [".mp3", ".wav", ".aac", ".flac", ".ogg", ".m4a", ".wma"],
    "Code": [".py", ".js", ".ts", ".html", ".css", ".php", ".c", ".cpp", ".java", ".json", ".xml", ".yaml", ".yml"]
}

dry_run = True

class MyHandler(FileSystemEventHandler):
    def __init__(self):
        self.processed_count = 0
        self.moved_count = 0
        self.failed_count = 0
        self.successes = []
        self.errors = []

    def on_created(self, event):
        if not event.is_directory:
            self.processed_count += 1
            path = Path(event.src_path)

            if is_file_ready(path):
                status, file_name, destination = organize_file(path, dry_run)
                if status in ("success", "dryrun"):
                    self.successes.append({"original": file_name, "destination": destination})
                else:
                    self.errors.append(f"{file_name}: {destination}")

                self.moved_count, self.failed_count = handle_result(status, self.moved_count, self.failed_count)

def classify_file(item):
    for category, extensions in file_categories.items():
        if item.suffix.lower() in extensions: break

    else:
        category = "Others"

    return category

def create_folder(category_folder):
    if category_folder.is_file():
        raise OSError(f"{category_folder} exists but is a file 😅")

    category_folder.mkdir(exist_ok=True)

    return category_folder

def get_unique_destination(category_folder, item):
    destination = category_folder / item.name

    counter = 0

    while destination.exists():
        counter += 1
        new_filename = f"{item.stem}_{counter}{item.suffix}"
        destination = category_folder / new_filename

    return destination

def is_file_ready(item):
    stable_count = 0
    attempts = 0

    while stable_count < 3 and attempts < 300:
        try:
            size_1 = item.stat().st_size

            time.sleep(2)

            size_2 = item.stat().st_size

        except FileNotFoundError:
            return False

        attempts += 1

        if size_1 == size_2:
            stable_count += 1

        else: stable_count = 0

    return stable_count >= 3

def move_file(item, destination, dry_run):
    if dry_run:
        return False

    else:
        item.rename(destination)
        return True

def organize_file(item, dry_run):
    result = classify_file(item)
    category_folder = folder / result

    try:
        if not dry_run:
            create_folder(category_folder)

        unique_destination = get_unique_destination(category_folder, item)

        moved = move_file(item, unique_destination, dry_run)

        if moved: return "success", item.name, unique_destination

        else:
            return "dryrun", item.name, unique_destination

    except OSError as error:
        return "failed", item.name, error

def handle_result(status, moved_count, failed_count):

    if status == "success":
        moved_count += 1
    elif status == "failed":
        failed_count += 1
    elif status == "dryrun":
        pass

    return moved_count, failed_count

def manual_mode():
    moved_count = 0
    failed_count = 0
    errors = []
    processed_count = 0
    successes = []

    for item in folder.iterdir():
        if item.is_file():
            processed_count += 1

            status, file_name, destination = organize_file(item, dry_run)

            if status in ("success", "dryrun"):
                successes.append({"original": file_name, "destination": destination})

            else:
                errors.append(f"{file_name}: {destination}")

            moved_count, failed_count = handle_result(status, moved_count, failed_count)

    return processed_count, moved_count, failed_count, successes, errors

def automatic_mode():
    handler = MyHandler()

    observer = Observer()
    observer.schedule(handler, folder)
    observer.start()

    start_tray()

    return handler, observer


processed_count, moved_count, failed_count, successes, errors = manual_mode()


root = tk.Tk()
root.withdraw()

action_queue = queue.Queue()

def view_logs(successes, errors):
    window = tk.Toplevel(root)
    window.title("Organization Logs📋")

    logs = tk.Text(window)

    logs_list = []

    for success in successes:
        original = success.get("original")
        destination = success.get("destination")
        logs_list.append(f"✓ {original} →\n{destination}")

    for error in errors:
        logs_list.append(f"✗ {error}")

    logs_text = "\n".join(logs_list)

    logs.insert("1.0", logs_text)

    logs.config(state="disabled")
    logs.pack()

def start_auto():
    handler, observer = automatic_mode()

    root.handler = handler
    root.observer = observer

    root.protocol("WM_DELETE_WINDOW", lambda: shutdown(root.observer))

    return root.handler

def close_window(window):
    close_button = tk.Button(
        window,
        text="Auto Mode ON",
        command=lambda:(start_auto(),window.destroy())
    )
    close_button.pack(pady=5)

def popup_window(dry_run_title, normal_title):
    window = tk.Toplevel(root)
    if dry_run:
        window.title(dry_run_title)

    else:
        window.title(normal_title)

    window.geometry("320x170")
    summary_label_e = tk.Label(
        window,
        text=f"Processed: {processed_count}\n\nMoved: {moved_count}\n\nFailed: {failed_count}"
    )
    summary_label_e.pack(pady=5)

    logs_button = tk.Button(
        window,
        text="View Logs",
        command=lambda:view_logs(successes, errors)
    )
    logs_button.pack(pady=5)

    return window

def automatic_logs():
    successes = root.handler.successes
    errors = root.handler.errors

    view_logs(successes, errors)

def shutdown(observer):
    observer.stop()
    observer.join()
    root.icon.stop()
    root.destroy()

def tray_view_logs(icon, item):
    action_queue.put("view_logs")

def tray_exit(icon, item):
    action_queue.put("shutdown")

def process_actions():
    try:
        action = action_queue.get_nowait()
        if action == "shutdown":
            shutdown(root.observer)
        elif action == "view_logs":
            automatic_logs()
            root.after(100, process_actions)

    except queue.Empty:
        root.after(100, process_actions)

def resource_path(filename):
    base_path = get_base_path()

    return base_path / filename

def start_tray():
    # put your png here👇
    image = Image.open(resource_path("tray_icon.png"))

    menu = pystray.Menu(
        pystray.MenuItem("View Logs", tray_view_logs),
        pystray.MenuItem("Exit", tray_exit)
        )

    icon = pystray.Icon("Downloads Organizer", image, "Organizer", menu)

    thread = threading.Thread(target=icon.run)
    thread.start()

    root.icon = icon

if processed_count == 0:
    start_auto()

elif failed_count == 0:
    success_window = popup_window("Dry Run Complete🧪", "Organization Complete!🥳")

    close_window(success_window)

else:
    error_window = popup_window("Dry Run Complete🧪", "Completed with errors⚠️")

    close_window(error_window)

root.after(100, process_actions)
root.mainloop()