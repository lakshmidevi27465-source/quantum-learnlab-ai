import streamlit as st
from google import genai

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

import hashlib
import json
from pathlib import Path

from supabase import create_client, Client

from qiskit import QuantumCircuit, transpile
from qiskit_aer import AerSimulator


# ============================================================
# PAGE CONFIGURATION
# ============================================================

st.set_page_config(
    page_title="Quantum LearnLab AI",
    page_icon="⚛️",
    layout="wide",
    initial_sidebar_state="expanded"
)


# ============================================================
# CONSTANTS
# ============================================================

APP_NAME = "Quantum LearnLab AI"

TOPICS = [
    "Qubit",
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

    "ai_answer": ""
}


for key, value in DEFAULT_SESSION_STATE.items():

    if key not in st.session_state:

        if isinstance(value, list):
            st.session_state[key] = value.copy()

        elif isinstance(value, dict):
            st.session_state[key] = value.copy()

        else:
            st.session_state[key] = value


# ============================================================
# CUSTOM CSS
# ============================================================

st.markdown(
    """
    <style>

    .main-title {
        font-size: 42px;
        font-weight: 700;
        margin-bottom: 5px;
    }

    .subtitle {
        font-size: 18px;
        color: #777;
        margin-bottom: 25px;
    }

    .workflow-box {
        padding: 18px;
        border-radius: 12px;
        border: 1px solid #ddd;
        margin-bottom: 15px;
    }

    .metric-box {
        padding: 15px;
        border-radius: 12px;
        border: 1px solid #ddd;
        text-align: center;
    }

    </style>
    """,
    unsafe_allow_html=True
)


# ============================================================
# SUPABASE
# ============================================================

@st.cache_resource
def get_supabase():

    url = st.secrets.get(
        "SUPABASE_URL",
        ""
    )

    key = st.secrets.get(
        "SUPABASE_KEY",
        ""
    )

    if not url or not key:
        return None

    try:

        return create_client(
            url,
            key
        )

    except Exception:

        return None


# ============================================================
# PASSWORD HASH
# ============================================================

def hash_password(password):

    return hashlib.sha256(
        password.encode()
    ).hexdigest()


# ============================================================
# LOAD USER PROFILE
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

    except Exception:

        pass

    return {}


# ============================================================
# SAVE USER PROFILE
# ============================================================

def save_profile():

    supabase = get_supabase()

    user = st.session_state.user

    if supabase is None or not user:
        return

    try:

        data = {
            "id": user.id,
            "points": st.session_state.points,
            "completed_topics": st.session_state.completed_topics,
            "badges": st.session_state.badges
        }

        supabase.table(
            "profiles"
        ).upsert(data).execute()

    except Exception as e:

        st.warning(
            f"Profile save error: {e}"
        )


# ============================================================
# RESTORE PROFILE
# ============================================================

def restore_profile(profile):

    if not profile:
        return

    st.session_state.points = profile.get(
        "points",
        0
    )

    st.session_state.completed_topics = profile.get(
        "completed_topics",
        []
    ) or []

    st.session_state.badges = profile.get(
        "badges",
        []
    ) or []


# ============================================================
# SIGN IN
# ============================================================

def sign_in(email, password):

    supabase = get_supabase()

    if supabase is None:

        return False, "Supabase is not configured."

    try:

        response = supabase.auth.sign_in_with_password(
            {
                "email": email,
                "password": password
            }
        )

        if response.user:

            st.session_state.logged_in = True
            st.session_state.user = response.user

            profile = load_profile(
                response.user.id
            )

            st.session_state.profile = profile

            restore_profile(
                profile
            )

            return True, None

        return False, "Login failed."

    except Exception as e:

        return False, str(e)


# ============================================================
# SIGN UP
# ============================================================

def sign_up(email, password):

    supabase = get_supabase()

    if supabase is None:

        return False, "Supabase is not configured."

    try:

        response = supabase.auth.sign_up(
            {
                "email": email,
                "password": password
            }
        )

        if response.user:

            return True, None

        return False, "Signup failed."

    except Exception as e:

        return False, str(e)


# ============================================================
# SIGN OUT
# ============================================================

def sign_out():

    supabase = get_supabase()

    if supabase:

        try:
            supabase.auth.sign_out()
        except Exception:
            pass

    st.session_state.logged_in = False
    st.session_state.user = None
    st.session_state.profile = {}

    st.session_state.page = "🏠 Home"

    st.rerun()


# ============================================================
# GEMINI
# ============================================================

@st.cache_resource
def get_gemini_client():

    api_key = st.secrets.get(
        "GEMINI_API_KEY",
        ""
    )

    if not api_key:
        return None

    try:

        return genai.Client(
            api_key=api_key
        )

    except Exception:

        return None


# ============================================================
# ASK GEMINI
# ============================================================

