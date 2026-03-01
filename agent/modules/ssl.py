#!/usr/bin/env python3
"""
SSL Certificate Management Module
Handles Let's Encrypt and self-signed certificates
"""

import os
import re
from typing import Dict, Any, List
from datetime import datetime, timedelta


class SslModule:
    """Module for managing SSL certificates"""
    
    def __init__(self, adapter):
        self.adapter = adapter
        self.letsencrypt_dir = '/etc/letsencrypt/live'
        self.ssl_dir = '/etc/fpanel/ssl'
    
    def handle_action(self, action: str, params: Dict[str, Any]) -> Any:
        """Handle SSL-related actions"""
        actions = {
            'create_letsencrypt': self.create_letsencrypt,
            'delete_certificate': self.delete_certificate,
            'renew': self.renew_certificate,
            'renew_all': self.renew_all_certificates,
            'list_certificates': self.list_certificates,
            'get_info': self.get_certificate_info,
            'create_self_signed': self.create_self_signed,
        }
        
        if action in actions:
            return actions[action](params)
        else:
            raise ValueError(f"Unknown SSL action: {action}")
    
    def create_letsencrypt(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Create Let's Encrypt certificate"""
        domain = params.get('domain')
        email = params.get('email')
        wildcard = params.get('wildcard', False)
        
        if not domain:
            return {'success': False, 'error': 'Domain is required'}
        
        if not email:
            return {'success': False, 'error': 'Email is required'}
        
        # Build certbot command
        cmd = [
            'certbot', 'certonly',
            '--standalone',
            '--agree-tos',
            '--non-interactive',
            '--email', email,
            '-d', domain
        ]
        
        if wildcard:
            cmd.extend(['-d', f'*.{domain}'])
            cmd.append('--dns-route53')  # Requires DNS challenge for wildcard
        
        returncode, stdout, stderr = self.adapter.run_command(cmd, check=False)
        
        if returncode == 0:
            cert_path = f"{self.letsencrypt_dir}/{domain}/fullchain.pem"
            key_path = f"{self.letsencrypt_dir}/{domain}/privkey.pem"
            
            return {
                'success': True,
                'message': f'SSL certificate created for {domain}',
                'domain': domain,
                'certificate_path': cert_path,
                'key_path': key_path,
                'expires': self._get_expiry_date(cert_path)
            }
        else:
            return {
                'success': False,
                'error': f'Failed to create certificate: {stderr}'
            }
    
    def delete_certificate(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Delete SSL certificate"""
        domain = params.get('domain')
        
        if not domain:
            return {'success': False, 'error': 'Domain is required'}
        
        cmd = ['certbot', 'delete', '--cert-name', domain, '--non-interactive']
        returncode, stdout, stderr = self.adapter.run_command(cmd, check=False)
        
        if returncode == 0:
            return {
                'success': True,
                'message': f'SSL certificate deleted for {domain}',
                'domain': domain
            }
        else:
            return {
                'success': False,
                'error': f'Failed to delete certificate: {stderr}'
            }
    
    def renew_certificate(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Renew specific certificate"""
        domain = params.get('domain')
        
        if not domain:
            return {'success': False, 'error': 'Domain is required'}
        
        cmd = ['certbot', 'renew', '--cert-name', domain, '--non-interactive']
        returncode, stdout, stderr = self.adapter.run_command(cmd, check=False)
        
        if returncode == 0:
            cert_path = f"{self.letsencrypt_dir}/{domain}/fullchain.pem"
            
            return {
                'success': True,
                'message': f'SSL certificate renewed for {domain}',
                'domain': domain,
                'expires': self._get_expiry_date(cert_path)
            }
        else:
            return {
                'success': False,
                'error': f'Failed to renew certificate: {stderr}'
            }
    
    def renew_all_certificates(self, params: Dict[str, Any] = None) -> Dict[str, Any]:
        """Renew all certificates"""
        cmd = ['certbot', 'renew', '--non-interactive', '--quiet']
        returncode, stdout, stderr = self.adapter.run_command(cmd, check=False)
        
        if returncode == 0:
            return {
                'success': True,
                'message': 'All certificates renewed successfully'
            }
        else:
            return {
                'success': False,
                'error': f'Failed to renew certificates: {stderr}'
            }
    
    def list_certificates(self, params: Dict[str, Any] = None) -> Dict[str, Any]:
        """List all SSL certificates"""
        certificates = []
        
        if os.path.exists(self.letsencrypt_dir):
            for domain in os.listdir(self.letsencrypt_dir):
                cert_path = f"{self.letsencrypt_dir}/{domain}/fullchain.pem"
                if os.path.exists(cert_path):
                    info = self._get_certificate_info(cert_path)
                    if info:
                        certificates.append({
                            'domain': domain,
                            'expires': info.get('expires'),
                            'days_until_expiry': info.get('days_until_expiry'),
                            'issuer': info.get('issuer')
                        })
        
        return {
            'success': True,
            'certificates': certificates,
            'count': len(certificates)
        }
    
    def get_certificate_info(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Get detailed certificate information"""
        domain = params.get('domain')
        
        if not domain:
            return {'success': False, 'error': 'Domain is required'}
        
        cert_path = f"{self.letsencrypt_dir}/{domain}/fullchain.pem"
        
        if not os.path.exists(cert_path):
            return {'success': False, 'error': f'Certificate not found for {domain}'}
        
        info = self._get_certificate_info(cert_path)
        
        if info:
            return {
                'success': True,
                'domain': domain,
                'info': info
            }
        else:
            return {
                'success': False,
                'error': 'Failed to parse certificate'
            }
    
    def create_self_signed(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Create self-signed certificate"""
        domain = params.get('domain')
        days = params.get('days', 365)
        key_size = params.get('key_size', 2048)
        
        if not domain:
            return {'success': False, 'error': 'Domain is required'}
        
        # Create SSL directory if needed
        os.makedirs(self.ssl_dir, exist_ok=True)
        
        cert_path = f"{self.ssl_dir}/{domain}.crt"
        key_path = f"{self.ssl_dir}/{domain}.key"
        
        # Generate private key
        cmd_key = [
            'openssl', 'genrsa',
            '-out', key_path,
            str(key_size)
        ]
        
        returncode, stdout, stderr = self.adapter.run_command(cmd_key, check=False)
        
        if returncode != 0:
            return {
                'success': False,
                'error': f'Failed to generate private key: {stderr}'
            }
        
        # Generate certificate
        cmd_cert = [
            'openssl', 'req', '-new', '-x509',
            '-key', key_path,
            '-out', cert_path,
            '-days', str(days),
            '-subj', f'/CN={domain}'
        ]
        
        returncode, stdout, stderr = self.adapter.run_command(cmd_cert, check=False)
        
        if returncode == 0:
            return {
                'success': True,
                'message': f'Self-signed certificate created for {domain}',
                'domain': domain,
                'certificate_path': cert_path,
                'key_path': key_path,
                'expires': (datetime.now() + timedelta(days=days)).isoformat()
            }
        else:
            return {
                'success': False,
                'error': f'Failed to create certificate: {stderr}'
            }
    
    def _get_expiry_date(self, cert_path: str) -> str:
        """Get certificate expiry date"""
        cmd = [
            'openssl', 'x509',
            '-in', cert_path,
            '-noout',
            '-enddate'
        ]
        
        returncode, stdout, stderr = self.adapter.run_command(cmd, check=False)
        
        if returncode == 0:
            # Parse output: notAfter=Dec 31 23:59:59 2024 GMT
            match = re.search(r'notAfter=(.+)', stdout)
            if match:
                return match.group(1).strip()
        
        return None
    
    def _get_certificate_info(self, cert_path: str) -> Dict[str, Any]:
        """Get certificate information"""
        cmd = [
            'openssl', 'x509',
            '-in', cert_path,
            '-noout',
            '-subject', '-issuer', '-dates', '-serial'
        ]
        
        returncode, stdout, stderr = self.adapter.run_command(cmd, check=False)
        
        if returncode == 0:
            info = {}
            
            for line in stdout.split('\n'):
                if '=' in line:
                    key, value = line.split('=', 1)
                    info[key.strip().lower()] = value.strip()
            
            # Calculate days until expiry
            if 'notafter' in info:
                expiry_str = info['notafter']
                try:
                    expiry_date = datetime.strptime(expiry_str, '%b %d %H:%M:%S %Y %Z')
                    days_until = (expiry_date - datetime.now()).days
                    info['days_until_expiry'] = days_until
                    info['expires'] = expiry_date.isoformat()
                except:
                    pass
            
            return info
        
        return None
