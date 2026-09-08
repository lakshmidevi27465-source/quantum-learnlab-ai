
import streamlit as st
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import hashlib
import json
from pathlib import Path

from qiskit import QuantumCircuit, transpile
from qiskit_aer import AerSimulator

# =========================================================
# SIMPLE LOCAL AUTHENTICATION
# =========================================================
# Prototype/MVP authentication using a local JSON file.
# For public production deployment, replace this with a proper
# authentication + database service.

USERS_FILE = Path("users.json")

def load_users():
    if USERS_FILE.exists():
        try:
            return json.loads(USERS_FILE.read_text(encoding="utf-8"))
        except Exception:
            return {}
    return {}

def save_users(users):
    USERS_FILE.write_text(json.dumps(users, indent=2), encoding="utf-8")

def hash_password(password):
    return hashlib.sha256(password.encode("utf-8")).hexdigest()

def authenticate_user(email, password):
    users = load_users()
    user = users.get(email.lower().strip())
    return user is not None and user["password"] == hash_password(password)

if "logged_in" not in st.session_state:
    st.session_state.logged_in = False
if "user_email" not in st.session_state:
    st.session_state.user_email = ""
if "user_name" not in st.session_state:
    st.session_state.user_name = ""

# =========================================================
# PAGE CONFIGURATION
# =========================================================

st.set_page_config(
    page_title="Quantum LearnLab AI",
    page_icon="⚛️",
    layout="wide"
)

# =========================================================
# SESSION STATE
# =========================================================

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
# CUSTOM CSS - RESPONSIVE UI
# =========================================================

st.markdown("""
<style>

.main-title {
    font-size: 42px;
    font-weight: bold;
    text-align: center;
}

.subtitle {
    text-align: center;
    font-size: 20px;
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

@media only screen and (max-width: 700px) {
    .main-title {
        font-size: 28px;
    }
}

</style>
""", unsafe_allow_html=True)

# =========================================================
# LOGIN / SIGN UP
# =========================================================

if not st.session_state.logged_in:
    st.markdown(
        '<div class="main-title">⚛️ Quantum LearnLab AI</div>',
        unsafe_allow_html=True
    )
    st.markdown(
        '<div class="subtitle">Sign in to continue your quantum learning journey</div>',
        unsafe_allow_html=True
    )
    st.divider()

    login_tab, signup_tab = st.tabs(["🔐 Login", "📝 Sign Up"])

    with login_tab:
        st.subheader("Welcome back")
        login_email = st.text_input("Email", key="login_email")
        login_password = st.text_input("Password", type="password", key="login_password")

        if st.button("🔓 Login", use_container_width=True):
            if authenticate_user(login_email, login_password):
                users = load_users()
                email = login_email.lower().strip()
                st.session_state.logged_in = True
                st.session_state.user_email = email
                st.session_state.user_name = users[email]["name"]
                st.success("Login successful!")
                st.rerun()
            else:
                st.error("Invalid email or password.")

    with signup_tab:
        st.subheader("Create your account")
        signup_name = st.text_input("Name", key="signup_name")
        signup_email = st.text_input("Email", key="signup_email")
        signup_password = st.text_input("Password", type="password", key="signup_password")
        signup_confirm = st.text_input("Confirm Password", type="password", key="signup_confirm")

        if st.button("🚀 Create Account", use_container_width=True):
            email = signup_email.lower().strip()
            users = load_users()

            if not signup_name.strip() or not email or not signup_password:
                st.warning("Please fill all fields.")
            elif "@" not in email:
                st.warning("Please enter a valid email.")
            elif len(signup_password) < 6:
                st.warning("Password must contain at least 6 characters.")
            elif signup_password != signup_confirm:
                st.error("Passwords do not match.")
            elif email in users:
                st.error("An account with this email already exists.")
            else:
                users[email] = {
                    "name": signup_name.strip(),
                    "password": hash_password(signup_password)
                }
                save_users(users)
                st.success("Account created. Please use the Login tab.")

    st.stop()

# =========================================================
# SIDEBAR
# =========================================================

st.sidebar.title("⚛️ Quantum LearnLab AI")
st.sidebar.success(f"👤 {st.session_state.user_name}")
if st.sidebar.button("🚪 Logout"):
    st.session_state.logged_in = False
    st.session_state.user_email = ""
    st.session_state.user_name = ""
    st.rerun()


