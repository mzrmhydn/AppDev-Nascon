# All SQLAlchemy tables in one import: platform tables (Track A) + league tables (Track B).
from app.models_platform import *  # noqa: F401,F403
from app.models_league import *  # noqa: F401,F403
