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
from api.produkadmin.endpoints import produkadmin_endpoints
from api.ruanganadmin.endpoints import ruanganadmin_endpoints
from api.eventspacesadmin.endpoints import eventspacesadmin_endpoints
from api.membershipadmin.endpoints import membershipadmin_endpoints
from api.virtualofficeadmin.endpoints import virtualofficeadmin_endpoints
from api.promo.endpoints import promo_endpoints
from api.promoadmin.endpoints import promoadmin_endpoints
from api.tenant.endpoints import tenant_endpoints
from api.eventSpaces.endpoints import eventspaces_endpoints
from api.tenantadmin.endpoints import tenantadmin_endpoints
from api.useradmin.endpoints import useradmin_endpoints
from api.owner.endpoints import owner_endpoints
from api.admin.endpoints import admin_endpoints
from api.acara.endpoints import acara_endpoints
from api.coadmin.endpoints import coaadmin_endpoints
from api.faq.endpoints import faq_endpoints

from config import Config
from static.static_file_server import static_file_server
from doc_endpoint.doc_file_server import doc_file_server

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
app.register_blueprint(produkadmin_endpoints, url_prefix='/api/v1/produkadmin/')
app.register_blueprint(ruanganadmin_endpoints, url_prefix='/api/v1/ruanganadmin/')
app.register_blueprint(eventspacesadmin_endpoints, url_prefix='/api/v1/eventspacesadmin/')
app.register_blueprint(membershipadmin_endpoints, url_prefix='/api/v1/membershipadmin/')
app.register_blueprint(virtualofficeadmin_endpoints, url_prefix='/api/v1/virtualofficeadmin/')
app.register_blueprint(promo_endpoints, url_prefix='/api/v1/promo/')
app.register_blueprint(promoadmin_endpoints, url_prefix='/api/v1/promoadmin/')
app.register_blueprint(tenant_endpoints, url_prefix='/api/v1/tenant/')
app.register_blueprint(eventspaces_endpoints, url_prefix='/api/v1/eventspaces/')
app.register_blueprint(tenantadmin_endpoints, url_prefix='/api/v1/tenantadmin/')
app.register_blueprint(useradmin_endpoints, url_prefix='/api/v1/useradmin/')
app.register_blueprint(owner_endpoints, url_prefix='/api/v1/owner/')
app.register_blueprint(admin_endpoints, url_prefix='/api/v1/admin/')
app.register_blueprint(doc_file_server)
app.register_blueprint(acara_endpoints, url_prefix='/api/v1/acara')
app.register_blueprint(coaadmin_endpoints, url_prefix='/api/v1/coaadmin')
app.register_blueprint(faq_endpoints, url_prefix='/api/v1/faq')

if __name__ == '__main__':
    app.run(host='127.0.0.1', debug=True, port=5000)
