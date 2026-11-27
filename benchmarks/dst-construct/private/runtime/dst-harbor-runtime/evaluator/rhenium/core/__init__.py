"""Game-independent benchmark primitives used by Rhenium."""

from .catalog import BenchmarkCatalog, BenchmarkTask, LocalizedList, LocalizedText
from .evaluation import EvaluationReport, normalize_evaluation
from .evaluation_host import (
    DisposableEvaluationHost,
    EvaluationHostCapability,
    EvaluationHostDescriptor,
    EvaluationSecurityMode,
    HostBaseVerification,
    HostDestructionProof,
    HostEvaluationRequest,
    HostExecution,
    HostInputProof,
    HostInstance,
    HostSecurityPolicy,
    evaluate_on_disposable_host,
    fail_closed_untrusted_evaluation,
    hash_untrusted_submission,
    sanitize_disposable_result,
)
from .identity import PackKey, TaskKey
from .plugin import (
    BenchmarkContext,
    BenchmarkPlugin,
    EvaluationBackend,
    EvaluationProfile,
    PluginDescriptor,
)

__all__ = [
    "BenchmarkCatalog",
    "BenchmarkContext",
    "BenchmarkPlugin",
    "BenchmarkTask",
    "EvaluationBackend",
    "EvaluationHostCapability",
    "EvaluationHostDescriptor",
    "EvaluationReport",
    "EvaluationProfile",
    "EvaluationSecurityMode",
    "DisposableEvaluationHost",
    "HostBaseVerification",
    "HostDestructionProof",
    "HostEvaluationRequest",
    "HostExecution",
    "HostInputProof",
    "HostInstance",
    "HostSecurityPolicy",
    "LocalizedList",
    "LocalizedText",
    "PackKey",
    "PluginDescriptor",
    "TaskKey",
    "evaluate_on_disposable_host",
    "fail_closed_untrusted_evaluation",
    "hash_untrusted_submission",
    "sanitize_disposable_result",
    "normalize_evaluation",
]
