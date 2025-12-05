import json
import os
from datetime import datetime
from typing import Dict, Optional

import httpx

from src.base import BaseBackupManager, Credentials

import hvac
import json
import tarfile
import os
import tempfile
from datetime import datetime
from urllib.parse import urlparse


class VaultBackupManager(BaseBackupManager):
    def __init__(self, credentials: Credentials) -> None:
        super().__init__(credentials)
        self.client = self._initialize_client()

    def _initialize_client(self) -> hvac.Client:
        """Initialize Vault client with provided credentials
        
        Returns:
            hvac.Client: Authenticated Vault client
        """
        client = hvac.Client(url=self.credentials.url)
        
        if self.credentials.api_key:
            client.token = self.credentials.api_key
        elif self.credentials.login and self.credentials.password:
            # Use userpass auth
            client.auth.userpass.login(
                username=self.credentials.login,
                password=self.credentials.password
            )
        else:
            raise ValueError("Either api_key or login/password credentials are required")
        
        if not client.is_authenticated():
            raise RuntimeError("Failed to authenticate with Vault")
        
        return client

    def _list_secrets_recursive(self, path: str, secrets: dict) -> None:
        """Recursively list all secrets in Vault
        
        Args:
            path: Current path to traverse
            secrets: Dictionary to store all secrets
        """
        try:
            list_response = self.client.secrets.kv.v2.list_secrets(path=path)
            keys = list_response.get("data", {}).get("keys", [])
            
            for key in keys:
                full_path = f"{path}/{key}" if path else key
                
                # If key ends with /, it's a directory, recurse
                if key.endswith("/"):
                    self._list_secrets_recursive(full_path.rstrip("/"), secrets)
                else:
                    # It's a secret, retrieve it
                    try:
                        secret = self.client.secrets.kv.v2.read_secret_version(path=full_path)
                        secrets[full_path] = secret["data"]["data"]
                    except Exception:
                        pass
        except Exception:
            pass

    def create_backup(self) -> str:
        """Create backup of all Vault secrets and configurations
        
        Returns:
            str: Path to the locally created backup tar.gz file
        """
        temp_dir = tempfile.mkdtemp()
        
        try:
            backup_data = {
                "timestamp": datetime.now().isoformat(),
                "auth_methods": {},
                "secrets": {},
                "policies": {}
            }
            
            # Backup all secrets from KV v2 mount
            self._list_secrets_recursive("", backup_data["secrets"])
            
            # Backup auth methods
            try:
                auth_methods = self.client.sys.list_auth_methods()
                backup_data["auth_methods"] = auth_methods.get("data", {})
            except Exception:
                pass
            
            # Backup policies
            try:
                policies = self.client.sys.list_policies()
                for policy_name in policies.get("data", {}).get("policies", []):
                    if policy_name not in ["root", "default"]:
                        try:
                            policy_content = self.client.sys.read_policy(name=policy_name)
                            backup_data["policies"][policy_name] = policy_content.get("data", {}).get("rules", "")
                        except Exception:
                            pass
            except Exception:
                pass
            
            # Write backup to JSON file
            backup_file = os.path.join(temp_dir, "vault_backup.json")
            with open(backup_file, "w") as f:
                json.dump(backup_data, f, indent=2, default=str)
            
            # Create tar.gz archive
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_path = f"vault_backup_{timestamp}.tar.gz"
            
            with tarfile.open(backup_path, "w:gz") as tar:
                tar.add(temp_dir, arcname="vault_backup")
            
            return backup_path
            
        finally:
            # Cleanup temporary directory
            for file in os.listdir(temp_dir):
                os.remove(os.path.join(temp_dir, file))
            os.rmdir(temp_dir)

    def restore_from_backup(self, backup_path: str, backup_destination: str) -> None:
        """Restore Vault secrets and configurations from backup
        
        Args:
            backup_path: Path to the backup tar.gz file
            backup_destination: Vault instance URL to restore to (optional, uses current client if not provided)
        """
        temp_dir = tempfile.mkdtemp()
        
        try:
            # Extract tar.gz archive
            with tarfile.open(backup_path, "r:gz") as tar:
                tar.extractall(temp_dir)
            
            backup_file = os.path.join(temp_dir, "vault_backup", "vault_backup.json")
            
            if not os.path.exists(backup_file):
                raise FileNotFoundError(f"Backup file not found: {backup_file}")
            
            with open(backup_file, "r") as f:
                backup_data = json.load(f)
            
            # Restore policies first
            policies = backup_data.get("policies", {})
            for policy_name, policy_content in policies.items():
                try:
                    self.client.sys.create_or_update_policy(
                        name=policy_name,
                        policy=policy_content
                    )
                except Exception as e:
                    print(f"Failed to restore policy {policy_name}: {str(e)}")
            
            # Restore secrets
            secrets = backup_data.get("secrets", {})
            for secret_path, secret_data in secrets.items():
                try:
                    self.client.secrets.kv.v2.create_or_update_secret(
                        path=secret_path,
                        secret=secret_data
                    )
                except Exception as e:
                    print(f"Failed to restore secret {secret_path}: {str(e)}")
            
        finally:
            # Cleanup temporary directory
            for root, dirs, files in os.walk(temp_dir, topdown=False):
                for file in files:
                    os.remove(os.path.join(root, file))
                for dir_name in dirs:
                    os.rmdir(os.path.join(root, dir_name))
            os.rmdir(temp_dir)