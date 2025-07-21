import streamlit as st
import subprocess
import os
import re
import signal
import time
from pathlib import Path
from datetime import datetime, timedelta

# --- Configuration ---
LOG_FILE = Path("bot.log")
PID_FILE = Path("bot.pid")
STATUS_FILE = Path("bot_status.txt")

# --- Helper Functions ---

def get_bot_status():
    """Check if the bot process is running and its pause status."""
    if not PID_FILE.exists():
        return "Stopped", "N/A"
    
    try:
        pid = int(PID_FILE.read_text())
        os.kill(pid, 0)
    except (OSError, ValueError):
        if PID_FILE.exists():
            os.remove(PID_FILE)
        return "Stopped", "N/A"

    pause_status = "Paused" if STATUS_FILE.exists() and STATUS_FILE.read_text() == "paused" else "Running"
    return "Running", pause_status

def start_bot():
    """Starts the bot by running main.py as a background process."""
    if get_bot_status()[0] == "Running":
        st.warning("Bot is already running.")
        return
    
    process = subprocess.Popen(["python", "main.py"])
    PID_FILE.write_text(str(process.pid))
    
    if STATUS_FILE.exists():
        os.remove(STATUS_FILE)
        
    st.success(f"Bot started successfully with PID: {process.pid}")
    time.sleep(2)

def stop_bot():
    """Stops the bot process."""
    if get_bot_status()[0] == "Stopped":
        st.warning("Bot is already stopped.")
        return
        
    try:
        pid = int(PID_FILE.read_text())
        os.kill(pid, signal.SIGTERM)
        st.success(f"Stop signal sent to bot with PID: {pid}")
    except (OSError, ValueError, FileNotFoundError):
        st.error("Could not find or stop the bot process.")
    finally:
        if PID_FILE.exists():
            os.remove(PID_FILE)
        if STATUS_FILE.exists():
            os.remove(STATUS_FILE)
        time.sleep(1)

def toggle_pause_bot():
    """Pauses or resumes the bot by writing to the status file."""
    status, pause_status = get_bot_status()
    if status == "Stopped":
        st.error("Cannot pause/resume a stopped bot.")
        return

    if pause_status == "Running":
        STATUS_FILE.write_text("paused")
        st.info("Bot is now PAUSED.")
    else:
        if STATUS_FILE.exists():
            os.remove(STATUS_FILE)
        st.info("Bot has been RESUMED.")
    time.sleep(1)
    
# --- NEW FUNCTION TO CLEAR LOGS ---
def clear_log_file():
    """Truncates the log file to zero bytes."""
    if LOG_FILE.exists():
        try:
            # Opening in 'w' mode and immediately closing clears the file
            with open(LOG_FILE, 'w'):
                pass
            st.sidebar.success("Log file cleared! 🧹")
        except Exception as e:
            st.sidebar.error(f"Error clearing log: {e}")
    else:
        st.sidebar.warning("Log file does not exist.")
    time.sleep(1) # Give time for user to see the message

@st.cache_data(ttl=5)
def read_and_parse_logs():
    """Reads the log file and extracts unique user IDs."""
    if not LOG_FILE.exists():
        return [], set()
    
    with open(LOG_FILE, "r") as f:
        log_lines = f.readlines()
        
    user_ids = set()
    user_id_pattern = re.compile(r'(?:from|for|User) (\d{6,})')
    
    for line in log_lines:
        match = user_id_pattern.search(line)
        if match:
            user_ids.add(match.group(1))
            
    return log_lines, user_ids
    
def display_beautified_log(log_lines, selected_user="All Users"):
    """Parses and displays the log file with color-coding, filtered by user."""
    if selected_user != "All Users":
        log_lines = [line for line in log_lines if selected_user in line]

    if not log_lines:
        st.warning(f"No logs found for user: {selected_user}")
        return

    log_pattern = re.compile(r"(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2},\d{3}) - .*? - (INFO|ERROR|WARNING) - (.*)")

    for line in reversed(log_lines[-100:]):
        match = log_pattern.match(line)
        if match:
            timestamp, level, message = match.groups()
            time_only = timestamp.split(" ")[1].split(",")[0]

            with st.container(border=True):
                col1, col2 = st.columns([1, 8])
                with col1:
                    st.markdown(f"**`{time_only}`**")
                with col2:
                    if level == "ERROR":
                        st.error(message.strip(), icon="🚨")
                    elif level == "WARNING":
                        st.warning(message.strip(), icon="⚠️")
                    else:
                        st.markdown(f"`{message.strip()}`")
        else:
            st.text(line.strip())

