"""
nPulse ECG Analyzer - Web GUI Application with Real-Time BLE Graphing
Web-based GUI for ECG data collection and analysis using Flask.
Features real-time ECG visualization during BLE data collection.
"""

import os
import json
import base64
import asyncio
import threading
import queue
from io import BytesIO
from datetime import datetime
from flask import Flask, render_template_string, request, jsonify, send_file, Response
import matplotlib
matplotlib.use('Agg')  # Non-GUI backend
import matplotlib.pyplot as plt

# Import our modules
from ecg_processor import analyze_ecg_file, create_ecg_plot, format_hr_results
from ble_handler import BLEHandler

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = 'files'
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max

# Ensure upload folder exists
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

# Store last analysis results
last_results = {}

# BLE state
ble_handler = None
ble_data_queue = queue.Queue()
ble_status = {
    'scanning': False,
    'connected': False,
    'collecting': False,
    'device_name': None,
    'battery': 0,
    'sample_count': 0,
    'devices': []
}

HTML_TEMPLATE = '''
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>🫀 nPulse ECG Analyzer</title>
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
    <script src="https://cdn.jsdelivr.net/npm/hammerjs@2.0.8"></script>
    <script src="https://cdn.jsdelivr.net/npm/chartjs-plugin-zoom@2.0.1"></script>
    <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }
        
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, sans-serif;
            background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%);
            min-height: 100vh;
            color: #eaeaea;
            padding: 20px;
        }
        
        .container {
            max-width: 1400px;
            margin: 0 auto;
        }
        
        h1 {
            text-align: center;
            font-size: 2.5rem;
            margin-bottom: 30px;
            background: linear-gradient(90deg, #ff6b6b, #feca57, #48dbfb, #ff9ff3);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            background-clip: text;
        }
        
        .tabs {
            display: flex;
            gap: 10px;
            margin-bottom: 20px;
        }
        
        .tab-btn {
            background: rgba(255, 255, 255, 0.1);
            border: none;
            color: #eaeaea;
            padding: 12px 24px;
            border-radius: 8px;
            cursor: pointer;
            font-size: 1rem;
            transition: all 0.3s;
        }
        
        .tab-btn:hover {
            background: rgba(255, 255, 255, 0.2);
        }
        
        .tab-btn.active {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        }
        
        .tab-content {
            display: none;
        }
        
        .tab-content.active {
            display: block;
        }
        
        .card {
            background: rgba(255, 255, 255, 0.05);
            border-radius: 16px;
            padding: 24px;
            margin-bottom: 20px;
            backdrop-filter: blur(10px);
            border: 1px solid rgba(255, 255, 255, 0.1);
        }
        
        .card h2 {
            font-size: 1.3rem;
            margin-bottom: 20px;
            color: #48dbfb;
        }
        
        .upload-area {
            border: 2px dashed rgba(255, 255, 255, 0.3);
            border-radius: 12px;
            padding: 40px;
            text-align: center;
            cursor: pointer;
            transition: all 0.3s ease;
        }
        
        .upload-area:hover {
            border-color: #48dbfb;
            background: rgba(72, 219, 251, 0.1);
        }
        
        input[type="file"] {
            display: none;
        }
        
        .btn {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            border: none;
            padding: 12px 28px;
            border-radius: 8px;
            font-size: 1rem;
            cursor: pointer;
            transition: transform 0.2s, box-shadow 0.2s;
            margin: 10px 5px;
        }
        
        .btn:hover {
            transform: translateY(-2px);
            box-shadow: 0 10px 20px rgba(102, 126, 234, 0.3);
        }
        
        .btn:disabled {
            opacity: 0.5;
            cursor: not-allowed;
            transform: none;
        }
        
        .btn-primary {
            background: linear-gradient(135deg, #11998e 0%, #38ef7d 100%);
        }
        
        .btn-secondary {
            background: linear-gradient(135deg, #f093fb 0%, #f5576c 100%);
        }
        
        .btn-danger {
            background: linear-gradient(135deg, #eb3349 0%, #f45c43 100%);
        }
        
        .btn-scan {
            background: linear-gradient(135deg, #4facfe 0%, #00f2fe 100%);
        }
        
        
        .results-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 16px;
            margin-top: 20px;
        }
        
        .result-box {
            background: rgba(255, 255, 255, 0.08);
            border-radius: 12px;
            padding: 20px;
            text-align: center;
        }
        
        .result-box .value {
            font-size: 2rem;
            font-weight: bold;
            color: #48dbfb;
        }
        
        .result-box .label {
            font-size: 0.9rem;
            color: #ffffff;
            margin-top: 5px;
        }
        
        .result-box.sensor1 .value { color: #e74c3c; }
        .result-box.sensor2 .value { color: #3498db; }
        .result-box.sensor3 .value { color: #2ecc71; }
        .result-box.combined .value { color: #feca57; }
        
        .plot-container {
            text-align: center;
            margin-top: 20px;
        }
        
        .plot-container img {
            max-width: 100%;
            border-radius: 12px;
            box-shadow: 0 10px 40px rgba(0, 0, 0, 0.3);
        }
        
        /* ===== Professional ECG Graph Styling ===== */
        .analysis-chart-container {
            background: linear-gradient(145deg, #0a1628 0%, #0d1f3c 100%);
            border-radius: 16px;
            padding: 24px;
            margin-top: 20px;
            min-height: 600px;
            border: 1px solid rgba(72, 219, 251, 0.2);
            box-shadow: 0 8px 32px rgba(0, 0, 0, 0.4);
        }
        
        /* ECG Control Panel */
        .ecg-control-panel {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 16px;
            margin-bottom: 20px;
            padding: 16px;
            background: rgba(255, 255, 255, 0.03);
            border-radius: 12px;
            border: 1px solid rgba(255, 255, 255, 0.08);
        }
        
        .control-group {
            display: flex;
            flex-direction: column;
            gap: 8px;
        }
        
        .control-group-label {
            font-size: 0.75rem;
            text-transform: uppercase;
            letter-spacing: 1px;
            color: #48dbfb;
            font-weight: 600;
        }
        
        .control-group-content {
            display: flex;
            gap: 8px;
            flex-wrap: wrap;
            align-items: center;
        }
        
        .ecg-btn {
            padding: 8px 14px;
            border-radius: 6px;
            border: 1px solid rgba(255, 255, 255, 0.15);
            background: rgba(255, 255, 255, 0.05);
            color: #bbb;
            font-size: 0.85rem;
            cursor: pointer;
            transition: all 0.2s;
        }
        
        .ecg-btn:hover {
            background: rgba(255, 255, 255, 0.1);
            color: #fff;
        }
        
        .ecg-btn.active {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            border-color: transparent;
            color: #fff;
        }
        
        .ecg-btn-icon {
            padding: 8px 12px;
            font-size: 1rem;
        }
        
        /* Sensor Toggle Buttons */
        .sensor-toggle {
            padding: 6px 12px;
            border-radius: 6px;
            border: 2px solid;
            background: transparent;
            font-size: 0.8rem;
            font-weight: 600;
            cursor: pointer;
            transition: all 0.2s;
            opacity: 0.4;
        }
        
        .sensor-toggle.active {
            opacity: 1;
        }
        
        .sensor-toggle.sensor1 {
            border-color: #e74c3c;
            color: #e74c3c;
        }
        
        .sensor-toggle.sensor1.active {
            background: rgba(231, 76, 60, 0.2);
        }
        
        .sensor-toggle.sensor2 {
            border-color: #3498db;
            color: #3498db;
        }
        
        .sensor-toggle.sensor2.active {
            background: rgba(52, 152, 219, 0.2);
        }
        
        .sensor-toggle.sensor3 {
            border-color: #2ecc71;
            color: #2ecc71;
        }
        
        .sensor-toggle.sensor3.active {
            background: rgba(46, 204, 113, 0.2);
        }
        
        /* ECG Input Fields */
        .ecg-input {
            padding: 8px 12px;
            border-radius: 6px;
            border: 1px solid rgba(255, 255, 255, 0.15);
            background: rgba(0, 0, 0, 0.3);
            color: #fff;
            font-size: 0.9rem;
            width: 100px;
            text-align: center;
        }
        
        .ecg-input:focus {
            outline: none;
            border-color: #48dbfb;
            box-shadow: 0 0 0 2px rgba(72, 219, 251, 0.2);
        }
        
        /* ECG Range Slider */
        .ecg-range {
            -webkit-appearance: none;
            appearance: none;
            width: 100%;
            height: 6px;
            background: rgba(255, 255, 255, 0.1);
            border-radius: 3px;
            outline: none;
        }
        
        .ecg-range::-webkit-slider-thumb {
            -webkit-appearance: none;
            appearance: none;
            width: 18px;
            height: 18px;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            border-radius: 50%;
            cursor: pointer;
            box-shadow: 0 2px 8px rgba(102, 126, 234, 0.5);
        }
        
        .ecg-range::-moz-range-thumb {
            width: 18px;
            height: 18px;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            border-radius: 50%;
            cursor: pointer;
            border: none;
            box-shadow: 0 2px 8px rgba(102, 126, 234, 0.5);
        }
        
        /* ECG Chart Canvas Container */
        .ecg-canvas-wrapper {
            position: relative;
            background: 
                /* Small grid (1mm equivalent) */
                linear-gradient(rgba(255, 182, 193, 0.08) 1px, transparent 1px),
                linear-gradient(90deg, rgba(255, 182, 193, 0.08) 1px, transparent 1px),
                /* Large grid (5mm equivalent) */
                linear-gradient(rgba(255, 182, 193, 0.15) 1px, transparent 1px),
                linear-gradient(90deg, rgba(255, 182, 193, 0.15) 1px, transparent 1px),
                /* Background */
                linear-gradient(135deg, #0a0a12 0%, #0d1520 100%);
            background-size:
                10px 10px,
                10px 10px,
                50px 50px,
                50px 50px,
                100% 100%;
            border-radius: 12px;
            padding: 16px;
            border: 1px solid rgba(255, 255, 255, 0.1);
        }
        
        #analysisChart {
            width: 100% !important;
            height: 450px !important;
        }
        
        /* ECG Info Bar */
        .ecg-info-bar {
            display: flex;
            justify-content: space-between;
            align-items: center;
            padding: 12px 16px;
            margin-top: 12px;
            background: rgba(0, 0, 0, 0.3);
            border-radius: 8px;
            flex-wrap: wrap;
            gap: 12px;
        }
        
        .ecg-info-item {
            display: flex;
            align-items: center;
            gap: 8px;
            font-size: 0.85rem;
            color: #bbb;
        }
        
        .ecg-info-value {
            font-weight: 600;
            color: #48dbfb;
            font-family: 'SF Mono', 'Monaco', 'Consolas', monospace;
        }
        
        /* Timeline Navigation */
        .ecg-timeline {
            margin-top: 16px;
            padding: 16px;
            background: rgba(255, 255, 255, 0.03);
            border-radius: 8px;
        }
        
        .ecg-timeline-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 12px;
        }
        
        .ecg-timeline-label {
            font-size: 0.8rem;
            color: #888;
        }
        
        .ecg-timeline-position {
            font-size: 0.85rem;
            color: #48dbfb;
            font-family: 'SF Mono', 'Monaco', 'Consolas', monospace;
        }
        
        /* Navigation Buttons */
        .ecg-nav-buttons {
            display: flex;
            gap: 8px;
            align-items: center;
        }
        
        .ecg-nav-btn {
            width: 36px;
            height: 36px;
            border-radius: 8px;
            border: 1px solid rgba(255, 255, 255, 0.15);
            background: rgba(255, 255, 255, 0.05);
            color: #bbb;
            font-size: 1rem;
            cursor: pointer;
            display: flex;
            align-items: center;
            justify-content: center;
            transition: all 0.2s;
        }
        
        .ecg-nav-btn:hover {
            background: rgba(255, 255, 255, 0.1);
            color: #fff;
        }
        
        .ecg-nav-btn:active {
            transform: scale(0.95);
        }
        
        /* Measurement Display */
        .ecg-measurements {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
            gap: 12px;
            margin-top: 16px;
        }
        
        .ecg-measurement-card {
            background: linear-gradient(135deg, rgba(255, 255, 255, 0.05) 0%, rgba(255, 255, 255, 0.02) 100%);
            border-radius: 10px;
            padding: 14px;
            border: 1px solid rgba(255, 255, 255, 0.08);
        }
        
        .ecg-measurement-label {
            font-size: 0.7rem;
            text-transform: uppercase;
            letter-spacing: 0.5px;
            color: #888;
            margin-bottom: 4px;
        }
        
        .ecg-measurement-value {
            font-size: 1.3rem;
            font-weight: 700;
            font-family: 'SF Mono', 'Monaco', 'Consolas', monospace;
        }
        
        .ecg-measurement-unit {
            font-size: 0.8rem;
            color: #888;
            font-weight: 400;
            margin-left: 4px;
        }
        
        /* Sensor colors for measurement cards */
        .ecg-measurement-card.sensor1 .ecg-measurement-value { color: #e74c3c; }
        .ecg-measurement-card.sensor2 .ecg-measurement-value { color: #3498db; }
        .ecg-measurement-card.sensor3 .ecg-measurement-value { color: #2ecc71; }
        .ecg-measurement-card.combined .ecg-measurement-value { color: #feca57; }
        
        /* Help tooltip */
        .ecg-help {
            display: flex;
            align-items: center;
            gap: 6px;
            padding: 8px 12px;
            background: rgba(72, 219, 251, 0.1);
            border-radius: 6px;
            font-size: 0.8rem;
            color: #48dbfb;
        }
        
        .ecg-help-icon {
            font-size: 1rem;
        }
        
        /* Chart Controls (bottom bar) */
        .chart-controls {
            margin-top: 16px;
            display: flex;
            justify-content: space-between;
            align-items: center;
            flex-wrap: wrap;
            gap: 12px;
        }
        
        .chart-controls-hint {
            display: flex;
            align-items: center;
            gap: 16px;
            color: #888;
            font-size: 0.8rem;
            flex-wrap: wrap;
        }
        
        .hint-item {
            display: flex;
            align-items: center;
            gap: 6px;
        }
        
        .hint-key {
            padding: 3px 8px;
            background: rgba(255, 255, 255, 0.1);
            border-radius: 4px;
            font-family: 'SF Mono', 'Monaco', 'Consolas', monospace;
            font-size: 0.75rem;
            color: #bbb;
        }
        
        /* Chart Legend - Hide default as we have sensor toggles */
        .chart-legend {
            display: none;
        }
        
        .status {
            padding: 12px 20px;
            border-radius: 8px;
            margin: 10px 0;
            display: none;
        }
        
        .status.success {
            background: rgba(46, 204, 113, 0.2);
            border: 1px solid #2ecc71;
            display: block;
        }
        
        .status.error {
            background: rgba(231, 76, 60, 0.2);
            border: 1px solid #e74c3c;
            display: block;
        }
        
        .status.loading {
            background: rgba(52, 152, 219, 0.2);
            border: 1px solid #3498db;
            display: block;
        }
        
        .spinner {
            display: inline-block;
            width: 20px;
            height: 20px;
            border: 3px solid rgba(255,255,255,0.3);
            border-radius: 50%;
            border-top-color: #fff;
            animation: spin 1s ease-in-out infinite;
            margin-right: 10px;
            vertical-align: middle;
        }
        
        @keyframes spin {
            to { transform: rotate(360deg); }
        }
        
        /* BLE Controls */
        .ble-controls {
            display: flex;
            flex-wrap: wrap;
            gap: 10px;
            align-items: center;
            margin-bottom: 20px;
        }
        
        .device-select {
            padding: 10px 16px;
            border-radius: 8px;
            border: 1px solid rgba(255,255,255,0.2);
            background: rgba(255,255,255,0.1);
            color: #eaeaea;
            font-size: 1rem;
            min-width: 250px;
        }
        
        .ble-status {
            display: flex;
            gap: 20px;
            margin-top: 15px;
        }
        
        .ble-status-item {
            display: flex;
            align-items: center;
            gap: 8px;
        }
        
        .status-dot {
            width: 12px;
            height: 12px;
            border-radius: 50%;
            background: #666;
        }
        
        .status-dot.connected {
            background: #2ecc71;
            box-shadow: 0 0 10px #2ecc71;
        }
        
        .status-dot.scanning {
            background: #f39c12;
            animation: pulse 1s infinite;
        }
        
        .status-dot.collecting {
            background: #e74c3c;
            animation: pulse 0.5s infinite;
        }
        
        @keyframes pulse {
            0%, 100% { opacity: 1; }
            50% { opacity: 0.5; }
        }
        
        /* Real-time chart */
        .realtime-chart-container {
            background: rgba(0,0,0,0.3);
            border-radius: 12px;
            padding: 20px;
            margin-top: 20px;
        }
        
        #realtimeChart {
            max-height: 400px;
        }
        
        .chart-stats {
            display: grid;
            grid-template-columns: repeat(4, 1fr);
            gap: 15px;
            margin-top: 20px;
        }
        
        .chart-stat {
            background: rgba(255,255,255,0.05);
            padding: 15px;
            border-radius: 8px;
            text-align: center;
        }
        
        .chart-stat .value {
            font-size: 1.5rem;
            font-weight: bold;
        }
        
        .chart-stat .label {
            color: #ffffff;
            font-size: 0.85rem;
        }
        
        .duration-input {
            padding: 10px 16px;
            border-radius: 8px;
            border: 1px solid rgba(255,255,255,0.2);
            background: rgba(255,255,255,0.1);
            color: #eaeaea;
            font-size: 1rem;
            width: 80px;
            text-align: center;
        }
    </style>
</head>
<body>
    <div class="container">
        <h1>🫀 nPulse ECG Analyzer</h1>
        
        <!-- Tabs -->
        <div class="tabs">
            <button class="tab-btn active" onclick="showTab('realtime')">📡 Real-Time Collection</button>
            <button class="tab-btn" onclick="showTab('analysis')">📊 File Analysis</button>
        </div>
        
        <!-- Real-Time Collection Tab -->
        <div id="realtime-tab" class="tab-content active">
            <div class="card">
                <h2>📡 BLE Device Control</h2>
                
                <div class="ble-controls">
                    <button class="btn btn-scan" id="scanBtn" onclick="scanDevices()">
                        🔍 Scan for Devices
                    </button>
                    
                    <select class="device-select" id="deviceSelect">
                        <option value="">Select a device...</option>
                    </select>
                    
                    <button class="btn btn-primary" id="connectBtn" onclick="connectDevice()" disabled>
                        🔗 Connect
                    </button>
                    
                    <button class="btn btn-danger" id="disconnectBtn" onclick="disconnectDevice()" disabled>
                        ❌ Disconnect
                    </button>
                </div>
                
                <div class="ble-status">
                    <div class="ble-status-item">
                        <span class="status-dot" id="statusDot"></span>
                        <span id="statusText">Not Connected</span>
                    </div>
                    <div class="ble-status-item">
                        🔋 <span id="batteryLevel">---%</span>
                    </div>
                    <div class="ble-status-item">
                        📈 Samples: <span id="sampleCount">0</span>
                    </div>
                </div>
            </div>
            
            <div class="card">
                <h2>⏱️ Data Collection</h2>
                
                <div class="ble-controls">
                    <label>Duration (seconds):</label>
                    <input type="number" class="duration-input" id="durationInput" value="60" min="10" max="300">
                    
                    <button class="btn btn-primary" id="startBtn" onclick="startCollection()" disabled>
                        ▶️ Start Recording
                    </button>
                    
                    <button class="btn btn-danger" id="stopBtn" onclick="stopCollection()" disabled>
                        ⏹️ Stop
                    </button>
                </div>
                
                <div id="collectionStatus" class="status"></div>
                
                <!-- Real-time Chart -->
                <div class="realtime-chart-container">
                    <canvas id="realtimeChart"></canvas>
                    <div style="margin-top: 10px; display: flex; justify-content: space-between; align-items: center;">
                        <span style="color: #888; font-size: 0.85rem;">🔍 Scroll to zoom • Drag to select zoom area • Ctrl+Drag to pan</span>
                        <button class="btn" onclick="realtimeChart.resetZoom()" style="padding: 8px 16px; font-size: 0.85rem;">
                            🔄 Reset Zoom
                        </button>
                    </div>
                </div>
                
                <div class="chart-stats">
                    <div class="chart-stat">
                        <div class="value" id="sensor1Value" style="color: #e74c3c;">--</div>
                        <div class="label">Sensor 1</div>
                    </div>
                    <div class="chart-stat">
                        <div class="value" id="sensor2Value" style="color: #3498db;">--</div>
                        <div class="label">Sensor 2</div>
                    </div>
                    <div class="chart-stat">
                        <div class="value" id="sensor3Value" style="color: #2ecc71;">--</div>
                        <div class="label">Sensor 3</div>
                    </div>
                    <div class="chart-stat">
                        <div class="value" id="samplingRate" style="color: #feca57;">-- Hz</div>
                        <div class="label">Sampling Rate</div>
                    </div>
                </div>
            </div>
        </div>
        
        <!-- File Analysis Tab -->
        <div id="analysis-tab" class="tab-content">
            <div class="card">
                <h2>📁 Upload ECG Data File</h2>
                <div class="upload-area" id="uploadArea">
                    <p style="font-size: 3rem; margin-bottom: 10px;">📄</p>
                    <p>Drag and drop your ECG data file here</p>
                    <p style="color: #888; margin: 10px 0;">or</p>
                    <button class="btn" onclick="document.getElementById('fileInput').click()">
                        Choose File
                    </button>
                    <input type="file" id="fileInput" accept=".txt" onchange="handleFileSelect(event)">
                </div>
                <div id="uploadStatus" class="status"></div>
            </div>
            
            
            <div class="card" id="resultsCard" style="display: none;">
                <h2 style="color: #ffffff;">📊 Analysis Results</h2>
                <div id="analysisStatus" class="status"></div>
                
                <div class="results-grid" id="resultsGrid">
                </div>
                
                <!-- Professional ECG Chart with Controls -->
                <div class="analysis-chart-container" id="analysisChartContainer" style="display: none;">
                    
                    <!-- ECG Control Panel -->
                    <div class="ecg-control-panel">
                        <!-- Paper Speed Control -->
                        <div class="control-group">
                            <span class="control-group-label">📏 Paper Speed</span>
                            <div class="control-group-content">
                                <button class="ecg-btn" data-speed="10" onclick="setECGSpeed(10)">10mm/s</button>
                                <button class="ecg-btn active" data-speed="25" onclick="setECGSpeed(25)">25mm/s</button>
                                <button class="ecg-btn" data-speed="50" onclick="setECGSpeed(50)">50mm/s</button>
                            </div>
                        </div>
                        
                        <!-- Gain/Amplitude Control -->
                        <div class="control-group">
                            <span class="control-group-label">📊 Gain (Amplitude)</span>
                            <div class="control-group-content">
                                <button class="ecg-btn" data-gain="0.5" onclick="setECGGain(0.5)">0.5x</button>
                                <button class="ecg-btn active" data-gain="1" onclick="setECGGain(1)">1x</button>
                                <button class="ecg-btn" data-gain="2" onclick="setECGGain(2)">2x</button>
                                <button class="ecg-btn" data-gain="4" onclick="setECGGain(4)">4x</button>
                            </div>
                        </div>
                        
                        <!-- Sensor Visibility -->
                        <div class="control-group">
                            <span class="control-group-label">👁️ Visible Channels</span>
                            <div class="control-group-content">
                                <button class="sensor-toggle sensor1 active" data-sensor="0" onclick="toggleSensor(0)">S1</button>
                                <button class="sensor-toggle sensor2 active" data-sensor="1" onclick="toggleSensor(1)">S2</button>
                                <button class="sensor-toggle sensor3 active" data-sensor="2" onclick="toggleSensor(2)">S3</button>
                            </div>
                        </div>
                        
                        <!-- Actions -->
                        <div class="control-group">
                            <span class="control-group-label">⚡ Actions</span>
                            <div class="control-group-content">
                                <button class="ecg-btn ecg-btn-icon" onclick="resetAnalysisZoom()" title="Reset Zoom">🔄</button>
                                <button class="ecg-btn ecg-btn-icon" onclick="fitToScreen()" title="Fit to Screen">📐</button>
                                <button class="ecg-btn ecg-btn-icon" onclick="exportECGData()" title="Export Data">💾</button>
                            </div>
                        </div>
                    </div>
                    
                    <!-- ECG Chart Canvas -->
                    <div class="ecg-canvas-wrapper">
                        <canvas id="analysisChart"></canvas>
                    </div>
                    
                    <!-- ECG Info Bar -->
                    <div class="ecg-info-bar">
                        <div class="ecg-info-item">
                            <span>📊 Samples:</span>
                            <span class="ecg-info-value" id="ecgTotalSamples">--</span>
                        </div>
                        <div class="ecg-info-item">
                            <span>⏱️ Duration:</span>
                            <span class="ecg-info-value" id="ecgDuration">--</span>
                        </div>
                        <div class="ecg-info-item">
                            <span>📈 Sample Rate:</span>
                            <span class="ecg-info-value" id="ecgSampleRate">-- Hz</span>
                        </div>
                        <div class="ecg-info-item">
                            <span>🔍 Zoom:</span>
                            <span class="ecg-info-value" id="ecgZoomLevel">100%</span>
                        </div>
                    </div>
                    
                    <!-- Timeline Navigation -->
                    <div class="ecg-timeline">
                        <div class="ecg-timeline-header">
                            <span class="ecg-timeline-label">Timeline Navigation</span>
                            <span class="ecg-timeline-position" id="ecgTimePosition">0.00s - 0.00s</span>
                        </div>
                        <div style="display: flex; gap: 12px; align-items: center;">
                            <div class="ecg-nav-buttons">
                                <button class="ecg-nav-btn" onclick="navigateECG('start')" title="Go to Start">⏮️</button>
                                <button class="ecg-nav-btn" onclick="navigateECG('prev')" title="Previous">◀️</button>
                            </div>
                            <input type="range" class="ecg-range" id="ecgTimeSlider" min="0" max="100" value="0" 
                                   oninput="seekECGPosition(this.value)" style="flex: 1;">
                            <div class="ecg-nav-buttons">
                                <button class="ecg-nav-btn" onclick="navigateECG('next')" title="Next">▶️</button>
                                <button class="ecg-nav-btn" onclick="navigateECG('end')" title="Go to End">⏭️</button>
                            </div>
                            <input type="text" class="ecg-input" id="ecgGoToTime" placeholder="0.00s" 
                                   onkeypress="if(event.key==='Enter') goToECGTime(this.value)">
                        </div>
                    </div>
                    
                    <!-- Measurements Display -->
                    <div class="ecg-measurements" id="ecgMeasurementsGrid">
                        <div class="ecg-measurement-card sensor1">
                            <div class="ecg-measurement-label">Sensor 1 - Peak</div>
                            <div class="ecg-measurement-value" id="ecgS1Peak">--<span class="ecg-measurement-unit">mV</span></div>
                        </div>
                        <div class="ecg-measurement-card sensor2">
                            <div class="ecg-measurement-label">Sensor 2 - Peak</div>
                            <div class="ecg-measurement-value" id="ecgS2Peak">--<span class="ecg-measurement-unit">mV</span></div>
                        </div>
                        <div class="ecg-measurement-card sensor3">
                            <div class="ecg-measurement-label">Sensor 3 - Peak</div>
                            <div class="ecg-measurement-value" id="ecgS3Peak">--<span class="ecg-measurement-unit">mV</span></div>
                        </div>
                        <div class="ecg-measurement-card combined">
                            <div class="ecg-measurement-label">Average Signal</div>
                            <div class="ecg-measurement-value" id="ecgAvgSignal">--<span class="ecg-measurement-unit">mV</span></div>
                        </div>
                    </div>
                    
                    <!-- Controls Hint -->
                    <div class="chart-controls">
                        <div class="chart-controls-hint">
                            <div class="hint-item">
                                <span class="hint-key">Scroll</span>
                                <span>Zoom</span>
                            </div>
                            <div class="hint-item">
                                <span class="hint-key">Drag</span>
                                <span>Select Area</span>
                            </div>
                            <div class="hint-item">
                                <span class="hint-key">Ctrl+Drag</span>
                                <span>Pan</span>
                            </div>
                            <div class="hint-item">
                                <span class="hint-key">Double-click</span>
                                <span>Reset</span>
                            </div>
                        </div>
                        <div class="ecg-help">
                            <span class="ecg-help-icon">💡</span>
                            <span>Use controls above to adjust visualization settings</span>
                        </div>
                    </div>
                </div>
                
                <div class="plot-container" id="plotContainer">
                </div>
            </div>
        </div>
    </div>
    
    <script>
        // Tab switching
        function showTab(tabName) {
            document.querySelectorAll('.tab-content').forEach(tab => tab.classList.remove('active'));
            document.querySelectorAll('.tab-btn').forEach(btn => btn.classList.remove('active'));
            document.getElementById(tabName + '-tab').classList.add('active');
            event.target.classList.add('active');
        }
        
        // Real-time Chart Setup
        const ctx = document.getElementById('realtimeChart').getContext('2d');
        const maxDataPoints = 500;
        
        const realtimeChart = new Chart(ctx, {
            type: 'line',
            data: {
                labels: [],
                datasets: [
                    {
                        label: 'Sensor 1',
                        data: [],
                        borderColor: '#e74c3c',
                        backgroundColor: 'rgba(231, 76, 60, 0.1)',
                        borderWidth: 1.5,
                        pointRadius: 0,
                        tension: 0.1
                    },
                    {
                        label: 'Sensor 2',
                        data: [],
                        borderColor: '#3498db',
                        backgroundColor: 'rgba(52, 152, 219, 0.1)',
                        borderWidth: 1.5,
                        pointRadius: 0,
                        tension: 0.1
                    },
                    {
                        label: 'Sensor 3',
                        data: [],
                        borderColor: '#2ecc71',
                        backgroundColor: 'rgba(46, 204, 113, 0.1)',
                        borderWidth: 1.5,
                        pointRadius: 0,
                        tension: 0.1
                    }
                ]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                animation: false,
                scales: {
                    x: {
                        display: false
                    },
                    y: {
                        grid: {
                            color: 'rgba(255,255,255,0.1)'
                        },
                        ticks: {
                            color: '#888'
                        }
                    }
                },
                plugins: {
                    legend: {
                        labels: {
                            color: '#eaeaea'
                        }
                    },
                    zoom: {
                        pan: {
                            enabled: true,
                            mode: 'xy',
                            modifierKey: 'ctrl'
                        },
                        zoom: {
                            wheel: {
                                enabled: true
                            },
                            pinch: {
                                enabled: true
                            },
                            drag: {
                                enabled: true,
                                backgroundColor: 'rgba(102, 126, 234, 0.25)',
                                borderColor: 'rgba(102, 126, 234, 0.8)',
                                borderWidth: 1
                            },
                            mode: 'xy'
                        }
                    }
                }
            }
        });
        
        let eventSource = null;
        let sampleStartTime = null;
        let totalSamples = 0;
        
        // BLE Functions
        function scanDevices() {
            const scanBtn = document.getElementById('scanBtn');
            scanBtn.disabled = true;
            scanBtn.innerHTML = '<span class="spinner"></span>Scanning...';
            document.getElementById('statusDot').className = 'status-dot scanning';
            document.getElementById('statusText').textContent = 'Scanning...';
            
            fetch('/ble/scan', {method: 'POST'})
            .then(response => response.json())
            .then(data => {
                scanBtn.disabled = false;
                scanBtn.innerHTML = '🔍 Scan for Devices';
                document.getElementById('statusDot').className = 'status-dot';
                document.getElementById('statusText').textContent = 'Not Connected';
                
                const select = document.getElementById('deviceSelect');
                select.innerHTML = '<option value="">Select a device...</option>';
                
                if (data.devices && data.devices.length > 0) {
                    data.devices.forEach((device, i) => {
                        const option = document.createElement('option');
                        option.value = i;
                        option.textContent = `${device.name} (${device.address})`;
                        select.appendChild(option);
                    });
                    document.getElementById('connectBtn').disabled = false;
                } else {
                    select.innerHTML = '<option value="">No devices found</option>';
                }
            })
            .catch(error => {
                scanBtn.disabled = false;
                scanBtn.innerHTML = '🔍 Scan for Devices';
                alert('Scan failed: ' + error);
            });
        }
        
        function connectDevice() {
            const deviceIndex = document.getElementById('deviceSelect').value;
            if (!deviceIndex) return;
            
            const connectBtn = document.getElementById('connectBtn');
            connectBtn.disabled = true;
            connectBtn.innerHTML = '<span class="spinner"></span>Connecting...';
            
            fetch('/ble/connect', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({device_index: parseInt(deviceIndex)})
            })
            .then(response => response.json())
            .then(data => {
                if (data.success) {
                    document.getElementById('statusDot').className = 'status-dot connected';
                    document.getElementById('statusText').textContent = 'Connected: ' + data.device_name;
                    document.getElementById('batteryLevel').textContent = data.battery + '%';
                    document.getElementById('connectBtn').disabled = true;
                    document.getElementById('connectBtn').innerHTML = '🔗 Connect';
                    document.getElementById('disconnectBtn').disabled = false;
                    document.getElementById('startBtn').disabled = false;
                } else {
                    alert('Connection failed: ' + data.error);
                    connectBtn.disabled = false;
                    connectBtn.innerHTML = '🔗 Connect';
                }
            })
            .catch(error => {
                alert('Connection error: ' + error);
                connectBtn.disabled = false;
                connectBtn.innerHTML = '🔗 Connect';
            });
        }
        
        function disconnectDevice() {
            fetch('/ble/disconnect', {method: 'POST'})
            .then(response => response.json())
            .then(data => {
                document.getElementById('statusDot').className = 'status-dot';
                document.getElementById('statusText').textContent = 'Not Connected';
                document.getElementById('batteryLevel').textContent = '---%';
                document.getElementById('connectBtn').disabled = false;
                document.getElementById('disconnectBtn').disabled = true;
                document.getElementById('startBtn').disabled = true;
                document.getElementById('stopBtn').disabled = true;
            });
        }
        
        function startCollection() {
            const duration = parseInt(document.getElementById('durationInput').value) || 60;
            
            // Clear chart
            realtimeChart.data.labels = [];
            realtimeChart.data.datasets.forEach(ds => ds.data = []);
            realtimeChart.update();
            
            sampleStartTime = Date.now();
            totalSamples = 0;
            
            document.getElementById('startBtn').disabled = true;
            document.getElementById('stopBtn').disabled = false;
            document.getElementById('statusDot').className = 'status-dot collecting';
            
            const statusDiv = document.getElementById('collectionStatus');
            statusDiv.className = 'status loading';
            statusDiv.innerHTML = '<span class="spinner"></span>Recording data...';
            
            // Start SSE stream
            eventSource = new EventSource('/ble/stream?duration=' + duration);
            
            eventSource.onmessage = function(event) {
                const data = JSON.parse(event.data);
                
                if (data.type === 'data') {
                    totalSamples++;
                    
                    // Update chart
                    realtimeChart.data.labels.push(totalSamples);
                    realtimeChart.data.datasets[0].data.push(data.values[0]);
                    realtimeChart.data.datasets[1].data.push(data.values[1]);
                    realtimeChart.data.datasets[2].data.push(data.values[2]);
                    
                    // Keep only last N points
                    if (realtimeChart.data.labels.length > maxDataPoints) {
                        realtimeChart.data.labels.shift();
                        realtimeChart.data.datasets.forEach(ds => ds.data.shift());
                    }
                    
                    // Update every 10 samples for performance
                    if (totalSamples % 10 === 0) {
                        realtimeChart.update('none');
                    }
                    
                    // Update stats
                    document.getElementById('sampleCount').textContent = totalSamples;
                    document.getElementById('sensor1Value').textContent = data.values[0];
                    document.getElementById('sensor2Value').textContent = data.values[1];
                    document.getElementById('sensor3Value').textContent = data.values[2];
                    
                    // Calculate sampling rate
                    const elapsed = (Date.now() - sampleStartTime) / 1000;
                    if (elapsed > 0) {
                        const rate = (totalSamples / elapsed).toFixed(1);
                        document.getElementById('samplingRate').textContent = rate + ' Hz';
                    }
                    
                } else if (data.type === 'complete') {
                    eventSource.close();
                    collectionComplete(data);
                    
                } else if (data.type === 'error') {
                    eventSource.close();
                    collectionError(data.message);
                }
            };
            
            eventSource.onerror = function() {
                eventSource.close();
                collectionError('Connection lost');
            };
        }
        
        function stopCollection() {
            if (eventSource) {
                eventSource.close();
            }
            fetch('/ble/stop', {method: 'POST'});
            
            document.getElementById('startBtn').disabled = false;
            document.getElementById('stopBtn').disabled = true;
            document.getElementById('statusDot').className = 'status-dot connected';
            
            const statusDiv = document.getElementById('collectionStatus');
            statusDiv.className = 'status success';
            statusDiv.textContent = '⏹️ Collection stopped by user';
        }
        
        function collectionComplete(data) {
            document.getElementById('startBtn').disabled = false;
            document.getElementById('stopBtn').disabled = true;
            document.getElementById('statusDot').className = 'status-dot connected';
            
            const statusDiv = document.getElementById('collectionStatus');
            statusDiv.className = 'status success';
            statusDiv.innerHTML = `✅ Recording complete!<br>📁 Saved to: ${data.filepath}<br>📈 Total samples: ${data.sample_count}`;
            
            loadFileList();
        }
        
        function collectionError(message) {
            document.getElementById('startBtn').disabled = false;
            document.getElementById('stopBtn').disabled = true;
            document.getElementById('statusDot').className = 'status-dot connected';
            
            const statusDiv = document.getElementById('collectionStatus');
            statusDiv.className = 'status error';
            statusDiv.textContent = '❌ Error: ' + message;
        }
        
        // File Analysis Functions (same as before)
        const uploadArea = document.getElementById('uploadArea');
        
        ['dragenter', 'dragover', 'dragleave', 'drop'].forEach(eventName => {
            uploadArea.addEventListener(eventName, preventDefaults, false);
        });
        
        function preventDefaults(e) {
            e.preventDefault();
            e.stopPropagation();
        }
        
        ['dragenter', 'dragover'].forEach(eventName => {
            uploadArea.addEventListener(eventName, () => uploadArea.classList.add('dragover'));
        });
        
        ['dragleave', 'drop'].forEach(eventName => {
            uploadArea.addEventListener(eventName, () => uploadArea.classList.remove('dragover'));
        });
        
        uploadArea.addEventListener('drop', handleDrop);
        
        function handleDrop(e) {
            const files = e.dataTransfer.files;
            if (files.length > 0) {
                uploadFile(files[0]);
            }
        }
        
        function handleFileSelect(e) {
            if (e.target.files.length > 0) {
                uploadFile(e.target.files[0]);
            }
        }
        
        function uploadFile(file) {
            const statusDiv = document.getElementById('uploadStatus');
            statusDiv.className = 'status loading';
            statusDiv.innerHTML = '<span class="spinner"></span>Uploading...';
            
            const formData = new FormData();
            formData.append('file', file);
            
            fetch('/upload', {
                method: 'POST',
                body: formData
            })
            .then(response => response.json())
            .then(data => {
                if (data.success) {
                    statusDiv.className = 'status success';
                    statusDiv.textContent = '✅ File uploaded: ' + data.filename;
                    analyzeFile(data.filepath);
                } else {
                    statusDiv.className = 'status error';
                    statusDiv.textContent = '❌ Error: ' + data.error;
                }
            })
            .catch(error => {
                statusDiv.className = 'status error';
                statusDiv.textContent = '❌ Upload failed: ' + error;
            });
        }
        
        function analyzeFile(filepath) {
            const resultsCard = document.getElementById('resultsCard');
            const statusDiv = document.getElementById('analysisStatus');
            const resultsGrid = document.getElementById('resultsGrid');
            const plotContainer = document.getElementById('plotContainer');
            
            resultsCard.style.display = 'block';
            statusDiv.className = 'status loading';
            statusDiv.innerHTML = '<span class="spinner"></span>Analyzing ECG data...';
            resultsGrid.innerHTML = '';
            plotContainer.innerHTML = '';
            
            fetch('/analyze', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({filepath: filepath})
            })
            .then(response => response.json())
            .then(data => {
                if (data.success) {
                    statusDiv.className = 'status success';
                    statusDiv.textContent = '✅ Analysis complete - ' + data.filename;
                    
                    const sensors = ['Sensor 1', 'Sensor 2', 'Sensor 3'];
                    const sensorClasses = ['sensor1', 'sensor2', 'sensor3'];
                    
                    let gridHtml = `
                        <div class="result-box">
                            <div class="value">${data.total_samples}</div>
                            <div class="label">Total Samples</div>
                        </div>
                        <div class="result-box">
                            <div class="value">${data.sampling_rate.toFixed(1)} Hz</div>
                            <div class="label">Sampling Rate</div>
                        </div>
                    `;
                    
                    data.hr_results.forEach((hr, i) => {
                        gridHtml += `
                            <div class="result-box ${sensorClasses[i]}">
                                <div class="value">${hr.avg.toFixed(1)}</div>
                                <div class="label">${sensors[i]} Avg HR (BPM)</div>
                            </div>
                        `;
                    });
                    
                    gridHtml += `
                        <div class="result-box combined">
                            <div class="value">${data.combined_hr.avg.toFixed(1)}</div>
                            <div class="label">Combined Avg HR (BPM)</div>
                        </div>
                    `;
                    
                    resultsGrid.innerHTML = gridHtml;
                    
                    // Fetch chart data and render interactive chart
                    fetch('/chart-data?t=' + Date.now())
                    .then(res => res.json())
                    .then(chartData => {
                        if (chartData.success) {
                            document.getElementById('analysisChartContainer').style.display = 'block';
                            plotContainer.innerHTML = '';
                            renderAnalysisChart(chartData);
                        } else {
                            // Fallback to static image
                            plotContainer.innerHTML = `<img src="/plot?t=${Date.now()}" alt="ECG Plot">`;
                        }
                    })
                    .catch(() => {
                        // Fallback to static image
                        plotContainer.innerHTML = `<img src="/plot?t=${Date.now()}" alt="ECG Plot">`;
                    });
                    
                } else {
                    statusDiv.className = 'status error';
                    statusDiv.textContent = '❌ Analysis failed: ' + data.error;
                }
            })
            .catch(error => {
                statusDiv.className = 'status error';
                statusDiv.textContent = '❌ Analysis failed: ' + error;
            });
        }
        
        // Analysis Chart instance and ECG state
        let analysisChart = null;
        let ecgState = {
            rawData: null,
            samplingRate: 100,
            totalSamples: 0,
            duration: 0,
            speed: 25,  // mm/s
            gain: 1,
            visibleSensors: [true, true, true],
            currentPosition: 0,
            zoomLevel: 100
        };
        
        function renderAnalysisChart(chartData) {
            const ctx = document.getElementById('analysisChart').getContext('2d');
            
            // Destroy existing chart if any
            if (analysisChart) {
                analysisChart.destroy();
            }
            
            // Store raw data for controls
            ecgState.rawData = chartData;
            ecgState.samplingRate = chartData.sampling_rate || 100;
            ecgState.totalSamples = chartData.labels.length;
            ecgState.duration = ecgState.totalSamples / ecgState.samplingRate;
            
            // Update ECG info display
            updateECGInfo();
            updateMeasurements(chartData);
            
            // Downsample data for better performance if too many points
            const maxPoints = 3000;
            let sensor1 = chartData.sensor1;
            let sensor2 = chartData.sensor2;
            let sensor3 = chartData.sensor3;
            let labels = chartData.labels;
            
            // Convert labels to time in seconds
            let timeLabels = labels.map((_, i) => (i / ecgState.samplingRate).toFixed(2));
            
            if (labels.length > maxPoints) {
                const step = Math.ceil(labels.length / maxPoints);
                sensor1 = sensor1.filter((_, i) => i % step === 0);
                sensor2 = sensor2.filter((_, i) => i % step === 0);
                sensor3 = sensor3.filter((_, i) => i % step === 0);
                timeLabels = timeLabels.filter((_, i) => i % step === 0);
            }
            
            // Apply gain
            sensor1 = sensor1.map(v => v * ecgState.gain);
            sensor2 = sensor2.map(v => v * ecgState.gain);
            sensor3 = sensor3.map(v => v * ecgState.gain);
            
            analysisChart = new Chart(ctx, {
                type: 'line',
                data: {
                    labels: timeLabels,
                    datasets: [
                        {
                            label: 'Sensor 1 (Lead I)',
                            data: sensor1,
                            borderColor: '#e74c3c',
                            backgroundColor: 'rgba(231, 76, 60, 0.05)',
                            borderWidth: 1.5,
                            pointRadius: 0,
                            tension: 0.2,
                            fill: true,
                            hidden: !ecgState.visibleSensors[0]
                        },
                        {
                            label: 'Sensor 2 (Lead II)',
                            data: sensor2,
                            borderColor: '#3498db',
                            backgroundColor: 'rgba(52, 152, 219, 0.05)',
                            borderWidth: 1.5,
                            pointRadius: 0,
                            tension: 0.2,
                            fill: true,
                            hidden: !ecgState.visibleSensors[1]
                        },
                        {
                            label: 'Sensor 3 (Lead III)',
                            data: sensor3,
                            borderColor: '#2ecc71',
                            backgroundColor: 'rgba(46, 204, 113, 0.05)',
                            borderWidth: 1.5,
                            pointRadius: 0,
                            tension: 0.2,
                            fill: true,
                            hidden: !ecgState.visibleSensors[2]
                        }
                    ]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    animation: {
                        duration: 300
                    },
                    interaction: {
                        mode: 'index',
                        intersect: false
                    },
                    scales: {
                        x: {
                            display: true,
                            title: {
                                display: true,
                                text: 'Time (seconds)',
                                color: '#48dbfb',
                                font: { size: 12, weight: 'bold' }
                            },
                            grid: {
                                color: 'rgba(255, 182, 193, 0.12)',
                                lineWidth: 1
                            },
                            ticks: {
                                color: '#aaa',
                                maxTicksLimit: 15,
                                callback: function(value, index) {
                                    return this.getLabelForValue(value) + 's';
                                }
                            }
                        },
                        y: {
                            display: true,
                            title: {
                                display: true,
                                text: 'Amplitude (mV)',
                                color: '#48dbfb',
                                font: { size: 12, weight: 'bold' }
                            },
                            grid: {
                                color: 'rgba(255, 182, 193, 0.12)',
                                lineWidth: 1
                            },
                            ticks: {
                                color: '#aaa',
                                callback: function(value) {
                                    return value.toFixed(0);
                                }
                            }
                        }
                    },
                    plugins: {
                        legend: {
                            display: false
                        },
                        tooltip: {
                            enabled: true,
                            mode: 'index',
                            intersect: false,
                            backgroundColor: 'rgba(10, 22, 40, 0.95)',
                            titleColor: '#48dbfb',
                            bodyColor: '#fff',
                            borderColor: 'rgba(72, 219, 251, 0.3)',
                            borderWidth: 1,
                            padding: 12,
                            cornerRadius: 8,
                            titleFont: { weight: 'bold' },
                            callbacks: {
                                title: function(context) {
                                    return '⏱️ Time: ' + context[0].label + 's';
                                },
                                label: function(context) {
                                    const sensorNames = ['🔴 Sensor 1', '🔵 Sensor 2', '🟢 Sensor 3'];
                                    return sensorNames[context.datasetIndex] + ': ' + context.raw.toFixed(1) + ' mV';
                                }
                            }
                        },
                        zoom: {
                            pan: {
                                enabled: true,
                                mode: 'xy',
                                modifierKey: 'ctrl',
                                onPan: updateZoomDisplay
                            },
                            zoom: {
                                wheel: {
                                    enabled: true,
                                    speed: 0.08
                                },
                                pinch: {
                                    enabled: true
                                },
                                drag: {
                                    enabled: true,
                                    backgroundColor: 'rgba(72, 219, 251, 0.15)',
                                    borderColor: 'rgba(72, 219, 251, 0.8)',
                                    borderWidth: 2
                                },
                                mode: 'xy',
                                onZoom: updateZoomDisplay
                            }
                        }
                    }
                }
            });
            
            // Double-click to reset zoom
            document.getElementById('analysisChart').addEventListener('dblclick', resetAnalysisZoom);
        }
        
        // Update ECG info display
        function updateECGInfo() {
            document.getElementById('ecgTotalSamples').textContent = ecgState.totalSamples.toLocaleString();
            document.getElementById('ecgDuration').textContent = ecgState.duration.toFixed(2) + 's';
            document.getElementById('ecgSampleRate').textContent = ecgState.samplingRate.toFixed(1) + ' Hz';
            document.getElementById('ecgZoomLevel').textContent = ecgState.zoomLevel + '%';
            document.getElementById('ecgTimePosition').textContent = 
                '0.00s - ' + ecgState.duration.toFixed(2) + 's';
        }
        
        // Update measurements display
        function updateMeasurements(data) {
            if (!data) return;
            
            const s1Max = Math.max(...data.sensor1);
            const s2Max = Math.max(...data.sensor2);
            const s3Max = Math.max(...data.sensor3);
            
            const s1Avg = data.sensor1.reduce((a, b) => a + b, 0) / data.sensor1.length;
            const s2Avg = data.sensor2.reduce((a, b) => a + b, 0) / data.sensor2.length;
            const s3Avg = data.sensor3.reduce((a, b) => a + b, 0) / data.sensor3.length;
            
            document.getElementById('ecgS1Peak').innerHTML = s1Max.toFixed(0) + '<span class="ecg-measurement-unit">mV</span>';
            document.getElementById('ecgS2Peak').innerHTML = s2Max.toFixed(0) + '<span class="ecg-measurement-unit">mV</span>';
            document.getElementById('ecgS3Peak').innerHTML = s3Max.toFixed(0) + '<span class="ecg-measurement-unit">mV</span>';
            document.getElementById('ecgAvgSignal').innerHTML = ((s1Avg + s2Avg + s3Avg) / 3).toFixed(1) + '<span class="ecg-measurement-unit">mV</span>';
        }
        
        // Update zoom display
        function updateZoomDisplay() {
            if (!analysisChart) return;
            
            const xScale = analysisChart.scales.x;
            const fullRange = ecgState.duration;
            const visibleRange = parseFloat(xScale.max) - parseFloat(xScale.min);
            const zoomPercent = Math.round((fullRange / visibleRange) * 100);
            
            ecgState.zoomLevel = Math.min(zoomPercent, 1000);
            document.getElementById('ecgZoomLevel').textContent = ecgState.zoomLevel + '%';
            
            // Update time position
            document.getElementById('ecgTimePosition').textContent = 
                parseFloat(xScale.min).toFixed(2) + 's - ' + parseFloat(xScale.max).toFixed(2) + 's';
            
            // Update slider
            const sliderPos = (parseFloat(xScale.min) / fullRange) * 100;
            document.getElementById('ecgTimeSlider').value = Math.max(0, Math.min(100, sliderPos));
        }
        
        // Paper Speed Control
        function setECGSpeed(speed) {
            ecgState.speed = speed;
            
            // Update button states
            document.querySelectorAll('[data-speed]').forEach(btn => {
                btn.classList.toggle('active', parseInt(btn.dataset.speed) === speed);
            });
            
            // Adjust visible window based on speed
            if (analysisChart && ecgState.rawData) {
                const windowSize = speed === 10 ? 20 : (speed === 25 ? 10 : 5); // seconds visible
                const currentPos = parseFloat(analysisChart.scales.x.min) || 0;
                
                analysisChart.options.scales.x.min = currentPos;
                analysisChart.options.scales.x.max = Math.min(currentPos + windowSize, ecgState.duration);
                analysisChart.update('none');
                updateZoomDisplay();
            }
        }
        
        // Gain Control
        function setECGGain(gain) {
            ecgState.gain = gain;
            
            // Update button states
            document.querySelectorAll('[data-gain]').forEach(btn => {
                btn.classList.toggle('active', parseFloat(btn.dataset.gain) === gain);
            });
            
            // Re-render chart with new gain if data exists
            if (ecgState.rawData) {
                renderAnalysisChart(ecgState.rawData);
            }
        }
        
        // Toggle Sensor Visibility
        function toggleSensor(index) {
            ecgState.visibleSensors[index] = !ecgState.visibleSensors[index];
            
            // Update button states
            const btn = document.querySelector(`[data-sensor="${index}"]`);
            btn.classList.toggle('active', ecgState.visibleSensors[index]);
            
            // Update chart
            if (analysisChart) {
                analysisChart.data.datasets[index].hidden = !ecgState.visibleSensors[index];
                analysisChart.update('none');
            }
        }
        
        // Timeline Navigation
        function navigateECG(direction) {
            if (!analysisChart) return;
            
            const xScale = analysisChart.scales.x;
            const visibleRange = parseFloat(xScale.max) - parseFloat(xScale.min);
            const step = visibleRange * 0.5; // 50% step
            
            let newMin, newMax;
            
            switch(direction) {
                case 'start':
                    newMin = 0;
                    newMax = visibleRange;
                    break;
                case 'end':
                    newMax = ecgState.duration;
                    newMin = Math.max(0, newMax - visibleRange);
                    break;
                case 'prev':
                    newMin = Math.max(0, parseFloat(xScale.min) - step);
                    newMax = newMin + visibleRange;
                    break;
                case 'next':
                    newMax = Math.min(ecgState.duration, parseFloat(xScale.max) + step);
                    newMin = newMax - visibleRange;
                    break;
            }
            
            analysisChart.options.scales.x.min = newMin;
            analysisChart.options.scales.x.max = newMax;
            analysisChart.update('none');
            updateZoomDisplay();
        }
        
        // Seek to position via slider
        function seekECGPosition(percent) {
            if (!analysisChart) return;
            
            const xScale = analysisChart.scales.x;
            const visibleRange = parseFloat(xScale.max) - parseFloat(xScale.min);
            const newMin = (percent / 100) * (ecgState.duration - visibleRange);
            const newMax = newMin + visibleRange;
            
            analysisChart.options.scales.x.min = Math.max(0, newMin);
            analysisChart.options.scales.x.max = Math.min(ecgState.duration, newMax);
            analysisChart.update('none');
            updateZoomDisplay();
        }
        
        // Go to specific time
        function goToECGTime(timeStr) {
            if (!analysisChart) return;
            
            const time = parseFloat(timeStr.replace('s', ''));
            if (isNaN(time) || time < 0 || time > ecgState.duration) return;
            
            const xScale = analysisChart.scales.x;
            const visibleRange = parseFloat(xScale.max) - parseFloat(xScale.min);
            const halfRange = visibleRange / 2;
            
            let newMin = time - halfRange;
            let newMax = time + halfRange;
            
            if (newMin < 0) {
                newMin = 0;
                newMax = visibleRange;
            } else if (newMax > ecgState.duration) {
                newMax = ecgState.duration;
                newMin = newMax - visibleRange;
            }
            
            analysisChart.options.scales.x.min = newMin;
            analysisChart.options.scales.x.max = newMax;
            analysisChart.update('none');
            updateZoomDisplay();
        }
        
        // Fit to screen
        function fitToScreen() {
            if (!analysisChart) return;
            
            analysisChart.options.scales.x.min = undefined;
            analysisChart.options.scales.x.max = undefined;
            analysisChart.options.scales.y.min = undefined;
            analysisChart.options.scales.y.max = undefined;
            analysisChart.resetZoom();
            ecgState.zoomLevel = 100;
            updateZoomDisplay();
        }
        
        // Export ECG data
        function exportECGData() {
            if (!ecgState.rawData) {
                alert('No data available to export');
                return;
            }
            
            const data = ecgState.rawData;
            let csv = 'Time(s),Sensor1,Sensor2,Sensor3\\n';
            
            for (let i = 0; i < data.labels.length; i++) {
                const time = (i / ecgState.samplingRate).toFixed(4);
                csv += `${time},${data.sensor1[i]},${data.sensor2[i]},${data.sensor3[i]}\\n`;
            }
            
            const blob = new Blob([csv], { type: 'text/csv' });
            const url = URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = 'ecg_data_export_' + new Date().toISOString().slice(0,19).replace(/:/g, '-') + '.csv';
            a.click();
            URL.revokeObjectURL(url);
        }
        
        function resetAnalysisZoom() {
            if (analysisChart) {
                analysisChart.resetZoom();
                ecgState.zoomLevel = 100;
                updateZoomDisplay();
            }
        }
        
        
    </script>
</body>
</html>
'''


