from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Iterable, Mapping


IDENTIFIER_PATTERN = re.compile(r"^[a-z][a-z0-9_]*$")
ALLOWED_STATUSES = {"ADAPTER_ONLY", "DESIGN_ONLY"}
ALLOWED_DOMAINS = {
    "compatibility",
    "addressing",
    "l2_vlan",
    "services",
    "security",
    "routing",
    "performance",
}


class ModularCollectorRegistryError(ValueError):
    """Raised when the X1 collector design boundary is invalid."""


@dataclass(frozen=True)
class CollectorSpec:
    collector_id: str
    version: int
    domain: str
    feature_ids: tuple[str, ...]
    required_capabilities: tuple[str, ...]
    implementation_status: str
    runtime_authorized: bool = False

    def __post_init__(self) -> None:
        if not IDENTIFIER_PATTERN.fullmatch(self.collector_id):
            raise ModularCollectorRegistryError(
                "collector_id must be a lowercase identifier."
            )
        if (
            isinstance(self.version, bool)
            or not isinstance(self.version, int)
            or self.version < 1
        ):
            raise ModularCollectorRegistryError(
                "collector version must be a positive integer."
            )
        if self.domain not in ALLOWED_DOMAINS:
            raise ModularCollectorRegistryError(
                "collector domain is outside the X1 catalog."
            )
        if not self.feature_ids or len(set(self.feature_ids)) != len(
            self.feature_ids
        ):
            raise ModularCollectorRegistryError(
                "collector feature_ids must be non-empty and unique."
            )
        for value in (*self.feature_ids, *self.required_capabilities):
            if not IDENTIFIER_PATTERN.fullmatch(value):
                raise ModularCollectorRegistryError(
                    "collector features and capabilities must be identifiers."
                )
        if self.implementation_status not in ALLOWED_STATUSES:
            raise ModularCollectorRegistryError(
                "X1 collectors must be adapter-only or design-only."
            )
        if self.runtime_authorized:
            raise ModularCollectorRegistryError(
                "X1 cannot authorize collector runtime."
            )

    @property
    def key(self) -> str:
        return f"{self.collector_id}:v{self.version}"


@dataclass(frozen=True)
class CollectionPlan:
    requested_feature_ids: tuple[str, ...]
    collector_keys: tuple[str, ...]
    capability_gaps: Mapping[str, tuple[str, ...]]
    runtime_authorized: bool = False


class CollectorRegistry:
    """Deterministic metadata registry; it deliberately stores no executor."""

    def __init__(self, catalog_feature_ids: Iterable[str]) -> None:
        self._catalog = frozenset(catalog_feature_ids)
        if not self._catalog:
            raise ModularCollectorRegistryError(
                "The collector registry requires a non-empty feature catalog."
            )
        self._specs: dict[str, CollectorSpec] = {}
        self._owner_by_feature: dict[str, str] = {}

    def register(self, spec: CollectorSpec) -> None:
        if spec.key in self._specs:
            raise ModularCollectorRegistryError(
                f"Duplicate collector key: {spec.key}"
            )
        unknown = set(spec.feature_ids) - self._catalog
        if unknown:
            raise ModularCollectorRegistryError(
                "Collector references unknown catalog features: "
                + ", ".join(sorted(unknown))
            )
        overlap = set(spec.feature_ids) & set(self._owner_by_feature)
        if overlap:
            raise ModularCollectorRegistryError(
                "A feature cannot have multiple X1 collector owners: "
                + ", ".join(sorted(overlap))
            )
        self._specs[spec.key] = spec
        for feature_id in spec.feature_ids:
            self._owner_by_feature[feature_id] = spec.key

    @property
    def specs(self) -> tuple[CollectorSpec, ...]:
        return tuple(self._specs[key] for key in sorted(self._specs))

    @property
    def uncovered_features(self) -> tuple[str, ...]:
        return tuple(sorted(self._catalog - set(self._owner_by_feature)))

    def plan(
        self,
        requested_feature_ids: Iterable[str],
        available_capabilities: Iterable[str],
    ) -> CollectionPlan:
        requested = tuple(dict.fromkeys(requested_feature_ids))
        unknown = set(requested) - self._catalog
        if unknown:
            raise ModularCollectorRegistryError(
                "Collection plan requested unknown features: "
                + ", ".join(sorted(unknown))
            )
        available = frozenset(available_capabilities)
        selected_keys = sorted(
            {self._owner_by_feature[name] for name in requested}
        )
        gaps: dict[str, tuple[str, ...]] = {}
        runnable: list[str] = []
        for key in selected_keys:
            spec = self._specs[key]
            missing = tuple(
                sorted(set(spec.required_capabilities) - available)
            )
            if missing:
                gaps[key] = missing
            else:
                runnable.append(key)
        return CollectionPlan(
            requested_feature_ids=requested,
            collector_keys=tuple(runnable),
            capability_gaps=gaps,
            runtime_authorized=False,
        )


