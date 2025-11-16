#!/usr/bin/env python3
"""
OpenAI Status Page Tracker

Monitors the OpenAI Status Page for new incidents, outages, and service updates
using efficient conditional HTTP requests with ETag support.
"""

import requests
import json
import time
import signal
import sys
from datetime import datetime
from typing import Dict, Set, Optional, List


class StatusTracker:
    """Tracks and monitors OpenAI Status Page for service updates."""
    
    def __init__(self, poll_interval: int = 60):
        """
        Initialize the StatusTracker.
        
        Args:
            poll_interval: Time in seconds between API checks (default: 60)
        """
        self.poll_interval = poll_interval
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'OpenAI-Status-Tracker/1.0'
        })
        
        # API endpoints
        self.incidents_url = "https://status.openai.com/api/v2/incidents.json"
        self.components_url = "https://status.openai.com/api/v2/components.json"
        
        # State tracking
        self.etag_incidents: Optional[str] = None
        self.etag_components: Optional[str] = None
        self.seen_incident_ids: Set[str] = set()
        self.incident_states: Dict[str, Dict] = {}  # Track incident status changes
        self.component_states: Dict[str, Dict] = {}  # Track component status
        
        # Graceful shutdown flag
        self.running = True
        
    def _make_conditional_request(self, url: str, etag: Optional[str] = None) -> tuple:
        """
        Make a conditional HTTP request using ETag.
        
        Args:
            url: The API endpoint URL
            etag: Previous ETag value for conditional request
            
        Returns:
            Tuple of (response_data, new_etag, status_code)
            Returns (None, etag, 304) if not modified
        """
        headers = {}
        if etag:
            headers['If-None-Match'] = etag
            
        try:
            response = self.session.get(url, headers=headers, timeout=10)
            
            if response.status_code == 304:
                # Not modified - no changes
                return None, etag, 304
            elif response.status_code == 200:
                # Content has changed
                new_etag = response.headers.get('ETag', '').strip('"')
                data = response.json()
                return data, new_etag, 200
            else:
                print(f"Warning: Unexpected status code {response.status_code} for {url}")
                return None, etag, response.status_code
                
        except requests.exceptions.RequestException as e:
            print(f"Error fetching {url}: {e}")
            return None, etag, None
    
    def _fetch_incidents(self) -> Optional[Dict]:
        """Fetch incidents from the API with conditional request."""
        data, new_etag, status = self._make_conditional_request(
            self.incidents_url, 
            self.etag_incidents
        )
        
        if status == 200:
            # Update ETag if available, but still return data even without ETag
            if new_etag:
                self.etag_incidents = new_etag
            return data
        elif status == 304:
            # No changes
            return None
        else:
            return None
    
    def _fetch_components(self) -> Optional[Dict]:
        """Fetch components from the API with conditional request."""
        data, new_etag, status = self._make_conditional_request(
            self.components_url,
            self.etag_components
        )
        
        if status == 200:
            # Update ETag if available, but still return data even without ETag
            if new_etag:
                self.etag_components = new_etag
            return data
        elif status == 304:
            # No changes
            return None
        else:
            return None
    
    def _get_component_name(self, component_id: str, components_data: Dict) -> str:
        """Get component name by ID from components data."""
        if not components_data or 'components' not in components_data:
            return component_id
            
        for component in components_data['components']:
            if component.get('id') == component_id:
                return component.get('name', component_id)
        return component_id
    
    def _format_timestamp(self, timestamp: str) -> str:
        """Format ISO timestamp to readable format."""
        try:
            dt = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
            return dt.strftime('%Y-%m-%d %H:%M:%S')
        except:
            return timestamp
    
    def _print_incident_update(self, incident: Dict, components_data: Optional[Dict] = None):
        """
        Print formatted incident update to console.
        
        Args:
            incident: Incident data from API
            components_data: Optional components data for name resolution
        """
        updated_at = incident.get('updated_at', '')
        
        # Get affected components
        affected_components = incident.get('components', [])
        component_names = []
        for comp in affected_components:
            comp_id = comp.get('id') if isinstance(comp, dict) else comp
            comp_name = self._get_component_name(comp_id, components_data) if components_data else comp_id
            component_names.append(comp_name)
        
        # Get latest incident update
        incident_updates = incident.get('incident_updates', [])
        latest_message = "No status message available"
        if incident_updates:
            latest_update = incident_updates[0]  # Most recent is first
            latest_message = latest_update.get('body', latest_message)
        
        # Format timestamp
        timestamp = self._format_timestamp(updated_at) if updated_at else datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        
        # Format product names
        if component_names:
            product_str = ', '.join(component_names)
        else:
            product_str = "OpenAI Services"
        
        # Print simplified output
        print(f"[{timestamp}] Product: {product_str}")
        print(f"Status: {latest_message}")
        print()  # Empty line for readability
    
    def _print_status_change(self, incident: Dict, old_status: str, components_data: Optional[Dict] = None):
        """Print formatted status change update."""
        updated_at = incident.get('updated_at', '')
        
        # Get affected components
        affected_components = incident.get('components', [])
        component_names = []
        for comp in affected_components:
            comp_id = comp.get('id') if isinstance(comp, dict) else comp
            comp_name = self._get_component_name(comp_id, components_data) if components_data else comp_id
            component_names.append(comp_name)
        
        # Get latest update message
        incident_updates = incident.get('incident_updates', [])
        latest_message = "No status message available"
        if incident_updates:
            latest_update = incident_updates[0]
            latest_message = latest_update.get('body', latest_message)
        
        # Format timestamp
        timestamp = self._format_timestamp(updated_at) if updated_at else datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        
        # Format product names
        if component_names:
            product_str = ', '.join(component_names)
        else:
            product_str = "OpenAI Services"
        
        # Print simplified output
        print(f"[{timestamp}] Product: {product_str}")
        print(f"Status: {latest_message}")
        print()  # Empty line for readability
    
    def _process_incidents(self, incidents_data: Dict, components_data: Optional[Dict] = None):
        """
        Process incidents data and detect new incidents or status changes.
        
        Args:
            incidents_data: Incidents data from API
            components_data: Optional components data for name resolution
        """
        if not incidents_data or 'incidents' not in incidents_data:
            return
        
        incidents = incidents_data['incidents']
        
        for incident in incidents:
            incident_id = incident.get('id')
            if not incident_id:
                continue
            
            current_status = incident.get('status', 'unknown')
            
            # Check if this is a new incident
            if incident_id not in self.seen_incident_ids:
                self.seen_incident_ids.add(incident_id)
                self.incident_states[incident_id] = {
                    'status': current_status,
                    'last_updated': incident.get('updated_at', '')
                }
                self._print_incident_update(incident, components_data)
            
            # Check if status has changed
            elif incident_id in self.incident_states:
                old_status = self.incident_states[incident_id].get('status')
                if old_status and old_status != current_status:
                    self.incident_states[incident_id]['status'] = current_status
                    self.incident_states[incident_id]['last_updated'] = incident.get('updated_at', '')
                    self._print_status_change(incident, old_status, components_data)
    
    def _signal_handler(self, signum, frame):
        """Handle interrupt signals for graceful shutdown."""
        print("\n\nShutting down gracefully...")
        self.running = False
    
    def start(self):
        """Start monitoring the status page."""
        # Set up signal handlers for graceful shutdown
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)
        
        print("OpenAI Status Page Tracker")
        print("=" * 70)
        print(f"Monitoring: {self.incidents_url}")
        print(f"Poll interval: {self.poll_interval} seconds")
        print("Press Ctrl+C to stop")
        print("=" * 70 + "\n")
        
        # Initial fetch to populate state
        print("Fetching initial status...")
        incidents_data = self._fetch_incidents()
        components_data = self._fetch_components()
        
        if incidents_data:
            # Mark all existing incidents as seen (don't print them on startup)
            if 'incidents' in incidents_data:
                for incident in incidents_data['incidents']:
                    incident_id = incident.get('id')
                    if incident_id:
                        self.seen_incident_ids.add(incident_id)
                        self.incident_states[incident_id] = {
                            'status': incident.get('status', 'unknown'),
                            'last_updated': incident.get('updated_at', '')
                        }
            print(f"Initialized: Found {len(self.seen_incident_ids)} existing incident(s)")
        else:
            print("Initialized: No incidents found")
        
        print(f"Monitoring for new updates (checking every {self.poll_interval} seconds)...\n")
        
        # Main monitoring loop
        check_count = 0
        while self.running:
            try:
                check_count += 1
                current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                print(f"[{current_time}] Checking for updates... (check #{check_count})", end='\r')
                
                # Fetch incidents with conditional request
                incidents_data = self._fetch_incidents()
                
                # Fetch components (less frequently, but needed for name resolution)
                if incidents_data:  # Only fetch components if incidents changed
                    components_data = self._fetch_components()
                    print()  # New line when changes detected
                else:
                    components_data = None
                
                # Process incidents if data changed
                if incidents_data:
                    self._process_incidents(incidents_data, components_data)
                
                # Wait before next check
                if self.running:
                    time.sleep(self.poll_interval)
                    
            except KeyboardInterrupt:
                self._signal_handler(signal.SIGINT, None)
                break
            except Exception as e:
                print(f"\nError in monitoring loop: {e}")
                if self.running:
                    time.sleep(self.poll_interval)
        
        print("\nTracker stopped.")


def main():
    """Main entry point."""
    # Default poll interval: 60 seconds
    poll_interval = 60
    
    # Allow override via command line argument
    if len(sys.argv) > 1:
        try:
            poll_interval = int(sys.argv[1])
            if poll_interval < 10:
                print("Warning: Poll interval too short, using minimum of 10 seconds")
                poll_interval = 10
        except ValueError:
            print(f"Invalid poll interval '{sys.argv[1]}', using default 60 seconds")
    
    tracker = StatusTracker(poll_interval=poll_interval)
    tracker.start()


if __name__ == "__main__":
    main()