@app.route('/')
def index():
    return render_template_string(HTML_TEMPLATE)


@app.route('/files')
def list_files():
    """List available ECG data files."""
    files = []
    files_dir = app.config['UPLOAD_FOLDER']
    
    if os.path.exists(files_dir):
        for filename in sorted(os.listdir(files_dir), reverse=True):
            if filename.endswith('.txt'):
                filepath = os.path.join(files_dir, filename)
                files.append({
                    'name': filename,
                    'path': filepath,
                    'size': os.path.getsize(filepath)
                })
    
    return jsonify({'files': files})


@app.route('/upload', methods=['POST'])
def upload_file():
    """Handle file upload."""
    if 'file' not in request.files:
        return jsonify({'success': False, 'error': 'No file provided'})
    
    file = request.files['file']
    if file.filename == '':
        return jsonify({'success': False, 'error': 'No file selected'})
    
    if file and file.filename.endswith('.txt'):
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"uploaded_{timestamp}_{file.filename}"
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(filepath)
        return jsonify({
            'success': True, 
            'filename': filename,
            'filepath': filepath
        })
    
    return jsonify({'success': False, 'error': 'Invalid file type. Only .txt files allowed.'})


@app.route('/analyze', methods=['POST'])
def analyze():
    """Analyze an ECG file."""
    global last_results
    
    data = request.get_json()
    filepath = data.get('filepath')
    
    if not filepath or not os.path.exists(filepath):
        return jsonify({'success': False, 'error': 'File not found'})
    
    try:
        results = analyze_ecg_file(filepath)
        
        if not results:
            return jsonify({'success': False, 'error': 'Could not analyze file. Check data format.'})
        
        fig = create_ecg_plot(
            results['dataframe'],
            results['hr_results'],
            results['combined_hr']
        )
        
        buf = BytesIO()
        fig.savefig(buf, format='png', dpi=100, bbox_inches='tight', 
                   facecolor='#1a1a2e', edgecolor='none')
        buf.seek(0)
        plt.close(fig)
        
        last_results = {
            'plot_data': buf.getvalue(),
            'results': results,
            'df': results['dataframe']
        }
        
        return jsonify({
            'success': True,
            'filename': os.path.basename(filepath),
            'total_samples': results['total_samples'],
            'sampling_rate': results['sampling_rate'],
            'hr_results': results['hr_results'],
            'combined_hr': results['combined_hr']
        })
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})


