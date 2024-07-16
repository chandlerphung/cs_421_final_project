from flask import Flask, redirect, url_for, render_template, request, session
from flask_sqlalchemy import SQLAlchemy
from werkzeug.utils import secure_filename
import os

app = Flask(__name__)
app.secret_key = "hello"
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///users.sqlite3'
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
app.config['UPLOAD_FOLDER'] = 'static/uploads'
app.config['ALLOWED_EXTENSIONS'] = {'png', 'jpg', 'jpeg', 'gif'}

db = SQLAlchemy(app)

class Users(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(100))
    password = db.Column(db.String(100))
    bio = db.Column(db.String(100))
    image = db.Column(db.String(100), nullable=True)

    def __init__(self, username, password, image=None, bio=None):
        self.username = username
        self.password = password
        self.image = image
        self.bio = bio

class Follower(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    followee_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    follower_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    is_pending = db.Column(db.Boolean, default=False)
    is_friend = db.Column(db.Boolean, default=False)

    follower = db.relationship('Users', foreign_keys=[follower_id], backref=db.backref('following', cascade='all, delete-orphan'))
    followee = db.relationship('Users', foreign_keys=[followee_id], backref='followers')

    def __init__(self, followee_id, follower_id, is_pending=False, is_friend=False):
        self.followee_id = followee_id
        self.follower_id = follower_id
        self.is_pending = is_pending
        self.is_friend = is_friend
    
class Posts(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user = db.Column(db.String(100))
    caption = db.Column(db.String(100))
    file = db.Column(db.String(100), nullable=True)

    def __init__(self, user, caption, file=None):
        self.user = user
        self.caption = caption
        self.file = file

class Comments(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    post_id = db.Column(db.Integer, db.ForeignKey('posts.id'), nullable=False)
    user = db.Column(db.String(100))
    comment = db.Column(db.String(500))

    def __init__(self, post_id, user, comment):
        self.post_id = post_id
        self.user = user
        self.comment = comment

class Likes(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    post_id = db.Column(db.Integer, db.ForeignKey('posts.id'), nullable=False)
    user = db.Column(db.String(100))

    def __init__(self, post_id, user):
        self.post_id = post_id
        self.user = user

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in app.config['ALLOWED_EXTENSIONS']

@app.route("/", methods=["POST", "GET"])
def home():
    if request.method == "POST":
        username = request.form.get("username")
        password = request.form.get("password")

        existing_user = Users.query.filter_by(username=username).first()

        if existing_user:
            return render_template("index.html", message="Username already exists. Please choose a different username.")
        
        if not username or not password:
            return redirect(url_for("home"))
        else:
            session["username"] = username
            session["password"] = password
            user = Users(username, password)
            db.session.add(user)
            db.session.commit()
            return redirect(url_for("login"))
    else:
        return render_template("index.html")

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username")
        password = request.form.get("password")
        session["username"] = username
        session["password"] = password
        found_user = Users.query.filter_by(username=username, password=password).first()
        if found_user:
            session['logged_in'] = True
            return redirect(url_for("main"))
    return render_template("login.html")

@app.route("/friends")
def friends():
    if 'logged_in' not in session:
        return redirect(url_for('login'))
    
    user = session["username"]
    id = Users.query.filter_by(username=user).first().id
    list_of_friends = Follower.query.filter_by(followee_id=id, is_friend=True).all()
    friends_ids = [friend.follower_id for friend in list_of_friends]

    friends_users = Users.query.filter(Users.id.in_(friends_ids)).all()
    friends_names = [user.username for user in friends_users]

    posts = {}
    for username in friends_names:
        user_posts = Posts.query.filter_by(user=username).all()
        for post in user_posts:
            post.likes = Likes.query.filter_by(post_id=post.id).count()
            post.comments = Comments.query.filter_by(post_id=post.id).all()
        posts[username] = user_posts

    return render_template("friends.html", friends_names=friends_names, posts=posts)


@app.route("/main", methods=["POST", "GET"])
def main():
    if 'logged_in' not in session:
        return redirect(url_for('login'))
    
    search_user = request.form.get("search_user")
    user = session["username"]
    id = Users.query.filter_by(username=user).first().id
    
    post_visible = False  # Initialize post_visible variable

    if Follower.query.filter_by(followee_id=id).all():
        post_visible = True

    if request.method == "POST":
        if search_user != session["username"]:
            user_check = Users.query.filter_by(username=search_user).first()
            if user_check:
                bio = user_check.bio
                image = user_check.image
                return render_template("search.html", name=search_user, bio=bio, image=url_for('static', filename=f'uploads/{image}'))
            else:
                return redirect(url_for("main"))  # Corrected redirect function

    if post_visible:
        return render_template("main.html", posts=Posts.query.filter_by(user=user).all())

    return render_template("main.html")


@app.route("/search", methods=["POST", "GET"])
def search():
    if 'logged_in' not in session:
        return redirect(url_for('login'))
    
    if request.method == "POST":
        followee_name = request.form.get("name")
        follower = Users.query.filter_by(username=session["username"]).first().id
        followee = Users.query.filter_by(username=followee_name).first().id
        follow = Follower(followee_id=followee, follower_id=follower, is_pending=True)
        db.session.add(follow)
        db.session.commit()
        return redirect(url_for("main"))

    return render_template("search.html")

@app.route("/follows", methods=["POST", "GET"])
def follows():
    if 'logged_in' not in session:
        return redirect(url_for('login'))
    
    user = session["username"]
    user = Users.query.filter_by(username=user).first()
    requested = Follower.query.filter_by(followee_id=user.id).all()

    if request.method == "POST":
        action = request.form.get("action")
        id = request.form.get("id")
        follower = Follower.query.filter_by(id=id).first()

        if follower:
            if action == "accept":
                follower.is_pending = False
                follower.is_friend = True
            else:
                db.session.delete(follower)
            
            db.session.commit()
            return redirect(url_for('follows'))

    return render_template("follows.html", requested=requested, Users=Users)



@app.route("/post", methods=["POST", "GET"])
def post():
    if 'logged_in' not in session:
        return redirect(url_for('login'))
    
    if request.method == "POST":
        caption = request.form.get("caption")
        user = session["username"]

        if "file" in request.files:
            file = request.files["file"]
            if file:
                filename = secure_filename(file.filename)
                file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
                new_post = Posts(user=user, caption=caption, file=filename)
                db.session.add(new_post)
                db.session.commit()
                return redirect(url_for('main'))

            else:
                new_post = Posts(user=user, caption=caption)
                db.session.add(new_post)
                db.session.commit()
                return redirect(url_for('main'))

    return render_template("post.html")

@app.route("/like_post", methods=["POST"])
def like_post():
    if 'logged_in' not in session:
        return redirect(url_for('login'))
    
    post_id = request.form.get("post_id")
    user = session["username"]

    # Check if user has already liked the post
    existing_like = Likes.query.filter_by(post_id=post_id, user=user).first()
    if not existing_like:
        new_like = Likes(post_id=post_id, user=user)
        db.session.add(new_like)
        db.session.commit()

    return redirect(url_for('friends'))

@app.route("/comment_post", methods=["POST"])
def comment_post():
    if 'logged_in' not in session:
        return redirect(url_for('login'))
    
    post_id = request.form.get("post_id")
    comment_text = request.form.get("comment")
    user = session["username"]

    new_comment = Comments(post_id=post_id, user=user, comment=comment_text)
    db.session.add(new_comment)
    db.session.commit()

    return redirect(url_for('friends'))


@app.route("/profile", methods=["POST", "GET"])
def profile():
    if 'logged_in' not in session:
        return redirect(url_for('login'))
    name = session["username"]

    user = Users.query.filter_by(username=name).first()
    image = user.image if user and user.image else 'default.png'
    bio = user.bio if user and user.bio else ''

    if request.method == "POST":
        bio_updated = False
        image_updated = False

        # Handle bio update
        if "bio" in request.form:
            bio = request.form["bio"]
            user.bio = bio
            bio_updated = True
        
        # Handle image update
        if "image" in request.files:
            file = request.files["image"]
            if file and allowed_file(file.filename):
                filename = secure_filename(file.filename)
                file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
                user.image = filename
                image_updated = True

        # Commit changes only if there were updates
        if bio_updated or image_updated:
            db.session.commit()

        return redirect(url_for('profile'))

    return render_template("profile.html", name=name, image=image, bio=bio)


@app.route("/logout")
def logout():
    session.pop("username", None)
    session.pop("logged_in", None)
    return redirect(url_for("login"))

@app.route("/view")
def view():
    return render_template("view.html", values=Users.query.all(), values2=Follower.query.all())

if __name__ == "__main__":
    if not os.path.exists('static/uploads'):
        os.makedirs('static/uploads')
    with app.app_context():
        db.create_all()
    app.run(debug=True)
