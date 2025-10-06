import os
import discord
import asyncio
from typing import Optional
from datetime import datetime, timedelta

from src.config import BotConfig

class DiscordAutoBot(discord.Client):
    """Discord 자동 메시지 봇 - 최적화 버전
    
    성능 개선사항:
    - 연결 타임아웃 30초
    - heartbeat 타임아웃 60초
    - 불필요한 intent 최소화
    """
    
    def __init__(self, config: BotConfig, loop=None):
        # discord.py-self는 intents를 지원하지 않으므로 기본 초기화
        super().__init__(
            self_bot=True,
            heartbeat_timeout=60.0,  # heartbeat 타임아웃
            guild_ready_timeout=30.0  # 길드 준비 타임아웃
        )
        self.config = config
        self.is_running = False
        self.scheduler_task: Optional[asyncio.Task] = None
        self.next_send_time: Optional[datetime] = None
        self._loop = loop or asyncio.get_event_loop()
        
    async def on_ready(self):
        """봇이 준비되었을 때 실행"""
        print(f'✅ 로그인 성공: {self.user} (ID: {self.user.id})')
        print(f'📅 계정 생성일: {self.user.created_at}')
        
        # 채널 확인
        channel = self.get_channel(int(self.config.channel_id))
        if not channel:
            print(f"❌ 채널 ID {self.config.channel_id}를 찾을 수 없습니다.")
            await self.close()
            return
        
        print(f"📨 전송 채널: #{channel.name} (서버: {channel.guild.name})")
        print(f"⏰ 전송 간격: {self.config.send_interval}초 ({self.config.send_interval//60}분)")
        print(f"🎛️ 봇 상태: {'활성화' if self.config.is_enabled else '비활성화'}")
        print(f"🖼️ 이미지 설정: {'이미지와 함께 전송' if self.config.send_with_image else '텍스트만 전송'}")
        
        # 자동 전송 시작
        if self.config.is_enabled:
            await self.start_scheduler()
    
    async def start_scheduler(self):
        """스케줄러 시작"""
        if self.is_running:
            return
            
        self.is_running = True
        print("🚀 메시지 스케줄러 시작")
        
        # 첫 메시지 즉시 전송
        await self.send_auto_message()
        
        # 스케줄러 태스크 시작
        self.scheduler_task = asyncio.create_task(self._scheduler_loop())
    
    async def stop_scheduler(self):
        """스케줄러 중지"""
        self.is_running = False
        if self.scheduler_task:
            self.scheduler_task.cancel()
            try:
                await self.scheduler_task
            except asyncio.CancelledError:
                pass
        print("⏸️ 메시지 스케줄러 중지")
    
    async def _scheduler_loop(self):
        """스케줄러 루프 - 최적화된 로깅"""
        try:
            while self.is_running:
                # 다음 전송 시간 계산
                self.next_send_time = datetime.now() + timedelta(seconds=self.config.send_interval)
                # 로깅 축소: 시간만 표시
                print(f"⏰ 다음 전송: {self.next_send_time.strftime('%H:%M:%S')}")
                
                # 대기
                await asyncio.sleep(self.config.send_interval)
                
                if self.is_running and self.config.is_enabled:
                    await self.send_auto_message()
                    
        except asyncio.CancelledError:
            pass  # 조용히 종료
        except Exception as e:
            print(f"❌ 스케줄러 오류: {e}")
    
    async def send_auto_message(self) -> bool:
        """자동 메시지 전송"""
        try:
            channel = self.get_channel(int(self.config.channel_id))
            if not channel:
                print(f"❌ 채널을 찾을 수 없습니다: {self.config.channel_id}")
                return False
            
            # 이미지와 함께 보내기 설정 확인
            if self.config.send_with_image and self.config.image_path:
                if os.path.exists(self.config.image_path):
                    file = discord.File(self.config.image_path)
                    await channel.send(self.config.message_content, file=file)
                    print(f"📨 메시지+이미지 전송 완료")
                else:
                    await channel.send(self.config.message_content)
                    print(f"📨 메시지 전송 완료 (이미지 없음)")
            else:
                # 텍스트만 전송
                await channel.send(self.config.message_content)
                print(f"📨 메시지 전송 완료")
            
            return True
            
        except discord.HTTPException as e:
            print(f"❌ HTTP 오류: {e}")
            return False
        except discord.Forbidden:
            print("❌ 권한 없음: 메시지 전송 권한이 필요합니다")
            return False
        except Exception as e:
            print(f"❌ 전송 오류: {e}")
            return False
    
    async def update_config(self, **kwargs):
        """실행 중 설정 업데이트"""
        # 설정 업데이트
        for key, value in kwargs.items():
            if hasattr(self.config, key):
                setattr(self.config, key, value)
                print(f"🔧 설정 업데이트: {key} = {value}")
        
        # 활성화 상태 변경시 스케줄러 제어
        if 'is_enabled' in kwargs:
            if kwargs['is_enabled'] and not self.is_running:
                await self.start_scheduler()
            elif not kwargs['is_enabled'] and self.is_running:
                await self.stop_scheduler()
        
        # 간격 변경시 스케줄러 재시작
        if 'send_interval' in kwargs and self.is_running:
            print("⚙️ 전송 간격 변경으로 스케줄러 재시작")
            await self.stop_scheduler()
            await asyncio.sleep(1)
            if self.config.is_enabled:
                await self.start_scheduler()
    
    async def on_error(self, event, *args, **kwargs):
        """오류 처리"""
        print(f"❌ Discord 이벤트 오류: {event}")
        import traceback
        traceback.print_exc()
