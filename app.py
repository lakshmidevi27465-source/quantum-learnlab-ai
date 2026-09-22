import streamlit as st
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import hashlib
import json
from pathlib import Path

from supabase import create_client, Client

from qiskit import QuantumCircuit, transpile
from qiskit_aer import AerSimulator


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

    fig = qc.draw(
        output="mpl",
        fold=-1
    )

    return fig


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
            st.pyplot(draw_circuit(qc))
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

        "Select-and-add quantum circuit builder with gate learning",

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

        st.pyplot(
            draw_circuit(qc_demo)
        )

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

        st.pyplot(
            draw_circuit(qc_demo)
        )

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

        st.pyplot(
            draw_circuit(qc_demo)
        )

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

        st.pyplot(
            draw_circuit(qc_demo)
        )

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

        st.pyplot(
            draw_circuit(qc_demo)
        )

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
# CIRCUIT BUILDER + GATE LEARNING
# =========================================================

elif page == "⚛️ Circuit Builder":

    st.title("⚛️ Quantum Circuit Builder")
    st.write(
        "Build a circuit by selecting a gate and qubit. "
        "No drag-and-drop is required."
    )

    # --------------------------------------------------------
    # Gate learning information
    # --------------------------------------------------------
    GATE_INFO = {
        "H": {
            "name": "Hadamard Gate (H)",
            "type": "Single-qubit gate",
            "description": "The Hadamard gate creates an equal superposition from a computational-basis state.",
            "matrix": "1/√2 × [[1, 1], [1, -1]]",
            "example": "|0⟩ → (|0⟩ + |1⟩)/√2",
            "use": "Creating quantum superposition.",
            "circuit": "q0: ──H──"
        },
        "X": {
            "name": "Pauli-X Gate (X)",
            "type": "Single-qubit gate",
            "description": "The X gate flips the computational-basis state of a qubit.",
            "matrix": "[[0, 1], [1, 0]]",
            "example": "|0⟩ → |1⟩   and   |1⟩ → |0⟩",
            "use": "Bit-flip operation.",
            "circuit": "q0: ──X──"
        },
        "Y": {
            "name": "Pauli-Y Gate (Y)",
            "type": "Single-qubit gate",
            "description": "The Y gate performs a bit flip together with a phase change.",
            "matrix": "[[0, -i], [i, 0]]",
            "example": "|0⟩ → i|1⟩   and   |1⟩ → -i|0⟩",
            "use": "Bit and phase transformation.",
            "circuit": "q0: ──Y──"
        },
        "Z": {
            "name": "Pauli-Z Gate (Z)",
            "type": "Single-qubit gate",
            "description": "The Z gate changes the phase of |1⟩ while leaving |0⟩ unchanged.",
            "matrix": "[[1, 0], [0, -1]]",
            "example": "|0⟩ → |0⟩   and   |1⟩ → -|1⟩",
            "use": "Phase-flip operation.",
            "circuit": "q0: ──Z──"
        },
        "S": {
            "name": "S Gate", 
            "type": "Single-qubit gate",
            "description": "The S gate applies a π/2 phase shift to the |1⟩ component.",
            "matrix": "[[1, 0], [0, i]]",
            "example": "|0⟩ → |0⟩   and   |1⟩ → i|1⟩",
            "use": "Applying a 90° phase shift.",
            "circuit": "q0: ──S──"
        },
        "T": {
            "name": "T Gate",
            "type": "Single-qubit gate",
            "description": "The T gate applies a π/4 phase shift to the |1⟩ component.",
            "matrix": "[[1, 0], [0, e^(iπ/4)]]",
            "example": "|0⟩ → |0⟩   and   |1⟩ → e^(iπ/4)|1⟩",
            "use": "Applying a 45° phase shift.",
            "circuit": "q0: ──T──"
        },
        "CNOT": {
            "name": "Controlled-NOT Gate (CNOT)",
            "type": "Two-qubit gate",
            "description": "CNOT flips the target qubit when the control qubit is |1⟩.",
            "matrix": "[[1,0,0,0], [0,1,0,0], [0,0,0,1], [0,0,1,0]]",
            "example": "|10⟩ → |11⟩   and   |11⟩ → |10⟩",
            "use": "Conditional bit flip and entanglement demonstrations.",
            "circuit": "q0: ──●──\n      │\nq1: ──X──"
        },
        "CZ": {
            "name": "Controlled-Z Gate (CZ)",
            "type": "Two-qubit gate",
            "description": "CZ applies a phase flip only when both qubits are in |1⟩.",
            "matrix": "[[1,0,0,0], [0,1,0,0], [0,0,1,0], [0,0,0,-1]]",
            "example": "|11⟩ → -|11⟩",
            "use": "Conditional phase operation.",
            "circuit": "q0: ──●──\n      │\nq1: ──●──"
        },
        "SWAP": {
            "name": "SWAP Gate",
            "type": "Two-qubit gate",
            "description": "SWAP exchanges the quantum states of two qubits.",
            "matrix": "[[1,0,0,0], [0,0,1,0], [0,1,0,0], [0,0,0,1]]",
            "example": "|01⟩ → |10⟩   and   |10⟩ → |01⟩",
            "use": "Exchanging the states of two qubits.",
            "circuit": "q0: ──×──\n      │\nq1: ──×──"
        }
    }

    single_gates = ["H", "X", "Y", "Z", "S", "T"]
    two_gates = ["CNOT", "CZ", "SWAP"]
    all_gates = single_gates + two_gates

    if "builder_num_qubits" not in st.session_state:
        st.session_state.builder_num_qubits = 2
    if "builder_operations" not in st.session_state:
        st.session_state.builder_operations = []

    n_qubits = st.selectbox(
        "Number of Qubits",
        [1, 2, 3, 4],
        index=[1, 2, 3, 4].index(st.session_state.builder_num_qubits),
        key="builder_qubit_count"
    )

    if n_qubits != st.session_state.builder_num_qubits:
        st.session_state.builder_num_qubits = n_qubits
        st.session_state.builder_operations = []

    st.subheader("➕ Add a Gate")

    gate = st.selectbox(
        "Select Gate",
        all_gates,
        key="builder_gate_select"
    )

    q1 = st.selectbox(
        "Select Qubit",
        list(range(n_qubits)),
        format_func=lambda x: f"q{x}",
        key="builder_q1"
    )

    q2 = None
    if gate in two_gates:
        q2 = st.selectbox(
            "Select Target / Second Qubit",
            [q for q in range(n_qubits) if q != q1],
            format_func=lambda x: f"q{x}",
            key="builder_q2"
        )

    c1, c2, c3 = st.columns(3)

    with c1:
        if st.button("➕ Add Gate", use_container_width=True):
            if gate in two_gates and q1 == q2:
                st.error("A two-qubit gate needs two different qubits.")
            else:
                st.session_state.builder_operations.append(
                    {"gate": gate, "q1": q1, "q2": q2}
                )
                st.success(f"{gate} gate added.")

    with c2:
        if st.button("↩️ Remove Last Gate", use_container_width=True):
            if st.session_state.builder_operations:
                removed = st.session_state.builder_operations.pop()
                st.success(f"Removed {removed['gate']} gate.")
            else:
                st.info("No gates to remove.")

    with c3:
        if st.button("🗑️ Clear Circuit", use_container_width=True):
            st.session_state.builder_operations = []
            st.success("Circuit cleared.")

    # Build the circuit from the stored operations.
    qc = QuantumCircuit(n_qubits)

    for op in st.session_state.builder_operations:
        g = op["gate"]
        a = op["q1"]
        b = op.get("q2")
        if g == "H":
            qc.h(a)
        elif g == "X":
            qc.x(a)
        elif g == "Y":
            qc.y(a)
        elif g == "Z":
            qc.z(a)
        elif g == "S":
            qc.s(a)
        elif g == "T":
            qc.t(a)
        elif g == "CNOT":
            qc.cx(a, b)
        elif g == "CZ":
            qc.cz(a, b)
        elif g == "SWAP":
            qc.swap(a, b)

    st.subheader("📋 Gates in Current Circuit")
    if st.session_state.builder_operations:
        for i, op in enumerate(st.session_state.builder_operations, start=1):
            if op.get("q2") is None:
                st.write(f"{i}. **{op['gate']}** → q{op['q1']}")
            else:
                st.write(f"{i}. **{op['gate']}** → q{op['q1']} → q{op['q2']}")
    else:
        st.info("No gates added yet. Select a gate and click Add Gate.")

    st.subheader("⚛️ Circuit")
    try:
        st.pyplot(draw_circuit(qc))
    except Exception:
        st.code(str(qc))

    if st.button("▶️ Simulate Circuit", use_container_width=True):
        if not st.session_state.builder_operations:
            st.warning("Add at least one gate before simulation.")
        else:
            counts = run_circuit(qc)
            st.session_state.history.append(
                {"Circuit": str(qc), "Result": counts}
            )
            save_profile()
            st.subheader("📊 Measurement Result")
            st.write(counts)
            st.bar_chart(pd.DataFrame({"Count": counts}).T)
            add_points(10)
            check_badges()
            st.success("Circuit executed! +10 points")

    # --------------------------------------------------------
    # Learn about the selected gate
    # --------------------------------------------------------
    st.divider()
    st.subheader("📖 Learn About This Gate")

    info = GATE_INFO[gate]
    st.markdown(f"### {info['name']}")
    st.caption(info["type"])
    st.write(info["description"])

    with st.expander("📐 Matrix Representation", expanded=True):
        st.code(info["matrix"])

    with st.expander("🔄 Input → Output", expanded=True):
        st.code(info["example"])

    with st.expander("🧩 Simple Circuit Example", expanded=True):
        st.code(info["circuit"])

    st.info(f"Main use: {info['use']}")

    if st.button(f"💡 Explain {gate} Gate", use_container_width=True):
        st.session_state.builder_operations.append(
            {"gate": gate, "q1": q1, "q2": q2}
        )
        st.success(
            f"{gate} gate added to the circuit. Now you can simulate it above."
        )

