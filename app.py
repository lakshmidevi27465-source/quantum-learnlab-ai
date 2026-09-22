import streamlit as st
from google import genai
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import hashlib
import json
import time

from pathlib import Path
from supabase import create_client
from qiskit import QuantumCircuit, transpile
from qiskit_aer import AerSimulator

try:
    from streamlit_sortables import sort_items
    SORTABLES_AVAILABLE = True
except Exception:
    sort_items = None
    SORTABLES_AVAILABLE = False


# ============================================================
# PAGE CONFIG
# ============================================================

st.set_page_config(
    page_title="Quantum LearnLab AI",
    page_icon="⚛️",
    layout="wide"
)


# ============================================================
# EXISTING FIGURES / ASSETS
# ============================================================

ASSETS_DIR = Path("assets")
FIG_QUBIT = ASSETS_DIR / "fig1_qubit_superposition.png"
FIG_ENTANGLEMENT = ASSETS_DIR / "fig3_entanglement_teleportation.png"
FIG_CIRCUIT = ASSETS_DIR / "fig4_hadamard_cnot_circuit.png"


# ============================================================
# TOPICS
# ============================================================

TOPICS = [
    "Qubit",
    "Quantum Circuit",
    "Superposition",
    "Entanglement",
    "CNOT Gate",
    "Measurement",
    "Grover Search",
    "QFT"
]


# ============================================================
# SESSION STATE
# ============================================================

DEFAULT_SESSION_STATE = {
    "logged_in": False,
    "user": None,
    "profile": {},
    "page": "🏠 Home",

    "points": 0,
    "completed_topics": [],
    "badges": [],

    "workflow_stage": "ASK",
    "workflow_question": "",
    "workflow_topic": "",
    "workflow_explanation": "",
    "workflow_circuit": None,
    "workflow_simulation": None,
    "workflow_score": None,

    "quiz_score": 0,

    "circuit": QuantumCircuit(2),

    "ai_answer": "",

    "last_question": "",
    "gemini_last_error": ""
}


for key, value in DEFAULT_SESSION_STATE.items():

    if key not in st.session_state:

        if isinstance(value, list):
            st.session_state[key] = value.copy()

        elif isinstance(value, QuantumCircuit):
            st.session_state[key] = QuantumCircuit(2)

        else:
            st.session_state[key] = value


# ============================================================
# SUPABASE
# ============================================================

@st.cache_resource
def get_supabase():

    try:

        url = st.secrets.get("SUPABASE_URL", "")
        key = st.secrets.get("SUPABASE_KEY", "")

        if not url or not key:
            return None

        return create_client(url, key)

    except Exception:
        return None


def sign_in(email, password):

    supabase = get_supabase()

    if supabase is None:
        return False, "Supabase is not configured."

    try:

        response = supabase.auth.sign_in_with_password({
            "email": email,
            "password": password
        })

        user = response.user

        if user:

            st.session_state.logged_in = True
            st.session_state.user = user

            profile = load_profile(user.id)

            if profile:
                restore_profile(profile)

            return True, "Login successful."

        return False, "Invalid login."

    except Exception as e:

        return False, str(e)


def sign_up(name, email, password):

    supabase = get_supabase()

    if supabase is None:
        return False, "Supabase is not configured."

    try:

        response = supabase.auth.sign_up({
            "email": email,
            "password": password,
            "options": {
                "data": {
                    "full_name": name
                }
            }
        })

        if response.user:

            return True, (
                "Account created successfully. "
                "Please verify your email if confirmation is enabled."
            )

        return False, "Signup failed."

    except Exception as e:

        return False, str(e)


def logout():

    supabase = get_supabase()

    try:

        if supabase:
            supabase.auth.sign_out()

    except Exception:
        pass

    st.session_state.logged_in = False
    st.session_state.user = None
    st.session_state.profile = {}
    st.session_state.page = "🏠 Home"

    st.rerun()


# ============================================================
# PROFILE
# ============================================================

def load_profile(user_id):

    supabase = get_supabase()

    if supabase is None:
        return {}

    try:

        response = (
            supabase
            .table("profiles")
            .select("*")
            .eq("id", user_id)
            .execute()
        )

        if response.data:
            return response.data[0]

        return {}

    except Exception:
        return {}


def save_profile():

    supabase = get_supabase()

    user = st.session_state.user

    if supabase is None or user is None:
        return

    try:

        display_name = ""

        try:
            display_name = user.user_metadata.get("full_name", "")
        except Exception:
            pass

        data = {
            "id": user.id,
            "name": display_name,
            "points": int(st.session_state.points),
            "completed_topics": st.session_state.completed_topics,
            "badges": st.session_state.badges
        }

        supabase.table("profiles").upsert(data).execute()

    except Exception:
        pass


def restore_profile(profile):

    st.session_state.profile = profile or {}

    st.session_state.points = int(
        profile.get("points", 0)
    )

    st.session_state.completed_topics = (
        profile.get("completed_topics", [])
        or []
    )

    st.session_state.badges = (
        profile.get("badges", [])
        or []
    )


# ============================================================
# GEMINI CLIENT
# ============================================================

@st.cache_resource
def get_gemini_client():

    api_key = st.secrets.get("GEMINI_API_KEY", "")

    if not api_key:
        return None

    try:

        return genai.Client(
            api_key=api_key
        )

    except Exception:
        return None


