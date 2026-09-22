import streamlit as st
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import hashlib
import json
import time
from pathlib import Path

from google import genai

from supabase import create_client, Client

from qiskit import QuantumCircuit, transpile
from qiskit_aer import AerSimulator

try:
    from streamlit_sortables import sort_items
    SORTABLES_AVAILABLE = True
except Exception:
    SORTABLES_AVAILABLE = False


# =========================================================
# PAGE CONFIGURATION
# =========================================================

st.set_page_config(
    page_title="Quantum LearnLab AI",
    page_icon="⚛️",
    layout="wide"
)


# =========================================================
# FILE PATHS
# =========================================================

ASSETS_DIR = Path("assets")

FIG_QUBIT = ASSETS_DIR / "fig1_qubit_superposition.png"
FIG_ENTANGLEMENT = ASSETS_DIR / "fig3_entanglement_teleportation.png"
FIG_CIRCUIT = ASSETS_DIR / "fig4_hadamard_cnot_circuit.png"


# =========================================================
# SUPABASE AUTHENTICATION + PERSISTENT DATA
# =========================================================

@st.cache_resource
def get_supabase() -> Client:
    url = st.secrets.get("SUPABASE_URL", "")
    key = st.secrets.get("SUPABASE_KEY", "")
    if not url or not key:
        return None
    return create_client(url, key)


def load_profile(user_id):
    sb = get_supabase()
    if sb is None:
        return None
    try:
        result = sb.table("profiles").select("*").eq("id", user_id).limit(1).execute()
        if result.data:
            return result.data[0]
    except Exception as e:
        st.error(f"Could not load your profile: {e}")
    return None


def save_profile():
    user_id = st.session_state.get("user_id", "")
    if not user_id:
        return
    sb = get_supabase()
    if sb is None:
        return
    data = {
        "id": user_id,
        "name": st.session_state.get("user_name", ""),
        "completed": st.session_state.get("completed", []),
        "quiz_score": int(st.session_state.get("quiz_score", 0)),
        "points": int(st.session_state.get("points", 0)),
        "badges": st.session_state.get("badges", []),
        "history": st.session_state.get("history", []),
    }
    try:
        sb.table("profiles").upsert(data).execute()
    except Exception as e:
        st.warning(f"Progress could not be saved: {e}")


def load_user_progress(user_id):
    profile = load_profile(user_id)
    if not profile:
        return
    st.session_state.user_name = profile.get("name", st.session_state.user_name)
    st.session_state.completed = profile.get("completed") or []
    st.session_state.quiz_score = int(profile.get("quiz_score") or 0)
    st.session_state.points = int(profile.get("points") or 0)
    st.session_state.badges = profile.get("badges") or []
    st.session_state.history = profile.get("history") or []


def require_supabase():
    if get_supabase() is None:
        st.error("Supabase is not configured. Add SUPABASE_URL and SUPABASE_KEY to Streamlit Secrets.")
        st.stop()


def sign_in(email, password):
    sb = get_supabase()
    if sb is None:
        return None, "Supabase is not configured."
    try:
        result = sb.auth.sign_in_with_password({"email": email.strip().lower(), "password": password})
        return result, None
    except Exception as e:
        return None, str(e)


def sign_up(email, password, name):
    sb = get_supabase()
    if sb is None:
        return None, "Supabase is not configured."
    try:
        result = sb.auth.sign_up({
            "email": email.strip().lower(),
            "password": password,
            "options": {"data": {"name": name.strip()}},
        })
        return result, None
    except Exception as e:
        return None, str(e)


def sign_out():
    sb = get_supabase()
    if sb is not None:
        try:
            sb.auth.sign_out()
        except Exception:
            pass


# =========================================================
# GEMINI AI
# =========================================================

@st.cache_resource
def get_gemini_client():
    key = st.secrets.get("GEMINI_API_KEY", "")
    if not key:
        return None
    try:
        return genai.Client(api_key=key)
    except Exception:
        return None


def ask_gemini(prompt, attempts=3):
    client = get_gemini_client()
    if client is None:
        return None, "Gemini API is not configured. Add GEMINI_API_KEY to Streamlit Secrets."
    last_error = ""
    for attempt in range(attempts):
        try:
            response = client.models.generate_content(
                model="gemini-3.6-flash",
                contents=prompt,
            )
            text = getattr(response, "text", None)
            if text and text.strip():
                return text.strip(), None
            last_error = "Gemini returned an empty response."
        except Exception as e:
            last_error = str(e)
            if "503" in last_error or "UNAVAILABLE" in last_error or "high demand" in last_error.lower():
                time.sleep(1.5 * (attempt + 1))
                continue
            break
    return None, last_error


# =========================================================
# SESSION STATE
# =========================================================


if "logged_in" not in st.session_state:
    st.session_state.logged_in = False

if "user_id" not in st.session_state:
    st.session_state.user_id = ""

if "user_email" not in st.session_state:
    st.session_state.user_email = ""

if "user_name" not in st.session_state:
    st.session_state.user_name = ""

if "completed" not in st.session_state:
    st.session_state.completed = []

if "quiz_score" not in st.session_state:
    st.session_state.quiz_score = 0

if "points" not in st.session_state:
    st.session_state.points = 0

if "badges" not in st.session_state:
    st.session_state.badges = []

if "history" not in st.session_state:
    st.session_state.history = []


# =========================================================
# CUSTOM CSS
# =========================================================

st.markdown(
    """
    <style>

    .main-title {
        font-size: 42px;
        font-weight: bold;
        text-align: center;
        margin-bottom: 10px;
    }

    .subtitle {
        text-align: center;
        font-size: 20px;
        margin-bottom: 20px;
    }

    .card {
        padding: 20px;
        border-radius: 15px;
        border: 1px solid #ddd;
        margin-bottom: 15px;
    }

    .badge {
        padding: 10px;
        border-radius: 10px;
        border: 1px solid #aaa;
        margin: 5px;
        display: inline-block;
    }

    </style>
    """,
    unsafe_allow_html=True
)


# =========================================================
# LOGIN / SIGN UP
# =========================================================