@app.route('/plot')
def get_plot():
    """Return the last generated plot."""
    global last_results
    
    if 'plot_data' not in last_results:
        return "No plot available", 404
    
    return send_file(
        BytesIO(last_results['plot_data']),
        mimetype='image/png'
    )


@app.route('/chart-data')
def get_chart_data():
    """Return the chart data as JSON for interactive plotting."""
    global last_results
    
    if 'df' not in last_results:
        return jsonify({'success': False, 'error': 'No data available'})
    
    try:
        df = last_results['df']
        
        # Convert dataframe columns to lists for JSON serialization
        # Column names from ecg_processor.py are: line_1, line_2, line_3
        sensor1 = df['line_1'].tolist() if 'line_1' in df.columns else []
        sensor2 = df['line_2'].tolist() if 'line_2' in df.columns else []
        sensor3 = df['line_3'].tolist() if 'line_3' in df.columns else []
        
        # Create sample index labels
        labels = list(range(len(sensor1)))
        
        return jsonify({
            'success': True,
            'sensor1': sensor1,
            'sensor2': sensor2,
            'sensor3': sensor3,
            'labels': labels,
            'sampling_rate': last_results['results'].get('sampling_rate', 100) if 'results' in last_results else 100
        })
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})


# ==================== BLE Endpoints ====================