# ============================================================
# GEMINI SAFE GENERATION
# ============================================================

def generate_gemini(prompt, attempts=3):

    client = get_gemini_client()

    if client is None:
        st.session_state.gemini_last_error = "Gemini client is not configured. Check GEMINI_API_KEY in Streamlit Secrets."
        return None

    last_error = "Unknown Gemini error."

    for attempt in range(attempts):

        try:

            response = client.models.generate_content(
                model="gemini-3.6-flash",
                contents=prompt
            )

            answer = getattr(response, "text", None)

            if answer:
                st.session_state.gemini_last_error = ""
                return answer.strip()

            last_error = "Gemini returned an empty response."

        except Exception as e:

            last_error = str(e)
            error_text = last_error.lower()

            is_temporary_error = (
                "503" in error_text
                or "unavailable" in error_text
                or "high demand" in error_text
                or "429" in error_text
                or "resource exhausted" in error_text
            )

            if is_temporary_error and attempt < attempts - 1:
                time.sleep(2 ** attempt)
                continue

            break

    st.session_state.gemini_last_error = last_error
    return None


# ============================================================
# LOCAL TOPIC DETECTION
# ============================================================

def local_topic_detection(question):

    q = question.lower()

    if "grover" in q:
        return "Grover Search"

    if "fourier" in q or "qft" in q:
        return "QFT"

    if "cnot" in q or "controlled not" in q:
        return "CNOT Gate"

    if "entangle" in q or "bell state" in q:
        return "Entanglement"

    if "superposition" in q or "hadamard" in q:
        return "Superposition"

    if "measure" in q or "measurement" in q:
        return "Measurement"

    if (
        "quantum circuit" in q
        or "quantum circuits" in q
        or "circuit" in q
    ):
        return "Quantum Circuit"

    if "qubit" in q:
        return "Qubit"

    return "General"


# ============================================================
# GEMINI QUESTION ANSWER
# ============================================================

def ask_gemini(question):

    prompt = f"""
You are an AI tutor inside an interactive quantum computing learning platform.

User question:
{question}

Explain the answer in simple technical English.

Requirements:
- Answer the user's actual question directly.
- Beginner friendly but technically correct.
- Use short sections and bullet points where useful.
- Give a simple example when appropriate.
- Do not replace the answer with a predefined topic explanation.
- Focus on quantum computing when the question is about quantum computing.
"""

    answer = generate_gemini(prompt)

    if answer:
        return answer

    error = st.session_state.get("gemini_last_error", "Gemini is temporarily unavailable.")
    return (
        "### ⚠️ Gemini is temporarily unavailable\n\n"
        f"The platform could not generate an AI answer right now.\n\n"
        f"**Error:** `{error}`\n\n"
        "Please try the same question again after a short time."
    )


# ============================================================
# WORKFLOW TOPIC DETECTION
# ============================================================

def workflow_topic_from_question(question):

    prompt = f"""
Classify this quantum computing question into exactly one
of the following topics:

Qubit
Quantum Circuit
Superposition
Entanglement
CNOT Gate
Measurement
Grover Search
QFT
General

Question:
{question}

Return ONLY the topic name.
"""

    result = generate_gemini(prompt)

    if result:

        result_lower = result.lower()

        for topic in TOPICS:

            if topic.lower() in result_lower:
                return topic

    # Gemini failed → local detection
    return local_topic_detection(question)


# ============================================================
# LOCAL EXPLANATIONS
# ============================================================

def workflow_explain(topic):

    explanations = {

        "Qubit": """
A qubit is the basic unit of quantum information.

A classical bit can be 0 or 1.
A qubit can exist in a quantum superposition of 0 and 1.

Example:
|ψ⟩ = α|0⟩ + β|1⟩
""",

        "Quantum Circuit": """
A quantum circuit is a sequence of quantum gates
applied to one or more qubits.

Main components:
- Qubits
- Quantum gates
- Measurement

Example:

H gate → Measurement

The Hadamard gate creates superposition before measurement.
""",

        "Superposition": """
Superposition means a qubit can exist in a combination
of |0⟩ and |1⟩ before measurement.

The Hadamard gate is commonly used to create
a superposition state.
""",

        "Entanglement": """
Quantum entanglement is a strong correlation between
quantum particles.

When two qubits are entangled, their measurement
results are correlated.

A Bell state can be created using:
H gate + CNOT gate.
""",

        "CNOT Gate": """
CNOT means Controlled-NOT.

It uses:
- One control qubit
- One target qubit

The target qubit flips when the control qubit is 1.
""",

        "Measurement": """
Measurement converts a quantum state into a classical
measurement result.

For a qubit in superposition, measurement produces
a probabilistic classical result.
""",

        "Grover Search": """
Grover's algorithm is a quantum search algorithm.

It provides a quadratic speedup for searching
an unstructured database.

For N possibilities, the idealized query complexity
is approximately O(√N).
""",

        "QFT": """
QFT means Quantum Fourier Transform.

It is the quantum version of the Fourier transform
and is an important component of several quantum algorithms.
""",

        "General": """
This is a general quantum computing question.

The platform can explain the concept using the AI tutor
and provide an introductory quantum circuit example.
"""
    }

    return explanations.get(
        topic,
        explanations["General"]
    )


