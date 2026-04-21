"""
Kernell OS SDK — Rate Limiter & Circuit Breaker Test Suite
══════════════════════════════════════════════════════════
Tests:
  1. Sliding window correctness
  2. Circuit breaker state transitions
  3. Delegation tree budget enforcement
  4. Multi-threaded stress (1, 10, 100 agents)
  5. Burst traffic simulation
  6. Coordinated multi-agent attack simulation
  7. Deep delegation tree (depth 1-4)
  8. Recursion storm prevention
"""
import time
import threading
import sys
import os

# Ensure SDK is importable
sys.path.insert(0, os.path.join(os.path.dirname(__file__)))

from kernell_os_sdk.security.rate_limiter import (
    SlidingWindowLimiter,
    QuotaConfig,
    RateLimitExceeded,
    CircuitBreaker,
    CircuitBreakerConfig,
    CircuitState,
    DelegationBudgetTracker,
    RateLimitGovernor,
)

PASS = 0
FAIL = 0


def check(name: str, condition: bool, detail: str = ""):
    global PASS, FAIL
    if condition:
        PASS += 1
        print(f"  ✅ {name}")
    else:
        FAIL += 1
        print(f"  ❌ {name} — {detail}")


# ═══════════════════════════════════════════════════════════════════
# 1. SLIDING WINDOW RATE LIMITER
# ═══════════════════════════════════════════════════════════════════

def test_sliding_window_basic():
    print("\n🧪 1. Sliding Window — Basic Enforcement")
    limiter = SlidingWindowLimiter()
    limiter.add_quota("test", QuotaConfig(limit=5, window_seconds=10))

    # Should allow 5 calls
    for i in range(5):
        limiter.check_and_record("test", "agent_1")

    # 6th should fail
    blocked = False
    try:
        limiter.check_and_record("test", "agent_1")
    except RateLimitExceeded as e:
        blocked = True
        check("Exception contains dimension", e.dimension == "test")
        check("Exception contains key", e.key == "agent_1")
        check("Exception contains current count", e.current == 5)

    check("6th call blocked", blocked)


def test_sliding_window_isolation():
    print("\n🧪 2. Sliding Window — Key Isolation")
    limiter = SlidingWindowLimiter()
    limiter.add_quota("test", QuotaConfig(limit=3, window_seconds=10))

    for i in range(3):
        limiter.check_and_record("test", "agent_A")

    # Agent B should still work (different key)
    try:
        limiter.check_and_record("test", "agent_B")
        check("Different key not affected", True)
    except RateLimitExceeded:
        check("Different key not affected", False, "agent_B was incorrectly blocked")


def test_sliding_window_expiry():
    print("\n🧪 3. Sliding Window — Expiry (Short Window)")
    limiter = SlidingWindowLimiter()
    limiter.add_quota("test", QuotaConfig(limit=3, window_seconds=0.5))

    for i in range(3):
        limiter.check_and_record("test", "agent_1")

    # Wait for window to expire
    time.sleep(0.6)

    try:
        limiter.check_and_record("test", "agent_1")
        check("Calls allowed after window expiry", True)
    except RateLimitExceeded:
        check("Calls allowed after window expiry", False, "Still blocked after expiry")


def test_sliding_window_usage():
    print("\n🧪 4. Sliding Window — Usage Stats")
    limiter = SlidingWindowLimiter()
    limiter.add_quota("test", QuotaConfig(limit=10, window_seconds=60))

    for i in range(7):
        limiter.check_and_record("test", "agent_1")

    usage = limiter.get_usage("test", "agent_1")
    check("Usage current is 7", usage["current"] == 7)
    check("Usage remaining is 3", usage["remaining"] == 3)
    check("Utilization is 70%", usage["utilization_pct"] == 70.0)


# ═══════════════════════════════════════════════════════════════════
# 2. CIRCUIT BREAKER
# ═══════════════════════════════════════════════════════════════════

