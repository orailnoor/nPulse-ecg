import numpy as np
import pandas as pd
import scipy.signal as signal
import matplotlib.pyplot as plt
import requests
import re


def fetch_url(url):
    """Fetch content from a given URL."""
    try:
        response = requests.get(url)
        response.raise_for_status()
        return response.text
    except Exception as e:
        print(f"Error fetching URL: {e}")
        return None


def read_file_content(file_path):
    """Read text file from local storage."""
    try:
        with open(file_path, 'r') as file:
            return file.read().strip()  # Strip leading/trailing whitespace
    except FileNotFoundError:
        print("File not found. Please check the file path.")
        return None


def clean_text(text):
    """Remove unwanted strings and trim unnecessary parts."""
    if text:
        text = text.strip()
        text = re.sub(re.escape("Start nPULSE001"), "", text)
        text = re.sub(re.escape("Start"), "", text)
        return text[:-25] if len(text) > 25 else text  # Prevent slicing errors
    return ""


def process_lines(text):
    """Convert text data into a structured DataFrame."""
    if not text:
        return None

    line_1, line_2, line_3 = [], [], []

    for line in text.split('\n'):
        values = line.split(',')
        if len(values) >= 3:  # Ensure three columns exist
            line_1.append(values[0])
            line_2.append(values[1])
            line_3.append(values[2])

    if not line_1:  # If no valid data was extracted
        print("No valid data found in the file.")
        return None

    df = pd.DataFrame({'line_1': line_1, 'line_2': line_2, 'line_3': line_3})

    # Convert to numeric, coerce errors
    for col in df.columns:
        df[col] = pd.to_numeric(df[col], errors='coerce')  # Convert to numbers

    return df.dropna().astype('Int64')  # Drop NaNs and use Int64


def process_ppg_signal(ppg_signal, fs=220):
    """Process PPG signal to extract heart rate information."""
    if len(ppg_signal) < 10:  # Ensure enough data points
        print("Insufficient data for heart rate analysis.")
        return [], 0, 0, 0

    # 1. Preprocessing
    ppg_signal = ppg_signal - np.mean(ppg_signal)  # Remove DC offset
    std = np.std(ppg_signal)
    if std == 0:
        print("Signal is constant; cannot process.")
        return [], 0, 0, 0
    ppg_signal = ppg_signal / std  # Normalize

    # 2. Bandpass Filtering (0.5-8 Hz)
    b, a = signal.butter(4, [0.5 / (fs / 2), 8 / (fs / 2)], btype='bandpass')
    filtered_ppg = signal.filtfilt(b, a, ppg_signal)

    # 3. Peak Detection
    peaks, _ = signal.find_peaks(filtered_ppg, distance=fs * 0.5, prominence=0.5)

    # 4. Heart Rate Calculation
    if len(peaks) > 1:
        ibi = np.diff(peaks) / fs
        bpm_values = 72 / ibi
        bpm_values = bpm_values[(bpm_values > 40) & (bpm_values < 220)]  # Remove outliers

        max_bpm = np.max(bpm_values) if bpm_values.size else 0
        avg_bpm = np.mean(bpm_values) if bpm_values.size else 0
        min_bpm = np.min(bpm_values) if bpm_values.size else 0
    else:
        avg_bpm, min_bpm, max_bpm = 0, 0, 0

    return peaks, avg_bpm, min_bpm, max_bpm, filtered_ppg


def calculate_breaths_per_minute(df, sampling_rate=25):  # assumed sampling rate
    """Calculate breaths per minute from the first column of the DataFrame."""
    if df is None or df.empty:
        return None

    signal_data = df['line_1'].values

    # Apply a bandpass filter to remove noise
    low_cutoff = 0.1  # Hz
    high_cutoff = 0.5  # Hz
    nyquist_rate = sampling_rate / 2
    low_normalized = low_cutoff / nyquist_rate
    high_normalized = high_cutoff / nyquist_rate
    b, a = signal.butter(3, [low_normalized, high_normalized], btype='band')
    filtered_signal = signal.lfilter(b, a, signal_data)

    # Find peaks in the filtered signal (breathing peaks)
    peaks, _ = signal.find_peaks(filtered_signal, distance=sampling_rate * 2,
                                 prominence=0.1)

    # Calculate time differences between peaks
    if len(peaks) < 2:
        return None

    peak_intervals = np.diff(peaks) / sampling_rate  # Time in seconds

    # Calculate breaths per minute
    if len(peak_intervals) == 0:
        return None

    breaths_per_minute = 60 / np.mean(peak_intervals)

    return breaths_per_minute


# Main Program
while True:
    print("Press 'exit' to close.")
    user_input = input("Enter file's URL or local path: ")

    if user_input.lower() == "exit":
        break

    # Check if input is a URL or local file
    if user_input.startswith("http"):
        nadi_patient_data = fetch_url(user_input)
    else:
        nadi_patient_data = read_file_content(user_input)

    if not nadi_patient_data:
        continue  # If file read failed, restart loop

    cleaned_text = clean_text(nadi_patient_data)
    df = process_lines(cleaned_text)

    if df is None or "line_1" not in df:
        continue  # Restart loop if data processing failed

    # Convert column to numpy array
    ppg_signal = df["line_1"].to_numpy()

    # Process the PPG signal
    peaks, avg_bpm, min_bpm, max_bpm, filtered_ppg = process_ppg_signal(ppg_signal)

    breath = int(calculate_breaths_per_minute(df))

    # Create the peak plot
    plt.figure(figsize=(12, 6))
    plt.plot(filtered_ppg, label='Filtered PPG Signal')
    plt.plot(peaks, filtered_ppg[peaks], "rx", markersize=10, label='Detected Peaks')
    plt.title(f'--PPG Signal with Peak Detection-- \n Heart Rate: {avg_bpm:.2f} BPM \n Breath per Minute: {breath}')
    plt.xlabel('Sample Index')
    plt.ylabel('PPG Value')
    plt.legend()
    plt.show()

    # Display results
    print(f"Max Heart Rate: {max_bpm:.2f} BPM")
    print(f"Average Heart Rate: {avg_bpm:.2f} BPM")
    print(f"Lowest Heart Rate: {min_bpm:.2f} BPM")
    print(f"Breath per Minute: {breath} ")