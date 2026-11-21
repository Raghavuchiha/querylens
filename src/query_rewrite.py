from langchain_core.messages import HumanMessage, SystemMessage
from llm import get_llm

llm = get_llm()


def rewrite_query_with_history(current_query, chat_history):
    if not chat_history:
        return current_query

    messages = [
        SystemMessage(content="Given the chat history, rewrite the new question to be standalone and searchable. Just return the rewritten question."),
    ] + chat_history + [
        HumanMessage(content=f"New question: {current_query}")
    ]

    try:
        result = llm.invoke(messages)
        if isinstance(result.content, list):
            standalone_query = "".join(
                part if isinstance(part, str) else part.get("text", "")
                for part in result.content
            )
        else:
            standalone_query = result.content

        return standalone_query.strip() or current_query
    except Exception as e:
        print("Query rewrite failed:", e)
        return current_query
