"""Small apps to demonstrate endpoints with basic feature - CRUD"""

from flask import Flask
from flask_cors import CORS
from dotenv import load_dotenv
from extensions import jwt
from api.books.endpoints import books_endpoints
from api.menu.endpoints import menu_endpoints
from api.authors.endpoints import authors_endpoints
from api.auth.endpoints import auth_endpoints
from api.data_protected.endpoints import protected_endpoints
from api.Kasir.endpoints import kasir_endpoints
from api.Ruangan.endpoints import ruangan_endpoints
from api.virtualOffice.endpoints import virtualOffice_endpoints
from api.memberships.endpoints import memberships_endpoints
from api.transaksi.endpoints import transaksi_endpoints
from api.produk.endpoints import produk_endpoints

from config import Config
from static.static_file_server import static_file_server


# Load environment variables from the .env file
load_dotenv()

app = Flask(__name__)
app.config.from_object(Config)
CORS(app)


jwt.init_app(app)

# register the blueprint
app.register_blueprint(auth_endpoints, url_prefix='/api/v1/auth')
app.register_blueprint(protected_endpoints,
                       url_prefix='/api/v1/protected')
app.register_blueprint(books_endpoints, url_prefix='/api/v1/books')
app.register_blueprint(authors_endpoints, url_prefix='/api/v1/authors')
app.register_blueprint(static_file_server, url_prefix='/static/')
app.register_blueprint(menu_endpoints, url_prefix='/api/v1/menu/')
app.register_blueprint(kasir_endpoints, url_prefix='/api/v1/kasir/')
app.register_blueprint(ruangan_endpoints, url_prefix='/api/v1/ruangan/')
app.register_blueprint(virtualOffice_endpoints, url_prefix='/api/v1/virtualOffice/')
app.register_blueprint(memberships_endpoints, url_prefix='/api/v1/memberships/')
app.register_blueprint(transaksi_endpoints, url_prefix='/api/v1/transaksi/')
app.register_blueprint(produk_endpoints, url_prefix='/api/v1/produk/')



if __name__ == '__main__':
    app.run(host='127.0.0.1', debug=True, port=5000)
