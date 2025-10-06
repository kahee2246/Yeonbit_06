#!/usr/bin/env python3
"""
Discord Auto Bot - 백엔드 서버 (Flask API)
"""

import os
import sys
import time
import asyncio
import threading
import argparse
from pathlib import Path

# 프로젝트 루트 디렉토리를 Python 경로에 추가
project_root = Path(__file__).parent
monorepo_root = project_root.parent
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(monorepo_root))

from src.config import BotConfig
from src.bot import DiscordAutoBot
from src.web_interface import WebInterface

def main():
    """메인 함수"""
    parser = argparse.ArgumentParser(description='Discord Auto Bot Backend')
    parser.add_argument('--mode', choices=['bot', 'web', 'both'], default='both',
                      help='실행 모드 선택')
    parser.add_argument('--web-port', type=int, default=5000,
                      help='웹 인터페이스 포트')
    
    args = parser.parse_args()
    
    print("🤖 Discord Auto Bot Backend 시작")
    print("=" * 50)
    
    try:
        # 설정 로드 (여기서 .env 파일이 로드됨)
        print("설정을 로드하는 중...")
        config = BotConfig.load()
        
        # 환경변수 체크 (웹 모드에서는 선택사항)
        print("환경 변수를 확인하는 중...")
        user_token = config.user_token
        
        if not user_token and args.mode == 'bot':
            # 봇 전용 모드에서는 토큰이 필수
            print("❌ USER_TOKEN 환경변수가 설정되지 않았습니다!")
            print("🔧 다음 환경변수를 설정해주세요:")
            print("   USER_TOKEN=your_discord_user_token")
            print("   CHANNEL_ID=your_channel_id")
            
            print("60초 후 재시도합니다...")
            time.sleep(60)
            return main()
        elif user_token:
            print("✅ USER_TOKEN이 설정되어 있습니다.")
        else:
            print("⚠️ USER_TOKEN이 없습니다. 웹 서버만 시작합니다.")
        
        if args.mode == 'web':
            # 웹 인터페이스만 실행
            print(f"🌐 웹 인터페이스를 {args.web_port}번 포트에서 시작합니다...")
            web_interface = WebInterface(config)
            web_interface.run(host='0.0.0.0', port=args.web_port, debug=False)
            
        elif args.mode == 'bot':
            # 봇만 실행 (CLI 모드)
            print("🤖 Discord 봇을 시작합니다...")
            if not user_token:
                print("❌ 봇 모드는 USER_TOKEN이 필요합니다!")
                return
                
            bot = DiscordAutoBot(config)
            asyncio.run(bot.start(user_token))
            
        else:  # both
            # 봇과 웹 인터페이스 동시 실행
            print("🚀 봇과 웹 인터페이스를 모두 시작합니다...")
            
            # 웹 인터페이스를 먼저 초기화 (healthcheck를 위해)
            print(f"🌐 웹 인터페이스를 {args.web_port}번 포트에서 시작합니다...")
            web_interface = WebInterface(config)
            
            # 봇을 별도 스레드에서 실행
            def run_bot():
                if user_token:
                    print("🤖 Discord 봇을 시작합니다...")
                    bot = DiscordAutoBot(config)
                    asyncio.run(bot.start(user_token))
                else:
                    print("⚠️ USER_TOKEN이 없어 Discord 봇을 시작할 수 없습니다.")
                    print("💡 웹 인터페이스만 실행됩니다.")
            
            # 봇 스레드 시작 (daemon=True로 웹 서버 종료 시 함께 종료)
            bot_thread = threading.Thread(target=run_bot, daemon=True)
            bot_thread.start()
            
            # 웹 서버 실행 (메인 스레드에서)
            web_interface.run(host='0.0.0.0', port=args.web_port, debug=False)
            
    except KeyboardInterrupt:
        print("\n👋 봇을 종료합니다...")
    except Exception as e:
        print(f"❌ 오류 발생: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