# =========================================================
# QUANTUM ALGORITHMS
# =========================================================

elif page == "🧪 Quantum Algorithms":

    st.title(
        "🧪 Quantum Algorithms"
    )


    algorithm = st.selectbox(
        "Select Algorithm",
        [
            "Bell State",
            "Grover Search",
            "Deutsch-Jozsa",
            "Quantum Fourier Transform"
        ]
    )


    # =====================================================
    # BELL STATE
    # =====================================================

    if algorithm == "Bell State":

        st.subheader(
            "🔗 Bell State"
        )

        qc = QuantumCircuit(2)

        qc.h(0)

        qc.cx(
            0,
            1
        )

        st.pyplot(
            draw_circuit(qc)
        )

        counts = run_circuit(
            qc
        )

        st.write(
            "Measurement:",
            counts
        )

        st.info(
            "Bell states demonstrate quantum entanglement."
        )

        if FIG_ENTANGLEMENT.exists():

            st.subheader(
                "🖼️ Entanglement Figure"
            )

            st.image(
                str(FIG_ENTANGLEMENT),
                use_container_width=True
            )


        complete_topic(
            "Bell State"
        )


    # =====================================================
    # GROVER
    # =====================================================

    elif algorithm == "Grover Search":

        st.subheader(
            "🔎 Grover Search"
        )

        qc = QuantumCircuit(2)

        qc.h(
            [0, 1]
        )

        qc.cz(
            0,
            1
        )

        qc.h(
            [0, 1]
        )

        qc.x(
            [0, 1]
        )

        qc.h(1)

        qc.cx(
            0,
            1
        )

        qc.h(1)

        qc.x(
            [0, 1]
        )

        qc.h(
            [0, 1]
        )

        st.pyplot(
            draw_circuit(qc)
        )

        counts = run_circuit(
            qc
        )

        st.write(
            "Measurement:",
            counts
        )

        st.info(
            "Grover's algorithm provides a "
            "quadratic speedup for unstructured search."
        )


    # =====================================================
    # DEUTSCH-JOZSA
    # =====================================================

    elif algorithm == "Deutsch-Jozsa":

        st.subheader(
            "⚡ Deutsch-Jozsa"
        )

        qc = QuantumCircuit(2)

        qc.x(1)

        qc.h(
            [0, 1]
        )

        qc.cx(
            0,
            1
        )

        qc.h(0)

        st.pyplot(
            draw_circuit(qc)
        )

        counts = run_circuit(
            qc
        )

        st.write(
            "Measurement:",
            counts
        )

        st.info(
            "Deutsch-Jozsa demonstrates quantum advantage "
            "for determining properties of a function."
        )


    # =====================================================
    # QFT
    # =====================================================

    else:

        st.subheader(
            "🌊 Quantum Fourier Transform"
        )

        qc = QuantumCircuit(2)

        qc.h(0)

        qc.cp(
            np.pi / 2,
            0,
            1
        )

        qc.h(1)

        st.pyplot(
            draw_circuit(qc)
        )

        counts = run_circuit(
            qc
        )

        st.write(
            "Measurement:",
            counts
        )

        st.info(
            "QFT is an important building block "
            "in several quantum algorithms."
        )


        if FIG_CIRCUIT.exists():

            st.subheader(
                "🖼️ Quantum Circuit Figure"
            )

            st.image(
                str(FIG_CIRCUIT),
                use_container_width=True
            )


