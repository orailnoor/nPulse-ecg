"""
ECG Signal Processor
Handles ECG/PPG signal processing and analysis.
Refactored from main.py for modular use.
"""

import numpy as np
import pandas as pd
import scipy.signal as signal
import matplotlib.pyplot as plt
from matplotlib.figure import Figure
from matplotlib.backends.backend_agg import FigureCanvasAgg
import re
import requests
from typing import Optional, Tuple, List, Dict
from io import BytesIO


def fetch_url(url: str) -> Optional[str]:
    """Fetch content from a given URL."""
    try:
        response = requests.get(url)
        response.raise_for_status()
        return response.text
    except Exception as e:
        print(f"Error fetching URL: {e}")
        return None


def read_file_content(file_path: str) -> Optional[str]:
    """Read text file from local storage."""
    try:
        with open(file_path, 'r') as file:
            return file.read().strip()
    except FileNotFoundError:
        print("File not found. Please check the file path.")
        return None
    except Exception as e:
        print(f"Error reading file: {e}")
        return None


def clean_text(text: str) -> str:
    """Remove unwanted strings and trim unnecessary parts."""
    if text:
        text = text.strip()
        text = re.sub(re.escape("Start nPULSE001"), "", text)
        text = re.sub(re.escape("Start"), "", text)
        # Remove last 25 chars if text is long enough
        return text[:-25] if len(text) > 25 else text
    return ""


def process_lines(text: str) -> Optional[pd.DataFrame]:
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
    
    if not line_1:
        print("No valid data found in the file.")
        return None

    df = pd.DataFrame({'line_1': line_1, 'line_2': line_2, 'line_3': line_3})

    # Convert to numeric, coerce errors
    for col in df.columns:
        df[col] = pd.to_numeric(df[col], errors='coerce')
    
    return df.dropna().astype('Int64')


def process_ppg_signal(ppg_signal: np.ndarray, fs: int = 220) -> Tuple[np.ndarray, float, float, float, np.ndarray]:
    """
    Process PPG signal to extract heart rate information.
    
    Args:
        ppg_signal: Raw PPG signal array
        fs: Sampling frequency in Hz
        
    Returns:
        Tuple of (peaks, avg_bpm, min_bpm, max_bpm, filtered_signal)
    """
    if len(ppg_signal) < 10:
        print("Insufficient data for heart rate analysis.")
        return np.array([]), 0, 0, 0, np.array([])
    
    # 1. Preprocessing
    ppg_signal = ppg_signal - np.mean(ppg_signal)  # Remove DC offset
    std = np.std(ppg_signal)
    if std == 0:
        print("Signal is constant; cannot process.")
        return np.array([]), 0, 0, 0, np.array([])
    ppg_signal = ppg_signal / std  # Normalize

    # 2. Bandpass Filtering (0.5-8 Hz)
    b, a = signal.butter(4, [0.5 / (fs / 2), 8 / (fs / 2)], btype='bandpass')
    filtered_ppg = signal.filtfilt(b, a, ppg_signal)

    # 3. Peak Detection
    peaks, _ = signal.find_peaks(filtered_ppg, distance=fs * 0.5, prominence=0.5)

    # 4. Heart Rate Calculation
    if len(peaks) > 1:
        ibi = np.diff(peaks) / fs
        bpm_values = 73 / ibi
        bpm_values = bpm_values[(bpm_values > 40) & (bpm_values < 220)]  # Remove outliers

        max_bpm = np.max(bpm_values) if bpm_values.size else 0
        avg_bpm = np.mean(bpm_values) if bpm_values.size else 0
        min_bpm = np.min(bpm_values) if bpm_values.size else 0
    else:
        avg_bpm, min_bpm, max_bpm = 0, 0, 0

    return peaks, avg_bpm, min_bpm, max_bpm, filtered_ppg


def analyze_ecg_file(file_path: str) -> Optional[Dict]:
    """
    Analyze an ECG data file and return results.
    
    Args:
        file_path: Path to the ECG data file
        
    Returns:
        Dictionary with analysis results or None if failed
    """
    # Read file
    if file_path.startswith("http"):
        nadi_patient_data = fetch_url(file_path)
    else:
        nadi_patient_data = read_file_content(file_path)

    if not nadi_patient_data:
        return None
    
    cleaned_text = clean_text(nadi_patient_data)
    df = process_lines(cleaned_text)
    
    if df is None or "line_1" not in df:
        return None

    # Process all 3 sensors
    sensor_columns = ["line_1", "line_2", "line_3"]
    hr_results = []
    all_bpm_values = []
    
    for i, col in enumerate(sensor_columns):
        sensor_signal = df[col].to_numpy()
        
        # Trim 500 data points from start and end if there are enough points
        if len(sensor_signal) > 1000:
            sensor_signal = sensor_signal[500:-500]
        else:
            print(f"Not enough data points to trim for Sensor {i+1}.")
            hr_results.append({'avg': 0, 'min': 0, 'max': 0})
            continue
        
        # Process the signal
        peaks, avg_bpm, min_bpm, max_bpm, filtered_signal = process_ppg_signal(sensor_signal)
        
        hr_results.append({
            'avg': avg_bpm,
            'min': min_bpm,
            'max': max_bpm
        })
        
        # Collect BPM values for combined calculation
        if len(peaks) > 1:
            ibi = np.diff(peaks) / 220  # Using default fs
            bpm_values = 73 / ibi
            bpm_values = bpm_values[(bpm_values > 40) & (bpm_values < 220)]
            all_bpm_values.extend(bpm_values.tolist())
    
    # Calculate combined HR from all sensors
    if all_bpm_values:
        combined_hr = {
            'avg': np.mean(all_bpm_values),
            'min': np.min(all_bpm_values),
            'max': np.max(all_bpm_values)
        }
    else:
        combined_hr = {'avg': 0, 'min': 0, 'max': 0}

    return {
        'dataframe': df,
        'hr_results': hr_results,
        'combined_hr': combined_hr,
        'total_samples': len(df),
        'sampling_rate': len(df) / 60  # Assuming 60 second recording
    }


