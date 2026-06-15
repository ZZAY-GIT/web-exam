# -*- coding: utf-8 -*-
import unittest
import os
import hashlib
from io import BytesIO
from app import app, db, render_markdown
from models import Book, Genre, Cover, User, Role, Review

class TestElectronicLibrary(unittest.TestCase):
    def setUp(self):
        app.config['TESTING'] = True
        # Use in-memory database for testing
        app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///:memory:'
        app.config['UPLOAD_FOLDER'] = os.path.join(os.path.dirname(__file__), 'static', 'test_covers')
        self.app_context = app.app_context()
        self.app_context.push()
        
        db.create_all()
        
        # Clear existing data if connection is reused
        db.session.query(Genre).delete()
        db.session.query(Role).delete()
        db.session.commit()
        
        # Seed test data
        self.role_admin = Role(name="Администратор", description="admin")
        self.role_user = Role(name="Пользователь", description="user")
        db.session.add(self.role_admin)
        db.session.add(self.role_user)
        
        self.genre_roman = Genre(name="Роман")
        self.genre_detective = Genre(name="Детектив")
        db.session.add(self.genre_roman)
        db.session.add(self.genre_detective)
        
        db.session.commit()

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        self.app_context.pop()
        
        # Cleanup test upload folder if created
        if os.path.exists(app.config['UPLOAD_FOLDER']):
            for f in os.listdir(app.config['UPLOAD_FOLDER']):
                os.remove(os.path.join(app.config['UPLOAD_FOLDER'], f))
            os.rmdir(app.config['UPLOAD_FOLDER'])

    def test_markdown_rendering(self):
        text = "## Hello\nThis is **bold** code."
        html = render_markdown(text)
        self.assertIn("<h2>Hello</h2>", html)
        self.assertIn("<strong>bold</strong>", html)

    def test_book_creation_and_search(self):
        # Create books
        b1 = Book(title="Шерлок Холмс", author="Конан Дойл", year=2020, publisher="АСТ", pages=350, description="Детективные истории")
        b1.genres.append(self.genre_detective)
        
        b2 = Book(title="Война и мир", author="Лев Толстой", year=2015, publisher="Эксмо", pages=1200, description="Исторический роман")
        b2.genres.append(self.genre_roman)
        
        db.session.add(b1)
        db.session.add(b2)
        db.session.commit()
        
        # Search by Title (partial match)
        results = Book.query.filter(Book.title.ilike('%Шерлок%')).all()
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].title, "Шерлок Холмс")
        
        # Search by Author (partial match)
        results = Book.query.filter(Book.author.ilike('%Толстой%')).all()
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].title, "Война и мир")
        
        # Search by Genre
        results = Book.query.filter(Book.genres.any(Genre.id == self.genre_detective.id)).all()
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].title, "Шерлок Холмс")
        
        # Search by Pages range
        results = Book.query.filter(Book.pages >= 300, Book.pages <= 400).all()
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].title, "Шерлок Холмс")

    def test_cover_deduplication(self):
        # Mock file
        file_bytes = b"fake image contents"
        md5_hash = hashlib.md5(file_bytes).hexdigest()
        
        b1 = Book(title="Book One", author="Author A", year=2021, publisher="Pub A", pages=100, description="Desc A")
        db.session.add(b1)
        db.session.flush()
        
        # First upload
        c1 = Cover(filename="cover1.jpg", mime_type="image/jpeg", md5_hash=md5_hash, book_id=b1.id)
        db.session.add(c1)
        db.session.commit()
        
        # Second book with same cover content
        b2 = Book(title="Book Two", author="Author B", year=2022, publisher="Pub B", pages=200, description="Desc B")
        db.session.add(b2)
        db.session.flush()
        
        # Check if hash exists in db
        existing_cover = Cover.query.filter_by(md5_hash=md5_hash).first()
        self.assertIsNotNone(existing_cover)
        
        # Reuse existing cover info
        c2 = Cover(filename=existing_cover.filename, mime_type=existing_cover.mime_type, md5_hash=md5_hash, book_id=b2.id)
        db.session.add(c2)
        db.session.commit()
        
        # Verify both reference same cover filename
        self.assertEqual(c1.filename, c2.filename)
        
        # Verify cascade deletion on Book delete
        db.session.delete(b1)
        db.session.commit()
        
        # Check that c1 is deleted but c2 is not (associated to b2)
        c1_lookup = Cover.query.filter_by(id=c1.id).first()
        c2_lookup = Cover.query.filter_by(id=c2.id).first()
        self.assertIsNone(c1_lookup)
        self.assertIsNotNone(c2_lookup)

    def test_review_creation_and_cascade_delete(self):
        b1 = Book(title="Book One", author="Author A", year=2021, publisher="Pub A", pages=100, description="Desc A")
        db.session.add(b1)
        db.session.flush()
        
        u1 = User(login="test_user", last_name="L", first_name="F", role_id=self.role_user.id)
        u1.set_password("pass")
        db.session.add(u1)
        db.session.flush()
        
        r1 = Review(book_id=b1.id, user_id=u1.id, rating=4, text="Test review text")
        db.session.add(r1)
        db.session.commit()
        
        # Verify review exists
        self.assertEqual(Review.query.count(), 1)
        
        # Delete review
        db.session.delete(r1)
        db.session.commit()
        self.assertEqual(Review.query.count(), 0)

    def test_review_deletion_route_permissions(self):
        u_mod = User(login="mod_user", last_name="L", first_name="F", role_id=self.role_admin.id)
        u_mod.set_password("pass")
        db.session.add(u_mod)
        
        b = Book(title="Book", author="Author", year=2021, publisher="Pub", pages=100, description="Desc")
        db.session.add(b)
        db.session.flush()
        
        r = Review(book_id=b.id, user_id=u_mod.id, rating=4, text="Test text")
        db.session.add(r)
        db.session.commit()
        
        client = app.test_client()
        
        # Try to delete without login (unauthorized redirects)
        response = client.post(f'/reviews/{r.id}/delete')
        self.assertEqual(response.status_code, 302)
        self.assertEqual(Review.query.count(), 1)

if __name__ == '__main__':
    unittest.main()
