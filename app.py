import os
import uuid
from datetime import datetime
from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, send_from_directory
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_login import LoginManager, current_user
from models import db, Customer, Service, Employee, Category, ServiceHistory, ServiceHistoryImage, Settings
from config import Config
from werkzeug.utils import secure_filename
from flask_moment import Moment
from sqlalchemy import or_, and_
import cloudinary
from cloudinary.uploader import upload as cloudinary_upload
from cloudinary.utils import cloudinary_url
from cloudinary.api import delete_resources_by_prefix, delete_resources

# Import cloudinary utils
from cloudinary_utils import configure_cloudinary, upload_to_cloudinary, delete_from_cloudinary, get_cloudinary_public_id

# Import filters
from filters import init_app as init_filters

# This is a dummy comment to force re-parsing of the file.

# Định nghĩa các phần mở rộng cho phép
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}

def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

app = Flask(__name__, static_url_path='')
app.config.from_object(Config)

# Đảm bảo thư mục uploads được phục vụ tĩnh
app.static_folder = 'static'
app.static_url_path = ''

# Khởi tạo database
db.init_app(app)

# Khởi tạo filters
init_filters(app)

# Khởi tạo Flask-Migrate
migrate = Migrate(app, db)

# Khởi tạo Flask-Login
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

# Khởi tạo Flask-Moment
moment = Moment(app)

# Cấu hình Cloudinary
configure_cloudinary(app)

# Tạo một user ảo để tương thích với code hiện tại
class DummyUser:
    def __init__(self):
        self.is_authenticated = True
        self.is_active = True
        self.is_anonymous = False
        self.role = 'admin'
        self.username = 'admin'

    def get_id(self):
        return '1'

@login_manager.user_loader
def load_user(user_id):
    return DummyUser()

# Context processor để cung cấp biến now cho tất cả các template
@app.context_processor
def inject_now_and_datetime():
    return {'now': datetime.now(), 'datetime': datetime}

@app.context_processor
def inject_moment():
    return dict(moment=moment)

# Context processor để cung cấp cài đặt cho tất cả các template
@app.context_processor
def inject_settings():
    settings = Settings.query.first()
    if not settings:
        settings = Settings() # Tạo cài đặt mặc định nếu chưa có
        db.session.add(settings)
        db.session.commit()
    return {'settings': settings}

# Tạo thư mục uploads nếu chưa tồn tại
if not os.path.exists(app.config['UPLOAD_FOLDER']):
    os.makedirs(app.config['UPLOAD_FOLDER'])

# Route tĩnh cho thư mục uploads
@app.route('/uploads/<path:filename>')
def uploaded_file(filename):
    print(f"\n=== DEBUG ===")
    print(f"Requested filename: {filename}")
    print(f"Upload folder: {app.config['UPLOAD_FOLDER']}")
    full_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
    print(f"Full path: {full_path}")
    print(f"File exists: {os.path.exists(full_path)}")
    
    try:
        return send_from_directory(app.config['UPLOAD_FOLDER'], filename)
    except Exception as e:
        print(f"Error serving {filename}: {str(e)}")
        return str(e), 404

# Tạo một đối tượng user ảo
def get_current_user():
    return DummyUser()

# Đã xóa các route đăng nhập/đăng xuất

# Routes cho trang chủ
@app.route('/')
def index():
    # Không cần đăng nhập
    
    # Lấy thống kê
    total_customers = Customer.query.count()
    total_employees = Employee.query.count()
    total_services = Service.query.count()
    total_service_history = ServiceHistory.query.count()
    
    return render_template('index.html',
                         total_customers=total_customers,
                         total_employees=total_employees,
                         total_services=total_services,
                         total_service_history=total_service_history)

# Routes cho quản lý khách hàng
@app.route('/customers')
def customer_list():
    page = request.args.get('page', 1, type=int)
    search = request.args.get('search', '')
    birth_day = request.args.get('birth_day', type=int)
    birth_month = request.args.get('birth_month', type=int)

    query = Customer.query

    if search:
        query = query.filter(or_(
            Customer.name.ilike(f'%{search}%'),
            Customer.phone.ilike(f'%{search}%')
        ))
    
    if birth_month:
        query = query.filter(db.extract('month', Customer.birth_date) == birth_month)
        if birth_day:
            query = query.filter(db.extract('day', Customer.birth_date) == birth_day)

    query = query.order_by(Customer.name.asc())

    pagination = query.paginate(
        page=page, per_page=app.config['ITEMS_PER_PAGE'], error_out=False)

    return render_template('customers/index.html',
                         customers=pagination.items,
                         pagination=pagination,
                         search=search,
                         birth_day=birth_day,
                         birth_month=birth_month)

