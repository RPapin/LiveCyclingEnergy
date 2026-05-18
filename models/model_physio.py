"""
Modèle physiologique d'estimation d'énergie restante
pour une sortie de cyclisme route.

Hypothèses :
  - delta_t = 1 seconde entre chaque point
  - Puissance en watts, poids en kg, FTP en watts
  - Efficacité mécanique du cycliste : ~25%
  - Réserves glycogéniques de base : ~500g ≈ 2000 kcal
"""

import pandas as pd
import numpy as np


# ─────────────────────────────────────────────
# Constantes physiologiques
# ─────────────────────────────────────────────

MECHANICAL_EFFICIENCY = 0.25   # 25% : énergie mécanique / énergie métabolique totale
KCAL_PER_KJ           = 0.239  # 1 kJ = 0.239 kcal
GLYCOGEN_KCAL_PER_G   = 4.0    # 1g de glycogène ≈ 4 kcal
BASE_GLYCOGEN_G       = 500    # réserves de base d'un athlète entraîné (grammes)
DELTA_T               = 1      # secondes entre chaque point


# ─────────────────────────────────────────────
# 1. Énergie dépensée
# ─────────────────────────────────────────────

def compute_kj_spent(power_series: pd.Series) -> pd.Series:
    """
    Calcule les kJ dépensés cumulés seconde par seconde.

    Formule :
        kJ_instant = power (W) × delta_t (s) / 1000
        kJ_cumul   = somme cumulative des kJ_instant

    Note : on divise par l'efficacité mécanique pour obtenir
    l'énergie MÉTABOLIQUE réelle (ce que ton corps dépense),
    pas seulement l'énergie mécanique transmise aux pédales.
    """
    kj_per_second = (power_series * DELTA_T) / 1000
    metabolic_kj  = kj_per_second / MECHANICAL_EFFICIENCY
    return metabolic_kj.cumsum()


def kj_to_kcal(kj: float) -> float:
    """Convertit des kJ en kcal."""
    return kj * KCAL_PER_KJ


# ─────────────────────────────────────────────
# 2. Réserves maximales estimées (kJ_max)
# ─────────────────────────────────────────────

def estimate_kj_max(
    weight_kg: float,
    ftp_watts: float,
    ctl: float = 50.0,
) -> float:
    """
    Estime les réserves énergétiques disponibles au départ de la sortie.

    Logique :
      - Base glycogénique = 500g × 4 kcal/g = 2000 kcal pour un athlète moyen
      - Ajustement par le poids (plus on est lourd, plus les réserves absolues sont grandes)
      - Ajustement par le FTP (plus on est entraîné, meilleure utilisation des graisses)
      - Correction CTL : une CTL élevée = meilleure forme = réserves plus accessibles
        Une CTL basse = moins bien entraîné = réserves moins disponibles

    CTL (Chronic Training Load) : charge d'entraînement chronique sur 42 jours.
      - < 30  : débutant / peu entraîné
      - 30-60 : cycliste régulier
      - > 60  : athlète entraîné

    ⚠️  Ces coefficients sont des points de départ.
        Tu dois les calibrer avec tes propres données.
    """
    # Réserves glycogéniques de base en kcal
    base_kcal = BASE_GLYCOGEN_G * GLYCOGEN_KCAL_PER_G

    # Ajustement au poids (±1% par kg au-dessus/en-dessous de 70kg)
    weight_factor = 1 + (weight_kg - 70) * 0.01

    # Ajustement au FTP (meilleur FTP = meilleure économie = réserves plus durables)
    ftp_factor = 1 + (ftp_watts - 200) * 0.001

    # Ajustement CTL (forme du jour)
    ctl_factor = 0.85 + (ctl / 100) * 0.30

    estimated_kcal = base_kcal * weight_factor * ftp_factor * ctl_factor

    # Conversion kcal → kJ (1 kcal = 4.184 kJ)
    return estimated_kcal * 4.184


# ─────────────────────────────────────────────
# 3. Énergie restante
# ─────────────────────────────────────────────

def compute_energy_remaining(
    kj_spent: pd.Series,
    kj_max: float,
) -> pd.Series:
    """
    Calcule le % d'énergie restante à chaque instant.

    Clippé entre 0% et 100% pour éviter les valeurs aberrantes.
    En dessous de 0% : le modèle sous-estime kJ_max (à recalibrer).
    """
    remaining = (1 - kj_spent / kj_max) * 100
    return remaining.clip(lower=0, upper=100)


# ─────────────────────────────────────────────
# 4. Temps restant estimé
# ─────────────────────────────────────────────

