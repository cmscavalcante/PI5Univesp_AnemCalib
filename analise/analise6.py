import pandas as pd
import numpy as np
import matplotlib.pyplot as plt

from scipy.signal import savgol_filter
from scipy.optimize import curve_fit
from scipy.optimize import least_squares


from pathlib import Path
import glob

# ============================================================
# CONFIGURAÇÕES
# ============================================================

CSV_FOLDER = "."
CSV_PATTERN = "Teste_*.csv"

MIN_SPEED = 8.0
MIN_FREQ = 1.0

RADIUS = 0.156
PULSES_PER_REV = 3

MAX_SPEED_PHYSICAL = 80.0

# ============================================================
# FUNÇÕES AUXILIARES
# ============================================================

def smooth_signal(x, window=21, poly=2):

    if len(x) < window:
        window = len(x) - 1

    if window % 2 == 0:
        window -= 1

    if window < 5:
        return x

    return savgol_filter(x, window, poly)


# ============================================================
# FILTRO ADAPTATIVO
# ============================================================

def adaptive_smooth(signal, speed):

    out = np.copy(signal)

    low = speed < 12
    mid = (speed >= 12) & (speed < 25)
    high = speed >= 25

    if np.sum(low) > 15:
        out[low] = smooth_signal(signal[low], 41, 2)

    if np.sum(mid) > 15:
        out[mid] = smooth_signal(signal[mid], 25, 2)

    if np.sum(high) > 15:
        out[high] = smooth_signal(signal[high], 11, 2)

    return out


# ============================================================
# MODELO EMPÍRICO
# ============================================================

def aero_model(f, a, b, c, f0):

    f = np.clip(f, 0.3, 100)

    return (
        a * f
        + b
        + c / (f + f0)
    )


# ============================================================
# MODELO TSR
# ============================================================

def lambda_model(v, lambda_min, lambda_max, k):

    v = np.clip(v, 0, 120)

    exp_arg = np.clip(
        -k * v,
        -50,
        50
    )

    return (
        lambda_min
        + (lambda_max - lambda_min)
        * (1 - np.exp(exp_arg))
    )


# ============================================================
# MODELO FÍSICO
# ============================================================

def estimate_speed_physical(
    freq,
    radius,
    pulses_per_rev,
    lambda_min,
    lambda_max,
    k_lambda
):

    if not np.isfinite(freq):
        return 0.0

    freq = np.clip(freq, 0.3, 100)

    f_rot = freq / pulses_per_rev

    omega = 2 * np.pi * f_rot

    lambda_nominal = (
        lambda_min
        + lambda_max
    ) * 0.5

    lambda_nominal = np.clip(
        lambda_nominal,
        0.15,
        1.0
    )

    v_ms = (
        omega * radius
    ) / lambda_nominal

    for _ in range(6):

        v_kmh = np.clip(
            v_ms * 3.6,
            0,
            120
        )

        lam = lambda_model(
            v_kmh,
            lambda_min,
            lambda_max,
            k_lambda
        )

        lam = np.clip(
            lam,
            0.15,
            1.5
        )

        v_new = (
            omega * radius
        ) / lam

        # amortecimento
        v_ms = (
            0.7 * v_ms
            + 0.3 * v_new
        )

    return np.clip(
        v_ms * 3.6,
        0,
        MAX_SPEED_PHYSICAL
    )


# ============================================================
# MODELO DINÂMICO COM INÉRCIA
# ============================================================

def dynamic_rotor_compensation(
    freq,
    accel,
    k_up,
    k_down,
    tau=0.6
):

    freq = np.asarray(freq)

    # proteção absoluta
    accel = np.clip(
        accel,
        -6.0,
        6.0
    )

    f_out = np.copy(freq)

    state = freq[0]

    for i in range(1, len(freq)):

        a = accel[i]

        if a >= 0:
            correction = k_up * a
        else:
            correction = k_down * a

        target = freq[i] + correction

        state = (
            (1 - tau) * state
            + tau * target
        )

        f_out[i] = state

    return np.clip(
        f_out,
        0.3,
        100
    )


