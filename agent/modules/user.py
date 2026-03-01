#!/usr/bin/env python3
"""
User Management Module
Handles user creation, deletion, and management
"""

import bcrypt
from typing import Dict, Any, Tuple


class UserModule:
    """Module for managing Linux users"""
    
    def __init__(self, adapter):
        self.adapter = adapter
    
    def handle_action(self, action: str, params: Dict[str, Any]) -> Any:
        """Handle user-related actions"""
        actions = {
            'create': self.create_user,
            'delete': self.delete_user,
            'exists': self.user_exists,
            'suspend': self.suspend_user,
            'unsuspend': self.unsuspend_user,
            'set_password': self.set_password,
            'set_quota': self.set_quota,
            'set_limits': self.set_limits,
            'enable_ssh': self.enable_ssh,
            'disable_ssh': self.disable_ssh,
            'get_info': self.get_user_info,
        }
        
        if action in actions:
            return actions[action](params)
        else:
            raise ValueError(f"Unknown user action: {action}")
    
    def create_user(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Create a new hosting user"""
        username = params.get('username')
        password = params.get('password')
        shell = params.get('shell', '/bin/bash')
        
        if not username:
            return {'success': False, 'error': 'Username is required'}
        
        if not password:
            return {'success': False, 'error': 'Password is required'}
        
        # Validate username
        if not self._validate_username(username):
            return {'success': False, 'error': 'Invalid username format'}
        
        # Hash password for Linux
        hashed_password = self._hash_password_for_linux(password)
        
        # Create user
        success, message = self.adapter.create_user(
            username=username,
            password=hashed_password,
            shell=shell
        )
        
        return {
            'success': success,
            'message': message,
            'username': username
        }
    
    def delete_user(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Delete a hosting user"""
        username = params.get('username')
        remove_home = params.get('remove_home', True)
        
        if not username:
            return {'success': False, 'error': 'Username is required'}
        
        success, message = self.adapter.delete_user(username, remove_home)
        
        return {
            'success': success,
            'message': message,
            'username': username
        }
    
    def user_exists(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Check if user exists"""
        username = params.get('username')
        
        if not username:
            return {'success': False, 'error': 'Username is required'}
        
        exists = self.adapter.user_exists(username)
        
        return {
            'success': True,
            'exists': exists,
            'username': username
        }
    
    def suspend_user(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Suspend user account"""
        username = params.get('username')
        
        if not username:
            return {'success': False, 'error': 'Username is required'}
        
        success, message = self.adapter.suspend_user(username)
        
        return {
            'success': success,
            'message': message,
            'username': username
        }
    
    def unsuspend_user(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Unsuspend user account"""
        username = params.get('username')
        
        if not username:
            return {'success': False, 'error': 'Username is required'}
        
        success, message = self.adapter.unsuspend_user(username)
        
        return {
            'success': success,
            'message': message,
            'username': username
        }
    
    def set_password(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Set user password"""
        username = params.get('username')
        password = params.get('password')
        
        if not username or not password:
            return {'success': False, 'error': 'Username and password are required'}
        
        success, message = self.adapter.set_user_password(username, password)
        
        return {
            'success': success,
            'message': message,
            'username': username
        }
    
    def set_quota(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Set disk quota for user"""
        username = params.get('username')
        quota_mb = params.get('quota_mb')
        
        if not username or quota_mb is None:
            return {'success': False, 'error': 'Username and quota_mb are required'}
        
        success, message = self.adapter.set_disk_quota(username, quota_mb)
        
        return {
            'success': success,
            'message': message,
            'username': username,
            'quota_mb': quota_mb
        }
    
    def set_limits(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Set resource limits for user"""
        username = params.get('username')
        cpu_percent = params.get('cpu_percent')
        memory_mb = params.get('memory_mb')
        io_limit = params.get('io_limit')
        process_limit = params.get('process_limit')
        
        if not username:
            return {'success': False, 'error': 'Username is required'}
        
        success, message = self.adapter.set_cgroup_limits(
            username=username,
            cpu_percent=cpu_percent,
            memory_mb=memory_mb,
            io_limit=io_limit,
            process_limit=process_limit
        )
        
        return {
            'success': success,
            'message': message,
            'username': username,
            'limits': {
                'cpu_percent': cpu_percent,
                'memory_mb': memory_mb,
                'io_limit': io_limit,
                'process_limit': process_limit
            }
        }
    
    def enable_ssh(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Enable SSH access for user"""
        username = params.get('username')
        
        if not username:
            return {'success': False, 'error': 'Username is required'}
        
        # Change shell to allow SSH
        success, message = self.adapter.run_command(
            ['usermod', '-s', '/bin/bash', username],
            check=False
        )
        
        return {
            'success': success == 0,
            'message': f"SSH enabled for {username}" if success == 0 else message,
            'username': username
        }
    
    def disable_ssh(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Disable SSH access for user"""
        username = params.get('username')
        
        if not username:
            return {'success': False, 'error': 'Username is required'}
        
        # Change shell to nologin
        success, message = self.adapter.run_command(
            ['usermod', '-s', '/usr/sbin/nologin', username],
            check=False
        )
        
        return {
            'success': success == 0,
            'message': f"SSH disabled for {username}" if success == 0 else message,
            'username': username
        }
    
    def get_user_info(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Get user information"""
        username = params.get('username')
        
        if not username:
            return {'success': False, 'error': 'Username is required'}
        
        try:
            import pwd
            import grp
            
            user_info = pwd.getpwnam(username)
            
            # Get groups
            groups = [g.gr_name for g in grp.getgrall() if username in g.gr_mem]
            
            # Get quota info
            returncode, stdout, stderr = self.adapter.run_command(
                ['quota', '-u', username],
                check=False
            )
            
            return {
                'success': True,
                'username': username,
                'uid': user_info.pw_uid,
                'gid': user_info.pw_gid,
                'home': user_info.pw_dir,
                'shell': user_info.pw_shell,
                'groups': groups,
                'quota_info': stdout if returncode == 0 else None
            }
        except KeyError:
            return {'success': False, 'error': f'User {username} not found'}
        except Exception as e:
            return {'success': False, 'error': str(e)}
    
    def _validate_username(self, username: str) -> bool:
        """Validate username format"""
        import re
        # Username must start with letter, contain only letters, numbers, underscore, hyphen
        # Length: 3-32 characters
        pattern = r'^[a-z][a-z0-9_-]{2,31}$'
        return bool(re.match(pattern, username))
    
    def _hash_password_for_linux(self, password: str) -> str:
        """Hash password for Linux system"""
        # Generate salt and hash
        salt = bcrypt.gensalt(rounds=10)
        hashed = bcrypt.hashpw(password.encode('utf-8'), salt)
        return hashed.decode('utf-8')
