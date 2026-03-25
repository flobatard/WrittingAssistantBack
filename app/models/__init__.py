# app/models/__init__.py


from app.core.database import Base 


from app.models.book import Book

__all__ = ["Base", "Book"]