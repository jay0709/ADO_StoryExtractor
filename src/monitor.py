#!/usr/bin/env python3
"""
Background monitoring service for EPIC change detection and automatic synchronization.
"""

import asyncio
import json
import logging
import os
import signal
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Set
from dataclasses import dataclass, asdict
from concurrent.futures import ThreadPoolExecutor

from src.agent import StoryExtractionAgent
from src.models import EpicSyncResult, RequirementSnapshot
from config.settings import Settings


@dataclass
class MonitorConfig:
    """Configuration for the EPIC monitor"""
    poll_interval_seconds: int = 300  # 5 minutes default
    max_concurrent_syncs: int = 3
    snapshot_directory: str = "snapshots"
    log_level: str = "INFO"
    epic_ids: List[str] = None
    auto_sync: bool = True
    notification_webhook: Optional[str] = None
    retry_attempts: int = 3
    retry_delay_seconds: int = 60


@dataclass
class EpicMonitorState:
    """State tracking for a monitored EPIC"""
    epic_id: str
    last_check: datetime
    last_snapshot: Optional[Dict] = None
    consecutive_errors: int = 0
    last_sync_result: Optional[Dict] = None


class EpicChangeMonitor:
    """Background service that monitors EPICs for changes and triggers synchronization"""
    
    def __init__(self, config: MonitorConfig):
        self.config = config
        self.agent = StoryExtractionAgent()
        self.logger = self._setup_logger()
        self.is_running = False
        self.monitored_epics: Dict[str, EpicMonitorState] = {}
        self.executor = ThreadPoolExecutor(max_workers=config.max_concurrent_syncs)
        
        # Ensure snapshot directory exists
        self.snapshot_dir = Path(config.snapshot_directory)
        self.snapshot_dir.mkdir(exist_ok=True)
        
        # Load existing snapshots
        self._load_existing_snapshots()
    
    def _setup_logger(self) -> logging.Logger:
        """Setup logging for the monitor"""
        logger = logging.getLogger("EpicChangeMonitor")
        logger.setLevel(getattr(logging, self.config.log_level.upper()))
        
        if not logger.handlers:
            # Console handler
            console_handler = logging.StreamHandler()
            console_formatter = logging.Formatter(
                '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
            )
            console_handler.setFormatter(console_formatter)
            logger.addHandler(console_handler)
            
            # File handler
            log_file = Path("logs") / "epic_monitor.log"
            log_file.parent.mkdir(exist_ok=True)
            file_handler = logging.FileHandler(log_file)
            file_handler.setFormatter(console_formatter)
            logger.addHandler(file_handler)
        
        return logger
    
    def _load_existing_snapshots(self):
        """Load existing snapshots for monitored EPICs"""
        for epic_id in self.config.epic_ids or []:
            snapshot_file = self.snapshot_dir / f"epic_{epic_id}.json"
            if snapshot_file.exists():
                try:
                    with open(snapshot_file, 'r') as f:
                        snapshot_data = json.load(f)
                    
                    self.monitored_epics[epic_id] = EpicMonitorState(
                        epic_id=epic_id,
                        last_check=datetime.now(),
                        last_snapshot=snapshot_data
                    )
                    self.logger.info(f"Loaded existing snapshot for EPIC {epic_id}")
                except Exception as e:
                    self.logger.error(f"Failed to load snapshot for EPIC {epic_id}: {e}")
                    self.monitored_epics[epic_id] = EpicMonitorState(
                        epic_id=epic_id,
                        last_check=datetime.now()
                    )
            else:
                self.monitored_epics[epic_id] = EpicMonitorState(
                    epic_id=epic_id,
                    last_check=datetime.now()
                )
    
    def add_epic(self, epic_id: str) -> bool:
        """Add an EPIC to monitoring"""
        try:
            if epic_id not in self.monitored_epics:
                # Get initial snapshot
                initial_snapshot = self.agent.get_epic_snapshot(epic_id)
                if initial_snapshot:
                    self.monitored_epics[epic_id] = EpicMonitorState(
                        epic_id=epic_id,
                        last_check=datetime.now(),
                        last_snapshot=initial_snapshot
                    )
                    self._save_snapshot(epic_id, initial_snapshot)
                    self.logger.info(f"Added EPIC {epic_id} to monitoring")
                    return True
                else:
                    self.logger.error(f"Failed to get initial snapshot for EPIC {epic_id}")
                    return False
            else:
                self.logger.warning(f"EPIC {epic_id} is already being monitored")
                return True
        except Exception as e:
            self.logger.error(f"Failed to add EPIC {epic_id} to monitoring: {e}")
            return False
    
    def remove_epic(self, epic_id: str) -> bool:
        """Remove an EPIC from monitoring"""
        if epic_id in self.monitored_epics:
            del self.monitored_epics[epic_id]
            self.logger.info(f"Removed EPIC {epic_id} from monitoring")
            return True
        return False
    
    def _save_snapshot(self, epic_id: str, snapshot: Dict):
        """Save snapshot to file"""
        try:
            snapshot_file = self.snapshot_dir / f"epic_{epic_id}.json"
            with open(snapshot_file, 'w') as f:
                json.dump(snapshot, f, indent=2)
        except Exception as e:
            self.logger.error(f"Failed to save snapshot for EPIC {epic_id}: {e}")
    
    def _check_epic_changes(self, epic_id: str) -> bool:
        """Check if an EPIC has changes"""
        try:
            epic_state = self.monitored_epics[epic_id]
            current_snapshot = self.agent.get_epic_snapshot(epic_id)
            
            if not current_snapshot:
                self.logger.warning(f"Failed to get current snapshot for EPIC {epic_id}")
                epic_state.consecutive_errors += 1
                return False
            
            # Reset error counter on successful snapshot
            epic_state.consecutive_errors = 0
            
            # Compare with last known snapshot
            if epic_state.last_snapshot:
                last_hash = epic_state.last_snapshot.get('content_hash', '')
                current_hash = current_snapshot.get('content_hash', '')
                
                if last_hash != current_hash:
                    self.logger.info(f"Changes detected in EPIC {epic_id}")
                    self.logger.info(f"  Previous hash: {last_hash[:16]}...")
                    self.logger.info(f"  Current hash:  {current_hash[:16]}...")
                    return True
                else:
                    self.logger.info(f"No changes detected in EPIC {epic_id}")
                    return False
            else:
                # First check, save current snapshot
                self.logger.info(f"Initial snapshot saved for EPIC {epic_id}")
                epic_state.last_snapshot = current_snapshot
                self._save_snapshot(epic_id, current_snapshot)
                return False
                
        except Exception as e:
            self.logger.error(f"Error checking changes for EPIC {epic_id}: {e}")
            self.monitored_epics[epic_id].consecutive_errors += 1
            return False
    
    def _sync_epic(self, epic_id: str) -> EpicSyncResult:
        """Synchronize an EPIC with retry logic"""
        epic_state = self.monitored_epics[epic_id]
        
        for attempt in range(self.config.retry_attempts):
            try:
                self.logger.info(f"Synchronizing EPIC {epic_id} (attempt {attempt + 1})")
                
                result = self.agent.synchronize_epic(
                    epic_id=epic_id,
                    stored_snapshot=epic_state.last_snapshot
                )
                
                if result.sync_successful:
                    # Update snapshot after successful sync
                    new_snapshot = self.agent.get_epic_snapshot(epic_id)
                    if new_snapshot:
                        epic_state.last_snapshot = new_snapshot
                        self._save_snapshot(epic_id, new_snapshot)
                    
                    # Store sync result
                    epic_state.last_sync_result = {
                        'timestamp': datetime.now().isoformat(),
                        'success': True,
                        'created_stories': result.created_stories,
                        'updated_stories': result.updated_stories,
                        'unchanged_stories': result.unchanged_stories
                    }
                    
                    self.logger.info(f"Successfully synchronized EPIC {epic_id}")
                    self.logger.info(f"  Created: {len(result.created_stories)} stories")
                    self.logger.info(f"  Updated: {len(result.updated_stories)} stories")
                    self.logger.info(f"  Unchanged: {len(result.unchanged_stories)} stories")
                    
                    return result
                else:
                    self.logger.error(f"Sync failed for EPIC {epic_id}: {result.error_message}")
                    if attempt < self.config.retry_attempts - 1:
                        self.logger.info(f"Retrying in {self.config.retry_delay_seconds} seconds...")
                        time.sleep(self.config.retry_delay_seconds)
                    
            except Exception as e:
                self.logger.error(f"Exception during sync of EPIC {epic_id}: {e}")
                if attempt < self.config.retry_attempts - 1:
                    self.logger.info(f"Retrying in {self.config.retry_delay_seconds} seconds...")
                    time.sleep(self.config.retry_delay_seconds)
        
        # All attempts failed
        epic_state.last_sync_result = {
            'timestamp': datetime.now().isoformat(),
            'success': False,
            'error': f"Failed after {self.config.retry_attempts} attempts"
        }
        
        return EpicSyncResult(
            epic_id=epic_id,
            epic_title="",
            sync_successful=False,
            error_message=f"Failed after {self.config.retry_attempts} attempts"
        )
    
    async def _monitor_loop(self):
        """Main monitoring loop"""
        self.logger.info("Starting EPIC monitoring loop")
        
        while self.is_running:
            try:
                # Auto-detect new Epics at the start of each cycle
                self.update_monitored_epics()
                # Check each monitored EPIC
                sync_tasks = []
                
                for epic_id in list(self.monitored_epics.keys()):
                    try:
                        epic_state = self.monitored_epics[epic_id]
                        
                        # Skip if too many consecutive errors
                        if epic_state.consecutive_errors >= 5:
                            self.logger.warning(f"Skipping EPIC {epic_id} due to consecutive errors")
                            continue
                        
                        # Check for changes
                        if self._check_epic_changes(epic_id):
                            if self.config.auto_sync:
                                # Schedule sync
                                future = asyncio.get_event_loop().run_in_executor(
                                    self.executor, self._sync_epic, epic_id
                                )
                                sync_tasks.append((epic_id, future))
                            else:
                                self.logger.info(f"Changes detected in EPIC {epic_id}, but auto-sync is disabled")
                        
                        # Update last check time
                        epic_state.last_check = datetime.now()
                        
                    except Exception as e:
                        self.logger.error(f"Error processing EPIC {epic_id}: {e}")
                        import traceback
                        self.logger.error(traceback.format_exc())

                # Wait for sync tasks to complete
                if sync_tasks:
                    self.logger.info(f"Running {len(sync_tasks)} synchronization tasks")
                    for epic_id, future in sync_tasks:
                        try:
                            await future
                        except Exception as e:
                            self.logger.error(f"Sync task failed for EPIC {epic_id}: {e}")
                            import traceback
                            self.logger.error(traceback.format_exc())

                # Wait before next polling cycle
                self.logger.debug(f"Monitoring cycle complete, sleeping for {self.config.poll_interval_seconds} seconds")
                await asyncio.sleep(self.config.poll_interval_seconds)
                
            except Exception as e:
                self.logger.error(f"Error in monitoring loop: {e}")
                import traceback
                self.logger.error(traceback.format_exc())
                await asyncio.sleep(60)  # Wait a minute before retrying
    
    def fetch_all_epic_ids(self) -> List[str]:
        """Fetch all Epic IDs from Azure DevOps."""
        try:
            requirements = self.agent.ado_client.get_requirements()
            return [str(req.id) for req in requirements]
        except Exception as e:
            self.logger.error(f"Failed to fetch all Epics: {e}")
            return []

    def update_monitored_epics(self):
        """Update the monitored Epics set by auto-detecting new Epics."""
        all_epic_ids = set(self.fetch_all_epic_ids())
        current_epic_ids = set(self.monitored_epics.keys())
        new_epics = all_epic_ids - current_epic_ids
        for epic_id in new_epics:
            self.logger.info(f"Auto-detect: Adding new Epic {epic_id} to monitoring.")
            self.add_epic(epic_id)
        # Optionally, remove Epics that no longer exist in ADO
        # removed_epics = current_epic_ids - all_epic_ids
        # for epic_id in removed_epics:
        #     self.logger.info(f"Auto-detect: Removing Epic {epic_id} (no longer exists in ADO).")
        #     self.monitored_epics.pop(epic_id, None)

    def start(self):
        """Start the monitoring service"""
        if self.is_running:
            self.logger.warning("Monitor is already running")
            return
        
        self.is_running = True
        self.logger.info("Starting EPIC Change Monitor")
        self.logger.info(f"Monitoring {len(self.monitored_epics)} EPICs")
        self.logger.info(f"Poll interval: {self.config.poll_interval_seconds} seconds")
        self.logger.info(f"Auto-sync enabled: {self.config.auto_sync}")
        
        # Setup signal handlers for graceful shutdown
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)
        
        # Run the monitoring loop
        try:
            asyncio.run(self._monitor_loop())
        except KeyboardInterrupt:
            self.logger.info("Received interrupt signal")
        finally:
            self.stop()
    
    def stop(self):
        """Stop the monitoring service"""
        if not self.is_running:
            return
        
        self.logger.info("Stopping EPIC Change Monitor")
        self.is_running = False
        self.executor.shutdown(wait=True)
        self.logger.info("EPIC Change Monitor stopped")
    
    def _signal_handler(self, signum, frame):
        """Handle shutdown signals"""
        self.logger.info(f"Received signal {signum}, shutting down gracefully...")
        self.stop()
        sys.exit(0)
    
    def get_status(self) -> Dict:
        """Get current monitoring status"""
        status = {
            'is_running': self.is_running,
            'config': asdict(self.config),
            'monitored_epics': {},
            'last_update': datetime.now().isoformat()
        }
        
        for epic_id, state in self.monitored_epics.items():
            status['monitored_epics'][epic_id] = {
                'last_check': state.last_check.isoformat(),
                'consecutive_errors': state.consecutive_errors,
                'has_snapshot': state.last_snapshot is not None,
                'last_sync_result': state.last_sync_result
            }
        
        return status
    
    def force_check(self, epic_id: Optional[str] = None) -> Dict:
        """Force a check for changes (optionally for specific EPIC)"""
        results = {}
        
        epics_to_check = [epic_id] if epic_id else list(self.monitored_epics.keys())
        
        for eid in epics_to_check:
            if eid in self.monitored_epics:
                try:
                    has_changes = self._check_epic_changes(eid)
                    results[eid] = {
                        'has_changes': has_changes,
                        'check_time': datetime.now().isoformat()
                    }
                    
                    if has_changes and self.config.auto_sync:
                        sync_result = self._sync_epic(eid)
                        results[eid]['sync_result'] = {
                            'success': sync_result.sync_successful,
                            'created_stories': sync_result.created_stories,
                            'updated_stories': sync_result.updated_stories,
                            'error_message': sync_result.error_message
                        }
                except Exception as e:
                    results[eid] = {
                        'error': str(e),
                        'check_time': datetime.now().isoformat()
                    }
        
        return results


def load_config_from_file(config_file: str) -> MonitorConfig:
    """Load monitor configuration from JSON file"""
    try:
        with open(config_file, 'r') as f:
            config_data = json.load(f)
        return MonitorConfig(**config_data)
    except Exception as e:
        logging.error(f"Failed to load config from {config_file}: {e}")
        return MonitorConfig()


def create_default_config(config_file: str = "monitor_config.json"):
    """Create a default configuration file"""
    default_config = MonitorConfig(
        poll_interval_seconds=300,  # 5 minutes
        max_concurrent_syncs=3,
        snapshot_directory="snapshots",
        log_level="INFO",
        epic_ids=["12345", "67890"],  # Example EPIC IDs
        auto_sync=True,
        retry_attempts=3,
        retry_delay_seconds=60
    )
    
    with open(config_file, 'w') as f:
        json.dump(asdict(default_config), f, indent=2)
    
    print(f"Created default configuration file: {config_file}")
    return default_config
