#!/usr/bin/env python3

print("[STARTUP] Program starting...")

import argparse
import sys
from src.agent import StoryExtractionAgent
from config.settings import Settings

print("[STARTUP] Settings and Agent imported")

def main():
    print("[MAIN] Entering main function")
    parser = argparse.ArgumentParser(description="Extract user stories from ADO requirements using AI")
    
    subparsers = parser.add_subparsers(dest='command', help='Available commands')
    
    # Process single requirement
    process_cmd = subparsers.add_parser('process', help='Process a single requirement')
    process_cmd.add_argument('requirement_id', type=str, help='ID of the requirement to process (can be string or int)')
    process_cmd.add_argument('--no-upload', action='store_true', help='Do not upload extracted stories to ADO')

    # Process all requirements
    process_all_cmd = subparsers.add_parser('process-all', help='Process all requirements')
    process_all_cmd.add_argument('--state', type=str, help='Filter requirements by state (e.g., "Active", "New")')
    process_all_cmd.add_argument('--no-upload', action='store_true', help='Extract stories but do not upload to ADO')
    
    # Preview stories
    preview_cmd = subparsers.add_parser('preview', help='Preview extracted stories without uploading')
    preview_cmd.add_argument('requirement_id', type=str, help='ID of the requirement to preview (can be string or int)')

    # Get summary
    summary_cmd = subparsers.add_parser('summary', help='Get requirement summary')
    summary_cmd.add_argument('requirement_id', type=str, help='ID of the requirement (can be string or int)')

    # Validate config
    config_cmd = subparsers.add_parser('validate-config', help='Validate configuration settings')
    
    # Check work item types
    types_cmd = subparsers.add_parser('check-types', help='Check available work item types in the project')
    
    # Show ADO format
    format_cmd = subparsers.add_parser('show-format', help='Show how stories will be formatted in Azure DevOps')
    format_cmd.add_argument('requirement_id', type=str, help='ID of the requirement to show format for')
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        return
    
    try:
        print(f"[DEBUG] Starting command: {args.command}")
        if args.command == 'validate-config':
            validate_config()
            return
        
        # Initialize agent for all commands except validate-config
        agent = StoryExtractionAgent()

        if args.command == 'process':
            print(f"[DEBUG] Processing requirement ID: {args.requirement_id}")
            result = agent.process_requirement_by_id(
                args.requirement_id, 
                upload_to_ado=not args.no_upload
            )
            print(f"\n[RESULT] Processing completed for requirement ID: {args.requirement_id}")
            print(f"Extraction Successful: {getattr(result, 'extraction_successful', False)}")
            if getattr(result, 'error_message', None):
                print(f"Error: {result.error_message}")
            if hasattr(result, 'stories') and result.stories:
                print(f"Stories Extracted: {len(result.stories)}")
                for i, story in enumerate(result.stories, 1):
                    print(f"  Story {i}: {getattr(story, 'heading', '')}")
            else:
                print("No stories extracted.")
            return

        elif args.command == 'process-all':
            results = agent.process_all_requirements(
                state_filter=args.state,
                upload_to_ado=not args.no_upload
            )
            print_batch_results(results)
        
        elif args.command == 'preview':
            result = agent.preview_stories(args.requirement_id)
            print_extraction_result(result, preview=True)
        
        elif args.command == 'summary':
            summary = agent.get_requirement_summary(args.requirement_id)
            print_summary(summary)
        
        elif args.command == 'check-types':
            check_work_item_types(agent)
        
        elif args.command == 'show-format':
            show_ado_format(agent, args.requirement_id)
    
    except Exception as e:
        print(f"Error: {str(e)}", file=sys.stderr)
        sys.exit(1)

def validate_config():
    """Validate configuration settings"""
    try:
        Settings.validate()
        print("✅ Configuration is valid")
        print(f"Organization: {Settings.ADO_ORGANIZATION}")
        print(f"Project: {Settings.ADO_PROJECT}")
        print(f"Base URL: {Settings.ADO_BASE_URL}")
        print("✅ All required settings are present")
    except ValueError as e:
        print(f"❌ Configuration error: {str(e)}", file=sys.stderr)
        print("\nPlease check your .env file and ensure all required variables are set:")
        print("- ADO_ORGANIZATION")
        print("- ADO_PROJECT")
        print("- ADO_PAT")
        print("- OPENAI_API_KEY")
        sys.exit(1)

def print_extraction_result(result, preview=False):
    """Print the result of story extraction"""
    print(f"\n{'='*60}")
    print(f"Requirement #{result.requirement_id}: {result.requirement_title}")
    print(f"{'='*60}")
    
    if not result.extraction_successful:
        print(f"❌ Extraction failed: {result.error_message}")
        return
    
    if not result.stories:
        print("No stories extracted from this requirement.")
        return
    
    print(f"✅ Successfully extracted {len(result.stories)} user stories")
    if preview:
        print("(Preview mode - stories not uploaded to ADO)\n")
    else:
        print("(Stories uploaded to ADO)\n")
    
    for i, story in enumerate(result.stories, 1):
        print(f"Story {i}: {story.heading}")
        print(f"Description: {story.description}")
        print("Acceptance Criteria:")
        for j, criteria in enumerate(story.acceptance_criteria, 1):
            print(f"  {j}. {criteria}")
        print("-" * 40)