# ============================================================
# BUILD QUANTUM CIRCUIT
# ============================================================

def workflow_build_circuit(topic):

    # ----------------------------------------
    # QUBIT
    # ----------------------------------------

    if topic == "Qubit":

        qc = QuantumCircuit(1, 1)

        qc.measure(0, 0)

        return qc

    # ----------------------------------------
    # QUANTUM CIRCUIT
    # ----------------------------------------

    if topic == "Quantum Circuit":

        qc = QuantumCircuit(1, 1)

        qc.h(0)

        qc.measure(0, 0)

        return qc

    # ----------------------------------------
    # SUPERPOSITION
    # ----------------------------------------

    if topic == "Superposition":

        qc = QuantumCircuit(1, 1)

        qc.h(0)

        qc.measure(0, 0)

        return qc

    # ----------------------------------------
    # ENTANGLEMENT
    # ----------------------------------------

    if topic == "Entanglement":

        qc = QuantumCircuit(2, 2)

        qc.h(0)

        qc.cx(0, 1)

        qc.measure(
            [0, 1],
            [0, 1]
        )

        return qc

    # ----------------------------------------
    # CNOT
    # ----------------------------------------

    if topic == "CNOT Gate":

        qc = QuantumCircuit(2, 2)

        qc.x(0)

        qc.cx(0, 1)

        qc.measure(
            [0, 1],
            [0, 1]
        )

        return qc

    # ----------------------------------------
    # MEASUREMENT
    # ----------------------------------------

    if topic == "Measurement":

        qc = QuantumCircuit(1, 1)

        qc.h(0)

        qc.measure(0, 0)

        return qc

    # ----------------------------------------
    # GROVER DEMO
    # ----------------------------------------

    if topic == "Grover Search":

        qc = QuantumCircuit(2, 2)

        qc.h(0)

        qc.h(1)

        qc.measure(
            [0, 1],
            [0, 1]
        )

        return qc

    # ----------------------------------------
    # QFT DEMO
    # ----------------------------------------

    if topic == "QFT":

        qc = QuantumCircuit(2, 2)

        qc.h(0)

        qc.cp(
            np.pi / 2,
            0,
            1
        )

        qc.h(1)

        qc.measure(
            [0, 1],
            [0, 1]
        )

        return qc

    # ----------------------------------------
    # GENERAL FALLBACK
    # ----------------------------------------

    qc = QuantumCircuit(1, 1)

    qc.h(0)

    qc.measure(0, 0)

    return qc


# ============================================================
# SIMULATE CIRCUIT
# ============================================================

def simulate_circuit(qc, shots=512):

    try:

        simulator = AerSimulator()

        compiled = transpile(
            qc,
            simulator
        )

        result = simulator.run(
            compiled,
            shots=shots
        ).result()

        counts = result.get_counts()

        return counts

    except Exception as e:

        st.error(
            f"Simulation error: {e}"
        )

        return None


# ============================================================
# CIRCUIT BUILDER
# ============================================================

def render_circuit_builder():

    st.title("🔧 Circuit Builder")
    st.write("Drag gates from the Gate Palette into the Circuit area. Reorder them to change the circuit sequence.")

    num_qubits = st.number_input("Number of qubits", min_value=1, max_value=8, value=2, step=1)
    shots = st.number_input("Shots", min_value=1, max_value=10000, value=512, step=1)

    if "drag_gate_sequence" not in st.session_state:
        st.session_state.drag_gate_sequence = []
    if "builder_counts" not in st.session_state:
        st.session_state.builder_counts = None

    gates = ["H", "X", "Y", "Z", "S", "T", "CNOT", "CZ", "SWAP"]

    if not SORTABLES_AVAILABLE:
        st.error("Drag-and-drop component is not installed. Add streamlit-sortables==0.3.1 to requirements.txt.")
        return

    result = sort_items(
        [
            {"header": "🧩 Gate Palette", "items": gates},
            {"header": "⚛️ Circuit — drag gates here", "items": st.session_state.drag_gate_sequence},
        ],
        multi_containers=True,
        direction="horizontal",
        key="quantum_gate_drag_drop",
    )

    if isinstance(result, list) and len(result) >= 2:
        circuit_items = result[1].get("items", []) if isinstance(result[1], dict) else []
        st.session_state.drag_gate_sequence = [g for g in circuit_items if g in gates]

    seq = st.session_state.drag_gate_sequence

    st.subheader("Current Gate Sequence")
    st.info(" → ".join(seq) if seq else "Drag gates into the circuit area to begin.")

    qc = QuantumCircuit(int(num_qubits), int(num_qubits))

    for gate in seq:
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
        elif int(num_qubits) >= 2:
            if gate == "CNOT":
                qc.cx(0, 1)
            elif gate == "CZ":
                qc.cz(0, 1)
            elif gate == "SWAP":
                qc.swap(0, 1)

    st.subheader("⚛️ Circuit Diagram")
    st.code(str(qc.draw(output="text")), language="text")

    explanations = {
        "H": "Creates superposition.",
        "X": "Flips |0⟩ and |1⟩.",
        "Y": "Performs a bit flip together with a phase change.",
        "Z": "Changes the phase of |1⟩.",
        "S": "Applies a π/2 phase shift.",
        "T": "Applies a π/4 phase shift.",
        "CNOT": "Flips the target qubit when the control qubit is |1⟩.",
        "CZ": "Applies a phase flip to the |11⟩ component.",
        "SWAP": "Exchanges the states of two qubits."
    }

    st.subheader("📘 Circuit Explanation")
    if seq:
        for i, gate in enumerate(seq, 1):
            st.write(f"**Step {i} — {gate}:** {explanations[gate]}")
    else:
        st.caption("No gates selected yet.")

    c1, c2 = st.columns(2)
    with c1:
        if st.button("▶️ Simulate Circuit", width="stretch"):
            st.session_state.builder_counts = simulate_circuit(qc, int(shots))
    with c2:
        if st.button("🗑️ Clear Circuit", width="stretch"):
            st.session_state.drag_gate_sequence = []
            st.session_state.builder_counts = None
            st.rerun()

    if st.session_state.builder_counts:
        st.subheader("📊 Simulation Result")
        st.json(st.session_state.builder_counts)