# =========================================================
# VISUALIZATION
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

                st.pyplot(
                    draw_circuit(qc)
                )


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

    st.title(
        "🤖 AI Quantum Tutor"
    )

    st.write(
        "Ask questions about quantum computing."
    )


    question = st.text_input(
        "Ask your question"
    )


    if st.button(
        "💡 Ask AI"
    ):

        q = question.lower()


        if "qubit" in q:

            answer = """
A qubit is the basic unit of quantum information.

A classical bit can be 0 or 1, while a qubit can exist
in a superposition of |0⟩ and |1⟩.
"""


        elif "superposition" in q:

            answer = """
Superposition means that a quantum system can be
represented as a combination of multiple basis states
until measurement.
"""


        elif "entanglement" in q:

            answer = """
Quantum entanglement is a correlation between quantum
systems where their states cannot be described independently.
"""


        elif (
            "hadamard" in q
            or "h gate" in q
        ):

            answer = """
The Hadamard gate creates an equal superposition from |0⟩:

|0⟩ → (|0⟩ + |1⟩) / √2
"""


        elif "cnot" in q:

            answer = """
CNOT is a controlled-NOT gate.

If the control qubit is |1⟩,
the target qubit is flipped.
"""


        elif "grover" in q:

            answer = """
Grover's algorithm searches an unstructured space
with a quadratic speedup compared with classical search.
"""


        elif "qiskit" in q:

            answer = """
Qiskit is an open-source framework used to create,
simulate and run quantum circuits.
"""


        else:

            answer = """
I can help with:

• Qubits
• Superposition
• Entanglement
• Quantum gates
• Qiskit
• Quantum algorithms
• Quantum circuits
• Measurement

Try asking one of these topics.
"""


        st.success(
            answer
        )


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
