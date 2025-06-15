import os
import sys
from pathlib import Path
from app import app, db
from models import ServiceHistoryImage
from cloudinary_utils import upload_to_cloudinary, delete_from_cloudinary
from werkzeug.utils import secure_filename

def migrate_images():
    """Di chuyển ảnh từ thư mục local lên Cloudinary"""
    # Tạo đối tượng ứng dụng
    app_ctx = app.app_context()
    app_ctx.push()
    
    try:
        # Lấy tất cả các bản ghi ảnh cũ
        images = ServiceHistoryImage.query.filter(
            ServiceHistoryImage.image_url.like('%static/uploads/%')
        ).all()
        
        if not images:
            print("Không có ảnh nào cần di chuyển.")
            return
            
        print(f"Đang di chuyển {len(images)} ảnh lên Cloudinary...")
        
        for img in images:
            try:
                # Lấy đường dẫn file cũ
                old_path = img.image_url.replace('/static/uploads/', '')
                old_filepath = os.path.join(app.config['UPLOAD_FOLDER'], old_path)
                
                if not os.path.exists(old_filepath):
                    print(f"Không tìm thấy file: {old_filepath}")
                    continue
                
                # Tải lên Cloudinary
                with open(old_filepath, 'rb') as f:
                    upload_result = upload_to_cloudinary(
                        f,
                        folder=app.config.get('CLOUDINARY_FOLDER')
                    )
                
                # Cập nhật thông tin ảnh
                img.image_url = upload_result['url']
                img.cloudinary_public_id = upload_result['public_id']
                
                # Xóa file cũ
                os.remove(old_filepath)
                print(f"Đã di chuyển ảnh {old_path} lên Cloudinary")
                
            except Exception as e:
                print(f"Lỗi khi di chuyển ảnh {getattr(img, 'id', 'unknown')}: {str(e)}")
                db.session.rollback()
            else:
                db.session.commit()
                
        print("\nHoàn thành di chuyển ảnh lên Cloudinary!")
        
    except Exception as e:
        print(f"Lỗi: {str(e)}")
        db.session.rollback()
    finally:
        db.session.close()
        app_ctx.pop()

if __name__ == '__main__':
    print("Bắt đầu di chuyển ảnh lên Cloudinary...")
    migrate_images()
