import pytest
from app import app, db
from models import Detail, Bill, Product, Client, PaymentMethod, Category
 
def test_add_client(client):
    response = client.post('/add_client', data={
        'firstName': 'Pedro',
        'lastName': 'López',
        'address': 'Av. Siempre Viva',
        'birthDate': '1980-01-01',
        'phoneNumber': '987654321',
        'email': 'pedro.lopez@example.com'
    }, follow_redirects=True)

    assert response.status_code == 200
    with app.app_context():
        cliente = Client.query.filter_by(email='pedro.lopez@example.com').first()
        assert cliente is not None
        assert cliente.firstName == 'Pedro'
        assert cliente.lastName == 'López'

def test_add_category(client):
    response = client.post('/add_category', data={
        'categoryName': 'Electrodomésticos',
        'description': 'Productos electrónicos para el hogar'
    }, follow_redirects=True)

    assert response.status_code == 200
    with app.app_context():
        category = Category.query.filter_by(cathegoryName='Electrodomésticos').first()
        assert category is not None
        assert category.description == 'Productos electrónicos para el hogar'

def test_create_bill_with_details(client):
    with app.app_context():
        cliente = Client(firstName='Carlos', lastName='Ramírez', email='carlos.ramirez@example.com', createdAt='2024-01-01')
        metodo_pago = PaymentMethod(name='Transferencia', createdAt='2024-01-01')
        producto = Product(name='Lavadora', price=500, stock=10, FK_category=1, createdAt='2024-01-01')
        db.session.add_all([cliente, metodo_pago, producto])
        db.session.commit()

    response = client.post('/add_bill', data={
        'FK_client': cliente.PK_client,
        'FK_paymentMethod': metodo_pago.PK_paymentMethod,
        'products': [str(producto.PK_product)]
    }, follow_redirects=True)

    assert response.status_code == 200
    with app.app_context():
        factura = Bill.query.filter_by(FK_client=cliente.PK_client).first()
        assert factura is not None
        assert len(factura.details) == 1
        assert factura.details[0].product.name == 'Lavadora'

def test_update_product(client):
    with app.app_context():
        product = Product(name='Refrigerador', price=700, stock=5, FK_category=1, createdAt='2024-01-01')
        db.session.add(product)
        db.session.commit()

    response = client.post(f'/edit_product/{product.PK_product}', data={
        'name': 'Refrigerador Actualizado',
        'price': 750,
        'stock': 8,
        'category': 1
    }, follow_redirects=True)

    assert response.status_code == 200
    with app.app_context():
        updated_product = Product.query.get(product.PK_product)
        assert updated_product.name == 'Refrigerador Actualizado'
        assert updated_product.price == 750
        assert updated_product.stock == 8

def test_login_page(client):
    response = client.get('/login')
    assert response.status_code == 200
    assert b"Inicia sesion" in response.data

def test_index_page(client):
    with client:
        client.post('/login', data={'username': 'admin', 'password': 'admin'}, follow_redirects=True)
        response = client.get('/')
        assert response.status_code == 200
        assert b"Bienvenido" in response.data

def test_navigate_products(client):
    with client:
        client.post('/login', data={'username': 'admin', 'password': 'admin'}, follow_redirects=True)
        response = client.get('/products')
        assert response.status_code == 200
        assert b"Lista de Productos" in response.data

def test_user_add_client(client):
    with client:
        client.post('/login', data={'username': 'admin', 'password': 'admin'}, follow_redirects=True)
        response = client.get('/add_client')
        assert response.status_code == 200
        assert b"Agregar Cliente" in response.data


