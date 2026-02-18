from fastapi import FastAPI
from pydantic import BaseModel
import uvicorn

app = FastAPI()

class MarketRequest(BaseModel):
    item: str
    max_budget: float

@app.post("/test/requests")
def post_request(req: MarketRequest, agent_id: str):
    return {"status": "OK", "agent_id": agent_id, "item": req.item}

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8001)
