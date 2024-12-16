from flask import Flask, render_template, request, redirect, url_for, flash, send_file, session, jsonify
from flask_login import LoginManager, login_user, logout_user, login_required, UserMixin, current_user
from sqlalchemy.sql import text
from models import db, Client, Product, Category, Detail, Bill, PaymentMethod, User
from datetime import datetime
from io import BytesIO
from functools import wraps
from fpdf import FPDF
import pdfkit
import os
import secrets
from sqlalchemy.exc import SQLAlchemyError 


# Inicializar la aplicación
app = Flask(__name__)
app.config.from_object("config.Config")
db.init_app(app)



with app.app_context():
    try:
        # Asegúrate de usar text() para las consultas SQL
        result = db.session.execute(text("SELECT 1"))
        print("Conexión a la base de datos exitosa.")
    except Exception as e:
        print(f"Error al conectar con la base de datos: {e}")


# Configuración de Flask-Login
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = "login"
login_manager.login_message = "Por favor, inicia sesión para acceder a esta página."
login_manager.login_message_category = "info"

# Modelo de Usuario para Flask-Login
class LoginUser(UserMixin):
    def __init__(self, id, name, role):
        self.id = id
        self.name = name
        self.role = role

@login_manager.user_loader
def load_user(user_id):
    user = db.session.execute(
        text("""
        SELECT u."PK_User", u."name", r."roleName"
        FROM "tbUsers" u
        JOIN "tbRoles" r ON u."FK_Role" = r."PK_Role"
        WHERE u."PK_User" = :user_id
        """),
        {"user_id": user_id}
    ).fetchone()
    if user:
        return LoginUser(user.PK_User, user.name, user.roleName)
    return None


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        # Imprimir los valores de username y password para depuración
        print(f"Intentando iniciar sesión con username: {username} y password: {password}")

        # Buscar al usuario por nombre de usuario y contraseña
        user = db.session.execute(
            text("""
            SELECT u."PK_User", u."name", u."lastName", r."roleName"
            FROM "tbUsers" u
            JOIN "tbRoles" r ON u."FK_Role" = r."PK_Role"
            WHERE LOWER(u."userName") = LOWER(:username) 
            AND u."password" = :password 
            AND (u."state" = TRUE OR u."state" = 't')
            """),
            {"username": username, "password": password}
        ).fetchone()

        # Verificar si el usuario fue encontrado
        if user:
            login_user(LoginUser(user.PK_User, f"{user.name} {user.lastName}", user.roleName), remember="remember" in request.form)
            flash("Inicio de sesión exitoso.", "success")
            return redirect(url_for('index'))
        else:
            flash("Credenciales incorrectas.", "danger")
    return render_template("login.html")

@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash("Has cerrado sesión.", "info")
    return redirect(url_for('login'))

@app.route("/")
@login_required
def index():
    return render_template("base.html", user_role=current_user.role, user_name=current_user.name)

# Decorador para roles
def role_required(*roles):
    def decorator(f):
        @wraps(f)
        @login_required
        def decorated_function(*args, **kwargs):
            if current_user.role not in roles:
                flash("No tienes permisos para acceder a esta página.", "danger")
                return redirect(url_for('index'))
            return f(*args, **kwargs)
        return decorated_function
    return decorator

# Ruta para la página principal de productos (Empleado: solo lectura)
@app.route("/products")
@login_required
@role_required("Empleado", "Administrador", "Gerente")
def index_product():
    try:
        products = Product.query.all()
        return render_template("productos/index_product.html", products=products)
    except SQLAlchemyError as e:
        flash("Error al cargar los productos. Inténtalo más tarde.", "danger")
        print(f"Error al cargar productos: {e}")
        return redirect(url_for('index'))

