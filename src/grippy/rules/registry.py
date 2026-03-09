# SPDX-License-Identifier: MIT
"""Rule class registry — explicit list of all rule classes."""

from __future__ import annotations

from grippy.rules.base import Rule
from grippy.rules.ci_script_risk import CiScriptRiskRule
from grippy.rules.dangerous_sinks import DangerousSinksRule
from grippy.rules.hardcoded_credentials import HardcodedCredentialsRule
from grippy.rules.insecure_deserialization import InsecureDeserializationRule
from grippy.rules.llm_output_sinks import LlmOutputSinksRule
from grippy.rules.path_traversal import PathTraversalRule
from grippy.rules.secrets_in_diff import SecretsInDiffRule
from grippy.rules.sql_injection import SqlInjectionRule
from grippy.rules.weak_crypto import WeakCryptoRule
from grippy.rules.workflow_permissions import WorkflowPermissionsRule

RULE_REGISTRY: list[type[Rule]] = [
    WorkflowPermissionsRule,
    SecretsInDiffRule,
    DangerousSinksRule,
    PathTraversalRule,
    LlmOutputSinksRule,
    CiScriptRiskRule,
    SqlInjectionRule,
    WeakCryptoRule,
    HardcodedCredentialsRule,
    InsecureDeserializationRule,
]
