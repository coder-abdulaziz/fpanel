#!/usr/bin/env python3
"""
Mail Management Module
Handles Exim and Dovecot configuration
"""

import os
import re
import secrets
import string
from typing import Dict, Any, List


class MailModule:
    """Module for managing mail accounts and domains"""
    
    def __init__(self, adapter):
        self.adapter = adapter
        self.exim_config = '/etc/exim4'
        self.dovecot_config = '/etc/dovecot'
        self.mail_dir = '/var/mail'
        self.virtual_mail = '/var/mail/virtual'
    
    def handle_action(self, action: str, params: Dict[str, Any]) -> Any:
        """Handle mail-related actions"""
        actions = {
            'create_domain': self.create_mail_domain,
            'delete_domain': self.delete_mail_domain,
            'create_account': self.create_mail_account,
            'delete_account': self.delete_mail_account,
            'change_password': self.change_mail_password,
            'list_accounts': self.list_mail_accounts,
            'list_domains': self.list_mail_domains,
            'get_quota': self.get_mail_quota,
            'set_quota': self.set_mail_quota,
        }
        
        if action in actions:
            return actions[action](params)
        else:
            raise ValueError(f"Unknown mail action: {action}")
    
    def create_mail_domain(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Create mail domain"""
        domain = params.get('domain')
        
        if not domain:
            return {'success': False, 'error': 'Domain is required'}
        
        # Validate domain
        if not self._validate_domain(domain):
            return {'success': False, 'error': 'Invalid domain format'}
        
        # Add domain to Exim local domains
        local_domains_file = f"{self.exim_config}/conf.d/main/01_local_domains"
        
        if os.path.exists(local_domains_file):
            with open(local_domains_file, 'r') as f:
                content = f.read()
            
            if domain not in content:
                content = content.rstrip() + f"\n{domain}"
                
                with open(local_domains_file, 'w') as f:
                    f.write(content)
        else:
            # Create file
            self.adapter.write_file(local_domains_file, f"{domain}\n", mode=0o644)
        
        # Create domain directory
        domain_dir = f"{self.virtual_mail}/{domain}"
        os.makedirs(domain_dir, exist_ok=True)
        
        # Update Exim
        self.adapter.run_command(['update-exim4.conf'], check=False)
        self.adapter.reload_service('exim4')
        
        return {
            'success': True,
            'message': f'Mail domain {domain} created successfully',
            'domain': domain
        }
    
    def delete_mail_domain(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Delete mail domain"""
        domain = params.get('domain')
        delete_accounts = params.get('delete_accounts', False)
        
        if not domain:
            return {'success': False, 'error': 'Domain is required'}
        
        # Remove from Exim local domains
        local_domains_file = f"{self.exim_config}/conf.d/main/01_local_domains"
        
        if os.path.exists(local_domains_file):
            with open(local_domains_file, 'r') as f:
                lines = f.readlines()
            
            with open(local_domains_file, 'w') as f:
                for line in lines:
                    if line.strip() != domain:
                        f.write(line)
        
        # Delete accounts if requested
        if delete_accounts:
            domain_dir = f"{self.virtual_mail}/{domain}"
            if os.path.exists(domain_dir):
                import shutil
                shutil.rmtree(domain_dir)
        
        # Update Exim
        self.adapter.run_command(['update-exim4.conf'], check=False)
        self.adapter.reload_service('exim4')
        
        return {
            'success': True,
            'message': f'Mail domain {domain} deleted successfully',
            'domain': domain
        }
    
    def create_mail_account(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Create mail account"""
        domain = params.get('domain')
        email = params.get('email')
        password = params.get('password')
        quota_mb = params.get('quota_mb', 1000)
        
        if not domain or not email:
            return {'success': False, 'error': 'Domain and email are required'}
        
        # Generate password if not provided
        if not password:
            password = self._generate_password()
        
        # Create mail user
        local_part = email.split('@')[0]
        mail_dir = f"{self.virtual_mail}/{domain}/{local_part}"
        
        os.makedirs(mail_dir, exist_ok=True)
        os.makedirs(f"{mail_dir}/cur", exist_ok=True)
        os.makedirs(f"{mail_dir}/new", exist_ok=True)
        os.makedirs(f"{mail_dir}/tmp", exist_ok=True)
        
        # Set permissions
        os.chmod(mail_dir, 0o700)
        
        # Add to Dovecot passwd file
        passwd_file = f"{self.dovecot_config}/users"
        
        # Hash password
        hashed_password = self._hash_password(password)
        
        user_entry = f"{email}:{hashed_password}:{quota_mb * 1024 * 1024}\n"
        
        with open(passwd_file, 'a') as f:
            f.write(user_entry)
        
        # Reload Dovecot
        self.adapter.reload_service('dovecot')
        
        return {
            'success': True,
            'message': f'Mail account {email} created successfully',
            'email': email,
            'password': password,
            'quota_mb': quota_mb
        }
    
    def delete_mail_account(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Delete mail account"""
        email = params.get('email')
        delete_maildir = params.get('delete_maildir', False)
        
        if not email:
            return {'success': False, 'error': 'Email is required'}
        
        local_part, domain = email.split('@')
        
        # Remove from Dovecot passwd file
        passwd_file = f"{self.dovecot_config}/users"
        
        if os.path.exists(passwd_file):
            with open(passwd_file, 'r') as f:
                lines = f.readlines()
            
            with open(passwd_file, 'w') as f:
                for line in lines:
                    if not line.startswith(f"{email}:"):
                        f.write(line)
        
        # Delete maildir if requested
        if delete_maildir:
            mail_dir = f"{self.virtual_mail}/{domain}/{local_part}"
            if os.path.exists(mail_dir):
                import shutil
                shutil.rmtree(mail_dir)
        
        # Reload Dovecot
        self.adapter.reload_service('dovecot')
        
        return {
            'success': True,
            'message': f'Mail account {email} deleted successfully',
            'email': email
        }
    
    def change_mail_password(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Change mail account password"""
        email = params.get('email')
        new_password = params.get('new_password')
        
        if not email or not new_password:
            return {'success': False, 'error': 'Email and new password are required'}
        
        passwd_file = f"{self.dovecot_config}/users"
        
        if not os.path.exists(passwd_file):
            return {'success': False, 'error': 'Passwd file not found'}
        
        # Read current entries
        with open(passwd_file, 'r') as f:
            lines = f.readlines()
        
        # Find and update entry
        updated = False
        new_lines = []
        
        for line in lines:
            if line.startswith(f"{email}:"):
                parts = line.strip().split(':')
                if len(parts) >= 3:
                    hashed_password = self._hash_password(new_password)
                    new_lines.append(f"{email}:{hashed_password}:{parts[2]}\n")
                    updated = True
                else:
                    new_lines.append(line)
            else:
                new_lines.append(line)
        
        if not updated:
            return {'success': False, 'error': f'Email {email} not found'}
        
        with open(passwd_file, 'w') as f:
            f.writelines(new_lines)
        
        # Reload Dovecot
        self.adapter.reload_service('dovecot')
        
        return {
            'success': True,
            'message': f'Password changed for {email}',
            'email': email
        }
    
    def list_mail_accounts(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """List mail accounts for a domain"""
        domain = params.get('domain')
        
        accounts = []
        passwd_file = f"{self.dovecot_config}/users"
        
        if os.path.exists(passwd_file):
            with open(passwd_file, 'r') as f:
                for line in f:
                    if ':' in line:
                        email = line.split(':')[0]
                        if domain:
                            if email.endswith(f'@{domain}'):
                                accounts.append(email)
                        else:
                            accounts.append(email)
        
        return {
            'success': True,
            'accounts': accounts,
            'count': len(accounts)
        }
    
    def list_mail_domains(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """List all mail domains"""
        domains = []
        
        # Get from Exim local domains
        local_domains_file = f"{self.exim_config}/conf.d/main/01_local_domains"
        
        if os.path.exists(local_domains_file):
            with open(local_domains_file, 'r') as f:
                for line in f:
                    domain = line.strip()
                    if domain and not domain.startswith('#'):
                        domains.append(domain)
        
        return {
            'success': True,
            'domains': domains,
            'count': len(domains)
        }
    
    def get_mail_quota(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Get mail account quota usage"""
        email = params.get('email')
        
        if not email:
            return {'success': False, 'error': 'Email is required'}
        
        local_part, domain = email.split('@')
        mail_dir = f"{self.virtual_mail}/{domain}/{local_part}"
        
        if not os.path.exists(mail_dir):
            return {'success': False, 'error': 'Mail directory not found'}
        
        # Calculate size
        total_size = 0
        for dirpath, dirnames, filenames in os.walk(mail_dir):
            for f in filenames:
                fp = os.path.join(dirpath, f)
                total_size += os.path.getsize(fp)
        
        # Get quota from passwd file
        quota = 0
        passwd_file = f"{self.dovecot_config}/users"
        
        if os.path.exists(passwd_file):
            with open(passwd_file, 'r') as f:
                for line in f:
                    if line.startswith(f"{email}:"):
                        parts = line.strip().split(':')
                        if len(parts) >= 3:
                            quota = int(parts[2])
                        break
        
        return {
            'success': True,
            'email': email,
            'used_bytes': total_size,
            'used_mb': round(total_size / (1024 * 1024), 2),
            'quota_bytes': quota,
            'quota_mb': round(quota / (1024 * 1024), 2) if quota else 0
        }
    
    def set_mail_quota(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Set mail account quota"""
        email = params.get('email')
        quota_mb = params.get('quota_mb')
        
        if not email or quota_mb is None:
            return {'success': False, 'error': 'Email and quota_mb are required'}
        
        passwd_file = f"{self.dovecot_config}/users"
        
        if not os.path.exists(passwd_file):
            return {'success': False, 'error': 'Passwd file not found'}
        
        # Read and update
        with open(passwd_file, 'r') as f:
            lines = f.readlines()
        
        updated = False
        new_lines = []
        
        for line in lines:
            if line.startswith(f"{email}:"):
                parts = line.strip().split(':')
                if len(parts) >= 2:
                    new_lines.append(f"{parts[0]}:{parts[1]}:{quota_mb * 1024 * 1024}\n")
                    updated = True
                else:
                    new_lines.append(line)
            else:
                new_lines.append(line)
        
        if not updated:
            return {'success': False, 'error': f'Email {email} not found'}
        
        with open(passwd_file, 'w') as f:
            f.writelines(new_lines)
        
        return {
            'success': True,
            'message': f'Quota set to {quota_mb}MB for {email}',
            'email': email,
            'quota_mb': quota_mb
        }
    
    def _validate_domain(self, domain: str) -> bool:
        """Validate domain name"""
        pattern = r'^[a-zA-Z0-9]([a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?(\.[a-zA-Z0-9]([a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?)*$'
        return bool(re.match(pattern, domain)) and len(domain) <= 253
    
    def _generate_password(self, length: int = 16) -> str:
        """Generate secure random password"""
        alphabet = string.ascii_letters + string.digits + '!@#$%^&*'
        return ''.join(secrets.choice(alphabet) for _ in range(length))
    
    def _hash_password(self, password: str) -> str:
        """Hash password for Dovecot"""
        import crypt
        import secrets
        
        # Generate salt for SHA512
        salt = crypt.mksalt(crypt.METHOD_SHA512)
        return crypt.crypt(password, salt)
