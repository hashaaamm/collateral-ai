# deploy/components/network.py
"""VPC, subnet (with GKE secondary ranges), Serverless VPC connector, and private
services access (peering range + connection) for Cloud SQL private IP."""
from __future__ import annotations

import pulumi
import pulumi_gcp as gcp

from _iam import child_opts
from components.apis import ProjectApis
from config import InfraConfig


class Network(pulumi.ComponentResource):
    def __init__(self, cfg: InfraConfig, apis: ProjectApis, opts=None):
        super().__init__("collateralai:infra:Network", "network", None, opts)

        self.network = gcp.compute.Network(
            f"{cfg.name}-network",
            auto_create_subnetworks=False,
            opts=child_opts(self, depends_on=[apis.apis["compute"]]),
        )
        self.subnet = gcp.compute.Subnetwork(
            f"{cfg.name}-subnet",
            network=self.network.id,
            ip_cidr_range=cfg.subnet_ip,
            region=cfg.region,
            # VPC-native secondary ranges GKE Autopilot allocates pods/services from.
            secondary_ip_ranges=[
                gcp.compute.SubnetworkSecondaryIpRangeArgs(
                    range_name="gke-pods", ip_cidr_range=cfg.gke_pod_cidr),
                gcp.compute.SubnetworkSecondaryIpRangeArgs(
                    range_name="gke-services", ip_cidr_range=cfg.gke_svc_cidr),
            ],
            opts=child_opts(self),
        )
        self.connector = gcp.vpcaccess.Connector(
            f"{cfg.name}-connector",
            # Deterministic name so CI (cd.yml / jobs.yml) can reference it.
            name=f"{cfg.name}-connector",
            region=cfg.region,
            network=self.network.name,
            ip_cidr_range=cfg.vpc_connector_cidr,
            min_throughput=cfg.vpc_connector_min_throughput,
            max_throughput=cfg.vpc_connector_max_throughput,
            opts=child_opts(self, depends_on=[apis.apis["vpcaccess"]]),
        )
        self.private_ip = gcp.compute.GlobalAddress(
            f"{cfg.name}-private-ip",
            purpose="VPC_PEERING",
            address_type="INTERNAL",
            prefix_length=16,
            network=self.network.id,
            opts=child_opts(self),
        )
        self.private_vpc_connection = gcp.servicenetworking.Connection(
            f"{cfg.slug}-private-vpc",
            network=self.network.id,
            service="servicenetworking.googleapis.com",
            reserved_peering_ranges=[self.private_ip.name],
            opts=child_opts(self, depends_on=[apis.apis["servicenetworking"]]),
        )
        self.register_outputs({})
