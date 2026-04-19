import os
from dotenv import load_dotenv
from kernell_os_sdk import Agent, AgentPermissions
from kernell_os_sdk.llm import LLMRouter, OllamaProvider, AnthropicProvider
from kernell_os_sdk.cluster import ClusterDiscovery

load_dotenv()

def main():
    print("🚀 Booting Kernell OS Swarm: my_first_swarm")
    
    local = OllamaProvider(model="gemma-4:9b-q4_K_M")
    cloud = AnthropicProvider(model="claude-3-5-sonnet-20241022")
    router = LLMRouter(local_provider=local, cloud_provider=cloud, cloud_threshold="hard")
    
    director = Agent(
        name="Swarm Director",
        engine=router,
        permissions=AgentPermissions(network_access=True)
    )
    
    director.enable_delegation(max_workers=5, worker_engine=local)

    discovery = ClusterDiscovery(redis_url=os.getenv("REDIS_URL"), cluster_name=os.getenv("KERNELL_CLUSTER_NAME"))
    discovery.join(agent_name="director_node", hardware_profile={"model": "gemma-4:9b-q4_K_M"})

    print("✅ Swarm is online. Run 'kernell gui' to open the Command Center.")
    
if __name__ == "__main__":
    main()