def ask_gemini(question):

    client = get_gemini_client()

    if client is None:

        return (
            None,
            "GEMINI_API_KEY is not configured in Streamlit Secrets."
        )

    if not question or not question.strip():

        return (
            None,
            "Please enter a question."
        )

    prompt = f"""
You are Quantum LearnLab AI,
an interactive quantum-computing tutor.

Answer the user's question clearly and accurately
in simple technical English.

Use:

- Short sections
- Bullet points
- Simple examples
- Equations when useful

Focus mainly on:

- Qubits
- Quantum gates
- Quantum circuits
- Quantum algorithms
- Qiskit
- Quantum simulation
- Quantum visualization
- Quantum computing concepts

If the question is outside quantum computing,
answer briefly and politely explain that the
platform is mainly focused on quantum computing.

User question:

{question.strip()}
"""

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

        if not answer:

            return (
                None,
                "Gemini returned an empty response."
            )

        return answer, None

    except Exception as e:

        return (
            None,
            f"{type(e).__name__}: {e}"
        )


# ============================================================
# AI TOPIC CLASSIFICATION
# ============================================================

def workflow_topic_from_question(question):

    client = get_gemini_client()

    if client is None:

        return "General"

    prompt = f"""
You are a quantum computing tutor.

Classify the user's question into exactly ONE
of these topics:

Qubit
Superposition
Entanglement
CNOT Gate
Measurement
Grover Search
QFT
General

Rules:

- Return ONLY the topic name.
- Do not explain anything.

If the question is about qubits or basic
quantum information, choose Qubit.

If it is about superposition or Hadamard,
choose Superposition.

If it is about Bell states or entanglement,
choose Entanglement.

If it is about controlled-NOT,
choose CNOT Gate.

If it is about measuring quantum states,
choose Measurement.

If it is about Grover's search algorithm,
choose Grover Search.

If it is about Quantum Fourier Transform,
choose QFT.

Otherwise choose General.

User question:

{question}
"""

    try:

        response = client.models.generate_content(
            model="gemini--flash",
            contents=prompt
        )

        topic = getattr(
            response,
            "text",
            ""
        ).strip()

        supported_topics = [
            "Qubit",
            "Superposition",
            "Entanglement",
            "CNOT Gate",
            "Measurement",
            "Grover Search",
            "QFT",
            "General"
        ]

        if topic in supported_topics:

            return topic

        return "General"

    except Exception:

        return "General"


# ============================================================
# POINTS
# ============================================================

def add_points(points):

    st.session_state.points += points

    save_profile()


# ============================================================
# COMPLETE TOPIC
# ============================================================

def complete_topic(topic):

    if topic not in st.session_state.completed_topics:

        st.session_state.completed_topics.append(
            topic
        )

        add_points(10)

        check_badges()

        save_profile()


# ============================================================
# BADGES
# ============================================================

def check_badges():

    completed = len(
        st.session_state.completed_topics
    )

    badges = st.session_state.badges

    if completed >= 1 and "First Step" not in badges:

        badges.append(
            "First Step"
        )

    if completed >= 3 and "Quantum Explorer" not in badges:

        badges.append(
            "Quantum Explorer"
        )

    if completed >= 5 and "Quantum Learner" not in badges:

        badges.append(
            "Quantum Learner"
        )

    if completed >= 8 and "Quantum Master" not in badges:

        badges.append(
            "Quantum Master"
        )

    save_profile()


# ============================================================
# QUANTUM SIMULATION
# ============================================================

def run_circuit(qc, shots=1024):

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


# ============================================================
# DRAW CIRCUIT
# ============================================================

def draw_circuit(qc):

    try:

        return qc.draw(
            output="mpl",
            fold=-1
        )

    except Exception:

        return None


# ============================================================
# WORKFLOW EXPLANATION
# ============================================================

def workflow_explain(topic):

    explanations = {

        "Qubit":
            """
### What is a Qubit?

A qubit is the basic unit of quantum information.

A classical bit can be:

- 0
- 1

A qubit can be represented as:

|ψ⟩ = α|0⟩ + β|1⟩

where α and β are probability amplitudes.
""",

        "Superposition":
            """
### What is Superposition?

Superposition means that a quantum state
can be represented as a combination of basis states.

For example:

|+⟩ = (|0⟩ + |1⟩) / √2

A Hadamard gate is commonly used to create
this state from |0⟩.
""",

        "Entanglement":
            """
### What is Entanglement?

Quantum entanglement creates strong correlations
between quantum systems.

A common Bell-state circuit uses:

H gate → CNOT gate

The two qubits then become entangled.
""",

        "CNOT Gate":
            """
### What is a CNOT Gate?

CNOT means Controlled-NOT.

It operates on two qubits:

- One qubit is the control.
- One qubit is the target.
- The target flips when the control is |1⟩.
""",

        "Measurement":
            """
### What is Quantum Measurement?

Measurement converts a quantum state
into a classical result.

For example:

|ψ⟩ = α|0⟩ + β|1⟩

After measurement, the result is
either 0 or 1.
""",

        "Grover Search":
            """
### What is Grover's Algorithm?

Grover's algorithm is a quantum search
algorithm for an unstructured search problem.

Its main idea is:

1. Prepare superposition.
2. Mark the desired state.
3. Amplify its probability.
4. Measure the result.
""",

        "QFT":
            """
### What is QFT?

QFT stands for Quantum Fourier Transform.

It transforms quantum amplitudes into
a Fourier-like representation.

QFT is used in several quantum algorithms,
including phase-estimation-based methods.
""",

        "General":
            """
### General Quantum Question

Your question is related to quantum computing,
but it does not directly match one of the
currently supported automatic circuit-building topics.

You can continue with the AI explanation,
or ask about:

- Qubits
- Superposition
- Entanglement
- CNOT
- Measurement
- Grover Search
- QFT
"""
    }

    return explanations.get(
        topic,
        explanations["General"]
    )


