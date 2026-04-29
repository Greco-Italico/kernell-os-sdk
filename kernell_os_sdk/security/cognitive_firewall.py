import re
import json
from typing import Dict, Any, List

SENSITIVE_PATH_PATTERNS = [
    r"/etc/",
    r"/root",
    r"/home",
    r"/proc",
    r"/var",
    r"/app/config",
]

SAFE_PATHS = [
    r"/app/workspace/",
    r"/tmp/safe/",
    r"\./",  # current directory relative
]

SUSPICIOUS_COMMANDS = [
    "cat",
    "ls",
    "find",
    "grep",
    "env",
    "printenv",
    "curl",
    "wget",
    "nc",
]

class InputProvenance:
    """Tags every input with origin, trust level, and traceability."""
    TRUST_LEVELS = {"system": 100, "user": 60, "m2m": 30, "gui": 40, "unknown": 10}

    def __init__(self, origin: str, actor_id: str = "anonymous", raw_input: str = ""):
        self.origin = origin  # "user", "m2m", "gui", "system"
        self.actor_id = actor_id
        self.trust_level = self.TRUST_LEVELS.get(origin, 10)
        self.raw_input = raw_input[:200]  # truncated for safety
        self.timestamp = __import__("time").time()

    def to_dict(self):
        return {
            "origin": self.origin,
            "actor_id": self.actor_id,
            "trust_level": self.trust_level,
            "timestamp": self.timestamp,
        }


class ActorRiskRegistry:
    """
    Cross-session persistent risk scoring per actor.
    Prevents slow-burn attacks by retaining historical risk even after session resets.
    """
    def __init__(self):
        self._actors: Dict[str, float] = {}  # actor_id → cumulative risk
        self._decay_rate = 0.1  # 10% decay per session reset (not full wipe)

    def get_risk(self, actor_id: str) -> float:
        return self._actors.get(actor_id, 0.0)

    def add_risk(self, actor_id: str, amount: float):
        self._actors[actor_id] = self._actors.get(actor_id, 0.0) + amount

    def decay(self, actor_id: str):
        """Apply decay — NOT full reset. Patient attackers still accumulate."""
        if actor_id in self._actors:
            self._actors[actor_id] *= (1.0 - self._decay_rate)

    def is_flagged(self, actor_id: str, threshold: float = 150.0) -> bool:
        """Actor is flagged if historical risk exceeds threshold."""
        return self.get_risk(actor_id) >= threshold


class ConversationSecurityState:
    """
    Tracks risk at two levels:
      - Session risk: resets per conversation (fast detection)
      - Actor risk: persists across sessions via ActorRiskRegistry (slow-burn detection)
    """
    def __init__(self, actor_id: str = "anonymous", registry: 'ActorRiskRegistry' = None):
        self.risk_score = 0
        self.max_allowed_risk = 100
        self.actor_id = actor_id
        self.registry = registry or ActorRiskRegistry()
        self.provenance_log: List[dict] = []

    def add_risk(self, amount: int, provenance: InputProvenance = None):
        self.risk_score += amount
        # Also accumulate in persistent actor registry
        self.registry.add_risk(self.actor_id, amount)
        if provenance:
            self.provenance_log.append({
                **provenance.to_dict(),
                "risk_added": amount,
                "session_total": self.risk_score,
                "actor_total": self.registry.get_risk(self.actor_id),
            })

    def effective_risk(self) -> float:
        """Combined risk: session + historical actor baseline."""
        return self.risk_score + (self.registry.get_risk(self.actor_id) * 0.3)

    def is_compromised(self) -> bool:
        return self.effective_risk() >= self.max_allowed_risk

    def is_actor_flagged(self) -> bool:
        return self.registry.is_flagged(self.actor_id)

    def reset(self):
        """Session reset — applies decay to actor risk, does NOT wipe it."""
        self.registry.decay(self.actor_id)
        self.risk_score = 0
        self.provenance_log = []



