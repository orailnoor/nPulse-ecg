import matplotlib.pyplot as plt

# Sampling rate in Hz (samples per second)
SAMPLING_RATE = 125  # 7488 samples / 60 seconds ≈ 125 Hz

def load_ecg_data(file_path):

    sensor1 = []
    sensor2 = []
    sensor3 = []

    with open(file_path, 'r') as file:
        for line in file:
            if line.strip():
                parts = line.strip().split(',')
                if len(parts) >= 3:
                    try:
                        sensor1.append(int(parts[0]))
                        sensor2.append(int(parts[1]))
                        sensor3.append(int(parts[2]))
                    except ValueError:
                        continue  # Skip lines that can't be parsed

    return sensor1, sensor2, sensor3


def plot_ecg(sensor1, sensor2, sensor3, sampling_rate=SAMPLING_RATE):
    fig, axes = plt.subplots(3, 1, figsize=(24, 10), sharex=True)
    
    total_samples = len(sensor1)
    duration = total_samples / 60
    
    # Sensor 1
    axes[0].plot(sensor1, linewidth=0.9, color='#e74c3c')
    axes[0].set_ylabel("Sensor 1", fontsize=12)
    axes[0].set_title(f"ECG Signal — Sampling Rate: {sampling_rate} Hz | Samples: {total_samples} | Duration: {duration:.1f}s", 
                      fontsize=14, fontweight='bold')
    axes[0].grid(True, alpha=0.3)
    
    # Sensor 2
    axes[1].plot(sensor2, linewidth=0.9, color='#3498db')
    axes[1].set_ylabel("Sensor 2", fontsize=12)
    axes[1].grid(True, alpha=0.3)
    
    # Sensor 3
    axes[2].plot(sensor3, linewidth=0.9, color='#2ecc71')
    axes[2].set_ylabel("Sensor 3", fontsize=12)
    axes[2].set_xlabel("Sample Index", fontsize=12)
    axes[2].grid(True, alpha=0.3)
    
    plt.tight_layout()
    plt.show()


if __name__ == "__main__":
    file_path = "nadi_data-oldashanewcode-testing.txt"
    s1, s2, s3 = load_ecg_data(file_path)
    plot_ecg(s1, s2, s3)
