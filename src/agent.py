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
    
    def process_requirement_by_id(self, requirement_id: str, upload_to_ado: bool = True) -> StoryExtractionResult:
        """Process a single requirement by ID or title (string or int)"""
        print(f"\n[AGENT] Starting to process requirement ID: {requirement_id}")
        try:
            # Try to fetch requirement by ID or title (string or int)
            print("[AGENT] Fetching requirement from Azure DevOps...")
            requirement = self.ado_client.get_requirement_by_id(requirement_id)

            if not requirement:
                error_msg = f"Requirement {requirement_id} not found or access denied"
                print(f"[ERROR] {error_msg}")
                return StoryExtractionResult(
                    requirement_id=requirement_id,
                    requirement_title="",
                    stories=[],
                    extraction_successful=False,
                    error_message=error_msg
                )

            print(f"[AGENT] Found requirement: {requirement.title}")

            # Extract stories
            print("[DEBUG] StoryExtractionAgent: Starting story extraction")
            result = self.story_extractor.extract_stories(requirement)
            
            if not result.extraction_successful:
                print(f"[ERROR] StoryExtractionAgent: Story extraction failed: {result.error_message}")
                return result
            
            print(f"[DEBUG] StoryExtractionAgent: Successfully extracted {len(result.stories)} stories")

            # Upload to ADO if requested
            if upload_to_ado and result.stories:
                print("[DEBUG] StoryExtractionAgent: Starting upload to ADO")
                try:
                    uploaded_story_ids = self._upload_stories_to_ado(result.stories, requirement_id)
                    print(f"[DEBUG] StoryExtractionAgent: Successfully uploaded {len(uploaded_story_ids)} stories")
                except Exception as e:
                    print(f"[ERROR] StoryExtractionAgent: Failed to upload stories: {str(e)}")
                    result.error_message = f"Failed to upload stories: {str(e)}"
                    result.extraction_successful = False

        except Exception as e:
            # Accept string-based IDs (e.g., 'EPIC 1')
            ado_id = requirement_id.strip()
            print(f"[AGENT] Using requirement ID: {ado_id}")
            try:
                # Get all requirements
                requirement = self.ado_client.get_requirement_by_id(ado_id)
                self.logger.info(f"Found requirement to process: {ado_id}")
                result = self.process_requirement_by_id(str(requirement.id), upload_to_ado)
                # Summary
                successful = 1 if result.extraction_successful else 0
                total_stories = len(result.stories)
                print(f"[SUMMARY] Processed 1 requirement. Successful: {successful}, Total stories: {total_stories}")
                return [result]
            except Exception as inner_e:
                print(f"[ERROR] Failed to process requirement {ado_id}: {str(inner_e)}")
                return []

    def preview_stories(self, requirement_id: str) -> StoryExtractionResult:
        """Extract and preview stories without uploading to ADO"""
        return self.process_requirement_by_id(requirement_id, upload_to_ado=False)
    
    def _upload_stories_to_ado(self, stories: List[UserStory], parent_requirement_id: str) -> List[int]:
        """Upload user stories to ADO as child items of the requirement"""
        parent_id = parent_requirement_id  # No numeric parsing anymore
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
            numeric_id = requirement_id  # No numeric parsing
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
    
    def synchronize_epic(self, epic_id: str, stored_snapshot: Optional[Dict] = None) -> EpicSyncResult:
        """Detect changes in an EPIC and synchronize its tasks"""
        self.logger.info(f"[AGENT] Synchronizing Epic: {epic_id}")
        try:
            # Fetch the requirement (Epic) from ADO
            requirement = self.ado_client.get_requirement_by_id(epic_id)
            if not requirement:
                error_msg = f"[AGENT] Epic {epic_id} not found or access denied"
                self.logger.error(error_msg)
                return EpicSyncResult(
                    epic_id=epic_id,
                    epic_title="",
                    sync_successful=False,
                    error_message=error_msg
                )
            self.logger.info(f"[AGENT] Fetched Epic: {requirement.title}")
            self.logger.info(f"[AGENT] Epic Description: {requirement.description}")
            # Extract stories
            self.logger.info(f"[AGENT] Extracting stories from Epic {epic_id}")
            extraction_result = self.story_extractor.extract_stories(requirement)
            if not extraction_result.extraction_successful:
                self.logger.error(f"[AGENT] Story extraction failed: {extraction_result.error_message}")
                return EpicSyncResult(
                    epic_id=epic_id,
                    epic_title=requirement.title,
                    sync_successful=False,
                    error_message=extraction_result.error_message
                )
            self.logger.info(f"[AGENT] Extracted {len(extraction_result.stories)} stories from Epic {epic_id}")
            # Upload stories to ADO
            created_stories = []
            updated_stories = []
            unchanged_stories = []
            if extraction_result.stories:
                self.logger.info(f"[AGENT] Uploading {len(extraction_result.stories)} stories to ADO for Epic {epic_id}")
                for story in extraction_result.stories:
                    # TODO: Replace the following with actual upload logic that returns the new story's integer ID
                    # Example: story_id = self.ado_client.create_story(story)
                    story_id = None  # Placeholder for the created story's ID
                    try:
                        # Replace with actual upload logic and get the ID
                        story_id = self.ado_client.create_story(story)  # This should return an int ID
                    except Exception as upload_exc:
                        self.logger.error(f"[AGENT] Failed to upload story '{story.heading}': {upload_exc}")
                        continue
                    if isinstance(story_id, int):
                        created_stories.append(story_id)
                    else:
                        self.logger.error(f"[AGENT] Story upload did not return a valid integer ID for '{story.heading}'")
            else:
                self.logger.info(f"[AGENT] No stories extracted for Epic {epic_id}")
            return EpicSyncResult(
                epic_id=epic_id,
                epic_title=requirement.title,
                sync_successful=True,
                created_stories=created_stories,
                updated_stories=updated_stories,
                unchanged_stories=unchanged_stories
            )
        except Exception as e:
            self.logger.error(f"[AGENT] Exception during Epic sync: {e}")
            import traceback
            self.logger.error(traceback.format_exc())
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
    
    def get_epic_snapshot(self, epic_id: str) -> Optional[Dict[str, str]]:
        """Get a snapshot of the current EPIC for change tracking"""
        try:
            numeric_id = epic_id  # No numeric parsing
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

    def _setup_logger(self) -> logging.Logger:
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