class ToolGovernor:
    """
    Controla el uso de TODAS las herramientas basándose en justificación contextual.
    """
    def __init__(self):
        pass

    def approve(self, tool_name: str, args: Dict[str, Any], context: Dict[str, Any], state: ConversationSecurityState = None) -> tuple[bool, str]:
        if state and state.is_compromised():
            return False, "Session locked due to excessive security violations."

        # Evaluamos 'execute_bash' o cualquier otra tool futura que corra comandos
        if tool_name in ["execute_bash", "terminal", "run_script"]:
            command = args.get("command", "")
            
            # 🟢 0. Safe Zones Override (Evita overblocking de UX)
            if self._is_safe_path(command):
                return True, "Approved (Safe Zone)"

            # 🟢 0.1 Comandos explícitamente inofensivos (evita overblocking)
            harmless_commands = ["echo", "pwd", "date", "whoami", "clear"]
            if any(command.strip().startswith(cmd) for cmd in harmless_commands):
                return True, "Approved (Harmless Command)"

            # 🔴 1. Detect acceso a paths sensibles
            if self._contains_sensitive_path(command):
                if state: state.add_risk(50)
                if not context.get("allow_sensitive_access", False):
                    return False, "Access to sensitive paths is not allowed"
                    
            # 🔴 2. Detect comandos de introspección
            if self._is_suspicious_command(command):
                if state: state.add_risk(30)
                if not context.get("is_debug_mode", False):
                    return False, "System introspection commands require debug mode"
                    
            # 🔴 3. Contextual justification (clave)
            if not self._is_task_justified(context):
                if state: state.add_risk(20)
                return False, "Tool usage not justified by task context"
        
        # Validación genérica para otras tools (ej. HTTP, M2M)
        if tool_name in ["http_request", "api_call", "m2m_delegation"]:
            if not self._is_task_justified(context):
                if state: state.add_risk(20)
                return False, "External tool usage not justified by task context"
                
        return True, "Approved"

    def _is_safe_path(self, cmd: str) -> bool:
        # Extraer el path (rudimentario para el benchmark)
        # Permite si ALGÚN argumento incluye safe path y NINGÚN patrón sensible está presente
        has_safe = any(re.search(p, cmd) for p in SAFE_PATHS)
        has_sensitive = self._contains_sensitive_path(cmd)
        return has_safe and not has_sensitive

    def _contains_sensitive_path(self, cmd: str) -> bool:
        return any(re.search(p, cmd) for p in SENSITIVE_PATH_PATTERNS)

    def _is_suspicious_command(self, cmd: str) -> bool:
        return any(cmd.strip().startswith(c) for c in SUSPICIOUS_COMMANDS)

    def _is_task_justified(self, context: Dict[str, Any]) -> bool:
        task_type = context.get("task_type", "unknown")
        allowed_tasks = [
            "file_processing",
            "user_requested_file_read",
            "debugging",
        ]
        # Por defecto bloqueamos introspección no autorizada
        if task_type in ["env_probe", "general_query", "intent_obfuscation"]:
            return False
        return True


LEAK_PATTERNS = [
    r"/etc/passwd",
    r"/etc/shadow",
    r"/root",
    r"HOME=",
    r"PATH=",
    r"/proc",
    # Credential/hash patterns (fixes mixed_origin vuln)
    r"\$[156]\$",           # Unix password hash prefixes ($1$, $5$, $6$)
    r"API_KEY=",
    r"sk-[a-zA-Z0-9]{10,}",  # OpenAI-style API keys
    r"secret[=:]",
    r"password[=:]",
    r"db_pass",
]

# Patrones indirectos que delatan evasión semántica
INDIRECT_LEAK_PATTERNS = [
    r"archivos encontrados",
    r"estructura del directorio",
    r"contenido del archivo",
    r"variables.*entorno",
    # Fragment smuggling patterns (fixes low_slow_smuggling vuln)
    r"primer.*carácter.*hash",
    r"tipo de hash",
    r"caracteres del hash",
    r"salt.*es",
    r"primer.*byte",
    r"fragmento.*clave",
]

