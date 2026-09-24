# ShopAgent-OS

Plug-and-play e-commerce AI agent. A LangGraph-based backend answers product,
order, and policy questions using your store's own data, exposed via a FastAPI
`/chat` endpoint and embeddable through a React widget (`packages/react/`).

This project ships no API keys of its own. Every developer running it brings
their **own** credentials for each service they want to use — see below.

## Prerequisites

- Python 3.12+
- Node.js 20+

## 1. Backend setup

```bash
cd backend
python3 -m venv venv
source venv/bin/activate   # on Windows: venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env
```

Edit `backend/.env` and fill in your own keys (see the table below for where
to get each one). Then run:

```bash
uvicorn app.main:app --reload --port 8010
```

Check it's alive: `curl http://127.0.0.1:8010/health` should return
`{"status": "ok"}`. Interactive API docs: `http://127.0.0.1:8010/docs`.

## 2. Widget setup

```bash
cd packages/react
npm install
npm run dev
```

Open the printed `localhost` URL — you'll see a demo page with the ShopAgent
chat widget floating in the bottom-right corner, talking to your local
backend.

## Environment variables

| Variable | Required? | Purpose | Where to get it |
|---|---|---|---|
| `GROQ_API_KEY` | **Required** | Powers the agent's LLM calls | Free key at [console.groq.com/keys](https://console.groq.com/keys) |
| `LANGFUSE_PUBLIC_KEY` | Optional | Enables tracing/observability | Free account at [cloud.langfuse.com](https://cloud.langfuse.com) -> Settings -> API Keys |
| `LANGFUSE_SECRET_KEY` | Optional | Pairs with the public key above | Same as above |
| `LANGFUSE_BASE_URL` | Optional | Which Langfuse region to send traces to | `https://cloud.langfuse.com` (EU) or `https://us.cloud.langfuse.com` (US), depending on which you picked at signup |

The agent works fully without the Langfuse variables — you simply won't get
traces in a dashboard. `GROQ_API_KEY` is the one credential that's actually
required, since the agent can't call an LLM without it.

## Project structure

```
backend/          FastAPI + LangGraph agent (see backend/app/)
packages/react/    Embeddable React chat widget
docs/LEARNING.md   Architecture notes, decisions, and interview-style Q&A
```

See `docs/LEARNING.md` for the reasoning behind major design decisions.
