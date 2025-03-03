import time
import logging
import sys
import re
from wxauto import WeChat
from openai import OpenAI

def setup_logging():
    # Set up logging to file (chatbot.log) and console.
    logger = logging.getLogger()
    logger.setLevel(logging.INFO)
    
    formatter = logging.Formatter("%(asctime)s [%(levelname)s] %(message)s", datefmt="%Y-%m-%d %H:%M:%S")
    
    file_handler = logging.FileHandler("chatbot.log", encoding="utf-8")
    file_handler.setFormatter(formatter)
    file_handler.setLevel(logging.INFO)
    
    stream_handler = logging.StreamHandler()
    stream_handler.setFormatter(formatter)
    stream_handler.setLevel(logging.INFO)
    
    logger.addHandler(file_handler)
    logger.addHandler(stream_handler)
    
    # Log any uncaught exceptions.
    def log_exceptions(exc_type, exc_value, exc_traceback):
        if issubclass(exc_type, KeyboardInterrupt):
            sys.__excepthook__(exc_type, exc_value, exc_traceback)
            return
        logging.error("Uncaught exception:", exc_info=(exc_type, exc_value, exc_traceback))
    sys.excepthook = log_exceptions

def clean_sender(sender: str) -> str:
    """
    Cleans the sender's name by:
      1. Removing all leading and trailing whitespace,
      2. Removing any trailing member count pattern such as "(3)" or "（3）",
      3. And trimming any residual whitespace.
    Example: "测试 (3)" -> "测试", "group(5)" -> "group", "测试 " -> "测试"
    """
    cleaned = sender.strip()
    cleaned = re.sub(r'[\(（]\s*\d+\s*[\)）]', '', cleaned)
    return cleaned.strip()

def trim_conversation_history(messages, max_rounds=15):
    """
    Keep system messages intact and trim non-system messages to the most recent rounds.
    Each round consists of a user and an assistant message (2 messages per round).
    """
    system_messages = [m for m in messages if m["role"] == "system"]
    other_messages = [m for m in messages if m["role"] != "system"]
    trimmed_other = other_messages[-max_rounds * 2:]
    return system_messages + trimmed_other

def main():
    setup_logging()
    logging.info("Chatbot starting up with wxauto and full error logging...")
    
    try:
        # Get necessary user inputs.
        api_key = input("Enter OpenAI API Key: ").strip()
        model_name = input("Enter Model Name (e.g., gpt-3.5-turbo): ").strip()
        system_prompt = input("Enter System Prompt: ").strip()
        logging.info("Received API key, model name, and system prompt.")
        
        # Initialize OpenAI client.
        client = OpenAI(api_key=api_key, base_url="https://api.siliconflow.cn/v1")
        
        # Initialize conversation history with the system prompt.
        conversation = [{"role": "system", "content": system_prompt}]
        logging.info("Initialized conversation history with system prompt.")
        
        # Initialize wxauto for WeChat automation.
        wx = WeChat()
        bot_nickname = "@" + wx.nickname  # Bot's WeChat nickname.
        logging.info("wxauto initialized. Bot nickname: %s", bot_nickname)
        
        logging.info("Entering main loop for processing messages...")
        
        # Main loop to process new messages.
        while True:
            new_messages = wx.GetAllNewMessage()
            if new_messages:
                logging.info("New messages received: %s", new_messages)
            # The keys in new_messages represent chat groups.
            for chat, messages_list in new_messages.items():
                cleaned_chat = clean_sender(chat)
                for msg in messages_list:
                    # Each msg is a tuple; the first element is the actual sender,
                    # and the second is the message text.
                    actual_sender, msg_text = msg[0], msg[1]
                    # Skip if the sender is "SYS" or "Self"
                    if actual_sender in ["SYS", "Self"]:
                        continue
                    # Process only if the message text starts with the bot's nickname.
                    if not msg_text.startswith(bot_nickname):
                        continue
                    # Remove the bot mention from the text.
                    user_query = msg_text[len(bot_nickname):].strip()
                    logging.info("Message in chat '%s' from %s: %s", cleaned_chat, actual_sender, user_query)
                    
                    # Append the user's message to the conversation history.
                    conversation.append({"role": "user", "content": user_query})
                    
                    try:
                        logging.info("Sending conversation history to OpenAI API.")
                        response = client.chat.completions.create(
                            model=model_name,
                            messages=conversation,
                            temperature=0.7,
                            max_tokens=150
                        )
                        reply = response.choices[0].message.content.strip()
                        logging.info("Received reply from OpenAI API: %s", reply)
                        
                        # Send the reply via WeChat using the original chat group name.
                        wx.SendMsg(reply, who=cleaned_chat)
                        logging.info("Sent reply to chat '%s': %s", cleaned_chat, reply)
                        
                        # Append the assistant's reply to the conversation history.
                        conversation.append({"role": "assistant", "content": reply})
                        
                        # Trim the conversation history to keep only recent rounds.
                        conversation = trim_conversation_history(conversation, max_rounds=15)
                    
                    except Exception as e:
                        logging.error("Error generating reply for chat '%s': %s", cleaned_chat, e, exc_info=True)
                        wx.SendMsg("Sorry, encountered an error processing your request.", who=cleaned_chat)
            
            time.sleep(1)  # Poll for new messages every second.
    
    except Exception as e:
        logging.critical("Fatal error in main loop", exc_info=True)

if __name__ == "__main__":
    main()
