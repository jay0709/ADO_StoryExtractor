import base64
import json
import hashlib
from typing import List, Optional, Dict, Any
from datetime import datetime
import requests
from azure.devops.connection import Connection
from azure.devops.v7_1.work_item_tracking import WorkItemTrackingClient
from msrest.authentication import BasicAuthentication

from config.settings import Settings
from src.models import Requirement, ExistingUserStory, RequirementSnapshot

class ADOClient:
    """Client for interacting with Azure DevOps APIs"""
    
    def __init__(self):
        Settings.validate()
        self.organization = Settings.ADO_ORGANIZATION
        self.project = Settings.ADO_PROJECT
        self.pat = Settings.ADO_PAT
        self.base_url = Settings.ADO_BASE_URL
        
        # Create connection
        credentials = BasicAuthentication('', self.pat)
        self.connection = Connection(
            base_url=f"{self.base_url}/{self.organization}",
            creds=credentials
        )
        
        # Get work item tracking client
        self.wit_client: WorkItemTrackingClient = self.connection.clients.get_work_item_tracking_client()

    def _parse_requirement_id(self, requirement_id: str) -> int:
        """Parse numeric ID from string requirement ID"""
        import re
        numeric_match = re.search(r'\d+', str(requirement_id))
        if numeric_match:
            return int(numeric_match.group())
        else:
            raise ValueError(f"Could not extract numeric ID from '{requirement_id}'")
    
    def get_requirements(self, state_filter: Optional[str] = None) -> List[Requirement]:
        """Get all requirements from the project"""
        try:
            # Build WIQL query
            wiql_query = f"""
            SELECT [System.Id], [System.Title], [System.Description], [System.State]
            FROM WorkItems
            WHERE [System.WorkItemType] = '{Settings.REQUIREMENT_TYPE}'
            AND [System.TeamProject] = '{self.project}'
            """
            
            if state_filter:
                wiql_query += f" AND [System.State] = '{state_filter}'"
            
            # Execute query
            wiql_result = self.wit_client.query_by_wiql({"query": wiql_query})
            
            if not wiql_result.work_items:
                return []
            
            # Get work item IDs
            work_item_ids = [item.id for item in wiql_result.work_items]
            
            # Get full work items
            work_items = self.wit_client.get_work_items(
                ids=work_item_ids,
                fields=["System.Id", "System.Title", "System.Description", "System.State"]
            )
            
            requirements = []
            for item in work_items:
                fields = item.fields
                requirement = Requirement(
                    id=item.id,
                    title=fields.get("System.Title", ""),
                    description=fields.get("System.Description", ""),
                    state=fields.get("System.State", ""),
                    url=item.url
                )
                requirements.append(requirement)
            
            return requirements
            
        except Exception as e:
            raise Exception(f"Failed to get requirements: {str(e)}")
    
    def get_requirement_by_id(self, requirement_id: str) -> Optional[Requirement]:
        """Get a specific requirement by ID (can be int or string)"""
        try:
            numeric_id = self._parse_requirement_id(requirement_id)
            work_item = self.wit_client.get_work_item(
                id=numeric_id,
                fields=["System.Id", "System.Title", "System.Description", "System.State"]
            )
            
            if not work_item:
                return None
            
            fields = work_item.fields
            return Requirement(
                id=work_item.id,
                title=fields.get("System.Title", ""),
                description=fields.get("System.Description", ""),
                state=fields.get("System.State", ""),
                url=work_item.url
            )
            
        except Exception as e:
            raise Exception(f"Failed to get requirement {requirement_id}: {str(e)}")
    
    def create_user_story(self, story_data: Dict[str, Any], parent_requirement_id: int) -> int:
        """Create a user story and link it to a parent requirement"""
        try:
            # Prepare work item data
            document = []
            
            # Add fields
            for field, value in story_data.items():
                document.append({
                    "op": "add",
                    "path": f"/fields/{field}",
                    "value": value
                })
            
            # Set work item type
            document.append({
                "op": "add", 
                "path": "/fields/System.WorkItemType",
                "value": Settings.USER_STORY_TYPE
            })
            
            # Create the work item
            work_item = self.wit_client.create_work_item(
                document=document,
                project=self.project,
                type=Settings.USER_STORY_TYPE
            )
            
            # Create parent-child relationship
            if parent_requirement_id:
                self._create_parent_child_link(parent_requirement_id, work_item.id)
            
            return work_item.id
            
        except Exception as e:
            raise Exception(f"Failed to create user story: {str(e)}")
    
    def _create_parent_child_link(self, parent_id: int, child_id: int):
        """Create a parent-child relationship between work items"""
        try:
            # Create the link
            document = [{
                "op": "add",
                "path": "/relations/-",
                "value": {
                    "rel": "System.LinkTypes.Hierarchy-Forward",
                    "url": f"{self.base_url}/{self.organization}/_apis/wit/workItems/{child_id}"
                }
            }]
            
            self.wit_client.update_work_item(
                document=document,
                id=parent_id
            )
            
        except Exception as e:
            raise Exception(f"Failed to create parent-child link: {str(e)}")
    
    def detect_changes_in_epic(self, epic_id: int) -> Optional[RequirementSnapshot]:
        """Detect changes in an EPIC based on its requirement snapshot"""
        try:
            work_item = self.wit_client.get_work_item(
                id=epic_id,
                fields=["System.Id", "System.Title", "System.Description", "System.State", "System.ChangedDate"]
            )
            
            fields = work_item.fields
            
            # Calculate a hash of the title and description for change detection
            content_hash = hashlib.sha256((fields["System.Title"] + fields["System.Description"]).encode()).hexdigest()
            
            return RequirementSnapshot(
                id=work_item.id,
                title=fields["System.Title"],
                description=fields["System.Description"],
                state=fields["System.State"],
                last_modified=datetime.strptime(fields["System.ChangedDate"], "%Y-%m-%dT%H:%M:%S.%fZ"),
                content_hash=content_hash
            )
            
        except Exception as e:
            raise Exception(f"Failed to detect changes in EPIC {epic_id}: {str(e)}")

    def get_existing_user_stories(self, epic_id: int) -> List[ExistingUserStory]:
        """Retrieve existing user stories for a given epic ID"""
        try:
            child_ids = self.get_child_stories(epic_id)
            stories = []
            if child_ids:
                work_items = self.wit_client.get_work_items(
                    ids=child_ids,
                    fields=["System.Id", "System.Title", "System.Description", "System.State"]
                )
                for item in work_items:
                    fields = item.fields
                    story = ExistingUserStory(
                        id=item.id,
                        title=fields.get("System.Title", ""),
                        description=fields.get("System.Description", ""),
                        state=fields.get("System.State", ""),
                        parent_id=epic_id
                    )
                    stories.append(story)
            return stories
        except Exception as e:
            raise Exception(f"Failed to retrieve existing user stories for epic {epic_id}: {str(e)}")

    def get_child_stories(self, requirement_id: int) -> List[int]:
        """Get all child user stories for a requirement"""
        try:
            work_item = self.wit_client.get_work_item(
                id=requirement_id,
                expand="Relations"
            )
            
            child_ids = []
            if work_item.relations:
                for relation in work_item.relations:
                    if relation.rel == "System.LinkTypes.Hierarchy-Forward":
                        # Extract work item ID from URL
                        url_parts = relation.url.split('/')
                        child_id = int(url_parts[-1])
                        child_ids.append(child_id)
            
            return child_ids
            
        except Exception as e:
            raise Exception(f"Failed to get child stories: {str(e)}")
    
    def update_work_item(self, work_item_id: int, update_data: Dict[str, Any]) -> bool:
        """Update an existing work item"""
        try:
            # Prepare update document
            document = []
            for field, value in update_data.items():
                document.append({
                    "op": "replace",
                    "path": f"/fields/{field}",
                    "value": value
                })
            
            # Update the work item
            self.wit_client.update_work_item(
                document=document,
                id=work_item_id
            )
            
            return True
            
        except Exception as e:
            raise Exception(f"Failed to update work item {work_item_id}: {str(e)}")
    
    def get_work_item_types(self) -> List[str]:
        """Get all available work item types in the project"""
        try:
            work_item_types = self.wit_client.get_work_item_types(project=self.project)
            return [wit.name for wit in work_item_types]
        except Exception as e:
            raise Exception(f"Failed to get work item types: {str(e)}")