# ============================================================
# BUILD WORKFLOW CIRCUIT
# ============================================================

def workflow_build_circuit(topic):

    if topic == "General":

        return None

    # ----------------------------------------
    # ENTANGLEMENT
    # ----------------------------------------

    if topic == "Entanglement":

        qc = QuantumCircuit(
            2,
            2
        )

        qc.h(0)

        qc.cx(
            0,
            1
        )

        qc.measure(
            [0, 1],
            [0, 1]
        )

        return qc

    # ----------------------------------------
    # CNOT
    # ----------------------------------------

    if topic == "CNOT Gate":

        qc = QuantumCircuit(
            2,
            2
        )

        qc.x(0)

        qc.cx(
            0,
            1
        )

        qc.measure(
            [0, 1],
            [0, 1]
        )

        return qc

    # ----------------------------------------
    # GROVER DEMO
    # ----------------------------------------

    if topic == "Grover Search":

        qc = QuantumCircuit(
            2,
            2
        )

        qc.h(
            [0, 1]
        )

        qc.measure(
            [0, 1],
            [0, 1]
        )

        return qc

    # ----------------------------------------
    # QFT DEMO
    # ----------------------------------------

    if topic == "QFT":

        qc = QuantumCircuit(
            2,
            2
        )

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
    # QUBIT / SUPERPOSITION / MEASUREMENT
    # ----------------------------------------

    qc = QuantumCircuit(
        1,
        1
    )

    if topic in [
        "Superposition",
        "Measurement"
    ]:

        qc.h(0)

    qc.measure(
        0,
        0
    )

    return qc


# ============================================================
# NEXT TOPIC
# ============================================================

def workflow_next_topic(topic):

    order = [
        "Qubit",
        "Superposition",
        "Entanglement",
        "Measurement",
        "Grover Search",
        "QFT"
    ]

    if topic in order:

        index = order.index(
            topic
        )

        if index < len(order) - 1:

            return order[index + 1]

    return "Quantum Algorithms"


# ============================================================
# WORKFLOW
# ============================================================