@app.route('/customers/add', methods=['GET', 'POST'])
def customer_add():
    if request.method == 'POST':
        try:
            # Chỉ lấy các trường còn lại trên form: Họ và tên, Số điện thoại, Ngày sinh, Địa chỉ, Ghi chú
            name = request.form.get('name')
            phone = request.form.get('phone')
            birth_date_str = request.form.get('birth_date')
            address = request.form.get('address')
            notes = request.form.get('notes')

            # Xử lý ngày sinh: dd-mm-yyyy hoặc dd-mm (mặc định năm 1900)
            birth_date = None
            if birth_date_str:
                try:
                    # Thử định dạng dd-mm-yyyy
                    birth_date = datetime.strptime(birth_date_str, '%d-%m-%Y').date()
                except ValueError:
                    try:
                        # Thử định dạng dd-mm và đặt năm 1900
                        birth_date = datetime.strptime(birth_date_str, '%d-%m').date().replace(year=1900)
                    except ValueError:
                        flash('Định dạng ngày sinh không hợp lệ. Vui lòng sử dụng định dạng dd-mm hoặc dd-mm-yyyy.', 'danger')
                        return render_template('customers/add.html'), 400

            # Kiểm tra các trường bắt buộc (Họ và tên, Số điện thoại)
            if not name or not phone:
                 flash('Họ và tên và Số điện thoại là bắt buộc.', 'danger')
                 # Có thể cần truyền lại dữ liệu đã nhập và thông báo lỗi cụ thể hơn
                 return render_template('customers/add.html'), 400

            customer = Customer(
                name=name,
                phone=phone,
                birth_date=birth_date,
                address=address,
                notes=notes,
                # Status sẽ nhận giá trị mặc định từ model (active)
                # email sẽ nhận giá trị mặc định là NULL từ model (vì đã xóa khỏi form và DB)
            )
            db.session.add(customer)
            db.session.commit()
            flash('Thêm khách hàng thành công!', 'success')
            return redirect(url_for('customer_list'))
        except Exception as e:
            db.session.rollback()
            print(f"Error adding customer: {e}") # In lỗi chi tiết hơn để debug
            flash(f'Có lỗi xảy ra: {str(e)}', 'danger')
            # Có thể cần truyền lại dữ liệu đã nhập
            return render_template('customers/add.html'), 400

    return render_template('customers/add.html')

@app.route('/customers/<int:id>/edit', methods=['GET', 'POST'])
def customer_edit(id):
    customer = Customer.query.get_or_404(id)
    
    if request.method == 'POST':
        try:
            # Lấy dữ liệu từ form, sử dụng .get() cho tất cả các trường
            customer.name = request.form.get('name')
            customer.phone = request.form.get('phone')
            birth_date_str = request.form.get('birth_date')
            customer.address = request.form.get('address')
            customer.notes = request.form.get('notes')

            # Xử lý ngày sinh tương tự hàm add
            birth_date = None
            if birth_date_str:
                try:
                    # Thử định dạng dd-mm-yyyy
                    birth_date = datetime.strptime(birth_date_str, '%d-%m-%Y').date()
                except ValueError:
                    try:
                        # Thử định dạng dd-mm và đặt năm 1900
                        birth_date = datetime.strptime(birth_date_str, '%d-%m').date().replace(year=1900)
                    except ValueError:
                        flash('Định dạng ngày sinh không hợp lệ. Vui lòng sử dụng dd-mm hoặc dd-mm-yyyy.', 'danger')
                        # Truyền lại dữ liệu đã nhập và đối tượng customer
                        return render_template('customers/edit.html', customer=customer), 400
            customer.birth_date = birth_date # Cập nhật ngày sinh của đối tượng customer
            
            # Kiểm tra các trường bắt buộc (Họ và tên, Số điện thoại)
            if not customer.name or not customer.phone:
                 flash('Họ và tên và Số điện thoại là bắt buộc.', 'danger')
                 # Có thể cần truyền lại dữ liệu đã nhập và thông báo lỗi cụ thể hơn
                 return render_template('customers/edit.html', customer=customer), 400

            # Status không còn trên form, không cần cập nhật
            # Email không còn trên form, không cần cập nhật

            db.session.commit()
            flash('Cập nhật thông tin khách hàng thành công!', 'success')
            # Chuyển hướng về trang danh sách
            return redirect(url_for('customer_list'))
        except Exception as e:
            db.session.rollback()
            print(f"Error editing customer: {e}") # In lỗi chi tiết hơn để debug
            flash(f'Có lỗi xảy ra: {str(e)}', 'danger')
            # Có thể cần truyền lại dữ liệu đã nhập
            return render_template('customers/edit.html', customer=customer), 400
    
    return render_template('customers/edit.html', customer=customer)