# Ruta para agregar un nuevo producto (solo Gerente)
@app.route('/add_product', methods=['GET', 'POST'])
@login_required
@role_required("Gerente")
def add_product():
    try:
        categories = Category.query.all()  # Cargar categorías disponibles
    except SQLAlchemyError as e:
        flash("Error al cargar las categorías. Inténtalo más tarde.", "danger")
        print(f"Error al cargar categorías: {e}")
        return redirect(url_for('index_product'))

    if request.method == 'POST':
        name = request.form.get('name')
        price = request.form.get('price')
        stock = request.form.get('stock')
        category_id = request.form.get('category')

        # Validaciones de entrada
        if not name or not price or not stock or not category_id:
            flash("Todos los campos son obligatorios.", "warning")
            return render_template("productos/add_product.html", categories=categories)

        try:
            new_product = Product(
                name=name,
                price=float(price),
                stock=int(stock),
                FK_category=int(category_id),
                createdAt=datetime.now().date(),
                updatedAt=datetime.now().date()
            )
            db.session.add(new_product)
            db.session.commit()
            flash("Producto agregado exitosamente.", "success")
            return redirect(url_for('index_product'))
        except ValueError:
            flash("Datos inválidos. Por favor, verifica los campos.", "warning")
        except SQLAlchemyError as e:
            db.session.rollback()
            flash("Error al agregar el producto. Inténtalo más tarde.", "danger")
            print(f"Error al agregar producto: {e}")
    return render_template("productos/add_product.html", categories=categories)

# Ruta para editar un producto existente (solo Gerente)
@app.route('/edit_product/<int:id>', methods=['GET', 'POST'])
@login_required
@role_required("Gerente")
def edit_product(id):
    try:
        product = Product.query.get_or_404(id)  # Obtener el producto por ID
        categories = Category.query.all()  # Obtener todas las categorías
    except SQLAlchemyError as e:
        flash("Error al cargar los datos. Inténtalo más tarde.", "danger")
        print(f"Error al cargar producto o categorías: {e}")
        return redirect(url_for('index_product'))

    if request.method == 'POST':
        product.name = request.form.get('name')
        product.price = request.form.get('price')
        product.stock = request.form.get('stock')
        product.FK_category = request.form.get('category')

        # Validaciones de entrada
        if not product.name or not product.price or not product.stock or not product.FK_category:
            flash("Todos los campos son obligatorios.", "warning")
            return render_template("productos/edit_product.html", product=product, categories=categories)

        try:
            product.updatedAt = datetime.now().date()
            db.session.commit()
            flash("Producto actualizado exitosamente.", "success")
            return redirect(url_for('index_product'))
        except ValueError:
            flash("Datos inválidos. Por favor, verifica los campos.", "warning")
        except SQLAlchemyError as e:
            db.session.rollback()
            flash("Error al actualizar el producto. Inténtalo más tarde.", "danger")
            print(f"Error al actualizar producto: {e}")
    return render_template("productos/edit_product.html", product=product, categories=categories)

# Ruta para eliminar un producto (solo Gerente)
@app.route('/delete_product/<int:id>', methods=['POST'])
@login_required
@role_required("Gerente")
def delete_product(id):
    try:
        product = Product.query.get_or_404(id)
        db.session.delete(product)
        db.session.commit()
        flash("Producto eliminado exitosamente.", "success")
    except SQLAlchemyError as e:
        db.session.rollback()
        flash("Error al eliminar el producto. Inténtalo más tarde.", "danger")
        print(f"Error al eliminar producto: {e}")
    return redirect(url_for('index_product'))


# Ruta para la página principal de clientes (Empleado, Administrador, Gerente)
@app.route("/clients")
@login_required
@role_required("Empleado", "Administrador", "Gerente")
def index_client():
    try:
        clients = Client.query.all()
        return render_template("clientes/index_client.html", clients=clients)
    except SQLAlchemyError as e:
        flash("Error al cargar la lista de clientes. Inténtalo más tarde.", "danger")
        print(f"Error al cargar clientes: {e}")
        return redirect(url_for('index'))