def create_ecg_plot(df: pd.DataFrame, hr_results: List[Dict], combined_hr: Dict, 
                    save_path: Optional[str] = None) -> Figure:
    """
    Create ECG plot with all 3 sensors.
    
    Args:
        df: DataFrame with sensor data
        hr_results: List of HR results for each sensor
        combined_hr: Combined HR results
        save_path: Optional path to save the plot
        
    Returns:
        Matplotlib Figure object
    """
    sensor1 = df["line_1"].to_numpy()
    sensor2 = df["line_2"].to_numpy()
    sensor3 = df["line_3"].to_numpy()
    
    # Hardcoded duration of 60 seconds to measure sampling rate
    DURATION_SECONDS = 60
    total_samples = len(sensor1)
    calculated_sampling_rate = total_samples / DURATION_SECONDS
    
    fig, axes = plt.subplots(3, 1, figsize=(16, 10), sharex=True)
    
    colors = ['#e74c3c', '#3498db', '#2ecc71']
    sensors = [sensor1, sensor2, sensor3]
    sensor_names = ['Sensor 1', 'Sensor 2', 'Sensor 3']
    
    for i, (sensor, name, color, hr) in enumerate(zip(sensors, sensor_names, colors, hr_results)):
        axes[i].plot(sensor, linewidth=0.9, color=color)
        axes[i].set_ylabel(name, fontsize=12)
        axes[i].set_title(f"{name} — Avg HR: {hr['avg']:.2f} BPM | Min: {hr['min']:.2f} | Max: {hr['max']:.2f}", 
                          fontsize=12, fontweight='bold')
        axes[i].grid(True, alpha=0.3)
    
    axes[2].set_xlabel("Sample Index", fontsize=12)
    
    # Add main title with sampling rate and combined HR
    fig.suptitle(f"ECG Signal — Sampling Rate: {calculated_sampling_rate:.2f} Hz | Samples: {total_samples} | Duration: {DURATION_SECONDS}s\n"
                 f"COMBINED HR — Avg: {combined_hr['avg']:.2f} BPM | Min: {combined_hr['min']:.2f} | Max: {combined_hr['max']:.2f}", 
                 fontsize=14, fontweight='bold', y=1.02)
    
    plt.tight_layout()
    
    if save_path:
        plt.savefig(save_path, dpi=150, bbox_inches='tight')
        print(f"Plot saved to {save_path}")
    
    return fig


def format_hr_results(hr_results: List[Dict], combined_hr: Dict) -> str:
    """Format HR results as a string for display."""
    output = []
    sensor_names = ['Sensor 1', 'Sensor 2', 'Sensor 3']
    
    for name, hr in zip(sensor_names, hr_results):
        output.append(f"{name}: Avg {hr['avg']:.1f} | Min {hr['min']:.1f} | Max {hr['max']:.1f} BPM")
    
    output.append(f"\nCombined: Avg {combined_hr['avg']:.1f} | Min {combined_hr['min']:.1f} | Max {combined_hr['max']:.1f} BPM")
    
    return '\n'.join(output)


if __name__ == "__main__":
    # Test with a sample file
    import sys
    
    if len(sys.argv) > 1:
        file_path = sys.argv[1]
    else:
        file_path = "files/nadi_data_clean_data.txt"
    
    print(f"Analyzing: {file_path}")
    results = analyze_ecg_file(file_path)
    
    if results:
        print("\n" + "="*50)
        print("ANALYSIS RESULTS")
        print("="*50)
        print(f"Total Samples: {results['total_samples']}")
        print(f"Sampling Rate: {results['sampling_rate']:.2f} Hz")
        print("\n" + format_hr_results(results['hr_results'], results['combined_hr']))
        
        # Create and show plot
        fig = create_ecg_plot(
            results['dataframe'], 
            results['hr_results'], 
            results['combined_hr'],
            save_path="Heart Beat Plot.png"
        )
        plt.show()
    else:
        print("Analysis failed. Check file path and data format.")
