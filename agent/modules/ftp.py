#!/usr/bin/env python3
"""
FTP Management Module
Handles ProFTPD and SFTP configuration
"""

import os
import re
from typing import Dict, Any, List


class FtpModule:
    """Module for managing FTP and SFTP accounts"""
    
    def __init__(self, adapter):
        self.adapter = adapter
        self.proftpd_conf = '/etc/proftpd/conf.d'
        self.sftp_config = '/etc/ssh/sshd_config.d'
    
    def handle_action(self, action: str, params: Dict[str, Any]) -> Any:
        """Handle FTP-related actions"""
        actions = {
            'create_ftp_user': self.create_ftp_user,
            'delete_ftp_user': self.delete_ftp_user,
            'create_sftp_user': self.create_sftp_user,
            'delete_sftp_user': self.delete_sftp_user,
            'list_ftp_users': self.list_ftp_users,
            'change_password': self.change_password,
            'enable_ftp': self.enable_ftp,
            'disable_ftp': self.disable_ftp,
        }
        
        if action in actions:
            return actions[action](params)
        else:
            raise ValueError(f"Unknown FTP action: {action}")
    
    def create_ftp_user(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Create FTP user (virtual user for ProFTPD)"""
        username = params.get('username')
        ftp_username = params.get('ftp_username')
        password = params.get('password')
        home_dir = params.get('home_dir')
        
        if not username or not ftp_username or not password:
            return {'success': False, 'error': 'Username, ftp_username, and password are required'}
        
        # Create FTP user config
        ftp_config_file = f"{self.proftpd_conf}/{username}_{ftp_username}.conf"
        
        config = f"""<IfUser {ftp_username}>
    UserPassword {ftp_username} {self._crypt_password(password)}
    UserAlias {ftp_username} {username}
    <Limit LOGIN>
        AllowUser {ftp_username}
    </Limit>
</IfUser>
"""
        
        success, message = self.adapter.write_file(ftp_config_file, config, mode=0o644)
        
        if success:
            # Reload ProFTPD
            self.adapter.reload_service('proftpd')
            
            return {
                'success': True,
                'message': f'FTP user {ftp_username} created successfully',
                'ftp_username': ftp_username,
                'home_dir': home_dir
            }
        else:
            return {
                'success': False,
                'error': f'Failed to create FTP user: {message}'
            }
    
    def delete_ftp_user(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Delete FTP user"""
        username = params.get('username')
        ftp_username = params.get('ftp_username')
        
        if not ftp_username:
            return {'success': False, 'error': 'FTP username is required'}
        
        # Remove config file
        ftp_config_file = f"{self.proftpd_conf}/{username}_{ftp_username}.conf"
        
        if os.path.exists(ftp_config_file):
            os.remove(ftp_config_file)
        
        # Reload ProFTPD
        self.adapter.reload_service('proftpd')
        
        return {
            'success': True,
            'message': f'FTP user {ftp_username} deleted successfully',
            'ftp_username': ftp_username
        }
    
    def create_sftp_user(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Create SFTP user with chroot jail"""
        username = params.get('username')
        sftp_username = params.get('sftp_username')
        password = params.get('password')
        home_dir = params.get('home_dir')
        
        if not username or not sftp_username or not password:
            return {'success': False, 'error': 'Username, sftp_username, and password are required'}
        
        # Create SFTP user config for sshd
        sftp_config_file = f"{self.sftp_config}/{sftp_username}.conf"
        
        config = f"""Match User {sftp_username}
    ChrootDirectory {home_dir}
    ForceCommand internal-sftp
    AllowTcpForwarding no
    X11Forwarding no
    PasswordAuthentication yes
"""
        
        success, message = self.adapter.write_file(sftp_config_file, config, mode=0o644)
        
        if success:
            # Create user if not exists
            if not self.adapter.user_exists(sftp_username):
                self.adapter.create_user(
                    sftp_username,
                    home_dir=home_dir,
                    shell='/usr/sbin/nologin'
                )
            
            # Set password
            self.adapter.set_user_password(sftp_username, password)
            
            # Set up chroot jail
            self._setup_chroot_jail(home_dir)
            
            # Reload SSH
            self.adapter.reload_service('ssh')
            
            return {
                'success': True,
                'message': f'SFTP user {sftp_username} created successfully',
                'sftp_username': sftp_username,
                'home_dir': home_dir,
                'port': 2222
            }
        else:
            return {
                'success': False,
                'error': f'Failed to create SFTP user: {message}'
            }
    
    def delete_sftp_user(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Delete SFTP user"""
        sftp_username = params.get('sftp_username')
        delete_user = params.get('delete_user', False)
        
        if not sftp_username:
            return {'success': False, 'error': 'SFTP username is required'}
        
        # Remove SSH config
        sftp_config_file = f"{self.sftp_config}/{sftp_username}.conf"
        if os.path.exists(sftp_config_file):
            os.remove(sftp_config_file)
        
        # Delete Linux user if requested
        if delete_user:
            self.adapter.delete_user(sftp_username, remove_home=False)
        
        # Reload SSH
        self.adapter.reload_service('ssh')
        
        return {
            'success': True,
            'message': f'SFTP user {sftp_username} deleted successfully',
            'sftp_username': sftp_username
        }
    
    def list_ftp_users(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """List FTP users for a hosting user"""
        username = params.get('username')
        
        ftp_users = []
        sftp_users = []
        
        # List ProFTPD virtual users
        if os.path.exists(self.proftpd_conf):
            for filename in os.listdir(self.proftpd_conf):
                if username and filename.startswith(f"{username}_"):
                    ftp_username = filename.replace(f"{username}_", "").replace('.conf', '')
                    ftp_users.append(ftp_username)
                elif not username and filename.endswith('.conf'):
                    parts = filename.replace('.conf', '').split('_')
                    if len(parts) >= 2:
                        ftp_users.append(parts[-1])
        
        # List SFTP users
        if os.path.exists(self.sftp_config):
            for filename in os.listdir(self.sftp_config):
                if filename.endswith('.conf'):
                    sftp_username = filename.replace('.conf', '')
                    sftp_users.append(sftp_username)
        
        return {
            'success': True,
            'ftp_users': ftp_users,
            'sftp_users': sftp_users,
            'total_ftp': len(ftp_users),
            'total_sftp': len(sftp_users)
        }
    
    def change_password(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Change FTP/SFTP user password"""
        username = params.get('username')
        ftp_username = params.get('ftp_username')
        new_password = params.get('new_password')
        user_type = params.get('type', 'ftp')  # ftp or sftp
        
        if not ftp_username or not new_password:
            return {'success': False, 'error': 'FTP username and new password are required'}
        
        if user_type == 'ftp':
            # Update ProFTPD config
            ftp_config_file = f"{self.proftpd_conf}/{username}_{ftp_username}.conf"
            
            if not os.path.exists(ftp_config_file):
                return {'success': False, 'error': f'FTP user {ftp_username} not found'}
            
            with open(ftp_config_file, 'r') as f:
                content = f.read()
            
            # Update password
            new_hash = self._crypt_password(new_password)
            content = re.sub(r'UserPassword\s+\S+\s+\S+', f'UserPassword {ftp_username} {new_hash}', content)
            
            with open(ftp_config_file, 'w') as f:
                f.write(content)
            
            # Reload ProFTPD
            self.adapter.reload_service('proftpd')
            
            return {
                'success': True,
                'message': f'FTP password changed for {ftp_username}',
                'ftp_username': ftp_username
            }
        
        else:  # sftp
            # Update Linux user password
            success, message = self.adapter.set_user_password(ftp_username, new_password)
            
            return {
                'success': success,
                'message': message,
                'sftp_username': ftp_username
            }
    
    def enable_ftp(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Enable FTP for user"""
        returncode, stdout, stderr = self.adapter.run_command(
            ['systemctl', 'start', 'proftpd'],
            check=False
        )
        
        if returncode == 0:
            self.adapter.run_command(['systemctl', 'enable', 'proftpd'], check=False)
            return {'success': True, 'message': 'FTP server enabled'}
        else:
            return {'success': False, 'error': stderr}
    
    def disable_ftp(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Disable FTP for user"""
        returncode, stdout, stderr = self.adapter.run_command(
            ['systemctl', 'stop', 'proftpd'],
            check=False
        )
        
        if returncode == 0:
            return {'success': True, 'message': 'FTP server disabled'}
        else:
            return {'success': False, 'error': stderr}
    
    def _setup_chroot_jail(self, home_dir: str):
        """Set up chroot jail for SFTP"""
        # Create directory structure
        os.makedirs(home_dir, exist_ok=True)
        
        # Set ownership to root (required for chroot)
        os.chmod(home_dir, 0o755)
        
        # Create upload directory
        upload_dir = f"{home_dir}/upload"
        os.makedirs(upload_dir, exist_ok=True)
    
    def _crypt_password(self, password: str) -> str:
        """Crypt password for ProFTPD"""
        import crypt
        import secrets
        
        # Generate salt
        salt = crypt.mksalt(crypt.METHOD_SHA512)
        return crypt.crypt(password, salt)