# Ruta para agregar un nuevo cliente (Empleado, Administrador, Gerente)
@app.route('/add_client', methods=['GET', 'POST'])
@login_required
@role_required("Empleado", "Administrador", "Gerente")
def add_client():
    if request.method == 'POST':
        first_name = request.form.get('firstName')
        last_name = request.form.get('lastName')
        address = request.form.get('address')
        birth_date = request.form.get('birthDate')
        phone_number = request.form.get('phoneNumber')
        email = request.form.get('email')

        # Validaciones
        if not all([first_name, last_name, phone_number, email]):
            flash("Por favor, completa todos los campos obligatorios.", "warning")
            return render_template("clientes/add_client.html")

        try:
            new_client = Client(
                firstName=first_name,
                lastName=last_name,
                address=address,
                birthDate=birth_date,
                phoneNumber=phone_number,
                email=email,
                createdAt=datetime.now().date(),
                updatedAt=datetime.now().date()
            )
            db.session.add(new_client)
            db.session.commit()
            flash("Cliente agregado exitosamente.", "success")
            return redirect(url_for('index_client'))
        except SQLAlchemyError as e:
            db.session.rollback()
            flash("Error al agregar el cliente. Inténtalo más tarde.", "danger")
            print(f"Error al agregar cliente: {e}")
    return render_template("clientes/add_client.html")

# Ruta para editar un cliente existente (Administrador, Gerente)
@app.route('/edit_client/<int:id>', methods=['GET', 'POST'])
@login_required
@role_required("Administrador", "Gerente")
def edit_client(id):
    try:
        client = Client.query.get_or_404(id)
    except SQLAlchemyError as e:
        flash("Error al cargar los datos del cliente. Inténtalo más tarde.", "danger")
        print(f"Error al cargar cliente: {e}")
        return redirect(url_for('index_client'))

    if request.method == 'POST':
        client.firstName = request.form.get('firstName')
        client.lastName = request.form.get('lastName')
        client.address = request.form.get('address')
        client.birthDate = request.form.get('birthDate')
        client.phoneNumber = request.form.get('phoneNumber')
        client.email = request.form.get('email')

        # Validaciones
        if not all([client.firstName, client.lastName, client.phoneNumber, client.email]):
            flash("Por favor, completa todos los campos obligatorios.", "warning")
            return render_template("clientes/edit_client.html", client=client)

        try:
            client.updatedAt = datetime.now().date()
            db.session.commit()
            flash("Cliente actualizado exitosamente.", "success")
            return redirect(url_for('index_client'))
        except SQLAlchemyError as e:
            db.session.rollback()
            flash("Error al actualizar el cliente. Inténtalo más tarde.", "danger")
            print(f"Error al actualizar cliente: {e}")
    return render_template("clientes/edit_client.html", client=client)

# Ruta para eliminar un cliente (Gerente)
@app.route('/delete_client/<int:id>', methods=['POST'])
@login_required
@role_required("Gerente")
def delete_client(id):
    try:
        client = Client.query.get_or_404(id)
        db.session.delete(client)
        db.session.commit()
        flash("Cliente eliminado exitosamente.", "success")
    except SQLAlchemyError as e:
        db.session.rollback()
        flash("Error al eliminar el cliente. Inténtalo más tarde.", "danger")
        print(f"Error al eliminar cliente: {e}")
    return redirect(url_for('index_client')) 


# Ruta para la página principal de categorías (Administrador, Gerente)
@app.route("/categories")
@login_required
@role_required("Administrador", "Gerente")
def index_category():
    try:
        categories = Category.query.all()
        return render_template("categorias/index_category.html", categories=categories)
    except SQLAlchemyError as e:
        flash("Error al cargar las categorías. Inténtalo más tarde.", "danger")
        print(f"Error al cargar categorías: {e}")
        return redirect(url_for('index'))

# Ruta para agregar una nueva categoría (Gerente)
@app.route('/add_category', methods=['GET', 'POST'])
@login_required
@role_required("Gerente")
def add_category():
    if request.method == 'POST':
        category_name = request.form.get('categoryName')
        description = request.form.get('description')

        # Validaciones
        if not category_name:
            flash("El nombre de la categoría es obligatorio.", "warning")
            return render_template("categorias/add_category.html")

        try:
            new_category = Category(
                cathegoryName=category_name,
                description=description,
                createdAt=datetime.now().date(),
                updatedAt=datetime.now().date(),
                state=True
            )
            db.session.add(new_category)
            db.session.commit()
            flash("Categoría agregada exitosamente.", "success")
            return redirect(url_for('index_category'))
        except SQLAlchemyError as e:
            db.session.rollback()
            flash("Error al agregar la categoría. Inténtalo más tarde.", "danger")
            print(f"Error al agregar categoría: {e}")
    return render_template("categorias/add_category.html")