def test_circuit_breaker_transitions():
    print("\n🧪 5. Circuit Breaker — State Transitions")
    cb = CircuitBreaker("test_cb", CircuitBreakerConfig(
        failure_threshold=3,
        recovery_timeout=0.5,
        window_seconds=10,
        success_threshold=2,
        half_open_max_calls=2,
    ))

    check("Initial state is CLOSED", cb.state == CircuitState.CLOSED)

    # Record 3 failures → should trip
    cb.record_failure("err1")
    cb.record_failure("err2")
    check("Still CLOSED after 2 failures", cb.state == CircuitState.CLOSED)
    cb.record_failure("err3")
    check("OPEN after 3 failures", cb.state == CircuitState.OPEN)
    check("Requests blocked when OPEN", cb.allow_request() is False)

    # Wait for recovery timeout
    time.sleep(0.6)
    check("Transitions to HALF_OPEN after timeout", cb.state == CircuitState.HALF_OPEN)
    check("Probe request allowed in HALF_OPEN", cb.allow_request() is True)

    # Success in HALF_OPEN
    cb.record_success()
    check("Still HALF_OPEN after 1 success", cb.state == CircuitState.HALF_OPEN)
    cb.record_success()
    check("CLOSED after 2 successes", cb.state == CircuitState.CLOSED)


def test_circuit_breaker_half_open_failure():
    print("\n🧪 6. Circuit Breaker — HALF_OPEN Failure Reopens")
    cb = CircuitBreaker("test_reopen", CircuitBreakerConfig(
        failure_threshold=2,
        recovery_timeout=0.3,
        window_seconds=10,
    ))

    cb.record_failure("err1")
    cb.record_failure("err2")
    check("OPEN after threshold", cb.state == CircuitState.OPEN)

    time.sleep(0.4)
    check("HALF_OPEN after timeout", cb.state == CircuitState.HALF_OPEN)

    # Failure in HALF_OPEN
    cb.record_failure("err3")
    check("Back to OPEN on HALF_OPEN failure", cb.state == CircuitState.OPEN)


def test_circuit_breaker_force():
    print("\n🧪 7. Circuit Breaker — Force Open/Close")
    cb = CircuitBreaker("test_force", CircuitBreakerConfig())
    cb.force_open()
    check("Force OPEN works", cb.state == CircuitState.OPEN)
    cb.force_close()
    check("Force CLOSE works", cb.state == CircuitState.CLOSED)


# ═══════════════════════════════════════════════════════════════════
# 3. DELEGATION BUDGET TRACKER
# ═══════════════════════════════════════════════════════════════════

def test_delegation_budget_basic():
    print("\n🧪 8. Delegation Budget — Basic Tree")
    tracker = DelegationBudgetTracker(
        root_budget=100_000,
        max_depth=3,
        max_children_per_node=3,
        budget_decay_factor=0.5,
    )

    root = tracker.register_root("root_agent")
    check("Root budget is 100k", root.budget_allocated == 100_000)

    child = tracker.spawn_child("root_agent", "child_1")
    check("Child budget is 50k (50% decay)", child.budget_allocated == 50_000)
    check("Child depth is 1", child.depth == 1)

    grandchild = tracker.spawn_child("child_1", "grandchild_1")
    expected = 50_000 * 0.5  # 50% of child's remaining (which is 50k since nothing consumed)
    check(f"Grandchild budget is {expected}", grandchild.budget_allocated == expected)
    check("Grandchild depth is 2", grandchild.depth == 2)


def test_delegation_depth_limit():
    print("\n🧪 9. Delegation Budget — Depth Limit")
    tracker = DelegationBudgetTracker(
        root_budget=1_000_000,
        max_depth=2,
        budget_decay_factor=0.5,
    )
    tracker.register_root("d0")
    tracker.spawn_child("d0", "d1")
    tracker.spawn_child("d1", "d2")

    blocked = False
    try:
        tracker.spawn_child("d2", "d3")
    except RateLimitExceeded as e:
        blocked = True
        check("Blocked dimension is delegation_depth", e.dimension == "delegation_depth")

    check("Depth 3 blocked (max=2)", blocked)


def test_delegation_budget_exhaustion():
    print("\n🧪 10. Delegation Budget — Budget Exhaustion")
    tracker = DelegationBudgetTracker(
        root_budget=1000,
        max_depth=10,
        budget_decay_factor=0.5,
    )
    tracker.register_root("root")

    # Keep spawning until budget runs out
    parent = "root"
    depth = 0
    for i in range(20):
        try:
            child_id = f"child_{i}"
            tracker.spawn_child(parent, child_id)
            parent = child_id
            depth += 1
        except RateLimitExceeded:
            break

    check(f"Budget exhaustion stops spawning (stopped at depth {depth})", depth < 20)
    check("At least depth 2 was reached", depth >= 2)