def render_fix_circuit():

    st.title("🛠️ Fix My Circuit")

    st.write(
        "Describe your circuit problem and the AI tutor "
        "will suggest a correction."
    )

    question = st.text_area(
        "What is wrong with your circuit?",
        placeholder=(
            "Example: My CNOT circuit is not producing "
            "the expected Bell state."
        )
    )

    if st.button(
        "🤖 Analyze Circuit",
        width="stretch"
    ):

        if not question.strip():

            st.warning(
                "Please enter a circuit problem."
            )

            return

        prompt = f"""
You are a quantum computing tutor.

Analyze this circuit problem:

{question}

Give:
1. Possible cause
2. Explanation
3. Correct approach
4. Simple Qiskit example
"""

        answer = generate_gemini(prompt)

        if answer:

            st.markdown(answer)

        else:

            st.info(
                "Gemini is temporarily unavailable. "
                "Please try again after a short time."
            )


# ============================================================
# AI TUTOR
# ============================================================

def render_ai_tutor():

    st.title("🤖 AI Tutor")

    question = st.text_area(
        "Ask any quantum computing question",
        placeholder=(
            "Example: What is the difference between "
            "a classical computer and a quantum computer?"
        ),
        height=150
    )

    if st.button(
        "Ask Gemini",
        width="stretch"
    ):

        if not question.strip():

            st.warning(
                "Please enter a question."
            )

            return

        answer = ask_gemini(question)

        st.session_state.ai_answer = answer

    if st.session_state.ai_answer:

        st.subheader("AI Answer")

        st.markdown(
            st.session_state.ai_answer
        )


# ============================================================
# VISUALIZATION
# ============================================================

def render_visualization():

    st.title("📊 Visualization")

    qc = st.session_state.get(
        "workflow_circuit"
    )

    counts = st.session_state.get(
        "workflow_simulation"
    )

    if qc is None:

        st.info(
            "Complete the workflow BUILD stage first."
        )

        return

    st.subheader("Quantum Circuit")

    st.code(
        str(qc.draw(output="text")),
        language="text"
    )

    if counts:

        st.subheader("Measurement Distribution")

        states = list(counts.keys())
        values = list(counts.values())

        fig, ax = plt.subplots()

        ax.bar(
            states,
            values
        )

        ax.set_xlabel(
            "Measured State"
        )

        ax.set_ylabel(
            "Counts"
        )

        ax.set_title(
            "Quantum Measurement Results"
        )

        st.pyplot(fig)

        plt.close(fig)


# ============================================================
# QUIZ
# ============================================================

QUIZ_DATA = [

    {
        "question": "What is the basic unit of quantum information?",
        "options": [
            "Bit",
            "Qubit",
            "Byte",
            "Register"
        ],
        "answer": "Qubit"
    },

    {
        "question": "Which gate is commonly used to create superposition?",
        "options": [
            "X",
            "Z",
            "H",
            "CX"
        ],
        "answer": "H"
    },

    {
        "question": "Which gate is used to create two-qubit entanglement?",
        "options": [
            "CNOT",
            "X",
            "Z",
            "T"
        ],
        "answer": "CNOT"
    },

    {
        "question": "What does QFT stand for?",
        "options": [
            "Quantum Fast Technology",
            "Quantum Fourier Transform",
            "Quantum Function Theory",
            "Quantum Frequency Tool"
        ],
        "answer": "Quantum Fourier Transform"
    },

    {
        "question": "What happens during quantum measurement?",
        "options": [
            "Quantum state becomes a classical result",
            "Qubit disappears",
            "Computer shuts down",
            "Nothing happens"
        ],
        "answer": "Quantum state becomes a classical result"
    }
]


def render_quiz():

    st.title("📝 Quantum Quiz")

    score = 0

    for i, item in enumerate(QUIZ_DATA):

        st.subheader(
            f"Q{i + 1}. {item['question']}"
        )

        answer = st.radio(
            "Select an answer:",
            item["options"],
            key=f"quiz_{i}"
        )

        if answer == item["answer"]:
            score += 1

    if st.button(
        "Submit Quiz",
        width="stretch"
    ):

        st.session_state.quiz_score = score

        earned = score * 10

        st.session_state.points += earned

        if score == len(QUIZ_DATA):

            if "Quantum Master" not in st.session_state.badges:

                st.session_state.badges.append(
                    "Quantum Master"
                )

        save_profile()

        st.success(
            f"Score: {score}/{len(QUIZ_DATA)}"
        )

        st.info(
            f"You earned {earned} points."
        )


