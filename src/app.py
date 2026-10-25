import uuid

import requests
import streamlit as st

API_URL = "http://127.0.0.1:8000"

st.set_page_config(page_title="QueryLens", layout="wide")


# ------------------------------------------------------------
# SESSION STATE SETUP (persists across reruns, resets on server restart)
# ------------------------------------------------------------
if "conversations" not in st.session_state:
    st.session_state.conversations = {}


def start_new_conversation():
    new_id = str(uuid.uuid4())
    st.session_state.conversations[new_id] = []
    st.session_state.current_conversation_id = new_id


if "current_conversation_id" not in st.session_state:
    start_new_conversation()


def get_conversation_title(conversation_id):
    messages = st.session_state.conversations[conversation_id]
    if not messages:
        return "New chat"
    first_user_message = next((m["content"] for m in messages if m["role"] == "user"), "New chat")
    return first_user_message[:40] + ("..." if len(first_user_message) > 40 else "")


# ------------------------------------------------------------
# SIDEBAR
# ------------------------------------------------------------
with st.sidebar:
    st.title("QueryLens")

    if st.button("+ New Chat", use_container_width=True):
        start_new_conversation()
        st.rerun()

    st.divider()

    with st.expander("📁 Upload Documents"):
        uploaded_files = st.file_uploader(
            "Choose files", accept_multiple_files=True, key="uploader"
        )
        doc_type = st.text_input("Document type", value="official")

        if st.button("Upload"):
            if uploaded_files:
                files_payload = [
                    ("files", (f.name, f.getvalue())) for f in uploaded_files
                ]
                data_payload = {"doc_type": doc_type}

                try:
                    response = requests.post(
                        f"{API_URL}/upload", files=files_payload, data=data_payload
                    )
                    if response.status_code == 200:
                        result = response.json()
                        st.success(result["message"])
                        for item in result.get("skipped", []):
                            st.info(f"Skipped {item['file']}: {item['reason']}")
                        for item in result.get("errors", []):
                            st.warning(f"{item['file']}: {item['error']}")
                    else:
                        st.error(f"Upload failed: {response.text}")
                except requests.exceptions.ConnectionError:
                    st.error("Could not reach the API. Is the server running?")
            else:
                st.warning("Please select at least one file first.")

    st.divider()

    st.caption("Chat History")
    for conversation_id in list(st.session_state.conversations.keys())[::-1]:
        title = get_conversation_title(conversation_id)
        is_current = conversation_id == st.session_state.current_conversation_id

        if st.button(
            title,
            key=f"conv_{conversation_id}",
            use_container_width=True,
            type="primary" if is_current else "secondary",
        ):
            st.session_state.current_conversation_id = conversation_id
            st.rerun()


# ------------------------------------------------------------
# MAIN CHAT AREA
# ------------------------------------------------------------
current_id = st.session_state.current_conversation_id
current_messages = st.session_state.conversations[current_id]

st.title("Ask QueryLens")

for message in current_messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

user_input = st.chat_input("Ask a question about your documents...")

if user_input:
    current_messages.append({"role": "user", "content": user_input})
    with st.chat_message("user"):
        st.markdown(user_input)

    with st.chat_message("assistant"):
        with st.spinner("Thinking..."):
            try:
                response = requests.post(
                    f"{API_URL}/query",
                    json={"query": user_input, "conversation_id": current_id},
                )
                if response.status_code == 200:
                    result = response.json()

                    answer_text = result["answer"]
                    if result.get("citations"):
                        answer_text += "\n\n**Sources:**\n"
                        for citation in result["citations"]:
                            source = citation["doc_name"]
                            if citation.get("page"):
                                source += f", p. {citation['page']}"
                            answer_text += f"- {citation['claim']} *(from {source})*\n"

                    st.markdown(answer_text)
                    current_messages.append({"role": "assistant", "content": answer_text})
                else:
                    error_text = f"Error: {response.text}"
                    st.error(error_text)
                    current_messages.append({"role": "assistant", "content": error_text})

            except requests.exceptions.ConnectionError:
                error_text = "Could not reach the API. Is the server running?"
                st.error(error_text)
                current_messages.append({"role": "assistant", "content": error_text})