def get_logs_since(start_datetime: datetime):
    """Filters log file for entries since a given datetime."""
    if not LOG_FILE.exists():
        return "Log file not found."

    with open(LOG_FILE, "r") as f:
        all_lines = f.readlines()

    filtered_logs = []
    log_pattern = re.compile(r"(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2},\d{3})")
    
    for line in all_lines:
        match = log_pattern.match(line)
        if match:
            timestamp_str = match.group(1)
            log_datetime = datetime.strptime(timestamp_str, "%Y-%m-%d %H:%M:%S,%f")
            if log_datetime >= start_datetime:
                filtered_logs.append(line)
    
    return "".join(filtered_logs) if filtered_logs else "No logs found since the specified time."

# --- Streamlit App Layout ---

st.set_page_config(page_title="Money Bhai Control Panel", layout="wide")
st.title("Money Bhai - Control Panel 🤖")

# --- Status and Controls ---
st.header("Bot Controls")
status, pause_status = get_bot_status()
col1, col2 = st.columns(2)
with col1:
    st.metric("Bot Process Status", status)
with col2:
    st.metric("Message Handling", pause_status)
st.divider()
c1, c2, c3 = st.columns(3)
with c1:
    if st.button("🚀 Start Bot", use_container_width=True, type="primary", disabled=(status=="Running")):
        start_bot()
        st.rerun()
with c2:
    pause_button_text = "⏸️ Pause Bot" if pause_status == "Running" else "▶️ Resume Bot"
    if st.button(pause_button_text, use_container_width=True, disabled=(status=="Stopped")):
        toggle_pause_bot()
        st.rerun()
with c3:
    if st.button("🛑 Stop Bot", use_container_width=True, disabled=(status=="Stopped")):
        stop_bot()
        st.rerun()
st.divider()

all_logs, user_ids = read_and_parse_logs()

# --- Sidebar for Filters ---
st.sidebar.title("Filters")
selected_user = st.sidebar.selectbox(
    "Filter Logs by User ID",
    options=["All Users"] + sorted(list(user_ids))
)
st.sidebar.divider()

# --- Log Copy Section ---
st.sidebar.header("Copy Recent Logs")
b_col1, b_col2, b_col3 = st.sidebar.columns(3)
if b_col1.button("5 min", use_container_width=True):
    st.session_state.log_to_show = get_logs_since(datetime.now() - timedelta(minutes=5))
    st.rerun()
if b_col2.button("10 min", use_container_width=True):
    st.session_state.log_to_show = get_logs_since(datetime.now() - timedelta(minutes=10))
    st.rerun()
if b_col3.button("15 min", use_container_width=True):
    st.session_state.log_to_show = get_logs_since(datetime.now() - timedelta(minutes=15))
    st.rerun()

st.sidebar.markdown("---")
custom_minutes = st.sidebar.number_input("Or enter custom minutes:", min_value=1, value=60)
if st.sidebar.button("Get Custom", use_container_width=True):
    st.session_state.log_to_show = get_logs_since(datetime.now() - timedelta(minutes=custom_minutes))
    st.rerun()

# --- NEW SECTION IN SIDEBAR FOR LOG MANAGEMENT ---
st.sidebar.divider()
st.sidebar.header("Log Management")
if st.sidebar.button("🧹 Clear Log File", use_container_width=True, type="secondary", help="Deletes the content of bot.log"):
    clear_log_file()
    st.rerun()
# -----------------------------------------------

# --- Main Page Content ---
if 'log_to_show' in st.session_state:
    st.header("Copyable Log Text")
    st.text_area("Logs:", value=st.session_state.log_to_show, height=250)
    if st.button("Close Copy Box"):
        del st.session_state.log_to_show
        st.rerun()
st.divider()

st.header(f"Live Log Viewer: {selected_user}")
if not all_logs:
    st.info("Log file is empty or not found. Start the bot or clear filters to see logs.")
else:
    display_beautified_log(all_logs, selected_user)

time.sleep(3)
st.rerun()