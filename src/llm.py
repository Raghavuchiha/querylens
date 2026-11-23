import os
from dotenv import load_dotenv
from langchain_openai import ChatOpenAI

load_dotenv()


def get_llm(temperature=0):
    return ChatOpenAI(
        model=os.getenv("GROQ_MODEL", "openai/gpt-oss-120b"),
        base_url="https://api.groq.com/openai/v1",
        api_key=os.environ["GROQ_API_KEY"],
        temperature=temperature,
        max_tokens=2048,
        timeout=45,
        max_retries=2,
    )
