import os
import hashlib
from functools import wraps
from flask import Flask, render_template, redirect, url_for, flash, request, abort
from flask_login import LoginManager, current_user, login_required
from flask_migrate import Migrate
import bleach
import markdown
from werkzeug.utils import secure_filename

from config import Config
from models import db, User, Role, Genre, Book, Cover, Review
from auth import auth_bp

app = Flask(__name__)
app.config.from_object(Config)

db.init_app(app)
migrate = Migrate(app, db)

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'auth.login'
login_manager.login_message = 'Для выполнения данного действия необходимо пройти процедуру аутентификации'
login_manager.login_message_category = 'warning'

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

app.register_blueprint(auth_bp)

def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated:
            return login_manager.unauthorized()
        if not current_user.is_admin:
            flash("У вас недостаточно прав для выполнения данного действия", "danger")
            return redirect(url_for('index'))
        return f(*args, **kwargs)
    return decorated_function

def editor_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated:
            return login_manager.unauthorized()
        if not (current_user.is_admin or current_user.is_moderator):
            flash("У вас недостаточно прав для выполнения данного действия", "danger")
            return redirect(url_for('index'))
        return f(*args, **kwargs)
    return decorated_function

@app.template_filter('markdown')
def render_markdown(text):
    if not text:
        return ""
    # Безопасный рендеринг: очистка тегов с помощью bleach перед конвертацией Markdown
    return markdown.markdown(text, extensions=['fenced_code', 'tables'])

@app.route('/')
def index():
    title = request.args.get('title', '').strip()
    author = request.args.get('author', '').strip()
    selected_genres = request.args.getlist('genre')
    selected_years = request.args.getlist('year')
    pages_min = request.args.get('pages_min', '').strip()
    pages_max = request.args.get('pages_max', '').strip()
    page = request.args.get('page', 1, type=int)

    query = db.session.query(Book)
    if title:
        query = query.filter(Book.title.ilike(f'%{title}%'))
    if author:
        query = query.filter(Book.author.ilike(f'%{author}%'))
    if selected_genres:
        query = query.filter(Book.genres.any(Genre.id.in_([int(g) for g in selected_genres])))
    if selected_years:
        query = query.filter(Book.year.in_([int(y) for y in selected_years]))
    if pages_min:
        try:
            query = query.filter(Book.pages >= int(pages_min))
        except ValueError:
            pass
    if pages_max:
        try:
            query = query.filter(Book.pages <= int(pages_max))
        except ValueError:
            pass

    query = query.order_by(Book.year.desc(), Book.id.desc())

    pagination = query.paginate(page=page, per_page=10, error_out=False)

    genres = Genre.query.order_by(Genre.name).all()
    # Варианты выбора в поле «год» формируются исходя из содержимого БД
    years_tuples = db.session.query(Book.year).distinct().order_by(Book.year.desc()).all()
    years = [y[0] for y in years_tuples]

    return render_template('index.html', pagination=pagination, genres=genres, years=years)

@app.route('/books/<int:book_id>')
def book_show(book_id):
    book = Book.query.get_or_404(book_id)
    reviews = Review.query.filter_by(book_id=book_id).order_by(Review.created_at.desc()).all()
    
    user_review = None
    if current_user.is_authenticated:
        user_review = Review.query.filter_by(book_id=book_id, user_id=current_user.id).first()
        
    return render_template('book_show.html', book=book, reviews=reviews, user_review=user_review)

@app.route('/books/new', methods=['GET', 'POST'])
@admin_required
def book_add():
    if request.method == 'POST':
        title = request.form.get('title', '').strip()
        author = request.form.get('author', '').strip()
        year = request.form.get('year', '').strip()
        publisher = request.form.get('publisher', '').strip()
        pages = request.form.get('pages', '').strip()
        genres_list = request.form.getlist('genres')
        description = request.form.get('description', '').strip()
        cover_file = request.files.get('cover_file')

        if not (title and author and year and publisher and pages and genres_list and description and cover_file):
            flash("Все поля формы обязательны для заполнения.", "danger")
            genres = Genre.query.all()
            return render_template('book_form.html', genres=genres, selected_genre_ids=[int(x) for x in genres_list])

        # Вычисление MD5-хэша обложки для дедупликации файлов
        try:
            file_data = cover_file.read()
            md5_hash = hashlib.md5(file_data).hexdigest()
            cover_file.seek(0)
            
            existing_cover = Cover.query.filter_by(md5_hash=md5_hash).first()
            
            clean_desc = bleach.clean(description)
            
            new_book = Book(
                title=title,
                author=author,
                year=int(year),
                publisher=publisher,
                pages=int(pages),
                description=clean_desc
            )
            
            selected_genres = Genre.query.filter(Genre.id.in_([int(g) for g in genres_list])).all()
            new_book.genres = selected_genres
            
            db.session.add(new_book)
            db.session.flush()
            
            if existing_cover:
                # Повторное использование имени файла обложки при совпадении хэша
                new_cover = Cover(
                    filename=existing_cover.filename,
                    mime_type=existing_cover.mime_type,
                    md5_hash=md5_hash,
                    book_id=new_book.id
                )
                db.session.add(new_cover)
            else:
                mime_type = cover_file.mimetype or 'image/jpeg'
                temp_filename = "temp_" + secure_filename(cover_file.filename)
                
                new_cover = Cover(
                    filename=temp_filename,
                    mime_type=mime_type,
                    md5_hash=md5_hash,
                    book_id=new_book.id
                )
                db.session.add(new_cover)
                db.session.flush()
                
                # Формирование имени файла: ID обложки + исходное расширение
                ext = os.path.splitext(cover_file.filename)[1].lower()
                if not ext:
                    ext = '.jpg'
                final_filename = f"{new_cover.id}{ext}"
                new_cover.filename = final_filename
                
                os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
                
                file_path = os.path.join(app.config['UPLOAD_FOLDER'], final_filename)
                with open(file_path, 'wb') as f:
                    f.write(file_data)
                    
            db.session.commit()
            flash("Книга успешно добавлена.", "success")
            return redirect(url_for('book_show', book_id=new_book.id))
            
        except Exception as e:
            db.session.rollback()
            print(f"Error saving book: {e}")
            flash("При сохранении данных возникла ошибка. Проверьте корректность введённых данных.", "danger")
            genres = Genre.query.all()
            return render_template('book_form.html', genres=genres, selected_genre_ids=[int(x) for x in genres_list])
            
    genres = Genre.query.all()
    return render_template('book_form.html', genres=genres, selected_genre_ids=[])

