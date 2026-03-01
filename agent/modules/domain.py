#!/usr/bin/env python3
"""
Domain Management Module
Handles domain creation, deletion, and web server configuration
"""

import os
import re
from typing import Dict, Any
from datetime import datetime


class DomainModule:
    """Module for managing domains and virtual hosts"""
    
    def __init__(self, adapter):
        self.adapter = adapter
        self.nginx_sites = '/etc/nginx/sites-available'
        self.nginx_enabled = '/etc/nginx/sites-enabled'
        self.php_fpm_pools = '/etc/php/8.2/fpm/pool.d'
        self.web_root = '/var/www'
    
    def handle_action(self, action: str, params: Dict[str, Any]) -> Any:
        """Handle domain-related actions"""
        actions = {
            'create': self.create_domain,
            'delete': self.delete_domain,
            'enable': self.enable_domain,
            'disable': self.disable_domain,
            'list': self.list_domains,
            'get_info': self.get_domain_info,
            'create_ssl': self.create_ssl,
            'delete_ssl': self.delete_ssl,
            'set_php_version': self.set_php_version,
        }
        
        if action in actions:
            return actions[action](params)
        else:
            raise ValueError(f"Unknown domain action: {action}")
    
    def create_domain(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Create a new domain with vhost"""
        domain = params.get('domain')
        username = params.get('username')
        php_version = params.get('php_version', '8.2')
        web_server = params.get('web_server', 'nginx')
        
        if not domain or not username:
            return {'success': False, 'error': 'Domain and username are required'}
        
        # Validate domain
        if not self._validate_domain(domain):
            return {'success': False, 'error': 'Invalid domain format'}
        
        # Check if user exists
        if not self.adapter.user_exists(username):
            return {'success': False, 'error': f'User {username} does not exist'}
        
        # Create domain directory
        domain_dir = f"{self.web_root}/{username}/data/www/{domain}"
        os.makedirs(domain_dir, exist_ok=True)
        
        # Create index file
        index_file = f"{domain_dir}/index.php"
        if not os.path.exists(index_file):
            with open(index_file, 'w') as f:
                f.write(self._get_default_index(domain))
        
        # Set permissions
        import pwd
        uid = pwd.getpwnam(username).pw_uid
        gid = pwd.getpwnam(username).pw_gid
        os.chown(domain_dir, uid, gid)
        
        # Create PHP-FPM pool if not exists
        self._create_php_fpm_pool(username, php_version)
        
        # Create nginx vhost
        if web_server == 'nginx':
            vhost_result = self._create_nginx_vhost(domain, username, php_version)
            if not vhost_result['success']:
                return vhost_result
        
        # Reload services
        self.adapter.reload_service('nginx')
        self.adapter.reload_service(f'php{php_version}-fpm')
        
        return {
            'success': True,
            'message': f'Domain {domain} created successfully',
            'domain': domain,
            'username': username,
            'document_root': domain_dir,
            'php_version': php_version
        }
    
    def delete_domain(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Delete a domain"""
        domain = params.get('domain')
        username = params.get('username')
        delete_files = params.get('delete_files', False)
        
        if not domain:
            return {'success': False, 'error': 'Domain is required'}
        
        # Disable nginx vhost
        self._disable_nginx_vhost(domain)
        
        # Remove nginx config
        vhost_file = f"{self.nginx_sites}/{domain}.conf"
        if os.path.exists(vhost_file):
            os.remove(vhost_file)
        
        # Delete files if requested
        if delete_files and username:
            domain_dir = f"{self.web_root}/{username}/data/www/{domain}"
            if os.path.exists(domain_dir):
                import shutil
                shutil.rmtree(domain_dir)
        
        # Reload nginx
        self.adapter.reload_service('nginx')
        
        return {
            'success': True,
            'message': f'Domain {domain} deleted successfully',
            'domain': domain
        }
    
    def enable_domain(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Enable a domain"""
        domain = params.get('domain')
        
        if not domain:
            return {'success': False, 'error': 'Domain is required'}
        
        return self._enable_nginx_vhost(domain)
    
    def disable_domain(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Disable a domain"""
        domain = params.get('domain')
        
        if not domain:
            return {'success': False, 'error': 'Domain is required'}
        
        return self._disable_nginx_vhost(domain)
    
    def list_domains(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """List all domains for a user"""
        username = params.get('username')
        
        domains = []
        
        if username:
            # List domains for specific user
            user_www_dir = f"{self.web_root}/{username}/data/www"
            if os.path.exists(user_www_dir):
                domains = [d for d in os.listdir(user_www_dir) 
                          if os.path.isdir(os.path.join(user_www_dir, d))]
        else:
            # List all domains from nginx sites
            if os.path.exists(self.nginx_sites):
                domains = [f.replace('.conf', '') for f in os.listdir(self.nginx_sites)
                          if f.endswith('.conf')]
        
        return {
            'success': True,
            'domains': domains,
            'count': len(domains)
        }
    
    def get_domain_info(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Get domain information"""
        domain = params.get('domain')
        
        if not domain:
            return {'success': False, 'error': 'Domain is required'}
        
        vhost_file = f"{self.nginx_sites}/{domain}.conf"
        
        info = {
            'domain': domain,
            'enabled': os.path.exists(f"{self.nginx_enabled}/{domain}.conf"),
            'config_exists': os.path.exists(vhost_file),
        }
        
        # Parse config for document root
        if info['config_exists']:
            with open(vhost_file, 'r') as f:
                content = f.read()
                root_match = re.search(r'root\s+([^;]+);', content)
                if root_match:
                    info['document_root'] = root_match.group(1).strip()
                
                php_match = re.search(r'php(\d+\.\d+)', content)
                if php_match:
                    info['php_version'] = php_match.group(1)
        
        return {
            'success': True,
            'info': info
        }
    
    def create_ssl(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Create SSL certificate using Let's Encrypt"""
        domain = params.get('domain')
        email = params.get('email', 'admin@' + domain)
        
        if not domain:
            return {'success': False, 'error': 'Domain is required'}
        
        # Use certbot to create certificate
        cmd = [
            'certbot', 'certonly', '--nginx',
            '-d', domain,
            '--non-interactive',
            '--agree-tos',
            '--email', email
        ]
        
        returncode, stdout, stderr = self.adapter.run_command(cmd, check=False)
        
        if returncode == 0:
            # Update nginx config to use SSL
            self._update_nginx_ssl(domain)
            self.adapter.reload_service('nginx')
            
            return {
                'success': True,
                'message': f'SSL certificate created for {domain}',
                'domain': domain,
                'certificate_path': f'/etc/letsencrypt/live/{domain}/fullchain.pem',
                'key_path': f'/etc/letsencrypt/live/{domain}/privkey.pem'
            }
        else:
            return {
                'success': False,
                'error': f'Failed to create SSL certificate: {stderr}'
            }
    
    def delete_ssl(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Delete SSL certificate"""
        domain = params.get('domain')
        
        if not domain:
            return {'success': False, 'error': 'Domain is required'}
        
        cmd = ['certbot', 'delete', '--cert-name', domain, '--non-interactive']
        returncode, stdout, stderr = self.adapter.run_command(cmd, check=False)
        
        return {
            'success': returncode == 0,
            'message': f'SSL certificate deleted for {domain}' if returncode == 0 else stderr,
            'domain': domain
        }
    
    def set_php_version(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Change PHP version for domain"""
        domain = params.get('domain')
        username = params.get('username')
        php_version = params.get('php_version')
        
        if not domain or not php_version:
            return {'success': False, 'error': 'Domain and PHP version are required'}
        
        # Update PHP-FPM pool
        if username:
            self._create_php_fpm_pool(username, php_version)
        
        # Update nginx config
        self._update_nginx_php_version(domain, php_version)
        
        # Reload services
        self.adapter.reload_service('nginx')
        self.adapter.reload_service(f'php{php_version}-fpm')
        
        return {
            'success': True,
            'message': f'PHP version changed to {php_version} for {domain}',
            'domain': domain,
            'php_version': php_version
        }
    
    def _validate_domain(self, domain: str) -> bool:
        """Validate domain name format"""
        pattern = r'^[a-zA-Z0-9]([a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?(\.[a-zA-Z0-9]([a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?)*$'
        return bool(re.match(pattern, domain)) and len(domain) <= 253
    
    def _create_nginx_vhost(self, domain: str, username: str, php_version: str) -> Dict[str, Any]:
        """Create nginx virtual host configuration"""
        document_root = f"{self.web_root}/{username}/data/www/{domain}"
        socket_path = f"/run/php/php{php_version}-{username}.sock"
        
        config = f"""server {{
    listen 80;
    listen [::]:80;
    server_name {domain} www.{domain};
    root {document_root};
    index index.php index.html index.htm;

    access_log /var/log/nginx/{domain}.access.log;
    error_log /var/log/nginx/{domain}.error.log;

    # Security headers
    add_header X-Frame-Options "SAMEORIGIN" always;
    add_header X-Content-Type-Options "nosniff" always;
    add_header X-XSS-Protection "1; mode=block" always;
    add_header Referrer-Policy "strict-origin-when-cross-origin" always;

    # WAF Rules
    location ~* \.(jpg|jpeg|png|gif|ico|css|js|svg|woff|woff2|ttf|eot)$ {{
        expires 1y;
        add_header Cache-Control "public, immutable";
    }}

    # Block access to sensitive files
    location ~ /\. {{
        deny all;
        access_log off;
        log_not_found off;
    }}

    location ~* ^/(\.htaccess|\.htpasswd|\.env|\.git|\.svn|\.hg) {{
        deny all;
    }}

    location ~* \.(sql|log|conf|bak|backup|swp|swo)$ {{
        deny all;
    }}

    # PHP handling
    location ~ \.php$ {{
        try_files $uri =404;
        fastcgi_split_path_info ^(.+\.php)(/.+)$;
        fastcgi_pass unix:{socket_path};
        fastcgi_index index.php;
        include fastcgi_params;
        fastcgi_param SCRIPT_FILENAME $document_root$fastcgi_script_name;
        fastcgi_param PATH_INFO $fastcgi_path_info;
        fastcgi_param PHP_VALUE "open_basedir={self.web_root}/{username}/:/tmp/:/var/tmp/";
        fastcgi_read_timeout 300;
    }}

    location / {{
        try_files $uri $uri/ /index.php?$query_string;
    }}
}}
"""
        
        vhost_file = f"{self.nginx_sites}/{domain}.conf"
        success, message = self.adapter.write_file(vhost_file, config, mode=0o644)
        
        if success:
            # Enable site
            return self._enable_nginx_vhost(domain)
        else:
            return {'success': False, 'error': message}
    
    def _enable_nginx_vhost(self, domain: str) -> Dict[str, Any]:
        """Enable nginx virtual host"""
        available = f"{self.nginx_sites}/{domain}.conf"
        enabled = f"{self.nginx_enabled}/{domain}.conf"
        
        if not os.path.exists(available):
            return {'success': False, 'error': f'Virtual host config not found for {domain}'}
        
        if os.path.exists(enabled):
            return {'success': True, 'message': f'Domain {domain} is already enabled'}
        
        os.symlink(available, enabled)
        
        return {'success': True, 'message': f'Domain {domain} enabled'}
    
    def _disable_nginx_vhost(self, domain: str) -> Dict[str, Any]:
        """Disable nginx virtual host"""
        enabled = f"{self.nginx_enabled}/{domain}.conf"
        
        if os.path.exists(enabled):
            os.remove(enabled)
        
        return {'success': True, 'message': f'Domain {domain} disabled'}
    
    def _create_php_fpm_pool(self, username: str, php_version: str) -> Dict[str, Any]:
        """Create PHP-FPM pool for user"""
        pool_file = f"{self.php_fpm_pools}/{username}.conf"
        socket_path = f"/run/php/php{php_version}-{username}.sock"
        
        config = f"""[{username}]
user = {username}
group = {username}
listen = {socket_path}
listen.owner = www-data
listen.group = www-data
pm = dynamic
pm.max_children = 5
pm.start_servers = 2
pm.min_spare_servers = 1
pm.max_spare_servers = 3
pm.max_requests = 500
php_admin_value[open_basedir] = /var/www/{username}/:/tmp/:/var/tmp/
php_admin_value[upload_tmp_dir] = /var/www/{username}/tmp
php_admin_value[session.save_path] = /var/www/{username}/tmp
php_admin_value[disable_functions] = exec,passthru,shell_exec,system,proc_open,popen,curl_exec,curl_multi_exec,parse_ini_file,show_source
"""
        
        success, message = self.adapter.write_file(pool_file, config, mode=0o644)
        
        return {'success': success, 'message': message}
    
    def _update_nginx_ssl(self, domain: str):
        """Update nginx config to use SSL"""
        vhost_file = f"{self.nginx_sites}/{domain}.conf"
        
        if not os.path.exists(vhost_file):
            return
        
        with open(vhost_file, 'r') as f:
            content = f.read()
        
        # Add SSL configuration
        ssl_config = f"""
    listen 443 ssl http2;
    listen [::]:443 ssl http2;
    ssl_certificate /etc/letsencrypt/live/{domain}/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/{domain}/privkey.pem;
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers ECDHE-ECDSA-AES128-GCM-SHA256:ECDHE-RSA-AES128-GCM-SHA256:ECDHE-ECDSA-AES256-GCM-SHA384:ECDHE-RSA-AES256-GCM-SHA384;
    ssl_prefer_server_ciphers off;
    ssl_session_cache shared:SSL:10m;
    ssl_session_timeout 1d;
"""
        
        # Replace listen directives
        content = re.sub(r'listen 80;\n\s*listen \[::\]:80;', 
                        f'listen 80;\n    listen [::]:80;\n    return 301 https://$server_name$request_uri;\n}}\n\nserver {{{ssl_config}', 
                        content)
        
        with open(vhost_file, 'w') as f:
            f.write(content)
    
    def _update_nginx_php_version(self, domain: str, php_version: str):
        """Update PHP version in nginx config"""
        vhost_file = f"{self.nginx_sites}/{domain}.conf"
        
        if not os.path.exists(vhost_file):
            return
        
        with open(vhost_file, 'r') as f:
            content = f.read()
        
        # Update socket path
        content = re.sub(r'fastcgi_pass unix:/run/php/php[\d.]+-[^;]+\.sock;',
                        f'fastcgi_pass unix:/run/php/php{php_version}-{domain.split(".")[0]}.sock;',
                        content)
        
        with open(vhost_file, 'w') as f:
            f.write(content)
    
    def _get_default_index(self, domain: str) -> str:
        """Get default index.php content"""
        return f"""<!DOCTYPE html>
<html lang="uz">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{domain} - FPANEL</title>
    <style>
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            display: flex;
            justify-content: center;
            align-items: center;
            min-height: 100vh;
            margin: 0;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
        }}
        .container {{
            text-align: center;
            padding: 2rem;
        }}
        h1 {{
            font-size: 3rem;
            margin-bottom: 1rem;
        }}
        p {{
            font-size: 1.2rem;
            opacity: 0.9;
        }}
    </style>
</head>
<body>
    <div class="container">
        <h1>{domain}</h1>
        <p>Sayt muvaffaqiyatli yaratildi!</p>
        <p>Powered by FPANEL</p>
    </div>
</body>
</html>
"""