# ============================================================
# AJUSTE ROBUSTO
# ============================================================

def limit_rate(x, max_delta):

    y = np.copy(x)

    for i in range(1, len(y)):

        delta = y[i] - y[i - 1]

        if delta > max_delta:
            y[i] = y[i - 1] + max_delta

        elif delta < -max_delta:
            y[i] = y[i - 1] - max_delta

    return y

def robust_fit(f, v):

    def residuals(params):

        a, b, c, f0 = params

        pred = aero_model(
            f,
            a,
            b,
            c,
            f0
        )

        return pred - v

    result = least_squares(
        residuals,
        x0=[2.5, 0.0, 1.0, 0.5],
        bounds=(
            [0, -20, 0, 0.01],
            [10, 20, 100, 10]
        ),
        loss='huber',
        f_scale=2.0,
        max_nfev=20000
    )

    return result.x


# ============================================================
# MODELO HÍBRIDO
# ============================================================

def hybrid_model(v_phys, v_emp):

    alpha = np.clip(
        1.0 - (v_phys / 40.0),
        0.15,
        0.85
    )

    return (
        alpha * v_phys
        + (1 - alpha) * v_emp
    )


# ============================================================
# LEITURA CSV
# ============================================================

def load_csv(file_path):

    print(f"Lendo: {file_path}")

    df = pd.read_csv(file_path)

    required = [
        "t_app",
        "freqHz",
        "vGps",
        "obd_speed",
        "accelX"
    ]

    for c in required:

        df[c] = pd.to_numeric(
            df[c],
            errors="coerce"
        )

    df = df.dropna(
        subset=["t_app", "freqHz"]
    )

    if len(df) < 20:
        return None

    return df


# ============================================================
# PROCESSAMENTO
# ============================================================

def process_dataframe(df):

    t = df["t_app"].values

    # garante monotonicidade temporal
    valid_t = np.diff(t, prepend=t[0]) >= 0

    t = t[valid_t]

    df = df.iloc[valid_t].reset_index(drop=True)

    dt = np.diff(t)

    print(
        "dt min/max:",
        np.min(dt),
        np.max(dt)
    )

    v_ref = np.where(
        df["vGps"] > 1.0,
        df["vGps"],
        df["obd_speed"]
    )

    v_ref = adaptive_smooth(
        v_ref,
        v_ref
    )

    f = df["freqHz"].values

    from scipy.signal import medfilt

    # remove glitches isolados
    f = medfilt(
        f,
        kernel_size=5
    )

    f_smooth = adaptive_smooth(
        f,
        v_ref
    )

    # ========================================================
    # REJEIÇÃO DE SPIKES TEMPORAIS
    # ========================================================

    dfreq = np.diff(
        f_smooth,
        prepend=f_smooth[0]
    )

    # limite máximo de variação instantânea
    MAX_FREQ_STEP = 3.0

    for i in range(1, len(f_smooth)):

        if abs(dfreq[i]) > MAX_FREQ_STEP:

            f_smooth[i] = (
                0.7 * f_smooth[i - 1]
                + 0.3 * f_smooth[i]
            )

    accel = df["accelX"].values

    accel = (
        accel
        - np.mean(accel[:100])
    )

    accel = smooth_signal(
        accel,
        31,
        2
    )

    # ========================================================
    # LIMITADOR FÍSICO DE ACELERAÇÃO
    # ========================================================

    # aceleração máxima plausível
    # ~ ±6 m/s² (~0.6g)

    MAX_ACCEL = 6.0

    accel = np.clip(
        accel,
        -MAX_ACCEL,
        MAX_ACCEL
    )

    return {
        "t": t,
        "f": f_smooth,
        "v": v_ref,
        "acc": accel
    }


# ============================================================
# PRINT EQUAÇÃO
# ============================================================

