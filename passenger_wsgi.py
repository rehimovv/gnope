"""cPanel / Passenger entry point."""

from app.web import create_app

application = create_app()
