from __future__ import annotations

import hashlib
import json
from dataclasses import asdict

from core.intelligence.set_contract import SetPhase
from core.intelligence.transition_contract import TransitionContext

PHASE_CONTEXT_MAPPING_POLICY_VERSION = "phase-transition-context-v1"


def transition_context_for_phase(
    *,
    phase: SetPhase,
    base_context: TransitionContext,
    mapping_policy_version: str = PHASE_CONTEXT_MAPPING_POLICY_VERSION,
) -> TransitionContext:
    """Derive an explicit phase-scoped TransitionContext without hidden presets.

    The phase may narrow hard strategy eligibility through its explicit forbidden
    strategy list. It does not invent tempo limits, harmonic thresholds, weights or
    phrase requirements. Preferred phase strategies remain Set Intelligence soft
    preferences and are intentionally not converted into transition hard gates.
    """
    policy = str(mapping_policy_version).strip()
    if not policy:
        raise ValueError("mapping_policy_version must not be empty")

    forbidden = set(phase.forbidden_transition_strategies)
    allowed = tuple(
        strategy for strategy in base_context.allowed_strategies if strategy not in forbidden
    )
    if not allowed:
        raise ValueError("phase mapping removed every allowed transition strategy")

    material = json.dumps(
        {
            "policy": policy,
            "phase": asdict(phase),
            "base_context": asdict(base_context),
        },
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    )
    fingerprint = hashlib.sha256(material.encode("utf-8")).hexdigest()[:16]

    return TransitionContext(
        context_id=f"{base_context.context_id}:phase:{phase.phase_id}",
        context_version=f"{policy}:{fingerprint}",
        goal=base_context.goal,
        desired_energy_direction=base_context.desired_energy_direction,
        max_tempo_change_percent=base_context.max_tempo_change_percent,
        minimum_harmonic_fit=base_context.minimum_harmonic_fit,
        require_phrase_evidence=base_context.require_phrase_evidence,
        allowed_strategies=allowed,
        weights=base_context.weights,
    )


__all__ = [
    "PHASE_CONTEXT_MAPPING_POLICY_VERSION",
    "transition_context_for_phase",
]
