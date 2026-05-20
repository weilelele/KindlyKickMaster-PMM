from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # Feishu App
    feishu_app_id: str
    feishu_app_secret: str
    feishu_verification_token: str = ""
    feishu_encrypt_key: str = ""

    # Claude
    anthropic_api_key: str

    # Supabase (use service role key for full access)
    supabase_url: str
    supabase_service_key: str

    # Bot identity
    owner_open_id: str   # owner's Feishu open_id (for private commands)
    group_chat_id: str   # main group chat_id for daily broadcasts
    bot_open_id: str     # bot's own open_id (to detect @mentions)

    class Config:
        env_file = ".env"


settings = Settings()
