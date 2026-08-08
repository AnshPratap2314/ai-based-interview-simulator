import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from dotenv import load_dotenv
from google import genai

load_dotenv()

app = FastAPI(title="AI Interview Simulator")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class AnswerRequest(BaseModel):
    question: str
    answer: str


class InterviewEvaluation(BaseModel):
    score: int
    technical_accuracy: int
    relevance: int
    clarity: int
    completeness: int
    strengths: str
    weaknesses: str
    feedback: str
    improved_answer: str


api_key = os.getenv("GEMINI_API_KEY")

if not api_key:
    raise RuntimeError("GEMINI_API_KEY is missing from .env")

client = genai.Client(api_key=api_key)


@app.get("/")
def home():
    return {
        "message": "AI Interview Simulator Backend is running!"
    }


@app.post("/evaluate", response_model=InterviewEvaluation)
def evaluate_answer(data: AnswerRequest):

    prompt = f"""
You are an expert technical interviewer.

Evaluate the candidate's answer.

Question:
{data.question}

Candidate Answer:
{data.answer}

Evaluate:

1. Technical accuracy
2. Relevance
3. Clarity
4. Completeness

Give each category a score from 1 to 10.

Give an overall score from 0 to 100.

Also provide:
- strengths
- weaknesses
- constructive feedback
- an improved answer

Be fair and evaluate the actual quality of the answer.
Do not give a high score simply because keywords are present.
"""

    response = client.models.generate_content(
        model="gemini-3.5-flash-lite",
        contents=prompt,
        config={
            "response_mime_type": "application/json",
            "response_schema": InterviewEvaluation,
        },
    )

    return response.parsed