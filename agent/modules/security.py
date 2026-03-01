#!/usr/bin/env python3
"""
Security Management Module
Handles Fail2ban, WAF rules, and security scanning
"""

import os
import re
from typing import Dict, Any, List
from datetime import datetime


class SecurityModule:
    """Module for managing security features"""
    
    def __init__(self, adapter):
        self.adapter = adapter
        self.fail2ban_jail = '/etc/fail2ban/jail.d'
        self.fail2ban_filter = '/etc/fail2ban/filter.d'
        self.waf_rules = '/etc/nginx/waf'
    
    def handle_action(self, action: str, params: Dict[str, Any]) -> Any:
        """Handle security-related actions"""
        actions = {
            'ban_ip': self.ban_ip,
            'unban_ip': self.unban_ip,
            'list_banned': self.list_banned_ips,
            'add_waf_rule': self.add_waf_rule,
            'remove_waf_rule': self.remove_waf_rule,
            'scan_malware': self.scan_malware,
            'get_fail2ban_status': self.get_fail2ban_status,
            'configure_fail2ban': self.configure_fail2ban,
        }
        
        if action in actions:
            return actions[action](params)
        else:
            raise ValueError(f"Unknown security action: {action}")
    
    def ban_ip(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Ban an IP address"""
        ip = params.get('ip')
        reason = params.get('reason', 'Manual ban')
        duration = params.get('duration', '1h')  # 1h, 1d, permanent
        
        if not ip:
            return {'success': False, 'error': 'IP address is required'}
        
        # Validate IP
        if not self._validate_ip(ip):
            return {'success': False, 'error': 'Invalid IP address'}
        
        # Add to iptables
        returncode, stdout, stderr = self.adapter.run_command(
            ['iptables', '-I', 'INPUT', '-s', ip, '-j', 'DROP'],
            check=False
        )
        
        if returncode == 0:
            # Log ban
            self._log_security_event('BAN_IP', ip, reason)
            
            return {
                'success': True,
                'message': f'IP {ip} banned',
                'ip': ip,
                'duration': duration,
                'reason': reason
            }
        else:
            return {
                'success': False,
                'error': f'Failed to ban IP: {stderr}'
            }
    
    def unban_ip(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Unban an IP address"""
        ip = params.get('ip')
        
        if not ip:
            return {'success': False, 'error': 'IP address is required'}
        
        # Remove from iptables
        returncode, stdout, stderr = self.adapter.run_command(
            ['iptables', '-D', 'INPUT', '-s', ip, '-j', 'DROP'],
            check=False
        )
        
        # Also try to unban via fail2ban
        self.adapter.run_command(
            ['fail2ban-client', 'unban', ip],
            check=False
        )
        
        if returncode == 0:
            self._log_security_event('UNBAN_IP', ip, 'Manual unban')
            
            return {
                'success': True,
                'message': f'IP {ip} unbanned',
                'ip': ip
            }
        else:
            return {
                'success': False,
                'error': f'Failed to unban IP: {stderr}'
            }
    
    def list_banned_ips(self, params: Dict[str, Any] = None) -> Dict[str, Any]:
        """List all banned IPs"""
        # Get from iptables
        returncode, stdout, stderr = self.adapter.run_command(
            ['iptables', '-L', 'INPUT', '-n'],
            check=False
        )
        
        banned_ips = []
        
        if returncode == 0:
            for line in stdout.split('\n'):
                if 'DROP' in line:
                    match = re.search(r'(\d+\.\d+\.\d+\.\d+)', line)
                    if match:
                        banned_ips.append(match.group(1))
        
        # Get from fail2ban
        returncode, stdout, stderr = self.adapter.run_command(
            ['fail2ban-client', 'status'],
            check=False
        )
        
        fail2ban_bans = []
        if returncode == 0:
            # Parse fail2ban status
            for line in stdout.split('\n'):
                if 'Banned IP list' in line:
                    ips = re.findall(r'(\d+\.\d+\.\d+\.\d+)', line)
                    fail2ban_bans.extend(ips)
        
        return {
            'success': True,
            'iptables_banned': banned_ips,
            'fail2ban_banned': fail2ban_bans,
            'total_banned': len(set(banned_ips + fail2ban_bans))
        }
    
    def add_waf_rule(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Add WAF rule to nginx"""
        rule_name = params.get('rule_name')
        rule_pattern = params.get('rule_pattern')
        rule_action = params.get('rule_action', 'deny')
        
        if not rule_name or not rule_pattern:
            return {'success': False, 'error': 'Rule name and pattern are required'}
        
        # Create WAF rules directory
        os.makedirs(self.waf_rules, exist_ok=True)
        
        rule_file = f"{self.waf_rules}/{rule_name}.conf"
        
        rule_content = f"""# WAF Rule: {rule_name}
# Created: {datetime.now().isoformat()}

if ({rule_pattern}) {{
    return 403;
}}
"""
        
        success, message = self.adapter.write_file(rule_file, rule_content, mode=0o644)
        
        if success:
            # Reload nginx
            self.adapter.reload_service('nginx')
            
            return {
                'success': True,
                'message': f'WAF rule {rule_name} added',
                'rule_name': rule_name
            }
        else:
            return {
                'success': False,
                'error': f'Failed to add WAF rule: {message}'
            }
    
    def remove_waf_rule(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Remove WAF rule from nginx"""
        rule_name = params.get('rule_name')
        
        if not rule_name:
            return {'success': False, 'error': 'Rule name is required'}
        
        rule_file = f"{self.waf_rules}/{rule_name}.conf"
        
        if os.path.exists(rule_file):
            os.remove(rule_file)
            
            # Reload nginx
            self.adapter.reload_service('nginx')
            
            return {
                'success': True,
                'message': f'WAF rule {rule_name} removed',
                'rule_name': rule_name
            }
        else:
            return {
                'success': False,
                'error': f'WAF rule {rule_name} not found'
            }
    
    def scan_malware(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Scan for malware using AI-Bolit or ClamAV"""
        path = params.get('path', '/var/www')
        scan_type = params.get('scan_type', 'clamav')  # clamav, aibolit
        
        if scan_type == 'clamav':
            return self._scan_clamav(path)
        elif scan_type == 'aibolit':
            return self._scan_aibolit(path)
        else:
            return {'success': False, 'error': 'Unknown scan type'}
    
    def _scan_clamav(self, path: str) -> Dict[str, Any]:
        """Scan with ClamAV"""
        returncode, stdout, stderr = self.adapter.run_command(
            ['clamscan', '-r', '--infected', path],
            check=False
        )
        
        # Parse results
        infected = []
        for line in stdout.split('\n'):
            if 'FOUND' in line:
                infected.append(line)
        
        return {
            'success': True,
            'scan_type': 'clamav',
            'path': path,
            'infected_files': infected,
            'infected_count': len(infected),
            'raw_output': stdout
        }
    
    def _scan_aibolit(self, path: str) -> Dict[str, Any]:
        """Scan with AI-Bolit"""
        aibolit_path = '/usr/local/bin/ai-bolit'
        
        if not os.path.exists(aibolit_path):
            return {
                'success': False,
                'error': 'AI-Bolit not installed'
            }
        
        returncode, stdout, stderr = self.adapter.run_command(
            ['php', aibolit_path, '--path', path],
            check=False
        )
        
        return {
            'success': returncode == 0,
            'scan_type': 'aibolit',
            'path': path,
            'output': stdout,
            'errors': stderr
        }
    
    def get_fail2ban_status(self, params: Dict[str, Any] = None) -> Dict[str, Any]:
        """Get Fail2ban status"""
        returncode, stdout, stderr = self.adapter.run_command(
            ['fail2ban-client', 'status'],
            check=False
        )
        
        if returncode == 0:
            # Parse status
            jails = []
            for line in stdout.split('\n'):
                if 'Jail list' in line:
                    jails_str = line.split(':', 1)[1].strip()
                    jails = [j.strip() for j in jails_str.split(',')]
            
            return {
                'success': True,
                'status': 'running',
                'jails': jails,
                'raw_output': stdout
            }
        else:
            return {
                'success': False,
                'status': 'stopped',
                'error': stderr
            }
    
    def configure_fail2ban(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Configure Fail2ban jail"""
        jail_name = params.get('jail_name')
        enabled = params.get('enabled', True)
        max_retry = params.get('max_retry', 5)
        find_time = params.get('find_time', '10m')
        ban_time = params.get('ban_time', '1h')
        
        if not jail_name:
            return {'success': False, 'error': 'Jail name is required'}
        
        # Create jail configuration
        jail_config = f"""[{jail_name}]
enabled = {'true' if enabled else 'false'}
maxretry = {max_retry}
findtime = {find_time}
bantime = {ban_time}
"""
        
        jail_file = f"{self.fail2ban_jail}/{jail_name}.conf"
        success, message = self.adapter.write_file(jail_file, jail_config, mode=0o644)
        
        if success:
            # Reload fail2ban
            self.adapter.reload_service('fail2ban')
            
            return {
                'success': True,
                'message': f'Fail2ban jail {jail_name} configured',
                'jail_name': jail_name
            }
        else:
            return {
                'success': False,
                'error': f'Failed to configure jail: {message}'
            }
    
    def _validate_ip(self, ip: str) -> bool:
        """Validate IP address"""
        import ipaddress
        try:
            ipaddress.ip_address(ip)
            return True
        except ValueError:
            return False
    
    def _log_security_event(self, event_type: str, target: str, details: str):
        """Log security event"""
        log_dir = '/var/log/fpanel'
        os.makedirs(log_dir, exist_ok=True)
        
        log_file = f"{log_dir}/security.log"
        timestamp = datetime.now().isoformat()
        
        with open(log_file, 'a') as f:
            f.write(f"{timestamp} | {event_type} | {target} | {details}\n")
