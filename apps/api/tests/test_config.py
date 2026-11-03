from atlas.config import Settings


def test_generic_postgres_url_uses_installed_psycopg_driver():
    settings = Settings(database_url="postgresql://atlas:secret@db.internal:5432/atlas")

    assert settings.database_url == "postgresql+psycopg://atlas:secret@db.internal:5432/atlas"