# Ruta para editar una categoría existente (Gerente)
@app.route('/edit_category/<int:id>', methods=['GET', 'POST'])
@login_required
@role_required("Gerente")
def edit_category(id):
    try:
        category = Category.query.get_or_404(id)
    except SQLAlchemyError as e:
        flash("Error al cargar los datos de la categoría. Inténtalo más tarde.", "danger")
        print(f"Error al cargar categoría: {e}")
        return redirect(url_for('index_category'))

    if request.method == 'POST':
        category.cathegoryName = request.form.get('categoryName')
        category.description = request.form.get('description')

        # Validaciones
        if not category.cathegoryName:
            flash("El nombre de la categoría es obligatorio.", "warning")
            return render_template("categorias/edit_category.html", category=category)

        try:
            category.updatedAt = datetime.now().date()
            db.session.commit()
            flash("Categoría actualizada exitosamente.", "success")
            return redirect(url_for('index_category'))
        except SQLAlchemyError as e:
            db.session.rollback()
            flash("Error al actualizar la categoría. Inténtalo más tarde.", "danger")
            print(f"Error al actualizar categoría: {e}")
    return render_template("categorias/edit_category.html", category=category)

# Ruta para eliminar una categoría (Gerente)
@app.route('/delete_category/<int:id>', methods=['POST'])
@login_required
@role_required("Gerente")
def delete_category(id):
    try:
        category = Category.query.get_or_404(id)
        db.session.delete(category)
        db.session.commit()
        flash("Categoría eliminada exitosamente.", "success")
    except SQLAlchemyError as e:
        db.session.rollback()
        flash("Error al eliminar la categoría. Inténtalo más tarde.", "danger")
        print(f"Error al eliminar categoría: {e}")
    return redirect(url_for('index_category'))


# Ruta para mostrar todos los detalles de ventas (Administrador, Gerente)
@app.route("/details")
@login_required
@role_required("Administrador", "Gerente")
def index_details():
    try:
        details = Detail.query.all()
        return render_template("details/index_details.html", details=details)
    except SQLAlchemyError as e:
        flash("Error al cargar los detalles de ventas. Inténtalo más tarde.", "danger")
        print(f"Error al cargar detalles: {e}")
        return redirect(url_for('index'))

# Ruta para agregar un nuevo detalle de venta (Administrador, Gerente)
@app.route('/add_detail', methods=['GET', 'POST'])
@login_required
@role_required("Administrador", "Gerente")
def add_detail():
    try:
        bills = Bill.query.all()
        products = Product.query.all()
    except SQLAlchemyError as e:
        flash("Error al cargar las facturas o productos. Inténtalo más tarde.", "danger")
        print(f"Error al cargar datos para agregar detalle: {e}")
        return redirect(url_for('index_details'))

    if request.method == 'POST':
        FK_bill = request.form.get('FK_bill')
        FK_producto = request.form.get('FK_producto')

        # Validaciones
        if not FK_bill or not FK_producto:
            flash("Por favor, selecciona una factura y un producto.", "warning")
            return render_template("details/add_detail.html", bills=bills, products=products)

        try:
            new_detail = Detail(
                FK_bill=int(FK_bill),
                FK_producto=int(FK_producto),
                createdAt=datetime.now().date(),
                updatedAt=datetime.now().date(),
                state=True
            )
            db.session.add(new_detail)
            db.session.commit()
            flash("Detalle de venta agregado exitosamente.", "success")
            return redirect(url_for('index_details'))
        except ValueError:
            flash("Datos inválidos. Por favor, verifica los campos.", "warning")
        except SQLAlchemyError as e:
            db.session.rollback()
            flash("Error al agregar el detalle de venta. Inténtalo más tarde.", "danger")
            print(f"Error al agregar detalle de venta: {e}")
    return render_template("details/add_detail.html", bills=bills, products=products)

