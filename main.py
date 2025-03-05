import time
import logging
import re
from wxauto import WeChat
from openai import OpenAI
from utils import setup_logging, clean_sender, trim_conversation_history, save_conversation_log
from context_builder import build_context
import threading

# You could export the file as a exe file using the command below: 
# pyinstaller --onefile main.py

# Global conversation history stored per group and per user.
# Used for independent conversation based on group and user.
# Structure: { group_chat: { sender: [ {role, content}, ... ] } }
conversation_history = {}

def main():
    """
    functionalities: 
    - The bot listens for new messages from the WeChat client.
    - It processes only messages that start with the bot's nickname.
    - Conversation history is maintained per group and per sender.
    - For each user message, the bot builds a context (via build_context), 
      sends it to the OpenAI API, and then sends a personalized reply (prefixed with @{sender}).
    - Conversation history is trimmed and logged for inspection.
    """

    setup_logging()
    logging.info("Chatbot starting up with wxauto and general conversation mode...")
    
    try:
        # Console input
        base_url = input("Enter the base url: ").strip()
        api_key = input("Enter API Key: ").strip()
        model_name = input("Enter Model Name (different by cloud service): ").strip()
        system_prompt = input("Enter System Prompt: ").strip()
        logging.info("Received API key, model name, and system prompt.")
        
        # Initialize LLM and wechat automation 
        """
        some base url
        Silicon flow: "https://api.siliconflow.cn/v1"
        Volcengine (can do online search): "https://ark.cn-beijing.volces.com/api/v3/bots"
        """
        client = OpenAI(api_key=api_key, base_url=base_url)
        wx = WeChat()
        bot_nickname = "@" + wx.nickname
        logging.info("wxauto initialized. Bot nickname: %s", bot_nickname)
        logging.info("Entering main loop for processing messages...")
        
        # Main conversation loop
        while True:
            new_messages = wx.GetAllNewMessage()
            if new_messages:
                logging.info("New messages received: %s", new_messages)
            
            # Process each chat group.
            for chat, messages_list in new_messages.items():
                cleaned_chat = clean_sender(chat)
                # Ensure conversation history for this group exists.
                if cleaned_chat not in conversation_history:
                    conversation_history[cleaned_chat] = {}
                
                for msg in messages_list:
                    actual_sender, msg_text = msg[0], msg[1]
                    # Skip system messages and self messages.
                    if actual_sender in ["SYS", "Self"]:
                        continue
                    
                    # Process only messages that start with the bot's nickname.
                    if not msg_text.startswith(bot_nickname):
                        continue
                    
                    # Remove the bot's nickname from the message.
                    content = msg_text[len(bot_nickname):].strip()
                    
                    # Initialize conversation history for this sender if needed.
                    if actual_sender not in conversation_history[cleaned_chat]:
                        conversation_history[cleaned_chat][actual_sender] = [{"role": "system", "content": system_prompt}]
                    
                    # Append user's message.
                    conversation_history[cleaned_chat][actual_sender].append({"role": "user", "content": content})
                    
                    try:
                        # Build context using this sender's conversation history.
                        user_history = conversation_history[cleaned_chat][actual_sender]
                        context = build_context(user_history, system_prompt, client, model_name, round_threshold=5, recent_rounds=2)
                        logging.info("Sending conversation context to OpenAI API for %s in '%s': %s", actual_sender, cleaned_chat, context)
                        
                        response = client.chat.completions.create(
                            model=model_name,
                            messages=context,
                            temperature=0.7,
                            max_tokens=150
                        )
                        reply = response.choices[0].message.content.strip()
                        logging.info("Received reply from OpenAI API: %s", reply)
                        
                        # Prepend sender's mention to reply.
                        personalized_reply = f"@{actual_sender} " + reply
                        wx.SendMsg(personalized_reply, who=cleaned_chat)
                        logging.info("Sent reply to chat '%s' for %s: %s", cleaned_chat, actual_sender, personalized_reply)
                        
                        conversation_history[cleaned_chat][actual_sender].append({"role": "assistant", "content": reply})
                        conversation_history[cleaned_chat][actual_sender] = trim_conversation_history(conversation_history[cleaned_chat][actual_sender], max_rounds=15)
                        save_conversation_log(conversation_history)
                    except Exception as e:
                        logging.error("Error generating reply for %s in chat '%s': %s", actual_sender, cleaned_chat, e, exc_info=True)
                        wx.SendMsg("Sorry, encountered an error processing your request.", who=cleaned_chat)
            time.sleep(1)
    
    except Exception as e:
        logging.critical("Fatal error in main loop", exc_info=True)

if __name__ == "__main__":
    main()
