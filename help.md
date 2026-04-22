1. create the virtual environment.
-- py -m venv venv
2. activate the virtual environment.
-- .\env\Scripts\activate
3. install flask
-- pip install flask

4. create a file named main.py and add the following code to it:
-- from flask import Flask

app = Flask(__name__)

@app.route("/")
def hello_world():
    return "<p>Hello, World!</p>"

if __name__ == "__main__":
    app.run(debug=True)

5. run the application.
-- py main.py
6. open a web browser and navigate to http://127.0.0.1:5000
You should see "Hello, World!" displayed on the page.