def render_workflow():

    st.title(
        "🔄 Interactive Quantum Learning Workflow"
    )

    st.write(
        "ASK → EXPLAIN → BUILD → SIMULATE → "
        "VISUALIZE → ASSESS / ADAPT → NEXT LEARNING PATH"
    )

    # ========================================================
    # WORKFLOW STAGES
    # ========================================================

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

    if current_stage not in stages:

        current_stage = "ASK"

        st.session_state.workflow_stage = "ASK"

    current_index = stages.index(
        current_stage
    )

    st.progress(
        (current_index + 1) / len(stages)
    )

    st.caption(
        f"Stage {current_index + 1} of {len(stages)}"
    )

    st.divider()

    # ========================================================
    # 1 ASK
    # ========================================================

    if current_stage == "ASK":

        st.subheader(
            "1. ASK — Learner Input"
        )

        st.write(
            "Ask any quantum-computing question."
        )

        question = st.text_input(
            "Your question",
            value=st.session_state.workflow_question,
            placeholder=(
                "Example: What is the difference "
                "between classical and quantum computers?"
            )
        )

        if st.button(
            "🚀 Submit Question → EXPLAIN",
            use_container_width=True
        ):

            if not question.strip():

                st.warning(
                    "Please enter a question."
                )

            else:

                st.session_state.workflow_question = (
                    question.strip()
                )

                # Gemini identifies topic

                topic = workflow_topic_from_question(
                    question
                )

                st.session_state.workflow_topic = topic

                # Gemini generates answer

                answer, error = ask_gemini(
                    question
                )

                if error:

                    st.error(
                        f"Gemini Error: {error}"
                    )

                else:

                    st.session_state.workflow_explanation = (
                        answer
                    )

                    st.session_state.workflow_circuit = None
                    st.session_state.workflow_simulation = None
                    st.session_state.workflow_score = None

                    st.session_state.workflow_stage = (
                        "EXPLAIN"
                    )

                    st.rerun()

    # ========================================================
    # 2 EXPLAIN
    # ========================================================

    elif current_stage == "EXPLAIN":

        st.subheader(
            "2. EXPLAIN — AI Explanation"
        )

        topic = st.session_state.workflow_topic

        st.info(
            f"🤖 Gemini detected topic: **{topic}**"
        )

        if st.session_state.workflow_explanation:

            st.markdown(
                st.session_state.workflow_explanation
            )

        else:

            st.markdown(
                workflow_explain(topic)
            )

        st.divider()

        if topic != "General":

            st.write(
                "### Topic Explanation"
            )

            st.markdown(
                workflow_explain(topic)
            )

        else:

            st.info(
                "This question does not currently have "
                "an automatic circuit-building topic."
            )

        col1, col2 = st.columns(2)

        with col1:

            if st.button(
                "← Ask Another",
                use_container_width=True
            ):

                st.session_state.workflow_stage = "ASK"

                st.rerun()

        with col2:

            if st.button(
                "Continue → BUILD",
                use_container_width=True
            ):

                circuit = workflow_build_circuit(
                    topic
                )

                st.session_state.workflow_circuit = circuit

                st.session_state.workflow_stage = "BUILD"

                st.rerun()

    # ========================================================
    # 3 BUILD
    # ========================================================

    elif current_stage == "BUILD":

        st.subheader(
            "3. BUILD — Quantum Circuit"
        )

        topic = st.session_state.workflow_topic

        st.write(
            f"Detected learning topic: **{topic}**"
        )

        circuit = st.session_state.workflow_circuit

        if circuit is None:

            st.info(
                "No automatic circuit is available "
                "for this general question."
            )

            st.write(
                "The AI explanation is still available. "
                "Try a circuit-related question such as "
                "superposition, entanglement, CNOT, Grover, or QFT."
            )

            if st.button(
                "← Ask Another Question",
                use_container_width=True
            ):

                st.session_state.workflow_stage = "ASK"

                st.rerun()

        else:

            st.write(
                "### Generated Quantum Circuit"
            )

            st.code(
                str(circuit),
                language="text"
            )

            st.success(
                "Circuit generated successfully."
            )

            if st.button(
                "Continue → SIMULATE",
                use_container_width=True
            ):

                st.session_state.workflow_stage = (
                    "SIMULATE"
                )

                st.rerun()

    # ========================================================
    # 4 SIMULATE
    # ========================================================

    elif current_stage == "SIMULATE":

        st.subheader(
            "4. SIMULATE — Quantum Simulation"
        )

        circuit = st.session_state.workflow_circuit

        if circuit is None:

            st.warning(
                "No circuit is available."
            )

        else:

            shots = st.slider(
                "Number of shots",
                min_value=100,
                max_value=2000,
                value=1024,
                step=100
            )

            if st.button(
                "▶ Run Quantum Simulation",
                use_container_width=True
            ):

                try:

                    counts = run_circuit(
                        circuit,
                        shots=shots
                    )

                    st.session_state.workflow_simulation = (
                        counts
                    )

                    st.success(
                        "Simulation completed successfully."
                    )

                except Exception as e:

                    st.error(
                        f"Simulation Error: {e}"
                    )

            if st.session_state.workflow_simulation:

                st.write(
                    "### Measurement Results"
                )

                st.json(
                    st.session_state.workflow_simulation
                )

                if st.button(
                    "Continue → VISUALIZE",
                    use_container_width=True
                ):

                    st.session_state.workflow_stage = (
                        "VISUALIZE"
                    )

                    st.rerun()

    # ========================================================
    # 5 VISUALIZE
    # ========================================================

    elif current_stage == "VISUALIZE":

        st.subheader(
            "5. VISUALIZE — Quantum Circuit & Results"
        )

        circuit = st.session_state.workflow_circuit

        if circuit is not None:

            st.write(
                "### Quantum Circuit"
            )

            try:

                fig = circuit.draw(
                    output="mpl",
                    fold=-1
                )

                st.pyplot(
                    fig
                )

            except Exception as e:

                st.warning(
                    "Circuit graphical visualization "
                    "is not available."
                )

                st.code(
                    str(circuit),
                    language="text"
                )

        # ----------------------------------------
        # RESULTS GRAPH
        # ----------------------------------------

        counts = st.session_state.workflow_simulation

        if counts:

            st.write(
                "### Measurement Distribution"
            )

            labels = list(
                counts.keys()
            )

            values = list(
                counts.values()
            )

            fig, ax = plt.subplots()

            ax.bar(
                labels,
                values
            )

            ax.set_xlabel(
                "Measurement Result"
            )

            ax.set_ylabel(
                "Counts"
            )

            ax.set_title(
                "Quantum Measurement Results"
            )

            st.pyplot(
                fig
            )

        if st.button(
            "Continue → ASSESS / ADAPT",
            use_container_width=True
        ):

            st.session_state.workflow_stage = (
                "ASSESS / ADAPT"
            )

            st.rerun()

    # ========================================================
    # 6 ASSESS / ADAPT
    # ========================================================

    elif current_stage == "ASSESS / ADAPT":

        st.subheader(
            "6. ASSESS / ADAPT — Learning Assessment"
        )

        topic = st.session_state.workflow_topic

        questions = {

            "Qubit": (
                "What is the basic unit of quantum information?",
                [
                    "Bit",
                    "Qubit",
                    "Byte",
                    "Register"
                ],
                1
            ),

            "Superposition": (
                "Which gate is commonly used to create "
                "superposition from |0⟩?",
                [
                    "X",
                    "Z",
                    "H",
                    "CNOT"
                ],
                2
            ),

            "Entanglement": (
                "Which gate is commonly combined with H "
                "to create a Bell state?",
                [
                    "X",
                    "CNOT",
                    "Z",
                    "T"
                ],
                1
            ),

            "CNOT Gate": (
                "What type of operation is CNOT?",
                [
                    "Single-qubit operation",
                    "Controlled two-qubit operation",
                    "Measurement",
                    "Classical operation"
                ],
                1
            ),

            "Measurement": (
                "What does quantum measurement produce?",
                [
                    "Only a quantum state",
                    "A classical outcome",
                    "A new qubit",
                    "A new gate"
                ],
                1
            ),

            "Grover Search": (
                "What problem is Grover's algorithm "
                "designed for?",
                [
                    "Unstructured search",
                    "Image compression",
                    "Classical sorting",
                    "Data storage"
                ],
                0
            ),

            "QFT": (
                "QFT stands for:",
                [
                    "Quantum Fast Transformation",
                    "Quantum Fourier Transform",
                    "Quantum Feature Transfer",
                    "Quantum Function Tool"
                ],
                1
            ),

            "General": (
                "Which technology provides the AI explanations "
                "in this platform?",
                [
                    "Gemini",
                    "Excel",
                    "MATLAB only",
                    "HTML only"
                ],
                0
            )
        }

        question_data = questions.get(
            topic,
            questions["General"]
        )

        question_text = question_data[0]

        options = question_data[1]

        correct_answer = question_data[2]

        st.write(
            f"### {question_text}"
        )

        answer = st.radio(
            "Select your answer:",
            options,
            key="workflow_assessment_answer"
        )

        if st.button(
            "Submit Assessment",
            use_container_width=True
        ):

            selected_index = options.index(
                answer
            )

            if selected_index == correct_answer:

                st.session_state.workflow_score = 100

                st.success(
                    "Correct! 🎉"
                )

                complete_topic(
                    topic
                )

            else:

                st.session_state.workflow_score = 0

                st.error(
                    "Incorrect."
                )

                st.info(
                    f"Correct answer: "
                    f"{options[correct_answer]}"
                )

        if st.session_state.workflow_score is not None:

            st.write(
                f"### Score: "
                f"{st.session_state.workflow_score}%"
            )

            if st.session_state.workflow_score >= 80:

                st.success(
                    "Good understanding! You can continue "
                    "to the next learning topic."
                )

            else:

                st.warning(
                    "More practice is recommended."
                )

            if st.button(
                "Continue → NEXT LEARNING PATH",
                use_container_width=True
            ):

                st.session_state.workflow_stage = (
                    "NEXT LEARNING PATH"
                )

                st.rerun()

    # ========================================================
    # 7 NEXT LEARNING PATH
    # ========================================================

    elif current_stage == "NEXT LEARNING PATH":

        st.subheader(
            "7. NEXT LEARNING PATH — Adaptive Guidance"
        )

        topic = st.session_state.workflow_topic

        score = st.session_state.workflow_score

        if score is None:

            score = 0

        st.write(
            f"Current topic: **{topic}**"
        )

        st.write(
            f"Assessment score: **{score}%**"
        )

        st.divider()

        if score >= 80:

            next_topic = workflow_next_topic(
                topic
            )

            st.success(
                "Good performance! "
                "You can move to the next topic."
            )

            st.write(
                f"### Recommended Next Topic"
            )

            st.info(
                next_topic
            )

        else:

            next_topic = topic

            st.warning(
                "Your score is below 80%. "
                "Practice this topic again."
            )

            st.write(
                f"### Recommended Practice"
            )

            st.info(
                topic
            )

        st.divider()

        if st.button(
            "🚀 Start Recommended Learning",
            use_container_width=True
        ):

            st.session_state.workflow_question = (
                f"Teach me {next_topic} in quantum computing."
            )

            st.session_state.workflow_topic = (
                next_topic
            )

            answer, error = ask_gemini(
                st.session_state.workflow_question
            )

            if error:

                st.error(
                    f"Gemini Error: {error}"
                )

            else:

                st.session_state.workflow_explanation = (
                    answer
                )

                st.session_state.workflow_circuit = (
                    workflow_build_circuit(
                        next_topic
                    )
                )

                st.session_state.workflow_simulation = None
                st.session_state.workflow_score = None

                st.session_state.workflow_stage = (
                    "EXPLAIN"
                )

                st.rerun()

        if st.button(
            "🔄 Start New Question",
            use_container_width=True
        ):

            st.session_state.workflow_question = ""
            st.session_state.workflow_topic = ""
            st.session_state.workflow_explanation = ""
            st.session_state.workflow_circuit = None
            st.session_state.workflow_simulation = None
            st.session_state.workflow_score = None

            st.session_state.workflow_stage = "ASK"

            st.rerun()


