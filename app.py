"""
Flask frontend application.
Handles template rendering and frontend routes.
"""
import os
from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify
from flask_jwt_extended import JWTManager, create_access_token, jwt_required, get_jwt_identity
from flask_sqlalchemy import SQLAlchemy
from datetime import timedelta

# Initialize Flask app
app = Flask(__name__, 
    template_folder='templates',
    static_folder='static')

# Configuration
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'your-secret-key-change-in-production')
app.config['JWT_SECRET_KEY'] = os.environ.get('JWT_SECRET_KEY', 'your-jwt-secret-key-change-in-production')
app.config['JWT_ACCESS_TOKEN_EXPIRES'] = timedelta(hours=24)

# Note: Client does NOT connect to database directly - it calls the API server
# This is a frontend-only Flask app that renders templates

# Stripe Configuration
app.config['STRIPE_PUBLISHABLE_KEY'] = os.environ.get('STRIPE_PUBLISHABLE_KEY', '')

# Initialize extensions
# Note: No database needed for frontend - it calls the API
jwt = JWTManager(app)

# Helper functions
def get_categories():
    """Get all categories."""
    try:
        response = requests.get('http://localhost:5000/api/categories')
        if response.status_code == 200:
            return response.json().get('categories', [])
    except:
        pass
    return []

def get_featured_products():
    """Get featured products."""
    try:
        response = requests.get('http://localhost:5000/api/products/featured')
        if response.status_code == 200:
            return response.json().get('products', [])
    except:
        pass
    return []

def get_cart_count():
    """Get cart item count."""
    if 'user_id' in session:
        try:
            response = requests.get(
                'http://localhost:5000/api/cart',
                headers={'Authorization': f'Bearer {session.get("access_token")}'}
            )
            if response.status_code == 200:
                return response.json().get('total_items', 0)
        except:
            pass
    return 0


# Routes
@app.route('/')
def index():
    """Homepage."""
    # Get featured products from API
    featured_products = []
    categories = []
    
    try:
        import requests
        # Try to get data from backend API
        try:
            response = requests.get('http://localhost:5000/api/products/featured', timeout=2)
            if response.status_code == 200:
                featured_products = response.json().get('products', [])
        except:
            pass
        
        try:
            cat_response = requests.get('http://localhost:5000/api/categories', timeout=2)
            if cat_response.status_code == 200:
                categories = cat_response.json().get('categories', [])
        except:
            pass
    except ImportError:
        pass
    
    cart_count = session.get('cart_count', 0)
    
    return render_template('index.html', 
                         featured_products=featured_products,
                         categories=categories,
                         cart_count=cart_count)


@app.route('/products')
def products():
    """Product listing page."""
    page = request.args.get('page', 1, type=int)
    per_page = 12
    category = request.args.get('category', '')
    search = request.args.get('search', '')
    sort = request.args.get('sort', 'created_at')
    
    products_data = {'items': [], 'pages': 1, 'page': 1}
    categories_list = []
    
    try:
        import requests
        # Build query parameters
        params = {'page': page, 'per_page': per_page, 'sort': sort}
        if category and category != 'all':
            params['category'] = category
        if search:
            params['search'] = search
            
        try:
            response = requests.get('http://localhost:5000/api/products', params=params, timeout=2)
            if response.status_code == 200:
                products_data = response.json()
        except:
            pass
        
        try:
            cat_response = requests.get('http://localhost:5000/api/categories', timeout=2)
            if cat_response.status_code == 200:
                categories_list = cat_response.json().get('categories', [])
        except:
            pass
    except ImportError:
        pass
    
    cart_count = session.get('cart_count', 0)
    
    return render_template('products.html',
                         products=products_data,
                         categories=categories_list,
                         selected_category=category,
                         search_query=search,
                         sort=sort,
                         cart_count=cart_count)


