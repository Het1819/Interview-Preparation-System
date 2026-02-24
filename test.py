import smtplib
from email.message import EmailMessage

# 1. Setup your credentials and content
email_sender = "het.patel.ias@gmail.com"
email_password = "coafrmautnxqyyrf"  # Not your regular password!
email_receiver = "phet6011@gmail.com"

subject = "Check out this Python script!"
body = "Hello! This email was sent directly from a Python script. Neat, right?"

# 2. Create the email structure
em = EmailMessage()
em['From'] = email_sender
em['To'] = email_receiver
em['Subject'] = subject
em.set_content(body)

# 3. Connect to the server and send
# Using Gmail's SMTP server as an example
try:
    with smtplib.SMTP_SSL('smtp.gmail.com', 465) as smtp:
        smtp.login(email_sender, email_password)
        smtp.send_message(em)
    print("Email sent successfully!")
except Exception as e:
    print(f"Something went wrong: {e}")






# from document_loader import SmartLoader
# pdf_loader = SmartLoader()
# # job_data = pdf_loader.load_image("01_test_case.png")
# job_data = pdf_loader.load_docx("JD FOR KNOWN.docx")
# resume_data = pdf_loader.load_pdf("Naval_Dhandha_DA (1).pdf") 

# print(resume_data)
# print(job_data)


# from google import genai
# client = genai.Client(api_key="")
# response = client.models.generate_content(
#     model="gemini-2.5-flash",
#     contents=["Please describe this image:", job_data]
# )
# print(response.text)







# from pypdf import PdfReader

# reader = PdfReader("Naval_Dhandha_DA (1).pdf")

# document_txt = " "
# for page in reader.pages:
#     document_txt += page.extract_text()

# print(document_txt)







# import os
# from langchain_ollama import ChatOllama
# from langchain_core.messages import HumanMessage
# from langgraph.prebuilt import create_react_agent
# from langchain_core.tools import tool

# # Using a lighter model to ensure it fits in your 3.7GB RAM
# llm = ChatOllama(
#     model="smollm2:1.7b", 
#     temperature=0
# )

# @tool
# def check_interview_slots(date: str):
#     """Checks available interview slots for a specific date."""
#     return ["10:00 AM", "2:00 PM", "4:30 PM"]

# tools = [check_interview_slots]
# app = create_react_agent(llm, tools)

# print('---Starting Local Agent---')

# # FIXED: key must be lowercase "messages"
# inputs = {"messages": [HumanMessage(content="What times are available for interviews on Friday?")]}

# try:
#     for chunk in app.stream(inputs, stream_mode="values"):
#         final_result = chunk["messages"][-1].content
#     print("\nAgent Response:", final_result)
# except Exception as e:
#     print(f"Error: {e}")
#     print("TIP: Close Chrome or other apps to free up RAM for Ollama.")



# # from langchain.agents import create_agent

# # def get_weather(city:str) -> str:
# #     """
# #     Docstring for get_weather
    
# #     :param city: Description
# #     :type city: str
# #     :return: Description
# #     :rtype: str
# #     """
# #     return f"It's always sunny in {city}"


# # agent = create_agent(
# #     model="gpt-3.5-turbo",
# #     tools=[get_weather],
# #     system_prompt="You are a helpful assistant"
# # )

# # agent.invoke(
# #     {"messages": [{"role": "user", "content": "what is the weather in sf"}]}
# # )