# ============================================================
# HOME
# ============================================================

def render_home():

    st.markdown(
        '<div class="main-title">⚛️ Quantum LearnLab AI</div>',
        unsafe_allow_html=True
    )

    st.markdown(
        '<div class="subtitle">'
        'AI-powered interactive quantum computing learning platform'
        '</div>',
        unsafe_allow_html=True
    )

    st.write(
        """
        Learn quantum computing through an integrated
        learning and experimentation workflow.
        """
    )

    st.divider()

    col1, col2, col3, col4 = st.columns(4)

    with col1:

        st.metric(
            "⭐ Points",
            st.session_state.points
        )

    with col2:

        st.metric(
            "📚 Topics Completed",
            len(
                st.session_state.completed_topics
            )
        )

    with col3:

        st.metric(
            "🏆 Badges",
            len(
                st.session_state.badges
            )
        )

    with col4:

        st.metric(
            "🤖 AI Tutor",
            "Gemini 3.6 Flash"
        )

    st.divider()

    st.subheader(
        "🚀 Learning Workflow"
    )

    st.code(
        """
LOGIN / SIGNUP
      ↓
ASK
      ↓
EXPLAIN
      ↓
BUILD
      ↓
SIMULATE
      ↓
VISUALIZE
      ↓
ASSESS / ADAPT
      ↓
NEXT LEARNING PATH
        """,
        language="text"
    )

    st.write(
        """
        The platform combines AI explanations,
        quantum circuit construction, simulation,
        visualization and learner assessment
        into one continuous learning process.
        """
    )


