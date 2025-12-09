# -*- coding: utf-8 -*-
"""
미국 주식 저평가 매수 알림 앱
================================
RSI 30 이하 또는 전일 대비 -5% 하락 시 텔레그램으로 알림을 보냅니다.
Streamlit Community Cloud 배포용 - st.secrets 사용
"""

import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import requests
from datetime import datetime, timedelta
import pytz
import time

# ============================================================
# 페이지 설정
# ============================================================
st.set_page_config(
    page_title="📈 미국 주식 저평가 알림",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ============================================================
# st.secrets에서 텔레그램 설정 불러오기
# ============================================================
def get_telegram_config():
    """st.secrets에서 텔레그램 설정을 안전하게 불러옵니다."""
    try:
        bot_token = st.secrets.get("TELEGRAM_BOT_TOKEN", "")
        chat_id = st.secrets.get("TELEGRAM_CHAT_ID", "")
        return bot_token, chat_id
    except Exception:
        return "", ""

BOT_TOKEN, CHAT_ID = get_telegram_config()

# ============================================================
# 커스텀 CSS 스타일링
# ============================================================
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Noto+Sans+KR:wght@300;400;500;700&family=JetBrains+Mono:wght@400;500&display=swap');
    
    * {
        font-family: 'Noto Sans KR', sans-serif;
    }
    
    .main {
        background: linear-gradient(135deg, #0f0f23 0%, #1a1a2e 50%, #16213e 100%);
    }
    
    .stApp {
        background: linear-gradient(135deg, #0f0f23 0%, #1a1a2e 50%, #16213e 100%);
    }
    
    h1, h2, h3 {
        color: #00d4aa !important;
        font-weight: 700 !important;
    }
    
    .metric-card {
        background: linear-gradient(145deg, #1e1e3f 0%, #2d2d5a 100%);
        border-radius: 16px;
        padding: 20px;
        border: 1px solid #3d3d6b;
        box-shadow: 0 8px 32px rgba(0, 212, 170, 0.1);
    }
    
    .status-open {
        background: linear-gradient(90deg, #00d4aa, #00b894);
        color: #0f0f23;
        padding: 8px 16px;
        border-radius: 20px;
        font-weight: 700;
        display: inline-block;
    }
    
    .status-closed {
        background: linear-gradient(90deg, #e74c3c, #c0392b);
        color: white;
        padding: 8px 16px;
        border-radius: 20px;
        font-weight: 700;
        display: inline-block;
    }
    
    .signal-alert {
        background: linear-gradient(145deg, #e74c3c, #c0392b);
        color: white;
        padding: 16px;
        border-radius: 12px;
        margin: 10px 0;
        font-weight: 500;
        animation: pulse 2s infinite;
    }
    
    @keyframes pulse {
        0% { box-shadow: 0 0 0 0 rgba(231, 76, 60, 0.7); }
        70% { box-shadow: 0 0 0 10px rgba(231, 76, 60, 0); }
        100% { box-shadow: 0 0 0 0 rgba(231, 76, 60, 0); }
    }
    
    .stDataFrame {
        background: #1e1e3f !important;
        border-radius: 12px !important;
    }
    
    div[data-testid="stDataFrame"] > div {
        background: #1e1e3f !important;
        border-radius: 12px !important;
    }
    
    .stButton > button {
        background: linear-gradient(90deg, #00d4aa, #00b894) !important;
        color: #0f0f23 !important;
        font-weight: 700 !important;
        border: none !important;
        border-radius: 12px !important;
        padding: 12px 24px !important;
        font-size: 16px !important;
        transition: all 0.3s ease !important;
    }
    
    .stButton > button:hover {
        transform: translateY(-2px) !important;
        box-shadow: 0 8px 24px rgba(0, 212, 170, 0.4) !important;
    }
    
    .sidebar .stTextInput > div > div > input {
        background: #2d2d5a !important;
        border: 1px solid #3d3d6b !important;
        color: white !important;
        border-radius: 8px !important;
    }
    
    section[data-testid="stSidebar"] {
        background: linear-gradient(180deg, #1a1a2e 0%, #16213e 100%) !important;
        border-right: 1px solid #3d3d6b !important;
    }
    
    .info-box {
        background: linear-gradient(145deg, #2d2d5a, #1e1e3f);
        border-left: 4px solid #00d4aa;
        padding: 16px;
        border-radius: 0 12px 12px 0;
        margin: 16px 0;
    }
    
    .config-status {
        padding: 12px;
        border-radius: 8px;
        margin: 8px 0;
    }
    
    .config-ok {
        background: rgba(0, 212, 170, 0.2);
        border: 1px solid #00d4aa;
    }
    
    .config-error {
        background: rgba(231, 76, 60, 0.2);
        border: 1px solid #e74c3c;
    }
</style>
""", unsafe_allow_html=True)

# ============================================================
# 세션 상태 초기화
# ============================================================
if 'watchlist' not in st.session_state:
    st.session_state.watchlist = ['NVDA', 'GOOGL', 'MRVL', 'MU', 'AVGO']

if 'monitoring' not in st.session_state:
    st.session_state.monitoring = False

if 'last_alert_time' not in st.session_state:
    st.session_state.last_alert_time = {}

if 'alert_history' not in st.session_state:
    st.session_state.alert_history = []

if 'last_data_fetch' not in st.session_state:
    st.session_state.last_data_fetch = None

# ============================================================
# 유틸리티 함수들
# ============================================================

def calculate_rsi(prices, period=14):
    """RSI (상대강도지수) 직접 계산"""
    delta = prices.diff()
    
    gain = delta.where(delta > 0, 0)
    loss = (-delta).where(delta < 0, 0)
    
    avg_gain = gain.rolling(window=period, min_periods=period).mean()
    avg_loss = loss.rolling(window=period, min_periods=period).mean()
    
    rs = avg_gain / avg_loss
    rsi = 100 - (100 / (1 + rs))
    
    return rsi


def is_market_open():
    """미국 뉴욕 증시 개장 시간인지 확인 (09:30 ~ 16:00 EST)"""
    ny_tz = pytz.timezone('America/New_York')
    now_ny = datetime.now(ny_tz)
    
    # 주말 체크 (토요일=5, 일요일=6)
    if now_ny.weekday() >= 5:
        return False, now_ny, "주말"
    
    market_open = now_ny.replace(hour=9, minute=30, second=0, microsecond=0)
    market_close = now_ny.replace(hour=16, minute=0, second=0, microsecond=0)
    
    if market_open <= now_ny <= market_close:
        return True, now_ny, "개장 중"
    elif now_ny < market_open:
        return False, now_ny, "개장 전"
    else:
        return False, now_ny, "장 마감"


@st.cache_data(ttl=60)  # 60초 캐싱으로 API 호출 최소화
def get_stock_data(ticker):
    """주식 데이터 가져오기 (1분 단위, 최근 5일) - 캐싱 적용"""
    try:
        stock = yf.Ticker(ticker)
        
        # 1분 단위 데이터 (최대 7일까지 가능)
        df = stock.history(period="5d", interval="1m")
        
        if df.empty:
            return None, None, None, None, None
        
        # RSI 계산 (14기간)
        df['RSI'] = calculate_rsi(df['Close'], period=14)
        
        current_price = df['Close'].iloc[-1]
        current_rsi = df['RSI'].iloc[-1] if not pd.isna(df['RSI'].iloc[-1]) else None
        
        # 전일 종가 가져오기
        daily_df = stock.history(period="5d", interval="1d")
        if len(daily_df) >= 2:
            prev_close = daily_df['Close'].iloc[-2]
            change_pct = ((current_price - prev_close) / prev_close) * 100
        else:
            prev_close = current_price
            change_pct = 0
        
        return current_price, current_rsi, change_pct, prev_close, df
        
    except Exception as e:
        return None, None, None, None, None


def send_telegram_message(message):
    """텔레그램 메시지 전송 (st.secrets 사용)"""
    if not BOT_TOKEN or not CHAT_ID:
        return False, "텔레그램 설정이 필요합니다. (secrets.toml 확인)"
    
    try:
        url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
        payload = {
            "chat_id": CHAT_ID,
            "text": message,
            "parse_mode": "HTML"
        }
        response = requests.post(url, json=payload, timeout=10)
        
        if response.status_code == 200:
            return True, "메시지 전송 성공"
        else:
            error_info = response.json().get('description', response.text)
            return False, f"전송 실패: {error_info}"
    except requests.exceptions.Timeout:
        return False, "오류: 요청 시간 초과"
    except requests.exceptions.RequestException as e:
        return False, f"오류: {str(e)}"


def can_send_alert(ticker, cooldown_minutes=30):
    """알림 쿨다운 체크 (30분에 한 번만)"""
    now = datetime.now()
    last_alert = st.session_state.last_alert_time.get(ticker)
    
    if last_alert is None:
        return True
    
    time_diff = (now - last_alert).total_seconds() / 60
    return time_diff >= cooldown_minutes


def check_buy_signal(ticker, current_price, rsi, change_pct, rsi_threshold=30, drop_threshold=-5, cooldown=30):
    """매수 신호 체크 및 알림 전송"""
    signals = []
    
    # RSI 임계값 이하 체크
    if rsi is not None and rsi <= rsi_threshold:
        signals.append(f"RSI {rsi:.1f} (과매도)")
    
    # 하락률 임계값 이하 체크
    if change_pct is not None and change_pct <= drop_threshold:
        signals.append(f"전일 대비 {change_pct:.2f}% 하락")
    
    if signals and can_send_alert(ticker, cooldown):
        signal_text = " / ".join(signals)
        message = f"""
🚨 <b>매수 신호 포착!</b>

📊 종목: <b>{ticker}</b>
💵 현재가: <b>${current_price:.2f}</b>
📉 신호: {signal_text}

⏰ 시간: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
        """
        
        success, result = send_telegram_message(message)
        
        if success:
            st.session_state.last_alert_time[ticker] = datetime.now()
            st.session_state.alert_history.append({
                'time': datetime.now().strftime('%H:%M:%S'),
                'ticker': ticker,
                'price': current_price,
                'signal': signal_text
            })
        
        return True, signal_text, success
    
    return len(signals) > 0, signals[0] if signals else None, False


def rate_limited_sleep(seconds):
    """서버 부하 방지를 위한 대기 함수"""
    time.sleep(seconds)


# ============================================================
# 사이드바 구성
# ============================================================
with st.sidebar:
    st.markdown("## ⚙️ 설정")
    
    st.markdown("---")
    
    # 텔레그램 연결 상태 표시
    st.markdown("### 📬 텔레그램 알림")
    
    if BOT_TOKEN and CHAT_ID:
        st.markdown(
            '<div class="config-status config-ok">✅ 텔레그램 설정 완료</div>',
            unsafe_allow_html=True
        )
        st.caption(f"Chat ID: {CHAT_ID[:4]}...{CHAT_ID[-2:]}")
    else:
        st.markdown(
            '<div class="config-status config-error">❌ 텔레그램 설정 필요</div>',
            unsafe_allow_html=True
        )
        st.caption("Streamlit Cloud > Settings > Secrets에서 설정하세요")
        with st.expander("📋 설정 방법"):
            st.code("""
# Secrets에 아래 내용 추가:
TELEGRAM_BOT_TOKEN = "your-bot-token"
TELEGRAM_CHAT_ID = "your-chat-id"
            """, language="toml")
    
    # 텔레그램 테스트 버튼
    if st.button("📤 테스트 메시지 전송"):
        if BOT_TOKEN and CHAT_ID:
            with st.spinner("전송 중..."):
                success, result = send_telegram_message(
                    "✅ 텔레그램 연결 테스트 성공!\n미국 주식 알림 앱이 정상 작동합니다."
                )
            if success:
                st.success("✅ 테스트 메시지 전송 완료!")
            else:
                st.error(f"❌ {result}")
        else:
            st.warning("⚠️ 먼저 Secrets에서 텔레그램을 설정해주세요.")
    
    st.markdown("---")
    
    # 관심 종목 관리
    st.markdown("### 📋 관심 종목 관리")
    
    # 종목 추가
    new_ticker = st.text_input(
        "➕ 종목 추가",
        placeholder="예: AAPL",
        help="추가할 종목 심볼을 입력하세요"
    ).upper().strip()
    
    if st.button("추가하기") and new_ticker:
        if new_ticker not in st.session_state.watchlist:
            st.session_state.watchlist.append(new_ticker)
            st.success(f"✅ {new_ticker} 추가됨!")
            st.rerun()
        else:
            st.warning(f"⚠️ {new_ticker}는 이미 목록에 있습니다.")
    
    # 종목 삭제
    st.markdown("#### 🗑️ 종목 삭제")
    for ticker in st.session_state.watchlist:
        col1, col2 = st.columns([3, 1])
        with col1:
            st.text(ticker)
        with col2:
            if st.button("❌", key=f"del_{ticker}"):
                st.session_state.watchlist.remove(ticker)
                st.rerun()
    
    st.markdown("---")
    
    # 알림 설정
    st.markdown("### 🔔 알림 조건")
    rsi_threshold = st.slider("RSI 임계값", 10, 50, 30, help="이 값 이하일 때 알림")
    drop_threshold = st.slider("하락률 임계값 (%)", -10, -1, -5, help="이 값 이하일 때 알림")
    cooldown = st.slider("알림 간격 (분)", 10, 60, 30, help="동일 종목 알림 최소 간격")
    refresh_interval = st.slider("데이터 갱신 간격 (초)", 30, 120, 60, help="실시간 감시 시 데이터 갱신 주기")

# ============================================================
# 메인 화면
# ============================================================
st.markdown("# 📈 미국 주식 저평가 매수 알림")
st.markdown("##### RSI 과매도 및 급락 종목을 실시간으로 감시합니다")

# 시장 상태 표시
is_open, ny_time, market_status = is_market_open()

col1, col2, col3 = st.columns([2, 2, 2])

with col1:
    if is_open:
        st.markdown(f'<div class="status-open">🟢 {market_status}</div>', unsafe_allow_html=True)
    else:
        st.markdown(f'<div class="status-closed">🔴 {market_status}</div>', unsafe_allow_html=True)

with col2:
    st.markdown(f"🗽 **뉴욕 시간**: {ny_time.strftime('%Y-%m-%d %H:%M:%S')}")

with col3:
    kr_tz = pytz.timezone('Asia/Seoul')
    kr_time = datetime.now(kr_tz)
    st.markdown(f"🇰🇷 **한국 시간**: {kr_time.strftime('%Y-%m-%d %H:%M:%S')}")

st.markdown("---")

# 실시간 감시 버튼
col_btn1, col_btn2, col_btn3 = st.columns([1, 1, 2])

with col_btn1:
    start_btn = st.button("🚀 실시간 감시 시작", type="primary", use_container_width=True)

with col_btn2:
    refresh_btn = st.button("🔄 데이터 새로고침", use_container_width=True)

# 데이터 표시 영역
st.markdown("### 📊 관심 종목 현황")

# 데이터 로드 및 표시
if st.session_state.watchlist:
    data_rows = []
    signals_detected = []
    
    progress_bar = st.progress(0)
    status_text = st.empty()
    
    for idx, ticker in enumerate(st.session_state.watchlist):
        status_text.text(f"📡 {ticker} 데이터 로드 중...")
        progress_bar.progress((idx + 1) / len(st.session_state.watchlist))
        
        current_price, rsi, change_pct, prev_close, df = get_stock_data(ticker)
        
        # API 부하 방지를 위한 짧은 대기
        if idx < len(st.session_state.watchlist) - 1:
            rate_limited_sleep(0.5)
        
        if current_price is not None:
            # RSI 상태 이모지
            if rsi is not None:
                if rsi <= rsi_threshold:
                    rsi_status = "🔴 과매도"
                elif rsi >= 70:
                    rsi_status = "🟡 과매수"
                else:
                    rsi_status = "🟢 보통"
            else:
                rsi_status = "⚪ N/A"
            
            # 등락 상태 이모지
            if change_pct is not None:
                if change_pct <= drop_threshold:
                    change_status = "🔴"
                elif change_pct < 0:
                    change_status = "🟠"
                else:
                    change_status = "🟢"
            else:
                change_status = "⚪"
            
            data_rows.append({
                '종목': ticker,
                '현재가': f"${current_price:.2f}",
                '전일종가': f"${prev_close:.2f}" if prev_close else "N/A",
                '등락률': f"{change_status} {change_pct:.2f}%" if change_pct is not None else "N/A",
                'RSI (14)': f"{rsi:.1f}" if rsi else "N/A",
                '상태': rsi_status
            })
            
            # 매수 신호 체크
            has_signal, signal_text, alert_sent = check_buy_signal(
                ticker, current_price, rsi, change_pct, 
                rsi_threshold, drop_threshold, cooldown
            )
            
            if has_signal:
                signals_detected.append({
                    'ticker': ticker,
                    'price': current_price,
                    'signal': signal_text,
                    'alert_sent': alert_sent
                })
        else:
            data_rows.append({
                '종목': ticker,
                '현재가': "로드 실패",
                '전일종가': "N/A",
                '등락률': "N/A",
                'RSI (14)': "N/A",
                '상태': "⚪ 오류"
            })
    
    progress_bar.empty()
    status_text.empty()
    
    # 마지막 업데이트 시간 저장
    st.session_state.last_data_fetch = datetime.now()
    
    # 데이터프레임 표시
    df_display = pd.DataFrame(data_rows)
    st.dataframe(
        df_display,
        use_container_width=True,
        hide_index=True,
        column_config={
            '종목': st.column_config.TextColumn('종목', width='small'),
            '현재가': st.column_config.TextColumn('현재가', width='small'),
            '전일종가': st.column_config.TextColumn('전일종가', width='small'),
            '등락률': st.column_config.TextColumn('등락률', width='medium'),
            'RSI (14)': st.column_config.TextColumn('RSI (14)', width='small'),
            '상태': st.column_config.TextColumn('상태', width='medium'),
        }
    )
    
    # 매수 신호 표시
    if signals_detected:
        st.markdown("### 🚨 매수 신호 감지!")
        for signal in signals_detected:
            alert_icon = "📤" if signal['alert_sent'] else "⏳"
            st.markdown(
                f"""<div class="signal-alert">
                    {alert_icon} <b>{signal['ticker']}</b> - 현재가 ${signal['price']:.2f} | {signal['signal']}
                </div>""",
                unsafe_allow_html=True
            )
    
    # 알림 히스토리
    if st.session_state.alert_history:
        st.markdown("### 📜 알림 발송 기록")
        history_df = pd.DataFrame(st.session_state.alert_history[-10:])  # 최근 10개만
        st.dataframe(history_df, use_container_width=True, hide_index=True)

else:
    st.info("📋 사이드바에서 관심 종목을 추가해주세요.")

# 실시간 감시 모드
if start_btn:
    if not is_open:
        st.warning(f"⚠️ 현재 미국 증시가 {market_status} 상태입니다. 개장 시간(09:30~16:00 EST)에 다시 시도해주세요.")
    elif not BOT_TOKEN or not CHAT_ID:
        st.warning("⚠️ 텔레그램 설정이 필요합니다. Streamlit Cloud의 Secrets에서 설정해주세요.")
    else:
        st.markdown("### 🔴 실시간 감시 중...")
        st.markdown(f"*{refresh_interval}초마다 데이터 갱신, {cooldown}분 간격으로 알림 전송*")
        st.caption("페이지를 닫거나 새로고침하면 감시가 중단됩니다.")
        
        monitoring_placeholder = st.empty()
        
        # 실시간 감시 루프
        while True:
            # 시장 상태 재확인
            is_open, ny_time, market_status = is_market_open()
            
            if not is_open:
                monitoring_placeholder.warning(f"⚠️ 장이 마감되었습니다. ({market_status})")
                break
            
            with monitoring_placeholder.container():
                st.markdown(f"**마지막 업데이트**: {datetime.now().strftime('%H:%M:%S')}")
                
                for idx, ticker in enumerate(st.session_state.watchlist):
                    # 캐시 무효화를 위해 직접 호출
                    get_stock_data.clear()
                    current_price, rsi, change_pct, prev_close, df = get_stock_data(ticker)
                    
                    if current_price is not None:
                        has_signal, signal_text, alert_sent = check_buy_signal(
                            ticker, current_price, rsi, change_pct,
                            rsi_threshold, drop_threshold, cooldown
                        )
                        
                        status_icon = "🚨" if has_signal else "✅"
                        alert_status = " (알림 전송!)" if alert_sent else ""
                        st.text(f"{status_icon} {ticker}: ${current_price:.2f} | RSI: {rsi:.1f if rsi else 'N/A'} | {change_pct:.2f}%{alert_status}")
                    else:
                        st.text(f"⚪ {ticker}: 데이터 로드 실패")
                    
                    # API 부하 방지
                    if idx < len(st.session_state.watchlist) - 1:
                        rate_limited_sleep(1)
            
            # 서버 부하 방지를 위한 대기 (사용자 설정 값 사용)
            rate_limited_sleep(refresh_interval)
            st.rerun()

# 하단 정보
st.markdown("---")
st.markdown("""
<div class="info-box">
    <b>📌 사용 안내</b><br>
    • <b>RSI (상대강도지수)</b>: 30 이하면 과매도(저평가), 70 이상이면 과매수(고평가)로 판단합니다.<br>
    • <b>알림 조건</b>: RSI ≤ 30 또는 전일 대비 -5% 이상 하락 시 텔레그램으로 알림을 보냅니다.<br>
    • <b>알림 간격</b>: 동일 종목에 대해 30분에 한 번만 알림이 발송됩니다 (스팸 방지).<br>
    • <b>시장 시간</b>: 미국 뉴욕 증시 개장 시간 (09:30~16:00 EST) 동안만 감시가 활성화됩니다.
</div>
""", unsafe_allow_html=True)

st.markdown("---")
st.caption("Made with ❤️ using Streamlit | 투자는 본인 책임입니다.")
