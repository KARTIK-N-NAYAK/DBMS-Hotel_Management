from flask import Flask
import os

FOLDER_PATH = os.path.realpath(__file__)[:-7]

app = Flask(__name__)
app.config["SECRET_KEY"] = r'BG:Na}O9C-$N2LL=[nDF_@.8:,$Y[G"D?A5@qb<@'

from routes import *

if __name__=="__main__":
	app.run(debug=True)
