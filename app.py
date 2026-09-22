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

    "last_question": ""
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
        return None

    for attempt in range(attempts):

        try:

            response = client.models.generate_content(
                model="gemini-3.6-flash",
                contents=prompt
            )

            answer = getattr(
                response,
                "text",
                None
            )

            if answer:
                return answer.strip()

        except Exception as e:

            error_text = str(e)

            is_temporary_error = (
                "503" in error_text
                or
                "UNAVAILABLE" in error_text
                or
                "high demand" in error_text.lower()
            )

            if is_temporary_error:

                if attempt < attempts - 1:

                    wait_time = 2 ** attempt

                    time.sleep(wait_time)

                    continue

            return None

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
# LOCAL QUESTION ANSWER FALLBACK
# ============================================================
def local_question_answer(question):
    """Useful offline answers when Gemini is temporarily unavailable."""
    q = question.lower().strip()

    if "quantum circuit" in q or "what is a quantum circuit" in q:
        return """### What is a Quantum Circuit?

A **quantum circuit** is a sequence of quantum operations applied to one or more qubits to perform a quantum computation.

**Main components:**
- **Qubits** – store quantum information.
- **Quantum gates** – change qubit states, such as H, X, Z and CNOT.
- **Measurement** – converts the final quantum state into a classical result.

**Simple example:** A Hadamard (H) gate puts a qubit into superposition, and measurement gives a probabilistic 0 or 1 result.

```text
q0: ──H──M──
```
"""
    if "qubit" in q and ("what is" in q or "explain" in q or "meaning" in q):
        return """### What is a Qubit?

A **qubit** is the basic unit of quantum information. A qubit can be in a superposition of the basis states |0⟩ and |1⟩.

**|ψ⟩ = α|0⟩ + β|1⟩**
"""
    if "superposition" in q:
        return """### What is Superposition?

**Superposition** means a qubit can be in a combination of |0⟩ and |1⟩ before measurement.

The Hadamard gate can create an equal superposition:
**|0⟩ → (|0⟩ + |1⟩)/√2**.
"""
    if "entanglement" in q or "entangled" in q:
        return """### What is Quantum Entanglement?

**Quantum entanglement** is a quantum correlation between two or more qubits where their joint state cannot be described as independent states.

A common Bell-state circuit uses **H + CNOT**.
"""
    if "cnot" in q or "controlled not" in q:
        return """### What is a CNOT Gate?

**CNOT (Controlled-NOT)** is a two-qubit gate. The target qubit flips when the control qubit is |1⟩.

Example: **|10⟩ → |11⟩**.
"""
    if "measurement" in q or "measure" in q:
        return """### What is Quantum Measurement?

Measurement reads a quantum state and produces a classical result. For a qubit in superposition, repeated measurements reveal a probability distribution.
"""
    if "hadamard" in q or " h gate" in q or q.startswith("h gate"):
        return """### What is the Hadamard Gate?

The **Hadamard (H) gate** creates superposition. For example:
**|0⟩ → (|0⟩ + |1⟩)/√2**.
"""
    if "grover" in q:
        return """### What is Grover's Algorithm?

Grover's algorithm is a quantum search algorithm for unstructured search problems. Its idealized query complexity is approximately **O(√N)**.
"""
    if "qft" in q or "quantum fourier transform" in q:
        return """### What is QFT?

**QFT (Quantum Fourier Transform)** is the quantum analogue of the discrete Fourier transform and is used as a component of several quantum algorithms.
"""
    if "classical computer" in q and "quantum computer" in q:
        return """### Classical Computer vs Quantum Computer

Classical computers use bits, while quantum computers use qubits and quantum operations such as superposition, interference and entanglement. Quantum computers are not automatically faster for every problem; the advantage depends on the algorithm and problem structure.
"""

    topic = local_topic_detection(question)
    if topic != "General":
        return workflow_explain(topic)

    return """### AI Tutor

Gemini is temporarily unavailable for this question. Please try again in a moment. The platform will return a direct AI answer when the service is available.
"""


# ============================================================
# GEMINI QUESTION ANSWER
# ============================================================

def ask_gemini(question):

    prompt = f"""
You are an AI tutor inside an interactive quantum computing
learning platform.

User question:
{question}

Explain the answer in simple technical English.

Requirements:
- Beginner friendly
- Technically correct
- Use short sections
- Use bullet points where useful
- Give a simple example
- Focus on quantum computing
"""

    answer = generate_gemini(prompt)

    if answer:
        return answer

    # Gemini unavailable → answer the actual question locally
    return local_question_answer(question)


