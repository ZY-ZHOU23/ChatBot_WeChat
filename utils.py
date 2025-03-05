import time
import logging
import sys
import re
import json

"""
Builds the conversation context for each API call by starting with the system prompt, 
optionally adding a summary (if conversation history is long), 
appending the most recent conversation rounds, and adding a final instruction ("回复消息字数小于250字").
"""

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
    """Remove surrounding whitespace and any trailing member count (e.g. '(3)') from a sender's name."""
    cleaned = sender.strip()
    cleaned = re.sub(r'[\(（]\s*\d+\s*[\)）]', '', cleaned)
    return cleaned.strip()

def trim_conversation_history(messages, max_rounds=15):
    """
    Keeps system messages intact and trims non-system messages to the most recent rounds.
    Each round is assumed to consist of 2 messages (user + assistant).
    """
    system_messages = [m for m in messages if m["role"] == "system"]
    other_messages = [m for m in messages if m["role"] != "system"]
    trimmed_other = other_messages[-max_rounds * 2:]
    return system_messages + trimmed_other

def save_conversation_log(conversation):
    """Save the conversation history (a nested dictionary) in JSON format for inspection."""
    try:
        with open("conversation_history.log", "w", encoding="utf-8") as f:
            json.dump(conversation, f, ensure_ascii=False, indent=2)
        logging.info("Conversation history saved to conversation_history.log")
    except Exception as e:
        logging.error("Error saving conversation history: %s", e, exc_info=True)
