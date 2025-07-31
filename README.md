# ado-story-extractor

## Overview

This project provides an automated way to extract user stories from requirements using AI and Azure DevOps.

### Project Structure

- **ado-story-extractor/**: The root directory for our project.
- **src/**: Contains the core application logic.
    - **models.py**: Defines the data structures for Requirements, User Stories, and extraction results.
    - **ado_client.py**: A client for interacting with the Azure DevOps API.
    - **story_extractor.py**: The AI-powered component that uses OpenAI to extract stories from requirements.
    - **agent.py**: The main orchestrator that brings everything together.
- **tests/**: Contains all the tests for the project.
    - Includes tests for models, settings, and the story extractor.
    - **conftest.py**: For test configuration.
- **config/**: For configuration files.
    - **settings.py**: Handles application settings.
- **.env.example**: An example environment file. You'll need to create a `.env` file based on this and fill in your ADO and OpenAI credentials.
- **requirements.txt**: Lists all the Python dependencies.
- **main.py**: The command-line interface (CLI) for running the agent.

---

Feel free to explore the code and adapt it to your needs!