# ============================================================
# WORKFLOW TOPIC DETECTION
# ============================================================

def workflow_topic_from_question(question):

    # Detect common topics locally first so valid questions are not
    # incorrectly labeled General during a Gemini outage.
    local_topic = local_topic_detection(question)
    if local_topic != "General":
        return local_topic

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

    return "General"


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

def build_drag_drop_circuit(num_qubits, gate_sequence):

    qc = QuantumCircuit(num_qubits, num_qubits)

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
        elif gate == "CNOT":
            if num_qubits >= 2:
                qc.cx(0, 1)
        elif gate == "CZ":
            if num_qubits >= 2:
                qc.cz(0, 1)
        elif gate == "SWAP":
            if num_qubits >= 2:
                qc.swap(0, 1)

    qc.measure(range(num_qubits), range(num_qubits))
    return qc


def render_circuit_builder():

    st.title("🔧 Circuit Builder")
    st.write("Build a quantum circuit by dragging gates into the circuit area.")

    col1, col2 = st.columns(2)
    with col1:
        num_qubits = st.number_input("Number of qubits", min_value=1, max_value=8, value=2, step=1)
    with col2:
        shots = st.number_input("Shots", min_value=1, max_value=10000, value=512, step=1)

    if "drag_gate_sequence" not in st.session_state:
        st.session_state.drag_gate_sequence = []

    if "builder_counts" not in st.session_state:
        st.session_state.builder_counts = None

    if not SORTABLES_AVAILABLE:
        st.error("Drag-and-drop support requires streamlit-sortables. Add streamlit-sortables to requirements.txt.")
        return

    st.subheader("Drag Gates → Circuit")

    available_gates = ["H", "X", "Y", "Z", "S", "T", "CNOT", "CZ", "SWAP"]
    current = st.session_state.drag_gate_sequence

    containers = [
        {"header": "🧩 Gate Palette", "items": available_gates},
        {"header": "⚛️ Circuit — drag gates here", "items": current}
    ]

    custom_style = """
    .sortable-component { border-radius: 12px; }
    .sortable-container { min-height: 90px; }
    .sortable-item { font-weight: 700; border-radius: 8px; margin: 5px; }
    """

    result = sort_items(
        containers,
        multi_containers=True,
        direction="horizontal",
        custom_style=custom_style,
        key="quantum_drag_drop_builder"
    )

    if isinstance(result, list) and len(result) == 2:
        circuit_items = result[1].get("items", [])
        # Palette items are intentionally ignored; only items dropped into
        # the Circuit container become operations.
        st.session_state.drag_gate_sequence = [
            item for item in circuit_items if item in available_gates
        ]

    gate_sequence = st.session_state.drag_gate_sequence

    st.subheader("Current Circuit")
    if gate_sequence:
        st.write(" → ".join(gate_sequence))
    else:
        st.info("Drag gates from the Gate Palette into the Circuit area.")

    qc = build_drag_drop_circuit(num_qubits, gate_sequence)

    st.code(str(qc.draw(output="text")), language="text")

    st.subheader("Circuit Explanation")
    if not gate_sequence:
        st.write("Add gates to see how the circuit works.")
    else:
        explanations = {
            "H": "H creates an equal superposition of |0⟩ and |1⟩.",
            "X": "X flips the qubit: |0⟩ ↔ |1⟩.",
            "Y": "Y performs a bit flip together with a phase change.",
            "Z": "Z changes the phase of |1⟩ without changing measurement probabilities.",
            "S": "S applies a phase shift of π/2.",
            "T": "T applies a phase shift of π/4.",
            "CNOT": "CNOT uses qubit 0 as control and flips qubit 1 when the control is 1.",
            "CZ": "CZ applies a phase flip to |11⟩ when both qubits are 1.",
            "SWAP": "SWAP exchanges the quantum states of qubit 0 and qubit 1."
        }
        for i, gate in enumerate(gate_sequence, 1):
            st.write(f"**Step {i} — {gate}:** {explanations[gate]}")

    col1, col2, col3 = st.columns(3)
    with col1:
        if st.button("▶️ Simulate", use_container_width=True):
            counts = simulate_circuit(qc, shots)
            if counts:
                st.session_state.builder_counts = counts
    with col2:
        if st.button("🗑️ Clear Circuit", use_container_width=True):
            st.session_state.drag_gate_sequence = []
            st.session_state.builder_counts = None
            st.rerun()
    with col3:
        if st.button("↩️ Remove Last", use_container_width=True):
            if st.session_state.drag_gate_sequence:
                st.session_state.drag_gate_sequence.pop()
                st.session_state.builder_counts = None
                st.rerun()

    counts = st.session_state.builder_counts
    if counts:
        st.subheader("Measurement Results")
        st.json(counts)


