from app import app, db
from flask_migrate import Migrate, migrate

# Khởi tạo Flask-Migrate
migrate = Migrate(app, db)

# Tạo migration trực tiếp
with app.app_context():
    # Tạo thư mục migrations nếu chưa tồn tại
    from pathlib import Path
    migrations_dir = Path('migrations')
    if not migrations_dir.exists():
        migrations_dir.mkdir()
    
    # Tạo migration
    from flask_migrate import upgrade, migrate, init, stamp
    
    # Khởi tạo migrations nếu chưa có
    try:
        init()
    except:
        pass
    
    # Tạo migration mới
    migrate(message='Add cloudinary_public_id to ServiceHistoryImage')
    
    print("Migration created successfully!")
