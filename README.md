# Khởi Nghiệp Salon - Hệ thống quản lý Salon

Đây là một ứng dụng web được xây dựng bằng Flask để quản lý hoạt động của một salon, bao gồm quản lý khách hàng, nhân viên, dịch vụ, lịch sử dịch vụ và cài đặt ứng dụng.

> **Lưu ý quan trọng:** Ứng dụng đã được tích hợp với Cloudinary để lưu trữ hình ảnh. Tất cả hình ảnh mới sẽ được tải lên Cloudinary thay vì lưu trữ cục bộ.

## Mục lục

1.  [Yêu cầu](#yêu-cầu)
2.  [Cài đặt](#cài-đặt)
3.  [Chạy ứng dụng với Docker Compose](#chạy-ứng-dụng-với-docker-compose)
4.  [Di chuyển cơ sở dữ liệu](#di-chuyển-cơ-sở-dữ-liệu)
5.  [Truy cập ứng dụng](#truy-cập-ứng-dụng)
6.  [Chạy Tailwind CSS](#chạy-tailwind-css)

## Yêu cầu

Để chạy ứng dụng này, bạn cần cài đặt:

*   [Docker](https://www.docker.com/get-started/)
*   [Docker Compose](https://docs.docker.com/compose/)
*   [Python 3.8+](https://www.python.org/downloads/)
*   [Pip](https://pip.pypa.io/en/stable/installation/)
*   Tài khoản [Cloudinary](https://cloudinary.com/) (miễn phí)

## Cài đặt

1.  **Clone repository:**
    ```bash
    git clone <URL_REPOSITORY_CỦA_BẠN>
    cd webappnoimi
    ```

2.  **Cài đặt các phụ thuộc Python:**
    ```bash
    pip install -r requirements.txt
    ```

3.  **Cấu hình biến môi trường:**
    - Tạo file `.env` từ file `.env.example`
    - Cập nhật các thông tin Cloudinary:
      ```
      CLOUDINARY_CLOUD_NAME=your_cloud_name
      CLOUDINARY_API_KEY=your_api_key
      CLOUDINARY_API_SECRET=your_api_secret
      CLOUDINARY_FOLDER=salon_uploads  # Tùy chọn
      ```

## Chạy ứng dụng với Docker Compose

Sử dụng Docker Compose để xây dựng và chạy ứng dụng cùng với cơ sở dữ liệu PostgreSQL.

1.  **Xây dựng và khởi động các dịch vụ:**
    ```bash
    docker-compose up --build -d
    ```
    Lệnh này sẽ xây dựng các Docker image (nếu chưa có hoặc có thay đổi), tạo các container và khởi động chúng trong chế độ nền.

## Di chuyển dữ liệu hình ảnh lên Cloudinary

Sau khi cấu hình xong, bạn có thể di chuyển các hình ảnh hiện có từ thư mục `static/uploads` lên Cloudinary bằng lệnh:

```bash
python migrate_to_cloudinary.py
```

Lưu ý: Script này sẽ tự động cập nhật các URL ảnh trong cơ sở dữ liệu và xóa các file ảnh cục bộ sau khi tải lên thành công.

## Di chuyển cơ sở dữ liệu

Sau khi các dịch vụ Docker đã chạy, bạn cần khởi tạo và áp dụng các bản di chuyển cơ sở dữ liệu để tạo bảng và cấu hình dữ liệu ban đầu.

1.  **Xóa thư mục migrations cũ (nếu có, đặc biệt khi gặp lỗi database schema)**:
    ```bash
    Remove-Item -Recurse -Force migrations # Đối với PowerShell trên Windows
    # hoặc
    # rm -rf migrations # Đối với Linux/macOS
    ```

2.  **Khởi tạo Flask-Migrate**:
    ```bash
    docker-compose run --rm web flask db init
    ```
    Lệnh này sẽ tạo thư mục `migrations` và các tệp cấu hình cần thiết.

3.  **Tạo bản di chuyển ban đầu**:
    ```bash
    docker-compose run --rm web flask db migrate -m "Initial migration"
    ```
    Lệnh này sẽ quét các mô hình SQLAlchemy của bạn và tạo một bản di chuyển dựa trên các thay đổi schema.

4.  **Áp dụng bản di chuyển vào cơ sở dữ liệu**:
    ```bash
    docker-compose run --rm web flask db upgrade
    ```
    Lệnh này sẽ thực thi bản di chuyển đã tạo, tạo các bảng trong cơ sở dữ liệu PostgreSQL.

5.  **Chạy lại ứng dụng (sau khi di chuyển)**:
    Sau khi di chuyển, bạn nên dừng và khởi động lại các container để đảm bảo ứng dụng kết nối với cơ sở dữ liệu đã được cập nhật.
    ```bash
    docker-compose down
    docker-compose up -d
    ```

## Truy cập ứng dụng

Sau khi các container đã chạy, bạn có thể truy cập ứng dụng tại:

[http://localhost:5000](http://localhost:5000)

## Chạy Tailwind CSS

## Tích hợp Cloudinary

Ứng dụng đã được tích hợp với Cloudinary để lưu trữ hình ữu ảnh. Để sử dụng tính năng này, bạn cần:

1. Tạo tài khoản miễn phí tại [Cloudinary](https://cloudinary.com/)
2. Lấy các thông tin API từ Dashboard của Cloudinary
3. Cập nhật các thông tin này vào file `.env`

### Lợi ích khi sử dụng Cloudinary:
- Tự động tối ưu hóa hình ảnh
- Hỗ trợ CDN giúp tải ảnh nhanh hơn
- Dễ dàng quản lý và chỉnh sửa ảnh
- Tiết kiệm không gian lưu trữ server

## Xử lý sự cố

### Lỗi khi tải ảnh lên Cloudinary
- Kiểm tra lại các thông tin API trong file `.env`
- Đảm bảo kết nối Internet ổn định
- Kiểm tra quyền truy cập API Key trên Cloudinary Dashboard

### Khôi phục dữ liệu ảnh
Nếu cần khôi phục lại ảnh từ bản sao lưu, thư mục `backup/uploads` chứa tất cả các ảnh gốc trước khi di chuyển lên Cloudinary.

Nếu bạn thực hiện bất kỳ thay đổi nào đối với các tệp mẫu (`.html`) hoặc cấu hình Tailwind, bạn cần biên dịch lại CSS:

```bash
npx tailwindcss -i ./static/css/main.css -o ./static/css/output.css --minify
```

Bạn cũng có thể chạy Tailwind CSS ở chế độ "watch" để tự động biên dịch khi có thay đổi:

```bash
npx tailwindcss -i ./static/css/main.css -o ./static/css/output.css --watch
```

Chúc bạn thành công! 