# ============================================================
# QUANTUM ALGORITHMS
# ============================================================

def render_algorithms():

    st.title("🧠 Quantum Algorithms")
    st.write("Your algorithm learning section is kept with explanation, circuit and circuit explanation.")

    algorithm = st.selectbox(
        "Select algorithm",
        ["Grover Search", "QFT", "VQE", "QAOA"]
    )

    algorithm_data = {
        "Grover Search": {
            "explanation": "Grover's algorithm searches an unstructured search space with approximately O(√N) oracle queries.",
            "circuit": "H → Oracle → Diffusion → Measurement",
            "circuit_explanation": "Hadamard gates create the initial superposition. The Oracle marks the target state, and the diffusion operation amplifies its probability. Measurement returns the searched state.",
            "qc": None
        },
        "QFT": {
            "explanation": "Quantum Fourier Transform transforms amplitudes into the Fourier basis and is used in several quantum algorithms.",
            "circuit": "H → Controlled Phase → H → SWAP",
            "circuit_explanation": "Hadamard and controlled-phase operations build the Fourier-basis transformation. SWAP operations reverse the qubit order when required.",
            "qc": None
        },
        "VQE": {
            "explanation": "VQE is a hybrid quantum-classical algorithm that uses a parameterized circuit and a classical optimizer to estimate an objective such as molecular energy.",
            "circuit": "Parameterized Ansatz → Measurement → Classical Optimizer",
            "circuit_explanation": "The ansatz prepares a parameterized quantum state. Measurements estimate the objective function, and a classical optimizer updates the circuit parameters.",
            "qc": None
        },
        "QAOA": {
            "explanation": "QAOA is a hybrid quantum-classical algorithm for approximate combinatorial optimization.",
            "circuit": "Initial State → Cost Hamiltonian → Mixer → Measurement",
            "circuit_explanation": "The cost layer encodes the optimization problem, while the mixer explores candidate states. Repeated parameter optimization improves the measured objective.",
            "qc": None
        }
    }

    data = algorithm_data[algorithm]

    # Existing user-added figures should remain above/below this section in
    # the user's original file. This block does not replace them with a new image.
    st.markdown("### Algorithm Explanation")
    st.markdown(data["explanation"])

    st.divider()
    st.subheader("Quantum Circuit")
    st.code(data["circuit"], language="text")

    st.subheader("Circuit Explanation")
    st.info(data["circuit_explanation"])

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
        qc.measure([0, 1], [0, 1])

    st.subheader("Executable Circuit Example")
    st.code(str(qc.draw(output="text")), language="text")

    if st.button("▶️ Simulate Algorithm Circuit", use_container_width=True, key=f"simulate_algorithm_{algorithm}"):
        counts = simulate_circuit(qc, 512)
        if counts:
            st.subheader("Simulation Result")
            st.json(counts)


