import os
from dotenv import load_dotenv
from langchain_groq import ChatGroq

load_dotenv()

llm = ChatGroq(
    model=os.getenv(
        "WORKPILOT_MODEL",
        "llama-3.3-70b-versatile"
    ),
    temperature=0
)

response = llm.invoke(
    "Explain what an autonomous AI agent is in one sentence."
)

print("\nGROQ RESPONSE:")
print(response.content)