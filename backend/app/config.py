from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    semap_host: str = "0.0.0.0"
    semap_port: int = 8000
    database_url: str
    jwt_secret: str
    fr24_api_token: str = ""
    google_maps_api_key: str = ""
    baidu_maps_api_key: str = ""
    amap_maps_api_key: str = ""

    model_config = SettingsConfigDict(
        env_file="/root/semap/.env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


settings = Settings()
