from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage

llm = ChatGoogleGenerativeAI(model="gemini-3.6-flash", temperature=0)


def rewrite_query_with_history(current_query, chat_history):
    if not chat_history:
        return current_query

    messages = [
        SystemMessage(content="Given the chat history, rewrite the new question to be standalone and searchable. Just return the rewritten question."),
    ] + chat_history + [
        HumanMessage(content=f"New question: {current_query}")
    ]

    result = llm.invoke(messages)

    # .content can be a plain string OR a list of content parts depending on response type
    if isinstance(result.content, list):
        standalone_query = "".join(
            part if isinstance(part, str) else part.get("text", "")
            for part in result.content
        )
    else:
        standalone_query = result.content

    standalone_query = standalone_query.strip()

    return standalone_query