def print_aero_equation(params, name):

    a, b, c, f0 = params

    print("\n================================================")
    print(name)
    print("================================================")

    print(
        f"v(km/h) = "
        f"{a:.8f}·f + "
        f"{b:.8f} + "
        f"{c:.8f}/(f + {f0:.8f})"
    )

    print("\nParâmetros:")

    print(f"a  = {a:.12f}")
    print(f"b  = {b:.12f}")
    print(f"c  = {c:.12f}")
    print(f"f0 = {f0:.12f}")


# ============================================================
# LEITURA DOS CSVs
# ============================================================

csv_files = sorted(
    glob.glob(
        str(Path(CSV_FOLDER) / CSV_PATTERN)
    )
)

if len(csv_files) == 0:
    raise Exception(
        "Nenhum CSV encontrado."
    )

all_f = []
all_v = []
all_acc = []

datasets = []

# ============================================================
# PROCESSAMENTO
# ============================================================

for file in csv_files:

    df = load_csv(file)

    if df is None:
        continue

    data = process_dataframe(df)

    mask = (
        (data["v"] > MIN_SPEED)
        & (data["f"] > MIN_FREQ)
    )

    all_f.extend(
        data["f"][mask]
    )

    all_v.extend(
        data["v"][mask]
    )

    all_acc.extend(
        data["acc"][mask]
    )

    datasets.append(data)

# ============================================================
# ARRAYS
# ============================================================

all_f = np.array(all_f)
all_v = np.array(all_v)
all_acc = np.array(all_acc)

# ============================================================
# PESOS
# ============================================================

weights = np.ones_like(all_v)

weights[all_v <= 15] = 4.0

weights[
    (all_v > 15)
    & (all_v <= 30)
] = 2.0

weights[
    (all_v > 30)
    & (all_v <= 40)
] = 1.0

weights[all_v > 40] = 0.3

# ============================================================
# TSR
# ============================================================

f_rot = all_f / PULSES_PER_REV

omega = 2 * np.pi * f_rot

v_ms = all_v / 3.6

lambda_tsr = (
    omega * RADIUS
) / v_ms

valid_lambda = (
    np.isfinite(lambda_tsr)
    & (lambda_tsr > 0.05)
    & (lambda_tsr < 1.5)
    & (all_v > 8)
    & (all_v < 45)
)

lambda_valid = lambda_tsr[
    valid_lambda
]

v_valid = all_v[
    valid_lambda
]

print("\n================================================")
print("TIP SPEED RATIO")
print("================================================")

print(f"TSR médio   : {np.mean(lambda_valid):.3f}")
print(f"TSR mediano : {np.median(lambda_valid):.3f}")
print(f"TSR desvio  : {np.std(lambda_valid):.3f}")

# ============================================================
# AJUSTE lambda(v)
# ============================================================

popt_lambda, _ = curve_fit(
    lambda_model,
    v_valid,
    lambda_valid,
    p0=[0.08, 0.40, 0.08],
    bounds=(
        [0.03, 0.2, 0.005],
        [0.20, 0.8, 0.25]
    )
)

lambda_min, lambda_max, k_lambda = popt_lambda

print("\n================================================")
print("MODELO lambda(v)")
print("================================================")

print(
    f"lambda(v) = "
    f"{lambda_min:.4f} + "
    f"({lambda_max:.4f} - {lambda_min:.4f})"
    f"(1-exp(-{k_lambda:.4f}·v))"
)

# ============================================================
# AJUSTE ROBUSTO
# ============================================================

popt_raw = robust_fit(
    all_f,
    all_v
)

v_est_raw = aero_model(
    all_f,
    *popt_raw
)

residual = all_v - v_est_raw

mask_good = np.abs(residual) < 12

all_f = all_f[mask_good]
all_v = all_v[mask_good]
all_acc = all_acc[mask_good]
weights = weights[mask_good]

# RECALCULA após remoção dos outliers
v_est_raw = aero_model(
    all_f,
    *popt_raw
)