# ============================================================
# LEARN
# ============================================================

def render_learn():

    st.title(
        "📚 Learn Quantum Computing"
    )

    topic = st.selectbox(
        "Choose a topic",
        TOPICS
    )

    st.divider()

    st.subheader(
        topic
    )

    st.markdown(
        workflow_explain(topic)
    )

    if st.button(
        "✅ Mark Topic Complete"
    ):

        complete_topic(
            topic
        )

        st.success(
            f"{topic} completed!"
        )


# ============================================================
# CIRCUIT BUILDER
# ============================================================

def render_circuit_builder():

    st.title(
        "🔧 Quantum Circuit Builder"
    )

    st.write(
        "Build and simulate a simple quantum circuit."
    )

    qc = QuantumCircuit(
        2,
        2
    )

    col1, col2 = st.columns(2)

    with col1:

        if st.button(
            "H Gate on Q0"
        ):

            qc.h(0)

    with col2:

        if st.button(
            "CNOT Q0 → Q1"
        ):

            qc.h(0)
            qc.cx(
                0,
                1
            )

    qc.measure(
        [0, 1],
        [0, 1]
    )

    st.write(
        "### Circuit"
    )

    st.code(
        str(qc),
        language="text"
    )

    if st.button(
        "▶ Simulate Circuit"
    ):

        try:

            counts = run_circuit(
                qc
            )

            st.write(
                "### Results"
            )

            st.json(
                counts
            )

        except Exception as e:

            st.error(
                f"Simulation Error: {e}"
            )


# ============================================================
# QUANTUM ALGORITHMS
# ============================================================

def render_algorithms():

    st.title(
        "🧠 Quantum Algorithms"
    )

    algorithm = st.selectbox(
        "Select Algorithm",
        [
            "Bell State",
            "Grover Search",
            "QFT"
        ]
    )

    if algorithm == "Bell State":

        st.subheader(
            "Bell State"
        )

        st.write(
            "A Bell state demonstrates quantum entanglement."
        )

        qc = QuantumCircuit(
            2,
            2
        )

        qc.h(0)
        qc.cx(0, 1)

        qc.measure(
            [0, 1],
            [0, 1]
        )

    elif algorithm == "Grover Search":

        st.subheader(
            "Grover Search"
        )

        st.write(
            "This is a simplified Grover demonstration."
        )

        qc = QuantumCircuit(
            2,
            2
        )

        qc.h(
            [0, 1]
        )

        qc.measure(
            [0, 1],
            [0, 1]
        )

    else:

        st.subheader(
            "Quantum Fourier Transform"
        )

        qc = QuantumCircuit(
            2,
            2
        )

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

    st.code(
        str(qc),
        language="text"
    )

    if st.button(
        "▶ Run Algorithm"
    ):

        counts = run_circuit(
            qc
        )

        st.json(
            counts
        )

    if st.button(
        "✅ Complete Algorithm"
    ):

        complete_topic(
            algorithm
        )

        st.success(
            "Completed!"
        )


