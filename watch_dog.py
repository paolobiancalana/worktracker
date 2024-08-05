import os
import time
from threading import Thread
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

class WatchdogHandler(FileSystemEventHandler):
    def __init__(self, file_to_monitor, callback):
        self.file_to_monitor = file_to_monitor
        self.callback = callback
        self.last_modified = time.time()

    def on_modified(self, event):
        if event.src_path.endswith(self.file_to_monitor):
            current_time = time.time()
            # Debounce: Only trigger if last event was more than 1 second ago
            if current_time - self.last_modified > 1:
                self.callback()
                self.last_modified = current_time

def start_watchdog():
    directory_to_watch = os.path.dirname(os.path.abspath(__file__))
    file_to_monitor = "main.py"

    def on_file_change():
        print(f"{file_to_monitor} has been modified, reloading...")

    event_handler = WatchdogHandler(file_to_monitor, on_file_change)
    observer = Observer()
    observer.schedule(event_handler, path=directory_to_watch, recursive=False)
    observer_thread = Thread(target=observer.start)
    observer_thread.daemon = True
    observer_thread.start()

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        observer.stop()
        observer.join()

if __name__ == "__main__":
    start_watchdog()
