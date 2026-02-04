import os
from langchain_ollama import ChatOllama
from langchain_core.messages import HumanMessage
from langgraph.prebuilt import create_react_agent
from langchain_core.tools import tool

# Using a lighter model to ensure it fits in your 3.7GB RAM
llm = ChatOllama(
    model="smollm2:1.7b", 
    temperature=0
)

@tool
def check_interview_slots(date: str):
    """Checks available interview slots for a specific date."""
    return ["10:00 AM", "2:00 PM", "4:30 PM"]

tools = [check_interview_slots]
app = create_react_agent(llm, tools)

print('---Starting Local Agent---')

# FIXED: key must be lowercase "messages"
inputs = {"messages": [HumanMessage(content="What times are available for interviews on Friday?")]}

try:
    for chunk in app.stream(inputs, stream_mode="values"):
        final_result = chunk["messages"][-1].content
    print("\nAgent Response:", final_result)
except Exception as e:
    print(f"Error: {e}")
    print("TIP: Close Chrome or other apps to free up RAM for Ollama.")










# import os
# from langchain_groq import ChatGroq
# from langchain_core.tools import tool
# from langgraph.prebuilt import create_react_agent

# # 1. Set your Free API Key (Get it from console.groq.com)
# os.environ["GROQ_API_KEY"] = "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"

# # 2. Define the tool using the @tool decorator (better for LangGraph)
# @tool
# def get_weather(city: str) -> str:
#     """
#     Returns the current weather for a given city.
#     """
#     return f"It's always sunny in {city}"


# # 3. Use a powerful free model like Llama 3
# # Note: Groq is compatible with the standard LangGraph agent factory
# llm = ChatGroq(
#     model="llama-3.3-70b-versatile",
#     temperature=0
# )

# # 4. Create the agent
# tools = [get_weather]
# agent = create_react_agent(llm, tools)

# # 5. Run the agent
# result = agent.invoke(
#     {"messages": [{"role": "user", "content": "what is the weather in ahmedabad"}]}
# )

# # Print the last message from the agent
# print(result["messages"][-1].content)













# from langchain.agents import create_agent

# def get_weather(city:str) -> str:
#     """
#     Docstring for get_weather
    
#     :param city: Description
#     :type city: str
#     :return: Description
#     :rtype: str
#     """
#     return f"It's always sunny in {city}"


# agent = create_agent(
#     model="gpt-3.5-turbo",
#     tools=[get_weather],
#     system_prompt="You are a helpful assistant"
# )

# agent.invoke(
#     {"messages": [{"role": "user", "content": "what is the weather in sf"}]}
# )