page = st.sidebar.radio(
    "Navigation",
    [
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
    ]
)

# =========================================================
# HELPER FUNCTIONS
# =========================================================

def add_points(points):
    st.session_state.points += points


def complete_topic(topic):
    if topic not in st.session_state.completed:
        st.session_state.completed.append(topic)
        add_points(10)


def check_badges():

    if len(st.session_state.completed) >= 3:
        if "Quantum Beginner" not in st.session_state.badges:
            st.session_state.badges.append("Quantum Beginner")

    if len(st.session_state.completed) >= 6:
        if "Quantum Explorer" not in st.session_state.badges:
            st.session_state.badges.append("Quantum Explorer")

    if st.session_state.quiz_score >= 4:
        if "Quiz Master" not in st.session_state.badges:
            st.session_state.badges.append("Quiz Master")

    if st.session_state.points >= 100:
        if "Quantum Champion" not in st.session_state.badges:
            st.session_state.badges.append("Quantum Champion")


def run_circuit(qc, shots=1024):

    simulator = AerSimulator()

    qc_run = qc.copy()

    if qc_run.num_clbits == 0:
        qc_run.measure_all()

    compiled = transpile(qc_run, simulator)

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
# HOME
# =========================================================

if page == "🏠 Home":

    st.markdown(
        '<div class="main-title">⚛️ Quantum LearnLab AI</div>',
        unsafe_allow_html=True
    )

    st.markdown(
        '<div class="subtitle">Interactive AI-Powered Quantum Computing Learning Platform</div>',
        unsafe_allow_html=True
    )

    st.divider()

    col1, col2, col3 = st.columns(3)

    with col1:
        st.info("📚 Learn\n\nQuantum concepts interactively.")

    with col2:
        st.success("⚛️ Build\n\nCreate quantum circuits.")

    with col3:
        st.warning("🤖 Ask AI\n\nGet explanations and debugging help.")

    st.divider()

    st.subheader("🚀 Learning Workflow")

    st.write(
        "Learn → Build → Run → Visualize → Ask AI → Fix → Challenge → Track"
    )

    st.subheader("✨ Platform Features")

    features = [
        "Interactive quantum learning modules",
        "Drag-and-select quantum circuit builder",
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
        st.write("✅", feature)


# =========================================================
# LEARN
# =========================================================

elif page == "📚 Learn":

    st.title("📚 Learn Quantum Computing")
    st.write("Learn the concepts using the explanations and figures from the supplied quantum-network paper.")

    topics = {
        "Qubit": {
            "description": "A qubit is the quantum counterpart of a classical bit. Unlike a classical bit, a qubit can exist in a superposition of states. When measured, it produces a classical outcome according to the measurement basis.",
            "representation": "|ψ⟩ = α|0⟩ + β|1⟩",
            "takeaway": "The measurement outcome depends on the quantum state and the measurement basis.",
            "image": "assets/fig1_qubit_superposition.png",
            "caption": "Figure 1 — Qubit in a superposition and collapse after measurement (from the supplied PDF)."
        },
        "Superposition": {
            "description": "Superposition means that a quantum state can be represented as a combination of basis states until measurement. The supplied paper illustrates this using a qubit whose state is not determined before measurement.",
            "representation": "|ψ⟩ = α|0⟩ + β|1⟩",
            "takeaway": "Measurement selects a classical outcome from the quantum state.",
            "image": "assets/fig1_qubit_superposition.png",
            "caption": "Figure 1 — Superposition and measurement of a qubit (from the supplied PDF)."
        },
        "Entanglement": {
            "description": "Entanglement produces correlations between quantum systems. The paper explains entanglement and shows entanglement swapping and quantum teleportation as important quantum-network operations.",
            "representation": "H + CNOT → entangled qubits",
            "takeaway": "Entangled-qubit measurement outcomes can be correlated even when the qubits do not directly interact at the end of the protocol.",
            "image": "assets/fig3_entanglement_teleportation.png",
            "caption": "Figure 3 — Entanglement swapping and quantum teleportation (from the supplied PDF)."
        },
        "Hadamard Gate": {
            "description": "The Hadamard gate is shown in the paper's distributed quantum circuit. It creates a superposition from a computational-basis state; for example, |0⟩ is transformed into an equal superposition of |0⟩ and |1⟩.",
            "representation": "H|0⟩ = (|0⟩ + |1⟩)/√2",
            "takeaway": "The Hadamard operation is the first step in the paper's example distributed circuit.",
            "image": "assets/fig4_hadamard_cnot_circuit.png",
            "caption": "Figure 4 — Distributed circuit showing Hadamard and CNOT operations (from the supplied PDF)."
        },
        "CNOT Gate": {
            "description": "CNOT is a two-qubit controlled operation. In the paper's example, CNOT operations are used to create entanglement between qubits as part of entanglement swapping.",
            "representation": "Q0: ──●──\nQ1: ──⊕──",
            "takeaway": "CNOT combined with Hadamard is a standard way to demonstrate entanglement.",
            "image": "assets/fig4_hadamard_cnot_circuit.png",
            "caption": "Figure 4 — Distributed quantum circuit containing CNOT operations (from the supplied PDF)."
        },
        "Measurement": {
            "description": "Measurement is the process of observing a qubit with respect to a chosen basis. The supplied paper explains that measurement changes the state and maps the quantum result to a classical outcome.",
            "representation": "Quantum state → Measurement → 0 or 1",
            "takeaway": "The measurement basis matters, and measurement is an active process.",
            "image": "assets/fig1_qubit_superposition.png",
            "caption": "Figure 1 — Measurement of a qubit in the computational basis (from the supplied PDF)."
        },
        "Quantum Interference": {
            "description": "The supplied PDF does not contain a dedicated figure specifically labelled as quantum interference. This lesson therefore explains the concept without claiming that a PDF figure depicts interference.",
            "representation": "Amplitudes → constructive/destructive interference → probabilities",
            "takeaway": "Interference changes probability amplitudes and is a key mechanism used by quantum algorithms.",
            "image": None,
            "caption": "No dedicated interference figure was found in the supplied PDF."
        },
        "Quantum Algorithms": {
            "description": "Quantum algorithms combine quantum states, gates, measurements and interference to perform computational tasks. This platform also provides circuit simulations.",
            "representation": "State preparation → gates → measurement",
            "takeaway": "Quantum algorithms are built from sequences of quantum operations.",
            "image": "assets/fig4_hadamard_cnot_circuit.png",
            "caption": "Figure 4 — Example distributed quantum circuit from the supplied PDF."
        }
    }

    selected = st.selectbox("Select a topic", list(topics.keys()))
    lesson = topics[selected]

    st.markdown(
        f"""
        <div class="card">
        <h2>{selected}</h2>
        <p>{lesson["description"]}</p>
        </div>
        """,
        unsafe_allow_html=True
    )

    st.subheader("🧠 Key idea")
    st.info(lesson["takeaway"])

    st.subheader("⚛️ Mathematical / Circuit Representation")
    st.code(lesson["representation"])

    if lesson["image"]:
        image_path = Path(lesson["image"])
        if image_path.exists():
            st.subheader("🖼️ Figure from your PDF")
            st.image(str(image_path), use_container_width=True)
            st.caption(lesson["caption"])
        else:
            st.warning(f"Image asset not found: {image_path}. Upload the assets folder to GitHub.")
    else:
        st.info(lesson["caption"])

    if selected == "Hadamard Gate":
        qc_demo = QuantumCircuit(1)
        qc_demo.h(0)
        st.subheader("Interactive H-gate demonstration")
        st.pyplot(draw_circuit(qc_demo))
        if st.button("▶️ Simulate Hadamard", key="learn_h"):
            st.write("Measurement:", run_circuit(qc_demo))
            add_points(5)

    elif selected == "CNOT Gate":
        qc_demo = QuantumCircuit(2)
        qc_demo.h(0)
        qc_demo.cx(0, 1)
        st.subheader("Interactive H + CNOT demonstration")
        st.pyplot(draw_circuit(qc_demo))
        if st.button("▶️ Simulate H + CNOT", key="learn_cnot"):
            st.write("Measurement:", run_circuit(qc_demo))
            add_points(5)

    elif selected == "Superposition":
        qc_demo = QuantumCircuit(1)
        qc_demo.h(0)
        st.subheader("Interactive superposition demonstration")
        st.pyplot(draw_circuit(qc_demo))
        if st.button("▶️ Simulate Superposition", key="learn_superposition"):
            st.write("Measurement:", run_circuit(qc_demo))
            add_points(5)

    elif selected == "Entanglement":
        qc_demo = QuantumCircuit(2)
        qc_demo.h(0)
        qc_demo.cx(0, 1)
        st.subheader("Interactive Bell-state demonstration")
        st.pyplot(draw_circuit(qc_demo))
        if st.button("▶️ Simulate Entanglement", key="learn_entanglement"):
            st.write("Measurement:", run_circuit(qc_demo))
            add_points(5)

    elif selected == "Measurement":
        qc_demo = QuantumCircuit(1)
        qc_demo.h(0)
        qc_demo.measure_all()
        st.subheader("Interactive measurement demonstration")
        st.pyplot(draw_circuit(qc_demo))
        if st.button("▶️ Run Measurement", key="learn_measurement"):
            st.write("Measurement:", run_circuit(qc_demo))
            add_points(5)

    elif selected == "Quantum Algorithms":
        st.info("Use 🧪 Quantum Algorithms in the sidebar for algorithm demonstrations.")

    if st.button("✅ Mark Topic Complete"):
        complete_topic(selected)
        check_badges()
        st.success(f"{selected} completed! +10 points")


# =========================================================
# CIRCUIT BUILDER
# =========================================================

elif page == "⚛️ Circuit Builder":

    st.title("⚛️ Quantum Circuit Builder")

    st.write(
        "Create a quantum circuit by selecting gates for each qubit."
    )

    n_qubits = st.selectbox(
        "Number of Qubits",
        [1, 2, 3]
    )

    gates = [
        "None",
        "H",
        "X",
        "Y",
        "Z",
        "RX",
        "RY",
        "RZ"
    ]

    selected_gates = []

    for q in range(n_qubits):

        gate = st.selectbox(
            f"Qubit {q}",
            gates,
            key=f"gate_{q}"
        )

        selected_gates.append(gate)

    cnot = False

    if n_qubits >= 2:

        cnot = st.checkbox(
            "Add CNOT between Q0 → Q1"
        )

    qc = QuantumCircuit(n_qubits)

    for q, gate in enumerate(selected_gates):

        if gate == "H":
            qc.h(q)

        elif gate == "X":
            qc.x(q)

        elif gate == "Y":
            qc.y(q)

        elif gate == "Z":
            qc.z(q)

        elif gate == "RX":
            qc.rx(np.pi / 2, q)

        elif gate == "RY":
            qc.ry(np.pi / 2, q)

        elif gate == "RZ":
            qc.rz(np.pi / 2, q)

    if cnot:
        qc.cx(0, 1)

    st.subheader("Circuit")

    try:
        st.pyplot(draw_circuit(qc))
    except Exception:
        st.code(str(qc))

    if st.button("▶️ Run Circuit"):

        counts = run_circuit(qc)

        st.session_state.history.append(
            {
                "Circuit": str(qc),
                "Result": counts
            }
        )

        st.subheader("Measurement Result")

        st.write(counts)

        add_points(10)
        check_badges()

        st.success("Circuit executed! +10 points")


# =========================================================
# QUANTUM ALGORITHMS
# =========================================================

elif page == "🧪 Quantum Algorithms":

    st.title("🧪 Quantum Algorithms")

    algorithm = st.selectbox(
        "Select Algorithm",
        [
            "Bell State",
            "Grover Search",
            "Deutsch-Jozsa",
            "Quantum Fourier Transform"
        ]
    )

    if algorithm == "Bell State":

        st.subheader("🔗 Bell State")

        qc = QuantumCircuit(2)

        qc.h(0)
        qc.cx(0, 1)

        st.pyplot(draw_circuit(qc))

        counts = run_circuit(qc)

        st.write("Measurement:", counts)

        st.info(
            "Bell states demonstrate quantum entanglement."
        )

        complete_topic("Bell State")

    elif algorithm == "Grover Search":

        st.subheader("🔎 Grover Search")

        qc = QuantumCircuit(2)

        qc.h([0, 1])

        # Oracle for |11>
        qc.cz(0, 1)

        qc.h([0, 1])

        qc.x([0, 1])

        qc.h(1)

        qc.cx(0, 1)

        qc.h(1)

        qc.x([0, 1])

        qc.h([0, 1])

        st.pyplot(draw_circuit(qc))

        counts = run_circuit(qc)

        st.write("Measurement:", counts)

        st.info(
            "Grover's algorithm provides a quadratic speedup "
            "for unstructured search."
        )

    elif algorithm == "Deutsch-Jozsa":

        st.subheader("⚡ Deutsch-Jozsa")

        qc = QuantumCircuit(2)

        qc.x(1)
        qc.h([0, 1])

        qc.cx(0, 1)

        qc.h(0)

        st.pyplot(draw_circuit(qc))

        counts = run_circuit(qc)

        st.write("Measurement:", counts)

        st.info(
            "Deutsch-Jozsa demonstrates quantum advantage "
            "for determining properties of a function."
        )

    else:

        st.subheader("🌊 Quantum Fourier Transform")

        qc = QuantumCircuit(2)

        qc.h(0)
        qc.cp(np.pi / 2, 0, 1)
        qc.h(1)

        st.pyplot(draw_circuit(qc))

        counts = run_circuit(qc)

        st.write("Measurement:", counts)

        st.info(
            "QFT is an important building block in several quantum algorithms."
        )


# =========================================================
# VISUALIZATION
# =========================================================

elif page == "📊 Visualization":

    st.title("📊 Quantum State Visualization")

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
        probs = [1, 0]

    elif state == "|1⟩":
        probs = [0, 1]

    else:
        probs = [0.5, 0.5]

    st.subheader("Probability Distribution")

    fig, ax = plt.subplots()

    ax.bar(
        ["|0⟩", "|1⟩"],
        probs
    )

    ax.set_ylim(0, 1)
    ax.set_ylabel("Probability")
    ax.set_title(f"State {state}")

    st.pyplot(fig)

    st.subheader("Measurement Simulation")

    shots = st.slider(
        "Shots",
        100,
        5000,
        1000
    )

    results = np.random.choice(
        ["0", "1"],
        size=shots,
        p=probs
    )

    unique, counts = np.unique(
        results,
        return_counts=True
    )

    measurement_data = dict(
        zip(unique, counts)
    )

    st.write(measurement_data)

    # Simple Bloch sphere representation

    st.subheader("🌀 Bloch Sphere")

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
        np.ones(np.size(u)),
        np.cos(v)
    )

    ax2.plot_wireframe(
        x,
        y,
        z,
        alpha=0.15
    )

    if state == "|0⟩":
        point = [0, 0, 1]

    elif state == "|1⟩":
        point = [0, 0, -1]

    elif state == "|+⟩":
        point = [1, 0, 0]

    else:
        point = [-1, 0, 0]

    ax2.scatter(
        point[0],
        point[1],
        point[2],
        s=100
    )

    ax2.set_xlabel("X")
    ax2.set_ylabel("Y")
    ax2.set_zlabel("Z")

    st.pyplot(fig2)