@app.route('/customers/<int:id>/view')
def customer_view(id):
    customer = Customer.query.get_or_404(id)
    
    # Thêm phân trang cho lịch sử dịch vụ
    page = request.args.get('page', 1, type=int)
    pagination = ServiceHistory.query.filter_by(customer_id=id).order_by(ServiceHistory.service_date.desc()).paginate(page=page, per_page=app.config['ITEMS_PER_PAGE'])
    
    return render_template('customers/view.html', 
                         customer=customer, 
                         pagination=pagination)

@app.route('/customers/<int:id>/delete', methods=['POST'])
def customer_delete(id):
    customer = Customer.query.get_or_404(id)
    try:
        db.session.delete(customer)
        db.session.commit()
        flash('Xóa khách hàng thành công!', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Có lỗi xảy ra khi xóa khách hàng: {str(e)}', 'danger')
    return redirect(url_for('customer_list'))

# Routes cho quản lý dịch vụ
@app.route('/services')
def service_list():
    page = request.args.get('page', 1, type=int)
    search = request.args.get('search', '')
    
    query = Service.query
    if search:
        query = query.filter(Service.name.ilike(f'%{search}%'))
    
    query = query.order_by(Service.name.asc()) # Sắp xếp theo tên dịch vụ A-Z
        
    pagination = query.paginate(page=page, per_page=app.config['ITEMS_PER_PAGE'])
    return render_template('services/index.html', 
                         services=pagination.items,
                         pagination=pagination)

@app.route('/services/add', methods=['GET', 'POST'])
def service_add():
    if request.method == 'POST':
        try:
            # Lấy dữ liệu từ form, sử dụng .get() cho các trường không bắt buộc
            name = request.form.get('name')
            description = request.form.get('description')

            # Kiểm tra các trường bắt buộc (tên dịch vụ)
            if not name:
                flash('Tên dịch vụ là bắt buộc.', 'danger')
                return render_template('services/add.html'), 400

            service = Service(
                name=name,
                description=description
            )
            db.session.add(service)
            db.session.commit()
            flash('Thêm dịch vụ thành công!', 'success')
            return redirect(url_for('service_list'))
        except Exception as e:
            db.session.rollback()
            flash(f'Có lỗi xảy ra: {str(e)}', 'danger')
            return render_template('services/add.html'), 400

    # Xử lý GET request
    return render_template('services/add.html')

@app.route('/services/<int:id>/view')
def service_view(id):
    service = Service.query.get_or_404(id)
    page = request.args.get('page', 1, type=int)
    # Lấy lịch sử dịch vụ của dịch vụ này, sắp xếp theo ngày dịch vụ giảm dần
    service_histories_query = ServiceHistory.query.filter_by(service_id=service.id).order_by(ServiceHistory.service_date.desc())
    pagination = service_histories_query.paginate(page=page, per_page=app.config['ITEMS_PER_PAGE'])
    return render_template('services/view.html', 
                         service=service,
                         pagination=pagination)

@app.route('/services/<int:id>/edit', methods=['GET', 'POST'])
def service_edit(id):
    service = Service.query.get_or_404(id)
    
    if request.method == 'POST':
        try:
            # Lấy dữ liệu từ form, sử dụng .get() cho các trường có thể không tồn tại
            service.name = request.form.get('name')
            service.description = request.form.get('description')
            
            # Kiểm tra trường bắt buộc (tên dịch vụ)
            if not service.name:
                flash('Tên dịch vụ là bắt buộc.', 'danger')
                return render_template('services/edit.html', service=service), 400

            db.session.commit()
            flash('Cập nhật dịch vụ thành công!', 'success')
            # Redirect về trang chi tiết dịch vụ hoặc danh sách dịch vụ
            return redirect(url_for('service_list')) # Hoặc 'service_view', id=service.id nếu có trang view
            
        except Exception as e:
            db.session.rollback()
            flash(f'Có lỗi xảy ra khi cập nhật dịch vụ: {str(e)}', 'danger')
            return render_template('services/edit.html', service=service), 400

    # Xử lý GET request: hiển thị form chỉnh sửa
    return render_template('services/edit.html', service=service)

@app.route('/services/<int:id>/delete', methods=['POST'])
def service_delete(id):
    service = Service.query.get_or_404(id)
    try:
        db.session.delete(service)
        db.session.commit()
        flash('Xóa dịch vụ thành công!', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Có lỗi xảy ra khi xóa dịch vụ: {str(e)}', 'danger')
    return redirect(url_for('service_list'))

# Routes cho quản lý nhân viên
@app.route('/employees')
def employee_list():
    page = request.args.get('page', 1, type=int)
    search = request.args.get('search', '')
    
    query = Employee.query
    if search:
        query = query.filter(Employee.name.ilike(f'%{search}%'))
        
    pagination = query.paginate(page=page, per_page=app.config['ITEMS_PER_PAGE'])
    return render_template('employees/index.html', 
                         employees=pagination.items,
                         pagination=pagination)

@app.route('/employees/add', methods=['GET', 'POST'])
def employee_add():
    if request.method == 'POST':
        try:
            name = request.form.get('name')
            phone = request.form.get('phone')
            hire_date_str = request.form.get('hire_date')
            notes = request.form.get('notes')

            hire_date = None
            if hire_date_str:
                try:
                    hire_date = datetime.strptime(hire_date_str, '%Y-%m-%d').date()
                except ValueError:
                    flash('Định dạng ngày thuê không hợp lệ. Vui lòng sử dụng định dạng YYYY-MM-DD.', 'danger')
                    return render_template('employees/add.html'), 400

            if not name or not phone:
                flash('Họ và tên và Số điện thoại là bắt buộc.', 'danger')
                return render_template('employees/add.html'), 400
            
            employee = Employee(
                name=name,
                phone=phone,
                hire_date=hire_date,
                notes=notes
            )
            db.session.add(employee)
            db.session.commit()
            flash('Thêm nhân viên thành công!', 'success')
            return redirect(url_for('employee_list'))
        except Exception as e:
            db.session.rollback()
            print(f"Error adding employee: {e}")
            flash(f'Có lỗi xảy ra: {str(e)}', 'danger')
            return render_template('employees/add.html'), 400

    return render_template('employees/add.html')

@app.route('/employees/<int:id>/edit', methods=['GET', 'POST'])
def employee_edit(id):
    employee = Employee.query.get_or_404(id)
    
    if request.method == 'POST':
        try:
            employee.name = request.form.get('name')
            employee.phone = request.form.get('phone')
            hire_date_str = request.form.get('hire_date')
            employee.notes = request.form.get('notes')

            hire_date = None
            if hire_date_str:
                try:
                    hire_date = datetime.strptime(hire_date_str, '%Y-%m-%d').date()
                except ValueError:
                    flash('Định dạng ngày thuê không hợp lệ. Vui lòng sử dụng định dạng YYYY-MM-DD.', 'danger')
                    return render_template('employees/edit.html', employee=employee), 400
            employee.hire_date = hire_date

            if not employee.name or not employee.phone:
                flash('Họ và tên và Số điện thoại là bắt buộc.', 'danger')
                return render_template('employees/edit.html', employee=employee), 400

            db.session.commit()
            flash('Cập nhật nhân viên thành công!', 'success')
            return redirect(url_for('employee_list'))
        except Exception as e:
            db.session.rollback()
            flash(f'Có lỗi xảy ra: {str(e)}', 'danger')
            return render_template('employees/edit.html', employee=employee), 400

    return render_template('employees/edit.html', employee=employee)

@app.route('/employees/<int:id>/delete', methods=['POST'])
def employee_delete(id):
    employee = Employee.query.get_or_404(id)
    try:
        db.session.delete(employee)
        db.session.commit()
        flash('Xóa nhân viên thành công!', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Có lỗi xảy ra khi xóa nhân viên: {str(e)}', 'danger')
    return redirect(url_for('employee_list'))

@app.route('/employees/<int:id>/view')
def employee_view(id):
    employee = Employee.query.get_or_404(id)
    page = request.args.get('page', 1, type=int)
    # Lấy lịch sử dịch vụ của nhân viên, sắp xếp theo ngày dịch vụ giảm dần
    service_histories_query = ServiceHistory.query.filter_by(employee_id=employee.id).order_by(ServiceHistory.service_date.desc())
    service_histories_pagination = service_histories_query.paginate(page=page, per_page=app.config['ITEMS_PER_PAGE'])
    return render_template('employees/view.html', 
                           employee=employee,
                           service_histories_pagination=service_histories_pagination)

# Routes cho quản lý danh mục
@app.route('/categories')
def category_list():
    categories = Category.query.order_by(Category.name.asc()).all()
    return render_template('categories/index.html', categories=categories)

@app.route('/categories/add', methods=['GET', 'POST'])
def category_add():
    if request.method == 'POST':
        try:
            name = request.form.get('name')
            description = request.form.get('description')
            if not name:
                flash('Tên danh mục là bắt buộc.', 'danger')
                return render_template('categories/add.html'), 400
            category = Category(name=name, description=description)
            db.session.add(category)
            db.session.commit()
            flash('Thêm danh mục thành công!', 'success')
            return redirect(url_for('category_list'))
        except Exception as e:
            db.session.rollback()
            flash(f'Có lỗi xảy ra: {str(e)}', 'danger')
            return render_template('categories/add.html'), 400
    return render_template('categories/add.html')

@app.route('/categories/<int:id>/edit', methods=['GET', 'POST'])
def category_edit(id):
    category = Category.query.get_or_404(id)
    if request.method == 'POST':
        try:
            category.name = request.form.get('name')
            category.description = request.form.get('description')
            if not category.name:
                flash('Tên danh mục là bắt buộc.', 'danger')
                return render_template('categories/edit.html', category=category), 400
            db.session.commit()
            flash('Cập nhật danh mục thành công!', 'success')
            return redirect(url_for('category_list'))
        except Exception as e:
            db.session.rollback()
            flash(f'Có lỗi xảy ra: {str(e)}', 'danger')
            return render_template('categories/edit.html', category=category), 400
    return render_template('categories/edit.html', category=category)

@app.route('/categories/<int:id>/delete', methods=['POST'])
def category_delete(id):
    category = Category.query.get_or_404(id)
    try:
        db.session.delete(category)
        db.session.commit()
        flash('Xóa danh mục thành công!', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Có lỗi xảy ra khi xóa danh mục: {str(e)}', 'danger')
    return redirect(url_for('category_list'))


# Routes cho quản lý lịch sử dịch vụ
@app.route('/service-histories')
def service_history_list():
    date_from_str = request.args.get('date_from')
    date_to_str = request.args.get('date_to')

    query = ServiceHistory.query

    if date_from_str:
        try:
            date_from = datetime.strptime(date_from_str, '%Y-%m-%d')
            query = query.filter(ServiceHistory.service_date >= date_from)
        except ValueError:
            flash('Định dạng ngày bắt đầu không hợp lệ.', 'danger')

    if date_to_str:
        try:
            date_to = datetime.strptime(date_to_str, '%Y-%m-%d')
            query = query.filter(ServiceHistory.service_date <= date_to)
        except ValueError:
            flash('Định dạng ngày kết thúc không hợp lệ.', 'danger')

    service_histories = query.order_by(ServiceHistory.service_date.desc()).all()

    # Nhóm lịch sử dịch vụ theo ngày
    grouped_histories = {}
    for history in service_histories:
        date_str = history.service_date.strftime('%Y-%m-%d')
        if date_str not in grouped_histories:
            grouped_histories[date_str] = []
        grouped_histories[date_str].append(history)

    # Sắp xếp các ngày giảm dần
    sorted_dates = sorted(grouped_histories.keys(), reverse=True)

    return render_template('service_histories/index.html', grouped_histories=grouped_histories, sorted_dates=sorted_dates)

@app.route('/service-histories/add', methods=['GET', 'POST'])
@app.route('/service-histories/add/<int:customer_id>', methods=['GET', 'POST'])
def service_history_add(customer_id=None):
    # customer_id có thể được truyền từ trang chi tiết khách hàng
    # Lấy danh sách khách hàng để chọn (cho trường hợp không truyền customer_id)
    # Bỏ lọc theo status vì lỗi xảy ra khi truy cập thuộc tính status
    customers = Customer.query.all()
    services = Service.query.order_by(Service.name).all()
    employees = Employee.query.order_by(Employee.name).all()

    # Nếu customer_id được truyền, tìm khách hàng tương ứng
    selected_customer = None
    if customer_id:
        selected_customer = Customer.query.get(customer_id)
        if not selected_customer:
            flash('Khách hàng không tồn tại.', 'danger')
            return redirect(url_for('customer_list')) # Or appropriate fallback

    if request.method == 'POST':
        try:
            # Use customer_id from URL if available, otherwise from form
            customer_id_to_save = customer_id if customer_id else request.form['customer_id']

            service_history = ServiceHistory(
                customer_id=customer_id_to_save,
                service_id=request.form['service_id'],
                employee_id=request.form['employee_id'],
                service_date=datetime.strptime(request.form['service_date'], '%Y-%m-%d'),
                payment_method=request.form['payment_method'], # Now it's text
                price=float(request.form['amount_raw']),
                notes=request.form.get('notes')
            )
            db.session.add(service_history)
            db.session.commit()

            # Xử lý upload hình ảnh
            files = request.files.getlist('images')
            for file in files:
                if file and file.filename:
                    # Tạo tên file duy nhất bằng UUID
                    original_filename = secure_filename(file.filename)
                    file_extension = os.path.splitext(original_filename)[1]
                    unique_filename = str(uuid.uuid4().hex) + file_extension
                    filepath = os.path.join(app.config['UPLOAD_FOLDER'], unique_filename)
                    file.save(filepath)
                    image = ServiceHistoryImage(service_history_id=service_history.id, image_url='static/uploads/' + unique_filename)
                    db.session.add(image)
            db.session.commit()
            flash('Thêm lịch sử dịch vụ thành công!', 'success')
            # Redirect to customer view if coming from customer page, else to list
            if customer_id:
                return redirect(url_for('customer_view', id=customer_id))
            else:
                return redirect(url_for('service_history_list'))
        except Exception as e:
            db.session.rollback()
            flash(f'Có lỗi xảy ra: {str(e)}', 'danger')

    return render_template('service_histories/add.html',
                         customers=customers, # Pass all customers even if one is preselected (for context)
                         services=services,
                         employees=employees,
                         now=datetime.now(),
                         customer_preselected=selected_customer) # Pass the preselected customer object

@app.route('/service-histories/<int:id>/edit', methods=['GET', 'POST'])
def service_history_edit(id):
    history = ServiceHistory.query.get_or_404(id)
    customers = Customer.query.all()
    services = Service.query.order_by(Service.name).all()
    employees = Employee.query.order_by(Employee.name).all()

    if request.method == 'POST':
        try:
            history.customer_id = request.form.get('customer') or history.customer_id
            history.service_id = request.form.get('service') or history.service_id
            history.employee_id = request.form.get('employee') or history.employee_id
            # Xử lý ngày giờ
            service_date_str = request.form.get('service_date')
            if service_date_str:
                try:
                    history.service_date = datetime.strptime(service_date_str, '%Y-%m-%dT%H:%M')
                except ValueError:
                    try:
                        history.service_date = datetime.strptime(service_date_str, '%Y-%m-%d')
                    except ValueError:
                        pass
            history.price = float(request.form.get('price', history.price))
            history.payment_method = request.form.get('payment_method', history.payment_method)
            history.notes = request.form.get('notes', history.notes)

            # Xử lý xóa ảnh
            delete_image_ids = request.form.getlist('delete_images')
            if delete_image_ids:
                for img_id in delete_image_ids:
                    img = ServiceHistoryImage.query.get(int(img_id))
                    if img:
                        # Xóa file vật lý nếu tồn tại
                        img_path = os.path.join(app.config['UPLOAD_FOLDER'], os.path.basename(img.image_url))
                        if os.path.exists(img_path):
                            os.remove(img_path)
                        db.session.delete(img)

            db.session.commit()

            # Xử lý upload hình ảnh mới
            # files = request.files.getlist('images')
            # for file in files:
            #     if file and file.filename:
            #         # Tạo tên file duy nhất bằng UUID
            #         original_filename = secure_filename(file.filename)
            #         file_extension = os.path.splitext(original_filename)[1]
            #         unique_filename = str(uuid.uuid4().hex) + file_extension
            #         filepath = os.path.join(app.config['UPLOAD_FOLDER'], unique_filename)
            #         file.save(filepath)
            #         rel_path = os.path.relpath(filepath, start=os.path.dirname(__file__))
            #         image = ServiceHistoryImage(service_history_id=history.id, image_url='static/uploads/' + unique_filename)
            #         db.session.add(image)
            # db.session.commit()
            flash('Cập nhật lịch sử dịch vụ thành công!', 'success')
            return redirect(url_for('customer_view', id=history.customer_id))
        except Exception as e:
            db.session.rollback()
            flash(f'Có lỗi xảy ra khi cập nhật lịch sử dịch vụ: {str(e)}', 'danger')
            # Reload lại đối tượng history để danh sách ảnh mới nhất
            history = ServiceHistory.query.get_or_404(id)

    return render_template('service_histories/edit.html',
                           history=history,
                           customers=customers,
                           services=services,
                           employees=employees)

@app.route('/service-histories/<int:id>/upload-images', methods=['POST'])
def upload_service_history_images(id):
    history = ServiceHistory.query.get_or_404(id)
    new_images_data = []
    
    if 'images' not in request.files:
        return jsonify({'success': False, 'message': 'Không có hình ảnh nào được tải lên.'}), 400
    
    files = request.files.getlist('images')
    if not files or not any(files):
        return jsonify({'success': False, 'message': 'Không có hình ảnh nào được chọn.'}), 400
    
    try:
        for file in files:
            if file and file.filename and allowed_file(file.filename):
                # Tải lên Cloudinary
                upload_result = upload_to_cloudinary(
                    file,
                    folder=app.config.get('CLOUDINARY_FOLDER')
                )
                
                # Lưu thông tin ảnh vào database
                image = ServiceHistoryImage(
                    service_history_id=history.id,
                    image_url=upload_result['url'],
                    cloudinary_public_id=upload_result['public_id']
                )
                db.session.add(image)
                db.session.flush()  # Lấy ID trước khi commit
                
                new_images_data.append({
                    'id': image.id, 
                    'image_url': upload_result['url']
                })
        
        db.session.commit()
        return jsonify({
            'success': True, 
            'new_images': new_images_data, 
            'message': 'Hình ảnh đã được tải lên thành công!'
        })
        
    except Exception as e:
        db.session.rollback()
        app.logger.error(f"Error uploading images: {str(e)}")
        return jsonify({
            'success': False, 
            'message': f'Lỗi khi tải lên hình ảnh: {str(e)}'
        }), 500


@app.route('/service-histories/<int:id>/replace-image/<int:image_id>', methods=['POST'])
def replace_service_history_image(id, image_id):
    history = ServiceHistory.query.get_or_404(id)
    image_to_replace = ServiceHistoryImage.query.get_or_404(image_id)

    if 'new_image' not in request.files:
        return jsonify({'success': False, 'message': 'Không có file ảnh mới.'}), 400
    
    file = request.files['new_image']
    if not file or file.filename == '':
        return jsonify({'success': False, 'message': 'Không có file ảnh được chọn.'}), 400

    if not allowed_file(file.filename):
        return jsonify({'success': False, 'message': 'Định dạng file không hợp lệ.'}), 400
    
    try:
        # Xóa ảnh cũ trên Cloudinary nếu có
        if image_to_replace.cloudinary_public_id:
            delete_from_cloudinary(image_to_replace.cloudinary_public_id)
        
        # Tải lên ảnh mới lên Cloudinary
        upload_result = upload_to_cloudinary(
            file,
            folder=app.config.get('CLOUDINARY_FOLDER')
        )
        
        # Cập nhật thông tin ảnh trong database
        image_to_replace.image_url = upload_result['url']
        image_to_replace.cloudinary_public_id = upload_result['public_id']
        
        db.session.commit()
        
        return jsonify({
            'success': True, 
            'message': 'Thay thế ảnh thành công!', 
            'new_image_url': upload_result['url']
        })
        
    except Exception as e:
        db.session.rollback()
        app.logger.error(f"Error replacing image: {str(e)}")
        return jsonify({
            'success': False, 
            'message': f'Lỗi khi thay thế ảnh: {str(e)}'
        }), 500





@app.route('/service-histories/<int:id>/details')
def service_history_details(id):
    history = ServiceHistory.query.get_or_404(id)
    return render_template('service_histories/details.html', history=history)


@app.route('/service-histories/<int:id>/export-pdf')
def export_service_history_pdf(id):
    history = ServiceHistory.query.get_or_404(id)
    html_content = render_template('service_histories/pdf_template.html', history=history)

    # Tạo PDF từ HTML (sử dụng xhtml2pdf hoặc thư viện tương tự)
    # Đây là ví dụ, bạn cần cài đặt xhtml2pdf: pip install xhtml2pdf
    pdf = HTML(string=html_content).write_pdf()

    response = make_response(pdf)
    response.headers['Content-Type'] = 'application/pdf'
    response.headers['Content-Disposition'] = f'attachment; filename=lich_su_dich_vu_{history.id}.pdf'
    return response


@app.route('/revenue')
def revenue():
    # Lấy thống kê doanh thu
    total_revenue = db.session.query(db.func.sum(ServiceHistory.price)).scalar() or 0
    total_services = ServiceHistory.query.count()
    avg_revenue = total_revenue / total_services if total_services > 0 else 0

    # Thống kê doanh thu theo dịch vụ
    revenue_by_service = db.session.query(
        Service.name,
        db.func.count(ServiceHistory.id).label('count'),
        db.func.sum(ServiceHistory.price).label('total')
    ).join(ServiceHistory).group_by(Service.name).all()

    # Thống kê doanh thu theo nhân viên
    revenue_by_employee = db.session.query(
        Employee.name,
        db.func.count(ServiceHistory.id).label('count'),
        db.func.sum(ServiceHistory.price).label('total')
    ).join(ServiceHistory).group_by(Employee.name).all()

    return render_template('revenue.html',
                         total_revenue=total_revenue,
                         total_services=total_services,
                         avg_revenue=avg_revenue,
                         revenue_by_service=revenue_by_service,
                         revenue_by_employee=revenue_by_employee)

@app.route('/static/uploads/<path:filename>')
def serve_uploaded_file(filename):
    print(f"\n=== DEBUG ===")
    print(f"Requested filename: {filename}")
    print(f"Upload folder: {app.config['UPLOAD_FOLDER']}")
    full_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
    print(f"Full path: {full_path}")
    print(f"File exists: {os.path.exists(full_path)}")
    
    try:
        return send_from_directory(app.config['UPLOAD_FOLDER'], filename)
    except Exception as e:
        print(f"Error serving {filename}: {str(e)}")
        return str(e), 404

@app.route('/test_image')
def test_image():
    # Dùng để kiểm tra việc phục vụ ảnh tĩnh
    # Tạo một file ảnh tạm thời để kiểm tra
    test_image_path = os.path.join(app.config['UPLOAD_FOLDER'], 'test_image.png')
    if not os.path.exists(test_image_path):
        # Tạo một ảnh PNG trống đơn giản
        from PIL import Image
        img = Image.new('RGB', (60, 30), color = 'red')
        img.save(test_image_path)
    
    return f'<img src="{url_for("uploaded_file", filename="test_image.png")}" alt="Test Image">'


@app.route('/service-histories/<int:id>/delete', methods=['POST'])
def service_history_delete(id):
    history = ServiceHistory.query.get_or_404(id)
    try:
        # Xóa tất cả hình ảnh liên quan
        for image in history.images:
            # Xóa file vật lý
            filename = os.path.basename(image.image_url)
            filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            if os.path.exists(filepath):
                os.remove(filepath)
            db.session.delete(image)
        
        # Xóa lịch sử dịch vụ
        db.session.delete(history)
        db.session.commit()
        flash('Xóa lịch sử dịch vụ thành công!', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Có lỗi xảy ra khi xóa lịch sử dịch vụ: {str(e)}', 'danger')
    
    return redirect(url_for('customer_view', id=history.customer_id))

@app.route('/service-histories/<int:id>/images/<int:image_id>', methods=['DELETE'])
def delete_service_history_image(id, image_id):
    history = ServiceHistory.query.get_or_404(id)
    image = ServiceHistoryImage.query.get_or_404(image_id)

    if image.service_history_id != history.id:
        return jsonify({'success': False, 'message': 'Ảnh không thuộc lịch sử dịch vụ này.'}), 403

    try:
        # Xóa ảnh từ Cloudinary nếu có
        if image.cloudinary_public_id:
            delete_from_cloudinary(image.cloudinary_public_id)
        
        # Xóa bản ghi trong database
        db.session.delete(image)
        db.session.commit()
        
        return jsonify({
            'success': True, 
            'message': 'Xóa ảnh thành công!'
        })
        
    except Exception as e:
        db.session.rollback()
        app.logger.error(f"Error deleting image: {str(e)}")
        return jsonify({
            'success': False, 
            'message': f'Lỗi khi xóa ảnh: {str(e)}'
        }), 500

# Routes cho trang cài đặt
@app.route('/settings', methods=['GET', 'POST'])
def settings_page():
    settings = Settings.query.first()
    if not settings:
        settings = Settings() # Tạo cài đặt mặc định nếu chưa có
        db.session.add(settings)
        db.session.commit()

    if request.method == 'POST':
        action = request.form.get('action')

        # Xử lý logo công ty
        if 'company_logo' in request.files and request.files['company_logo'].filename != '':
            logo_file = request.files['company_logo']
            if logo_file and allowed_file(logo_file.filename):
                logo_filename = secure_filename(f"{uuid.uuid4()}.{logo_file.filename.rsplit('.', 1)[1].lower()}")
                logo_filepath = os.path.join(app.config['UPLOAD_FOLDER'], logo_filename)
                logo_file.save(logo_filepath)
                settings.company_logo_url = url_for('uploaded_file', filename=logo_filename)
            else:
                flash('Định dạng tệp logo không hợp lệ.', 'danger')
        elif request.form.get('company_logo_clear') == '1': # Thêm một cách để xóa logo
            settings.company_logo_url = None

        # Xử lý Favicon
        if 'favicon' in request.files and request.files['favicon'].filename != '':
            favicon_file = request.files['favicon']
            if favicon_file and allowed_file(favicon_file.filename):
                favicon_filename = secure_filename(f"{uuid.uuid4()}.{favicon_file.filename.rsplit('.', 1)[1].lower()}")
                favicon_filepath = os.path.join(app.config['UPLOAD_FOLDER'], favicon_filename)
                favicon_file.save(favicon_filepath)
                settings.favicon_url = url_for('uploaded_file', filename=favicon_filename)
            else:
                flash('Định dạng tệp Favicon không hợp lệ.', 'danger')
        elif request.form.get('favicon_clear') == '1': # Thêm một cách để xóa favicon
            settings.favicon_url = None

        # Cập nhật các trường cài đặt khác từ form
        settings.company_name = request.form.get('company_name')
        settings.address = request.form.get('address')
        settings.phone = request.form.get('phone')
        settings.email = request.form.get('email')
        settings.welcome_title = request.form.get('welcome_title')
        settings.welcome_subtitle = request.form.get('welcome_subtitle')
        settings.primary_color = request.form.get('primary_color')
        settings.facebook_url = request.form.get('facebook_url')
        settings.instagram_url = request.form.get('instagram_url')
        settings.youtube_url = request.form.get('youtube_url')
        
        try:
            db.session.commit()
            flash('Cài đặt đã được lưu thành công!', 'success')
        except Exception as e:
            db.session.rollback()
            flash(f'Lỗi khi lưu cài đặt: {str(e)}', 'danger')
            print(f"Error saving settings: {e}")

        return redirect(url_for('settings_page'))

    return render_template('settings/index.html', settings=settings)

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=True, host='0.0.0.0', port=5000)
