
import time
import logging
import date

from wxauto import WeChat
from openai import OpenAI

from conversation import Conversation
from reminder_manager import ReminderManager
from helpers import calculate_default_reminder_time, extract_time_correction

# Set max output length
MAX_OUTPUT_LENGTH = 300

def main():

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )
    
    # User Inputs
    apikey = input("Enter OpenAI API Key: ")
    model_name = input("Enter Model Name: ")
    system_prompt = input("Enter System Role Prompt: ")

    # Initialize OpenAI Client and WeChat auto
    client = OpenAI(api_key=apikey, base_url="https://api.siliconflow.cn/v1")

    wx = WeChat()
    agent_name = "@" + wx.nickname  # Bot's WeChat nickname
    
    # Initialize conversation context with the system prompt.
    conversation = Conversation(system_prompt, max_rounds=15)

    # Start the ReminderManager thread.
    reminder_manager = ReminderManager(wx)
    reminder_manager.start()

    # This dictionary holds pending reminder confirmations.
    # Key: sender, Value: dict with keys 'reminder_text' and 'suggested_time'
    pending_reminders = {}

    logging.info("Chatbot is running...")

    while True:
        new_messages = wx.GetAllNewMessage()
        for sender, messages_list in new_messages.items():
            for message in messages_list:
                msg_text = message[1]
                # Only process messages directed at the bot.
                if not msg_text.startswith(agent_name):
                    continue

                # Remove the bot mention.
                user_query = msg_text[len(agent_name):].strip()

                # --------- Pending Reminder Confirmation or Correction ---------
                if sender in pending_reminders:
                    pending = pending_reminders[sender]
                    # Check if the user provided a correction (e.g., a time like "15:30")
                    correction = extract_time_correction(user_query, pending['suggested_time'])
                    if correction is not None:
                        # Update the suggested time.
                        pending['suggested_time'] = correction
                        formatted_time = correction.strftime("%Y-%m-%d %H:%M")
                        wx.SendMsg(
                            f"你希望我在{formatted_time}中国时间提醒你{pending['reminder_text']}吗？ (yes/no)",
                            who=sender
                        )
                        continue
                    # If the user confirms with "yes"
                    elif user_query.lower() == "yes":
                        scheduled_time = pending['suggested_time']
                        reminder_manager.add_reminder(sender, pending['reminder_text'], scheduled_time)
                        wx.SendMsg(
                            f"好的，我会在 {scheduled_time.strftime('%Y-%m-%d %H:%M')} 中国时间提醒你{pending['reminder_text']}.",
                            who=sender
                        )
                        pending_reminders.pop(sender)
                        continue
                    # If the user replies "no", ask for a correction.
                    elif user_query.lower() == "no":
                        wx.SendMsg("好的，请告诉我您希望的提醒时间（例如：15:30）", who=sender)
                        continue
                    # Otherwise, if the user response is ambiguous, prompt again.
                    else:
                        wx.SendMsg("请确认提醒时间或提供新的时间，例如：15:30", who=sender)
                        continue

                # --------- New Reminder Request Detection ---------
                if "提醒" in user_query:
                    # Extract the content after the keyword "提醒" as the reminder subject.
                    idx = user_query.find("提醒")
                    reminder_subject = user_query[idx + len("提醒"):].strip()
                    if not reminder_subject:
                        reminder_subject = user_query  # Fallback if nothing specific follows.
                    # Calculate a default reminder time based on the message and current system time.
                    default_time = calculate_default_reminder_time(user_query)
                    pending_reminders[sender] = {
                        'reminder_text': reminder_subject,
                        'suggested_time': default_time
                    }
                    formatted_time = default_time.strftime("%Y-%m-%d %H:%M")
                    wx.SendMsg(
                        f"你希望我在{formatted_time}中国时间提醒你{reminder_subject}吗？ (yes/no)",
                        who=sender
                    )
                    continue  # Skip normal conversation processing for reminder commands.

                # --------- Normal Conversation Flow ---------
                logging.info("Received query from %s: %s", sender, user_query)
                conversation.add_message("user", user_query)

                try:
                    history = conversation.get_history()
                    # Include a max_tokens parameter to limit generated output.
                    response = client.chat.completions.create(
                        model=model_name,
                        messages=history,
                        temperature=0.7,
                        max_tokens=200
                    )
                    reply_text = response.choices[0].message.content.strip()

                    # Enforce output-length limitation.
                    if len(reply_text) > MAX_OUTPUT_LENGTH:
                        reply_text = reply_text[:MAX_OUTPUT_LENGTH] + "..."

                    wx.SendMsg(reply_text, who=sender)
                    logging.info("Replied to %s: %s", sender, reply_text)
                    conversation.add_message("assistant", reply_text)
                except Exception as e:
                    logging.error("Error generating response for %s: %s", sender, e, exc_info=True)
                    wx.SendMsg("Sorry, I encountered an error processing your request.", who=sender)
        time.sleep(1)  # Check for new messages every second.

if __name__ == "__main__":
    main()
