from langchain_openai import AzureChatOpenAI
from langchain.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain.memory import ConversationBufferMemory
from langchain.schema.runnable import Runnable,RunnablePassthrough, RunnableLambda
from langchain.schema.runnable.config import RunnableConfig
from langchain.schema import StrOutputParser
from chainlit.data.sql_alchemy import SQLAlchemyDataLayer
from operator import itemgetter
from typing import Optional, Dict
from typing import cast
import chainlit as cl
from chainlit.types import ThreadDict

# Load environment variables    
from dotenv import load_dotenv
load_dotenv()

def setup_runnable():
    memory = cl.user_session.get("memory")  # type: ConversationBufferMemory
    model = AzureChatOpenAI(
        azure_deployment="gpt-4o-mini",  # or your deployment
        api_version="2024-05-01-preview",  # or your api version
        # api_version="1",
        temperature=0,
        max_tokens=None,
        timeout=None,
        max_retries=2,
        # other params...
    )
    prompt = ChatPromptTemplate.from_messages(
        [
            ("system", "You are a helpful chatbot"),
            MessagesPlaceholder(variable_name="history"),
            ("human", "{question}"),
        ]
    )

    runnable = (
        RunnablePassthrough.assign(
            history=RunnableLambda(memory.load_memory_variables) | itemgetter("history")
        )
        | prompt
        | model
        | StrOutputParser()
    )
    cl.user_session.set("runnable", runnable)

@cl.on_chat_resume
async def on_chat_resume(thread: ThreadDict):
    memory = ConversationBufferMemory(return_messages=True)
    root_messages = [m for m in thread["steps"] if m["parentId"] == None]
    for message in root_messages:
        if message["type"] == "user_message":
            memory.chat_memory.add_user_message(message["output"])
        else:
            memory.chat_memory.add_ai_message(message["output"])

    cl.user_session.set("memory", memory)

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
    cl.user_session.set("memory", ConversationBufferMemory(return_messages=True))
    setup_runnable()
    cl.user_session.set("counter", 0)
    # app_user = cl.user_session.get("user")
    # await cl.Message(f"Hello {app_user.identifier}").send()


@cl.on_message
async def on_message(message: cl.Message):
    memory = cl.user_session.get("memory") 
    runnable = cl.user_session.get("runnable")
    counter = cl.user_session.get("counter", 0)
    msg = cl.Message(content="")
    config: RunnableConfig = {
        "configurable": {"thread_id": cl.context.session.thread_id}
    }

    async for chunk in runnable.astream(
        {"question": message.content},
        # config=RunnableConfig(callbacks=[cl.LangchainCallbackHandler()]),
        config
    ):
        await msg.stream_token(chunk)

    await msg.send()

    counter += 1
    cl.user_session.set("counter", counter)
    memory.chat_memory.add_user_message(message.content)
    memory.chat_memory.add_ai_message(msg.content)