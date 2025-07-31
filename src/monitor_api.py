#!/usr/bin/env python3
"""
REST API interface for controlling the EPIC monitoring service.
"""

import json
import threading
from datetime import datetime
from flask import Flask, request, jsonify
from typing import Optional

from src.monitor import EpicChangeMonitor, MonitorConfig, load_config_from_file, create_default_config


class MonitorAPI:
    """REST API wrapper for the EPIC monitor"""
    
    def __init__(self, config: MonitorConfig):
        self.app = Flask(__name__)
        self.monitor: Optional[EpicChangeMonitor] = None
        self.monitor_thread: Optional[threading.Thread] = None
        self.config = config
        
        # Setup routes
        self._setup_routes()
    
    def _setup_routes(self):
        """Setup Flask routes"""
        
        @self.app.route('/api/status', methods=['GET'])
        def get_status():
            """Get monitoring status"""
            if self.monitor:
                status = self.monitor.get_status()
                return jsonify(status)
            else:
                return jsonify({
                    'is_running': False,
                    'message': 'Monitor not initialized'
                })
        
        @self.app.route('/api/start', methods=['POST'])
        def start_monitor():
            """Start the monitoring service"""
            try:
                if self.monitor and self.monitor.is_running:
                    return jsonify({
                        'success': False,
                        'message': 'Monitor is already running'
                    }), 400
                
                # Initialize monitor if not exists
                if not self.monitor:
                    self.monitor = EpicChangeMonitor(self.config)
                
                # Start in background thread
                self.monitor_thread = threading.Thread(target=self.monitor.start)
                self.monitor_thread.daemon = True
                self.monitor_thread.start()
                
                return jsonify({
                    'success': True,
                    'message': 'Monitor started successfully'
                })
                
            except Exception as e:
                return jsonify({
                    'success': False,
                    'error': str(e)
                }), 500
        
        @self.app.route('/api/stop', methods=['POST'])
        def stop_monitor():
            """Stop the monitoring service"""
            try:
                if self.monitor:
                    self.monitor.stop()
                    return jsonify({
                        'success': True,
                        'message': 'Monitor stopped successfully'
                    })
                else:
                    return jsonify({
                        'success': False,
                        'message': 'Monitor is not running'
                    }), 400
                    
            except Exception as e:
                return jsonify({
                    'success': False,
                    'error': str(e)
                }), 500
        
        @self.app.route('/api/epics', methods=['GET'])
        def list_epics():
            """List monitored EPICs"""
            if self.monitor:
                status = self.monitor.get_status()
                return jsonify({
                    'epics': list(status['monitored_epics'].keys()),
                    'details': status['monitored_epics']
                })
            else:
                return jsonify({
                    'epics': [],
                    'message': 'Monitor not initialized'
                })
        
        @self.app.route('/api/epics/<epic_id>', methods=['POST'])
        def add_epic(epic_id):
            """Add an EPIC to monitoring"""
            try:
                if not self.monitor:
                    self.monitor = EpicChangeMonitor(self.config)
                
                success = self.monitor.add_epic(epic_id)
                if success:
                    return jsonify({
                        'success': True,
                        'message': f'EPIC {epic_id} added to monitoring'
                    })
                else:
                    return jsonify({
                        'success': False,
                        'message': f'Failed to add EPIC {epic_id}'
                    }), 400
                    
            except Exception as e:
                return jsonify({
                    'success': False,
                    'error': str(e)
                }), 500
        
        @self.app.route('/api/epics/<epic_id>', methods=['DELETE'])
        def remove_epic(epic_id):
            """Remove an EPIC from monitoring"""
            try:
                if self.monitor:
                    success = self.monitor.remove_epic(epic_id)
                    if success:
                        return jsonify({
                            'success': True,
                            'message': f'EPIC {epic_id} removed from monitoring'
                        })
                    else:
                        return jsonify({
                            'success': False,
                            'message': f'EPIC {epic_id} was not being monitored'
                        }), 400
                else:
                    return jsonify({
                        'success': False,
                        'message': 'Monitor not initialized'
                    }), 400
                    
            except Exception as e:
                return jsonify({
                    'success': False,
                    'error': str(e)
                }), 500
        
        @self.app.route('/api/check', methods=['POST'])
        def force_check():
            """Force a check for changes"""
            try:
                data = request.get_json() or {}\n                epic_id = data.get('epic_id')  # Optional: check specific EPIC\n                \n                if self.monitor:\n                    results = self.monitor.force_check(epic_id)\n                    return jsonify({\n                        'success': True,\n                        'results': results\n                    })\n                else:\n                    return jsonify({\n                        'success': False,\n                        'message': 'Monitor not initialized'\n                    }), 400\n                    \n            except Exception as e:\n                return jsonify({\n                    'success': False,\n                    'error': str(e)\n                }), 500\n        \n        @self.app.route('/api/config', methods=['GET'])\n        def get_config():\n            \"\"\"Get current configuration\"\"\"\n            return jsonify({\n                'config': {\n                    'poll_interval_seconds': self.config.poll_interval_seconds,\n                    'max_concurrent_syncs': self.config.max_concurrent_syncs,\n                    'snapshot_directory': self.config.snapshot_directory,\n                    'log_level': self.config.log_level,\n                    'epic_ids': self.config.epic_ids,\n                    'auto_sync': self.config.auto_sync,\n                    'retry_attempts': self.config.retry_attempts,\n                    'retry_delay_seconds': self.config.retry_delay_seconds\n                }\n            })\n        \n        @self.app.route('/api/config', methods=['PUT'])\n        def update_config():\n            \"\"\"Update configuration (requires restart to take effect)\"\"\"\n            try:\n                data = request.get_json()\n                \n                # Update configuration\n                if 'poll_interval_seconds' in data:\n                    self.config.poll_interval_seconds = data['poll_interval_seconds']\n                if 'auto_sync' in data:\n                    self.config.auto_sync = data['auto_sync']\n                if 'epic_ids' in data:\n                    self.config.epic_ids = data['epic_ids']\n                \n                return jsonify({\n                    'success': True,\n                    'message': 'Configuration updated (restart required to take effect)',\n                    'config': {\n                        'poll_interval_seconds': self.config.poll_interval_seconds,\n                        'auto_sync': self.config.auto_sync,\n                        'epic_ids': self.config.epic_ids\n                    }\n                })\n                \n            except Exception as e:\n                return jsonify({\n                    'success': False,\n                    'error': str(e)\n                }), 500\n        \n        @self.app.route('/api/logs', methods=['GET'])\n        def get_logs():\n            \"\"\"Get recent log entries\"\"\"\n            try:\n                # Get query parameters\n                lines = request.args.get('lines', 100, type=int)\n                \n                # Read log file\n                log_file = 'logs/epic_monitor.log'\n                try:\n                    with open(log_file, 'r') as f:\n                        log_lines = f.readlines()\n                    \n                    # Return last N lines\n                    recent_logs = log_lines[-lines:] if len(log_lines) > lines else log_lines\n                    \n                    return jsonify({\n                        'success': True,\n                        'logs': [line.strip() for line in recent_logs],\n                        'total_lines': len(log_lines)\n                    })\n                    \n                except FileNotFoundError:\n                    return jsonify({\n                        'success': True,\n                        'logs': [],\n                        'message': 'Log file not found'\n                    })\n                    \n            except Exception as e:\n                return jsonify({\n                    'success': False,\n                    'error': str(e)\n                }), 500\n        \n        @self.app.route('/api/health', methods=['GET'])\n        def health_check():\n            \"\"\"Health check endpoint\"\"\"\n            return jsonify({\n                'status': 'healthy',\n                'timestamp': datetime.now().isoformat(),\n                'monitor_running': self.monitor.is_running if self.monitor else False\n            })\n        \n        @self.app.route('/', methods=['GET'])\n        def index():\n            \"\"\"API documentation\"\"\"\n            return jsonify({\n                'name': 'EPIC Change Monitor API',\n                'version': '1.0.0',\n                'endpoints': {\n                    'GET /api/status': 'Get monitoring status',\n                    'POST /api/start': 'Start monitoring service',\n                    'POST /api/stop': 'Stop monitoring service',\n                    'GET /api/epics': 'List monitored EPICs',\n                    'POST /api/epics/<epic_id>': 'Add EPIC to monitoring',\n                    'DELETE /api/epics/<epic_id>': 'Remove EPIC from monitoring',\n                    'POST /api/check': 'Force check for changes',\n                    'GET /api/config': 'Get configuration',\n                    'PUT /api/config': 'Update configuration',\n                    'GET /api/logs': 'Get recent log entries',\n                    'GET /api/health': 'Health check'\n                },\n                'monitor_status': self.monitor.is_running if self.monitor else False\n            })\n    \n    def run(self, host='127.0.0.1', port=5000, debug=False):\n        \"\"\"Run the API server\"\"\"\n        self.app.run(host=host, port=port, debug=debug)\n\n\ndef main():\n    \"\"\"Main entry point for the API server\"\"\"\n    import argparse\n    \n    parser = argparse.ArgumentParser(description='EPIC Change Monitor API Server')\n    parser.add_argument('--config', default='monitor_config.json', help='Configuration file')\n    parser.add_argument('--host', default='127.0.0.1', help='API server host')\n    parser.add_argument('--port', type=int, default=5000, help='API server port')\n    parser.add_argument('--debug', action='store_true', help='Enable debug mode')\n    parser.add_argument('--create-config', action='store_true', help='Create default config file')\n    \n    args = parser.parse_args()\n    \n    if args.create_config:\n        create_default_config(args.config)\n        return\n    \n    # Load configuration\n    try:\n        config = load_config_from_file(args.config)\n    except:\n        print(f\"Failed to load config from {args.config}, creating default...\")\n        config = create_default_config(args.config)\n    \n    # Start API server\n    api = MonitorAPI(config)\n    print(f\"Starting EPIC Change Monitor API on {args.host}:{args.port}\")\n    print(f\"Configuration: {args.config}\")\n    print(f\"Monitoring {len(config.epic_ids or [])} EPICs\")\n    print(f\"API Documentation: http://{args.host}:{args.port}/\")\n    \n    try:\n        api.run(host=args.host, port=args.port, debug=args.debug)\n    except KeyboardInterrupt:\n        print(\"\\nShutting down API server...\")\n        if api.monitor:\n            api.monitor.stop()\n\n\nif __name__ == '__main__':\n    main()