@app.route('/books/<int:book_id>/edit', methods=['GET', 'POST'])
@editor_required
def book_edit(book_id):
    book = Book.query.get_or_404(book_id)
    
    if request.method == 'POST':
        title = request.form.get('title', '').strip()
        author = request.form.get('author', '').strip()
        year = request.form.get('year', '').strip()
        publisher = request.form.get('publisher', '').strip()
        pages = request.form.get('pages', '').strip()
        genres_list = request.form.getlist('genres')
        description = request.form.get('description', '').strip()
        
        if not (title and author and year and publisher and pages and genres_list and description):
            flash("Все поля формы обязательны для заполнения.", "danger")
            genres = Genre.query.all()
            return render_template('book_form.html', genres=genres, selected_genre_ids=[int(x) for x in genres_list], book=book)
            
        try:
            book.title = title
            book.author = author
            book.year = int(year)
            book.publisher = publisher
            book.pages = int(pages)
            book.description = bleach.clean(description)
            
            selected_genres = Genre.query.filter(Genre.id.in_([int(g) for g in genres_list])).all()
            book.genres = selected_genres
            
            db.session.commit()
            flash("Книга успешно обновлена.", "success")
            return redirect(url_for('book_show', book_id=book.id))
            
        except Exception as e:
            db.session.rollback()
            print(f"Error updating book: {e}")
            flash("При сохранении данных возникла ошибка. Проверьте корректность введённых данных.", "danger")
            genres = Genre.query.all()
            return render_template('book_form.html', genres=genres, selected_genre_ids=[int(x) for x in genres_list], book=book)
            
    genres = Genre.query.all()
    selected_genre_ids = [g.id for g in book.genres]
    return render_template('book_form.html', genres=genres, selected_genre_ids=selected_genre_ids, book=book)

@app.route('/books/<int:book_id>/delete', methods=['POST'])
@admin_required
def book_delete(book_id):
    book = Book.query.get_or_404(book_id)
    title = book.title
    
    try:
        # Удаление физических файлов обложек из файловой системы при удалении книги (если они уникальны)
        covers = Cover.query.filter_by(book_id=book.id).all()
        for cover in covers:
            # Проверка, не привязана ли данная обложка к другим книгам (дедупликация)
            siblings_count = Cover.query.filter(Cover.filename == cover.filename, Cover.id != cover.id).count()
            if siblings_count == 0:
                file_path = os.path.join(app.config['UPLOAD_FOLDER'], cover.filename)
                if os.path.exists(file_path):
                    try:
                        os.remove(file_path)
                        print(f"Physical file {cover.filename} deleted.")
                    except Exception as fe:
                        print(f"Failed to delete file {cover.filename}: {fe}")
                        
        db.session.delete(book)
        db.session.commit()
        flash(f"Книга «{title}» была успешно удалена.", "success")
    except Exception as e:
        db.session.rollback()
        print(f"Error deleting book: {e}")
        flash("Не удалось удалить книгу из базы данных.", "danger")
        
    return redirect(url_for('index'))

@app.route('/reviews/<int:review_id>/delete', methods=['POST'])
@editor_required
def review_delete(review_id):
    review = Review.query.get_or_404(review_id)
    book_id = review.book_id
    try:
        db.session.delete(review)
        db.session.commit()
        flash("Рецензия успешно удалена.", "success")
    except Exception as e:
        db.session.rollback()
        print(f"Error deleting review: {e}")
        flash("Не удалось удалить рецензию.", "danger")
    return redirect(url_for('book_show', book_id=book_id))

@app.route('/books/<int:book_id>/reviews/new', methods=['GET', 'POST'])
@login_required
def review_add(book_id):
    book = Book.query.get_or_404(book_id)
    
    # Check if user already wrote a review
    existing_review = Review.query.filter_by(book_id=book_id, user_id=current_user.id).first()
    if existing_review:
        flash("Вы уже оставили рецензию на эту книгу.", "warning")
        return redirect(url_for('book_show', book_id=book_id))
        
    if request.method == 'POST':
        rating = request.form.get('rating', '').strip()
        text = request.form.get('text', '').strip()
        
        if not (rating and text):
            flash("Пожалуйста, заполните все поля.", "danger")
            return render_template('review_form.html', book=book)
            
        try:
            clean_text = bleach.clean(text)
            new_review = Review(
                book_id=book_id,
                user_id=current_user.id,
                rating=int(rating),
                text=clean_text
            )
            db.session.add(new_review)
            db.session.commit()
            
            flash("Рецензия успешно добавлена.", "success")
            return redirect(url_for('book_show', book_id=book_id))
            
        except Exception as e:
            db.session.rollback()
            print(f"Error saving review: {e}")
            flash("При сохранении данных возникла ошибка. Проверьте корректность введённых данных.", "danger")
            return render_template('review_form.html', book=book)
            
    return render_template('review_form.html', book=book)

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=True, host='0.0.0.0', port=5012)
