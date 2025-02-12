
import time
import datetime
import threading
import logging

class ReminderManager(threading.Thread):
    """
    Runs in a background thread checking if any scheduled reminders are due.
    When the time arrives, it sends a reminder message to the corresponding user.
    """
    def __init__(self, wx):
        super().__init__(daemon=True)
        self.wx = wx
        self.reminders = []  # Each reminder is a dict with keys: 'user', 'reminder_text', 'time'
        self.lock = threading.Lock()

    def add_reminder(self, user, reminder_text, scheduled_time):
        with self.lock:
            self.reminders.append({
                'user': user,
                'reminder_text': reminder_text,
                'time': scheduled_time
            })
            logging.info("Reminder added for %s at %s", user, scheduled_time)

    def run(self):
        while True:
            now = datetime.datetime.now()
            with self.lock:
                # Iterate over a shallow copy so that we can remove items safely.
                for reminder in self.reminders[:]:
                    if now >= reminder['time']:
                        # When the scheduled time arrives, send the reminder.
                        self.wx.SendMsg(f"Reminder: {reminder['reminder_text']}", who=reminder['user'])
                        logging.info("Sent reminder to %s: %s", reminder['user'], reminder['reminder_text'])
                        self.reminders.remove(reminder)
            time.sleep(10)  # Check every 10 seconds