# Ruta para editar un detalle de venta existente (Administrador, Gerente)
@app.route('/edit_detail/<int:id>', methods=['GET', 'POST'])
@login_required
@role_required("Administrador", "Gerente")
def edit_detail(id):
    try:
        detail = Detail.query.get_or_404(id)
        bills = Bill.query.all()
        products = Product.query.all()
    except SQLAlchemyError as e:
        flash("Error al cargar los datos del detalle. Inténtalo más tarde.", "danger")
        print(f"Error al cargar detalle para editar: {e}")
        return redirect(url_for('index_details'))

    if request.method == 'POST':
        FK_bill = request.form.get('FK_bill')
        FK_producto = request.form.get('FK_producto')

        # Validaciones
        if not FK_bill or not FK_producto:
            flash("Por favor, selecciona una factura y un producto.", "warning")
            return render_template("details/edit_detail.html", detail=detail, bills=bills, products=products)

        try:
            detail.FK_bill = int(FK_bill)
            detail.FK_producto = int(FK_producto)
            detail.updatedAt = datetime.now().date()
            db.session.commit()
            flash("Detalle de venta actualizado exitosamente.", "success")
            return redirect(url_for('index_details'))
        except SQLAlchemyError as e:
            db.session.rollback()
            flash("Error al actualizar el detalle de venta. Inténtalo más tarde.", "danger")
            print(f"Error al actualizar detalle de venta: {e}")
    return render_template("details/edit_detail.html", detail=detail, bills=bills, products=products)

# Ruta para eliminar un detalle de venta (Gerente)
@app.route('/delete_detail/<int:id>', methods=['POST'])
@login_required
@role_required("Gerente")
def delete_detail(id):
    try:
        detail = Detail.query.get_or_404(id)
        db.session.delete(detail)
        db.session.commit()
        flash("Detalle de venta eliminado exitosamente.", "success")
    except SQLAlchemyError as e:
        db.session.rollback()
        flash("Error al eliminar el detalle de venta. Inténtalo más tarde.", "danger")
        print(f"Error al eliminar detalle de venta: {e}")
    return redirect(url_for('index_details'))

##################Ruta de facturas#########################
# Ruta para mostrar todas las facturas (Empleado, Administrador, Gerente)
@app.route("/bills")
@login_required
@role_required("Empleado", "Administrador", "Gerente")
def index_bills():
    try:
        bills = Bill.query.all()
        return render_template("bills/index_bills.html", bills=bills)
    except SQLAlchemyError as e:
        flash("Error al cargar las facturas. Inténtalo más tarde.", "danger")
        print(f"Error al cargar facturas: {e}")
        return redirect(url_for('index'))

@app.route('/add_bill', methods=['GET', 'POST'])
@login_required
def add_bill():
    try:
        # Convertir los objetos a diccionarios serializables
        clients = [client.to_dict() for client in Client.query.all()]
        payment_methods = [payment_method.to_dict() for payment_method in PaymentMethod.query.all()]
        products = [product.to_dict() for product in Product.query.all()]
    except Exception as e:
        flash(f"Error al cargar los datos: {e}", "danger")
        return redirect(url_for('index'))

    if request.method == 'POST':
        FK_client = request.form.get('FK_client')
        FK_paymentMethod = request.form.get('FK_paymentMethod')
        selected_products = request.form.getlist('products')

        if not FK_client or not FK_paymentMethod or not selected_products:
            flash("Por favor, selecciona un cliente, un método de pago y al menos un producto.", "warning")
            return render_template("bills/add_bill.html", clients=clients, payment_methods=payment_methods, products=products)

        try:
            new_bill = Bill(
                FK_client=int(FK_client),
                FK_paymentMethod=int(FK_paymentMethod),
                date=datetime.now().date(),
                createdAt=datetime.now(),
                updatedAt=datetime.now(),
                state=True
            )
            db.session.add(new_bill)
            db.session.flush()  # Permite obtener el PK de la factura antes del commit

            for product_id in selected_products:
                new_detail = Detail(
                    FK_bill=new_bill.PK_bill,
                    FK_producto=int(product_id),
                    createdAt=datetime.now(),
                    updatedAt=datetime.now(),
                    state=True
                )
                db.session.add(new_detail)

            db.session.commit()
            flash("Factura creada exitosamente.", "success")
            return redirect(url_for('index'))
        except Exception as e:
            db.session.rollback()
            flash(f"Error al crear la factura: {e}", "danger")

    return render_template("bills/add_bill.html", clients=clients, payment_methods=payment_methods, products=products)