if not st.session_state.logged_in:

    require_supabase()

    st.markdown(
        '<div class="main-title">'
        '⚛️ Quantum LearnLab AI'
        '</div>',
        unsafe_allow_html=True
    )

    st.markdown(
        '<div class="subtitle">'
        'Sign in to continue your quantum learning journey'
        '</div>',
        unsafe_allow_html=True
    )

    st.divider()

    login_tab, signup_tab = st.tabs(["🔐 Login", "📝 Sign Up"])

    with login_tab:
        st.subheader("Welcome back")
        login_email = st.text_input("Email", key="login_email")
        login_password = st.text_input("Password", type="password", key="login_password")

        if st.button("🔓 Login", use_container_width=True):
            if not login_email.strip() or not login_password:
                st.warning("Please enter your email and password.")
            else:
                result, error = sign_in(login_email, login_password)
                if error:
                    st.error("Invalid email or password.")
                else:
                    user = result.user
                    st.session_state.logged_in = True
                    st.session_state.user_id = str(user.id)
                    st.session_state.user_email = user.email or login_email.strip().lower()
                    metadata = user.user_metadata or {}
                    st.session_state.user_name = metadata.get("name", "Learner")
                    load_user_progress(st.session_state.user_id)
                    st.success("Login successful!")
                    st.rerun()

    with signup_tab:
        st.subheader("Create your account")
        signup_name = st.text_input("Name", key="signup_name")
        signup_email = st.text_input("Email", key="signup_email")
        signup_password = st.text_input("Password", type="password", key="signup_password")
        signup_confirm = st.text_input("Confirm Password", type="password", key="signup_confirm")

        if st.button("🚀 Create Account", use_container_width=True):
            email = signup_email.lower().strip()
            if not signup_name.strip() or not email or not signup_password:
                st.warning("Please fill all fields.")
            elif "@" not in email:
                st.warning("Please enter a valid email.")
            elif len(signup_password) < 6:
                st.warning("Password must contain at least 6 characters.")
            elif signup_password != signup_confirm:
                st.error("Passwords do not match.")
            else:
                result, error = sign_up(email, signup_password, signup_name)
                if error:
                    st.error(f"Could not create account: {error}")
                else:
                    user = result.user
                    session = result.session
                    if session is not None:
                        st.session_state.logged_in = True
                        st.session_state.user_id = str(user.id)
                        st.session_state.user_email = user.email or email
                        st.session_state.user_name = signup_name.strip()
                        st.session_state.completed = []
                        st.session_state.quiz_score = 0
                        st.session_state.points = 0
                        st.session_state.badges = []
                        st.session_state.history = []
                        save_profile()
                        st.success("Account created and logged in successfully!")
                        st.rerun()
                    else:
                        st.success("Account created. Please check your email for confirmation, then use Login.")

    st.stop()


# =========================================================
# SIDEBAR
# =========================================================

st.sidebar.title(
    "⚛️ Quantum LearnLab AI"
)

st.sidebar.success(
    f"👤 {st.session_state.user_name}"
)


if st.sidebar.button(
    "🚪 Logout"
):

    sign_out()
    st.session_state.logged_in = False
    st.session_state.user_id = ""
    st.session_state.user_email = ""
    st.session_state.user_name = ""

    st.rerun()


if "workflow_stage" not in st.session_state:
    st.session_state.workflow_stage = "ASK"

if "workflow_question" not in st.session_state:
    st.session_state.workflow_question = ""

if "workflow_topic" not in st.session_state:
    st.session_state.workflow_topic = "Superposition"

if "workflow_explanation" not in st.session_state:
    st.session_state.workflow_explanation = ""

if "workflow_simulation" not in st.session_state:
    st.session_state.workflow_simulation = None

if "workflow_score" not in st.session_state:
    st.session_state.workflow_score = None

page = st.sidebar.radio(
    "Navigation",
    [
        "🚀 Learning Workflow",
        "🏠 Home",
        "📚 Learn",
        "📖 Gate Learning",
        "⚛️ Circuit Builder",
        "🧪 Quantum Algorithms",
        "📊 Visualization",
        "💻 Qiskit Code Editor",
        "🐛 Fix My Circuit",
        "🤖 AI Tutor",
        "📝 Quiz",
        "📈 Progress",
        "🏆 Leaderboard"
    ],
    index=0
)


# =========================================================
# HELPER FUNCTIONS
# =========================================================

def add_points(points):

    st.session_state.points += points
    save_profile()


def complete_topic(topic):

    if topic not in st.session_state.completed:

        st.session_state.completed.append(
            topic
        )

        add_points(10)
        save_profile()


def check_badges():

    if len(
        st.session_state.completed
    ) >= 3:

        if "Quantum Beginner" not in st.session_state.badges:

            st.session_state.badges.append(
                "Quantum Beginner"
            )


    if len(
        st.session_state.completed
    ) >= 6:

        if "Quantum Explorer" not in st.session_state.badges:

            st.session_state.badges.append(
                "Quantum Explorer"
            )


    if st.session_state.quiz_score >= 4:

        if "Quiz Master" not in st.session_state.badges:

            st.session_state.badges.append(
                "Quiz Master"
            )


    if st.session_state.points >= 100:

        if "Quantum Champion" not in st.session_state.badges:

            st.session_state.badges.append(
                "Quantum Champion"
            )

    save_profile()


def run_circuit(
    qc,
    shots=1024
):

    simulator = AerSimulator()

    qc_run = qc.copy()

    if qc_run.num_clbits == 0:

        qc_run.measure_all()

    compiled = transpile(
        qc_run,
        simulator
    )

    result = simulator.run(
        compiled,
        shots=shots
    ).result()

    return result.get_counts()


def draw_circuit(qc):
    try:
        return qc.draw(output="mpl", fold=-1)
    except Exception:
        return None


def show_circuit(qc):
    fig = draw_circuit(qc)
    if fig is not None:
        st.pyplot(fig)
    else:
        st.code(qc.draw(output="text"), language="text")


# =========================================================
# INTERACTIVE PATENT WORKFLOW
# =========================================================

def workflow_topic_from_question(question):
    q = question.lower()
    if "entangle" in q or "bell" in q:
        return "Entanglement"
    if "cnot" in q or "controlled not" in q:
        return "CNOT Gate"
    if "hadamard" in q or "h gate" in q or "superposition" in q:
        return "Superposition"
    if "measurement" in q or "measure" in q:
        return "Measurement"
    if "grover" in q or "search" in q:
        return "Grover Search"
    if "qft" in q or "fourier" in q:
        return "QFT"
    if "qubit" in q:
        return "Qubit"
    return "Superposition"


def workflow_explain(topic):
    explanations = {
        "Qubit": "A qubit is the basic unit of quantum information. Unlike a classical bit, a qubit can be represented using amplitudes for |0⟩ and |1⟩.",
        "Superposition": "Superposition means a quantum state can be represented as a combination of basis states. Applying a Hadamard gate to |0⟩ creates |+⟩ = (|0⟩ + |1⟩)/√2.",
        "Entanglement": "Quantum entanglement creates correlations between qubits. A common Bell-state demonstration uses a Hadamard gate followed by CNOT.",
        "CNOT Gate": "CNOT is a two-qubit controlled operation. The target qubit is flipped when the control qubit is |1⟩.",
        "Measurement": "Quantum measurement produces a classical outcome from a quantum state. Repeated measurements reveal the probability distribution of outcomes.",
        "Grover Search": "Grover's algorithm is a quantum search procedure that amplifies the probability of a marked solution in an unstructured search space.",
        "QFT": "The Quantum Fourier Transform converts quantum amplitudes into a Fourier-like representation and is used in several quantum algorithms."
    }
    return explanations.get(topic, explanations["Superposition"])


def workflow_build_circuit(topic):
    if topic == "Entanglement":
        qc = QuantumCircuit(2, 2)
        qc.h(0)
        qc.cx(0, 1)
        qc.measure([0, 1], [0, 1])
        return qc
    if topic == "CNOT Gate":
        qc = QuantumCircuit(2, 2)
        qc.x(0)
        qc.cx(0, 1)
        qc.measure([0, 1], [0, 1])
        return qc
    if topic == "Grover Search":
        qc = QuantumCircuit(2, 2)
        qc.h([0, 1])
        qc.measure([0, 1], [0, 1])
        return qc
    if topic == "QFT":
        qc = QuantumCircuit(2, 2)
        qc.h(0)
        qc.cp(np.pi / 2, 0, 1)
        qc.h(1)
        qc.measure([0, 1], [0, 1])
        return qc
    qc = QuantumCircuit(1, 1)
    if topic in ["Superposition", "Measurement"]:
        qc.h(0)
    qc.measure(0, 0)
    return qc


