import os
from dotenv import load_dotenv

load_dotenv()

class Settings:
    # Azure DevOps Configuration
    ADO_ORGANIZATION = os.getenv("ADO_ORGANIZATION")
    ADO_PROJECT = os.getenv("ADO_PROJECT") 
    ADO_PAT = os.getenv("ADO_PAT")
    ADO_BASE_URL = os.getenv("ADO_BASE_URL", "https://dev.azure.com")
    
    # OpenAI Configuration
    OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
    OPENAI_MAX_RETRIES = int(os.getenv("OPENAI_MAX_RETRIES", "3"))
    OPENAI_RETRY_DELAY = int(os.getenv("OPENAI_RETRY_DELAY", "5"))
    
    # Work Item Types - configurable via environment variables
    REQUIREMENT_TYPE = os.getenv("ADO_REQUIREMENT_TYPE", "Epic")
    USER_STORY_TYPE = os.getenv("ADO_USER_STORY_TYPE", "Task")
    
    @classmethod
    def validate(cls):
        """Validate that all required settings are present"""
        required_settings = [
            "ADO_ORGANIZATION",
            "ADO_PROJECT", 
            "ADO_PAT",
            "OPENAI_API_KEY"
        ]
        
        missing = []
        for setting in required_settings:
            if not getattr(cls, setting):
                missing.append(setting)
        
        if missing:
            raise ValueError(f"Missing required settings: {', '.join(missing)}")
        
        return True