@app.route('/edit_bill/<int:id>', methods=['GET', 'POST'])
@login_required
@role_required("Administrador", "Gerente")
def edit_bill(id):
    try:
        bill = Bill.query.get_or_404(id)

        # Convertir los objetos a diccionarios serializables
        clients = [client.to_dict() for client in Client.query.all()]
        payment_methods = [payment_method.to_dict() for payment_method in PaymentMethod.query.all()]
        products = [product.to_dict() for product in Product.query.all()]
        selected_products = [detail.FK_producto for detail in bill.details]

        # Generar token manual para proteger el formulario
        if 'form_token' not in session:
            session['form_token'] = secrets.token_hex(16)
        form_token = session['form_token']
    except SQLAlchemyError as e:
        flash("Error al cargar los datos de la factura. Inténtalo más tarde.", "danger")
        print(f"Error al cargar factura para editar: {e}")
        return redirect(url_for('index_bills'))

    if request.method == 'POST':
        # Verificar el token manual
        if request.form.get('form_token') != session.get('form_token'):
            flash("Token de seguridad inválido. Por favor, intenta de nuevo.", "danger")
            return redirect(url_for('edit_bill', id=id))

        # Limpiar token de la sesión después de usarlo
        session.pop('form_token', None)

        FK_client = request.form.get('FK_client')
        FK_paymentMethod = request.form.get('FK_paymentMethod')
        selected_products_new = request.form.getlist('products')

        if not FK_client or not FK_paymentMethod or not selected_products_new:
            flash("Por favor, completa todos los campos.", "warning")
            return render_template(
                "bills/edit_bill.html",
                bill=bill,
                clients=clients,
                payment_methods=payment_methods,
                products=products,
                selected_products=selected_products,
                form_token=form_token,
            )

        try:
            # Actualizar datos de la factura
            bill.FK_client = int(FK_client)
            bill.FK_paymentMethod = int(FK_paymentMethod)
            bill.updatedAt = datetime.now()

            # Actualizar detalles (productos)
            existing_details = {detail.FK_producto for detail in bill.details}
            new_details = set(map(int, selected_products_new))

            # Agregar nuevos productos
            for product_id in new_details - existing_details:
                new_detail = Detail(
                    FK_bill=bill.PK_bill,
                    FK_producto=product_id,
                    createdAt=datetime.now(),
                    updatedAt=datetime.now(),
                    state=True
                )
                db.session.add(new_detail)

            # Eliminar productos no seleccionados
            for detail in bill.details:
                if detail.FK_producto not in new_details:
                    db.session.delete(detail)

            db.session.commit()
            flash("Factura actualizada exitosamente.", "success")
            return redirect(url_for('index_bills'))
        except (ValueError, SQLAlchemyError) as e:
            db.session.rollback()
            flash("Error al actualizar la factura. Inténtalo más tarde.", "danger")
            print(f"Error al actualizar factura: {e}")
    return render_template(
        "bills/edit_bill.html",
        bill=bill,
        clients=clients,
        payment_methods=payment_methods,
        products=products,
        selected_products=selected_products,
        form_token=form_token,
    )


# Ruta para ver una factura (Empleado, Administrador, Gerente)
@app.route("/bill/<int:id>")
@login_required
@role_required("Empleado", "Administrador", "Gerente")
def bill(id):
    try:
        bill = Bill.query.get_or_404(id)
        details = Detail.query.filter_by(FK_bill=id).all()

        # Procesar detalles para agregar información faltante
        processed_details = []
        for detail in details:
            product = detail.product
            detail_data = {
                "product_name": product.name,
                "unit_price": product.price,
                "quantity": 1,  # Valor por defecto para cantidad
                "total": product.price * 1  # Total calculado
            }
            processed_details.append(detail_data)

        return render_template("bills/bill.html", bill=bill, details=processed_details)
    except SQLAlchemyError as e:
        flash("Error al cargar los detalles de la factura. Inténtalo más tarde.", "danger")
        print(f"Error al cargar factura: {e}")
        return redirect(url_for('index_bills'))