def test_delegation_consume_budget():
    print("\n🧪 11. Delegation Budget — Consumption Tracking")
    tracker = DelegationBudgetTracker(root_budget=10_000, budget_decay_factor=0.5)
    tracker.register_root("root")
    tracker.spawn_child("root", "worker")

    # Worker has 5000 budget
    ok = tracker.consume_budget("worker", 4000)
    check("4000 consumption allowed", ok)

    remaining = tracker.get_remaining("worker")
    check(f"Remaining is 1000 (got {remaining})", remaining == 1000)

    ok = tracker.consume_budget("worker", 2000)
    check("2000 consumption blocked (exceeds budget)", not ok)


# ═══════════════════════════════════════════════════════════════════
# 4. GOVERNOR INTEGRATION
# ═══════════════════════════════════════════════════════════════════

def test_governor_singleton():
    print("\n🧪 12. Governor — Singleton Pattern")
    RateLimitGovernor.reset_singleton()
    g1 = RateLimitGovernor()
    g2 = RateLimitGovernor()
    check("Singleton returns same instance", g1 is g2)
    RateLimitGovernor.reset_singleton()


def test_governor_agent_calls():
    print("\n🧪 13. Governor — Agent Call Rate Limiting")
    RateLimitGovernor.reset_singleton()
    gov = RateLimitGovernor()

    # Override with smaller limit for testing
    gov.limiter.add_quota("agent_calls", QuotaConfig(limit=5, window_seconds=10))

    for i in range(5):
        gov.check_agent_call("test_agent")

    blocked = False
    try:
        gov.check_agent_call("test_agent")
    except RateLimitExceeded:
        blocked = True

    check("Agent blocked after 5 calls", blocked)
    RateLimitGovernor.reset_singleton()


def test_governor_circuit_breaker_integration():
    print("\n🧪 14. Governor — Circuit Breaker Blocks Agent Calls")
    RateLimitGovernor.reset_singleton()
    gov = RateLimitGovernor()

    # Manually configure breaker with low threshold
    gov.breakers["llm_timeouts"] = CircuitBreaker(
        "llm_timeouts", CircuitBreakerConfig(failure_threshold=3, recovery_timeout=60)
    )

    gov.report_llm_timeout("agent_1")
    gov.report_llm_timeout("agent_2")
    gov.report_llm_timeout("agent_3")

    blocked = False
    try:
        gov.check_agent_call("agent_clean")
    except RateLimitExceeded as e:
        blocked = True
        check("Circuit breaker dimension in error", "circuit:llm_timeouts" in e.dimension)

    check("Clean agent blocked by circuit breaker", blocked)
    RateLimitGovernor.reset_singleton()


# ═══════════════════════════════════════════════════════════════════
# 5. STRESS TESTS
# ═══════════════════════════════════════════════════════════════════

def stress_test_single_agent():
    print("\n🔥 STRESS 1. Single Agent — 1000 Rapid Calls")
    limiter = SlidingWindowLimiter()
    limiter.add_quota("calls", QuotaConfig(limit=100, window_seconds=10))

    allowed = 0
    blocked = 0
    for _ in range(1000):
        try:
            limiter.check_and_record("calls", "stress_agent")
            allowed += 1
        except RateLimitExceeded:
            blocked += 1

    check(f"Exactly 100 allowed (got {allowed})", allowed == 100)
    check(f"Exactly 900 blocked (got {blocked})", blocked == 900)


def stress_test_concurrent_agents():
    print("\n🔥 STRESS 2. 10 Concurrent Agents — Thread Safety")
    limiter = SlidingWindowLimiter()
    limiter.add_quota("calls", QuotaConfig(limit=50, window_seconds=60))

    results = {"allowed": 0, "blocked": 0}
    lock = threading.Lock()

    def agent_work(agent_id: str, num_calls: int):
        local_allowed = 0
        local_blocked = 0
        for _ in range(num_calls):
            try:
                limiter.check_and_record("calls", agent_id)
                local_allowed += 1
            except RateLimitExceeded:
                local_blocked += 1
        with lock:
            results["allowed"] += local_allowed
            results["blocked"] += local_blocked

    threads = []
    for i in range(10):
        t = threading.Thread(target=agent_work, args=(f"agent_{i}", 100))
        threads.append(t)
        t.start()

    for t in threads:
        t.join()

    # Each of 10 agents has a limit of 50 → max 500 allowed total
    check(f"Max 500 total allowed (got {results['allowed']})", results["allowed"] == 500)
    check(f"500 blocked (got {results['blocked']})", results["blocked"] == 500)