err2_raw = (
    all_v - v_est_raw
) ** 2

rms_raw = np.sqrt(
    np.mean(err2_raw)
)

# ============================================================
# OTIMIZAÇÃO DINÂMICA
# ============================================================

best_rms = 1e9

best_k_up = 0
best_k_down = 0

best_params = None

k_range = np.linspace(
    -0.12,
    0.12,
    30
)



for k_up in k_range:

    for k_down in k_range:

        if abs(k_down) > abs(k_up) * 1.2:
            continue

        f_test = dynamic_rotor_compensation(
            all_f,
            all_acc,
            k_up,
            k_down
        )

        try:

            popt = robust_fit(
                f_test,
                all_v
            )

            v_est = aero_model(
                f_test,
                *popt
            )

            rms = np.sqrt(
                np.mean(
                    (all_v - v_est) ** 2
                )
            )

            if rms < best_rms:

                best_rms = rms

                best_k_up = k_up
                best_k_down = k_down

                best_params = popt

        except:
            pass

# ============================================================
# RESULTADOS
# ============================================================

print("\n================================================")
print("RESULTADO DA OTIMIZAÇÃO")
print("================================================")

print(f"K_UP ótimo   : {best_k_up:.8f}")
print(f"K_DOWN ótimo : {best_k_down:.8f}")

print(f"RMS original : {rms_raw:.3f} km/h")
print(f"RMS melhor   : {best_rms:.3f} km/h")

print_aero_equation(
    popt_raw,
    "MODELO ORIGINAL"
)

print_aero_equation(
    best_params,
    "MODELO COMPENSADO"
)

# ============================================================
# CURVA
# ============================================================

f_plot = np.linspace(
    0.5,
    np.max(all_f) * 1.05,
    500
)

plt.figure(figsize=(12, 8))

plt.scatter(
    all_f,
    all_v,
    s=8,
    alpha=0.2,
    label="Dados"
)

plt.plot(
    f_plot,
    aero_model(
        f_plot,
        *popt_raw
    ),
    linewidth=3,
    label="Modelo robusto"
)

plt.plot(
    f_plot,
    aero_model(
        f_plot,
        *best_params
    ),
    linewidth=3,
    label="Modelo compensado"
)

plt.xlabel("Frequência [Hz]")
plt.ylabel("Velocidade [km/h]")

plt.title(
    "Curva do anemômetro"
)

plt.grid(True)
plt.legend()

plt.tight_layout()
plt.show()

# ============================================================
# TSR
# ============================================================

plt.figure(figsize=(10, 6))

plt.scatter(
    v_valid,
    lambda_valid,
    s=8,
    alpha=0.3
)

v_lambda_plot = np.linspace(
    0,
    np.max(v_valid),
    300
)

plt.plot(
    v_lambda_plot,
    lambda_model(
        v_lambda_plot,
        *popt_lambda
    ),
    linewidth=3
)

plt.xlabel("Velocidade [km/h]")
plt.ylabel("TSR lambda")

plt.title(
    "Tip Speed Ratio"
)

plt.grid(True)

plt.tight_layout()
plt.show()

# ============================================================
# RESPOSTA TEMPORAL
# ============================================================

plt.figure(figsize=(14, 8))

all_errors = []

