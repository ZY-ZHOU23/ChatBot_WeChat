import time
import logging
from wxauto import WeChat
from openai import OpenAI
from utils import setup_logging, clean_sender, trim_conversation_history, save_conversation_log
from context_builder import build_context

def main():
    setup_logging()
    logging.info("Chatbot starting up with wxauto and full error logging...")
    
    try:
        api_key = input("Enter OpenAI API Key: ").strip()
        model_name = input("Enter Model Name (e.g., gpt-3.5-turbo): ").strip()
        system_prompt = input("Enter System Prompt: ").strip()
        logging.info("Received API key, model name, and system prompt.")
        
        client = OpenAI(api_key=api_key, base_url="https://api.siliconflow.cn/v1")
        conversation = [{"role": "system", "content": system_prompt}]
        logging.info("Initialized conversation history with system prompt.")
        
        wx = WeChat()
        bot_nickname = "@" + wx.nickname
        logging.info("wxauto initialized. Bot nickname: %s", bot_nickname)
        
        logging.info("Entering main loop for processing messages...")
        
        while True:
            new_messages = wx.GetAllNewMessage()
            if new_messages:
                logging.info("New messages received: %s", new_messages)
            for chat, messages_list in new_messages.items():
                cleaned_chat = clean_sender(chat)
                for msg in messages_list:
                    actual_sender, msg_text = msg[0], msg[1]
                    # Skip messages from system or self.
                    if actual_sender in ["SYS", "Self"]:
                        continue
                    # Only process if the message text starts with the bot's nickname.
                    if not msg_text.startswith(bot_nickname):
                        continue
                    user_query = msg_text[len(bot_nickname):].strip()
                    logging.info("Message in chat '%s' from %s: %s", cleaned_chat, actual_sender, user_query)
                    
                    conversation.append({"role": "user", "content": user_query})
                    
                    try:
                        context = build_context(conversation, system_prompt, client, round_threshold=5, recent_rounds=2)
                        logging.info("Sending conversation context to OpenAI API: %s", context)
                        
                        response = client.chat.completions.create(
                            model=model_name,
                            messages=context,
                            temperature=0.7,
                            max_tokens=150
                        )
                        reply = response.choices[0].message.content.strip()
                        logging.info("Received reply from OpenAI API: %s", reply)
                        
                        wx.SendMsg(reply, who=cleaned_chat)
                        logging.info("Sent reply to chat '%s': %s", cleaned_chat, reply)
                        
                        conversation.append({"role": "assistant", "content": reply})
                        conversation = trim_conversation_history(conversation, max_rounds=15)
                        save_conversation_log(conversation)
                    
                    except Exception as e:
                        logging.error("Error generating reply for chat '%s': %s", cleaned_chat, e, exc_info=True)
                        wx.SendMsg("Sorry, encountered an error processing your request.", who=cleaned_chat)
            
            time.sleep(1)
    
    except Exception as e:
        logging.critical("Fatal error in main loop", exc_info=True)

if __name__ == "__main__":
    main()
    