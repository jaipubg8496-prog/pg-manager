from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str
    secret_key: str
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 1440  # 24 hours

    # Optional until you're ready to take payments — billing endpoints check
    # for these at call-time and return a clear error if they're blank,
    # rather than crashing the whole app at startup like database_url would.
    razorpay_key_id: str = ""
    razorpay_key_secret: str = ""

    # Optional — only needed if you enable "Sign in with Google" on the login page.
    google_client_id: str = ""

    class Config:
        env_file = ".env"


settings = Settings()

# Business rules for trial/subscription — plain constants, not secrets,
# so they live here rather than in .env.
TRIAL_DAYS = 90  # ~3 months
SUBSCRIPTION_PRICE_RUPEES = 499
SUBSCRIPTION_PERIOD_DAYS = 30