# ============================================================
# LEARN
# ============================================================

def render_learn():

    st.title("📚 Learn Quantum Computing")

    topic = st.selectbox(
        "Choose a topic",
        TOPICS
    )

    st.markdown(
        workflow_explain(topic)
    )

    st.divider()

    if st.button(
        "Build Example Circuit",
        width="stretch"
    ):

        qc = workflow_build_circuit(
            topic
        )

        st.code(
            str(qc.draw(output="text")),
            language="text"
        )

        counts = simulate_circuit(
            qc,
            512
        )

        if counts:

            st.bar_chart(
                pd.DataFrame(
                    {
                        "State": list(counts.keys()),
                        "Count": list(counts.values())
                    }
                ).set_index("State")
            )


# ============================================================
# QUANTUM ALGORITHMS
# ============================================================

def render_algorithms():

    st.title("🧠 Quantum Algorithms")

    algorithm = st.selectbox(
        "Select algorithm",
        ["Grover Search", "QFT", "VQE", "QAOA"]
    )

    info = {
        "Grover Search": (
            "Grover's algorithm searches an unstructured space and ideally uses about O(√N) oracle queries.",
            "H → Oracle → Diffusion → Measurement",
            "The H gates create a search-space superposition. The oracle marks the target state, and the diffusion step amplifies its probability.",
            FIG_CIRCUIT
        ),
        "QFT": (
            "The Quantum Fourier Transform changes a quantum state into the Fourier basis and is used inside several quantum algorithms.",
            "H → Controlled Phase → H → SWAP → Measurement",
            "Hadamard gates create the Fourier components, controlled-phase operations add relative phase information, and SWAP reverses qubit order when required.",
            FIG_CIRCUIT
        ),
        "VQE": (
            "VQE is a hybrid quantum-classical algorithm used to estimate an objective such as molecular energy.",
            "Parameterized Ansatz → Measurement → Classical Optimizer",
            "The quantum circuit prepares a parameterized state. Measurements estimate the objective, and a classical optimizer updates the parameters.",
            FIG_ENTANGLEMENT
        ),
        "QAOA": (
            "QAOA is a hybrid quantum-classical method for approximate combinatorial optimization.",
            "Initial State → Cost Layer → Mixer → Measurement",
            "The cost layer encodes the optimization objective, the mixer explores candidate states, and a classical optimizer updates the circuit parameters.",
            FIG_CIRCUIT
        ),
    }

    explanation, flow, circuit_explanation, figure = info[algorithm]

    st.subheader("📖 Algorithm Explanation")
    st.write(explanation)

    if figure.exists():
        st.subheader("🖼️ Existing Figure")
        st.image(str(figure), width="stretch")

    st.subheader("🔗 Algorithm Flow")
    st.info(flow)

    if algorithm == "Grover Search":
        qc = QuantumCircuit(2, 2)
        qc.h([0, 1])
        qc.cz(0, 1)
        qc.h([0, 1])
        qc.measure([0, 1], [0, 1])
    elif algorithm == "QFT":
        qc = QuantumCircuit(2, 2)
        qc.h(0)
        qc.cp(np.pi / 2, 0, 1)
        qc.h(1)
        qc.swap(0, 1)
        qc.measure([0, 1], [0, 1])
    elif algorithm == "VQE":
        qc = QuantumCircuit(2, 2)
        qc.ry(np.pi / 4, 0)
        qc.cx(0, 1)
        qc.measure([0, 1], [0, 1])
    else:
        qc = QuantumCircuit(2, 2)
        qc.h([0, 1])
        qc.rzz(np.pi / 4, 0, 1)
        qc.rx(np.pi / 4, 0)
        qc.rx(np.pi / 4, 1)
        qc.measure([0, 1], [0, 1])

    st.subheader("⚛️ Circuit")
    st.code(str(qc.draw(output="text")), language="text")

    st.subheader("🧩 Circuit Explanation")
    st.write(circuit_explanation)

    if st.button("▶️ Simulate Algorithm Circuit", width="stretch", key=f"algo_sim_{algorithm}"):
        counts = simulate_circuit(qc, 512)
        if counts:
            st.subheader("📊 Simulation Result")
            st.json(counts)


def render_code_editor():

    st.title("💻 Qiskit Code Editor")

    default_code = """from qiskit import QuantumCircuit

qc = QuantumCircuit(2)

qc.h(0)
qc.cx(0, 1)

print(qc.draw())
"""

    code = st.text_area(
        "Write Qiskit code",
        value=default_code,
        height=300
    )

    if st.button(
        "▶️ Run Code",
        width="stretch"
    ):

        st.code(
            code,
            language="python"
        )

        st.info(
            "For security, this platform does not execute "
            "arbitrary Python code directly. Use the Circuit "
            "Builder or supported simulation workflow."
        )


# ============================================================
# LEARNING WORKFLOW
# ============================================================

