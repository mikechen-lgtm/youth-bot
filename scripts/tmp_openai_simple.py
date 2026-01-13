import os
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()
load_dotenv('.env.local')
api_key = os.getenv("OPENAI_API_KEY")
if not api_key:
    raise RuntimeError("OPENAI_API_KEY not set. Add it to .env or .env.local.")

client = OpenAI(api_key=api_key)
model = os.getenv('OPENAI_MODEL') or 'gpt-5-mini'
try:
    resp = client.responses.create(
        model=model,
        input=[{'role':'user','content':'hello'}],
    )
    print('ok', resp.output_text[:80])
except Exception as e:
    print('error', type(e).__name__, str(e))
