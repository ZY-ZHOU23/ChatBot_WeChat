import time
import logging
import re
from wxauto import WeChat
from openai import OpenAI

from conversation import Conversation
from reminder_manager import ReminderManager
from helpers import calculate_default_reminder_time, extract_time_correction

# Set max output length
MAX_OUTPUT_LENGTH = 300

def clean_sender(sender: str) -> str:
    """
    Cleans the sender's name by removing any trailing member count.
    Example: "test（3）" -> "test", "group(5)" -> "group"
    """
    return re.sub(r'[\(（]\d+[\)）]\s*$', '', sender)

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

    # Dictionary to hold pending reminder confirmations.
    pending_reminders = {}

    logging.info("Chatbot is running...")

    while True:
        new_messages = wx.GetAllNewMessage()
        for sender, messages_list in new_messages.items():
            cleaned_sender = clean_sender(sender)  # Clean group name before processing
            
            for message in messages_list:
                msg_text = message[1]
                
                # Only process messages directed at the bot.
                if not msg_text.startswith(agent_name):
                    continue

                # Remove the bot mention.
                user_query = msg_text[len(agent_name):].strip()

                # --------- Pending Reminder Confirmation or Correction ---------
                if cleaned_sender in pending_reminders:
                    pending = pending_reminders[cleaned_sender]
                    correction = extract_time_correction(user_query, pending['suggested_time'])
                    
                    if correction is not None:
                        pending['suggested_time'] = correction
                        formatted_time = correction.strftime("%Y-%m-%d %H:%M")
                        wx.SendMsg(
                            f"你希望我在{formatted_time}中国时间提醒你{pending['reminder_text']}吗？ (yes/no)",
                            who=cleaned_sender
                        )
                        continue
                    elif user_query.lower() == "yes":
                        scheduled_time = pending['suggested_time']
                        reminder_manager.add_reminder(cleaned_sender, pending['reminder_text'], scheduled_time)
                        wx.SendMsg(
                            f"好的，我会在 {scheduled_time.strftime('%Y-%m-%d %H:%M')} 中国时间提醒你{pending['reminder_text']}.",
                            who=cleaned_sender
                        )
                        pending_reminders.pop(cleaned_sender)
                        continue
                    elif user_query.lower() == "no":
                        wx.SendMsg("好的，请告诉我您希望的提醒时间（例如：15:30）", who=cleaned_sender)
                        continue
                    else:
                        wx.SendMsg("请确认提醒时间或提供新的时间，例如：15:30", who=cleaned_sender)
                        continue

                # --------- New Reminder Request Detection ---------
                if "提醒" in user_query:
                    idx = user_query.find("提醒")
                    reminder_subject = user_query[idx + len("提醒"):].strip()
                    if not reminder_subject:
                        reminder_subject = user_query
                    default_time = calculate_default_reminder_time(user_query)
                    
                    pending_reminders[cleaned_sender] = {
                        'reminder_text': reminder_subject,
                        'suggested_time': default_time
                    }
                    formatted_time = default_time.strftime("%Y-%m-%d %H:%M")
                    wx.SendMsg(
                        f"你希望我在{formatted_time}中国时间提醒你{reminder_subject}吗？ (yes/no)",
                        who=cleaned_sender
                    )
                    continue

                # --------- Normal Conversation Flow ---------
                logging.info("Received query from %s: %s", cleaned_sender, user_query)
                conversation.add_message("user", user_query)

                try:
                    history = conversation.get_history()
                    response = client.chat.completions.create(
                        model=model_name,
                        messages=history,
                        temperature=0.7,
                        max_tokens=200
                    )
                    reply_text = response.choices[0].message.content.strip()

                    if len(reply_text) > MAX_OUTPUT_LENGTH:
                        reply_text = reply_text[:MAX_OUTPUT_LENGTH] + "..."
                    
                    wx.SendMsg(reply_text, who=cleaned_sender)
                    logging.info("Replied to %s: %s", cleaned_sender, reply_text)
                    conversation.add_message("assistant", reply_text)
                except Exception as e:
                    logging.error("Error generating response for %s: %s", cleaned_sender, e, exc_info=True)
                    wx.SendMsg("Sorry, I encountered an error processing your request.", who=cleaned_sender)
        
        time.sleep(1)  # Check for new messages every second.

if __name__ == "__main__":
    main()
