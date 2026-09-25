import os

from dotenv import load_dotenv
from groq import Groq

load_dotenv()

# Groq's own docs mark this model "preview - intended for evaluation purposes
# only, not for production environments." Used anyway since it demonstrably
# works and is far better than no defense at all - but this choice should be
# re-checked before a real production launch, not assumed permanent.
PROMPT_GUARD_MODEL = "meta-llama/llama-prompt-guard-2-86m"
INJECTION_THRESHOLD = 0.8

_client = Groq(api_key=os.environ.get("GROQ_API_KEY"))


def is_prompt_injection(text: str) -> bool:
    try:
        response = _client.chat.completions.create(
            model=PROMPT_GUARD_MODEL,
            messages=[{"role": "user", "content": text}],
        )
        score = float(response.choices[0].message.content)
    except Exception:
        # Fail OPEN, not closed: if the guard-model call itself errors (Groq
        # hiccup, network issue), let the message through rather than taking
        # the whole chatbot down. Justified specifically because our tool
        # surface is already narrow and every sensitive action (order lookup)
        # is independently, deterministically checked regardless of what the
        # LLM was tricked into doing - this guardrail is defense-in-depth on
        # top of that, not the only thing standing between an attacker and
        # real damage. Revisit this choice if a higher-stakes tool (e.g.
        # "issue refund") is ever added.
        return False

    return score >= INJECTION_THRESHOLD
