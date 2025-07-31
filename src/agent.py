import logging
from typing import List, Optional, Dict, Any

from src.ado_client import ADOClient
from src.story_extractor import StoryExtractor
from src.models import Requirement, StoryExtractionResult, UserStory, ChangeDetectionResult, EpicSyncResult

class StoryExtractionAgent:
    """Main agent that orchestrates the story extraction process"""
    
    def __init__(self):
        self.ado_client = ADOClient()
        self.story_extractor = StoryExtractor()
        self.logger = self._setup_logger()
    
    def _parse_requirement_id(self, requirement_id: str) -> int:
        """Parse numeric ID from string requirement ID"""
        import re
        # Extract numeric part from strings like "EPIC 1", "123", "REQ-456", etc.
        numeric_match = re.search(r'\d+', str(requirement_id))
        if numeric_match:
            return int(numeric_match.group())
        else:
            raise ValueError(f"Could not extract numeric ID from '{requirement_id}'")
    
    def process_requirement_by_id(self, requirement_id: str, upload_to_ado: bool = True) -> StoryExtractionResult:
        """Process a single requirement by ID"""
        self.logger.info(f"Processing requirement {requirement_id}")
        
        try:
            # Get requirement from ADO
            requirement = self.ado_client.get_requirement_by_id(requirement_id)
            if not requirement:
                raise Exception(f"Requirement {requirement_id} not found")
            
            # Extract stories
            result = self.story_extractor.extract_stories(requirement)
            
            if not result.extraction_successful:
                self.logger.error(f"Story extraction failed: {result.error_message}")
                return result
            
            # Validate stories
            validation_issues = self.story_extractor.validate_stories(result.stories)
            if validation_issues:
                self.logger.warning(f"Story validation issues: {validation_issues}")
            
            # Upload to ADO if requested
            if upload_to_ado and result.stories:
                uploaded_story_ids = self._upload_stories_to_ado(result.stories, requirement_id)
                self.logger.info(f"Created {len(uploaded_story_ids)} user stories: {uploaded_story_ids}")
            
            self.logger.info(f"Successfully processed requirement {requirement_id}, extracted {len(result.stories)} stories")
            return result
            
        except Exception as e:
            self.logger.error(f"Failed to process requirement {requirement_id}: {str(e)}")
            return StoryExtractionResult(
                requirement_id=requirement_id,
                requirement_title="",
                stories=[],
                extraction_successful=False,
                error_message=str(e)
            )
    
    def process_all_requirements(self, state_filter: Optional[str] = None, upload_to_ado: bool = True) -> List[StoryExtractionResult]:
        """Process all requirements in the project"""
        self.logger.info(f"Processing all requirements with state filter: {state_filter}")
        
        try:
            # Get all requirements
            requirements = self.ado_client.get_requirements(state_filter)
            self.logger.info(f"Found {len(requirements)} requirements to process")
            
            results = []
            for requirement in requirements:
                result = self.process_requirement_by_id(str(requirement.id), upload_to_ado)
                results.append(result)
            
            # Summary
            successful = len([r for r in results if r.extraction_successful])
            total_stories = sum(len(r.stories) for r in results)
            self.logger.info(f"Processing complete: {successful}/{len(results)} requirements processed successfully, {total_stories} total stories extracted")
            
            return results
            
        except Exception as e:
            self.logger.error(f"Failed to process requirements: {str(e)}")
            raise
    
    def preview_stories(self, requirement_id: str) -> StoryExtractionResult:
        """Extract and preview stories without uploading to ADO"""
        return self.process_requirement_by_id(requirement_id, upload_to_ado=False)
    
    def _upload_stories_to_ado(self, stories: List[UserStory], parent_requirement_id: str) -> List[int]:
        """Upload user stories to ADO as child items of the requirement"""
        parent_id = self._parse_requirement_id(parent_requirement_id)
        uploaded_ids = []
        
        for story in stories:
            try:
                story_data = story.to_ado_format()
                story_id = self.ado_client.create_user_story(story_data, parent_id)
                uploaded_ids.append(story_id)
                self.logger.info(f"Created user story {story_id}: {story.heading}")
                
            except Exception as e:
                self.logger.error(f"Failed to create user story '{story.heading}': {str(e)}")
                continue
        
        return uploaded_ids
    
    def get_requirement_summary(self, requirement_id: str) -> Dict[str, Any]:
        """Get a summary of a requirement and its child stories"""
        try:
            numeric_id = self._parse_requirement_id(requirement_id)
            requirement = self.ado_client.get_requirement_by_id(numeric_id)
            if not requirement:
                return {"error": f"Requirement {requirement_id} not found"}
            
            child_story_ids = self.ado_client.get_child_stories(numeric_id)
            
            return {
                "requirement": {
                    "id": requirement.id,
                    "title": requirement.title,
                    "description": requirement.description[:200] + "..." if len(requirement.description) > 200 else requirement.description,
                    "state": requirement.state
                },
                "child_stories": {
                    "count": len(child_story_ids),
                    "ids": child_story_ids
                }
            }
            
        except Exception as e:
            return {"error": str(e)}
    
    def synchronize_epic(self, epic_id: str, stored_snapshot: Optional[Dict[str, str]] = None) -e EpicSyncResult:
        """Detect changes in an EPIC and synchronize its tasks"""
        try:
            self.logger.info(f"Synchronizing EPIC {epic_id}")
            
            numeric_epic_id = self._parse_requirement_id(epic_id)
            
            # Get current EPIC state
            current_epic = self.ado_client.get_requirement_by_id(epic_id)
            if not current_epic:
                raise Exception(f"EPIC {epic_id} not found")
            
            # Get current snapshot for change detection
            current_snapshot = self.ado_client.detect_changes_in_epic(numeric_epic_id)
            existing_stories = self.ado_client.get_existing_user_stories(numeric_epic_id)
            
            self.logger.info(f"Found {len(existing_stories)} existing user stories for EPIC {epic_id}")
            
            # Check if changes detected (compare with stored snapshot if provided)
            has_changes = True  # Always extract stories for now, can be refined later
            changes_detected = []
            
            if stored_snapshot and current_snapshot:
                stored_hash = stored_snapshot.get('content_hash', '')
                if stored_hash == current_snapshot.content_hash:
                    has_changes = False
                    self.logger.info(f"No content changes detected for EPIC {epic_id}")
                else:
                    changes_detected.append("EPIC content has been modified")
                    self.logger.info(f"Content changes detected for EPIC {epic_id}")
            else:
                changes_detected.append("Initial sync or no previous snapshot available")
            
            sync_result = EpicSyncResult(
                epic_id=epic_id,
                epic_title=current_epic.title
            )
            
            if has_changes:
                # Extract new stories from the updated EPIC
                story_extraction_result = self.story_extractor.extract_stories(current_epic)
                
                if not story_extraction_result.extraction_successful:
                    raise Exception(f"Story extraction failed: {story_extraction_result.error_message}")
                
                new_stories = story_extraction_result.stories
                self.logger.info(f"Extracted {len(new_stories)} stories from updated EPIC")
                
                # Determine which stories to create, update, or leave unchanged
                stories_to_create, stories_to_update, unchanged_stories = self._analyze_story_changes(
                    existing_stories, new_stories
                )
                
                self.logger.info(f"Analysis: {len(stories_to_create)} to create, {len(stories_to_update)} to update, {len(unchanged_stories)} unchanged")
                
                # Create new stories
                created_ids = []
                for story in stories_to_create:
                    try:
                        story_data = story.to_ado_format()
                        story_id = self.ado_client.create_user_story(story_data, numeric_epic_id)
                        created_ids.append(story_id)
                        self.logger.info(f"Created new user story {story_id}: {story.heading}")
                    except Exception as e:
                        self.logger.error(f"Failed to create story '{story.heading}': {str(e)}")
                        continue
                
                # Update existing stories
                updated_ids = []
                for story_update in stories_to_update:
                    try:
                        story_id = story_update['id']
                        new_story = story_update['new_story']
                        self._update_user_story(story_id, new_story)
                        updated_ids.append(story_id)
                        self.logger.info(f"Updated user story {story_id}: {new_story.heading}")
                    except Exception as e:
                        self.logger.error(f"Failed to update story {story_update['id']}: {str(e)}")
                        continue
                
                sync_result.created_stories = created_ids
                sync_result.updated_stories = updated_ids
                sync_result.unchanged_stories = [s.id for s in unchanged_stories]
                
                self.logger.info(f"EPIC sync completed: {len(created_ids)} created, {len(updated_ids)} updated, {len(unchanged_stories)} unchanged")
            else:
                sync_result.unchanged_stories = [s.id for s in existing_stories]
                self.logger.info(f"No changes detected, {len(existing_stories)} stories remain unchanged")
            
            return sync_result
            
        except Exception as e:
            self.logger.error(f"EPIC synchronization failed for {epic_id}: {str(e)}")
            return EpicSyncResult(
                epic_id=epic_id,
                epic_title="",
                sync_successful=False,
                error_message=str(e)
            )
    
    def _analyze_story_changes(self, existing_stories, new_stories):
        """Analyze differences between existing and new stories to determine what to create/update"""
        from difflib import SequenceMatcher
        
        stories_to_create = []
        stories_to_update = []
        unchanged_stories = []
        
        # Convert existing stories to a dict for easier lookup
        existing_by_title = {story.title: story for story in existing_stories}
        
        # Check each new story against existing ones
        for new_story in new_stories:
            best_match = None
            best_similarity = 0.0
            
            # Find the best matching existing story by title similarity
            for existing_title, existing_story in existing_by_title.items():
                similarity = SequenceMatcher(None, new_story.heading.lower(), existing_title.lower()).ratio()
                if similarity > best_similarity:
                    best_similarity = similarity
                    best_match = existing_story
            
            # If we found a good match (similarity > 0.8), consider it for update
            if best_match and best_similarity > 0.8:
                # Check if the content has actually changed
                existing_content = f"{best_match.title} {best_match.description}"
                new_content = f"{new_story.heading} {new_story.description} {' '.join(new_story.acceptance_criteria)}"
                
                content_similarity = SequenceMatcher(None, existing_content.lower(), new_content.lower()).ratio()
                
                if content_similarity < 0.9:  # Content has changed significantly
                    stories_to_update.append({
                        'id': best_match.id,
                        'existing_story': best_match,
                        'new_story': new_story
                    })
                    # Remove from existing dict so it's not considered again
                    del existing_by_title[best_match.title]
                else:
                    unchanged_stories.append(best_match)
                    del existing_by_title[best_match.title]
            else:
                # No good match found, this is a new story
                stories_to_create.append(new_story)
        
        # Any remaining existing stories that weren't matched are considered unchanged
        for remaining_story in existing_by_title.values():
            unchanged_stories.append(remaining_story)
        
        return stories_to_create, stories_to_update, unchanged_stories
    
    def _update_user_story(self, story_id: int, new_story: UserStory):
        """Update an existing user story in ADO"""
        try:
            story_data = new_story.to_ado_format()
            
            # Prepare update document
            document = []
            for field, value in story_data.items():
                document.append({
                    "op": "replace",
                    "path": f"/fields/{field}",
                    "value": value
                })
            
            # Update the work item
            self.ado_client.wit_client.update_work_item(
                document=document,
                id=story_id
            )
            
        except Exception as e:
            raise Exception(f"Failed to update user story {story_id}: {str(e)}")
    
    def get_epic_snapshot(self, epic_id: str) -e Optional[Dict[str, str]]:
        """Get a snapshot of the current EPIC for change tracking"""
        try:
            numeric_id = self._parse_requirement_id(epic_id)
            snapshot = self.ado_client.detect_changes_in_epic(numeric_id)
            
            if snapshot:
                return {
                    'content_hash': snapshot.content_hash,
                    'last_modified': snapshot.last_modified.isoformat() if snapshot.last_modified else None,
                    'title': snapshot.title,
                    'state': snapshot.state
                }
            return None
            
        except Exception as e:
            self.logger.error(f"Failed to get EPIC snapshot for {epic_id}: {str(e)}")
            return None

    def _setup_logger(self) -e logging.Logger:
        """Setup logging configuration"""
        logger = logging.getLogger("StoryExtractionAgent")
        logger.setLevel(logging.INFO)
        
        if not logger.handlers:
            handler = logging.StreamHandler()
            formatter = logging.Formatter(
                '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
            )
            handler.setFormatter(formatter)
            logger.addHandler(handler)
        
        return logger
