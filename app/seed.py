from app import app
from models import db, Role, User, Genre

def seed_db():
    with app.app_context():
        # Create tables
        db.create_all()
        print("Database tables created.")

        # Seed Roles
        roles_data = [
            {
                'name': 'Администратор',
                'description': 'суперпользователь, имеет полный доступ к системе, в том числе к созданию и удалению книг'
            },
            {
                'name': 'Модератор',
                'description': 'может редактировать данные книг и производить модерацию рецензий'
            },
            {
                'name': 'Пользователь',
                'description': 'может оставлять рецензии'
            }
        ]

        roles = {}
        for role_info in roles_data:
            role = Role.query.filter_by(name=role_info['name']).first()
            if not role:
                role = Role(name=role_info['name'], description=role_info['description'])
                db.session.add(role)
                db.session.commit()
                print(f"Role '{role.name}' created.")
            roles[role.name] = role

        # Seed Genres
        genres_data = [
            'Роман', 'Фантастика', 'Детектив', 'Наука', 'История', 
            'Поэзия', 'Приключения', 'Ужасы', 'Фэнтези', 'Биография'
        ]
        
        for name in genres_data:
            genre = Genre.query.filter_by(name=name).first()
            if not genre:
                genre = Genre(name=name)
                db.session.add(genre)
                db.session.commit()
                print(f"Genre '{name}' created.")

        # Seed Users
        users_data = [
            {
                'login': 'admin',
                'password': 'admin',
                'last_name': 'Иванов',
                'first_name': 'Иван',
                'middle_name': 'Иванович',
                'role_name': 'Администратор'
            },
            {
                'login': 'moderator',
                'password': 'moderator',
                'last_name': 'Петров',
                'first_name': 'Петр',
                'middle_name': 'Петрович',
                'role_name': 'Модератор'
            },
            {
                'login': 'user',
                'password': 'user',
                'last_name': 'Сидоров',
                'first_name': 'Сидор',
                'middle_name': 'Сидорович',
                'role_name': 'Пользователь'
            }
        ]

        for user_info in users_data:
            user = User.query.filter_by(login=user_info['login']).first()
            if not user:
                user = User(
                    login=user_info['login'],
                    last_name=user_info['last_name'],
                    first_name=user_info['first_name'],
                    middle_name=user_info['middle_name'],
                    role_id=roles[user_info['role_name']].id
                )
                user.set_password(user_info['password'])
                db.session.add(user)
                db.session.commit()
                print(f"User '{user.login}' created.")

        print("Database successfully seeded.")

if __name__ == '__main__':
    seed_db()
