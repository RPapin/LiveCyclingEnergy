"""
Visualisation interactive du modèle énergétique.
Génère un fichier HTML autonome avec Plotly.
"""

import plotly.graph_objects as go
from plotly.subplots import make_subplots
import pandas as pd


def plot_energy_model(df: pd.DataFrame, output_path: str = "energy_report.html"):
    fig = make_subplots(
        rows=4, cols=1,
        shared_xaxes=True,
        subplot_titles=[
            "Puissance (W)",
            "Énergie restante (%)",
            "Temps restant estimé (min)",
            "HR Drift — ratio Puissance / FC (signal de fatigue)",
        ],
        vertical_spacing=0.08,
    )

    x = df["timestamp"]

    # Puissance
    fig.add_trace(go.Scatter(
        x=x, y=df["power"],
        name="Puissance", line=dict(color="#378ADD", width=1),
        fill="tozeroy", fillcolor="rgba(55,138,221,0.1)"
    ), row=1, col=1)

    # Énergie restante avec zones colorées
    fig.add_trace(go.Scatter(
        x=x, y=df["energy_remaining"],
        name="Énergie restante", line=dict(color="#1D9E75", width=2),
    ), row=2, col=1)
    # Zone critique < 30%
    fig.add_hrect(y0=0, y1=30, row=2, col=1,
        fillcolor="rgba(226,75,74,0.12)", line_width=0,
        annotation_text="Zone critique", annotation_position="top left")
    # Zone d'alerte 30-50%
    fig.add_hrect(y0=30, y1=50, row=2, col=1,
        fillcolor="rgba(239,159,39,0.10)", line_width=0,
        annotation_text="Ravitaillement recommandé", annotation_position="top left")

    # Temps restant
    fig.add_trace(go.Scatter(
        x=x, y=df["time_remaining_min"],
        name="Temps restant", line=dict(color="#BA7517", width=2),
    ), row=3, col=1)

    # HR drift
    fig.add_trace(go.Scatter(
        x=x, y=df["hr_drift"],
        name="HR Drift", line=dict(color="#D85A30", width=1.5),
    ), row=4, col=1)

    fig.update_layout(
        height=900,
        title="Modèle énergétique — Analyse de sortie",
        showlegend=False,
        template="plotly_white",
        font=dict(family="sans-serif", size=12),
    )
    fig.update_yaxes(title_text="Watts", row=1, col=1)
    fig.update_yaxes(title_text="%", row=2, col=1, range=[0, 105])
    fig.update_yaxes(title_text="Minutes", row=3, col=1)
    fig.update_yaxes(title_text="W/bpm", row=4, col=1)

    fig.write_html(output_path)
    print(f"Rapport généré : {output_path}")
    return fig