def stress_test_100_agents():
    print("\n🔥 STRESS 3. 100 Concurrent Agents — High Contention")
    limiter = SlidingWindowLimiter()
    limiter.add_quota("calls", QuotaConfig(limit=10, window_seconds=60))

    results = {"allowed": 0, "blocked": 0}
    lock = threading.Lock()

    def agent_work(agent_id: str, num_calls: int):
        local_a = 0
        local_b = 0
        for _ in range(num_calls):
            try:
                limiter.check_and_record("calls", agent_id)
                local_a += 1
            except RateLimitExceeded:
                local_b += 1
        with lock:
            results["allowed"] += local_a
            results["blocked"] += local_b

    threads = []
    for i in range(100):
        t = threading.Thread(target=agent_work, args=(f"agent_{i}", 20))
        threads.append(t)
        t.start()

    for t in threads:
        t.join()

    # Each of 100 agents limited to 10 → max 1000 allowed
    check(f"Max 1000 allowed (got {results['allowed']})", results["allowed"] == 1000)
    check(f"1000 blocked (got {results['blocked']})", results["blocked"] == 1000)


def stress_test_burst():
    print("\n🔥 STRESS 4. Burst Traffic — 500 calls in <10ms")
    limiter = SlidingWindowLimiter()
    limiter.add_quota("burst", QuotaConfig(limit=50, window_seconds=1))

    allowed = 0
    blocked = 0
    start = time.time()
    for _ in range(500):
        try:
            limiter.check_and_record("burst", "burst_agent")
            allowed += 1
        except RateLimitExceeded:
            blocked += 1
    elapsed = time.time() - start

    check(f"Burst completed in {elapsed*1000:.1f}ms", elapsed < 0.5)
    check(f"Only 50 allowed in burst (got {allowed})", allowed == 50)
    check(f"450 blocked (got {blocked})", blocked == 450)


def stress_test_delegation_tree_depth():
    print("\n🔥 STRESS 5. Deep Delegation Trees (depth 1-4)")

    for max_d in [1, 2, 3, 4]:
        tracker = DelegationBudgetTracker(
            root_budget=1_000_000,
            max_depth=max_d,
            budget_decay_factor=0.5,
        )
        tracker.register_root("root")

        reached_depth = 0
        parent = "root"
        for d in range(1, max_d + 2):
            try:
                tracker.spawn_child(parent, f"depth_{d}")
                parent = f"depth_{d}"
                reached_depth = d
            except RateLimitExceeded:
                break

        check(
            f"  max_depth={max_d}: reached {reached_depth}, blocked at {reached_depth + 1}",
            reached_depth == max_d
        )


def stress_test_coordinated_attack():
    print("\n🔥 STRESS 6. Coordinated Multi-Agent Attack on Global Quota")
    limiter = SlidingWindowLimiter()
    limiter.add_quota("global", QuotaConfig(limit=100, window_seconds=60))

    results = {"allowed": 0, "blocked": 0}
    lock = threading.Lock()

    def attacker(agent_id: str):
        local_a = 0
        local_b = 0
        for _ in range(50):
            try:
                limiter.check_and_record("global", "__global__")
                local_a += 1
            except RateLimitExceeded:
                local_b += 1
        with lock:
            results["allowed"] += local_a
            results["blocked"] += local_b

    threads = []
    for i in range(20):  # 20 agents × 50 calls = 1000 attempts on shared key
        t = threading.Thread(target=attacker, args=(f"attacker_{i}",))
        threads.append(t)
        t.start()

    for t in threads:
        t.join()

    check(f"Global quota held at 100 (got {results['allowed']})", results["allowed"] == 100)
    check(f"900 coordinated attacks blocked (got {results['blocked']})", results["blocked"] == 900)