BASELINE_FEATURES = (
    "source_expected_gateway_reachable",
    "source_default_gateway_matches_expected",
    "destination_reachable",
    "route_to_destination_exists_on_observer",
    "route_next_hop_matches_expected",
    "route_next_hop_reachable_from_observer",
    "expected_next_hop_reachable_from_observer",
    "observer_egress_interface_oper_up",
    "destination_reachable_from_transit",
    "flow_blocked_by_policy",
)

COLLECTOR_BLUEPRINTS = (
    CollectorSpec(
        collector_id="evidence_v3_compatibility_adapter",
        version=1,
        domain="compatibility",
        feature_ids=BASELINE_FEATURES,
        required_capabilities=(),
        implementation_status="ADAPTER_ONLY",
    ),
    CollectorSpec(
        collector_id="addressing_state_collector",
        version=1,
        domain="addressing",
        feature_ids=(
            "source_address_matches_expected",
            "source_prefix_matches_expected",
            "source_default_route_present",
            "duplicate_address_detected",
            "duplicate_address_mac_churn_detected",
        ),
        required_capabilities=("ipv4_addressing",),
        implementation_status="DESIGN_ONLY",
    ),
    CollectorSpec(
        collector_id="l2_vlan_state_collector",
        version=1,
        domain="l2_vlan",
        feature_ids=(
            "access_vlan_matches_expected",
            "vlan_exists_on_target",
            "vlan_allowed_on_trunk",
            "native_vlan_matches_peer",
            "fdb_location_matches_expected",
        ),
        required_capabilities=("l2_vlan",),
        implementation_status="DESIGN_ONLY",
    ),
    CollectorSpec(
        collector_id="service_state_collector",
        version=1,
        domain="services",
        feature_ids=(
            "dhcp_server_reachable",
            "dhcp_lease_obtained",
            "dhcp_lease_matches_expected_scope",
            "dns_server_reachable",
            "dns_query_succeeds",
            "dns_answer_matches_expected",
            "service_process_running",
            "service_port_reachable",
        ),
        required_capabilities=("service_observation",),
        implementation_status="DESIGN_ONLY",
    ),
    CollectorSpec(
        collector_id="service_policy_state_collector",
        version=1,
        domain="security",
        feature_ids=("service_flow_blocked_by_policy",),
        required_capabilities=("service_policy",),
        implementation_status="DESIGN_ONLY",
    ),
    CollectorSpec(
        collector_id="ospf_state_collector",
        version=1,
        domain="routing",
        feature_ids=(
            "ospf_adjacency_full",
            "ospf_route_advertised",
            "ospf_route_installed",
            "route_filter_allows_prefix",
        ),
        required_capabilities=("ospf",),
        implementation_status="DESIGN_ONLY",
    ),
    CollectorSpec(
        collector_id="performance_state_collector",
        version=1,
        domain="performance",
        feature_ids=(
            "packet_loss_ratio",
            "round_trip_latency_ms_p95",
            "throughput_mbps",
            "interface_utilization_ratio",
            "queue_drop_count",
            "rate_limit_detected",
        ),
        required_capabilities=("performance_measurement",),
        implementation_status="DESIGN_ONLY",
    ),
)


def build_x1_registry(catalog_feature_ids: Iterable[str]) -> CollectorRegistry:
    registry = CollectorRegistry(catalog_feature_ids)
    for spec in COLLECTOR_BLUEPRINTS:
        registry.register(spec)
    if registry.uncovered_features:
        raise ModularCollectorRegistryError(
            "X1 collector blueprints do not cover the feature catalog: "
            + ", ".join(registry.uncovered_features)
        )
    return registry