# ============================================================
# VISUALIZATION
# ============================================================

def render_visualization():

    st.title(
        "📊 Quantum Visualization"
    )

    st.write(
        "Visualize a simple quantum measurement distribution."
    )

    state = st.selectbox(
        "Select quantum state",
        [
            "|0⟩",
            "|1⟩",
            "|+⟩",
            "Bell State"
        ]
    )

    if state == "|0⟩":

        labels = [
            "0",
            "1"
        ]

        probabilities = [
            1,
            0
        ]

    elif state == "|1⟩":

        labels = [
            "0",
            "1"
        ]

        probabilities = [
            0,
            1
        ]

    elif state == "|+⟩":

        labels = [
            "0",
            "1"
        ]

        probabilities = [
            0.5,
            0.5
        ]

    else:

        labels = [
            "00",
            "01",
            "10",
            "11"
        ]

        probabilities = [
            0.5,
            0,
            0,
            0.5
        ]

    fig, ax = plt.subplots()

    ax.bar(
        labels,
        probabilities
    )

    ax.set_xlabel(
        "Measurement State"
    )

    ax.set_ylabel(
        "Probability"
    )

    ax.set_title(
        f"Visualization of {state}"
    )

    st.pyplot(
        fig
    )


# ============================================================
# QISKIT CODE EDITOR
# ============================================================

def render_code_editor():

    st.title(
        "💻 Qiskit Code Editor"
    )

    st.write(
        "Run a simple Qiskit circuit."
    )

    default_code = """from qiskit import QuantumCircuit

qc = QuantumCircuit(2, 2)

qc.h(0)
qc.cx(0, 1)

qc.measure([0, 1], [0, 1])

print(qc)
"""

    code = st.text_area(
        "Qiskit Code",
        value=default_code,
        height=350
    )

    if st.button(
        "▶ Run Code"
    ):

        try:

            local_vars = {}

            exec(
                code,
                {},
                local_vars
            )

            st.success(
                "Code executed."
            )

            if "qc" in local_vars:

                qc = local_vars["qc"]

                st.code(
                    str(qc),
                    language="text"
                )

                counts = run_circuit(
                    qc
                )

                st.write(
                    "### Simulation Results"
                )

                st.json(
                    counts
                )

        except Exception as e:

            st.error(
                f"Code Error: {e}"
            )


# ============================================================
# FIX MY CIRCUIT
# ============================================================

def render_fix_circuit():

    st.title(
        "🛠️ Fix My Circuit"
    )

    code = st.text_area(
        "Paste your Qiskit circuit code",
        height=250
    )

    if st.button(
        "🤖 Analyze Circuit"
    ):

        if not code.strip():

            st.warning(
                "Please enter circuit code."
            )

        else:

            prompt = f"""
You are a quantum-computing debugging assistant.

Analyze the following Qiskit code.

Explain:
1. What the circuit is trying to do.
2. Any errors.
3. How to fix them.
4. Corrected code.

Keep the explanation simple.

Code:

{code}
"""

            client = get_gemini_client()

            if client is None:

                st.error(
                    "Gemini is not configured."
                )

            else:

                try:

                    response = client.models.generate_content(
                        model="gemini-2.5-flash",
                        contents=prompt
                    )

                    st.markdown(
                        response.text
                    )

                except Exception as e:

                    st.error(
                        f"Gemini Error: {e}"
                    )


# ============================================================
# AI TUTOR
# ============================================================

def render_ai_tutor():

    st.title(
        "🤖 AI Quantum Tutor"
    )

    st.write(
        "Ask any question about quantum computing."
    )

    question = st.text_area(
        "Ask your question",
        placeholder=(
            "Example: What is the difference "
            "between classical and quantum computers?"
        ),
        height=120
    )

    if st.button(
        "💡 Ask AI",
        use_container_width=True
    ):

        if not question.strip():

            st.warning(
                "Please enter a question."
            )

        else:

            answer, error = ask_gemini(
                question
            )

            if error:

                st.error(
                    f"Gemini Error: {error}"
                )

            else:

                st.markdown(
                    answer
                )


# ============================================================
# QUIZ
# ============================================================

