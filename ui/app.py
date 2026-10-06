from __future__ import annotations

import math
import numpy as np
import streamlit as st
import plotly.graph_objects as go

from utils_paths import add_project_root_to_syspath
add_project_root_to_syspath()

st.set_page_config(page_title="ADaPT — Home", layout="wide")

# -----------------------------
# Styling (FIXED)
# -----------------------------
st.markdown(
    """
<style>
.main > div { padding-top: 1.2rem; }

/* Floating screenshot button */
#screenshot-floating-btn {
    position: fixed;
    top: 70px;
    right: 20px;
    z-index: 9999;

    padding: 10px 14px;
    border-radius: 10px;
    border: 1px solid rgba(0,0,0,0.15);
    background: white;

    font-weight: 600;
    cursor: pointer;
    box-shadow: 0 4px 12px rgba(0,0,0,0.1);
}
#screenshot-floating-btn:hover {
    background: #f0f2f6;
}

/* Hero */
.adapt-hero {
  font-size: 44px;
  font-weight: 800;
  letter-spacing: -0.02em;
}
.adapt-sub {
  font-size: 16px;
  opacity: 0.85;
}

/* Cards */
.card {
  border: 1px solid rgba(49, 51, 63, 0.14);
  border-radius: 16px;
  padding: 16px;
  background: rgba(255,255,255,0.6);
  box-shadow: 0 6px 24px rgba(0,0,0,0.04);
}
</style>
""",
    unsafe_allow_html=True,
)

# -----------------------------
# Floating Button (ONLY ONE)
# -----------------------------
st.markdown(
    """
<button id="screenshot-floating-btn">
    📸 Save PNG
</button>
""",
    unsafe_allow_html=True,
)

# -----------------------------
# Hero
# -----------------------------
c1, c2 = st.columns([1.25, 1.0], gap="large")

with c1:
    st.markdown('<div class="adapt-hero">ADaPT</div>', unsafe_allow_html=True)
    st.markdown(
        '<p class="adapt-sub">Airship Design & Performance Tool</p>',
        unsafe_allow_html=True,
    )

    qs1, qs2, qs3 = st.columns(3)
    qs1.button("▶ Run MDA", use_container_width=True)
    qs2.button("🧪 Feasibility Case", use_container_width=True)
    qs3.button("📈 Pareto Maps", use_container_width=True)

with c2:
    x = np.linspace(0, 2 * math.pi, 120)
    wind = 8 + 3 * np.sin(x)

    fig = go.Figure()
    fig.add_trace(go.Scatter(x=np.arange(len(wind)), y=wind))

    fig.update_layout(height=220, margin=dict(l=0, r=0, t=0, b=0))
    st.plotly_chart(fig, use_container_width=True)

# -----------------------------
# Cards
# -----------------------------
st.markdown("<hr>", unsafe_allow_html=True)

cols = st.columns(3)
titles = ["Run MDA", "Validation", "Optimization"]

for i, col in enumerate(cols):
    with col:
        st.markdown(f"""
        <div class="card">
            <h3>{titles[i]}</h3>
            <p>Module description</p>
        </div>
        """, unsafe_allow_html=True)

# -----------------------------
# Playground
# -----------------------------
st.markdown("<hr>", unsafe_allow_html=True)

p1, p2 = st.columns(2)

with p1:
    L = st.slider("Length", 20.0, 120.0, 50.0)
    FR = st.slider("Fineness", 2.0, 8.0, 4.0)

    D = L / FR
    st.metric("Diameter", f"{D:.2f} m")

with p2:
    a = L / 2
    b = D / 2

    t = np.linspace(0, 2 * np.pi, 200)
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=a*np.cos(t), y=b*np.sin(t)))

    st.plotly_chart(fig, use_container_width=True)

# -----------------------------
# Screenshot Script (FIXED)
# -----------------------------
st.markdown("""
<script src="https://html2canvas.hertzen.com/dist/html2canvas.min.js"></script>

<script>
function attachScreenshot() {

    const btn = document.getElementById("screenshot-floating-btn");

    if (btn && !btn.dataset.bound) {

        btn.dataset.bound = "true";

        btn.onclick = function() {

            html2canvas(document.body, {
                backgroundColor: null,
                useCORS: true,
                scale: 3,
                scrollY: -window.scrollY
            }).then(canvas => {

                const link = document.createElement("a");
                link.download = "ADaPT_screenshot.png";
                link.href = canvas.toDataURL("image/png");
                link.click();
            });
        };
    }
}

// Streamlit-safe attach
setTimeout(attachScreenshot, 500);
setTimeout(attachScreenshot, 1500);

</script>
""", unsafe_allow_html=True)