def workflow_next_topic(topic):
    order = ["Qubit", "Superposition", "Entanglement", "Measurement", "Grover Search", "QFT"]
    if topic in order and order.index(topic) < len(order) - 1:
        return order[order.index(topic) + 1]
    return "Quantum Algorithms"


def render_workflow():
    st.markdown(
        '<div class="main-title">⚛️ Quantum LearnLab AI</div>',
        unsafe_allow_html=True
    )
    st.markdown(
        '<div class="subtitle">Interactive Patent Learning Workflow</div>',
        unsafe_allow_html=True
    )

    stages = [
        "ASK", "EXPLAIN", "BUILD", "SIMULATE",
        "VISUALIZE", "ASSESS / ADAPT", "NEXT LEARNING PATH"
    ]
    current = stages.index(st.session_state.workflow_stage)
    st.progress((current + 1) / len(stages))

    cols = st.columns(7)
    for i, stage in enumerate(stages):
        with cols[i]:
            if st.button(stage, key=f"workflow_stage_{i}", use_container_width=True):
                st.session_state.workflow_stage = stage
                st.rerun()

    st.caption(f"Current stage: **{st.session_state.workflow_stage}**")
    st.divider()

    stage = st.session_state.workflow_stage

    if stage == "ASK":
        st.subheader("1. ASK — Learner Input")
        st.write("Enter a quantum question or learning goal.")
        question = st.text_input(
            "Your question",
            value=st.session_state.workflow_question,
            placeholder="Example: What is superposition?"
        )
        if st.button("Submit Question → EXPLAIN", use_container_width=True):
            if not question.strip():
                st.warning("Please enter a question.")
            else:
                st.session_state.workflow_question = question.strip()
                st.session_state.workflow_topic = workflow_topic_from_question(question)
                st.session_state.workflow_explanation = workflow_explain(st.session_state.workflow_topic)
                st.session_state.workflow_simulation = None
                st.session_state.workflow_score = None
                st.session_state.workflow_stage = "EXPLAIN"
                st.rerun()

    elif stage == "EXPLAIN":
        st.subheader("2. EXPLAIN — AI Quantum Tutor")
        if not st.session_state.workflow_question:
            st.info("Start with ASK and submit a question.")
        else:
            st.success(f"Detected topic: **{st.session_state.workflow_topic}**")
            st.write(st.session_state.workflow_explanation)
            st.info("Backend role: the learner question is analyzed and mapped to a quantum concept explanation.")
            if st.button("Continue to BUILD →", use_container_width=True):
                st.session_state.workflow_stage = "BUILD"
                st.rerun()

    elif stage == "BUILD":
        st.subheader("3. BUILD — Quantum Circuit Builder")
        if not st.session_state.workflow_question:
            st.info("Start with ASK first.")
        else:
            qc = workflow_build_circuit(st.session_state.workflow_topic)
            st.write(f"Circuit for **{st.session_state.workflow_topic}**")
            show_circuit(qc)
            st.code(qc.draw(output="text"), language="text")
            st.info("Backend role: the selected learning concept is converted into an executable quantum circuit.")
            if st.button("Run SIMULATE →", use_container_width=True):
                st.session_state.workflow_simulation = run_circuit(qc, shots=512)
                st.session_state.workflow_stage = "SIMULATE"
                st.rerun()

    elif stage == "SIMULATE":
        st.subheader("4. SIMULATE — Quantum Circuit Execution")
        if st.session_state.workflow_simulation is None:
            st.info("Build the circuit first.")
        else:
            counts = st.session_state.workflow_simulation
            st.success("Circuit executed using the Qiskit Aer simulator.")
            st.write("Measurement counts:")
            st.json(counts)
            if st.button("Continue to VISUALIZE →", use_container_width=True):
                st.session_state.workflow_stage = "VISUALIZE"
                st.rerun()

    elif stage == "VISUALIZE":
        st.subheader("5. VISUALIZE — Quantum Results")
        counts = st.session_state.workflow_simulation
        if not counts:
            st.info("Run SIMULATE first.")
        else:
            df = pd.DataFrame({"State": list(counts.keys()), "Measurements": list(counts.values())})
            st.bar_chart(df.set_index("State"))
            total = sum(counts.values())
            st.write("### Measurement Probabilities")
            for state, value in counts.items():
                p = value / total if total else 0
                st.write(f"**|{state}⟩ — {p * 100:.1f}%**")
                st.progress(p)
            if st.button("Continue to ASSESS / ADAPT →", use_container_width=True):
                st.session_state.workflow_stage = "ASSESS / ADAPT"
                st.rerun()

    elif stage == "ASSESS / ADAPT":
        st.subheader("6. ASSESS / ADAPT — Learner Assessment")
        topic = st.session_state.workflow_topic
        questions = {
            "Qubit": ("What is the basic unit of quantum information?", ["Qubit", "Byte", "Pixel"], "Qubit"),
            "Superposition": ("Which gate is commonly used to create equal superposition from |0⟩?", ["Hadamard (H)", "CNOT", "Z"], "Hadamard (H)"),
            "Entanglement": ("Which gate is commonly used with H to create a Bell-state circuit?", ["CNOT", "Z", "RX"], "CNOT"),
            "Measurement": ("What does quantum measurement produce?", ["A classical outcome", "A new qubit", "A password"], "A classical outcome"),
            "CNOT Gate": ("CNOT is primarily a how-many-qubit operation?", ["Two-qubit", "One-qubit", "Ten-qubit"], "Two-qubit"),
            "Grover Search": ("Grover's algorithm is mainly associated with which task?", ["Search", "Sorting", "Image editing"], "Search"),
            "QFT": ("What does QFT stand for?", ["Quantum Fourier Transform", "Quantum Fast Transfer", "Qubit Frequency Tool"], "Quantum Fourier Transform")
        }
        q, options, correct = questions.get(topic, questions["Superposition"])
        answer = st.radio(q, options, key="workflow_assessment_answer")
        if st.button("Submit Assessment", use_container_width=True):
            if answer == correct:
                st.session_state.workflow_score = 100
                st.session_state.quiz_score = max(st.session_state.quiz_score, 5)
                st.session_state.points += 20
                save_profile()
                st.success("Correct. Adaptive learning can continue to the next topic.")
            else:
                st.session_state.workflow_score = 0
                st.warning(f"Review {topic} and try the assessment again.")
            check_badges()
        if st.session_state.workflow_score is not None:
            st.metric("Workflow Assessment", f"{st.session_state.workflow_score}%")
            if st.session_state.workflow_score >= 70:
                if st.button("Continue to NEXT LEARNING PATH →", use_container_width=True):
                    st.session_state.workflow_stage = "NEXT LEARNING PATH"
                    st.rerun()

    elif stage == "NEXT LEARNING PATH":
        st.subheader("7. NEXT LEARNING PATH")
        if st.session_state.workflow_score is None:
            st.info("Complete ASSESS / ADAPT first.")
        elif st.session_state.workflow_score >= 70:
            next_topic = workflow_next_topic(st.session_state.workflow_topic)
            st.success(f"Recommended next learning activity: **{next_topic}**")
            st.write("The recommendation is based on the current topic and assessment result.")
            if st.button("Start Recommended Topic →", use_container_width=True):
                st.session_state.workflow_question = f"Teach me about {next_topic}"
                st.session_state.workflow_topic = next_topic
                st.session_state.workflow_explanation = workflow_explain(next_topic)
                st.session_state.workflow_score = None
                st.session_state.workflow_stage = "EXPLAIN"
                st.rerun()
        else:
            st.warning("Revisit the current topic and complete the assessment successfully before progressing.")