@app.route("/bill/<int:id>/pdf")
@login_required
@role_required("Administrador", "Gerente")
def bill_pdf(id):
    try:
        # Obtener la factura
        bill = Bill.query.get_or_404(id)

        # Verificar que los datos esenciales existen
        if not bill.client or not bill.payment_method:
            flash("Datos incompletos en la factura. No se puede generar el PDF.", "warning")
            return redirect(url_for('bill', id=id))

        # Obtener los detalles de la factura
        details = Detail.query.filter_by(FK_bill=id).all()

        if not details:
            flash("La factura no tiene detalles de productos.", "warning")
            return redirect(url_for('bill', id=id))

        # Crear el PDF
        pdf = FPDF()
        pdf.add_page()
        pdf.set_auto_page_break(auto=True, margin=15)

        # Encabezado
        pdf.set_font("Arial", style="B", size=14)
        pdf.cell(200, 10, txt="Mi Empresa S.A.", ln=True, align="C")
        pdf.set_font("Arial", size=10)
        pdf.cell(200, 10, txt="Factura Comercial", ln=True, align="C")
        pdf.ln(10)

        # Información del cliente y factura
        pdf.set_font("Arial", style="B", size=12)
        pdf.cell(200, 8, txt=f"Factura N° {bill.PK_bill}", ln=True, align="L")
        pdf.set_font("Arial", size=10)
        pdf.cell(100, 8, txt=f"Cliente: {bill.client.firstName} {bill.client.lastName}")
        pdf.cell(100, 8, txt=f"Método de Pago: {bill.payment_method.name}", ln=True, align="R")
        pdf.cell(100, 8, txt=f"Fecha de Emisión: {bill.date.strftime('%d/%m/%Y')}", ln=True)
        pdf.ln(5)

        # Línea divisoria
        pdf.set_draw_color(169, 169, 169)
        pdf.set_line_width(0.5)
        pdf.line(10, pdf.get_y(), 200, pdf.get_y())
        pdf.ln(5)

        # Tabla de detalles
        pdf.set_font("Arial", style="B", size=10)
        pdf.cell(80, 8, txt="Producto", border=1, align="C")
        pdf.cell(40, 8, txt="Precio Unitario", border=1, align="C")
        pdf.cell(30, 8, txt="Cantidad", border=1, align="C")
        pdf.cell(40, 8, txt="Total", border=1, align="C")
        pdf.ln(8)

        # Detalles de los productos
        pdf.set_font("Arial", size=10)
        total_factura = 0
        for detail in details:
            product = detail.product  # Obtener el producto relacionado
            if not product:
                flash("Error: Producto relacionado no encontrado.", "danger")
                return redirect(url_for('bill', id=id))

            cantidad = 1  # Como no hay atributo `quantity`, asumimos que siempre es 1
            total_item = product.price * cantidad
            total_factura += total_item

            pdf.cell(80, 8, txt=product.name, border=1)
            pdf.cell(40, 8, txt=f"{product.price:.2f} Bs", border=1, align="C")
            pdf.cell(30, 8, txt=str(cantidad), border=1, align="C")
            pdf.cell(40, 8, txt=f"{total_item:.2f} Bs", border=1, align="C")
            pdf.ln(8)

        # Total de la factura
        pdf.set_font("Arial", style="B", size=12)
        pdf.ln(5)
        pdf.cell(150, 8, txt="Total Factura:", align="R")
        pdf.cell(40, 8, txt=f"{total_factura:.2f} Bs", border=1, align="C")

        # Pie de página
        pdf.set_y(-30)
        pdf.set_font("Arial", style="I", size=8)
        pdf.cell(200, 10, txt="Gracias por su compra. Visítenos en www.miempresa.com", ln=True, align="C")
        pdf.cell(200, 5, txt="Este documento es válido sin firma ni sello.", ln=True, align="C")

        # Guardar el PDF en memoria
        pdf_output = BytesIO()
        pdf_output.write(pdf.output(dest="S"))
        pdf_output.seek(0)

        # Enviar el PDF como respuesta
        return send_file(
            pdf_output,
            download_name=f"factura_{bill.PK_bill}.pdf",
            as_attachment=True,
            mimetype="application/pdf"
        )
    except Exception as e:
        flash("Error al generar el PDF. Inténtalo más tarde.", "danger")
        print(f"Error en bill_pdf: {e}")
        return redirect(url_for('index_bills'))


