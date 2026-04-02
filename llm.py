import os

from dotenv import load_dotenv
from groq import Groq

load_dotenv()  # loads .env into environment
GROQ_API_KEY = os.getenv("GROQ_API_KEY")

client = Groq(
    api_key=GROQ_API_KEY,
)
prompt=None
with open("prompt.txt","r") as f:
  prompt=f.read()
  f.close()

def classify(query: str):
    completion = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[
            {
                "role": "system",
                "content": f"{prompt}",
            },
            {
                "role": "user",
                "content": f"""{query}""",
            },
        ],
        temperature=0.3,
        max_completion_tokens=500,
    )

    return completion.choices[0].message.content


if __name__ == "__main__":
    print(classify("Technical Guidelines of GHG Deduction Processing and Antibiotic Degradation of Livestock Wastes"))