# =========================================================
# HOME
# =========================================================

if page == "🚀 Learning Workflow":
    render_workflow()

elif page == "🏠 Home":

    st.markdown(
        '<div class="main-title">'
        '⚛️ Quantum LearnLab AI'
        '</div>',
        unsafe_allow_html=True
    )

    st.markdown(
        '<div class="subtitle">'
        'Interactive AI-Powered Quantum Computing Learning Platform'
        '</div>',
        unsafe_allow_html=True
    )

    st.divider()

    col1, col2, col3 = st.columns(3)

    with col1:

        st.info(
            "📚 Learn\n\n"
            "Quantum concepts interactively."
        )

    with col2:

        st.success(
            "⚛️ Build\n\n"
            "Create quantum circuits."
        )

    with col3:

        st.warning(
            "🤖 Ask AI\n\n"
            "Get explanations and debugging help."
        )

    st.divider()

    st.subheader(
        "🚀 Learning Workflow"
    )

    st.write(
        "Learn → Build → Run → Visualize → "
        "Ask AI → Fix → Challenge → Track"
    )

    st.subheader(
        "✨ Platform Features"
    )

    features = [

        "Interactive quantum learning modules",

        "Select-and-add quantum circuit builder",

        "Qiskit simulation",

        "Quantum algorithm demonstrations",

        "Probability and measurement visualization",

        "Qiskit code editor",

        "Circuit debugging assistant",

        "AI quantum tutor",

        "Quiz and assessments",

        "Personal progress tracking",

        "Leaderboard and badges",

        "Voice-based learning support"
    ]

    for feature in features:

        st.write(
            "✅",
            feature
        )


# =========================================================
# GATE LEARNING
# =========================================================

GATE_INFO = {
    "H": {
        "name": "Hadamard Gate",
        "description": "The H gate creates an equal superposition from |0⟩ or |1⟩. It is commonly used at the beginning of quantum algorithms.",
        "matrix": "1/√2 × [[1, 1], [1, -1]]",
        "input_output": "|0⟩ → |+⟩ = (|0⟩ + |1⟩)/√2\n|1⟩ → |-⟩ = (|0⟩ - |1⟩)/√2",
        "use": "Creates superposition and is widely used in algorithms such as Deutsch-Jozsa and Grover's algorithm.",
        "example": "q0: ──H──",
        "qubits": 1,
    },
    "X": {
        "name": "Pauli-X Gate",
        "description": "The X gate flips the computational-basis state, similar to a classical NOT operation.",
        "matrix": "[[0, 1], [1, 0]]",
        "input_output": "|0⟩ → |1⟩\n|1⟩ → |0⟩",
        "use": "Bit-flip operation and preparation of the |1⟩ state.",
        "example": "q0: ──X──",
        "qubits": 1,
    },
    "Y": {
        "name": "Pauli-Y Gate",
        "description": "The Y gate changes the qubit state with both a bit-flip and a phase change.",
        "matrix": "[[0, -i], [i, 0]]",
        "input_output": "|0⟩ → i|1⟩\n|1⟩ → -i|0⟩",
        "use": "Performs a quantum rotation around the Y axis of the Bloch sphere.",
        "example": "q0: ──Y──",
        "qubits": 1,
    },
    "Z": {
        "name": "Pauli-Z Gate",
        "description": "The Z gate leaves |0⟩ unchanged and adds a phase of -1 to |1⟩.",
        "matrix": "[[1, 0], [0, -1]]",
        "input_output": "|0⟩ → |0⟩\n|1⟩ → -|1⟩",
        "use": "Phase flip and phase manipulation in quantum circuits.",
        "example": "q0: ──Z──",
        "qubits": 1,
    },
    "S": {
        "name": "S Gate",
        "description": "The S gate applies a 90° phase shift to the |1⟩ component of a qubit.",
        "matrix": "[[1, 0], [0, i]]",
        "input_output": "|0⟩ → |0⟩\n|1⟩ → i|1⟩",
        "use": "Phase rotation and phase-sensitive quantum algorithms.",
        "example": "q0: ──S──",
        "qubits": 1,
    },
    "T": {
        "name": "T Gate",
        "description": "The T gate applies a 45° phase shift to the |1⟩ component.",
        "matrix": "[[1, 0], [0, e^(iπ/4)]]",
        "input_output": "|0⟩ → |0⟩\n|1⟩ → e^(iπ/4)|1⟩",
        "use": "Fine phase control and universal quantum gate constructions.",
        "example": "q0: ──T──",
        "qubits": 1,
    },
    "CNOT": {
        "name": "Controlled-NOT Gate",
        "description": "CNOT is a two-qubit gate. It flips the target qubit only when the control qubit is |1⟩.",
        "matrix": "[[1,0,0,0],[0,1,0,0],[0,0,0,1],[0,0,1,0]]",
        "input_output": "|00⟩ → |00⟩\n|01⟩ → |01⟩\n|10⟩ → |11⟩\n|11⟩ → |10⟩",
        "use": "Creates entanglement and is a fundamental two-qubit operation.",
        "example": "q0: ──●──\n      │\nq1: ──⊕──",
        "qubits": 2,
    },
    "CZ": {
        "name": "Controlled-Z Gate",
        "description": "CZ applies a Z operation to the target when the control qubit is |1⟩. It changes the phase of |11⟩.",
        "matrix": "diag(1, 1, 1, -1)",
        "input_output": "|00⟩ → |00⟩\n|01⟩ → |01⟩\n|10⟩ → |10⟩\n|11⟩ → -|11⟩",
        "use": "Controlled phase operations and entanglement-based circuits.",
        "example": "q0: ──●──\n      │\nq1: ──Z──",
        "qubits": 2,
    },
    "SWAP": {
        "name": "SWAP Gate",
        "description": "The SWAP gate exchanges the quantum states of two qubits.",
        "matrix": "[[1,0,0,0],[0,0,1,0],[0,1,0,0],[0,0,0,1]]",
        "input_output": "|00⟩ → |00⟩\n|01⟩ → |10⟩\n|10⟩ → |01⟩\n|11⟩ → |11⟩",
        "use": "Moves or exchanges quantum states between qubit positions.",
        "example": "q0: ──×──\n      │\nq1: ──×──",
        "qubits": 2,
    },
}


