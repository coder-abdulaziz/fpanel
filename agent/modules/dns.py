#!/usr/bin/env python3
"""
DNS Management Module
Handles Bind9 zone and record management
"""

import os
import re
from typing import Dict, Any, List
from datetime import datetime


class DnsModule:
    """Module for managing DNS zones and records"""
    
    def __init__(self, adapter):
        self.adapter = adapter
        self.bind_zones = '/etc/bind/zones'
        self.bind_config = '/etc/bind/named.conf.local'
    
    def handle_action(self, action: str, params: Dict[str, Any]) -> Any:
        """Handle DNS-related actions"""
        actions = {
            'create_zone': self.create_zone,
            'delete_zone': self.delete_zone,
            'add_record': self.add_record,
            'delete_record': self.delete_record,
            'update_record': self.update_record,
            'get_zone': self.get_zone,
            'list_zones': self.list_zones,
            'reload': self.reload_bind,
        }
        
        if action in actions:
            return actions[action](params)
        else:
            raise ValueError(f"Unknown DNS action: {action}")
    
    def create_zone(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Create a new DNS zone"""
        domain = params.get('domain')
        ns1 = params.get('ns1', f'ns1.{domain}')
        ns2 = params.get('ns2', f'ns2.{domain}')
        admin_email = params.get('admin_email', f'admin.{domain}')
        ip_address = params.get('ip_address', '127.0.0.1')
        
        if not domain:
            return {'success': False, 'error': 'Domain is required'}
        
        # Validate domain
        if not self._validate_domain(domain):
            return {'success': False, 'error': 'Invalid domain format'}
        
        # Create zones directory if needed
        os.makedirs(self.bind_zones, exist_ok=True)
        
        # Create zone file
        zone_file = f"{self.bind_zones}/{domain}.db"
        serial = datetime.now().strftime('%Y%m%d%H')
        
        zone_content = f"""; Zone file for {domain}
$TTL 86400
@       IN      SOA     {ns1}. {admin_email}. (
                        {serial}01      ; Serial
                        3600            ; Refresh
                        1800            ; Retry
                        604800          ; Expire
                        86400 )         ; Minimum TTL

; Name Servers
@       IN      NS      {ns1}.
@       IN      NS      {ns2}.

; A Records
@       IN      A       {ip_address}
ns1     IN      A       {ip_address}
ns2     IN      A       {ip_address}
www     IN      CNAME   @
mail    IN      A       {ip_address}

; MX Records
@       IN      MX      10      mail.{domain}.

; TXT Records
@       IN      TXT     "v=spf1 a mx ~all"
"""
        
        success, message = self.adapter.write_file(zone_file, zone_content, mode=0o644)
        
        if not success:
            return {'success': False, 'error': f'Failed to create zone file: {message}'}
        
        # Add zone to named.conf.local
        zone_config = f"""
zone "{domain}" {{
    type master;
    file "{zone_file}";
    allow-transfer {{ none; }};
}};
"""
        
        # Append to named.conf.local
        if os.path.exists(self.bind_config):
            with open(self.bind_config, 'a') as f:
                f.write(zone_config)
        else:
            self.adapter.write_file(self.bind_config, zone_config, mode=0o644)
        
        # Reload BIND
        self._reload_bind()
        
        return {
            'success': True,
            'message': f'DNS zone {domain} created successfully',
            'domain': domain,
            'zone_file': zone_file
        }
    
    def delete_zone(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Delete a DNS zone"""
        domain = params.get('domain')
        
        if not domain:
            return {'success': False, 'error': 'Domain is required'}
        
        # Remove zone file
        zone_file = f"{self.bind_zones}/{domain}.db"
        if os.path.exists(zone_file):
            os.remove(zone_file)
        
        # Remove from named.conf.local
        if os.path.exists(self.bind_config):
            with open(self.bind_config, 'r') as f:
                content = f.read()
            
            # Remove zone block
            pattern = rf'zone "{re.escape(domain)}" \{{[^}}]+\}};\s*\n'
            content = re.sub(pattern, '', content)
            
            with open(self.bind_config, 'w') as f:
                f.write(content)
        
        # Reload BIND
        self._reload_bind()
        
        return {
            'success': True,
            'message': f'DNS zone {domain} deleted successfully',
            'domain': domain
        }
    
    def add_record(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Add DNS record to zone"""
        domain = params.get('domain')
        record_type = params.get('record_type', 'A')
        name = params.get('name', '@')
        value = params.get('value')
        ttl = params.get('ttl', 86400)
        priority = params.get('priority', 0)
        
        if not domain or not value:
            return {'success': False, 'error': 'Domain and value are required'}
        
        zone_file = f"{self.bind_zones}/{domain}.db"
        
        if not os.path.exists(zone_file):
            return {'success': False, 'error': f'Zone file not found for {domain}'}
        
        # Build record line
        if record_type.upper() == 'MX':
            record_line = f"{name}\tIN\t{record_type}\t{priority}\t{value}.\n"
        elif record_type.upper() == 'TXT':
            record_line = f'{name}\tIN\t{record_type}\t"{value}"\n'
        else:
            record_line = f"{name}\t{ttl}\tIN\t{record_type}\t{value}\n"
        
        # Append to zone file
        with open(zone_file, 'a') as f:
            f.write(record_line)
        
        # Update serial
        self._update_serial(zone_file)
        
        # Reload BIND
        self._reload_bind()
        
        return {
            'success': True,
            'message': f'{record_type} record added to {domain}',
            'domain': domain,
            'record': {'name': name, 'type': record_type, 'value': value}
        }
    
    def delete_record(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Delete DNS record from zone"""
        domain = params.get('domain')
        record_type = params.get('record_type')
        name = params.get('name')
        value = params.get('value')
        
        if not domain or not record_type or not name:
            return {'success': False, 'error': 'Domain, record_type, and name are required'}
        
        zone_file = f"{self.bind_zones}/{domain}.db"
        
        if not os.path.exists(zone_file):
            return {'success': False, 'error': f'Zone file not found for {domain}'}
        
        with open(zone_file, 'r') as f:
            lines = f.readlines()
        
        # Find and remove matching record
        new_lines = []
        removed = False
        
        for line in lines:
            if re.match(rf'^\s*{re.escape(name)}\s+\d*\s*IN\s+{re.escape(record_type)}', line, re.IGNORECASE):
                if value is None or value in line:
                    removed = True
                    continue
            new_lines.append(line)
        
        with open(zone_file, 'w') as f:
            f.writelines(new_lines)
        
        if removed:
            self._update_serial(zone_file)
            self._reload_bind()
        
        return {
            'success': removed,
            'message': f'{record_type} record deleted from {domain}' if removed else 'Record not found',
            'domain': domain
        }
    
    def update_record(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Update DNS record in zone"""
        domain = params.get('domain')
        record_type = params.get('record_type')
        name = params.get('name')
        new_value = params.get('new_value')
        new_ttl = params.get('new_ttl')
        
        if not domain or not record_type or not name or not new_value:
            return {'success': False, 'error': 'Domain, record_type, name, and new_value are required'}
        
        zone_file = f"{self.bind_zones}/{domain}.db"
        
        if not os.path.exists(zone_file):
            return {'success': False, 'error': f'Zone file not found for {domain}'}
        
        with open(zone_file, 'r') as f:
            content = f.read()
        
        # Find and update record
        pattern = rf'^(\s*{re.escape(name)}\s+)\d*(\s*IN\s+{re.escape(record_type)}\s+)(.+)$'
        replacement = rf'\g<1>{new_ttl or 86400}\g<2>{new_value}'
        
        new_content = re.sub(pattern, replacement, content, flags=re.MULTILINE | re.IGNORECASE)
        
        with open(zone_file, 'w') as f:
            f.write(new_content)
        
        self._update_serial(zone_file)
        self._reload_bind()
        
        return {
            'success': True,
            'message': f'{record_type} record updated in {domain}',
            'domain': domain
        }
    
    def get_zone(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Get zone file content"""
        domain = params.get('domain')
        
        if not domain:
            return {'success': False, 'error': 'Domain is required'}
        
        zone_file = f"{self.bind_zones}/{domain}.db"
        
        if not os.path.exists(zone_file):
            return {'success': False, 'error': f'Zone file not found for {domain}'}
        
        with open(zone_file, 'r') as f:
            content = f.read()
        
        # Parse records
        records = self._parse_zone_records(content)
        
        return {
            'success': True,
            'domain': domain,
            'content': content,
            'records': records
        }
    
    def list_zones(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """List all DNS zones"""
        zones = []
        
        if os.path.exists(self.bind_zones):
            for filename in os.listdir(self.bind_zones):
                if filename.endswith('.db'):
                    domain = filename[:-3]  # Remove .db extension
                    zones.append(domain)
        
        return {
            'success': True,
            'zones': zones,
            'count': len(zones)
        }
    
    def reload_bind(self, params: Dict[str, Any] = None) -> Dict[str, Any]:
        """Reload BIND configuration"""
        return self._reload_bind()
    
    def _reload_bind(self) -> Dict[str, Any]:
        """Reload BIND DNS server"""
        returncode, stdout, stderr = self.adapter.run_command(
            ['systemctl', 'reload', 'bind9'],
            check=False
        )
        
        if returncode == 0:
            return {'success': True, 'message': 'BIND reloaded successfully'}
        else:
            return {'success': False, 'error': f'Failed to reload BIND: {stderr}'}
    
    def _update_serial(self, zone_file: str):
        """Update zone serial number"""
        with open(zone_file, 'r') as f:
            content = f.read()
        
        # Find and increment serial
        serial_match = re.search(r'(\d{10})\s*;\s*Serial', content)
        if serial_match:
            old_serial = serial_match.group(1)
            new_serial = datetime.now().strftime('%Y%m%d%H') + '01'
            if new_serial <= old_serial[:10]:
                # Increment if same day
                counter = int(old_serial[10:]) + 1
                new_serial = old_serial[:10] + f'{counter:02d}'
            content = content.replace(old_serial, new_serial)
        
        with open(zone_file, 'w') as f:
            f.write(content)
    
    def _parse_zone_records(self, content: str) -> List[Dict[str, str]]:
        """Parse zone file and extract records"""
        records = []
        
        for line in content.split('\n'):
            line = line.strip()
            if not line or line.startswith(';') or line.startswith('$'):
                continue
            
            parts = line.split()
            if len(parts) >= 4:
                record = {
                    'name': parts[0],
                    'ttl': parts[1] if parts[1].isdigit() else '86400',
                    'type': parts[2] if parts[1].isdigit() else parts[1],
                    'value': ' '.join(parts[3:])
                }
                records.append(record)
        
        return records
    
    def _validate_domain(self, domain: str) -> bool:
        """Validate domain name"""
        pattern = r'^[a-zA-Z0-9]([a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?(\.[a-zA-Z0-9]([a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?)*$'
        return bool(re.match(pattern, domain)) and len(domain) <= 253
