import os
from dotenv import load_dotenv

class Settings:
    """Application settings loaded from environment variables"""

    # Load environment variables
    print("[CONFIG] Loading environment variables...")
    load_dotenv()

    # Azure DevOps settings
    ADO_ORGANIZATION = os.getenv('ADO_ORGANIZATION')
    ADO_PROJECT = os.getenv('ADO_PROJECT')
    ADO_PAT = os.getenv('ADO_PAT')
    ADO_BASE_URL = "https://dev.azure.com"

    # Work item types
    REQUIREMENT_TYPE = os.getenv('ADO_REQUIREMENT_TYPE', 'Epic')
    USER_STORY_TYPE = os.getenv('ADO_USER_STORY_TYPE', 'User Story')

    # OpenAI settings
    OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')
    OPENAI_MAX_RETRIES = int(os.getenv('OPENAI_MAX_RETRIES', 3))
    try:
        OPENAI_RETRY_DELAY = int(os.getenv('OPENAI_RETRY_DELAY', 5))
    except Exception:
        OPENAI_RETRY_DELAY = 5
    print(f"[CONFIG] OPENAI_RETRY_DELAY: {OPENAI_RETRY_DELAY}")

    @classmethod
    def validate(cls):
        """Validate required settings are present"""
        print("[CONFIG] Validating settings...")
        missing = []

        # Check Azure DevOps settings
        if not cls.ADO_ORGANIZATION:
            missing.append("ADO_ORGANIZATION")
            print("[ERROR] ADO_ORGANIZATION is not set")
        else:
            print(f"[CONFIG] ADO_ORGANIZATION: {cls.ADO_ORGANIZATION}")

        if not cls.ADO_PROJECT:
            missing.append("ADO_PROJECT")
            print("[ERROR] ADO_PROJECT is not set")
        else:
            print(f"[CONFIG] ADO_PROJECT: {cls.ADO_PROJECT}")

        if not cls.ADO_PAT:
            missing.append("ADO_PAT")
            print("[ERROR] ADO_PAT is not set")
        else:
            print("[CONFIG] ADO_PAT: [SECURED]")

        if not cls.OPENAI_API_KEY:
            missing.append("OPENAI_API_KEY")
            print("[ERROR] OPENAI_API_KEY is not set")
        else:
            print("[CONFIG] OPENAI_API_KEY: [SECURED]")

        if missing:
            raise ValueError(
                f"Missing required environment variables: {', '.join(missing)}. "
                f"Please check your .env file and ensure all required variables are set."
            )
