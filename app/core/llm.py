from __future__ import annotations

from openai import OpenAI
from app.core.settings import settings


class LLMClient:
    def __init__(self) -> None:
        if not settings.OPENAI_API_KEY:
            raise RuntimeError("OPENAI_API_KEY missing. Add it to .env")
        self.client = OpenAI(api_key=settings.OPENAI_API_KEY)

    def generate_answer(self, *, query: str, context: str, model: str | None = None) -> str:
        """
        Uses the OpenAI Responses API to generate an answer grounded in provided context.
        """
        model = model or settings.ANSWER_MODEL

        system_instructions = (
            "You are Recall, a document-grounded assistant.\n"
            "Rules:\n"
            "1) Use ONLY the provided CONTEXT.\n"
            "2) If the CONTEXT is insufficient or irrelevant, say you cannot answer from the documents and stop.\n"
            "3) Every factual claim MUST have a citation like [1]. If you cannot cite it, do not say it.\n"
            "4) Do not invent citations.\n"
        )

        resp = self.client.responses.create(
            model=model,
            input=[
                {"role": "system", "content": system_instructions},
                {
                    "role": "user",
                    "content": (
                        f"USER QUESTION:\n{query}\n\n"
                        f"CONTEXT (numbered):\n{context}\n\n"
                        "Write a clear answer with citations like [1] [2]."
                    ),
                },
            ],
        )

        return (resp.output_text or "").strip()