def gate_learning_circuit(gate):
    info = GATE_INFO[gate]
    qc = QuantumCircuit(info["qubits"])
    if gate == "H": qc.h(0)
    elif gate == "X": qc.x(0)
    elif gate == "Y": qc.y(0)
    elif gate == "Z": qc.z(0)
    elif gate == "S": qc.s(0)
    elif gate == "T": qc.t(0)
    elif gate == "CNOT": qc.cx(0, 1)
    elif gate == "CZ": qc.cz(0, 1)
    elif gate == "SWAP": qc.swap(0, 1)
    return qc


def render_gate_learning():
    st.title("📖 Gate Learning")
    st.write("Select a quantum gate and learn its meaning, matrix, input-output behavior, use, and circuit example.")

    selected_gate = st.selectbox(
        "Select a gate to learn",
        list(GATE_INFO.keys()),
        key="gate_learning_selector",
    )
    info = GATE_INFO[selected_gate]

    st.header(f"{selected_gate} — {info['name']}")
    st.info(info["description"])

    col1, col2 = st.columns(2)
    with col1:
        st.subheader("Matrix")
        st.code(info["matrix"], language="text")
    with col2:
        st.subheader("Input → Output")
        st.code(info["input_output"], language="text")

    st.subheader("Main Use")
    st.write(info["use"])

    st.subheader("Circuit Example")
    qc = gate_learning_circuit(selected_gate)
    try:
        show_circuit(qc)
    except Exception:
        st.code(qc.draw(output="text"), language="text")

    st.subheader("Try This Gate")
    if st.button(f"▶️ Try {selected_gate} Gate", use_container_width=True):
        counts = run_circuit(qc, shots=512)
        st.session_state.history.append({
            "Circuit": str(qc),
            "Result": counts,
            "Gate Learning": selected_gate,
        })
        add_points(5)
        check_badges()
        st.write("Measurement Result")
        st.write(counts)
        st.success(f"{selected_gate} gate simulated successfully! +5 points")


# =========================================================
# LEARN
# =========================================================

if page == "📖 Gate Learning":

    render_gate_learning()


# =========================================================
# LEARN
# =========================================================

elif page == "📚 Learn":

    st.title(
        "📚 Learn Quantum Computing"
    )

    st.write(
        "Learn quantum concepts using "
        "explanations and figures."
    )


    # =====================================================
    # TOPICS
    # =====================================================

    topics = {

        "Qubit": {

            "description":
            "A qubit is the quantum counterpart "
            "of a classical bit. Unlike a classical "
            "bit, a qubit can exist in a superposition "
            "of states. When measured, it produces "
            "a classical outcome according to the "
            "measurement basis.",

            "representation":
            "|ψ⟩ = α|0⟩ + β|1⟩",

            "takeaway":
            "The measurement outcome depends on "
            "the quantum state and the measurement basis.",

            "image":
            FIG_QUBIT,

            "caption":
            "Figure 1 — Qubit in a superposition "
            "and collapse after measurement."
        },


        "Superposition": {

            "description":
            "Superposition means that a quantum state "
            "can be represented as a combination of "
            "basis states until measurement.",

            "representation":
            "|ψ⟩ = α|0⟩ + β|1⟩",

            "takeaway":
            "Measurement selects a classical outcome "
            "from the quantum state.",

            "image":
            FIG_QUBIT,

            "caption":
            "Figure 1 — Superposition and measurement "
            "of a qubit."
        },


        "Entanglement": {

            "description":
            "Entanglement produces correlations between "
            "quantum systems. Entanglement swapping and "
            "quantum teleportation are important "
            "quantum-network operations.",

            "representation":
            "H + CNOT → entangled qubits",

            "takeaway":
            "Entangled-qubit measurement outcomes "
            "can be correlated.",

            "image":
            FIG_ENTANGLEMENT,

            "caption":
            "Figure 3 — Entanglement swapping "
            "and quantum teleportation."
        },


        "Hadamard Gate": {

            "description":
            "The Hadamard gate creates a superposition "
            "from a computational-basis state.",

            "representation":
            "H|0⟩ = (|0⟩ + |1⟩)/√2",

            "takeaway":
            "The Hadamard operation can be used "
            "to create superposition.",

            "image":
            FIG_CIRCUIT,

            "caption":
            "Figure 4 — Circuit showing Hadamard "
            "and CNOT operations."
        },


        "CNOT Gate": {

            "description":
            "CNOT is a two-qubit controlled operation. "
            "It is commonly used together with Hadamard "
            "to demonstrate entanglement.",

            "representation":
            "Q0: ──●──\n"
            "Q1: ──⊕──",

            "takeaway":
            "CNOT combined with Hadamard can "
            "demonstrate entanglement.",

            "image":
            FIG_CIRCUIT,

            "caption":
            "Figure 4 — Quantum circuit containing "
            "CNOT operations."
        },


        "Measurement": {

            "description":
            "Measurement is the process of observing "
            "a qubit with respect to a chosen basis.",

            "representation":
            "Quantum state → Measurement → 0 or 1",

            "takeaway":
            "The measurement basis matters.",

            "image":
            FIG_QUBIT,

            "caption":
            "Figure 1 — Measurement of a qubit."
        },


        "Quantum Interference": {

            "description":
            "Quantum interference occurs when probability "
            "amplitudes combine constructively or destructively.",

            "representation":
            "Amplitudes → interference → probabilities",

            "takeaway":
            "Interference changes probability amplitudes "
            "and is important in quantum algorithms.",

            "image":
            None,

            "caption":
            "No dedicated interference figure."
        },


        "Quantum Algorithms": {

            "description":
            "Quantum algorithms combine quantum states, "
            "gates, measurements and interference "
            "to perform computational tasks.",

            "representation":
            "State preparation → gates → measurement",

            "takeaway":
            "Quantum algorithms are built from "
            "sequences of quantum operations.",

            "image":
            FIG_CIRCUIT,

            "caption":
            "Figure 4 — Example quantum circuit."
        }
    }


    # =====================================================
    # SELECT TOPIC
    # =====================================================

    selected = st.selectbox(
        "Select a topic",
        list(topics.keys())
    )

    lesson = topics[selected]


    # =====================================================
    # DESCRIPTION
    # =====================================================

    st.markdown(
        f"""
        <div class="card">

        <h2>{selected}</h2>

        <p>
        {lesson["description"]}
        </p>

        </div>
        """,
        unsafe_allow_html=True
    )


    # =====================================================
    # KEY IDEA
    # =====================================================

    st.subheader(
        "🧠 Key idea"
    )

    st.info(
        lesson["takeaway"]
    )


    # =====================================================
    # REPRESENTATION
    # =====================================================

    st.subheader(
        "⚛️ Mathematical / Circuit Representation"
    )

    st.code(
        lesson["representation"]
    )


    # =====================================================
    # IMAGE
    # =====================================================

    if lesson["image"] is not None:

        image_path = Path(
            lesson["image"]
        )

        if image_path.exists():

            st.subheader(
                "🖼️ Figure"
            )

            st.image(
                str(image_path),
                use_container_width=True
            )

            st.caption(
                lesson["caption"]
            )

        else:

            st.error(
                f"Image not found: {image_path}"
            )

            st.info(
                "Make sure the image is uploaded "
                "inside the assets folder."
            )

    else:

        st.info(
            lesson["caption"]
        )


    # =====================================================
    # INTERACTIVE DEMOS
    # =====================================================

    if selected == "Hadamard Gate":

        qc_demo = QuantumCircuit(1)

        qc_demo.h(0)

        st.subheader(
            "Interactive H-gate demonstration"
        )

        show_circuit(qc_demo)

        if st.button(
            "▶️ Simulate Hadamard",
            key="learn_h"
        ):

            st.write(
                "Measurement:",
                run_circuit(qc_demo)
            )

            add_points(5)


    elif selected == "CNOT Gate":

        qc_demo = QuantumCircuit(2)

        qc_demo.h(0)

        qc_demo.cx(
            0,
            1
        )

        st.subheader(
            "Interactive H + CNOT demonstration"
        )

        show_circuit(qc_demo)

        if st.button(
            "▶️ Simulate H + CNOT",
            key="learn_cnot"
        ):

            st.write(
                "Measurement:",
                run_circuit(qc_demo)
            )

            add_points(5)


    elif selected == "Superposition":

        qc_demo = QuantumCircuit(1)

        qc_demo.h(0)

        st.subheader(
            "Interactive superposition demonstration"
        )

        show_circuit(qc_demo)

        if st.button(
            "▶️ Simulate Superposition",
            key="learn_superposition"
        ):

            st.write(
                "Measurement:",
                run_circuit(qc_demo)
            )

            add_points(5)


    elif selected == "Entanglement":

        qc_demo = QuantumCircuit(2)

        qc_demo.h(0)

        qc_demo.cx(
            0,
            1
        )

        st.subheader(
            "Interactive Bell-state demonstration"
        )

        show_circuit(qc_demo)

        if st.button(
            "▶️ Simulate Entanglement",
            key="learn_entanglement"
        ):

            st.write(
                "Measurement:",
                run_circuit(qc_demo)
            )

            add_points(5)


    elif selected == "Measurement":

        qc_demo = QuantumCircuit(1)

        qc_demo.h(0)

        qc_demo.measure_all()

        st.subheader(
            "Interactive measurement demonstration"
        )

        show_circuit(qc_demo)

        if st.button(
            "▶️ Run Measurement",
            key="learn_measurement"
        ):

            st.write(
                "Measurement:",
                run_circuit(qc_demo)
            )

            add_points(5)


    elif selected == "Quantum Algorithms":

        st.info(
            "Use 🧪 Quantum Algorithms "
            "in the sidebar for algorithm demonstrations."
        )


    # =====================================================
    # COMPLETE TOPIC
    # =====================================================

    if st.button(
        "✅ Mark Topic Complete"
    ):

        complete_topic(
            selected
        )

        check_badges()

        st.success(
            f"{selected} completed! +10 points"
        )


