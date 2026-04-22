from flask import request
from flask import Flask, render_template
from models import User
from database import db

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///site.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

session = {}

db.init_app(app)
with app.app_context():
    db.create_all()

@app.route("/")
def hello_world():
    return render_template("home.html")

@app.route("/about")
def about():
    return render_template("about.html")

@app.route("/signup",methods=["POST","GET"])
def signup():
    if request.method == "POST":
        name = request.form.get("name")
        email = request.form.get("email")
        password = request.form.get("password")
        user=User(name=name,email=email,password=password)
        db.session.add(user)
        db.session.commit()
        return render_template("login.html")
    return render_template("signup.html")

@app.route("/login",methods=["POST","GET"])
def login():
    if request.method == "POST":
        email = request.form.get("email")
        password = request.form.get("password")
        user=User.query.filter_by(email=email,password=password).first()
        if user:
            session[user.id]=user
            print(session)
            return render_template("home.html",user=user)
        else:
            return render_template("login.html")
    return render_template("login.html")

@app.route("/logout/<int:user_id>")
def logout(user_id):
    session.pop(user_id,None)
    return render_template("Home.html",user=None)

if __name__ == "__main__":
    app.run(debug=True,host="0.0.0.0",port=5000)