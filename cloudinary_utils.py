import cloudinary
import cloudinary.uploader
import cloudinary.api
from config import Config

def configure_cloudinary(app):
    """Cấu hình Cloudinary với các thông tin từ app config"""
    cloudinary.config(
        cloud_name=app.config.get('CLOUDINARY_CLOUD_NAME'),
        api_key=app.config.get('CLOUDINARY_API_KEY'),
        api_secret=app.config.get('CLOUDINARY_API_SECRET'),
        secure=True
    )

def upload_to_cloudinary(file, folder=None):
    """Tải file lên Cloudinary"""
    try:
        upload_result = cloudinary.uploader.upload(
            file,
            folder=folder,
            resource_type="auto"
        )
        return {
            'public_id': upload_result['public_id'],
            'url': upload_result['secure_url']
        }
    except Exception as e:
        print(f"Error uploading to Cloudinary: {e}")
        raise

def delete_from_cloudinary(public_id):
    """Xóa file từ Cloudinary"""
    try:
        if not public_id:
            return False
            
        result = cloudinary.uploader.destroy(public_id)
        return result.get('result') == 'ok'
    except Exception as e:
        print(f"Error deleting from Cloudinary: {e}")
        return False

def get_cloudinary_public_id(image_url):
    """Lấy public_id từ URL của ảnh trên Cloudinary"""
    if not image_url or 'cloudinary.com' not in image_url:
        return None
    
    # Trích xuất public_id từ URL
    # Ví dụ: https://res.cloudinary.com/demo/image/upload/v1234567890/sample.jpg
    # -> sample
    try:
        parts = image_url.split('/')
        # Lấy phần cuối cùng và bỏ đuôi file
        filename = parts[-1]
        public_id = filename.split('.')[0]
        
        # Nếu có folder, thêm vào public_id
        if 'upload' in parts:
            upload_index = parts.index('upload')
            if upload_index + 1 < len(parts) - 1:  # Có folder
                folder = '/'.join(parts[upload_index + 1:-1])
                public_id = f"{folder}/{public_id}"
        
        return public_id
    except Exception as e:
        print(f"Error extracting public_id: {e}")
        return None
