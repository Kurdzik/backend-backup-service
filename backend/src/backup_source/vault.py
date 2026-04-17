import json
import os
import tarfile
import tempfile
from datetime import datetime
from typing import Optional
from urllib.parse import urlparse

import hvac

from src.base import BaseBackupManager, Credentials


class VaultBackupManager(BaseBackupManager):
    def __init__(self, credentials: Credentials) -> None:
        super().__init__(credentials)
        self._mount_point = self._parse_mount_point()
        self.client = self._initialize_client()

    def _parse_mount_point(self) -> str:
        """Extract KV v2 mount point from URL path, defaulting to 'secret'.

        Allows callers to specify a non-default mount by including a path in
        the URL, e.g. https://vault.example.com/kv  ->  mount_point='kv'.
        """
        parsed = urlparse(self.credentials.url)
        path = parsed.path.strip("/")
        return path if path else "secret"

    def _vault_base_url(self) -> str:
        """Return the Vault server URL without any path component."""
        parsed = urlparse(self.credentials.url)
        return f"{parsed.scheme}://{parsed.netloc}"

    def _initialize_client(self) -> hvac.Client:
        client = hvac.Client(url=self._vault_base_url())

        if self.credentials.api_key:
            client.token = self.credentials.api_key
        elif self.credentials.login and self.credentials.password:
            client.auth.userpass.login(
                username=self.credentials.login, password=self.credentials.password
            )
        else:
            raise ValueError(
                "Either api_key or login/password credentials are required"
            )

        if not client.is_authenticated():
            raise RuntimeError("Failed to authenticate with Vault")

        return client

    def _list_secrets_recursive(
        self, path: str, secrets: dict, warnings: list
    ) -> None:
        """Recursively collect all secrets under *path* from the KV v2 mount."""
        try:
            list_response = self.client.secrets.kv.v2.list_secrets(
                path=path, mount_point=self._mount_point
            )
            keys = list_response.get("data", {}).get("keys", [])
        except Exception as exc:
            warnings.append(f"Could not list path '{path}': {exc}")
            return

        for key in keys:
            full_path = f"{path}/{key}".lstrip("/") if path else key

            if key.endswith("/"):
                self._list_secrets_recursive(
                    full_path.rstrip("/"), secrets, warnings
                )
            else:
                try:
                    secret = self.client.secrets.kv.v2.read_secret_version(
                        path=full_path, mount_point=self._mount_point
                    )
                    secrets[full_path] = secret["data"]["data"]
                except Exception as exc:
                    warnings.append(f"Could not read secret '{full_path}': {exc}")

    def create_backup(
        self, tenant_id: str, backup_source_id: int, schedule_id: Optional[int] = None
    ) -> str:
        temp_dir = tempfile.mkdtemp()

        try:
            warnings: list[str] = []
            backup_data: dict = {
                "timestamp": datetime.now().isoformat(),
                "mount_point": self._mount_point,
                "auth_methods": {},
                "secrets": {},
                "policies": {},
                "warnings": warnings,
            }

            self._list_secrets_recursive("", backup_data["secrets"], warnings)

            try:
                auth_methods = self.client.sys.list_auth_methods()
                backup_data["auth_methods"] = auth_methods.get("data", {})
            except Exception as exc:
                warnings.append(f"Could not back up auth methods: {exc}")

            try:
                policies = self.client.sys.list_policies()
                for policy_name in policies.get("data", {}).get("policies", []):
                    if policy_name in ("root", "default"):
                        continue
                    try:
                        policy_content = self.client.sys.read_policy(name=policy_name)
                        backup_data["policies"][policy_name] = (
                            policy_content.get("data", {}).get("rules", "")
                        )
                    except Exception as exc:
                        warnings.append(
                            f"Could not back up policy '{policy_name}': {exc}"
                        )
            except Exception as exc:
                warnings.append(f"Could not list policies: {exc}")

            if warnings:
                print(
                    f"[VaultBackup] {len(warnings)} item(s) skipped during backup:"
                )
                for w in warnings:
                    print(f"  - {w}")

            backup_file = os.path.join(temp_dir, "vault_backup.json")
            with open(backup_file, "w") as f:
                json.dump(backup_data, f, indent=2, default=str)

            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_path = f"vault_backup_usr={tenant_id}_sch={schedule_id}_src={backup_source_id}_created_at={timestamp}.tar.gz"

            with tarfile.open(backup_path, "w:gz") as tar:
                tar.add(temp_dir, arcname="vault_backup")

            return backup_path

        finally:
            for file in os.listdir(temp_dir):
                os.remove(os.path.join(temp_dir, file))
            os.rmdir(temp_dir)

    def restore_from_backup(self, backup_path: str) -> None:
        """Restore Vault KV secrets and policies from backup.

        Note: auth_methods are included in the backup JSON for reference but
        are NOT restored automatically — re-enabling auth methods requires a
        root token and manual configuration of mount-specific options.
        """
        temp_dir = tempfile.mkdtemp()

        try:
            with tarfile.open(backup_path, "r:gz") as tar:
                tar.extractall(temp_dir)

            backup_file = os.path.join(temp_dir, "vault_backup", "vault_backup.json")

            if not os.path.exists(backup_file):
                raise FileNotFoundError(f"Backup file not found: {backup_file}")

            with open(backup_file, "r") as f:
                backup_data = json.load(f)

            mount_point = backup_data.get("mount_point", self._mount_point)

            for policy_name, policy_content in backup_data.get("policies", {}).items():
                try:
                    self.client.sys.create_or_update_policy(
                        name=policy_name, policy=policy_content
                    )
                except Exception as e:
                    print(f"Failed to restore policy '{policy_name}': {e}")

            for secret_path, secret_data in backup_data.get("secrets", {}).items():
                try:
                    self.client.secrets.kv.v2.create_or_update_secret(
                        path=secret_path,
                        secret=secret_data,
                        mount_point=mount_point,
                    )
                except Exception as e:
                    print(f"Failed to restore secret '{secret_path}': {e}")

            skipped = backup_data.get("warnings", [])
            if skipped:
                print(
                    f"[VaultRestore] {len(skipped)} item(s) were missing from the "
                    "backup and could not be restored:"
                )
                for w in skipped:
                    print(f"  - {w}")

        finally:
            for root, dirs, files in os.walk(temp_dir, topdown=False):
                for file in files:
                    os.remove(os.path.join(root, file))
                for dir_name in dirs:
                    os.rmdir(os.path.join(root, dir_name))
            os.rmdir(temp_dir)

    def test_connection(self) -> bool:
        try:
            if not self.client.is_authenticated():
                return False
            self.client.sys.list_auth_methods()
            return True
        except Exception as e:
            print(f"Connection test failed: {e}")
            return False