def render_workflow():

    st.title(
        "🔄 Interactive Quantum Learning Workflow"
    )

    stages = [
        "ASK",
        "EXPLAIN",
        "BUILD",
        "SIMULATE",
        "VISUALIZE",
        "ASSESS / ADAPT",
        "NEXT LEARNING PATH"
    ]

    current_stage = st.session_state.workflow_stage

    st.progress(
        (
            stages.index(current_stage) + 1
        ) / len(stages)
    )

    st.write(
        " → ".join(stages)
    )

    st.divider()

    # ========================================================
    # ASK
    # ========================================================

    if current_stage == "ASK":

        st.subheader(
            "1️⃣ ASK"
        )

        question = st.text_area(
            "Ask a quantum computing question",
            placeholder=(
                "Example: What is a quantum circuit?"
            ),
            height=120
        )

        if st.button(
            "Ask",
            width="stretch"
        ):

            if not question.strip():

                st.warning(
                    "Please enter a question."
                )

            else:

                topic = workflow_topic_from_question(
                    question
                )

                answer = ask_gemini(
                    question
                )

                st.session_state.workflow_question = (
                    question
                )

                st.session_state.workflow_topic = (
                    topic
                )

                st.session_state.workflow_explanation = (
                    answer
                )

                st.session_state.last_question = (
                    question
                )

                st.session_state.workflow_stage = (
                    "EXPLAIN"
                )

                st.rerun()

    # ========================================================
    # EXPLAIN
    # ========================================================

    elif current_stage == "EXPLAIN":

        st.subheader(
            "2️⃣ EXPLAIN"
        )

        topic = st.session_state.workflow_topic

        st.info(
            f"Detected Topic: {topic}"
        )

        st.markdown(
            st.session_state.workflow_explanation
        )

        st.divider()

        st.subheader(
            "Topic Explanation"
        )

        st.markdown(
            workflow_explain(topic)
        )

        if st.button(
            "Continue to BUILD →",
            width="stretch"
        ):

            qc = workflow_build_circuit(
                topic
            )

            st.session_state.workflow_circuit = qc

            st.session_state.workflow_stage = (
                "BUILD"
            )

            st.rerun()

    # ========================================================
    # BUILD
    # ========================================================

    elif current_stage == "BUILD":

        st.subheader(
            "3️⃣ BUILD"
        )

        qc = st.session_state.workflow_circuit

        if qc is None:

            qc = workflow_build_circuit(
                st.session_state.workflow_topic
            )

            st.session_state.workflow_circuit = qc

        st.code(
            str(qc.draw(output="text")),
            language="text"
        )

        st.write(
            "The platform generated an example circuit "
            "based on the detected topic."
        )

        if st.button(
            "Continue to SIMULATE →",
            width="stretch"
        ):

            st.session_state.workflow_stage = (
                "SIMULATE"
            )

            st.rerun()

    # ========================================================
    # SIMULATE
    # ========================================================

    elif current_stage == "SIMULATE":

        st.subheader(
            "4️⃣ SIMULATE"
        )

        qc = st.session_state.workflow_circuit

        if qc is None:

            st.error(
                "No circuit available."
            )

            return

        shots = st.slider(
            "Number of shots",
            min_value=100,
            max_value=2000,
            value=512,
            step=100
        )

        if st.button(
            "▶️ Run Simulation",
            width="stretch"
        ):

            counts = simulate_circuit(
                qc,
                shots
            )

            st.session_state.workflow_simulation = (
                counts
            )

            if counts:

                st.success(
                    "Simulation completed."
                )

                st.json(
                    counts
                )

        if st.session_state.workflow_simulation:

            if st.button(
                "Continue to VISUALIZE →",
                width="stretch"
            ):

                st.session_state.workflow_stage = (
                    "VISUALIZE"
                )

                st.rerun()

    # ========================================================
    # VISUALIZE
    # ========================================================

    elif current_stage == "VISUALIZE":

        st.subheader(
            "5️⃣ VISUALIZE"
        )

        qc = st.session_state.workflow_circuit

        counts = st.session_state.workflow_simulation

        st.code(
            str(qc.draw(output="text")),
            language="text"
        )

        if counts:

            fig, ax = plt.subplots()

            ax.bar(
                list(counts.keys()),
                list(counts.values())
            )

            ax.set_xlabel(
                "Measured State"
            )

            ax.set_ylabel(
                "Counts"
            )

            ax.set_title(
                "Quantum Measurement Distribution"
            )

            st.pyplot(fig)

            plt.close(fig)

        if st.button(
            "Continue to ASSESS / ADAPT →",
            width="stretch"
        ):

            st.session_state.workflow_stage = (
                "ASSESS / ADAPT"
            )

            st.rerun()

    # ========================================================
    # ASSESS / ADAPT
    # ========================================================

    elif current_stage == "ASSESS / ADAPT":

        st.subheader(
            "6️⃣ ASSESS / ADAPT"
        )

        topic = st.session_state.workflow_topic

        questions = {

            "Qubit": {
                "question": "What is the basic unit of quantum information?",
                "options": ["Bit", "Qubit", "Byte", "CPU"],
                "answer": "Qubit"
            },

            "Quantum Circuit": {
                "question": "What is a quantum circuit?",
                "options": [
                    "A sequence of quantum operations",
                    "A classical database",
                    "A computer memory",
                    "A compiler"
                ],
                "answer": "A sequence of quantum operations"
            },

            "Superposition": {
                "question": "Which gate commonly creates superposition?",
                "options": [
                    "X",
                    "H",
                    "Z",
                    "CNOT"
                ],
                "answer": "H"
            },

            "Entanglement": {
                "question": "Which combination can create a Bell state?",
                "options": [
                    "H + CNOT",
                    "X + X",
                    "Z + Z",
                    "H + X"
                ],
                "answer": "H + CNOT"
            },

            "CNOT Gate": {
                "question": "What does CNOT use?",
                "options": [
                    "Control and target qubits",
                    "Only one qubit",
                    "Only classical bits",
                    "No qubits"
                ],
                "answer": "Control and target qubits"
            },

            "Measurement": {
                "question": "Measurement produces what?",
                "options": [
                    "Classical result",
                    "New qubit",
                    "New gate",
                    "Nothing"
                ],
                "answer": "Classical result"
            },

            "Grover Search": {
                "question": "What is Grover's approximate query complexity?",
                "options": [
                    "O(N)",
                    "O(√N)",
                    "O(N²)",
                    "O(log N)"
                ],
                "answer": "O(√N)"
            },

            "QFT": {
                "question": "What does QFT stand for?",
                "options": [
                    "Quantum Fourier Transform",
                    "Quantum Fast Transfer",
                    "Quantum Function Table",
                    "Quantum Frequency Theory"
                ],
                "answer": "Quantum Fourier Transform"
            }
        }

        qdata = questions.get(
            topic,
            questions["Quantum Circuit"]
        )

        answer = st.radio(
            qdata["question"],
            qdata["options"],
            key="workflow_assessment"
        )

        if st.button(
            "Submit Assessment",
            width="stretch"
        ):

            if answer == qdata["answer"]:

                score = 100

                st.success(
                    "Correct! 🎉"
                )

                st.session_state.points += 20

                if topic not in st.session_state.completed_topics:

                    st.session_state.completed_topics.append(
                        topic
                    )

            else:

                score = 0

                st.error(
                    f"Correct answer: {qdata['answer']}"
                )

            st.session_state.workflow_score = score

            save_profile()

        if st.session_state.workflow_score is not None:

            if st.session_state.workflow_score >= 70:

                st.info(
                    "Good performance. You can move "
                    "to the next learning topic."
                )

            else:

                st.warning(
                    "Review this topic once more "
                    "before moving ahead."
                )

            if st.button(
                "Continue to NEXT LEARNING PATH →",
                width="stretch"
            ):

                st.session_state.workflow_stage = (
                    "NEXT LEARNING PATH"
                )

                st.rerun()

    # ========================================================
    # NEXT LEARNING PATH
    # ========================================================

    elif current_stage == "NEXT LEARNING PATH":

        st.subheader(
            "7️⃣ NEXT LEARNING PATH"
        )

        current_topic = (
            st.session_state.workflow_topic
        )

        topic_index = (
            TOPICS.index(current_topic)
            if current_topic in TOPICS
            else 0
        )

        next_topic = TOPICS[
            (topic_index + 1) % len(TOPICS)
        ]

        score = (
            st.session_state.workflow_score
            or 0
        )

        if score >= 70:

            st.success(
                f"Recommended next topic: {next_topic}"
            )

        else:

            st.warning(
                f"Recommended action: Review {current_topic} "
                f"before moving to {next_topic}."
            )

        st.write(
            "The platform adapts the next learning topic "
            "based on the learner's assessment."
        )

        if st.button(
            "Start New Question",
            width="stretch"
        ):

            st.session_state.workflow_stage = "ASK"

            st.session_state.workflow_question = ""

            st.session_state.workflow_topic = ""

            st.session_state.workflow_explanation = ""

            st.session_state.workflow_circuit = None

            st.session_state.workflow_simulation = None

            st.session_state.workflow_score = None

            st.rerun()


