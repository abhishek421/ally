"""Test that all configuration is loaded from .env file."""

from src.config import get_settings
from src.tools.database import test_connection

def main():
    """Test configuration loading."""
    settings = get_settings()
    
    print("=" * 60)
    print("Configuration from .env file:")
    print("=" * 60)
    
    # Database
    if settings.database_url_ally:
        # Mask password in connection string
        db_url = settings.database_url_ally
        if "@" in db_url:
            parts = db_url.split("@")
            if ":" in parts[0]:
                user_pass = parts[0].split(":")
                if len(user_pass) > 2:
                    masked = f"{user_pass[0]}:{'*' * 10}@{parts[1]}"
                else:
                    masked = f"{user_pass[0]}:{'*' * 10}@{parts[1]}"
            else:
                masked = db_url
        else:
            masked = db_url
        print(f"✓ DATABASE_URL_ALLY: {masked}")
    else:
        print("✗ DATABASE_URL_ALLY: Not set")
    
    # API Keys (masked)
    print(f"✓ OPENAI_API_KEY: {'Set' if settings.openai_api_key else 'Not set'}")
    print(f"✓ GOOGLE_API_KEY: {'Set' if settings.google_api_key else 'Not set'}")
    print(f"✓ ANTHROPIC_API_KEY: {'Set' if settings.anthropic_api_key else 'Not set'}")
    
    # Other config
    print(f"✓ LLM_MODEL: {settings.llm_model}")
    print(f"✓ QUERY_PROCESSING_MODEL: {settings.query_processing_model}")
    print(f"✓ DATABASE_URL_ALLY required: {'Yes' if settings.database_url_ally else 'No (will raise error)'}")
    
    print("\n" + "=" * 60)
    print("Testing database connection...")
    print("=" * 60)
    
    try:
        result = test_connection()
        if result:
            print("✓ Database connection: SUCCESS")
        else:
            print("✗ Database connection: FAILED")
    except ValueError as e:
        print(f"✗ Database connection: {e}")
    except Exception as e:
        print(f"✗ Database connection error: {e}")

if __name__ == "__main__":
    main()

