# import os
# from dotenv import load_dotenv
# import chainlit as cl
# load_dotenv()

# from langgraph.graph import START, MessagesState, StateGraph
# import chainlit as cl
# from langchain_openai import AzureChatOpenAI
# from langchain_core.messages import HumanMessage, AIMessageChunk
# from langchain_core.runnables.config import RunnableConfig

# model = AzureChatOpenAI(
#     azure_deployment="gpt-4o-mini",  # or your deployment
#     api_version="2024-05-01-preview",  # or your API version
#     temperature=0,
#     max_tokens=None,
#     timeout=None,
#     max_retries=2,
#     streaming=True,
# )

# # Define the workflow
# workflow = StateGraph(state_schema=MessagesState)

# def call_model(state: MessagesState):
#     response = model.invoke(state["messages"])
#     return {"messages": response}

# workflow.add_edge(START, "model")
# workflow.add_node("model", call_model)

# def setup_runnable():
#     print("test setup_runnable")
#     postgres_checkpointer =  cl.user_session.get("memory") 
#     # Use the AzureChatOpenAI model from your configuration
#     # Compile the workflow using the checkpointer
#     session_app = workflow.compile(checkpointer=postgres_checkpointer)
    
#     # Store the workflow (and its persistent memory) in the user session
#     # print("test invoke",session_app.invoke({"messages": [HumanMessage(content="Hello")]},{"configurable": {"thread_id": cl.context.session.thread_id}}) )
#     cl.user_session.set("app", session_app)

# @cl.on_chat_start
# async def on_chat_start():
#     print("Chat start")
#     cl.user_session.set("counter", 0)
#     db_uri = os.getenv("DB_URI")
#     if not db_uri:
#         raise ValueError("DB_URI not found in environment variables")
        
#     # Establish a synchronous Postgres connection for this session
#     from psycopg import AsyncConnection
#     postgres_conn = await AsyncConnection.connect(db_uri)
    
#     # Create a synchronous checkpointer for this connection
#     # (Assuming a synchronous version is available as PostgresSaver)
#     from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
#     postgres_checkpointer = AsyncPostgresSaver(postgres_conn)
    
#     await postgres_checkpointer.setup()
    
#     # Store the checkpointer in the user session under "memory"
#     cl.user_session.set("memory", postgres_checkpointer)
#     print("Checkpoint setup completed.")
#     setup_runnable()
   

# @cl.password_auth_callback
# def auth_callback(username: str, password: str):
#     if (username, password) == ("admin", "admin"):
#         return cl.User(identifier="admin", metadata={"role": "admin", "provider": "credentials"})
#     else:
#         return None

# @cl.on_message
# async def main(message: cl.Message):
#     msg = cl.Message(content="")
#     app = cl.user_session.get("app")
#     if app is None:
#         msg.update(content="Error: Persistent memory not initialized.")

#     inputs = {"messages": [HumanMessage(content=message.content)]}
#     config: RunnableConfig = {"configurable": {"thread_id": cl.context.session.thread_id}}
#     async for output in app.astream_log(inputs,config, include_types=["llm"]):
#         for op in output.ops:
#             if op["path"] == "/streamed_output/-":
#                 # If needed, handle the general streamed output here
#                 pass
#             elif op["path"].startswith("/logs/") and op["path"].endswith("/streamed_output/-"):
#                 try:
#                     # Get the content from the operation.
#                     content_val = op["value"].content
#                     token_data = None

#                     # Handle different types of content structures.
#                     if isinstance(content_val, list):
#                         # Ensure list is not empty.
#                         if content_val:
#                             token_data = content_val[0]
#                     elif isinstance(content_val, dict):
#                         token_data = content_val
#                     elif isinstance(content_val, str):
#                         token_data = {"text": content_val}

#                     # If token_data is empty, skip.
#                     if not token_data:
#                         continue

#                     # Now, extract the token text.
#                     if "partial_json" in token_data:
#                         token = token_data["partial_json"]
#                     elif "text" in token_data:
#                         token = token_data["text"]
#                     else:
#                         token = token_data  # Fallback if not in expected format

#                     await msg.stream_token(token)
#                 except Exception as e:
#                     print("Error processing token:", e)

#     await msg.send()

# # @cl.on_chat_resume
# # async def on_chat_resume(thread: dict):
# #     """
# #     Resume a langgraph session by mapping the stored thread checkpoint into
# #     the AsyncPostgresSaver instance and reinitializing the workflow.
    
# #     We assume the thread contains:
# #       - "checkpoint": the saved checkpoint state (e.g. a serialized object)
# #       - "metadata": associated metadata for the checkpoint (optional)
# #     """
# #     # Extract checkpoint data and metadata from the thread
# #     checkpoint_data = thread.get("checkpoint")
# #     checkpoint_metadata = thread.get("metadata", {})

