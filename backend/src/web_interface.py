from flask import Flask, render_template, request, jsonify, redirect, url_for, send_file, send_from_directory
import os
import json
import asyncio
import threading
from datetime import datetime
from werkzeug.utils import secure_filename
import mimetypes
from functools import wraps
from flask import Response
from src.config import BotConfig
from src.bot import DiscordAutoBot

# 보안 관련 함수들
def check_basic_auth():
    """Basic Auth 체크"""
    auth = request.authorization
    username = os.getenv('ADMIN_USERNAME', 'admin')
    password = os.getenv('ADMIN_PASSWORD', 'password')
    
    if auth and auth.username == username and auth.password == password:
        return True
    return False

def require_auth(f):
    """인증 데코레이터"""
    @wraps(f)
    def decorated(*args, **kwargs):
        if not check_basic_auth():
            return Response(
                '🔐 인증이 필요합니다',
                401,
                {
                    'WWW-Authenticate': 'Basic realm="Discord Bot Admin"',
                    'Content-Type': 'text/plain; charset=utf-8'
                }
            )
        
        return f(*args, **kwargs)
    return decorated

class WebInterface:
    """웹 관리 인터페이스"""
    
    def __init__(self, config: BotConfig = None):
        # 현재 파일 위치에서 프로젝트 루트 찾기
        # Docker: /app/src/web_interface.py -> /app/src -> /app
        # Local: backend/src/web_interface.py -> backend/src -> backend -> 프로젝트 루트
        current_dir = os.path.dirname(os.path.abspath(__file__))  # .../src
        project_root = os.path.dirname(current_dir)  # /app (Docker) 또는 backend (Local)
        
        # Docker에서는 /app/web/templates, Local에서는 backend/../web/templates
        if os.path.exists(os.path.join(project_root, 'web', 'templates')):
            # Docker 경로 또는 올바른 경로
            template_dir = os.path.join(project_root, 'web', 'templates')
            static_dir = os.path.join(project_root, 'web', 'static')
        else:
            # Local 개발 환경 - backend에서 한 단계 위로
            parent_dir = os.path.dirname(project_root)
            template_dir = os.path.join(parent_dir, 'web', 'templates')
            static_dir = os.path.join(parent_dir, 'web', 'static')
        
        print(f"✅ Templates directory: {template_dir}")
        print(f"✅ Templates exist: {os.path.exists(template_dir)}")
        if os.path.exists(template_dir):
            print(f"✅ Template files: {os.listdir(template_dir)}")
        
        self.app = Flask(__name__, 
                        template_folder=template_dir,
                        static_folder=static_dir,
                        static_url_path='/static')
        
        # 설정 로드 - 전달받은 config 우선, 없으면 새로 로드
        self.config = config if config else BotConfig.load()
        self.bot = None
        self.bot_thread = None
        
        self._setup_routes()
    
    def _setup_routes(self):
        """라우트 설정"""
        
        @self.app.route('/health')
        def health_check():
            """Railway 헬스체크 엔드포인트"""
            return {'status': 'healthy', 'timestamp': datetime.now().isoformat()}, 200
        
        @self.app.route('/')
        @require_auth
        def dashboard():
            """대시보드 페이지"""
            status = {
                'is_running': self.bot is not None and self.bot.is_running,
                'is_enabled': self.config.is_enabled,
                'next_send_time': getattr(self.bot, 'next_send_time', None),
                'config': self.config
            }
            return render_template('dashboard.html', **status)
        
        @self.app.route('/config', methods=['GET', 'POST'])
        @require_auth
        def config_page():
            """설정 페이지 - JSON 파일 기반"""
            if request.method == 'POST':
                # 설정 업데이트
                data = request.form.to_dict()
                
                # 숫자 타입 변환
                if 'send_interval' in data:
                    data['send_interval'] = int(data['send_interval'])
                
                # 체크박스 처리
                data['is_enabled'] = 'is_enabled' in data
                data['send_with_image'] = 'send_with_image' in data
                
                # 이미지 경로 처리 - 빈 문자열이면 None으로 설정
                if 'image_path' in data and data['image_path'].strip() == '':
                    data['image_path'] = None
                
                # JSON 파일에 설정 저장
                success = self.config.update(**data)
                
                if success:
                    print("설정이 저장되었습니다.")
                    
                    # 실행 중인 봇에 설정 적용
                    if self.bot and hasattr(self.bot, '_loop') and self.bot._loop:
                        try:
                            future = asyncio.run_coroutine_threadsafe(
                                self.bot.update_config(**data),
                                self.bot._loop
                            )
                            future.result(timeout=5)  # 5초 타임아웃
                        except Exception as e:
                            print(f"봇 설정 업데이트 오류: {e}")
                else:
                    print("설정 저장에 실패했습니다.")
                
                return redirect(url_for('dashboard'))
            
            return render_template('config.html', config=self.config)
        
        @self.app.route('/api/bot/<action>', methods=['POST'])
        @require_auth
        def bot_control(action):
            """봇 제어 API"""
            try:
                if action == 'start':
                    if not self.bot or not self.bot.is_running:
                        self._start_bot()
                    return jsonify({'success': True, 'message': '봇이 시작되었습니다'})
                
                elif action == 'stop':
                    if self.bot:
                        self._stop_bot()
                    return jsonify({'success': True, 'message': '봇이 중지되었습니다'})
                
                elif action == 'send_now':
                    if self.bot:
                        future = asyncio.run_coroutine_threadsafe(
                            self.bot.send_auto_message(),
                            self.bot.loop
                        )
                        success = future.result(timeout=10)
                        message = '메시지가 전송되었습니다' if success else '메시지 전송에 실패했습니다'
                        return jsonify({'success': success, 'message': message})
                    else:
                        return jsonify({'success': False, 'message': '봇이 실행 중이 아닙니다'})
                
                else:
                    return jsonify({'success': False, 'message': '알 수 없는 명령입니다'})
                    
            except Exception as e:
                return jsonify({'success': False, 'message': str(e)})
        
        @self.app.route('/api/status')
        @require_auth
        def bot_status():
            """봇 상태 API"""
            # 봇 실행 상태 정확히 체크
            is_bot_connected = (self.bot is not None and 
                               hasattr(self.bot, 'is_ready') and 
                               self.bot.is_ready() and
                               not self.bot.is_closed())
            
            is_scheduler_running = (self.bot is not None and 
                                  hasattr(self.bot, 'is_running') and 
                                  self.bot.is_running)
            
            next_time = None
            if self.bot and hasattr(self.bot, 'next_send_time') and self.bot.next_send_time:
                # ISO 형식으로 변환
                next_time = self.bot.next_send_time.isoformat()
            
            status = {
                'is_running': is_scheduler_running,
                'is_connected': is_bot_connected,
                'is_enabled': self.config.is_enabled,
                'next_send_time': next_time,
                'current_time': datetime.now().isoformat(),
                'bot_user': str(self.bot.user) if is_bot_connected else None
            }
            return jsonify(status)
        
        @self.app.route('/api/images')
        @require_auth
        def list_images():
            """현재 설정된 이미지 조회 API"""
            try:
                current_image = None
                if self.config.image_path and os.path.exists(self.config.image_path):
                    file_size = os.path.getsize(self.config.image_path)
                    current_image = {
                        'filename': os.path.basename(self.config.image_path),
                        'path': self.config.image_path,
                        'size': file_size,
                        'size_mb': round(file_size / 1024 / 1024, 2)
                    }
                
                return jsonify({'current_image': current_image})
            except Exception as e:
                return jsonify({'current_image': None, 'error': str(e)})
        
        @self.app.route('/api/images/upload', methods=['POST'])
        @require_auth
        def upload_image():
            """이미지 업로드 API - 기존 이미지 교체"""
            try:
                if 'file' not in request.files:
                    return jsonify({'success': False, 'message': '파일이 선택되지 않았습니다'})
                
                file = request.files['file']
                if file.filename == '':
                    return jsonify({'success': False, 'message': '파일이 선택되지 않았습니다'})
                
                # 파일 확장자 검사
                allowed_extensions = {'.jpg', '.jpeg', '.png', '.gif', '.webp'}
                filename = secure_filename(file.filename)
                _, ext = os.path.splitext(filename.lower())
                
                if ext not in allowed_extensions:
                    return jsonify({'success': False, 'message': f'지원하지 않는 파일 형식입니다. 지원 형식: {", ".join(allowed_extensions)}'})
                
                # 파일 크기 검사 (10MB 제한) - 스트리밍 방식
                chunk_size = 8192  # 8KB 청크
                file_size = 0
                max_size = 10 * 1024 * 1024  # 10MB
                
                # 청크 단위로 읽으며 크기 계산
                while True:
                    chunk = file.read(chunk_size)
                    if not chunk:
                        break
                    file_size += len(chunk)
                    if file_size > max_size:
                        return jsonify({'success': False, 'message': '파일 크기가 10MB를 초과했습니다'})
                
                file.seek(0)  # 파일 시작으로 돌아가기
                
                # 기존 이미지 삭제
                if self.config.image_path and os.path.exists(self.config.image_path):
                    try:
                        os.remove(self.config.image_path)
                    except:
                        pass
                
                # 새 이미지 저장 (고정된 파일명 사용)
                # Docker: /app/assets/images, Local: backend/../assets/images
                current_dir = os.path.dirname(os.path.abspath(__file__))  # /app/src
                project_root = os.path.dirname(current_dir)  # /app
                images_dir = os.path.join(project_root, "assets", "images")
                os.makedirs(images_dir, exist_ok=True)
                
                # 항상 같은 파일명으로 저장 (확장자만 유지)
                new_filename = f"bot_image{ext}"
                file_path = os.path.join(images_dir, new_filename)
                
                file.save(file_path)
                
                # 설정 업데이트
                self.config.update(image_path=file_path)
                
                return jsonify({
                    'success': True, 
                    'message': '이미지가 업로드되었습니다',
                    'filename': new_filename,
                    'size_mb': round(file_size / 1024 / 1024, 2)
                })
                
            except Exception as e:
                return jsonify({'success': False, 'message': f'업로드 실패: {str(e)}'})
        
        @self.app.route('/api/images/<filename>')
        def serve_image(filename):
            """이미지 파일 서빙 (인증 불필요 - 이미지는 공개)"""
            try:
                # 현재 설정된 이미지만 서빙
                if not self.config.image_path:
                    print(f"⚠️ 이미지 경로 미설정: config.image_path={self.config.image_path}")
                    return jsonify({'error': '이미지가 설정되지 않았습니다'}), 404
                
                if not os.path.exists(self.config.image_path):
                    print(f"❌ 이미지 파일 없음: {self.config.image_path}")
                    return jsonify({'error': f'이미지를 찾을 수 없습니다: {self.config.image_path}'}), 404
                
                # 파일명 확인 (보안)
                config_filename = os.path.basename(self.config.image_path)
                if filename != config_filename:
                    print(f"⚠️ 파일명 불일치: 요청={filename}, 설정={config_filename}")
                    return jsonify({'error': '잘못된 이미지 요청입니다'}), 400
                
                print(f"✅ 이미지 서빙: {self.config.image_path}")
                # 이미지 파일 서빙
                return send_file(
                    self.config.image_path,
                    mimetype=f'image/{os.path.splitext(filename)[1][1:]}'  # .png -> image/png
                )
                
            except Exception as e:
                print(f"❌ 이미지 서빙 오류: {e}")
                import traceback
                traceback.print_exc()
                return jsonify({'error': str(e)}), 500
        
        @self.app.route('/api/images/delete', methods=['DELETE'])
        @require_auth
        def delete_image():
            """현재 이미지 삭제 API"""
            try:
                if not self.config.image_path or not os.path.exists(self.config.image_path):
                    return jsonify({'success': False, 'message': '삭제할 이미지가 없습니다'})
                
                os.remove(self.config.image_path)
                
                # 설정에서 이미지 경로 제거
                self.config.update(image_path=None)
                
                return jsonify({
                    'success': True,
                    'message': '이미지가 삭제되었습니다'
                })
                
            except Exception as e:
                return jsonify({'success': False, 'message': f'삭제 실패: {str(e)}'})
    
    def _start_bot(self):
        """봇 시작"""
        if self.bot_thread and self.bot_thread.is_alive():
            return
        
        def run_bot():
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            
            try:
                self.bot = DiscordAutoBot(self.config)
                # 봇에 루프 설정
                self.bot._loop = loop
                
                loop.run_until_complete(self.bot.start(self.config.user_token))
            except Exception as e:
                print(f"봇 실행 오류: {e}")
            finally:
                if self.bot:
                    self.bot.is_running = False
                loop.close()
        
        self.bot_thread = threading.Thread(target=run_bot, daemon=True)
        self.bot_thread.start()
    
    def _stop_bot(self):
        """봇 중지"""
        if self.bot:
            try:
                # 스케줄러 먼저 중지
                if hasattr(self.bot, '_loop') and self.bot._loop and not self.bot._loop.is_closed():
                    try:
                        future = asyncio.run_coroutine_threadsafe(
                            self.bot.stop_scheduler(),
                            self.bot._loop
                        )
                        future.result(timeout=5)  # 5초 타임아웃
                    except (asyncio.TimeoutError, RuntimeError):
                        pass  # 타임아웃이나 루프 종료는 무시
                
                # 봇 연결 종료
                if hasattr(self.bot, '_loop') and self.bot._loop and not self.bot._loop.is_closed():
                    try:
                        future = asyncio.run_coroutine_threadsafe(
                            self.bot.close(),
                            self.bot._loop
                        )
                        future.result(timeout=5)  # 5초 타임아웃
                    except (asyncio.TimeoutError, RuntimeError):
                        pass  # 타임아웃이나 루프 종료는 무시
                        
            except Exception as e:
                # 조용히 처리 (로그만 출력하지 않음)
                pass
            finally:
                self.bot = None
    
    def run(self, host='0.0.0.0', port=8080, debug=False):
        """웹 서버 실행"""
        self.app.run(host=host, port=port, debug=debug)
        