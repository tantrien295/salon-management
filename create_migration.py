from app import app, db
from flask_migrate import Migrate

# Khởi tạo Flask-Migrate
migrate = Migrate(app, db)

# Tạo migration
with app.app_context():
    import os
    os.environ['FLASK_APP'] = 'app.py'
    os.system('flask db migrate -m "Add cloudinary_public_id to ServiceHistoryImage"')
