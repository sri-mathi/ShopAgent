from deepeval.models.base_model import DeepEvalBaseLLM
from langchain_groq import ChatGroq


class GroqJudge(DeepEvalBaseLLM):
    """Uses a larger Groq-hosted model as the LLM-as-judge, reusing the same
    GROQ_API_KEY the agent itself uses - no separate OpenAI key required."""

    def __init__(self, model_name: str = "openai/gpt-oss-120b"):
        self.model_name = model_name
        self.model = ChatGroq(model=model_name, temperature=0)

    def load_model(self):
        return self.model

    def generate(self, prompt: str) -> str:
        return self.load_model().invoke(prompt).content

    async def a_generate(self, prompt: str) -> str:
        response = await self.load_model().ainvoke(prompt)
        return response.content

    def get_model_name(self) -> str:
        return self.model_name
