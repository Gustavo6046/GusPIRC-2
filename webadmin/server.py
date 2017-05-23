import flask
import glob
import os.path as path
import imp


def setup(auto_start=False):
    app = flask.Flask(__name__)

    files = glob.glob("html/*.html") + glob.glob("py/*.py")

    @app.route("/<page>")
    def get_page(page):
        if page in files:
            if page.endswith(".html"):
                return open(page).read()

            else:
                return imp.load_source(page, path.splitext(path.split(page)[-1])[0]).__page__()

    if auto_start:
        app.run()

    return app

def run():
    return setup(True)