@app.route('/product/<int:product_id>')
def product_detail(product_id):
    """Product detail page."""
    product = None
    related_products = []
    
    try:
        import requests
        try:
            response = requests.get(f'http://localhost:5000/api/products/{product_id}', timeout=2)
            if response.status_code == 200:
                product = response.json().get('product')
        except:
            pass
        
        if product:
            try:
                # Get related products from same category
                related_response = requests.get(
                    'http://localhost:5000/api/products',
                    params={'category': product.get('category_id'), 'per_page': 4},
                    timeout=2
                )
                if related_response.status_code == 200:
                    related_products = related_response.json().get('items', [])
                    # Remove current product from related
                    related_products = [p for p in related_products if p.get('id') != product_id]
            except:
                pass
    except ImportError:
        pass
    
    cart_count = session.get('cart_count', 0)
    
    return render_template('product_detail.html',
                         product=product,
                         related_products=related_products[:4],
                         cart_count=cart_count)


@app.route('/cart')
def cart():
    """Shopping cart page."""
    cart_items = []
    total_price = 0
    
    if 'user_id' in session:
        try:
            import requests
            response = requests.get(
                'http://localhost:5000/api/cart',
                headers={'Authorization': f'Bearer {session.get("access_token")}'},
                timeout=2
            )
            if response.status_code == 200:
                data = response.json()
                cart_items = data.get('cart_items', [])
                total_price = data.get('total_price', 0)
        except:
            pass
    
    cart_count = session.get('cart_count', 0)
    
    return render_template('cart.html',
                         cart_items=cart_items,
                         total_price=total_price,
                         cart_count=cart_count)


@app.route('/checkout')
def checkout():
    """Checkout page."""
    if 'user_id' not in session:
        flash('Please login to checkout', 'error')
        return redirect(url_for('login'))
    
    cart_items = []
    total_price = 0
    final_total = 0
    
    if 'user_id' in session:
        try:
            import requests
            response = requests.get(
                'http://localhost:5000/api/cart',
                headers={'Authorization': f'Bearer {session.get("access_token")}'},
                timeout=2
            )
            if response.status_code == 200:
                data = response.json()
                cart_items = data.get('cart_items', [])
                total_price = data.get('total_price', 0)
                
                # Calculate final total
                shipping = 0 if total_price > 500 else 49.99
                tax = total_price * 0.08
                final_total = total_price + shipping + tax
        except:
            pass
    
    if not cart_items:
        flash('Your cart is empty', 'error')
        return redirect(url_for('cart'))
    
    cart_count = session.get('cart_count', 0)
    stripe_key = app.config['STRIPE_PUBLISHABLE_KEY']
    
    return render_template('checkout.html',
                         cart_items=cart_items,
                         total_price=total_price,
                         final_total=final_total,
                         cart_count=cart_count,
                         stripe_publishable_key=stripe_key)


@app.route('/success')
def success():
    """Payment success page."""
    order_id = request.args.get('order_id')
    order = None
    
    if order_id and 'user_id' in session:
        try:
            import requests
            response = requests.get(
                f'http://localhost:5000/api/orders/{order_id}',
                headers={'Authorization': f'Bearer {session.get("access_token")}'},
                timeout=2
            )
            if response.status_code == 200:
                order = response.json().get('order')
        except:
            pass
    
    cart_count = session.get('cart_count', 0)
    
    return render_template('success.html', order=order, cart_count=cart_count)


@app.route('/failure')
def failure():
    """Payment failure page."""
    error_message = request.args.get('error', 'Payment was not completed')
    cart_count = session.get('cart_count', 0)
    
    return render_template('failure.html', error_message=error_message, cart_count=cart_count)