# ============================================================
# HOME
# ============================================================

def render_home():

    st.title(
        "⚛️ Quantum LearnLab AI"
    )

    user = st.session_state.user

    display_name = ""

    if user:

        try:

            display_name = (
                user.user_metadata.get(
                    "full_name",
                    ""
                )
            )

        except Exception:
            display_name = ""

        if not display_name:
            display_name = user.email

    st.success(
        f"Welcome, {display_name} 👋"
    )

    st.markdown(
        """
### AI-Powered Interactive Quantum Learning Platform

Learn quantum computing through:

**ASK → EXPLAIN → BUILD → SIMULATE → VISUALIZE → ASSESS / ADAPT → NEXT LEARNING PATH**
"""
    )

    st.divider()

    col1, col2, col3 = st.columns(3)

    with col1:

        st.metric(
            "Points",
            st.session_state.points
        )

    with col2:

        st.metric(
            "Topics Completed",
            len(
                st.session_state.completed_topics
            )
        )

    with col3:

        st.metric(
            "Badges",
            len(
                st.session_state.badges
            )
        )

    st.divider()

    st.subheader(
        "Available Learning Topics"
    )

    st.write(
        ", ".join(TOPICS)
    )

    st.info(
        "Gemini 3.6 Flash powers the AI tutor. "
        "If Gemini is temporarily unavailable, "
        "the platform uses local fallback explanations "
        "and circuit generation."
    )


