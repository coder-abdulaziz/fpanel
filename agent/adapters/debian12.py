#!/usr/bin/env python3
"""
Debian 12 OS Adapter
Handles Debian 12 specific system operations
"""

import os
import re
import subprocess
import shutil
import psutil
from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime


class Debian12Adapter:
    """Adapter for Debian 12 specific operations"""
    
    def __init__(self):
        self.os_name = "Debian"
        self.os_version = "12"
        self.web_root = "/var/www"
        self.config_root = "/etc/fpanel"
        self.log_root = "/var/log/fpanel"
    
    def run_command(self, command: List[str], check: bool = True, 
                   capture_output: bool = True, input_data: str = None) -> Tuple[int, str, str]:
        """Run shell command safely"""
        try:
            result = subprocess.run(
                command,
                check=check,
                capture_output=capture_output,
                text=True,
                input=input_data
            )
            return result.returncode, result.stdout, result.stderr
        except subprocess.CalledProcessError as e:
            return e.returncode, e.stdout, e.stderr
        except Exception as e:
            return -1, "", str(e)
    
    def get_os_info(self) -> Dict[str, Any]:
        """Get OS information"""
        try:
            with open('/etc/os-release', 'r') as f:
                os_info = {}
                for line in f:
                    if '=' in line:
                        key, value = line.strip().split('=', 1)
                        os_info[key] = value.strip('"')
            
            return {
                'name': os_info.get('NAME', 'Unknown'),
                'version': os_info.get('VERSION_ID', 'Unknown'),
                'id': os_info.get('ID', 'unknown'),
                'codename': os_info.get('VERSION_CODENAME', 'unknown')
            }
        except Exception as e:
            return {'error': str(e)}
    
    def get_system_stats(self) -> Dict[str, Any]:
        """Get system statistics"""
        try:
            # CPU usage
            cpu_percent = psutil.cpu_percent(interval=1)
            cpu_count = psutil.cpu_count()
            
            # Memory usage
            memory = psutil.virtual_memory()
            
            # Disk usage
            disk = psutil.disk_usage('/')
            
            # Load average
            load_avg = os.getloadavg()
            
            # Uptime
            uptime_seconds = int(float(open('/proc/uptime').read().split()[0]))
            
            return {
                'cpu': {
                    'percent': cpu_percent,
                    'count': cpu_count,
                    'load_avg': list(load_avg)
                },
                'memory': {
                    'total': memory.total,
                    'available': memory.available,
                    'percent': memory.percent,
                    'used': memory.used,
                    'free': memory.free
                },
                'disk': {
                    'total': disk.total,
                    'used': disk.used,
                    'free': disk.free,
                    'percent': (disk.used / disk.total) * 100
                },
                'uptime': uptime_seconds,
                'timestamp': datetime.now().isoformat()
            }
        except Exception as e:
            return {'error': str(e)}
    
    # ==================== User Management ====================
    
    def user_exists(self, username: str) -> bool:
        """Check if Linux user exists"""
        try:
            import pwd
            pwd.getpwnam(username)
            return True
        except KeyError:
            return False
    
    def create_user(self, username: str, home_dir: str = None, 
                    shell: str = '/bin/bash', password: str = None) -> Tuple[bool, str]:
        """Create Linux user"""
        if self.user_exists(username):
            return False, f"User {username} already exists"
        
        if not home_dir:
            home_dir = f"{self.web_root}/{username}"
        
        # Create user command
        cmd = [
            'useradd',
            '-m',  # Create home directory
            '-d', home_dir,
            '-s', shell,
            username
        ]
        
        if password:
            cmd.extend(['-p', password])  # Pre-hashed password
        
        returncode, stdout, stderr = self.run_command(cmd, check=False)
        
        if returncode == 0:
            # Set up directory structure
            self._setup_user_directories(username, home_dir)
            return True, f"User {username} created successfully"
        else:
            return False, f"Failed to create user: {stderr}"
    
    def delete_user(self, username: str, remove_home: bool = True) -> Tuple[bool, str]:
        """Delete Linux user"""
        if not self.user_exists(username):
            return False, f"User {username} does not exist"
        
        cmd = ['userdel']
        if remove_home:
            cmd.append('-r')  # Remove home directory
        cmd.append(username)
        
        returncode, stdout, stderr = self.run_command(cmd, check=False)
        
        if returncode == 0:
            return True, f"User {username} deleted successfully"
        else:
            return False, f"Failed to delete user: {stderr}"
    
    def set_user_password(self, username: str, password: str) -> Tuple[bool, str]:
        """Set user password"""
        if not self.user_exists(username):
            return False, f"User {username} does not exist"
        
        # Use chpasswd for secure password setting
        returncode, stdout, stderr = self.run_command(
            ['chpasswd'],
            input_data=f"{username}:{password}"
        )
        
        if returncode == 0:
            return True, f"Password set for {username}"
        else:
            return False, f"Failed to set password: {stderr}"
    
    def _setup_user_directories(self, username: str, home_dir: str):
        """Set up user directory structure"""
        directories = [
            f"{home_dir}/data/www",
            f"{home_dir}/data/logs",
            f"{home_dir}/tmp",
            f"{home_dir}/.ssh"
        ]
        
        for directory in directories:
            os.makedirs(directory, exist_ok=True)
        
        # Set permissions
        os.chmod(home_dir, 0o750)
        os.chmod(f"{home_dir}/data", 0o750)
        os.chmod(f"{home_dir}/tmp", 0o700)
        os.chmod(f"{home_dir}/.ssh", 0o700)
        
        # Change ownership
        import pwd
        uid = pwd.getpwnam(username).pw_uid
        gid = pwd.getpwnam(username).pw_gid
        
        for root, dirs, files in os.walk(home_dir):
            os.chown(root, uid, gid)
            for d in dirs:
                os.chown(os.path.join(root, d), uid, gid)
            for f in files:
                os.chown(os.path.join(root, f), uid, gid)
    
    def suspend_user(self, username: str) -> Tuple[bool, str]:
        """Suspend user account"""
        if not self.user_exists(username):
            return False, f"User {username} does not exist"
        
        # Lock the user account
        returncode, stdout, stderr = self.run_command(
            ['usermod', '-L', username],
            check=False
        )
        
        if returncode == 0:
            return True, f"User {username} suspended"
        else:
            return False, f"Failed to suspend user: {stderr}"
    
    def unsuspend_user(self, username: str) -> Tuple[bool, str]:
        """Unsuspend user account"""
        if not self.user_exists(username):
            return False, f"User {username} does not exist"
        
        # Unlock the user account
        returncode, stdout, stderr = self.run_command(
            ['usermod', '-U', username],
            check=False
        )
        
        if returncode == 0:
            return True, f"User {username} unsuspended"
        else:
            return False, f"Failed to unsuspend user: {stderr}"
    
    # ==================== Resource Limits ====================
    
    def set_disk_quota(self, username: str, quota_mb: int) -> Tuple[bool, str]:
        """Set disk quota for user"""
        try:
            # Enable quotas if not already enabled
            self.run_command(['quotacheck', '-cug', '/'], check=False)
            self.run_command(['quotaon', '/'], check=False)
            
            # Set quota (soft and hard limit)
            blocks = quota_mb * 1024  # Convert MB to blocks (1KB blocks)
            returncode, stdout, stderr = self.run_command(
                ['setquota', username, str(blocks), str(blocks), '0', '0', '/'],
                check=False
            )
            
            if returncode == 0:
                return True, f"Disk quota set to {quota_mb}MB for {username}"
            else:
                return False, f"Failed to set quota: {stderr}"
        except Exception as e:
            return False, f"Error setting quota: {str(e)}"
    
    def set_cgroup_limits(self, username: str, cpu_percent: int = None,
                          memory_mb: int = None, io_limit: str = None,
                          process_limit: int = None) -> Tuple[bool, str]:
        """Set cgroup limits for user"""
        try:
            cgroup_path = f"/sys/fs/cgroup/user.slice/user-{self._get_uid(username)}.slice"
            
            # CPU limit
            if cpu_percent:
                cpu_quota = int(cpu_percent * 1000)  # Convert to microseconds
                with open(f"{cgroup_path}/cpu.max", 'w') as f:
                    f.write(f"{cpu_quota} 100000")
            
            # Memory limit
            if memory_mb:
                memory_bytes = memory_mb * 1024 * 1024
                with open(f"{cgroup_path}/memory.max", 'w') as f:
                    f.write(str(memory_bytes))
            
            # Process limit
            if process_limit:
                with open(f"{cgroup_path}/pids.max", 'w') as f:
                    f.write(str(process_limit))
            
            return True, f"Resource limits set for {username}"
        except Exception as e:
            return False, f"Error setting cgroup limits: {str(e)}"
    
    def _get_uid(self, username: str) -> int:
        """Get user ID"""
        import pwd
        return pwd.getpwnam(username).pw_uid
    
    # ==================== Service Management ====================
    
    def service_action(self, service: str, action: str) -> Tuple[bool, str]:
        """Control system service"""
        returncode, stdout, stderr = self.run_command(
            ['systemctl', action, service],
            check=False
        )
        
        if returncode == 0:
            return True, f"Service {service} {action}ed successfully"
        else:
            return False, f"Failed to {action} {service}: {stderr}"
    
    def service_status(self, service: str) -> Dict[str, Any]:
        """Get service status"""
        returncode, stdout, stderr = self.run_command(
            ['systemctl', 'status', service, '--no-pager'],
            check=False
        )
        
        is_active = 'active (running)' in stdout
        
        return {
            'service': service,
            'active': is_active,
            'status': 'running' if is_active else 'stopped',
            'output': stdout
        }
    
    def reload_service(self, service: str) -> Tuple[bool, str]:
        """Reload service configuration"""
        return self.service_action(service, 'reload')
    
    def restart_service(self, service: str) -> Tuple[bool, str]:
        """Restart service"""
        return self.service_action(service, 'restart')
    
    # ==================== File Operations ====================
    
    def write_file(self, path: str, content: str, mode: int = 0o644,
                   owner: str = None, group: str = None) -> Tuple[bool, str]:
        """Write file with proper permissions"""
        try:
            # Create directory if needed
            directory = os.path.dirname(path)
            if directory and not os.path.exists(directory):
                os.makedirs(directory, mode=0o755)
            
            # Write file
            with open(path, 'w') as f:
                f.write(content)
            
            # Set permissions
            os.chmod(path, mode)
            
            # Set ownership
            if owner or group:
                import pwd
                import grp
                uid = pwd.getpwnam(owner).pw_uid if owner else -1
                gid = grp.getgrnam(group).gr_gid if group else -1
                os.chown(path, uid, gid)
            
            return True, f"File written: {path}"
        except Exception as e:
            return False, f"Failed to write file: {str(e)}"
    
    def read_file(self, path: str) -> Tuple[bool, str]:
        """Read file content"""
        try:
            with open(path, 'r') as f:
                content = f.read()
            return True, content
        except Exception as e:
            return False, str(e)
    
    def file_exists(self, path: str) -> bool:
        """Check if file exists"""
        return os.path.exists(path)
