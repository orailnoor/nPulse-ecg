"""
BLE Data Collector for nPulse Device
Terminal-based data collection from nPulse ECG device.
Saves data to ./files/ directory.
"""

import asyncio
import sys
from datetime import datetime
from ble_handler import BLEHandler


async def main():
    print("\n" + "="*50)
    print("nPulse BLE Data Collector")
    print("="*50)
    
    handler = BLEHandler()
    
    # Scan for devices
    print("\nScanning for nPulse devices...")
    devices = await handler.scan_for_devices(timeout=5.0)
    
    if not devices:
        print("No devices found. Make sure your nPulse device is on and nearby.")
        return
    
    print(f"\nFound {len(devices)} device(s):")
    for i, device in enumerate(devices):
        print(f"  {i + 1}. {device.name} ({device.address})")
    
    # Select device
    if len(devices) == 1:
        selected = devices[0]
        print(f"\n Auto-selecting: {selected.name}")
    else:
        while True:
            try:
                choice = input("\nEnter device number to connect (or 'q' to quit): ")
                if choice.lower() == 'q':
                    return
                idx = int(choice) - 1
                if 0 <= idx < len(devices):
                    selected = devices[idx]
                    break
                print("Invalid choice. Try again.")
            except ValueError:
                print("Please enter a number.")
    
    # Connect
    print(f"\n🔗 Connecting to {selected.name}...")
    success = await handler.connect(selected)
    
    if not success:
        print("Failed to connect.")
        return
    
    print(f"Connected! Battery: {handler.battery_level}%")
    
    # Get duration
    try:
        duration = input("\nEnter recording duration in seconds (default: 60): ").strip()
        duration = int(duration) if duration else 60
    except ValueError:
        duration = 60
    
    print(f"\nStarting {duration}-second data collection...")
    print("   (Press Ctrl+C to stop early)\n")
    
    sample_count = [0]
    
    def on_data(line):
        sample_count[0] += 1
        if sample_count[0] % 100 == 0:
            print(f"   Samples: {sample_count[0]}", end='\r')
    
    try:
        await handler.start_data_collection(
            duration_seconds=duration,
            command="1",
            data_callback=on_data
        )
    except KeyboardInterrupt:
        handler.cancel_collection()
        print("\n\nCollection stopped by user.")
    
    # Save data
    if handler.sample_count > 0:
        filepath = handler.save_to_file()
        print(f"\n\nData saved!")
        print(f"    File: {filepath}")
        print(f"   Samples: {handler.sample_count}")
    else:
        print("\nNo data collected.")
    
    # Disconnect
    print("\n🔌 Disconnecting...")
    await handler.disconnect()
    print("Done!")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n\nGoodbye!")
