import re
import threading
import time
import datetime

# --- Reminder class ---
class Reminder:
    def __init__(self, content, remind_time, time_str):
        self.content = content
        self.remind_time = remind_time  # datetime object
        self.time_str = time_str        # original string for display

# --- MemoManager class ---
class MemoManager:
    def __init__(self):
        # pending_users maps username to the timestamp when they initiated memo mode
        self.pending_users = {}  # {username: datetime.datetime}
        # reminders maps username to a list of Reminder objects
        self.reminders = {}      # {username: [Reminder, ...]}
        self.pending_timeout = 120  # seconds for pending memo mode expiration
        self.lock = threading.Lock()

    def cleanup_pending(self):
        """Remove pending requests that have expired (older than 2 minutes)."""
        now = datetime.datetime.now()
        with self.lock:
            expired = [
                user for user, ts in self.pending_users.items()
                if (now - ts).total_seconds() > self.pending_timeout
            ]
            for user in expired:
                del self.pending_users[user]

    def process_message(self, username, message):
        """
        Process a message from a user and return any bot responses.
        Supported commands:
          1. "@小z 提醒功能" 
             - Initializes memo mode (reminder function) for the user.
          2. "@小z 提醒内容：<提醒事项> 提醒时间：YYYY/MM/DD HH:MM"
             - Adds a new reminder (only allowed if memo mode was initialized).
          3. "@小z 查看提醒"
             - Displays all active reminders for the user.
          4. "@小z 删除提醒 <关键字>"
             - Deletes a reminder that contains the specified keyword.
          5. "@小z 修改提醒 <原提醒关键字> 新提醒内容：<新提醒事项> 新提醒时间：YYYY/MM/DD HH:MM"
             - Modifies an existing reminder.
        """
        self.cleanup_pending()
        responses = []
        msg = message.strip()

        # --- Step 1: Initialize Memo Mode ---
        if msg == "@小z 提醒功能":
            with self.lock:
                self.pending_users[username] = datetime.datetime.now()
            responses.append(
                "请严格按照以下格式输入你的提醒 (北京时间):\n"
                "提醒内容：<提醒事项> 提醒时间：YYYY/MM/DD HH:MM\n"
                "⚠️ 注意：必须在同一条消息中再次 @小z，并且是同一个人填写提醒信息。"
            )
            return responses

        # --- Step 2: View Reminders ---
        if msg == "@小z 查看提醒":
            if username in self.reminders and self.reminders[username]:
                resp = "📅 你的提醒："
                for idx, rem in enumerate(self.reminders[username], 1):
                    resp += f"\n{idx}️⃣ [{rem.content}] - {rem.time_str}"
                responses.append(resp)
            else:
                responses.append("你目前没有设置任何提醒。")
            return responses

        # --- Step 3: Delete Reminder ---
        if msg.startswith("@小z 删除提醒"):
            parts = msg.split("删除提醒", 1)
            if len(parts) < 2 or not parts[1].strip():
                responses.append("⚠️ 请提供要删除提醒的关键字。")
                return responses
            keyword = parts[1].strip()
            if username in self.reminders:
                found = None
                for rem in self.reminders[username]:
                    if keyword in rem.content:
                        found = rem
                        break
                if found:
                    self.reminders[username].remove(found)
                    responses.append(f"🗑 已删除提醒：\"{found.content}\" ({found.time_str})")
                else:
                    responses.append("⚠️ 未找到匹配的提醒。")
            else:
                responses.append("你目前没有设置任何提醒。")
            return responses

        # --- Step 4: Modify Reminder ---
        if msg.startswith("@小z 修改提醒"):
            # Expected format: 
            # "@小z 修改提醒 <原提醒关键字> 新提醒内容：<新提醒事项> 新提醒时间：YYYY/MM/DD HH:MM"
            pattern = r"^@小z\s+修改提醒\s+(\S+)\s+新提醒内容：(.*?)\s+新提醒时间：(\d{4}/\d{2}/\d{2}\s+\d{2}:\d{2})$"
            match = re.fullmatch(pattern, msg)
            if not match:
                responses.append(
                    "⚠️ 格式错误！请使用:\n"
                    "@小z 修改提醒 <原提醒关键字> 新提醒内容：<新提醒事项> 新提醒时间：YYYY/MM/DD HH:MM"
                )
                return responses
            original_keyword = match.group(1).strip()
            new_content = match.group(2).strip()
            new_time_str = match.group(3).strip()
            try:
                new_remind_time = datetime.datetime.strptime(new_time_str, "%Y/%m/%d %H:%M")
            except Exception:
                responses.append("⚠️ 提醒时间格式错误，请使用 YYYY/MM/DD HH:MM 格式。")
                return responses
            if new_remind_time < datetime.datetime.now():
                responses.append("⚠️ 新提醒时间已过，请设置未来的时间。")
                return responses

            if username in self.reminders:
                found = None
                for rem in self.reminders[username]:
                    if original_keyword in rem.content:
                        found = rem
                        break
                if found:
                    old_content = found.content
                    old_time_str = found.time_str
                    found.content = new_content
                    found.remind_time = new_remind_time
                    found.time_str = new_time_str
                    responses.append(
                        f"✅ 你的提醒已更新！\n旧提醒：\"{old_content}\" ({old_time_str})\n新提醒：\"{new_content}\" ({new_time_str})"
                    )
                else:
                    responses.append("⚠️ 未找到匹配的提醒。")
            else:
                responses.append("你目前没有设置任何提醒。")
            return responses

        # --- Step 5: Add Reminder (requires initialization) ---
        if msg.startswith("@小z 提醒内容："):
            with self.lock:
                if username not in self.pending_users:
                    responses.append("⚠️ 你还未初始化提醒功能，请先发送 '@小z 提醒功能'。")
                    return responses
                # Once processed, remove the pending state for the user.
                del self.pending_users[username]

            # Expected format:
            # "@小z 提醒内容：<提醒事项> 提醒时间：YYYY/MM/DD HH:MM"
            pattern = r"^@小z\s+提醒内容：(.*?)\s+提醒时间：(\d{4}/\d{2}/\d{2}\s+\d{2}:\d{2})$"
            match = re.fullmatch(pattern, msg)
            if not match:
                responses.append(
                    "⚠️ 格式错误！请严格按照以下格式输入：\n"
                    "@小z 提醒内容：<提醒事项> 提醒时间：YYYY/MM/DD HH:MM"
                )
                return responses

            reminder_content = match.group(1).strip()
            time_str = match.group(2).strip()
            try:
                remind_time = datetime.datetime.strptime(time_str, "%Y/%m/%d %H:%M")
            except Exception:
                responses.append("⚠️ 提醒时间格式错误，请使用 YYYY/MM/DD HH:MM 格式。")
                return responses

            if remind_time < datetime.datetime.now():
                responses.append("⚠️ 提醒时间已过，请设置未来的时间。")
                return responses

            reminder = Reminder(reminder_content, remind_time, time_str)
            with self.lock:
                if username not in self.reminders:
                    self.reminders[username] = []
                self.reminders[username].append(reminder)
            responses.append("✅ 你的提醒已记录！到时间我会提醒你~")
            return responses

        # --- If no command matches ---
        return responses

    def reminder_checker(self):
        """Background thread that checks for reminders that are due."""
        while True:
            now = datetime.datetime.now()
            with self.lock:
                for username in list(self.reminders.keys()):
                    for rem in self.reminders[username][:]:
                        if now >= rem.remind_time:
                            print(f"\n@{username} ⏰ 提醒你：{rem.content}！({rem.time_str})\n")
                            self.reminders[username].remove(rem)
            time.sleep(10)

# --- Standalone Test ---
if __name__ == "__main__":
    memo = MemoManager()
    # Start the reminder checker in a background thread.
    checker_thread = threading.Thread(target=memo.reminder_checker, daemon=True)
    checker_thread.start()
    
    print("Memo Manager Test - 输入消息:")
    while True:
        user_input = input("请输入消息: ").strip()
        username = "TestUser"
        responses = memo.process_message(username, user_input)
        for resp in responses:
            print(resp)
