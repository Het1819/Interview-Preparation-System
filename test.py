from langchain_anthropic import ChatAnthropic
from dotenv import load_dotenv
import os
load_dotenv()
llm = ChatAnthropic(
    model="claude-sonnet-4-6",
    temperature=0,
    max_tokens=500,
    api_key=os.getenv("ANTHROPIC_API_KEY")
)

response = llm.invoke("Explain LangChain in simple words.")

print(response.content)













