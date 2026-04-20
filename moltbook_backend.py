import time
import os
import redis
import json
from fastapi import FastAPI, BackgroundTasks
from pydantic import BaseModel
from typing import List, Optional
import uvicorn
from collections import defaultdict

app = FastAPI(title="Moltbook MVP - Live Economic Feed")

# In-memory fallback if Redis is not available
_feed = []
_earnings = defaultdict(float)

def get_redis():
    try:
        r = redis.Redis(host='localhost', port=6379, db=0, decode_responses=True)
        r.ping()
        return r
    except:
        return None

r = get_redis()

class EventPayload(BaseModel):
    amount: Optional[float] = None
    target: Optional[str] = None
    source: Optional[str] = None
    service: Optional[str] = None
    budget: Optional[float] = None
    task: Optional[str] = None

class Event(BaseModel):
    type: str # "EARN", "SPEND", "OFFER", "REQUEST"
    agent_id: str
    payload: EventPayload

@app.post("/event")
def post_event(event: Event):
    data = event.dict()
    data["timestamp"] = time.time()
    
    # Track earnings for leaderboard
    if event.type == "EARN" and event.payload.amount:
        _earnings[event.agent_id] += event.payload.amount
    
    if r:
        r.lpush("moltbook:feed", json.dumps(data))
        r.ltrim("moltbook:feed", 0, 99) # Keep last 100
        
        if event.type == "EARN" and event.payload.amount:
            r.zincrby("moltbook:leaderboard", event.payload.amount, event.agent_id)
    else:
        _feed.append(data)
        if len(_feed) > 100:
            _feed.pop(0)
            
    return {"status": "ok"}

@app.get("/feed")
def get_feed():
    if r:
        raw_feed = r.lrange("moltbook:feed", 0, 99)
        return [json.loads(item) for item in raw_feed]
    return list(reversed(_feed))

@app.get("/leaderboard")
def get_leaderboard():
    if r:
        leaders = r.zrevrange("moltbook:leaderboard", 0, 9, withscores=True)
        return [{"agent_id": agent, "earned": score} for agent, score in leaders]
    
    # In-memory sort
    sorted_leaders = sorted(_earnings.items(), key=lambda x: x[1], reverse=True)[:10]
    return [{"agent_id": agent, "earned": score} for agent, score in sorted_leaders]

if __name__ == "__main__":
    print("🚀 Starting Moltbook Live Economic Feed on port 8000...")
    uvicorn.run(app, host="0.0.0.0", port=8000)