def compute_time_remaining(
    energy_remaining_pct: pd.Series,
    kj_max: float,
    power_series: pd.Series,
    window_seconds: int = 300,
) -> pd.Series:
    """
    Estime le temps restant (en minutes) avant épuisement des réserves,
    en extrapolant la dépense moyenne sur les N dernières secondes.

    window_seconds : fenêtre glissante pour lisser la puissance (défaut 5 min).

    Formule :
        kJ_restants      = (energy_remaining_pct / 100) × kJ_max
        dépense_par_sec  = rolling_avg_power / 1000 / efficacité
        temps_restant(s) = kJ_restants / dépense_par_sec
    """
    kj_remaining = (energy_remaining_pct / 100) * kj_max

    rolling_power    = power_series.rolling(window=window_seconds, min_periods=1).mean()
    kj_per_second    = (rolling_power / 1000) / MECHANICAL_EFFICIENCY

    # Évite la division par zéro si puissance = 0 (descente, arrêt)
    kj_per_second_safe = kj_per_second.replace(0, np.nan)

    time_remaining_sec = kj_remaining / kj_per_second_safe
    time_remaining_min = time_remaining_sec / 60

    return time_remaining_min.clip(lower=0)


# ─────────────────────────────────────────────
# 5. Signaux de fatigue complémentaires
# ─────────────────────────────────────────────

def compute_hr_drift(
    power_series: pd.Series,
    hr_series: pd.Series,
    window_seconds: int = 300,
) -> pd.Series:
    """
    Calcule le découplage puissance/FC (HR drift).

    Un ratio puissance/FC qui baisse dans le temps indique que
    ton cœur travaille de plus en plus pour maintenir la même puissance :
    signal physiologique de fatigue et de déplétion glycogénique.

    Interprétation :
        ratio stable   → bonne forme, réserves suffisantes
        ratio qui baisse → fatigue croissante
    """
    ratio = power_series / hr_series.replace(0, np.nan)
    return ratio.rolling(window=window_seconds, min_periods=1).mean()


def compute_normalized_power(
    power_series: pd.Series,
    window_seconds: int = 30,
) -> float:
    """
    Calcule la Normalized Power (NP) de la sortie complète.

    La NP représente mieux le coût réel d'un effort variable
    qu'une simple moyenne de puissance.

    Formule :
        1. Moyenne glissante sur 30s
        2. Élever à la puissance 4
        3. Moyenne de ces valeurs
        4. Racine 4ème du résultat
    """
    rolling_avg  = power_series.rolling(window=window_seconds, min_periods=1).mean()
    fourth_power = rolling_avg ** 4
    np_value     = fourth_power.mean() ** 0.25
    return round(np_value, 1)


def compute_tss(
    normalized_power: float,
    ftp_watts: float,
    duration_seconds: int,
) -> float:
    """
    Calcule le Training Stress Score (TSS) de la sortie.

    TSS = (durée_s × NP × IF) / (FTP × 3600) × 100
    IF  = NP / FTP  (Intensity Factor)

    Interprétation du TSS :
        < 50   : sortie facile, récupération rapide
        50-100 : sortie modérée, fatigue le lendemain
        100-150: sortie difficile, 2-3 jours de récupération
        > 150  : sortie très difficile, > 3 jours
    """
    intensity_factor = normalized_power / ftp_watts
    tss = (duration_seconds * normalized_power * intensity_factor) / (ftp_watts * 3600) * 100
    return round(tss, 1)


# ─────────────────────────────────────────────
# 6. Fonction principale — pipeline complet
# ─────────────────────────────────────────────

def run_energy_model(
    df: pd.DataFrame,
    weight_kg: float,
    ftp_watts: float,
    ctl: float = 50.0,
) -> pd.DataFrame:
    """
    Colonnes attendues en entrée :
        - power        : puissance en watts
        - heartrate   : fréquence cardiaque en bpm
        - speed        : vitesse en km/h
        - altitude     : altitude en mètres
        - temperature  : température en °C

    Colonnes ajoutées en sortie :
        - kj_spent           : kJ métaboliques dépensés (cumulés)
        - kcal_spent         : kcal dépensées (cumulées)
        - energy_remaining   : % d'énergie restante (0-100)
        - time_remaining_min : temps restant estimé en minutes
        - hr_drift           : ratio puissance/FC lissé (signal de fatigue)
    """
    result = df.copy()

    kj_max = estimate_kj_max(weight_kg, ftp_watts, ctl)
    print(f"kJ_max estimé : {kj_max:.0f} kJ "
          f"({kj_to_kcal(kj_max):.0f} kcal) "
          f"pour {weight_kg}kg, FTP={ftp_watts}W, CTL={ctl}")

    result["kj_spent"]         = compute_kj_spent(result["power"])
    result["kcal_spent"]       = result["kj_spent"].apply(kj_to_kcal)
    result["energy_remaining"] = compute_energy_remaining(result["kj_spent"], kj_max)
    result["time_remaining_min"] = compute_time_remaining(
        result["energy_remaining"], kj_max, result["power"]
    )
    result["hr_drift"] = compute_hr_drift(result["power"], result["heartrate"])

    np_value = compute_normalized_power(result["power"])
    tss      = compute_tss(np_value, ftp_watts, len(result))
    print(f"NP : {np_value}W  |  IF : {np_value/ftp_watts:.2f}  |  TSS : {tss}")

    return result