# Ruta para mostrar todos los métodos de pago (Empleado, Administrador, Gerente)
@app.route("/payment_methods")
@login_required
@role_required("Empleado", "Administrador", "Gerente")
def index_payment_methods():
    try:
        payment_methods = PaymentMethod.query.all()
        return render_template("payment_methods/index_payment_methods.html", payment_methods=payment_methods)
    except SQLAlchemyError as e:
        flash("Error al cargar los métodos de pago. Inténtalo más tarde.", "danger")
        print(f"Error al cargar métodos de pago: {e}")
        return redirect(url_for('index'))

# Ruta para agregar un nuevo método de pago (Administrador, Gerente)
@app.route('/add_payment_method', methods=['GET', 'POST'])
@login_required
@role_required("Administrador", "Gerente")
def add_payment_method():
    if request.method == 'POST':
        name = request.form.get('name')
        anotherDetails = request.form.get('anotherDetails')

        if not name:
            flash("El nombre del método de pago es obligatorio.", "warning")
            return render_template('payment_methods/add_payment_method.html')

        try:
            new_payment_method = PaymentMethod(
                name=name,
                anotherDetails=anotherDetails,
                createdAt=datetime.now().date(),
                updatedAt=datetime.now().date(),
                state=True
            )
            db.session.add(new_payment_method)
            db.session.commit()
            flash("Método de pago agregado exitosamente.", "success")
            return redirect(url_for('index_payment_methods'))
        except SQLAlchemyError as e:
            db.session.rollback()
            flash("Error al agregar el método de pago. Inténtalo más tarde.", "danger")
            print(f"Error al agregar método de pago: {e}")
    return render_template('payment_methods/add_payment_method.html')

# Ruta para editar un método de pago existente (Administrador, Gerente)
@app.route('/edit_payment_method/<int:id>', methods=['GET', 'POST'])
@login_required
@role_required("Administrador", "Gerente")
def edit_payment_method(id):
    try:
        payment_method = PaymentMethod.query.get_or_404(id)
    except SQLAlchemyError as e:
        flash("Error al cargar los datos del método de pago. Inténtalo más tarde.", "danger")
        print(f"Error al cargar método de pago: {e}")
        return redirect(url_for('index_payment_methods'))

    if request.method == 'POST':
        payment_method.name = request.form.get('name')
        payment_method.anotherDetails = request.form.get('anotherDetails')

        if not payment_method.name:
            flash("El nombre del método de pago es obligatorio.", "warning")
            return render_template("payment_methods/edit_payment_method.html", payment_method=payment_method)

        try:
            payment_method.updatedAt = datetime.now().date()
            db.session.commit()
            flash("Método de pago actualizado exitosamente.", "success")
            return redirect(url_for('index_payment_methods'))
        except SQLAlchemyError as e:
            db.session.rollback()
            flash("Error al actualizar el método de pago. Inténtalo más tarde.", "danger")
            print(f"Error al actualizar método de pago: {e}")
    return render_template('payment_methods/edit_payment_method.html', payment_method=payment_method)

# Ruta para eliminar un método de pago (Administrador, Gerente)
@app.route('/delete_payment_method/<int:id>', methods=['POST'])
@login_required
@role_required("Administrador", "Gerente")
def delete_payment_method(id):
    try:
        payment_method = PaymentMethod.query.get_or_404(id)
        db.session.delete(payment_method)
        db.session.commit()
        flash("Método de pago eliminado exitosamente.", "success")
    except SQLAlchemyError as e:
        db.session.rollback()
        flash("Error al eliminar el método de pago. Inténtalo más tarde.", "danger")
        print(f"Error al eliminar método de pago: {e}")
    return redirect(url_for('index_payment_methods'))



if __name__ == "__main__":
    app.run(debug=True)
app = app  # Exporta la aplicación como variable global