@app.route('/ble/scan', methods=['POST'])
def ble_scan():
    """Scan for BLE devices."""
    global ble_handler, ble_status
    
    try:
        # Create new handler (has its own persistent event loop)
        ble_handler = BLEHandler()
        
        # Scan is now synchronous (handler manages async internally)
        devices = ble_handler.scan_for_devices(timeout=5.0)
        ble_status['devices'] = [{'name': d.name, 'address': d.address} for d in devices]
        
        return jsonify({
            'success': True,
            'devices': ble_status['devices']
        })
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'error': str(e)})


@app.route('/ble/connect', methods=['POST'])
def ble_connect():
    """Connect to a BLE device."""
    global ble_handler, ble_status
    
    data = request.get_json()
    device_index = data.get('device_index', 0)
    
    if not ble_handler or not ble_handler.discovered_devices:
        return jsonify({'success': False, 'error': 'No devices found. Scan first.'})
    
    if device_index >= len(ble_handler.discovered_devices):
        return jsonify({'success': False, 'error': 'Invalid device index'})
    
    try:
        device = ble_handler.discovered_devices[device_index]
        
        # Connect is now synchronous
        success = ble_handler.connect(device)
        
        if success and ble_handler.is_connected:
            ble_status['connected'] = True
            ble_status['device_name'] = device.name
            ble_status['battery'] = ble_handler.battery_level
            
            return jsonify({
                'success': True,
                'device_name': device.name,
                'battery': ble_handler.battery_level
            })
        else:
            return jsonify({'success': False, 'error': 'Connection failed'})
            
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'error': str(e)})