# #     # Retrieve the AsyncPostgresSaver from the user session.
# #     # This is the persistent memory that was set during the on_chat_start session.
# #     postgres_checkpointer = cl.user_session.get("memory")
# #     if postgres_checkpointer is None:
# #         # If for some reason it doesn't exist (e.g. a fresh start), reinitialize it.
# #         db_uri = os.getenv("DB_URI")
# #         from psycopg import AsyncConnection
# #         postgres_conn = await AsyncConnection.connect(db_uri)
# #         from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
# #         postgres_checkpointer = AsyncPostgresSaver(postgres_conn)
# #         await postgres_checkpointer.setup()
# #         cl.user_session.set("memory", postgres_checkpointer)

# #     # Map the checkpoint state from the thread into the checkpointer.
# #     # The configuration here ties the state to the current thread ID.
# #     config = {"configurable": {"thread_id": cl.context.session.thread_id}}
# #     if checkpoint_data:
# #         postgres_checkpointer.put(config, checkpoint_data, checkpoint_metadata, {})
# #         print("Checkpoint resumed from thread.")
# #     else:
# #         print("No checkpoint data found in thread. Starting a new session.")

# #     # Reinitialize the runnable workflow with the resumed state.
# #     setup_runnable()
# @cl.on_chat_resume
# async def on_chat_resume(thread: dict):
#     """
#     Resume a langgraph session by reinitializing the AsyncPostgresSaver and,
#     if available, restoring its checkpoint state from the thread data.
#     """
#     import os
#     from psycopg import AsyncConnection
#     from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver

#     # (Optional) If you want to reconstruct the conversation context from thread messages,
#     # you could use a ConversationBufferMemory here.
#     # However, for the persistent state of the workflow, we reinitialize the saver.
    
#     # Reinitialize the Postgres connection and the saver just as in on_chat_start.
#     db_uri = os.getenv("DB_URI")
#     if not db_uri:
#         raise ValueError("DB_URI not found in environment variables")
#     postgres_conn = await AsyncConnection.connect(db_uri)
#     postgres_checkpointer = AsyncPostgresSaver(postgres_conn)
#     await postgres_checkpointer.setup()

#     # Use the same config key as in the start session.
#     config = {"configurable": {"thread_id": cl.context.session.thread_id}}

#     # Try to retrieve checkpoint data and metadata from the thread.
#     # It is expected that when checkpointing, your code stored these in the thread dict.
#     checkpoint_data = thread.get("checkpoint")
#     checkpoint_metadata = thread.get("metadata", {})

#     if checkpoint_data:
#         # Restore the checkpoint state into the saver.
#         postgres_checkpointer.put(config, checkpoint_data, checkpoint_metadata, {})
#         print("Resumed checkpoint from thread.")
#     else:
#         print("No checkpoint data found in thread. Starting a new session.")

#     # Store the reinitialized saver in the user session as "memory"
#     cl.user_session.set("memory", postgres_checkpointer)

#     # Finally, recompile the runnable workflow with the (resumed) persistent memory.
#     setup_runnable()



import os
from dotenv import load_dotenv
import chainlit as cl
load_dotenv()

from langgraph.graph import START, MessagesState, StateGraph
from langchain_openai import AzureChatOpenAI
from langchain_core.messages import HumanMessage, AIMessageChunk
from langchain_core.runnables.config import RunnableConfig

# Initialize your model with streaming enabled
model = AzureChatOpenAI(
    azure_deployment="gpt-4o-mini",  # or your deployment
    api_version="2024-05-01-preview",  # or your API version
    temperature=0,
    max_tokens=None,
    timeout=None,
    max_retries=2,
    streaming=True,
)

# Define the workflow graph
workflow = StateGraph(state_schema=MessagesState)

def call_model(state: MessagesState):
    response = model.invoke(state["messages"])
    return {"messages": response}

workflow.add_edge(START, "model")
workflow.add_node("model", call_model)

def setup_runnable():
    print("test setup_runnable")
    postgres_checkpointer = cl.user_session.get("memory")
    # Compile the workflow using the checkpointer
    session_app = workflow.compile(checkpointer=postgres_checkpointer)
    
    # Store the workflow (and its persistent memory) in the user session
    cl.user_session.set("app", session_app)

@cl.on_chat_start
async def on_chat_start():
    print("Chat start")
    cl.user_session.set("counter", 0)
    db_uri = os.getenv("DB_URI")
    if not db_uri:
        raise ValueError("DB_URI not found in environment variables")
        
    # Establish an asynchronous Postgres connection for this session
    from psycopg import AsyncConnection
    postgres_conn = await AsyncConnection.connect(db_uri)
    
    # Create an asynchronous checkpointer for this connection
    from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
    postgres_checkpointer = AsyncPostgresSaver(postgres_conn)
    await postgres_checkpointer.setup()
    
    # Store the checkpointer in the user session under "memory"
    cl.user_session.set("memory", postgres_checkpointer)
    print("Checkpoint setup completed.")
    setup_runnable()