# ============================================================
# PROGRESS
# ============================================================

def render_progress():

    st.title(
        "📈 My Progress"
    )

    st.metric(
        "Total Points",
        st.session_state.points
    )

    st.metric(
        "Completed Topics",
        len(
            st.session_state.completed_topics
        )
    )

    st.subheader(
        "Completed Topics"
    )

    if st.session_state.completed_topics:

        for topic in st.session_state.completed_topics:

            st.success(
                f"✅ {topic}"
            )

    else:

        st.info(
            "No topics completed yet."
        )

    st.subheader(
        "Badges"
    )

    if st.session_state.badges:

        for badge in st.session_state.badges:

            st.write(
                f"🏅 {badge}"
            )

    else:

        st.info(
            "Complete quizzes to earn badges."
        )


# ============================================================
# LEADERBOARD
# ============================================================

def render_leaderboard():

    st.title(
        "🏆 Leaderboard"
    )

    st.info(
        "Leaderboard data can be extended using a "
        "Supabase leaderboard table."
    )

    st.write(
        f"Your current points: "
        f"**{st.session_state.points}**"
    )


# ============================================================
# LOGIN / SIGNUP
# ============================================================

def render_auth():

    st.title(
        "⚛️ Quantum LearnLab AI"
    )

    st.write(
        "AI-powered interactive quantum learning platform."
    )

    login_tab, signup_tab = st.tabs(
        [
            "🔐 Login",
            "📝 Signup"
        ]
    )

    # ========================================================
    # LOGIN
    # ========================================================

    with login_tab:

        email = st.text_input(
            "Email",
            key="login_email"
        )

        password = st.text_input(
            "Password",
            type="password",
            key="login_password"
        )

        if st.button(
            "Login",
            width="stretch"
        ):

            if not email or not password:

                st.warning(
                    "Please enter email and password."
                )

            else:

                success, message = sign_in(
                    email,
                    password
                )

                if success:

                    st.success(
                        message
                    )

                    time.sleep(0.5)

                    st.rerun()

                else:

                    st.error(
                        message
                    )

    # ========================================================
    # SIGNUP
    # ========================================================

    with signup_tab:

        name = st.text_input(
            "Name",
            key="signup_name"
        )

        email = st.text_input(
            "Email",
            key="signup_email"
        )

        password = st.text_input(
            "Password",
            type="password",
            key="signup_password"
        )

        confirm_password = st.text_input(
            "Confirm Password",
            type="password",
            key="signup_confirm_password"
        )

        if st.button(
            "Create Account",
            width="stretch"
        ):

            if not name or not email or not password:

                st.warning(
                    "Please fill all fields."
                )

            elif password != confirm_password:

                st.error(
                    "Passwords do not match."
                )

            elif len(password) < 6:

                st.error(
                    "Password should contain at least 6 characters."
                )

            else:

                success, message = sign_up(
                    name,
                    email,
                    password
                )

                if success:

                    st.success(
                        message
                    )

                else:

                    st.error(
                        message
                    )


# ============================================================
# SIDEBAR
# ============================================================

def render_sidebar():

    with st.sidebar:

        st.title(
            "⚛️ Quantum LearnLab"
        )

        st.caption(
            "AI-Powered Quantum Learning"
        )

        st.divider()

        pages = [
            "🏠 Home",
            "🔄 Learning Workflow",
            "📚 Learn",
            "📖 Gate Learning",
            "🔧 Circuit Builder",
            "🧠 Quantum Algorithms",
            "📊 Visualization",
            "💻 Qiskit Code Editor",
            "🛠️ Fix My Circuit",
            "🤖 AI Tutor",
            "📝 Quiz",
            "📈 Progress",
            "🏆 Leaderboard"
        ]

        selected = st.radio(
            "Navigation",
            pages,
            index=pages.index(
                st.session_state.page
            )
            if st.session_state.page in pages
            else 0
        )

        st.session_state.page = selected

        st.divider()

        st.write(
            f"⭐ Points: {st.session_state.points}"
        )

        if st.button(
            "🚪 Logout",
            width="stretch"
        ):

            logout()


# ============================================================
# MAIN APPLICATION
# ============================================================

if not st.session_state.logged_in:

    render_auth()

else:

    render_sidebar()

    page = st.session_state.page

    if page == "🏠 Home":

        render_home()

    elif page == "🔄 Learning Workflow":

        render_workflow()

    elif page == "📚 Learn":

        render_learn()

    elif page == "🔧 Circuit Builder":

        render_circuit_builder()

    elif page == "🧠 Quantum Algorithms":

        render_algorithms()

    elif page == "📊 Visualization":

        render_visualization()

    elif page == "💻 Qiskit Code Editor":

        render_code_editor()

    elif page == "🛠️ Fix My Circuit":

        render_fix_circuit()

    elif page == "🤖 AI Tutor":

        render_ai_tutor()

    elif page == "📝 Quiz":

        render_quiz()

    elif page == "📈 Progress":

        render_progress()

    elif page == "🏆 Leaderboard":

        render_leaderboard()
