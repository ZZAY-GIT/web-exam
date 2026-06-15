from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime

db = SQLAlchemy()

book_genres = db.Table('book_genres',
    db.Column('book_id', db.Integer, db.ForeignKey('books.id', ondelete='CASCADE'), primary_key=True),
    db.Column('genre_id', db.Integer, db.ForeignKey('genres.id', ondelete='CASCADE'), primary_key=True)
)

class Role(db.Model):
    __tablename__ = 'roles'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), unique=True, nullable=False)
    description = db.Column(db.Text, nullable=False)

    def __repr__(self):
        return f'<Role {self.name}>'

class User(db.Model, UserMixin):
    __tablename__ = 'users'
    
    id = db.Column(db.Integer, primary_key=True)
    login = db.Column(db.String(100), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    last_name = db.Column(db.String(100), nullable=False)
    first_name = db.Column(db.String(100), nullable=False)
    middle_name = db.Column(db.String(100), nullable=True)
    role_id = db.Column(db.Integer, db.ForeignKey('roles.id'), nullable=False)
    
    role = db.relationship('Role', backref=db.backref('users', lazy=True))

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    @property
    def full_name(self):
        if self.middle_name:
            return f"{self.last_name} {self.first_name} {self.middle_name}"
        return f"{self.last_name} {self.first_name}"

    @property
    def is_admin(self):
        return self.role.name == 'Администратор' if self.role else False

    @property
    def is_moderator(self):
        return self.role.name == 'Модератор' if self.role else False

    @property
    def is_user(self):
        return self.role.name == 'Пользователь' if self.role else False

    def can_edit(self):
        return self.is_admin or self.is_moderator

    def can_delete(self):
        return self.is_admin

    def can_create(self):
        return self.is_admin

    def __repr__(self):
        return f'<User {self.login}>'

class Genre(db.Model):
    __tablename__ = 'genres'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), unique=True, nullable=False)

    def __repr__(self):
        return f'<Genre {self.name}>'

class Book(db.Model):
    __tablename__ = 'books'
    
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(255), nullable=False)
    description = db.Column(db.Text, nullable=False)
    year = db.Column(db.Integer, nullable=False)
    publisher = db.Column(db.String(255), nullable=False)
    author = db.Column(db.String(255), nullable=False)
    pages = db.Column(db.Integer, nullable=False)
    
    genres = db.relationship('Genre', secondary=book_genres, backref=db.backref('books', lazy='dynamic'))
    reviews = db.relationship('Review', backref='book', cascade='all, delete-orphan')
    covers = db.relationship('Cover', backref='book', cascade='all, delete-orphan')

    @property
    def average_rating(self):
        ratings = [r.rating for r in self.reviews]
        if not ratings:
            return 0.0
        return round(sum(ratings) / len(ratings), 2)

    @property
    def review_count(self):
        return len(self.reviews)

    @property
    def cover(self):
        return self.covers[0] if self.covers else None

    def __repr__(self):
        return f'<Book {self.title}>'

class Cover(db.Model):
    __tablename__ = 'covers'
    
    id = db.Column(db.Integer, primary_key=True)
    filename = db.Column(db.String(255), nullable=False)
    mime_type = db.Column(db.String(100), nullable=False)
    md5_hash = db.Column(db.String(100), nullable=False)
    book_id = db.Column(db.Integer, db.ForeignKey('books.id', ondelete='CASCADE'), nullable=False)

    def __repr__(self):
        return f'<Cover {self.filename}>'

class Review(db.Model):
    __tablename__ = 'reviews'
    
    id = db.Column(db.Integer, primary_key=True)
    book_id = db.Column(db.Integer, db.ForeignKey('books.id', ondelete='CASCADE'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'), nullable=False)
    rating = db.Column(db.Integer, nullable=False)
    text = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    
    user = db.relationship('User', backref=db.backref('reviews', lazy=True))

    def __repr__(self):
        return f'<Review {self.rating} stars by User {self.user_id} on Book {self.book_id}>'
