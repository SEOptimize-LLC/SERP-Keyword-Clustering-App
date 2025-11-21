# SERP-Based AI Keyword Clustering & Cannibalization Analyzer

This application is a powerful SEO tool designed to cluster keywords based on live SERP data and analyze them for cannibalization issues using AI. It leverages DataforSEO for SERP extraction, OpenAI for intent analysis, and Redis for caching.

## Features

*   **SERP-Based Clustering**: Groups keywords that share a high percentage (default 80%) of ranking URLs in the top 10 results. This ensures clusters reflect how Google actually treats the keywords.
*   **AI Intent Analysis**: Uses OpenAI's Batch API (GPT-4o-mini) to analyze clusters, determine user intent (Informational, Commercial, etc.), and generate descriptive labels.
*   **Cannibalization Detection**: Identifies instances where multiple pages from your domain are competing for the same keyword cluster.
*   **Cost-Effective**: Utilizes OpenAI Batch API (50% discount) and Redis caching (30-day TTL) to minimize API costs.
*   **Streamlit Interface**: User-friendly dashboard for managing the entire workflow.

## Prerequisites

*   Python 3.8+
*   **DataforSEO API Credentials**: [Sign up here](https://dataforseo.com/)
*   **OpenAI API Key**: [Sign up here](https://platform.openai.com/) (Optional, for Batch API)
*   **OpenRouter API Key**: [Sign up here](https://openrouter.ai/) (Optional, for flexible model selection)
*   **Redis Database**: Required for caching SERP results. You can use a free tier from [Redis Cloud](https://redis.com/try-free/).

## Installation

1.  Clone the repository or navigate to the project directory.
2.  Install the required Python packages:

    ```bash
    pip install -r requirements.txt
    ```

## Usage

1.  Run the Streamlit application:

    ```bash
    streamlit run app.py
    ```

2.  **Configuration (Sidebar)**:
    *   Enter your **DataforSEO API User** and **Password**.
    *   Enter your **OpenAI API Key** (if using OpenAI Batch).
    *   Enter your **OpenRouter API Key** (if using OpenRouter).
    *   Enter your **Redis URL** (e.g., `redis://:password@host:port`).
    *   Set your **Domain** (e.g., `example.com`) for cannibalization checks.
    *   Adjust the **SERP Overlap Threshold** if needed.

3.  **Workflow**:
    *   **Tab 1: Setup & Scrape**: Upload your CSV file containing keywords. Click "Fetch SERP Data" to retrieve live results.
    *   **Tab 2: Clustering & AI**:
        *   Click "Run SERP Overlap Clustering" to group keywords.
        *   **AI Analysis**:
            *   Select **OpenAI (Batch API)** for cost savings (24h turnaround).
            *   Select **OpenRouter** to choose specific models (e.g., Claude 3.5 Sonnet, Gemini Pro, etc.) for immediate results.
    *   **Tab 3: Analytics & Action**:
        *   View the clustered data with AI-generated labels and intents.
        *   Click "Check for Cannibalization" to identify conflicting pages.
        *   Download the final report as a CSV.

## File Structure

*   `app.py`: Main Streamlit application interface.
*   `clustering_engine.py`: Logic for fetching SERPs, caching, and calculating overlap.
*   `ai_processor.py`: Handles OpenAI Batch API interactions.
*   `cannibalization_logic.py`: Logic for mapping clusters to URLs and detecting issues.
*   `requirements.txt`: Python dependencies.
*   `packages.txt`: System dependencies (for Streamlit Cloud).

## Deployment on Streamlit Cloud

1.  Push this code to a GitHub repository.
2.  Connect your repository to [Streamlit Cloud](https://streamlit.io/cloud).
3.  In the App Settings -> **Secrets**, add your API keys and Redis URL. This allows the app to automatically load your credentials without manual entry.

    ```toml
    DATAFORSEO_USER = "your_user_id"
    DATAFORSEO_PASSWORD = "your_password"
    OPENAI_API_KEY = "sk-..."
    OPENROUTER_API_KEY = "sk-or-..."
    REDIS_URL = "redis://:password@host:port"
    ```
    *(Note: If you don't set these secrets, the app will prompt you to enter them manually in the sidebar)*.

## License

[MIT License](LICENSE)