# =========================================================
# =========================================================
# CIRCUIT BUILDER
# =========================================================

elif page == "⚛️ Circuit Builder":

    st.title("⚛️ Quantum Circuit Builder")
    st.write("Drag quantum gates from the palette into the circuit area, then simulate the circuit.")

    col1, col2 = st.columns(2)
    with col1:
        n_qubits = st.selectbox("Number of Qubits", [1, 2, 3, 4], index=1)
    with col2:
        shots = st.number_input("Shots", min_value=128, max_value=4096, value=512, step=128)

    if "drag_gate_sequence" not in st.session_state:
        st.session_state.drag_gate_sequence = []
    if "builder_counts" not in st.session_state:
        st.session_state.builder_counts = None

    if not SORTABLES_AVAILABLE:
        st.error("Drag-and-drop component is not installed. Add streamlit-sortables==0.3.1 to requirements.txt.")
        st.info("The rest of the application can still run, but Circuit Builder needs this dependency for drag-and-drop.")
    else:
        available_gates = ["H", "X", "Y", "Z", "S", "T", "CNOT", "CZ", "SWAP"]
        current = [g for g in st.session_state.drag_gate_sequence if g in available_gates]

        st.subheader("🧩 Drag Gates → ⚛️ Circuit")
        containers = [
            {"header": "🧩 Gate Palette", "items": available_gates},
            {"header": "⚛️ Circuit — drop gates here", "items": current},
        ]

        result = sort_items(
            containers,
            multi_containers=True,
            direction="horizontal",
            key="quantum_drag_drop_builder"
        )

        if isinstance(result, list) and len(result) >= 2:
            dropped = result[1].get("items", [])
            st.session_state.drag_gate_sequence = [g for g in dropped if g in available_gates]

        gate_sequence = st.session_state.drag_gate_sequence

        if gate_sequence:
            st.success("Circuit sequence: " + " → ".join(gate_sequence))
        else:
            st.info("Drag gates from the Gate Palette into the Circuit area.")

        qc = QuantumCircuit(n_qubits, n_qubits)
        for gate in gate_sequence:
            if gate == "H":
                qc.h(0)
            elif gate == "X":
                qc.x(0)
            elif gate == "Y":
                qc.y(0)
            elif gate == "Z":
                qc.z(0)
            elif gate == "S":
                qc.s(0)
            elif gate == "T":
                qc.t(0)
            elif gate == "CNOT" and n_qubits >= 2:
                qc.cx(0, 1)
            elif gate == "CZ" and n_qubits >= 2:
                qc.cz(0, 1)
            elif gate == "SWAP" and n_qubits >= 2:
                qc.swap(0, 1)

        qc.measure(range(n_qubits), range(n_qubits))

        st.subheader("Circuit")
        st.code(str(qc.draw(output="text")), language="text")

        st.subheader("Circuit Explanation")
        explanations = {
            "H": "Creates superposition on qubit 0.",
            "X": "Flips qubit 0 from |0⟩ to |1⟩ or |1⟩ to |0⟩.",
            "Y": "Performs a bit flip together with a phase change.",
            "Z": "Applies a phase flip to the |1⟩ component.",
            "S": "Applies a π/2 phase shift.",
            "T": "Applies a π/4 phase shift.",
            "CNOT": "Uses qubit 0 as control and flips qubit 1 when the control is 1.",
            "CZ": "Applies a phase change when both qubits are in the |1⟩ state.",
            "SWAP": "Exchanges the states of qubit 0 and qubit 1."
        }
        for i, gate in enumerate(gate_sequence, 1):
            st.write(f"**Step {i} — {gate}:** {explanations[gate]}")

        b1, b2, b3 = st.columns(3)
        with b1:
            if st.button("▶️ Run Circuit", use_container_width=True):
                counts = run_circuit(qc, int(shots))
                st.session_state.builder_counts = counts
                st.session_state.history.append({"Circuit": str(qc), "Result": counts})
                save_profile()
                st.success("Circuit simulated successfully.")
        with b2:
            if st.button("↩️ Remove Last", use_container_width=True):
                if st.session_state.drag_gate_sequence:
                    st.session_state.drag_gate_sequence.pop()
                    st.session_state.builder_counts = None
                    st.rerun()
        with b3:
            if st.button("🗑️ Clear Circuit", use_container_width=True):
                st.session_state.drag_gate_sequence = []
                st.session_state.builder_counts = None
                st.rerun()

        if st.session_state.builder_counts:
            st.subheader("Measurement Result")
            st.json(st.session_state.builder_counts)


# =========================================================
# QUANTUM ALGORITHMS
# =========================================================

