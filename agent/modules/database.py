#!/usr/bin/env python3
"""
Database Management Module
Handles MySQL database and user management
"""

import re
import secrets
import string
from typing import Dict, Any, List


class DatabaseModule:
    """Module for managing MySQL databases"""
    
    def __init__(self, adapter):
        self.adapter = adapter
    
    def handle_action(self, action: str, params: Dict[str, Any]) -> Any:
        """Handle database-related actions"""
        actions = {
            'create_db': self.create_database,
            'delete_db': self.delete_database,
            'create_user': self.create_db_user,
            'delete_user': self.delete_db_user,
            'grant_privileges': self.grant_privileges,
            'revoke_privileges': self.revoke_privileges,
            'list_databases': self.list_databases,
            'list_users': self.list_db_users,
            'get_info': self.get_db_info,
            'change_password': self.change_password,
        }
        
        if action in actions:
            return actions[action](params)
        else:
            raise ValueError(f"Unknown database action: {action}")
    
    def _execute_mysql(self, command: str, root: bool = True) -> tuple:
        """Execute MySQL command"""
        if root:
            cmd = ['mysql', '-u', 'root', '-e', command]
        else:
            cmd = ['mysql', '-e', command]
        
        return self.adapter.run_command(cmd, check=False)
    
    def create_database(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Create a new MySQL database"""
        db_name = params.get('db_name')
        username = params.get('username')
        
        if not db_name:
            return {'success': False, 'error': 'Database name is required'}
        
        # Validate database name
        if not self._validate_db_name(db_name):
            return {'success': False, 'error': 'Invalid database name format'}
        
        # Create database
        returncode, stdout, stderr = self._execute_mysql(f"CREATE DATABASE IF NOT EXISTS `{db_name}` CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;")
        
        if returncode == 0:
            return {
                'success': True,
                'message': f'Database {db_name} created successfully',
                'db_name': db_name
            }
        else:
            return {
                'success': False,
                'error': f'Failed to create database: {stderr}'
            }
    
    def delete_database(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Delete a MySQL database"""
        db_name = params.get('db_name')
        
        if not db_name:
            return {'success': False, 'error': 'Database name is required'}
        
        returncode, stdout, stderr = self._execute_mysql(f"DROP DATABASE IF EXISTS `{db_name}`;")
        
        if returncode == 0:
            return {
                'success': True,
                'message': f'Database {db_name} deleted successfully',
                'db_name': db_name
            }
        else:
            return {
                'success': False,
                'error': f'Failed to delete database: {stderr}'
            }
    
    def create_db_user(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Create a new MySQL user"""
        db_user = params.get('db_user')
        password = params.get('password')
        host = params.get('host', 'localhost')
        
        if not db_user:
            return {'success': False, 'error': 'Database username is required'}
        
        # Generate password if not provided
        if not password:
            password = self._generate_password()
        
        # Validate username
        if not self._validate_db_name(db_user):
            return {'success': False, 'error': 'Invalid database username format'}
        
        # Create user
        returncode, stdout, stderr = self._execute_mysql(f"CREATE USER IF NOT EXISTS '{db_user}'@'{host}' IDENTIFIED BY '{password}';")
        
        if returncode == 0:
            return {
                'success': True,
                'message': f'Database user {db_user} created successfully',
                'db_user': db_user,
                'host': host,
                'password': password
            }
        else:
            return {
                'success': False,
                'error': f'Failed to create database user: {stderr}'
            }
    
    def delete_db_user(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Delete a MySQL user"""
        db_user = params.get('db_user')
        host = params.get('host', 'localhost')
        
        if not db_user:
            return {'success': False, 'error': 'Database username is required'}
        
        returncode, stdout, stderr = self._execute_mysql(f"DROP USER IF EXISTS '{db_user}'@'{host}';")
        
        if returncode == 0:
            return {
                'success': True,
                'message': f'Database user {db_user} deleted successfully',
                'db_user': db_user
            }
        else:
            return {
                'success': False,
                'error': f'Failed to delete database user: {stderr}'
            }
    
    def grant_privileges(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Grant privileges to database user"""
        db_user = params.get('db_user')
        db_name = params.get('db_name')
        host = params.get('host', 'localhost')
        privileges = params.get('privileges', 'ALL')
        
        if not db_user or not db_name:
            return {'success': False, 'error': 'Database user and database name are required'}
        
        returncode, stdout, stderr = self._execute_mysql(f"GRANT {privileges} ON `{db_name}`.* TO '{db_user}'@'{host}';")
        
        if returncode == 0:
            # Flush privileges
            self._execute_mysql("FLUSH PRIVILEGES;")
            
            return {
                'success': True,
                'message': f'Privileges granted to {db_user} on {db_name}',
                'db_user': db_user,
                'db_name': db_name,
                'privileges': privileges
            }
        else:
            return {
                'success': False,
                'error': f'Failed to grant privileges: {stderr}'
            }
    
    def revoke_privileges(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Revoke privileges from database user"""
        db_user = params.get('db_user')
        db_name = params.get('db_name')
        host = params.get('host', 'localhost')
        privileges = params.get('privileges', 'ALL')
        
        if not db_user or not db_name:
            return {'success': False, 'error': 'Database user and database name are required'}
        
        returncode, stdout, stderr = self._execute_mysql(f"REVOKE {privileges} ON `{db_name}`.* FROM '{db_user}'@'{host}';")
        
        if returncode == 0:
            # Flush privileges
            self._execute_mysql("FLUSH PRIVILEGES;")
            
            return {
                'success': True,
                'message': f'Privileges revoked from {db_user} on {db_name}',
                'db_user': db_user,
                'db_name': db_name
            }
        else:
            return {
                'success': False,
                'error': f'Failed to revoke privileges: {stderr}'
            }
    
    def list_databases(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """List all databases"""
        username = params.get('username')
        
        if username:
            # List databases for specific user
            returncode, stdout, stderr = self._execute_mysql(f"SHOW DATABASES LIKE '{username}_%';")
        else:
            # List all databases
            returncode, stdout, stderr = self._execute_mysql("SHOW DATABASES;")
        
        if returncode == 0:
            # Parse output
            databases = [line.strip() for line in stdout.split('\n')[1:] if line.strip()]
            # Filter out system databases
            system_dbs = ['Database', 'information_schema', 'mysql', 'performance_schema', 'sys']
            databases = [db for db in databases if db not in system_dbs]
            
            return {
                'success': True,
                'databases': databases,
                'count': len(databases)
            }
        else:
            return {
                'success': False,
                'error': f'Failed to list databases: {stderr}'
            }
    
    def list_db_users(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """List all database users"""
        username = params.get('username')
        
        if username:
            # List users matching pattern
            returncode, stdout, stderr = self._execute_mysql(f"SELECT User, Host FROM mysql.user WHERE User LIKE '{username}_%';")
        else:
            # List all users
            returncode, stdout, stderr = self._execute_mysql("SELECT User, Host FROM mysql.user;")
        
        if returncode == 0:
            # Parse output
            lines = stdout.strip().split('\n')[1:]  # Skip header
            users = []
            for line in lines:
                parts = line.split('\t')
                if len(parts) >= 2:
                    users.append({'user': parts[0], 'host': parts[1]})
            
            return {
                'success': True,
                'users': users,
                'count': len(users)
            }
        else:
            return {
                'success': False,
                'error': f'Failed to list users: {stderr}'
            }
    
    def get_db_info(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Get database information"""
        db_name = params.get('db_name')
        
        if not db_name:
            return {'success': False, 'error': 'Database name is required'}
        
        # Get database size
        returncode, stdout, stderr = self._execute_mysql(
            f"SELECT table_schema AS 'Database', ROUND(SUM(data_length + index_length) / 1024 / 1024, 2) AS 'Size (MB)' "
            f"FROM information_schema.tables WHERE table_schema = '{db_name}' GROUP BY table_schema;"
        )
        
        size_info = stdout.strip() if returncode == 0 else None
        
        # Get tables count
        returncode, stdout, stderr = self._execute_mysql(
            f"SELECT COUNT(*) FROM information_schema.tables WHERE table_schema = '{db_name}';"
        )
        
        tables_count = stdout.strip().split('\n')[-1] if returncode == 0 else '0'
        
        return {
            'success': True,
            'db_name': db_name,
            'size_info': size_info,
            'tables_count': tables_count
        }
    
    def change_password(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Change database user password"""
        db_user = params.get('db_user')
        new_password = params.get('new_password')
        host = params.get('host', 'localhost')
        
        if not db_user or not new_password:
            return {'success': False, 'error': 'Database user and new password are required'}
        
        returncode, stdout, stderr = self._execute_mysql(f"ALTER USER '{db_user}'@'{host}' IDENTIFIED BY '{new_password}';")
        
        if returncode == 0:
            # Flush privileges
            self._execute_mysql("FLUSH PRIVILEGES;")
            
            return {
                'success': True,
                'message': f'Password changed for {db_user}',
                'db_user': db_user
            }
        else:
            return {
                'success': False,
                'error': f'Failed to change password: {stderr}'
            }
    
    def _validate_db_name(self, name: str) -> bool:
        """Validate database/user name"""
        pattern = r'^[a-zA-Z][a-zA-Z0-9_]{0,63}$'
        return bool(re.match(pattern, name))
    
    def _generate_password(self, length: int = 16) -> str:
        """Generate secure random password"""
        alphabet = string.ascii_letters + string.digits + '!@#$%^&*'
        password = ''.join(secrets.choice(alphabet) for _ in range(length))
        return password