@app.route('/ble/disconnect', methods=['POST'])
def ble_disconnect():
    """Disconnect from BLE device."""
    global ble_handler, ble_status
    
    try:
        if ble_handler:
            ble_handler.disconnect()
        
        ble_status['connected'] = False
        ble_status['collecting'] = False
        
        return jsonify({'success': True})
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})


@app.route('/ble/stop', methods=['POST'])
def ble_stop():
    """Stop data collection."""
    global ble_handler
    
    if ble_handler:
        ble_handler.cancel_collection()
    
    return jsonify({'success': True})


@app.route('/ble/stream')
def ble_stream():
    """Server-Sent Events stream for real-time data."""
    global ble_handler, ble_status
    
    duration = int(request.args.get('duration', 60))
    
    def generate():
        if not ble_handler or not ble_handler.is_connected:
            yield f"data: {json.dumps({'type': 'error', 'message': 'Not connected'})}\n\n"
            return
        
        data_buffer = []
        collection_done = threading.Event()
        collection_error = [None]
        
        def on_data(line):
            try:
                parts = line.split(',')
                if len(parts) >= 3:
                    values = [int(p.strip()) for p in parts[:3]]
                    data_buffer.append(values)
            except:
                pass
        
        def collect_thread():
            try:
                # This now uses the handler's internal event loop
                ble_handler.start_data_collection(
                    duration_seconds=duration,
                    command="1",
                    data_callback=on_data
                )
            except Exception as e:
                collection_error[0] = str(e)
                print(f"Collection error: {e}")
            finally:
                collection_done.set()
        
        thread = threading.Thread(target=collect_thread)
        thread.start()
        
        last_sent = 0
        while not collection_done.is_set():
            # Send any new data
            while last_sent < len(data_buffer):
                values = data_buffer[last_sent]
                yield f"data: {json.dumps({'type': 'data', 'values': values})}\n\n"
                last_sent += 1
            
            collection_done.wait(timeout=0.05)
        
        # Send remaining data
        while last_sent < len(data_buffer):
            values = data_buffer[last_sent]
            yield f"data: {json.dumps({'type': 'data', 'values': values})}\n\n"
            last_sent += 1
        
        # Check for errors
        if collection_error[0]:
            yield f"data: {json.dumps({'type': 'error', 'message': collection_error[0]})}\n\n"
            return
        
        # Save data
        filepath = None
        sample_count = ble_handler.sample_count if ble_handler else 0
        
        if sample_count > 0:
            try:
                filepath = ble_handler.save_to_file()
            except Exception as e:
                print(f"Save error: {e}")
        
        yield f"data: {json.dumps({'type': 'complete', 'filepath': filepath, 'sample_count': sample_count})}\n\n"
    
    return Response(generate(), mimetype='text/event-stream')


def main():
    """Main entry point."""
    print("\n" + "="*50)
    print("🫀 nPulse ECG Analyzer - Web Interface")
    print("="*50)
    print("\n📍 Open your browser to: http://127.0.0.1:5000")
    print("\n💡 Press Ctrl+C to stop the server\n")
    app.run(debug=False, port=5000, host='127.0.0.1', threaded=True)


if __name__ == "__main__":
    main()