def stress_test_recursion_storm():
    print("\n🔥 STRESS 7. Recursion Storm Prevention")
    RateLimitGovernor.reset_singleton()
    gov = RateLimitGovernor()
    gov.limiter.add_quota("agent_calls", QuotaConfig(limit=20, window_seconds=10))

    # Simulate an agent calling itself in a loop
    allowed = 0
    blocked = 0
    for _ in range(500):
        try:
            gov.check_agent_call("recursive_agent")
            allowed += 1
        except RateLimitExceeded:
            blocked += 1

    check(f"Recursion capped at 20 (got {allowed})", allowed == 20)
    check(f"480 recursive calls blocked (got {blocked})", blocked == 480)
    RateLimitGovernor.reset_singleton()


def stress_test_escrow_spam():
    print("\n🔥 STRESS 8. Escrow Spam Prevention")
    RateLimitGovernor.reset_singleton()
    gov = RateLimitGovernor()
    gov.limiter.add_quota("escrow_create", QuotaConfig(limit=5, window_seconds=10))

    allowed = 0
    blocked = 0
    for _ in range(100):
        try:
            gov.check_escrow_create("wallet_spam")
            allowed += 1
        except RateLimitExceeded:
            blocked += 1

    check(f"Escrow capped at 5 (got {allowed})", allowed == 5)
    check(f"95 escrow spam blocked (got {blocked})", blocked == 95)
    RateLimitGovernor.reset_singleton()


def stress_test_skill_abuse():
    print("\n🔥 STRESS 9. Skill Abuse Prevention")
    RateLimitGovernor.reset_singleton()
    gov = RateLimitGovernor()
    gov.limiter.add_quota("skill_calls", QuotaConfig(limit=10, window_seconds=10))

    allowed = 0
    blocked = 0
    for _ in range(200):
        try:
            gov.check_skill_call("agent_evil", "execute_bash")
            allowed += 1
        except RateLimitExceeded:
            blocked += 1

    check(f"Skill abuse capped at 10 (got {allowed})", allowed == 10)
    check(f"190 abusive skill calls blocked (got {blocked})", blocked == 190)
    RateLimitGovernor.reset_singleton()


def stress_test_webhook_flood():
    print("\n🔥 STRESS 10. Webhook Flood Prevention")
    RateLimitGovernor.reset_singleton()
    gov = RateLimitGovernor()
    gov.limiter.add_quota("webhook_dispatch", QuotaConfig(limit=15, window_seconds=10))

    allowed = 0
    blocked = 0
    for _ in range(300):
        try:
            gov.check_webhook("agent_spammer")
            allowed += 1
        except RateLimitExceeded:
            blocked += 1

    check(f"Webhook flood capped at 15 (got {allowed})", allowed == 15)
    check(f"285 webhook floods blocked (got {blocked})", blocked == 285)
    RateLimitGovernor.reset_singleton()


# ═══════════════════════════════════════════════════════════════════
# RUNNER
# ═══════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    print("=" * 70)
    print("  KERNELL OS SDK — RATE LIMITER & CIRCUIT BREAKER TEST SUITE")
    print("=" * 70)

    # Unit tests
    test_sliding_window_basic()
    test_sliding_window_isolation()
    test_sliding_window_expiry()
    test_sliding_window_usage()
    test_circuit_breaker_transitions()
    test_circuit_breaker_half_open_failure()
    test_circuit_breaker_force()
    test_delegation_budget_basic()
    test_delegation_depth_limit()
    test_delegation_budget_exhaustion()
    test_delegation_consume_budget()
    test_governor_singleton()
    test_governor_agent_calls()
    test_governor_circuit_breaker_integration()

    # Stress tests
    stress_test_single_agent()
    stress_test_concurrent_agents()
    stress_test_100_agents()
    stress_test_burst()
    stress_test_delegation_tree_depth()
    stress_test_coordinated_attack()
    stress_test_recursion_storm()
    stress_test_escrow_spam()
    stress_test_skill_abuse()
    stress_test_webhook_flood()

    print("\n" + "=" * 70)
    print(f"  RESULTS: {PASS} passed / {FAIL} failed / {PASS + FAIL} total")
    if FAIL == 0:
        print("  ✅ ALL TESTS PASSED")
    else:
        print("  ❌ SOME TESTS FAILED")
    print("=" * 70)

    sys.exit(1 if FAIL > 0 else 0)