def print_batch_results(results):
    """Print results from batch processing"""
    print(f"\n{'='*60}")
    print(f"BATCH PROCESSING RESULTS")
    print(f"{'='*60}")
    
    successful = [r for r in results if r.extraction_successful]
    failed = [r for r in results if not r.extraction_successful]
    total_stories = sum(len(r.stories) for r in successful)
    
    print(f"Total requirements processed: {len(results)}")
    print(f"Successful: {len(successful)}")
    print(f"Failed: {len(failed)}")
    print(f"Total stories extracted: {total_stories}")
    
    if failed:
        print(f"\n❌ Failed requirements:")
        for result in failed:
            print(f"  - #{result.requirement_id}: {result.error_message}")
    
    if successful:
        print(f"\n✅ Successful requirements:")
        for result in successful:
            print(f"  - #{result.requirement_id}: {len(result.stories)} stories extracted")

def print_summary(summary):
    """Print requirement summary"""
    if "error" in summary:
        print(f"❌ Error: {summary['error']}")
        return
    
    req = summary["requirement"]
    stories = summary["child_stories"]
    
    print(f"\n{'='*60}")
    print(f"REQUIREMENT SUMMARY")
    print(f"{'='*60}")
    print(f"ID: {req['id']}")
    print(f"Title: {req['title']}")
    print(f"State: {req['state']}")
    print(f"Description: {req['description']}")
    print(f"\nChild Stories: {stories['count']}")
    if stories['ids']:
        print(f"Story IDs: {', '.join(map(str, stories['ids']))}")

def check_work_item_types(agent):
    """Check available work item types in the project"""
    try:
        work_item_types = agent.ado_client.get_work_item_types()
        
        print(f"\n{'='*60}")
        print(f"AVAILABLE WORK ITEM TYPES")
        print(f"{'='*60}")
        print(f"Project: {Settings.ADO_PROJECT}")
        print(f"Organization: {Settings.ADO_ORGANIZATION}")
        print(f"\nFound {len(work_item_types)} work item types:")
        
        for i, work_type in enumerate(work_item_types, 1):
            print(f"  {i}. {work_type}")
        
        print(f"\n{'='*60}")
        print(f"CURRENT CONFIGURATION")
        print(f"{'='*60}")
        print(f"Requirement Type: {Settings.REQUIREMENT_TYPE}")
        print(f"User Story Type: {Settings.USER_STORY_TYPE}")
        
        # Check if configured types exist
        if Settings.REQUIREMENT_TYPE in work_item_types:
            print(f"✅ Requirement type '{Settings.REQUIREMENT_TYPE}' is available")
        else:
            print(f"❌ Requirement type '{Settings.REQUIREMENT_TYPE}' is NOT available")
            
        if Settings.USER_STORY_TYPE in work_item_types:
            print(f"✅ User story type '{Settings.USER_STORY_TYPE}' is available")
        else:
            print(f"❌ User story type '{Settings.USER_STORY_TYPE}' is NOT available")
            print("\n💡 Suggested alternatives:")
            for work_type in work_item_types:
                if any(keyword in work_type.lower() for keyword in ['story', 'task', 'item', 'backlog']):
                    print(f"   - {work_type}")
        
    except Exception as e:
        print(f"❌ Error checking work item types: {str(e)}")

def show_ado_format(agent, requirement_id):
    """Show how stories will be formatted in Azure DevOps"""
    try:
        result = agent.preview_stories(requirement_id)
        
        if not result.extraction_successful:
            print(f"❌ Failed to extract stories: {result.error_message}")
            return
        
        print(f"\n{'='*80}")
        print(f"AZURE DEVOPS WORK ITEM FORMAT PREVIEW")
        print(f"{'='*80}")
        print(f"Requirement: {result.requirement_title}")
        print(f"Stories will be created as: {Settings.USER_STORY_TYPE}")
        print(f"\nTotal Stories: {len(result.stories)}")
        
        for i, story in enumerate(result.stories, 1):
            ado_format = story.to_ado_format()
            
            print(f"\n{'-'*80}")
            print(f"STORY {i} - ADO WORK ITEM FIELDS:")
            print(f"{'-'*80}")
            
            print(f"\n🏷️  System.Title:")
            print(f"{ado_format['System.Title']}")
            
            print(f"\n📝 System.Description:")
            print(f"{ado_format['System.Description']}")
            
            print(f"\n📊 Work Item Type: {Settings.USER_STORY_TYPE}")
        
        print(f"\n{'='*80}")
        print(f"NOTE: The acceptance criteria are now included in the Description field")
        print(f"as requested, formatted with bullet points and a clear heading.")
        print(f"{'='*80}")
        
    except Exception as e:
        print(f"❌ Error showing ADO format: {str(e)}")

if __name__ == "__main__":
    main()