# =========================================================
# QISKIT CODE EDITOR
# =========================================================

elif page == "💻 Qiskit Code Editor":

    st.title("💻 Qiskit Code Editor")

    st.write(
        "Write and execute your own Qiskit quantum program."
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

    if st.button("▶️ Run Qiskit Code"):

        output = {}

        try:

            exec(
                code,
                {
                    "__builtins__": __builtins__,
                    "QuantumCircuit": QuantumCircuit
                },
                output
            )

            st.success("Code executed successfully!")

            if "qc" in output:

                qc = output["qc"]

                st.pyplot(
                    draw_circuit(qc)
                )

                try:
                    counts = run_circuit(qc)
                    st.write(
                        "Measurement:",
                        counts
                    )
                except Exception as e:
                    st.warning(str(e))

            add_points(15)
            check_badges()

        except Exception as e:

            st.error("❌ Code Error")

            st.code(
                str(e)
            )

            st.info(
                "Use the 'Fix My Circuit' page for debugging suggestions."
            )


# =========================================================
# FIX MY CIRCUIT
# =========================================================

elif page == "🐛 Fix My Circuit":

    st.title("🐛 Fix My Circuit")

    st.write(
        "Enter your Qiskit code and get basic error analysis."
    )

    code = st.text_area(
        "Paste your Qiskit code",
        height=250
    )

    if st.button("🔧 Analyze Code"):

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
                    "Create a quantum circuit using QuantumCircuit()."
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
                    "Measurement is not present. Consider using qc.measure_all()."
                )

            if errors:

                st.error(
                    f"{len(errors)} possible issue(s) found:"
                )

                for error in errors:
                    st.write("🔴", error)

            else:

                st.success(
                    "No obvious structural errors detected."
                )

                st.info(
                    "Try running the code in the Qiskit Code Editor."
                )


