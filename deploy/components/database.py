# deploy/components/database.py
"""Cloud SQL (Postgres, private IP): random password, instance, database, user, and the
two connection URLs the app uses (unix socket for Cloud Run, private IP for GKE pods)."""
from __future__ import annotations

import pulumi
import pulumi_gcp as gcp
import pulumi_random as random

from _iam import child_opts
from components.network import Network
from config import InfraConfig


class Database(pulumi.ComponentResource):
    def __init__(self, cfg: InfraConfig, network: Network, opts=None):
        super().__init__("collateralai:infra:Database", "database", None, opts)

        self.password = random.RandomPassword(
            f"{cfg.name}-db-password",
            length=cfg.db_password_length,
            special=False,
            opts=child_opts(self),
        )
        self.instance = gcp.sql.DatabaseInstance(
            f"{cfg.name}-sql",
            database_version=cfg.sql_db_version,
            region=cfg.region,
            deletion_protection=cfg.sql_deletion_protection,
            settings=gcp.sql.DatabaseInstanceSettingsArgs(
                edition=cfg.sql_edition,
                tier=cfg.sql_instance_tier,
                availability_type=cfg.sql_availability_type,
                disk_type="PD_SSD",
                disk_size=20,
                disk_autoresize=True,
                ip_configuration=gcp.sql.DatabaseInstanceSettingsIpConfigurationArgs(
                    ipv4_enabled=False,
                    private_network=network.network.id,
                ),
                backup_configuration=gcp.sql.DatabaseInstanceSettingsBackupConfigurationArgs(
                    enabled=True,
                    point_in_time_recovery_enabled=True,
                ),
            ),
            opts=child_opts(self, depends_on=[network.private_vpc_connection]),
        )
        gcp.sql.Database(
            f"{cfg.name}-database",
            instance=self.instance.name,
            name=cfg.db_name,
            opts=child_opts(self),
        )
        gcp.sql.User(
            f"{cfg.name}-db-user",
            instance=self.instance.name,
            name=cfg.db_user,
            password=self.password.result,
            opts=child_opts(self),
        )

        self.socket_url = pulumi.Output.all(
            self.password.result, self.instance.connection_name
        ).apply(lambda a: f"postgres://{cfg.db_user}:{a[0]}@/{cfg.db_name}?host=/cloudsql/{a[1]}")
        self.private_url = pulumi.Output.all(
            self.password.result, self.instance.private_ip_address
        ).apply(lambda a: f"postgres://{cfg.db_user}:{a[0]}@{a[1]}:5432/{cfg.db_name}")
        self.register_outputs({})