# Auth routes
@app.route('/login', methods=['GET', 'POST'])
def login():
    """Login page."""
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        
        try:
            import requests
            response = requests.post(
                'http://localhost:5000/api/auth/login',
                json={'email': email, 'password': password},
                timeout=5
            )
            
            if response.status_code == 200:
                data = response.json()
                session['user_id'] = data['user']['id']
                session['user_name'] = data['user']['name']
                session['user_email'] = data['user']['email']
                session['is_admin'] = data['user']['is_admin']
                session['access_token'] = data['access_token']
                session['cart_count'] = 0
                
                flash('Login successful!', 'success')
                return redirect(url_for('index'))
            else:
                error = response.json().get('error', 'Login failed')
                flash(error, 'error')
        except Exception as e:
            flash('Unable to connect to server. Please try again.', 'error')
    
    cart_count = session.get('cart_count', 0)
    return render_template('login.html', cart_count=cart_count)


@app.route('/register', methods=['GET', 'POST'])
def register():
    """Registration page."""
    if request.method == 'POST':
        name = request.form.get('name')
        email = request.form.get('email')
        password = request.form.get('password')
        confirm_password = request.form.get('confirm_password')
        
        if password != confirm_password:
            flash('Passwords do not match', 'error')
            return redirect(url_for('register'))
        
        try:
            import requests
            response = requests.post(
                'http://localhost:5000/api/auth/register',
                json={'name': name, 'email': email, 'password': password},
                timeout=5
            )
            
            if response.status_code == 201:
                flash('Registration successful! Please login.', 'success')
                return redirect(url_for('login'))
            else:
                error = response.json().get('error', 'Registration failed')
                flash(error, 'error')
        except Exception as e:
            flash('Unable to connect to server. Please try again.', 'error')
    
    cart_count = session.get('cart_count', 0)
    return render_template('register.html', cart_count=cart_count)


@app.route('/logout')
def logout():
    """Logout."""
    session.clear()
    flash('You have been logged out', 'success')
    return redirect(url_for('index'))


@app.route('/orders')
@jwt_required(optional=True)
def orders():
    """Order history page."""
    order_list = []
    
    if 'user_id' in session:
        try:
            import requests
            response = requests.get(
                'http://localhost:5000/api/orders',
                headers={'Authorization': f'Bearer {session.get("access_token")}'},
                timeout=2
            )
            if response.status_code == 200:
                order_list = response.json().get('orders', [])
        except:
            pass
    
    cart_count = session.get('cart_count', 0)
    
    return render_template('orders.html', orders=order_list, cart_count=cart_count)


@app.route('/wishlist')
@jwt_required(optional=True)
def wishlist():
    """Wishlist page."""
    wishlist_items = []
    
    if 'user_id' in session:
        try:
            import requests
            response = requests.get(
                'http://localhost:5000/api/wishlist',
                headers={'Authorization': f'Bearer {session.get("access_token")}'},
                timeout=2
            )
            if response.status_code == 200:
                wishlist_items = response.json().get('wishlist_items', [])
        except:
            pass
    
    cart_count = session.get('cart_count', 0)
    
    return render_template('wishlist.html', wishlist_items=wishlist_items, cart_count=cart_count)


# Admin routes
@app.route('/admin')
def admin_dashboard():
    """Admin dashboard."""
    if not session.get('is_admin'):
        flash('Access denied', 'error')
        return redirect(url_for('index'))
    
    stats = {'total_products': 0, 'total_orders': 0, 'total_revenue': 0, 'total_users': 0}
    recent_orders = []
    
    try:
        import requests
        # This would need admin endpoint implementation
        pass
    except:
        pass
    
    cart_count = session.get('cart_count', 0)
    
    return render_template('admin/dashboard.html', 
                         stats=stats, 
                         recent_orders=recent_orders,
                         cart_count=cart_count)


# Context processor for all templates
@app.context_processor
def inject_user():
    """Inject user info into all templates."""
    return {
        'current_user': type('obj', (object,), {
            'is_authenticated': 'user_id' in session,
            'name': session.get('user_name', ''),
            'email': session.get('user_email', ''),
            'is_admin': session.get('is_admin', False)
        })(),
        'cart_count': session.get('cart_count', 0)
    }


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5001))
    app.run(host='0.0.0.0', port=port, debug=True)