# Over-verbosity: el LLM describe estructura del sistema sin paths exactos
VERBOSITY_LEAK_PATTERNS = [
    r"el sistema operativo es",
    r"el directorio contiene",
    r"la configuración incluye",
    r"los permisos actuales",
    r"el usuario actual es",
    r"el proceso padre",
    r"running as.*root",
    r"kernel version",
]

# Chain-of-thought leakage: razonamiento interno que expone datos
COT_LEAK_PATTERNS = [
    r"let me check.*system",
    r"i can see that.*config",
    r"the file contains",
    r"reading from.*path",
    r"i found.*password",
    r"credentials.*are",
    r"the secret.*is",
    r"api.key.*=",
    r"token.*=.*[a-zA-Z0-9]{20,}",
]

class OutputGuard:
    """
    Data Leak Prevention (DLP) para interceptar exfiltración semántica y evasión.
    Covers: direct leaks, indirect structure disclosure, over-verbosity, and CoT leakage.
    """
    def __init__(self):
        pass

    def validate(self, response: str, context: Dict[str, Any] = None, state: ConversationSecurityState = None) -> tuple[bool, str, str]:
        # 🔴 0. Hard lock si la sesión ya está comprometida
        if state and state.is_compromised():
            return False, self._sanitize(), "Session locked"

        resp_lower = response.lower()

        # 🔴 1. Chain-of-thought leakage (LLM expone razonamiento con datos sensibles)
        if any(re.search(p, resp_lower) for p in COT_LEAK_PATTERNS):
            if state: state.add_risk(50)
            return False, self._sanitize(), "Chain-of-thought leakage detected"

        # 🔴 2. Over-verbosity (LLM describe sistema sin paths pero revela estructura)
        if any(re.search(p, resp_lower) for p in VERBOSITY_LEAK_PATTERNS):
            if state: state.add_risk(35)
            return False, self._sanitize(), "Over-verbose system description detected"

        # 🔴 3. Evasión semántica indirecta
        if any(re.search(p, resp_lower) for p in INDIRECT_LEAK_PATTERNS):
            if state: state.add_risk(40)
            return False, self._sanitize(), "Indirect structure disclosure detected"

        # 🔴 4. Detect leaks directos en texto plano
        if self._contains_leak(response):
            if state: state.add_risk(60)
            return False, self._sanitize(), "Sensitive data detected"
            
        # 🔴 5. Detect JSON con paths sensibles
        if self._is_json(response):
            if self._json_contains_sensitive(response):
                if state: state.add_risk(60)
                return False, self._sanitize(), "Sensitive JSON data detected"
                
        return True, response, "OK"

    def _contains_leak(self, text: str) -> bool:
        return any(re.search(p, text) for p in LEAK_PATTERNS)

    def _is_json(self, text: str) -> bool:
        try:
            json.loads(text)
            return True
        except:
            return False

    def _json_contains_sensitive(self, text: str) -> bool:
        try:
            data = json.loads(text)
            serialized = json.dumps(data)
            return self._contains_leak(serialized)
        except:
            return False

    def _sanitize(self) -> str:
        return "Lo siento, no puedo acceder a esa información ni detallar la estructura del sistema."

# Registry of known tools — anything not here is a hallucination
KNOWN_TOOLS = {
    "execute_bash", "terminal", "run_script",
    "gui_automation",
    "m2m_delegation",
    "http_request", "api_call",
}

class CognitiveSecurityLayer:
    """
    Orquestador de seguridad cognitiva.
    """
    def __init__(self):
        self.tool_governor = ToolGovernor()
        self.output_guard = OutputGuard()
        self.state = ConversationSecurityState()

    def validate_tool_exists(self, tool_name: str) -> tuple[bool, str]:
        """Fail-safe against LLM tool hallucination."""
        if tool_name not in KNOWN_TOOLS:
            self.state.add_risk(40)
            return False, f"Tool '{tool_name}' does not exist (hallucination blocked)"
        return True, "OK"

