import time
import logging
import sys
import re
import json
from wxauto import WeChat
from openai import OpenAI

# ----- Logging and Utility Functions -----
def setup_logging():
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
    
    def log_exceptions(exc_type, exc_value, exc_traceback):
        if issubclass(exc_type, KeyboardInterrupt):
            sys.__excepthook__(exc_type, exc_value, exc_traceback)
            return
        logging.error("Uncaught exception:", exc_info=(exc_type, exc_value, exc_traceback))
    sys.excepthook = log_exceptions

def clean_sender(sender: str) -> str:
    cleaned = sender.strip()
    cleaned = re.sub(r'[\(（]\s*\d+\s*[\)）]', '', cleaned)
    return cleaned.strip()

def trim_conversation_history(messages, max_rounds=15):
    system_messages = [m for m in messages if m["role"] == "system"]
    other_messages = [m for m in messages if m["role"] != "system"]
    trimmed_other = other_messages[-max_rounds * 2:]
    return system_messages + trimmed_other

def save_conversation_log(conversation):
    try:
        with open("conversation_history.log", "w", encoding="utf-8") as f:
            json.dump(conversation, f, ensure_ascii=False, indent=2)
        logging.info("Conversation history saved to conversation_history.log")
    except Exception as e:
        logging.error("Error saving conversation history: %s", e, exc_info=True)

# ----- Summarization and Context Building -----
def summarize_history(client, text):
    """
    Uses DeepSeek-V3 to generate a short summary of the provided text.
    The prompt instructs: "总结对话历史(字数不要太多)："
    """
    logging.info("Triggering summarization for older messages (text length: %d characters)", len(text))
    try:
        summary_response = client.chat.completions.create(
            model="deepseek-ai/DeepSeek-V3",
            messages=[{"role": "user", "content": "总结对话历史(字数不要太多)：\n" + text}],
            temperature=0.5,
            max_tokens=100
        )
        summary = summary_response.choices[0].message.content.strip()
        logging.info("Summarization complete. Summary: %s", summary)
        return summary
    except Exception as e:
        logging.error("Error summarizing conversation: %s", e, exc_info=True)
        return ""

def build_context(conversation, system_prompt, client, round_threshold=5, recent_rounds=2):
    """
    Build the conversation context for the API call.
    
    If non-system messages exceed round_threshold rounds, summarize older messages.
    Then build the context as:
      - system prompt,
      - (optionally) summary message,
      - recent rounds,
      - and a final system instruction for truncation.
    """
    non_system = [m for m in conversation if m["role"] != "system"]
    summary_message = None
    if len(non_system) > round_threshold * 2:
        older_messages = non_system[:-recent_rounds * 2]
        text = "\n".join([f'{m["role"]}：{m["content"]}' for m in older_messages])
        summary = summarize_history(client, text)
        if summary:
            summary_message = {"role": "system", "content": "对话摘要：" + summary}
            logging.info("Older messages summarized into a summary message.")
        else:
            logging.info("Summarization triggered but no summary was produced.")
    else:
        logging.info("Conversation history below summarization threshold; no summary generated.")
    
    recent_messages = non_system[-recent_rounds * 2:] if len(non_system) >= recent_rounds * 2 else non_system
    
    context = [{"role": "system", "content": system_prompt}]
    if summary_message:
        context.append(summary_message)
    context.extend(recent_messages)
    # Add instruction for token truncation.
    context.append({"role": "system", "content": "回复消息字数小于250字"})
    logging.info("Built context with %d messages for API call.", len(context))
    return context

# ----- Main Loop -----
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
                    if actual_sender in ["SYS", "Self"]:
                        continue
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
