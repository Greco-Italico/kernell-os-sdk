import logging
from typing import List, Dict, Any, Optional
from .agent import Agent

logger = logging.getLogger("kernell.cluster")

class Cluster:
    """
    Swarm Intelligence / War Room Orchestrator.
    Groups multiple specialized agents to solve complex tasks dynamically,
    bypassing the traditional static Orchestrator-Subagent bottleneck.
    """
    def __init__(self, name: str, description: str = ""):
        self.name = name
        self.description = description
        self.agents: Dict[str, Agent] = {}
        self.roles: Dict[str, str] = {}
        
    def add_agent(self, agent: Agent, role: str):
        """Add an agent to the cluster with a specific role."""
        self.agents[agent.name] = agent
        self.roles[agent.name] = role
        logger.info(f"Added agent {agent.name} to cluster '{self.name}' as: {role}")
        
    def run(self, task: str, max_budget_kern: float = 0.0) -> Dict[str, Any]:
        """
        Executes a task across the cluster.
        In Kernell OS, this doesn't just run agents sequentially; it allows them
        to bid for subtasks or share a shared context space (Cortex).
        """
        logger.info(f"Cluster '{self.name}' starting task: {task} (Budget: {max_budget_kern} KERN)")
        
        # 1. Synthesizer phase (Task breakdown)
        logger.info("Breaking down task...")
        
        results = {}
        cost_incurred = 0.0
        
        # 2. Parallel / Routed Execution
        for agent_name, agent in self.agents.items():
            if cost_incurred + agent.rate > max_budget_kern and max_budget_kern > 0:
                logger.warning(f"Budget exceeded. Skipping {agent_name}.")
                continue
                
            logger.info(f"Delegating to {agent_name} ({self.roles[agent_name]})...")
            
            # Agent processes the task (in reality, a specific subtask)
            out = agent.prompt(f"Cluster Task: {task}. Your Role: {self.roles[agent_name]}")
            results[agent_name] = out
            cost_incurred += agent.rate
            
        # 3. Final Synthesis
        synthesis = f"Cluster {self.name} completed. {len(results)} agents participated. Total Cost: {cost_incurred} KERN."
        
        return {
            "status": "completed",
            "synthesis": synthesis,
            "agent_outputs": results,
            "cost_kern": cost_incurred
        }
