from functools import wraps
from typing import List
from flask import Flask, render_template, redirect, url_for, flash, abort
from flask_bootstrap import Bootstrap5
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, current_user, login_user, UserMixin, logout_user, login_required
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
from sqlalchemy import Integer, String, Text, select, ForeignKey
from flask_ckeditor import CKEditor
from datetime import date
from forms import CreatePostForm, LoginForm, RegisterForm
from werkzeug.security import generate_password_hash, check_password_hash
from dotenv import load_dotenv
import os

load_dotenv()


# Initializing Website name as 'app'
app = Flask(__name__)
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY')
ckeditor = CKEditor(app)
Bootstrap5(app)


# Base Class to Create table in database
class Base(DeclarativeBase):
    pass


# Creating Database Called 'post.db'
app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv('DATABASE_URL')
db = SQLAlchemy(model_class=Base)
db.init_app(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'


# Crea
class User(UserMixin, db.Model):
    __tablename__ = 'users'
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    username: Mapped[str] = mapped_column(String(250), nullable=False)
    email: Mapped[str] = mapped_column(String(250), unique=True, nullable=False)
    password: Mapped[str] = mapped_column(String(250), nullable=False)

    blog_posts: Mapped[List['BlogPost']] = relationship('BlogPost', back_populates='author', cascade="all, delete")

    def __repr__(self):
        return f'{self.username}'


class BlogPost(db.Model):
    __tablename__ = "blog_posts"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)

    user_id: Mapped[int] = mapped_column(ForeignKey('users.id'), nullable=False)
    author: Mapped['User'] = relationship('User', back_populates='blog_posts')

    title: Mapped[str] = mapped_column(String(250), unique=True, nullable=False)
    subtitle: Mapped[str] = mapped_column(String(250), nullable=False)
    date: Mapped[str] = mapped_column(String(250), nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)

    img_url: Mapped[str] = mapped_column(String(250), nullable=False)


@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, int(user_id))


def admin_or_author(f):
    @wraps(f)
    def decorated_function(post_id, *args, **kwargs):
        post = db.get_or_404(BlogPost, post_id)
        if not current_user.is_authenticated or (current_user != 1 and current_user.id != post.user_id):
            abort(403)
        return f(post_id, *args, **kwargs)

    return decorated_function


with app.app_context():
    db.create_all()


@app.route('/')
def get_all_posts():
    result = db.session.execute(select(BlogPost))
    posts = result.scalars().all()
    print(current_user.is_authenticated)
    return render_template("index.html", all_posts=posts, logged=current_user.is_authenticated)


@app.route('/login', methods=['GET', 'POST'])
def login():
    form = LoginForm()
    if form.validate_on_submit():
        email = form.email.data
        user = db.session.execute((select(User).where(User.email == email))).scalar_one_or_none()
        if user:
            if check_password_hash(pwhash=user.password, password=form.password.data):
                login_user(user)
                return redirect(url_for('get_all_posts'))
            else:
                flash(message="Incorrect Password!", category='danger')
        else:
            flash(message="Email doesn't exist !", category='danger')
            return redirect(url_for('register'))
    return render_template('login.html', form=form)


@app.route('/register', methods=['GET', 'POST'])
def register():
    form = RegisterForm()
    if form.validate_on_submit():
        email = form.email.data
        email_exist = db.session.execute(select(User).where(User.email == email)).scalar()
        if email_exist:
            flash(message='Already Logged in', category='danger')
            return redirect(url_for('login'))
        password = generate_password_hash(method='pbkdf2:sha256', password=form.password.data, salt_length=8)
        new_user = User(
            username=form.username.data,
            email=form.email.data,
            password=password
        )
        db.session.add(new_user)
        db.session.commit()
        print(current_user)
        login_user(new_user)
        return redirect(url_for('get_all_posts'))
    return render_template('register.html', form=form)


@app.route('/logout')
def logout():
    logout_user()
    return redirect(url_for('get_all_posts'))


@app.route("/post/<int:post_id>")
def show_post(post_id):
    requested_post = db.get_or_404(BlogPost, post_id)
    return render_template("post.html", post=requested_post)


@login_required
@app.route("/new-post", methods=["GET", "POST"])
def add_new_post():
    form = CreatePostForm()
    if form.validate_on_submit():
        new_post = BlogPost(
            title=form.title.data,
            subtitle=form.subtitle.data,
            body=form.body.data,
            img_url=form.img_url.data,
            author=current_user,
            date=date.today().strftime("%B %d, %Y")
        )
        db.session.add(new_post)
        db.session.commit()
        return redirect(url_for("get_all_posts"))
    return render_template("make-post.html", form=form)


@login_required
@app.route("/edit-post/<int:post_id>", methods=["GET", "POST"])
@admin_or_author
def edit_post(post_id):
    post = db.get_or_404(BlogPost, post_id)
    edit_form = CreatePostForm(
        title=post.title,
        subtitle=post.subtitle,
        img_url=post.img_url,
        author=post.author.username,
        body=post.body
    )
    if edit_form.validate_on_submit():
        post.title = edit_form.title.data
        post.subtitle = edit_form.subtitle.data
        post.img_url = edit_form.img_url.data
        post.author = current_user
        post.body = edit_form.body.data
        db.session.commit()
        return redirect(url_for("show_post", post_id=post.id))
    return render_template("make-post.html", form=edit_form, is_edit=True)


@app.route("/delete/<int:post_id>")
@admin_or_author
def delete_post(post_id):
    post_to_delete = db.get_or_404(BlogPost, post_id)
    user = db.session.execute(select(User))
    db.session.delete(post_to_delete)
    db.session.commit()
    return redirect(url_for('get_all_posts'))


@app.route("/about")
def about():
    return render_template("about.html")


@app.route("/contact")
def contact():
    return render_template("contact.html")


if __name__ == "__main__":
    app.run(debug=True, port=500)
