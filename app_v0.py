from langchain_openai import AzureChatOpenAI
from langchain.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain.memory import ConversationBufferMemory
from langchain.schema.runnable import Runnable,RunnablePassthrough, RunnableLambda
from langchain.schema.runnable.config import RunnableConfig
from langchain.schema import StrOutputParser

from operator import itemgetter
from typing import Optional, Dict
from typing import cast

import chainlit as cl
from chainlit.types import ThreadDict

# Load environment variables    
from dotenv import load_dotenv
load_dotenv()

from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.memory import MemorySaver
from typing import Annotated
from typing_extensions import TypedDict
from operator import add
from langgraph.graph.message import add_messages
from collections import defaultdict

class State(TypedDict):
    messages: Annotated[list, add_messages]


llm = AzureChatOpenAI(
        azure_deployment="gpt-4o-mini",  # or your deployment
        api_version="2024-05-01-preview",  # or your api version
        # api_version="1",
        temperature=0,
        max_tokens=None,
        timeout=None,
        max_retries=2,
        # other params...
    )

def chatbot(state: State):
    return {"messages": [llm.invoke(state["messages"])]}

graph_builder = StateGraph(State)
graph_builder.add_node("chatbot", chatbot)
graph_builder.add_edge(START, "chatbot")
graph_builder.add_edge("chatbot", END)


def setup_runnable():
    memory = cl.user_session.get("memory") 
    graph = graph_builder.compile(checkpointer=memory)
    cl.user_session.set("runnable", graph)

@cl.on_chat_resume
async def on_chat_resume(thread: ThreadDict):
    # root_messages = [m for m in thread["steps"] if m["parentId"] == None]
    # print(type(root_messages))
    # print(root_messages)
    print("Chat resumed ------------------------------------------")
    print(thread)
    memory_saver = MemorySaver()
    memory_saver.storage = thread
    cl.user_session.set("memory", memory_saver)
    setup_runnable()

@cl.password_auth_callback
def auth_callback(username: str, password: str):
    # Fetch the user matching username from your database
    # and compare the hashed password with the value stored in the database
    if (username, password) == ("admin", "admin"):
        return cl.User(
            identifier="admin", metadata={"role": "admin", "provider": "credentials"}
        )
    # if username contain aksorn and password is 1234 
    elif "aksorn" in username and password == "1234":
        return cl.User(
            identifier=username, metadata={"role": "user", "provider": "credentials"}
        )
    else:
        return None


@cl.on_chat_start
async def on_chat_start():
    print("Chat started ------------------------------------------")
    cl.user_session.set("memory", MemorySaver())
    setup_runnable()
    cl.user_session.set("counter", 0)
    # app_user = cl.user_session.get("user")
    # await cl.Message(f"Hello {app_user.identifier}").send()


@cl.on_message
async def on_message(message: cl.Message):
    runnable = cl.user_session.get("runnable")
    counter = cl.user_session.get("counter", 0)
    msg = cl.Message(content="")
    config = {"configurable": {"thread_id": cl.context.session.thread_id}}
    async for output in runnable.astream(
        {"messages":message.content},
        config,
        stream_mode="updates"):
        for key, value in output.items():
            await msg.stream_token(value["messages"][-1].content)

    await msg.send()
    counter += 1
    cl.user_session.set("counter", counter)