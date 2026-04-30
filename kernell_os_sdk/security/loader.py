def load_security_layer(shadow_mode: bool = False, observer=None):
    """
    Dynamically loads the best available security layer.
    Prefers Adaptive Shield (enterprise/private) if available.
    Falls back to BasicSecurityLayer (open-source) otherwise.
    """
    try:
        from kernell_adaptive_shield.cognitive_firewall import CognitiveSecurityLayer
        return CognitiveSecurityLayer(adaptive=True, shadow_mode=shadow_mode, observer=observer), "adaptive"
    except ImportError:
        # For local development before full split, try the internal path
        try:
            from kernell_os_sdk.security.cognitive_firewall import CognitiveSecurityLayer
            return CognitiveSecurityLayer(adaptive=True, shadow_mode=shadow_mode, observer=observer), "adaptive_local"
        except ImportError:
            from .baseline import BasicSecurityLayer
            return BasicSecurityLayer(), "baseline"
