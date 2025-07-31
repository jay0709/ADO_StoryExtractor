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
                data = request.get_json() or {}
                epic_id = data.get('epic_id')  # Optional: check specific EPIC
                
                if self.monitor:
                    results = self.monitor.force_check(epic_id)
                    return jsonify({
                        'success': True,
                        'results': results
                    })
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
        
        @self.app.route('/api/config', methods=['GET'])
        def get_config():
            """Get current configuration"""
            return jsonify({
                'config': {
                    'poll_interval_seconds': self.config.poll_interval_seconds,
                    'max_concurrent_syncs': self.config.max_concurrent_syncs,
                    'snapshot_directory': self.config.snapshot_directory,
                    'log_level': self.config.log_level,
                    'epic_ids': self.config.epic_ids,
                    'auto_sync': self.config.auto_sync,
                    'retry_attempts': self.config.retry_attempts,
                    'retry_delay_seconds': self.config.retry_delay_seconds
                }
            })
        
        @self.app.route('/api/config', methods=['PUT'])
        def update_config():
            """Update configuration (requires restart to take effect)"""
            try:
                data = request.get_json()
                
                # Update configuration
                if 'poll_interval_seconds' in data:
                    self.config.poll_interval_seconds = data['poll_interval_seconds']
                if 'auto_sync' in data:
                    self.config.auto_sync = data['auto_sync']
                if 'epic_ids' in data:
                    self.config.epic_ids = data['epic_ids']
                
                return jsonify({
                    'success': True,
                    'message': 'Configuration updated (restart required to take effect)',
                    'config': {
                        'poll_interval_seconds': self.config.poll_interval_seconds,
                        'auto_sync': self.config.auto_sync,
                        'epic_ids': self.config.epic_ids
                    }
                })
                
            except Exception as e:
                return jsonify({
                    'success': False,
                    'error': str(e)
                }), 500
        
        @self.app.route('/api/logs', methods=['GET'])
        def get_logs():
            """Get recent log entries"""
            try:
                # Get query parameters
                lines = request.args.get('lines', 100, type=int)
                
                # Read log file
                log_file = 'logs/epic_monitor.log'
                try:
                    with open(log_file, 'r') as f:
                        log_lines = f.readlines()
                    
                    # Return last N lines
                    recent_logs = log_lines[-lines:] if len(log_lines) > lines else log_lines
                    
                    return jsonify({
                        'success': True,
                        'logs': [line.strip() for line in recent_logs],
                        'total_lines': len(log_lines)
                    })
                    
                except FileNotFoundError:
                    return jsonify({
                        'success': True,
                        'logs': [],
                        'message': 'Log file not found'
                    })
                    
            except Exception as e:
                return jsonify({
                    'success': False,
                    'error': str(e)
                }), 500
        
        @self.app.route('/api/health', methods=['GET'])
        def health_check():
            """Health check endpoint"""
            return jsonify({
                'status': 'healthy',
                'timestamp': datetime.now().isoformat(),
                'monitor_running': self.monitor.is_running if self.monitor else False
            })
        
        @self.app.route('/', methods=['GET'])
        def index():
            """API documentation"""
            return jsonify({
                'name': 'EPIC Change Monitor API',
                'version': '1.0.0',
                'endpoints': {
                    'GET /api/status': 'Get monitoring status',
                    'POST /api/start': 'Start monitoring service',
                    'POST /api/stop': 'Stop monitoring service',
                    'GET /api/epics': 'List monitored EPICs',
                    'POST /api/epics/<epic_id>': 'Add EPIC to monitoring',
                    'DELETE /api/epics/<epic_id>': 'Remove EPIC from monitoring',
                    'POST /api/check': 'Force check for changes',
                    'GET /api/config': 'Get configuration',
                    'PUT /api/config': 'Update configuration',
                    'GET /api/logs': 'Get recent log entries',
                    'GET /api/health': 'Health check'
                },
                'monitor_status': self.monitor.is_running if self.monitor else False
            })
    
    def run(self, host='127.0.0.1', port=5000, debug=False):
        """Run the API server"""
        self.app.run(host=host, port=port, debug=debug)


def main():
    """Main entry point for the API server"""
    import argparse
    
    parser = argparse.ArgumentParser(description='EPIC Change Monitor API Server')
    parser.add_argument('--config', default='monitor_config.json', help='Configuration file')
    parser.add_argument('--host', default='127.0.0.1', help='API server host')
    parser.add_argument('--port', type=int, default=5000, help='API server port')
    parser.add_argument('--debug', action='store_true', help='Enable debug mode')
    parser.add_argument('--create-config', action='store_true', help='Create default config file')
    
    args = parser.parse_args()
    
    if args.create_config:
        create_default_config(args.config)
        return
    
    # Load configuration
    try:
        config = load_config_from_file(args.config)
    except:
        print(f"Failed to load config from {args.config}, creating default...")
        config = create_default_config(args.config)
    
    # Start API server
    api = MonitorAPI(config)
    print(f"Starting EPIC Change Monitor API on {args.host}:{args.port}")
    print(f"Configuration: {args.config}")
    print(f"Monitoring {len(config.epic_ids or [])} EPICs")
    print(f"API Documentation: http://{args.host}:{args.port}/")
    
    try:
        api.run(host=args.host, port=args.port, debug=args.debug)
    except KeyboardInterrupt:
        print("\nShutting down API server...")
        if api.monitor:
            api.monitor.stop()


if __name__ == '__main__':
    main()
