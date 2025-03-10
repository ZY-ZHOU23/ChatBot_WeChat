#!/usr/bin/env python3
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

# --- Bot class ---
class MemoBot:
    def __init__(self):
        # pending_users maps username to the timestamp when they initiated a memo mode
        self.pending_users = {}  # {username: datetime.datetime}
        # reminders maps username to a list of Reminder objects
        self.reminders = {}      # {username: [Reminder, ...]}
        self.pending_timeout = 120  # seconds for pending memo mode expiration
        self.lock = threading.Lock()

    def cleanup_pending(self):
        """Remove pending requests that have expired (older than 2 minutes)."""
        now = datetime.datetime.now()
        with self.lock:
            expired = [user for user, ts in self.pending_users.items()
                       if (now - ts).total_seconds() > self.pending_timeout]
            for user in expired:
                del self.pending_users[user]

    def process_message(self, username, message):
        """
        Process a message from a user and return any bot responses.
        Valid commands:
          1. '@小z 提醒功能'
          2. '@小z 提醒内容：<提醒事项> 提醒时间：YYYY/MM/DD HH:MM'
          3. '@小z 查看提醒'
          4. '@小z 删除提醒 <关键字>'
        """
        self.cleanup_pending()
        responses = []
        msg = message.strip()

        # --- Step 1: Initiate Memo Mode ---
        if msg == "@小z 提醒功能":
            with self.lock:
                # Record the timestamp for the user who initiated memo mode.
                self.pending_users[username] = datetime.datetime.now()
            responses.append(
                "严格按照以下格式填写你需要的提醒 (北京时间)\n"
                "提醒内容：\n"
                "提醒时间：YYYY/MM/DD HH:MM\n"
                "⚠️ 注意：你必须在同一条消息中再次 @小z，并且是同一个人填写提醒信息。"
            )
            return responses

        # --- Step 5: View Reminders ---
        if msg == "@小z 查看提醒":
            if username in self.reminders and self.reminders[username]:
                resp = "📅 你的提醒："
                for idx, rem in enumerate(self.reminders[username], 1):
                    resp += f"\n{idx}️⃣ [{rem.content}] - {rem.time_str}"
                responses.append(resp)
            else:
                responses.append("你目前没有设置任何提醒。")
            return responses

        # --- Step 5: Delete Reminder ---
        if msg.startswith("@小z 删除提醒"):
            # Expected format: "@小z 删除提醒 <关键字>"
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

        # --- Step 2: Provide Reminder (Must be from user who initiated memo mode) ---
        if msg.startswith("@小z 提醒内容："):
            with self.lock:
                if username not in self.pending_users:
                    responses.append(
                        "⚠️ 你的输入格式错误！请严格使用：\n"
                        "@小z 提醒内容：<提醒事项> 提醒时间：YYYY/MM/DD HH:MM\n"
                        "或者，你不是发起提醒功能的用户！"
                    )
                    return responses
                # Once processed, remove the pending state for the user.
                del self.pending_users[username]

            # Use a regex to strictly verify the format.
            pattern = r"^@小z\s+提醒内容：(.*?)\s+提醒时间：(\d{4}/\d{2}/\d{2}\s+\d{2}:\d{2})$"
            match = re.fullmatch(pattern, msg)
            if not match:
                responses.append(
                    "⚠️ 你的输入格式错误！请严格使用：\n"
                    "@小z 提醒内容：<提醒事项> 提醒时间：YYYY/MM/DD HH:MM\n"
                    "或者，你不是发起提醒功能的用户！"
                )
                return responses

            reminder_content = match.group(1).strip()
            time_str = match.group(2).strip()
            try:
                remind_time = datetime.datetime.strptime(time_str, "%Y/%m/%d %H:%M")
            except Exception:
                responses.append("⚠️ 提醒时间格式错误，请使用 YYYY/MM/DD HH:MM 格式。")
                return responses

            # Check that the reminder time is in the future.
            if remind_time < datetime.datetime.now():
                responses.append("⚠️ 提醒时间已过，请设置未来的时间。")
                return responses

            # Save the reminder.
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
                            # "Notify" the user by printing the reminder message.
                            print(f"\n@{username} ⏰ 提醒你：{rem.content}！({rem.time_str})\n")
                            self.reminders[username].remove(rem)
            time.sleep(10)  # Check every 10 seconds

# --- Main loop for interactive simulation ---
def main():
    bot = MemoBot()
    # Assume a global current user. In real use, this is derived from the session.
    current_user = "ZHOU"

    # Optionally, allow switching users with a special command.
    def switch_user(new_user):
        nonlocal current_user
        current_user = new_user
        print(f"当前用户切换为: {current_user}")

    # Start the background reminder checker thread.
    checker_thread = threading.Thread(target=bot.reminder_checker, daemon=True)
    checker_thread.start()

    print("欢迎使用提醒系统模拟器！")
    print("请直接输入命令，例如：")
    print("  @小z 提醒功能")
    print("  @小z 提醒内容：去见我的高中同学 提醒时间：YYYY/MM/DD HH:MM")
    print("  @小z 查看提醒")
    print("  @小z 删除提醒 <关键字>")
    print("如需切换当前用户(模拟不同用户发送消息)，请输入: switchuser <用户名>")
    print("-----------------------------------------------------")

    try:
        while True:
            # Read input message directly.
            raw = input("请输入消息: ").strip()
            if not raw:
                continue

            # Allow switching user for testing purposes.
            if raw.startswith("switchuser"):
                parts = raw.split(maxsplit=1)
                if len(parts) == 2:
                    switch_user(parts[1].strip())
                else:
                    print("请使用格式: switchuser <用户名>")
                continue

            responses = bot.process_message(current_user, raw)
            for resp in responses:
                print(resp)
    except KeyboardInterrupt:
        print("\n退出提醒系统。")

if __name__ == '__main__':
    main()
