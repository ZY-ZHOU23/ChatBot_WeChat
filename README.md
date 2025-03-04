# WeChat Chatbot for Conversational AI

## Overview
This project implements a WeChat chatbot that uses OpenAI's API to deliver context-aware conversational responses. It integrates directly with WeChat to retrieve and process messages in real time, ensuring dynamic and coherent interactions with users.

## Features
- **Conversational AI**: Leverages OpenAI's API to generate responses based on ongoing conversation history.
- **WeChat Integration**: Automatically retrieves and processes incoming messages from WeChat.
- **Contextual Memory**: Maintains conversation context to enhance the relevance and coherence of responses.
- **Background Processing**: Runs background tasks to continuously monitor for new messages and manage interactions.

## Requirements
- **PC WeChat Version**: Requires PC WeChat version **3.9.11.17**.
- **Python 3.x**: Ensure you have an appropriate version of Python installed.
- **OpenAI API Key**: A valid API key is necessary to interact with OpenAI's services.

## How It Works
- **Message Retrieval**: The chatbot listens for incoming messages from WeChat.
- **Context Building**: The `context_builder.py` module constructs the conversation context by incorporating recent message history.
- **Response Generation**: The `main.py` script sends the conversation context to OpenAI's API and processes the generated response.
- **Utility Functions**: The `utils.py` module provides supporting functionality for logging, message formatting, and other helper tasks.

## References & Credits
This project is inspired by and references the following repositories:
- [Deepseek WeChat](https://github.com/CatBallV/Deepseek_wechat?tab=readme-ov-file)
- [WxAuto](https://github.com/cluic/wxauto)