for i, d in enumerate(datasets):

    f_dyn = dynamic_rotor_compensation(
        d["f"],
        d["acc"],
        best_k_up,
        best_k_down
    )

    v_emp = aero_model(
        f_dyn,
        *best_params
    )

    v_phys = []

    for f in f_dyn:

        v_phys.append(
            estimate_speed_physical(
                f,
                RADIUS,
                PULSES_PER_REV,
                lambda_min,
                lambda_max,
                k_lambda
            )
        )

    v_phys = np.array(v_phys)

    # ========================================================
    # MODELO HÍBRIDO
    # ========================================================

    v_hybrid = hybrid_model(
        v_phys,
        v_emp
    )

    v_hybrid = np.clip(
        v_hybrid,
        0,
        MAX_SPEED_PHYSICAL
    )

    v_hybrid = limit_rate(
        v_hybrid,
        2.5
    )

    # ========================================================
    # REMOÇÃO DE OUTLIER FINAL
    # ========================================================

    median = np.median(v_hybrid)

    for j in range(2, len(v_hybrid) - 2):

        local = v_hybrid[j-2:j+3]

        med = np.median(local)

        if abs(v_hybrid[j] - med) > 12:

            v_hybrid[j] = med

    err = d["v"] - v_hybrid

    all_errors.extend(err)

    # ============================================================
# DEBUG SPIKES
# ============================================================

for i, d in enumerate(datasets):

    f_dyn = dynamic_rotor_compensation(
        d["f"],
        d["acc"],
        best_k_up,
        best_k_down
    )

    v_emp = aero_model(
        f_dyn,
        *best_params
    )

    v_phys = []

    for f in f_dyn:

        v_phys.append(
            estimate_speed_physical(
                f,
                RADIUS,
                PULSES_PER_REV,
                lambda_min,
                lambda_max,
                k_lambda
            )
        )

    v_phys = np.array(v_phys)

    v_hybrid = hybrid_model(
        v_phys,
        v_emp
    )

    # procura spikes
    idx = np.where(v_hybrid > 120)[0]

    if len(idx) > 0:

        print("\n===================================")
        print(f"SPIKES DATASET {i}")
        print("===================================")

        for k in idx[:20]:

            print(
                f"i={k}  "
                f"t={d['t'][k]:.2f}  "
                f"f={d['f'][k]:.3f}  "
                f"acc={d['acc'][k]:.3f}  "
                f"f_dyn={f_dyn[k]:.3f}  "
                f"v_emp={v_emp[k]:.3f}  "
                f"v_phys={v_phys[k]:.3f}  "
                f"v_hybrid={v_hybrid[k]:.3f}"
            )

    if i == 0:

        plt.plot(
            d["t"],
            d["v"],
            linewidth=2,
            label="Referência"
        )

        plt.plot(
            d["t"],
            v_emp,
            linewidth=1.2,
            label="Empírico"
        )

        plt.plot(
            d["t"],
            v_phys,
            linewidth=1.2,
            label="Físico"
        )

        plt.plot(
            d["t"],
            v_hybrid,
            linewidth=2,
            label="Híbrido"
        )

    else:

        plt.plot(d["t"], d["v"], linewidth=2)
        plt.plot(d["t"], v_emp, linewidth=1.2)
        plt.plot(d["t"], v_phys, linewidth=1.2)
        plt.plot(d["t"], v_hybrid, linewidth=2)

plt.xlabel("Tempo [s]")
plt.ylabel("Velocidade [km/h]")

plt.title(
    "Resposta temporal"
)

plt.grid(True)
plt.legend()

plt.tight_layout()
plt.show()

# ============================================================
# HISTOGRAMA DE ERRO
# ============================================================

all_errors = np.array(all_errors)

plt.figure(figsize=(10, 6))

plt.hist(
    all_errors,
    bins=60
)

plt.xlabel("Erro [km/h]")
plt.ylabel("Ocorrências")

plt.title(
    "Histograma de erro"
)

plt.grid(True)

plt.tight_layout()
plt.show()

# ============================================================
# ERRO x VELOCIDADE
# ============================================================

all_est = aero_model(
    all_f,
    *best_params
)

errors = all_v - all_est

plt.figure(figsize=(10, 6))

plt.scatter(
    all_v,
    errors,
    s=8,
    alpha=0.3
)

plt.axhline(
    0,
    linestyle="--"
)

plt.xlabel("Velocidade [km/h]")
plt.ylabel("Erro [km/h]")

plt.title(
    "Erro x velocidade"
)

plt.grid(True)

plt.tight_layout()
plt.show()