# ============================================================
# QISKIT CODE EDITOR
# ============================================================

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
        use_container_width=True
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
            use_container_width=True
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

        st.subheader("Your Question")
        st.write(st.session_state.workflow_question)
        st.caption("The answer above is for your actual question. The detected topic is used to select the related circuit.")

        if st.button(
            "Continue to BUILD →",
            use_container_width=True
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
            use_container_width=True
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
            use_container_width=True
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
                use_container_width=True
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
            use_container_width=True
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
            use_container_width=True
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
                use_container_width=True
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
            use_container_width=True
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
            use_container_width=True
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
            use_container_width=True
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
# GATE LEARNING
# ============================================================

GATE_INFO = {
    "H": {"name":"Hadamard Gate","description":"Creates superposition from computational-basis states.","matrix":"1/√2 × [[1, 1], [1, -1]]","input_output":"|0⟩ → |+⟩\n|1⟩ → |-⟩","use":"Creates superposition.","qubits":1},
    "X": {"name":"Pauli-X Gate","description":"Flips |0⟩ to |1⟩ and |1⟩ to |0⟩.","matrix":"[[0, 1], [1, 0]]","input_output":"|0⟩ → |1⟩\n|1⟩ → |0⟩","use":"Bit flip / NOT operation.","qubits":1},
    "Y": {"name":"Pauli-Y Gate","description":"Performs a bit flip together with a phase change.","matrix":"[[0, -i], [i, 0]]","input_output":"|0⟩ → i|1⟩\n|1⟩ → -i|0⟩","use":"Rotation around the Y axis.","qubits":1},
    "Z": {"name":"Pauli-Z Gate","description":"Leaves |0⟩ unchanged and applies a phase flip to |1⟩.","matrix":"[[1, 0], [0, -1]]","input_output":"|0⟩ → |0⟩\n|1⟩ → -|1⟩","use":"Phase flip.","qubits":1},
    "S": {"name":"S Gate","description":"Applies a π/2 phase rotation to the |1⟩ component.","matrix":"[[1, 0], [0, i]]","input_output":"|0⟩ → |0⟩\n|1⟩ → i|1⟩","use":"Phase rotation.","qubits":1},
    "T": {"name":"T Gate","description":"Applies a π/4 phase rotation to the |1⟩ component.","matrix":"[[1, 0], [0, e^(iπ/4)]]","input_output":"|0⟩ → |0⟩\n|1⟩ → e^(iπ/4)|1⟩","use":"Fine phase control.","qubits":1},
    "CNOT": {"name":"Controlled-NOT Gate","description":"Flips the target only when the control qubit is |1⟩.","matrix":"[[1,0,0,0],[0,1,0,0],[0,0,0,1],[0,0,1,0]]","input_output":"|00⟩ → |00⟩\n|01⟩ → |01⟩\n|10⟩ → |11⟩\n|11⟩ → |10⟩","use":"Two-qubit control and entanglement.","qubits":2},
    "CZ": {"name":"Controlled-Z Gate","description":"Applies a controlled phase flip to |11⟩.","matrix":"diag(1, 1, 1, -1)","input_output":"|00⟩ → |00⟩\n|01⟩ → |01⟩\n|10⟩ → |10⟩\n|11⟩ → -|11⟩","use":"Controlled phase operation.","qubits":2},
    "SWAP": {"name":"SWAP Gate","description":"Exchanges the quantum states of two qubits.","matrix":"[[1,0,0,0],[0,0,1,0],[0,1,0,0],[0,0,0,1]]","input_output":"|00⟩ → |00⟩\n|01⟩ → |10⟩\n|10⟩ → |01⟩\n|11⟩ → |11⟩","use":"Exchanges two qubit states.","qubits":2},
}

def gate_learning_circuit(gate):
    qc = QuantumCircuit(GATE_INFO[gate]["qubits"], GATE_INFO[gate]["qubits"])
    if gate == "H": qc.h(0)
    elif gate == "X": qc.x(0)
    elif gate == "Y": qc.y(0)
    elif gate == "Z": qc.z(0)
    elif gate == "S": qc.s(0)
    elif gate == "T": qc.t(0)
    elif gate == "CNOT": qc.cx(0, 1)
    elif gate == "CZ": qc.cz(0, 1)
    elif gate == "SWAP": qc.swap(0, 1)
    qc.measure(range(GATE_INFO[gate]["qubits"]), range(GATE_INFO[gate]["qubits"]))
    return qc

def render_gate_learning():
    st.title("📖 Gate Learning")
    st.write("Learn each quantum gate with its meaning, matrix, input-output behavior and simulation.")
    gate = st.selectbox("Select a gate", list(GATE_INFO.keys()), key="gate_learning_selector")
    info = GATE_INFO[gate]
    st.header(f"{gate} — {info['name']}")
    st.info(info["description"])
    c1, c2 = st.columns(2)
    with c1:
        st.subheader("Matrix")
        st.code(info["matrix"], language="text")
    with c2:
        st.subheader("Input → Output")
        st.code(info["input_output"], language="text")
    st.subheader("Main Use")
    st.write(info["use"])
    qc = gate_learning_circuit(gate)
    st.subheader("Circuit Example")
    st.code(qc.draw(output="text"), language="text")
    if st.button(f"▶️ Try {gate} Gate", use_container_width=True, key=f"try_gate_{gate}"):
        counts = simulate_circuit(qc, 512)
        if counts:
            st.subheader("Measurement Result")
            st.write(counts)
            st.success(f"{gate} gate simulated successfully.")


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
            use_container_width=True
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

    elif page == "📖 Gate Learning":

        render_gate_learning()

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
