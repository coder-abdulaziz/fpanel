#!/usr/bin/env python3
"""
FPANEL - Host Control Agent
Root daemon for system operations
Communicates via UNIX socket with JSON RPC
"""

import os
import sys
import json
import socket
import logging
import threading
import traceback
from datetime import datetime
from typing import Dict, Any, Optional

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('/var/log/fpanel/agent.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger('hostctl')

# Constants
SOCKET_PATH = '/run/hostctl.sock'
BUFFER_SIZE = 65536
MAX_CONNECTIONS = 50

class HostController:
    """Main controller class for handling system operations"""
    
    def __init__(self):
        self.modules = {}
        self.adapter = None
        self.load_adapter()
        self.load_modules()
    
    def load_adapter(self):
        """Load OS-specific adapter"""
        try:
            # Detect OS
            with open('/etc/os-release', 'r') as f:
                os_info = {}
                for line in f:
                    if '=' in line:
                        key, value = line.strip().split('=', 1)
                        os_info[key] = value.strip('"')
            
            os_id = os_info.get('ID', '').lower()
            version_id = os_info.get('VERSION_ID', '').split('.')[0]
            
            # Load appropriate adapter
            if os_id == 'debian' and version_id == '12':
                from adapters.debian12 import Debian12Adapter
                self.adapter = Debian12Adapter()
                logger.info("Loaded Debian 12 adapter")
            elif os_id == 'ubuntu' and version_id in ['22', '24']:
                from adapters.debian12 import Debian12Adapter
                self.adapter = Debian12Adapter()
                logger.info(f"Loaded Ubuntu {version_id} adapter")
            elif os_id == 'almalinux' and version_id == '8':
                from adapters.almalinux8 import AlmaLinux8Adapter
                self.adapter = AlmaLinux8Adapter()
                logger.info("Loaded AlmaLinux 8 adapter")
            else:
                logger.warning(f"OS {os_id} {version_id} not fully supported, using Debian 12 adapter")
                from adapters.debian12 import Debian12Adapter
                self.adapter = Debian12Adapter()
        except Exception as e:
            logger.error(f"Failed to load adapter: {e}")
            raise
    
    def load_modules(self):
        """Load all modules"""
        module_names = ['user', 'domain', 'database', 'mail', 'ftp', 'dns', 'ssl', 'security']
        
        for name in module_names:
            try:
                module_path = f'modules.{name}'
                module = __import__(module_path, fromlist=[name.title() + 'Module'])
                class_name = name.title() + 'Module'
                module_class = getattr(module, class_name)
                self.modules[name] = module_class(self.adapter)
                logger.info(f"Loaded module: {name}")
            except ImportError as e:
                logger.warning(f"Module {name} not found: {e}")
            except Exception as e:
                logger.error(f"Failed to load module {name}: {e}")
    
    def handle_request(self, request: Dict[str, Any]) -> Dict[str, Any]:
        """Handle incoming JSON RPC request"""
        try:
            # Validate request
            if 'method' not in request:
                return self.error_response(-32600, "Invalid Request: missing method")
            
            method = request['method']
            params = request.get('params', {})
            request_id = request.get('id', None)
            
            logger.info(f"Handling method: {method}")
            
            # Parse method (module.action)
            if '.' not in method:
                return self.error_response(-32601, "Method not found", request_id)
            
            module_name, action = method.split('.', 1)
            
            # Route to appropriate module
            if module_name == 'system':
                result = self.handle_system_action(action, params)
            elif module_name in self.modules:
                result = self.modules[module_name].handle_action(action, params)
            else:
                return self.error_response(-32601, f"Module {module_name} not found", request_id)
            
            return {
                'jsonrpc': '2.0',
                'result': result,
                'id': request_id
            }
            
        except Exception as e:
            logger.error(f"Error handling request: {e}")
            logger.error(traceback.format_exc())
            return self.error_response(-32603, str(e), request.get('id'))
    
    def handle_system_action(self, action: str, params: Dict[str, Any]) -> Any:
        """Handle system-level actions"""
        if action == 'ping':
            return {'status': 'ok', 'timestamp': datetime.now().isoformat()}
        elif action == 'get_os_info':
            return self.adapter.get_os_info()
        elif action == 'get_system_stats':
            return self.adapter.get_system_stats()
        else:
            raise ValueError(f"Unknown system action: {action}")
    
    def error_response(self, code: int, message: str, request_id=None) -> Dict[str, Any]:
        """Create error response"""
        return {
            'jsonrpc': '2.0',
            'error': {'code': code, 'message': message},
            'id': request_id
        }


class UnixSocketServer:
    """UNIX socket server for agent communication"""
    
    def __init__(self, socket_path: str, controller: HostController):
        self.socket_path = socket_path
        self.controller = controller
        self.server_socket = None
        self.running = False
    
    def start(self):
        """Start the socket server"""
        # Remove old socket if exists
        if os.path.exists(self.socket_path):
            os.remove(self.socket_path)
        
        # Create socket directory if needed
        socket_dir = os.path.dirname(self.socket_path)
        if not os.path.exists(socket_dir):
            os.makedirs(socket_dir, mode=0o755)
        
        # Create socket
        self.server_socket = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self.server_socket.bind(self.socket_path)
        self.server_socket.listen(MAX_CONNECTIONS)
        
        # Set permissions
        os.chmod(self.socket_path, 0o666)
        
        self.running = True
        logger.info(f"Server started on {self.socket_path}")
        
        try:
            while self.running:
                try:
                    client_socket, _ = self.server_socket.accept()
                    client_thread = threading.Thread(
                        target=self.handle_client,
                        args=(client_socket,)
                    )
                    client_thread.daemon = True
                    client_thread.start()
                except socket.error as e:
                    if self.running:
                        logger.error(f"Socket error: {e}")
        except KeyboardInterrupt:
            logger.info("Server shutting down...")
        finally:
            self.stop()
    
    def handle_client(self, client_socket: socket.socket):
        """Handle client connection"""
        try:
            # Receive data
            data = b''
            while True:
                chunk = client_socket.recv(BUFFER_SIZE)
                if not chunk:
                    break
                data += chunk
                # Check for complete JSON
                try:
                    request = json.loads(data.decode('utf-8'))
                    break
                except json.JSONDecodeError:
                    continue
            
            if data:
                request = json.loads(data.decode('utf-8'))
                response = self.controller.handle_request(request)
                response_json = json.dumps(response).encode('utf-8')
                client_socket.sendall(response_json)
        
        except json.JSONDecodeError as e:
            error_response = json.dumps({
                'jsonrpc': '2.0',
                'error': {'code': -32700, 'message': f'Parse error: {e}'},
                'id': None
            }).encode('utf-8')
            client_socket.sendall(error_response)
        
        except Exception as e:
            logger.error(f"Error handling client: {e}")
            logger.error(traceback.format_exc())
        
        finally:
            client_socket.close()
    
    def stop(self):
        """Stop the server"""
        self.running = False
        if self.server_socket:
            self.server_socket.close()
        if os.path.exists(self.socket_path):
            os.remove(self.socket_path)
        logger.info("Server stopped")


def main():
    """Main entry point"""
    # Check if running as root
    if os.geteuid() != 0:
        print("Error: This daemon must run as root", file=sys.stderr)
        sys.exit(1)
    
    # Create log directory
    log_dir = '/var/log/fpanel'
    if not os.path.exists(log_dir):
        os.makedirs(log_dir, mode=0o755)
    
    # Initialize controller
    controller = HostController()
    
    # Start server
    server = UnixSocketServer(SOCKET_PATH, controller)
    server.start()


if __name__ == '__main__':
    main()