elif page == "🧪 Quantum Algorithms":

    st.title("🧪 Quantum Algorithms")
    st.write("Learn the algorithm, see the figure, inspect the circuit, understand each step, and simulate it.")

    algorithm = st.selectbox(
        "Select Algorithm",
        ["Bell State", "Grover Search", "Deutsch-Jozsa", "Quantum Fourier Transform", "VQE", "QAOA"]
    )

    if algorithm == "Bell State":
        qc = QuantumCircuit(2, 2)
        qc.h(0)
        qc.cx(0, 1)
        explanation = "H creates superposition on qubit 0. CNOT then correlates qubit 1 with qubit 0, producing a Bell-state example."
        figure = FIG_ENTANGLEMENT
        title = "🔗 Bell State"
    elif algorithm == "Grover Search":
        qc = QuantumCircuit(2, 2)
        qc.h([0, 1])
        qc.cz(0, 1)
        qc.h([0, 1])
        explanation = "Hadamard gates prepare a superposition. The oracle marks a state, and the diffusion step increases the probability of the marked state."
        figure = FIG_CIRCUIT
        title = "🔎 Grover Search"
    elif algorithm == "Deutsch-Jozsa":
        qc = QuantumCircuit(2, 2)
        qc.x(1)
        qc.h([0, 1])
        qc.cx(0, 1)
        qc.h(0)
        explanation = "The input is prepared in superposition, an oracle is applied, and the final Hadamard operation reveals information about the function."
        figure = FIG_CIRCUIT
        title = "⚡ Deutsch-Jozsa"
    elif algorithm == "Quantum Fourier Transform":
        qc = QuantumCircuit(2, 2)
        qc.h(0)
        qc.cp(np.pi / 2, 0, 1)
        qc.h(1)
        qc.swap(0, 1)
        explanation = "Hadamard and controlled-phase gates transform the amplitudes into the Fourier basis. SWAP reverses the qubit order for the two-qubit QFT."
        figure = FIG_CIRCUIT
        title = "🌊 Quantum Fourier Transform"
    elif algorithm == "VQE":
        qc = QuantumCircuit(2, 2)
        qc.ry(np.pi / 4, 0)
        qc.cx(0, 1)
        explanation = "VQE uses a parameterized ansatz, measures an objective such as energy, and uses a classical optimizer to update circuit parameters."
        figure = FIG_CIRCUIT
        title = "⚛️ VQE"
    else:
        qc = QuantumCircuit(2, 2)
        qc.h([0, 1])
        qc.rzz(np.pi / 4, 0, 1)
        explanation = "QAOA alternates a cost operation with a mixer. Parameters are optimized classically to improve the objective for a combinatorial problem."
        figure = FIG_CIRCUIT
        title = "🧩 QAOA"

    st.subheader(title)

    if figure.exists():
        st.image(str(figure), use_container_width=True)
        st.caption("Existing Quantum LearnLab figure from the assets folder.")
    else:
        st.warning("The figure file is not in the deployed assets folder. Keep the existing assets folder in your GitHub repository.")

    st.subheader("Algorithm Explanation")
    st.info(explanation)

    st.subheader("Quantum Circuit")
    st.code(str(qc.draw(output="text")), language="text")

    st.subheader("Circuit Explanation")
    st.write(explanation)

    if st.button("▶️ Simulate Algorithm", use_container_width=True, key=f"simulate_algorithm_{algorithm}"):
        qc_run = qc.copy()
        qc_run.measure([0, 1], [0, 1])
        counts = run_circuit(qc_run, 512)
        st.subheader("Measurement Result")
        st.json(counts)


# =========================================================
# VISUALIZATION
# =========================================================

# =========================================================

elif page == "📊 Visualization":

    st.title(
        "📊 Quantum State Visualization"
    )


    state = st.selectbox(
        "Select State",
        [
            "|0⟩",
            "|1⟩",
            "|+⟩",
            "|-⟩"
        ]
    )


    if state == "|0⟩":

        probs = [
            1,
            0
        ]

    elif state == "|1⟩":

        probs = [
            0,
            1
        ]

    else:

        probs = [
            0.5,
            0.5
        ]


    st.subheader(
        "Probability Distribution"
    )


    fig, ax = plt.subplots()

    ax.bar(
        [
            "|0⟩",
            "|1⟩"
        ],
        probs
    )

    ax.set_ylim(
        0,
        1
    )

    ax.set_ylabel(
        "Probability"
    )

    ax.set_title(
        f"State {state}"
    )

    st.pyplot(
        fig
    )


    st.subheader(
        "Measurement Simulation"
    )


    shots = st.slider(
        "Shots",
        100,
        5000,
        1000
    )


    results = np.random.choice(
        [
            "0",
            "1"
        ],
        size=shots,
        p=probs
    )


    unique, counts = np.unique(
        results,
        return_counts=True
    )


    measurement_data = dict(
        zip(
            unique,
            counts
        )
    )


    st.write(
        measurement_data
    )


    # =====================================================
    # BLOCH SPHERE
    # =====================================================

    st.subheader(
        "🌀 Bloch Sphere"
    )


    fig2 = plt.figure()

    ax2 = fig2.add_subplot(
        111,
        projection="3d"
    )


    u = np.linspace(
        0,
        2 * np.pi,
        50
    )

    v = np.linspace(
        0,
        np.pi,
        50
    )


    x = np.outer(
        np.cos(u),
        np.sin(v)
    )

    y = np.outer(
        np.sin(u),
        np.sin(v)
    )

    z = np.outer(
        np.ones(
            np.size(u)
        ),
        np.cos(v)
    )


    ax2.plot_wireframe(
        x,
        y,
        z,
        alpha=0.15
    )


    if state == "|0⟩":

        point = [
            0,
            0,
            1
        ]

    elif state == "|1⟩":

        point = [
            0,
            0,
            -1
        ]

    elif state == "|+⟩":

        point = [
            1,
            0,
            0
        ]

    else:

        point = [
            -1,
            0,
            0
        ]


    ax2.scatter(
        point[0],
        point[1],
        point[2],
        s=100
    )


    ax2.set_xlabel(
        "X"
    )

    ax2.set_ylabel(
        "Y"
    )

    ax2.set_zlabel(
        "Z"
    )


    st.pyplot(
        fig2
    )


# =========================================================
# QISKIT CODE EDITOR
# =========================================================

elif page == "💻 Qiskit Code Editor":

    st.title(
        "💻 Qiskit Code Editor"
    )

    st.write(
        "Write and execute your own "
        "Qiskit quantum program."
    )


    default_code = """from qiskit import QuantumCircuit

qc = QuantumCircuit(2)

qc.h(0)
qc.cx(0, 1)

print(qc)

qc.measure_all()
"""


    code = st.text_area(
        "Enter Qiskit Code",
        value=default_code,
        height=300
    )


    if st.button(
        "▶️ Run Qiskit Code"
    ):

        output = {}

        try:

            exec(
                code,
                {
                    "__builtins__":
                        __builtins__,
                    "QuantumCircuit":
                        QuantumCircuit
                },
                output
            )

            st.success(
                "Code executed successfully!"
            )


            if "qc" in output:

                qc = output["qc"]

                show_circuit(qc)


                try:

                    counts = run_circuit(
                        qc
                    )

                    st.write(
                        "Measurement:",
                        counts
                    )

                except Exception as e:

                    st.warning(
                        str(e)
                    )


            add_points(15)

            check_badges()


        except Exception as e:

            st.error(
                "❌ Code Error"
            )

            st.code(
                str(e)
            )

            st.info(
                "Use the 'Fix My Circuit' page "
                "for debugging suggestions."
            )


