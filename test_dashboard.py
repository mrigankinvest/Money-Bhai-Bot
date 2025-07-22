import streamlit as st
import subprocess
import json
import pandas as pd
import os
import signal
import threading
import time
import ast # Using AST for safer docstring parsing

# --- Page Configuration ---
st.set_page_config(
    page_title="Money Bhai - Test Control Center",
    page_icon="🤖",
    layout="wide"
)

# --- State Management ---
# Initialize session state variables
if 'test_process' not in st.session_state:
    st.session_state.test_process = None
if 'test_running' not in st.session_state:
    st.session_state.test_running = False
if 'output_buffer' not in st.session_state:
    st.session_state.output_buffer = []
if 'report_data' not in st.session_state:
    st.session_state.report_data = None

# --- Helper Functions ---
def parse_test_report(report_path="test-report.json"):
    """Parses the JSON report file and structures it for the dashboard."""
    if not os.path.exists(report_path):
        return None, None

    with open(report_path, 'r', encoding='utf-8') as f:
        try:
            report = json.load(f)
        except json.JSONDecodeError:
            return None, None

    summary = report.get('summary', {})
    tests = []
    # Enumerate to create a simple Test ID
    for i, test in enumerate(report.get('tests', [])):
        nodeid_parts = test.get('nodeid', '').split('::')
        intention = "N/A"
        
        # Safely parse intention from test file docstrings using AST
        if len(nodeid_parts) > 1:
            test_file_path, test_func_name = nodeid_parts[0], nodeid_parts[-1]
            try:
                with open(test_file_path, 'r', encoding='utf-8') as f_source:
                    source_code = f_source.read()
                tree = ast.parse(source_code)
                for node in ast.walk(tree):
                    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == test_func_name:
                        docstring = ast.get_docstring(node)
                        if docstring:
                            intention = docstring.strip().split('\n')[0]
                        break
            except (FileNotFoundError, SyntaxError, IndexError):
                intention = "Could not parse intention."

        tests.append({
            "Test ID.": f"T-{i+1:02d}",
            "Intention": intention,
            "Input": test.get('nodeid', 'N/A'),
            "Output": test.get('longrepr', 'No output.') if test.get('outcome') != 'passed' else 'OK',
            "Status": test.get('outcome', 'unknown').upper()
        })
    
    df = pd.DataFrame(tests)
    # Reorder columns to match the user's request exactly
    final_columns = ["Test ID.", "Intention", "Input", "Output", "Status"]
    # Ensure all requested columns exist, fill missing with N/A
    for col in final_columns:
        if col not in df.columns:
            df[col] = "N/A"
            
    return summary, df[final_columns]

def run_tests_in_thread(output_buffer):
    """Runs pytest in a subprocess and captures output into a shared buffer."""
    try:
        command = ["pytest", "--json-report", "--json-report-file=test-report.json"]
        # Use preexec_fn to create a new process group for reliable termination
        process = subprocess.Popen(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding='utf-8',
            preexec_fn=os.setsid 
        )
        st.session_state.test_process = process

        # Read output line by line and append to the shared buffer
        for line in iter(process.stdout.readline, ''):
            output_buffer.append(line)
        
        process.stdout.close()
        process.wait()
    
    finally:
        # Mark the test as finished
        st.session_state.test_running = False
        st.session_state.test_process = None

# --- UI Layout ---
st.title("🤖 Money Bhai - Test Control Center")
st.markdown("Run, monitor, and review your `pytest` test suite from this interactive dashboard.")

col1, col2, _ = st.columns([1, 1, 5])

with col1:
    if st.button("▶️ Run All Tests", use_container_width=True, disabled=st.session_state.test_running):
        st.session_state.test_running = True
        st.session_state.output_buffer = [] # Reset the buffer
        st.session_state.report_data = None
        
        # Pass the buffer to the thread
        thread = threading.Thread(target=run_tests_in_thread, args=(st.session_state.output_buffer,))
        thread.start()
        st.rerun()

with col2:
    if st.button("⏹️ Stop Tests", use_container_width=True, disabled=not st.session_state.test_running):
        if st.session_state.test_process:
            # Terminate the entire process group
            os.killpg(os.getpgid(st.session_state.test_process.pid), signal.SIGTERM)
            st.session_state.test_running = False
            st.session_state.test_process = None
            st.session_state.output_buffer.append("\n\n--- TEST RUN MANUALLY STOPPED ---")
            st.rerun()

# --- Live Output & Results Display ---
if st.session_state.test_running:
    st.info("Test run in progress...")
    # Join the buffer content for display
    live_output = "".join(st.session_state.get('output_buffer', []))
    with st.expander("Live Test Output", expanded=True):
        st.code(live_output, language='bash')
    time.sleep(1) # Small delay to prevent excessive reruns
    st.rerun()
else:
    # When not running, process the final results
    if st.session_state.report_data is None:
        summary, df = parse_test_report()
        if df is not None:
            st.session_state.report_data = (summary, df)

    if st.session_state.report_data:
        summary, df = st.session_state.report_data
        st.header("Test Results Summary")

        total = summary.get('total', 0)
        passed = summary.get('passed', 0)
        failed = summary.get('failed', 0)
        error = summary.get('error', 0)
        
        summary_cols = st.columns(4)
        summary_cols[0].metric("Total Tests", total)
        summary_cols[1].metric("✅ Passed", passed)
        summary_cols[2].metric("❌ Failed", failed, delta=-failed if failed > 0 else 0)
        summary_cols[3].metric("⚠️ Errors", error, delta=-error if error > 0 else 0)

        st.header("Detailed Test Report")
        st.dataframe(df, use_container_width=True)

        final_output = "".join(st.session_state.get('output_buffer', []))
        if final_output:
            with st.expander("View Full Test Output"):
                st.code(final_output, language='bash')

    elif not st.session_state.test_running:
        st.info("Click 'Run All Tests' to begin. A `test-report.json` file must be present to view past results.")
