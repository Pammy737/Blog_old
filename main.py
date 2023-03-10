from flask import Flask, render_template, redirect, url_for, flash, request, abort
from flask_bootstrap import Bootstrap
from flask_ckeditor import CKEditor
from datetime import date
from werkzeug.security import generate_password_hash, check_password_hash
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.orm import relationship
from sqlalchemy import ForeignKey
from flask_login import UserMixin, login_user, LoginManager, login_required, current_user, logout_user
from forms import CreatePostForm, RegisterForm, LoginForm, CommentForm
from flask_gravatar import Gravatar
from functools import wraps
from dotenv import load_dotenv
import os

app = Flask(__name__)

# load env file
load_dotenv()
app.config['SECRET_KEY'] = os.environ.get("SECRET_KEY")

# ckeditor
ckeditor = CKEditor(app)

# Bootstrap
Bootstrap(app)

##CONNECT TO DB
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///blog.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

##CONNECT TO flask-login
login_manager = LoginManager(app)
login_manager.init_app(app)

login_manager.login_view = "login"


##CONFIGURE TABLES
class User(UserMixin, db.Model):
    __tablename__ = "users"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(20), nullable=False)
    email = db.Column(db.String(250), nullable=False)
    password = db.Column(db.String(200), nullable=False)

    # User & Post
    post = relationship("BlogPost", back_populates="author")
    # User & Comment
    comment = relationship("Comment", back_populates="commenter")


class BlogPost(db.Model):
    __tablename__ = "blog_posts"
    id = db.Column(db.Integer, primary_key=True)
    # author = db.Column(db.String(250), nullable=False)

    author_id = db.Column(db.Integer, db.ForeignKey("users.id"))
    author = relationship("User", back_populates="post")  # 命名就命名 此class所需要的data

    title = db.Column(db.String(250), unique=True, nullable=False)
    subtitle = db.Column(db.String(250), nullable=False)
    date = db.Column(db.String(250), nullable=False)
    body = db.Column(db.Text, nullable=False)
    img_url = db.Column(db.String(250), nullable=False)

    # Post & Comments
    post_comment = relationship("Comment", back_populates="comment_post")


class Comment(db.Model):
    __tablename__ = "comments"
    id = db.Column(db.Integer, primary_key=True)

    # User & Comments
    commenter_id = db.Column(db.Integer, ForeignKey("users.id"))
    commenter = relationship("User", back_populates="comment")

    # Post & Comments
    comment_post_id = db.Column(db.Integer, ForeignKey("blog_posts.id"))
    comment_post = relationship("BlogPost", back_populates="post_comment")

    text = db.Column(db.String(250), nullable=False)


with app.app_context():
    db.create_all()


def admin_only(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if current_user.id != 1:
            return abort(403)
        return f(*args, **kwargs)
    return decorated_function


@app.route('/')
def home():
    posts = BlogPost.query.all()
    authors = [print(post.author) for post in posts]
    return render_template("index.html", all_posts=posts)


@app.route('/register', methods=["GET", "POST"])
def register():
    form = RegisterForm()
    if form.validate_on_submit():
        pwd = form.password.data
        new_user = User(
            name=form.name.data,
            email=form.email.data,
            password=generate_password_hash(pwd, method="pbkdf2:sha256", salt_length=8),
        )
        db.session.add(new_user)
        db.session.commit()

        return redirect(url_for('login'))
    return render_template("register.html", form=form)


@app.route('/login', methods=["GET", "POST"])
def login():
    form = LoginForm(request.values, next=request.args.get("next"))
    if form.validate_on_submit():
        user_login = User.query.filter_by(email=form.email.data).first()
        print(user_login)
        if user_login:
            pwd = form.password.data
            print(pwd)
            if check_password_hash(pwhash=user_login.password, password=pwd):
                flash("You've logged in!")
                login_user(user=user_login)
                next = request.args.get("next")
                next_url = form.next.data
                # the ones with @login_required
                if next:
                    print(next)
                    return redirect(next)
                # the ones not using login_required
                elif next_url:
                    print(next_url)
                    return redirect(next_url)
                return redirect(url_for('home'))
            else:
                flash("Wrong password! Please try again!")
                return redirect(url_for('login'))
        else:
            flash("You're not our member yet! Please sign up first!")
            return redirect(url_for('register'))
    return render_template("login.html", form=form)


@login_manager.user_loader
def load_user(user_id):
    return User.query.get(user_id)


@app.route('/logout')
@login_required
def logout():
    logout_user()
    return render_template("index.html")


@app.route("/post/<int:post_id>", methods=["GET", "POST"])
def show_post(post_id):
    requested_post = BlogPost.query.get(post_id)
    # comments
    # all_comments = Comment.query.all()
    required_comment = Comment.query.filter_by(comment_post_id=post_id)
    print(required_comment)
    gravatar = Gravatar(app,
                        size=100,
                        rating='g',
                        default='retro',
                        force_default=False,
                        force_lower=False,
                        use_ssl=False,
                        base_url=None)
    comment_form = CommentForm()
    # not allowing non-users to browse the post -> change it to not allowing non-user to comment
    if comment_form.validate_on_submit():
        if not current_user.is_anonymous:
            print(comment_form.comment.data)
            new_comment = Comment(
                commenter_id=current_user.id,
                comment_post_id=post_id,
                text=comment_form.comment.data,
            )
            db.session.add(new_comment)
            db.session.commit()
            return redirect(url_for("show_post", post_id=post_id))
        else:
            flash("Please Log in before leaving a comment!")
            return redirect(url_for("login", next=request.url))  # 將此做為參數傳遞
    return render_template("post.html", post=requested_post, form=comment_form, required_comment=required_comment)


@app.route("/about")
@login_required
def about():
    return render_template("about.html")


@app.route("/new-post", methods=["GET", "POST"])
@admin_only
def add_new_post():
    current_id = current_user.id
    form = CreatePostForm()
    if form.validate_on_submit():
        new_post = BlogPost(
            title=form.title.data,
            subtitle=form.subtitle.data,
            body=form.body.data,
            img_url=form.img_url.data,
            author_id=current_id,
            date=date.today().strftime("%B %d, %Y")
        )
        db.session.add(new_post)
        db.session.commit()
        return redirect(url_for("home"))
    return render_template("make-post.html", form=form)


@app.route("/edit-post/<int:post_id>", methods=["GET", "POST"])
@admin_only
def edit_post(post_id):
    post = BlogPost.query.get_or_404(post_id)
    edit_form = CreatePostForm(
        title=post.title,
        subtitle=post.subtitle,
        img_url=post.img_url,
        # author=post.author,
        body=post.body
    )
    if edit_form.validate_on_submit():
        post.title = edit_form.title.data
        post.subtitle = edit_form.subtitle.data
        post.img_url = edit_form.img_url.data
        # post.author = edit_form.author.data
        post.body = edit_form.body.data
        db.session.commit()
        return redirect(url_for("show_post", post_id=post.id))

    return render_template("make-post.html", form=edit_form, is_edit=True)


@app.route("/delete/<int:post_id>")
@admin_only
def delete_post(post_id):
    post_to_delete = BlogPost.query.get(post_id)
    print(post_to_delete)
    db.session.delete(post_to_delete)
    db.session.commit()
    return redirect(url_for('home'))


if __name__ == "__main__":
    app.run(debug=True)
