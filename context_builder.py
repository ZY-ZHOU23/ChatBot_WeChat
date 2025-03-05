import logging

# Contains helper functions for logging, cleaning sender names, 
# trimming conversation history, and saving conversation logs.

def summarize_history(client, text, model_name):
    """
    Uses DeepSeek-V3 to generate a short summary of the provided text.
    The prompt instructs: "总结对话历史(字数不要太多)："
    """
    logging.info("Triggering summarization for older messages (text length: %d characters)", len(text))
    try:
        summary_response = client.chat.completions.create(
            model=model_name,
            messages=[{"role": "user", "content": "这是我们之前的对话记录，请总结我们的对话历史（字数不要太多）：\n" + text}],
            temperature=0.5,
            max_tokens=200
        )
        summary = summary_response.choices[0].message.content.strip()
        logging.info("Summarization complete. Summary: %s", summary)
        return summary
    except Exception as e:
        logging.error("Error summarizing conversation: %s", e, exc_info=True)
        return ""

def build_context(conversation, system_prompt, client, model_name, round_threshold=5, recent_rounds=2):
    """
    Builds the conversation context for the API call.
    
    1. Start with the system prompt.
    2. If non-system messages exceed round_threshold rounds, summarize older messages.
    3. Append the most recent rounds in full detail.
    4. Add a final system instruction: "回复消息字数小于250字".
    """
    non_system = [m for m in conversation if m["role"] != "system"]
    summary_message = None
    if len(non_system) > round_threshold * 2:
        older_messages = non_system[:-recent_rounds * 2]
        text = "\n".join([f'{m["role"]}：{m["content"]}' for m in older_messages])
        summary = summarize_history(client, text, model_name)
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
    context.append({"role": "system", "content": "回复消息字数小于250字"})
    logging.info("Built context with %d messages for API call.", len(context))
    return context
