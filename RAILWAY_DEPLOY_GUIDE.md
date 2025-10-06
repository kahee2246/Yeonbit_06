# 🚀 완전 자동화 Railway 배포 가이드

## ✨ 새로운 특징
- **웹 인터페이스 항상 실행**: 환경변수 없어도 웹 관리 페이지 접속 가능
- **스마트 fallback**: PostgreSQL 없어도 환경변수로 동작
- **친화적 안내**: 설정 누락시 자세한 가이드 제공
- **즉시 시작**: 배포 후 바로 웹에서 모든 설정 가능

## 🎯 초간단 배포 (3단계)

### 1단계: Railway 프로젝트 생성
```bash
1. Railway.app 접속 → GitHub 로그인
2. "New Project" → "Deploy from GitHub repo"
3. 이 저장소 선택
```

### 2단계: 환경변수 설정 (최소 2개만!)
```bash
Railway 대시보드 → Variables:

USER_TOKEN=your_discord_bot_token
PORT=8080
```

### 3단계: 완료!
```bash
✅ 자동 빌드 & 배포
✅ 웹 인터페이스 즉시 접속 가능
✅ /config 페이지에서 모든 설정 관리
```

## 🌐 배포 후 사용법

### 웹 인터페이스 접속
```
https://your-app.railway.app
```

### 설정 관리
```
https://your-app.railway.app/config
```
- 채널 ID 설정
- 메시지 내용 수정
- 전송 간격 조정
- 봇 활성화/비활성화

### 대시보드
```
https://your-app.railway.app/dashboard
```
- 실시간 봇 상태 확인
- 로그 모니터링
- 봇 제어 (시작/정지)

## 🔧 고급 설정 (선택사항)

### PostgreSQL 추가 (영구 설정 저장)
```bash
Railway 대시보드 → "Add Service" → "PostgreSQL"
→ DATABASE_URL 자동 생성됨
```

### 추가 환경변수 (선택)
```bash
CHANNEL_ID=your_channel_id          # 웹에서도 설정 가능
SEND_INTERVAL=1800                  # 기본: 30분
ADMIN_USERNAME=admin                # 기본값 사용 가능
ADMIN_PASSWORD=your_secure_password # 기본값 사용 가능
```

## 🎉 완성!
이제 Discord 봇이 Railway에서 24/7 실행되며, 웹에서 모든 설정을 편리하게 관리할 수 있습니다!