@cl.password_auth_callback
def auth_callback(username: str, password: str):
    if (username, password) == ("admin", "admin"):
        return cl.User(identifier="admin", metadata={"role": "admin", "provider": "credentials"})
    else:
        return None

@cl.on_message
async def main(message: cl.Message):
    msg = cl.Message(content="")
    app = cl.user_session.get("app")
    if app is None:
        msg.update("Error: Persistent memory not initialized.")
        await msg.send()
        return

    inputs = {"messages": [HumanMessage(content=message.content)]}
    config: RunnableConfig = {"configurable": {"thread_id": cl.context.session.thread_id}}
    
    # A flag to ensure we only send one checkpoint message per session
    checkpoint_sent = False

    # Process the streaming output
    async for output in app.astream_log(inputs, config, include_types=["llm"]):
        for op in output.ops:
            if op["path"] == "/streamed_output/-":
                # Optionally handle non-log streamed output here.
                pass
            elif op["path"].startswith("/logs/") and op["path"].endswith("/streamed_output/-"):
                try:
                    # Extract token information from the operation.
                    content_val = op["value"].content
                    token_data = None

                    if isinstance(content_val, list) and content_val:
                        token_data = content_val[0]
                    elif isinstance(content_val, dict):
                        token_data = content_val
                    elif isinstance(content_val, str):
                        token_data = {"text": content_val}

                    if not token_data:
                        continue

                    if "partial_json" in token_data:
                        token = token_data["partial_json"]
                    elif "text" in token_data:
                        token = token_data["text"]
                    else:
                        token = token_data  # Fallback

                    # Stream the token to the client
                    await msg.stream_token(token)

                    # Check for the specific condition to trigger a checkpoint.
                    # (Adjust the condition as needed for your use case.)
                    if not checkpoint_sent and token.strip() == "This is node 2":
                        # Retrieve the current checkpoint state from the saver.
                        postgres_checkpointer = cl.user_session.get("memory")
                        config_checkpoint = {"configurable": {"thread_id": cl.context.session.thread_id}}
                        checkpoint = postgres_checkpointer.get(config_checkpoint)
                        
                        # Serialize the checkpoint state
                        # from langgraph.serialization import JsonPlusSerializer
                        # serde = JsonPlusSerializer()
                        from langgraph.checkpoint.serde import jsonplus
                        serde = jsonplus
                        ser_type, ckpt_bytes = serde.dumps_typed(checkpoint)
                        # Encode the checkpoint bytes into a string (using latin1)
                        checkpoint_str = ckpt_bytes.decode("latin1")
                        
                        # Send a checkpoint message that will be stored in the thread's history.
                        cl.send_message(
                            content=checkpoint_str,
                            type="checkpoint",
                            metadata={"node": "node2"}
                        )
                        checkpoint_sent = True
                        print("Sent checkpoint message from streaming loop.")

                except Exception as e:
                    print("Error processing token:", e)

    await msg.send()

@cl.on_chat_resume
async def on_chat_resume(thread: dict):
    """
    Resume the langgraph session by reinitializing the AsyncPostgresSaver and,
    if available, restoring its checkpoint state from the thread data.
    """
    import os
    from psycopg import AsyncConnection
    from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
    # from langgraph.serialization import JsonPlusSerializer
    from langgraph.checkpoint.serde import jsonplus

    db_uri = os.getenv("DB_URI")
    if not db_uri:
        raise ValueError("DB_URI not found in environment variables")
    
    # Reinitialize the Postgres connection and the saver
    postgres_conn = await AsyncConnection.connect(db_uri)
    postgres_checkpointer = AsyncPostgresSaver(postgres_conn)
    await postgres_checkpointer.setup()

    config = {"configurable": {"thread_id": cl.context.session.thread_id}}

    # Look for a checkpoint message in the thread's steps.
    checkpoint_data = None
    checkpoint_metadata = {}
    for msg in thread.get("steps", []):
        if msg.get("type") == "checkpoint":
            checkpoint_str = msg.get("output")
            # Convert the stored string back to bytes.
            ckpt_bytes = checkpoint_str.encode("latin1")
            serde = jsonplus()
            checkpoint_data = serde.loads_typed(("msgpack", ckpt_bytes))
            checkpoint_metadata = msg.get("metadata", {})
            break

    if checkpoint_data:
        postgres_checkpointer.put(config, checkpoint_data, checkpoint_metadata, {})
        print("Resumed checkpoint from thread.")
    else:
        print("No checkpoint data found in thread. Starting a new session.")

    # Save the reinitialized saver in the user session.
    cl.user_session.set("memory", postgres_checkpointer)
    
    # Recompile the runnable workflow with the (resumed) persistent memory.
    setup_runnable()