# =========================================================
# FIX MY CIRCUIT
# =========================================================

elif page == "🐛 Fix My Circuit":

    st.title(
        "🐛 Fix My Circuit"
    )

    st.write(
        "Enter your Qiskit code and "
        "get basic error analysis."
    )


    code = st.text_area(
        "Paste your Qiskit code",
        height=250
    )


    if st.button(
        "🔧 Analyze Code"
    ):

        if not code.strip():

            st.warning(
                "Please enter Qiskit code."
            )

        else:

            errors = []


            if "QuantumCircuit" not in code:

                errors.append(
                    "QuantumCircuit is not imported."
                )


            if "QuantumCircuit(" not in code:

                errors.append(
                    "Create a quantum circuit "
                    "using QuantumCircuit()."
                )


            if ".h(" in code and "QuantumCircuit" not in code:

                errors.append(
                    "H gate requires a quantum circuit."
                )


            if ".cx(" in code and "QuantumCircuit" not in code:

                errors.append(
                    "CNOT requires a quantum circuit."
                )


            if "measure" not in code:

                errors.append(
                    "Measurement is not present. "
                    "Consider using qc.measure_all()."
                )


            if errors:

                st.error(
                    f"{len(errors)} possible issue(s) found:"
                )

                for error in errors:

                    st.write(
                        "🔴",
                        error
                    )

            else:

                st.success(
                    "No obvious structural errors detected."
                )

                st.info(
                    "Try running the code in "
                    "the Qiskit Code Editor."
                )


# =========================================================
# AI TUTOR
# =========================================================

elif page == "🤖 AI Tutor":

    st.title("🤖 AI Quantum Tutor")
    st.write("Ask any question about quantum computing. Gemini will generate the explanation.")

    question = st.text_area(
        "Ask your question",
        placeholder="Example: What is the difference between a classical computer and a quantum computer?",
        height=120,
        key="ai_tutor_question"
    )

    if st.button("💡 Ask AI", use_container_width=True):
        if not question.strip():
            st.warning("Please enter a question.")
        else:
            with st.spinner("Gemini is thinking..."):
                answer, error = ask_gemini(
                    "You are Quantum LearnLab AI Tutor. Explain the following question in simple, technically correct English for a beginner B.Tech student. Use short headings and examples when useful. Do not invent facts.\n\nQuestion: " + question.strip()
                )
            if answer:
                st.markdown(answer)
                st.session_state.history.append({"AI Question": question.strip(), "AI Answer": answer})
                save_profile()
                add_points(5)
            else:
                st.error(f"Gemini Error: {error}")
                st.info("The AI service may be temporarily busy. Please try the same question again.")

# =========================================================
# QUIZ
# =========================================================

elif page == "📝 Quiz":

    st.title(
        "📝 Quantum Computing Quiz"
    )


    questions = [

        (
            "What is the basic unit of quantum information?",
            [
                "Bit",
                "Qubit",
                "Byte",
                "Neuron"
            ],
            "Qubit"
        ),

        (
            "Which gate creates superposition from |0⟩?",
            [
                "X",
                "Z",
                "H",
                "CNOT"
            ],
            "H"
        ),

        (
            "Which gate is commonly used for two-qubit entanglement?",
            [
                "X",
                "CNOT",
                "Z",
                "RX"
            ],
            "CNOT"
        ),

        (
            "What framework is used in this platform?",
            [
                "TensorFlow",
                "Qiskit",
                "OpenCV",
                "Pandas"
            ],
            "Qiskit"
        ),

        (
            "Which algorithm provides a quadratic search speedup?",
            [
                "Grover",
                "Bubble Sort",
                "DFS",
                "Linear Search"
            ],
            "Grover"
        )
    ]


    difficulty = st.selectbox(
        "Difficulty",
        [
            "Easy",
            "Medium",
            "Hard"
        ]
    )


    score = 0


    for i, (
        question_text,
        options,
        answer
    ) in enumerate(questions):

        selected = st.radio(
            f"{i + 1}. {question_text}",
            options,
            key=f"question_{i}"
        )


        if selected == answer:

            score += 1


    if st.button(
        "📊 Submit Quiz"
    ):

        st.session_state.quiz_score = score
        save_profile()


        if score == len(questions):

            add_points(50)

            st.balloons()

        else:

            add_points(
                score * 5
            )


        check_badges()


        st.success(
            f"Your score: {score}/{len(questions)}"
        )


        st.write(
            f"Total points: "
            f"{st.session_state.points}"
        )


# =========================================================
# PROGRESS
# =========================================================

elif page == "📈 Progress":

    st.title(
        "📈 Learning Progress"
    )


    total_topics = 8


    completed_topics = len(
        st.session_state.completed
    )


    progress = min(
        completed_topics / total_topics,
        1.0
    )


    st.progress(
        progress
    )


    st.metric(
        "Topics Completed",
        f"{completed_topics}/{total_topics}"
    )


    st.metric(
        "Quiz Score",
        st.session_state.quiz_score
    )


    st.metric(
        "Points",
        st.session_state.points
    )


    st.subheader(
        "Completed Topics"
    )


    if st.session_state.completed:

        for topic in st.session_state.completed:

            st.write(
                "✅",
                topic
            )

    else:

        st.info(
            "Complete learning modules "
            "to see your progress."
        )


    st.subheader(
        "🏅 Badges"
    )


    if st.session_state.badges:

        for badge in st.session_state.badges:

            st.markdown(
                f"""
                <span class="badge">
                🏆 {badge}
                </span>
                """,
                unsafe_allow_html=True
            )

    else:

        st.info(
            "Earn badges by learning "
            "and completing quizzes."
        )


# =========================================================
# LEADERBOARD
# =========================================================

elif page == "🏆 Leaderboard":

    st.title(
        "🏆 Quantum Learner Leaderboard"
    )


    leaderboard = pd.DataFrame(
        {
            "Rank": [
                1,
                2,
                3,
                4
            ],

            "Learner": [
                "Quantum Master",
                "Qubit Explorer",
                "Circuit Builder",
                "You"
            ],

            "Points": [
                250,
                200,
                150,
                st.session_state.points
            ]
        }
    )


    leaderboard = (
        leaderboard
        .sort_values(
            "Points",
            ascending=False
        )
        .reset_index(
            drop=True
        )
    )


    leaderboard["Rank"] = range(
        1,
        len(leaderboard) + 1
    )


    st.dataframe(
        leaderboard,
        use_container_width=True
    )


    st.subheader(
        "🏅 Your Badges"
    )


    if st.session_state.badges:

        for badge in st.session_state.badges:

            st.write(
                "🏆",
                badge
            )

    else:

        st.info(
            "No badges yet. Start learning!"
        )


# =========================================================
# FOOTER
# =========================================================

st.sidebar.divider()

st.sidebar.write(
    "⚛️ Quantum LearnLab AI"
)

st.sidebar.write(
    "Interactive Quantum Education Platform"
)
