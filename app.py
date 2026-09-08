import streamlit as st

st.set_page_config(
    page_title="Quantum LearnLab AI",
    page_icon="⚛️",
    layout="wide"
)

st.title("⚛️ Quantum LearnLab AI")
st.write("Interactive Quantum Computing Learning Platform")

# -----------------------------
# 1. Qubit & Superposition
# -----------------------------
st.header("1. Qubit and Superposition")

st.write("""
A qubit is the basic unit of quantum information.
Unlike a classical bit, a qubit can exist in a superposition
of |0⟩ and |1⟩ states.
""")

st.image(
    "assets/fig1_qubit_superposition.png",
    caption="Qubit Superposition",
    use_container_width=True
)

# -----------------------------
# 2. Quantum Entanglement
# -----------------------------
st.header("2. Quantum Entanglement and Teleportation")

st.write("""
Quantum entanglement is a special quantum correlation between
two or more qubits. Quantum teleportation uses entanglement
to transfer quantum information.
""")

st.image(
    "assets/fig3_entanglement_teleportation.png",
    caption="Quantum Entanglement and Teleportation",
    use_container_width=True
)

# -----------------------------
# 3. Hadamard and CNOT
# -----------------------------
st.header("3. Hadamard and CNOT Gates")

st.write("""
The Hadamard gate creates superposition.
The CNOT gate is commonly used to create entanglement
between qubits.
""")

st.image(
    "assets/fig4_hadamard_cnot_circuit.png",
    caption="Hadamard and CNOT Quantum Circuit",
    use_container_width=True
)

st.success("Quantum concepts and diagrams loaded successfully!")
