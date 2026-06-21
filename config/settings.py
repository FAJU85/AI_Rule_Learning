from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    HF_TOKEN: str | None = None
    HF_DATASET_NAME: str = "your-org/conversation-memory"
    HF_RULES_DATASET: str = "your-org/active-rules"
    REDIS_URL: str = "redis://localhost:6379"
    REDIS_RULE_TTL: int = 604800
    OPENAI_API_KEY: str | None = None
    OPENAI_MODEL: str = "gpt-4-turbo-preview"
    ANTHROPIC_API_KEY: str | None = None
    ANTHROPIC_MODEL: str = "claude-3-opus-20240229"
    DEFAULT_AI_PROVIDER: str = "openai"
    EMBEDDING_MODEL: str = "all-MiniLM-L6-v2"
    MIN_SESSION_LENGTH: int = 3
    GAP_THRESHOLD: float = 0.3
    MIN_GAPS_FOR_RULE: int = 2
    VALIDATION_SAMPLE_SIZE: int = 100
    EFFECTIVENESS_THRESHOLD: float = 0.15
    LOG_LEVEL: str = "INFO"

    class Config:
        env_file = ".env"


settings = Settings()
