
class Conversation:
    """
    Manages conversation history by keeping system messages intact and truncating
    the conversation history (user and assistant messages) to a specified limit.
    """
    def __init__(self, system_prompt, max_rounds=15):
        # Keep system messages separate so they always persist.
        self.system_messages = [{"role": "system", "content": system_prompt}]
        self.user_assistant_history = []  # holds all non-system messages
        self.max_history = max_rounds * 2  # each round consists of a user and an assistant message

    def add_message(self, role, content):
        """Adds a new message to the conversation."""
        if role == "system":
            self.system_messages.append({"role": role, "content": content})
        else:
            self.user_assistant_history.append({"role": role, "content": content})
            # Truncate if exceeding the maximum allowed history.
            if len(self.user_assistant_history) > self.max_history:
                self.user_assistant_history = self.user_assistant_history[-self.max_history:]

    def get_history(self):
        """Returns the full conversation history (system + user/assistant messages)."""
        return self.system_messages + self.user_assistant_history
