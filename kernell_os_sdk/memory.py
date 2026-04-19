import json
from typing import List, Dict, Any, Optional
from .config import default_config, KernellConfig

try:
    import redis
    HAS_REDIS = True
except ImportError:
    HAS_REDIS = False

class Memory:
    """
    Cortex Shared Memory interface.
    Dramatically reduces token usage by stateful offloading and vector retrieval.
    """
    def __init__(self, agent_id: str, config: Optional[KernellConfig] = None):
        self.agent_id = agent_id
        self.config = config or default_config
        self.redis_client = None
        
        if HAS_REDIS and self.config.redis_url:
            self.redis_client = redis.Redis.from_url(self.config.redis_url)

    def store(self, key: str, value: Any, ttl: int = 86400):
        """Store arbitrary data in short-term memory."""
        if self.redis_client:
            self.redis_client.setex(f"kernell:memory:{self.agent_id}:{key}", ttl, json.dumps(value))

    def fetch(self, key: str) -> Optional[Any]:
        """Fetch data from short-term memory."""
        if self.redis_client:
            data = self.redis_client.get(f"kernell:memory:{self.agent_id}:{key}")
            if data:
                return json.loads(data)
        return None

    def add_episodic(self, event: str, metadata: Dict[str, Any] = None):
        """Add an event to the long-term episodic memory stream."""
        if self.redis_client:
            payload = {"event": event, "metadata": metadata or {}}
            self.redis_client.xadd(f"kernell:stream:{self.agent_id}", {"payload": json.dumps(payload)})

    def summarize_context(self, max_tokens: int = 500) -> str:
        """
        Retrieves a condensed summary of the agent's recent history.
        This is the core feature to avoid passing 50k token chat histories.
        """
        # In a full implementation, this calls the Cortex engine to compress
        # recent events into a dense semantic summary.
        if not self.redis_client:
            return "No recent memory available."
            
        events = self.redis_client.xrevrange(f"kernell:stream:{self.agent_id}", max=b'+', min=b'-', count=10)
        if not events:
            return "No recent memory available."
            
        summary = "Recent events:\n"
        for _, event_data in reversed(events):
            payload = json.loads(event_data[b'payload'])
            summary += f"- {payload['event']}\n"
            
        return summary