def render_quiz():

    st.title(
        "📝 Quantum Quiz"
    )

    questions = [

        (
            "What is the basic unit of quantum information?",
            [
                "Bit",
                "Qubit",
                "Byte",
                "Register"
            ],
            1
        ),

        (
            "Which gate creates superposition from |0⟩?",
            [
                "X",
                "Z",
                "H",
                "CNOT"
            ],
            2
        ),

        (
            "Which gate is commonly used to create entanglement?",
            [
                "X",
                "CNOT",
                "T",
                "S"
            ],
            1
        ),

        (
            "What does QFT stand for?",
            [
                "Quantum Fast Transformation",
                "Quantum Fourier Transform",
                "Quantum Feature Transfer",
                "Quantum Function Tool"
            ],
            1
        )
    ]

    score = 0

    for i, item in enumerate(questions):

        question = item[0]
        options = item[1]
        correct = item[2]

        st.write(
            f"**{i + 1}. {question}**"
        )

        answer = st.radio(
            "Answer",
            options,
            key=f"quiz_{i}"
        )

        if options.index(answer) == correct:

            score += 1

    if st.button(
        "Submit Quiz"
    ):

        percentage = int(
            (score / len(questions)) * 100
        )

        st.session_state.quiz_score = percentage

        st.success(
            f"Your score: {percentage}%"
        )

        if percentage >= 75:

            add_points(20)

            st.info(
                "+20 points added!"
            )


# ============================================================
# PROGRESS
# ============================================================

def render_progress():

    st.title(
        "📈 My Progress"
    )

    total_topics = 8

    completed = len(
        st.session_state.completed_topics
    )

    progress = min(
        completed / total_topics,
        1.0
    )

    st.progress(
        progress
    )

    st.write(
        f"Completed: {completed}/{total_topics}"
    )

    st.write(
        f"### ⭐ Points: {st.session_state.points}"
    )

    st.write(
        "### 🏆 Badges"
    )

    if st.session_state.badges:

        for badge in st.session_state.badges:

            st.write(
                f"🏅 {badge}"
            )

    else:

        st.info(
            "Complete topics to earn badges."
        )

    st.write(
        "### 📚 Completed Topics"
    )

    if st.session_state.completed_topics:

        for topic in st.session_state.completed_topics:

            st.write(
                f"✅ {topic}"
            )

    else:

        st.info(
            "No topics completed yet."
        )


# ============================================================
# LEADERBOARD
# ============================================================

def render_leaderboard():

    st.title(
        "🏆 Leaderboard"
    )

    current_email = ""

    if st.session_state.user:

        current_email = st.session_state.user.email or ""

    leaderboard = pd.DataFrame(
        {
            "Learner": [
                "Quantum Learner",
                "Quantum Explorer",
                "Future Quantum Engineer",
                current_email or "You"
            ],
            "Points": [
                120,
                100,
                80,
                st.session_state.points
            ]
        }
    )

    leaderboard = leaderboard.sort_values(
        "Points",
        ascending=False
    ).reset_index(
        drop=True
    )

    leaderboard.index = (
        leaderboard.index + 1
    )

    st.dataframe(
        leaderboard,
        use_container_width=True
    )


# ============================================================
# LOGIN PAGE
# ============================================================

def render_login():

    st.title(
        "⚛️ Quantum LearnLab AI"
    )

    st.subheader(
        "Login"
    )

    email = st.text_input(
        "Email"
    )

    password = st.text_input(
        "Password",
        type="password"
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

            success, error = sign_in(
                email,
                password
            )

            if success:

                st.success(
                    "Login successful!"
                )

                st.rerun()

            else:

                st.error(
                    error
                )

    st.divider()

    st.subheader(
        "Create Account"
    )

    signup_email = st.text_input(
        "Signup Email"
    )

    signup_password = st.text_input(
        "Signup Password",
        type="password"
    )

    if st.button(
        "Create Account",
        use_container_width=True
    ):

        if not signup_email or not signup_password:

            st.warning(
                "Please enter email and password."
            )

        elif len(signup_password) < 6:

            st.warning(
                "Password should contain at least 6 characters."
            )

        else:

            success, error = sign_up(
                signup_email,
                signup_password
            )

            if success:

                st.success(
                    "Account created. Check your email if confirmation is required."
                )

            else:

                st.error(
                    error
                )


# ============================================================
# SIDEBAR
# ============================================================

def render_sidebar():

    with st.sidebar:

        st.title(
            "⚛️ Quantum LearnLab"
        )

        if st.session_state.user:

            st.write(
                f"👤 {st.session_state.user.email}"
            )

        st.divider()

        page_options = [

            "🏠 Home",
            "🔄 Learning Workflow",
            "📚 Learn",
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

        current_page = st.session_state.page

        if current_page not in page_options:

            current_page = "🏠 Home"

        page = st.radio(
            "Navigation",
            page_options,
            index=page_options.index(
                current_page
            )
        )

        st.session_state.page = page

        st.divider()

        st.metric(
            "⭐ Points",
            st.session_state.points
        )

        st.metric(
            "📚 Completed",
            len(
                st.session_state.completed_topics
            )
        )

        st.divider()

        if st.button(
            "🚪 Logout",
            use_container_width=True
        ):

            sign_out()


# ============================================================
# MAIN APP
# ============================================================

if not st.session_state.logged_in:

    render_login()

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


# ============================================================
# FOOTER
# ============================================================

st.markdown(
    "---"
)

st.caption(
    "⚛️ Quantum LearnLab AI | "
    "AI-powered interactive quantum learning platform"
)