# =========================================================
# AI TUTOR
# =========================================================

elif page == "🤖 AI Tutor":

    st.title("🤖 AI Quantum Tutor")

    st.write(
        "Ask questions about quantum computing."
    )

    question = st.text_input(
        "Ask your question"
    )

    if st.button("💡 Ask AI"):

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

        elif "hadamard" in q or "h gate" in q:

            answer = """
The Hadamard gate creates an equal superposition from |0⟩:

|0⟩ → (|0⟩ + |1⟩) / √2
"""

        elif "cnot" in q:

            answer = """
CNOT is a controlled-NOT gate.

If the control qubit is |1⟩, the target qubit is flipped.
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

        st.success(answer)


# =========================================================
# QUIZ
# =========================================================

elif page == "📝 Quiz":

    st.title("📝 Quantum Computing Quiz")

    questions = [
        (
            "What is the basic unit of quantum information?",
            ["Bit", "Qubit", "Byte", "Neuron"],
            "Qubit"
        ),

        (
            "Which gate creates superposition from |0⟩?",
            ["X", "Z", "H", "CNOT"],
            "H"
        ),

        (
            "Which gate is commonly used for two-qubit entanglement?",
            ["X", "CNOT", "Z", "RX"],
            "CNOT"
        ),

        (
            "What framework is used in this platform?",
            ["TensorFlow", "Qiskit", "OpenCV", "Pandas"],
            "Qiskit"
        ),

        (
            "Which algorithm provides a quadratic search speedup?",
            ["Grover", "Bubble Sort", "DFS", "Linear Search"],
            "Grover"
        )
    ]

    difficulty = st.selectbox(
        "Difficulty",
        ["Easy", "Medium", "Hard"]
    )

    score = 0

    for i, (question, options, answer) in enumerate(questions):

        selected = st.radio(
            f"{i + 1}. {question}",
            options,
            key=f"question_{i}"
        )

        if selected == answer:
            score += 1

    if st.button("📊 Submit Quiz"):

        st.session_state.quiz_score = score

        if score == len(questions):
            add_points(50)
            st.balloons()

        else:
            add_points(score * 5)

        check_badges()

        st.success(
            f"Your score: {score}/{len(questions)}"
        )

        st.write(
            f"Total points: {st.session_state.points}"
        )


# =========================================================
# PROGRESS
# =========================================================

elif page == "📈 Progress":

    st.title("📈 Learning Progress")

    total_topics = 8

    completed_topics = len(
        st.session_state.completed
    )

    progress = min(
        completed_topics / total_topics,
        1.0
    )

    st.progress(progress)

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

    st.subheader("Completed Topics")

    if st.session_state.completed:

        for topic in st.session_state.completed:
            st.write(
                "✅",
                topic
            )

    else:

        st.info(
            "Complete learning modules to see your progress."
        )

    st.subheader("🏅 Badges")

    if st.session_state.badges:

        for badge in st.session_state.badges:

            st.markdown(
                f"""
                <span class="badge">🏆 {badge}</span>
                """,
                unsafe_allow_html=True
            )

    else:

        st.info(
            "Earn badges by learning and completing quizzes."
        )


# =========================================================
# LEADERBOARD
# =========================================================

elif page == "🏆 Leaderboard":

    st.title("🏆 Quantum Learner Leaderboard")

    leaderboard = pd.DataFrame(
        {
            "Rank": [1, 2, 3, 4],
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

    leaderboard = leaderboard.sort_values(
        "Points",
        ascending=False
    ).reset_index(drop=True)

    leaderboard["Rank"] = range(
        1,
        len(leaderboard) + 1
    )

    st.dataframe(
        leaderboard,
        use_container_width=True
    )

    st.subheader("🏅 Your Badges")

    if st.session_state.badges:

        for badge in st.session_state.badges:
            st.write("🏆", badge)

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

