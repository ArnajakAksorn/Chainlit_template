import os
from dotenv import load_dotenv
load_dotenv()

# Use the AzureChatOpenAI model from your configuration
from langchain_openai import AzureChatOpenAI
model = AzureChatOpenAI(
    azure_deployment="gpt-4o-mini",  # or your deployment
    api_version="2024-05-01-preview",  # or your API version
    temperature=0,
    max_tokens=None,
    timeout=None,
    max_retries=2,
)

from langgraph.graph import START, MessagesState, StateGraph
import chainlit as cl

# Define the workflow
workflow = StateGraph(state_schema=MessagesState)

def call_model(state: MessagesState):
    response = model.invoke(state["messages"])
    return {"messages": response}

workflow.add_edge(START, "model")
workflow.add_node("model", call_model)

@cl.on_chat_start
async def chat_start():
    """
    Initialize the PostgreSQL checkpointer and compile the workflow
    for this specific chat session.
    """
    db_uri = os.getenv("DB_URI")
    if not db_uri:
        raise ValueError("DB_URI not found in environment variables")
        
    # Establish a Postgres connection for this session
    from psycopg import AsyncConnection
    postgres_conn = await AsyncConnection.connect(db_uri)
    
    # Create a checkpointer for this connection
    from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
    postgres_checkpointer = AsyncPostgresSaver(postgres_conn)
    await postgres_checkpointer.setup()
    cl.user_session.set("memory",postgres_checkpointer)

    # Compile the workflow using the checkpointer
    session_app = workflow.compile(checkpointer=postgres_checkpointer)
    
    # Store the workflow (and its persistent memory) in the user session
    cl.user_session.set("app", session_app)

@cl.password_auth_callback
def auth_callback(username: str, password: str):
    if (username, password) == ("admin", "admin"):
        return cl.User(identifier="admin", metadata={"role": "admin", "provider": "credentials"})
    else:
        return None

@cl.on_message
async def main(message: cl.Message):
    answer = cl.Message(content="")
    await answer.send()
    # memory = cl.user_session.get("memory") 

    from langchain_core.messages import HumanMessage, AIMessageChunk
    from langchain_core.runnables.config import RunnableConfig

    config: RunnableConfig = {"configurable": {"thread_id": cl.context.session.thread_id}}

    # Retrieve the workflow (with persistent memory) for this session
    app = cl.user_session.get("app")
    if app is None:
        await answer.update(content="Error: Persistent memory not initialized.")
        return

    # Stream responses from the workflow while maintaining persistent memory
    async for msg, _ in app.astream(
        {"messages": [HumanMessage(content=message.content)]},
        config,
        stream_mode="messages",
    ):
        if isinstance(msg, AIMessageChunk):
            answer.content += msg.content
            await answer.update()

@cl.on_chat_resume
async def on_chat_resume(thread: dict):
    """
    Resume the conversation by reconnecting to PostgreSQL,
    compiling the workflow with the persistent checkpointer,
    and reloading the conversation history from the thread.
    """
    # Retrieve your DB connection URI from environment variables
    db_uri = os.getenv("DB_URI")
    if not db_uri:
        raise ValueError("DB_URI not found in environment variables")
    
    # Re-establish a PostgreSQL connection for this session
    from psycopg import AsyncConnection
    postgres_conn = await AsyncConnection.connect(db_uri)
    
    # Initialize the PostgreSQL checkpointer
    from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
    postgres_checkpointer = AsyncPostgresSaver(postgres_conn)
    await postgres_checkpointer.setup()
    
    # Compile the workflow using the checkpointer (this loads the persisted state if available)
    resumed_app = workflow.compile(checkpointer=postgres_checkpointer)
    
    # Reconstruct the conversation history from the thread steps
    # Note: We assume root messages (without parentId) are the conversation starters.
    from langchain_core.messages import HumanMessage, AIMessage
    conversation_history = []
    root_messages = [m for m in thread["steps"] if m.get("parentId") is None]
    for message in root_messages:
        if message["type"] == "user_message":
            conversation_history.append(HumanMessage(content=message["output"]))
        else:
            # Any non-user message will be treated as an AI response.
            conversation_history.append(AIMessage(content=message["output"]))
    
    # Set the resumed state in the workflow.
    # We assume that the workflow's state is a dict with a key "messages"
    # This call "injects" the conversation history into the workflow.
    initial_state = {"messages": conversation_history}
    resumed_app.get_state(initial_state)  # Ensure your workflow instance supports state updates.
    
    # Store the resumed workflow in the session so that on_message can access it.
    cl.user_session.set("app", resumed_app)