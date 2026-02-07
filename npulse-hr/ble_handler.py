"""
BLE Handler for nPulse Device
Handles Bluetooth Low Energy communication with nPulse ECG devices.
Based on Flutter implementation using Nordic UART Service.
Uses a persistent event loop for proper async handling in Flask.
"""

import asyncio
import threading
from datetime import datetime
from typing import Callable, Optional, List
from bleak import BleakClient, BleakScanner
from bleak.backends.device import BLEDevice


# Nordic UART Service UUIDs
NORDIC_UART_SERVICE_UUID = "6e400001-b5a3-f393-e0a9-e50e24dcca9e"
NORDIC_UART_TX_CHAR_UUID = "6e400003-b5a3-f393-e0a9-e50e24dcca9e"  # NOTIFY - receive data
NORDIC_UART_RX_CHAR_UUID = "6e400002-b5a3-f393-e0a9-e50e24dcca9e"  # WRITE - send commands

# Battery Service UUIDs
BATTERY_SERVICE_UUID = "0000180f-0000-1000-8000-00805f9b34fb"
BATTERY_CHAR_UUID = "00002a19-0000-1000-8000-00805f9b34fb"

# Device names to scan for
DEVICE_NAMES = ["nPulse001", "nPulse", "NADI_PULSE", "IMU_DUAL_CHAR"]


class BLEHandler:
    """
    Handler for BLE communication with nPulse device.
    Uses a dedicated background thread with persistent event loop.
    """
    
    def __init__(self):
        self.client: Optional[BleakClient] = None
        self.connected_device: Optional[BLEDevice] = None
        self.discovered_devices: List[BLEDevice] = []
        self.is_connected: bool = False
        self.is_collecting: bool = False
        self.collected_data: List[str] = []
        self.sample_count: int = 0
        self.battery_level: int = 0
        self._collection_cancelled: bool = False
        self._data_callback: Optional[Callable[[str], None]] = None
        self._buffer: str = ""
        
        # Persistent event loop in background thread
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._thread: Optional[threading.Thread] = None
        self._start_loop()
    
    def _start_loop(self):
        """Start the background event loop thread."""
        def run_loop():
            self._loop = asyncio.new_event_loop()
            asyncio.set_event_loop(self._loop)
            self._loop.run_forever()
        
        self._thread = threading.Thread(target=run_loop, daemon=True)
        self._thread.start()
        # Wait for loop to be ready
        while self._loop is None:
            pass
    
    def _run_async(self, coro):
        """Run a coroutine in the background loop and wait for result."""
        if self._loop is None:
            raise RuntimeError("Event loop not started")
        
        future = asyncio.run_coroutine_threadsafe(coro, self._loop)
        return future.result(timeout=120)  # 2 minute timeout for long operations
    
    def scan_for_devices(self, timeout: float = 5.0) -> List[BLEDevice]:
        """Scan for nPulse BLE devices."""
        return self._run_async(self._scan_for_devices_async(timeout))
    
    async def _scan_for_devices_async(self, timeout: float = 5.0) -> List[BLEDevice]:
        """Async implementation of device scanning."""
        self.discovered_devices.clear()
        
        def detection_callback(device: BLEDevice, advertisement_data):
            if device.name and any(name in device.name for name in DEVICE_NAMES):
                if device not in self.discovered_devices:
                    self.discovered_devices.append(device)
                    print(f"Found device: {device.name} ({device.address})")
        
        scanner = BleakScanner(detection_callback=detection_callback)
        await scanner.start()
        await asyncio.sleep(timeout)
        await scanner.stop()
        
        print(f"Scan complete. Found {len(self.discovered_devices)} device(s)")
        return self.discovered_devices
    
    def connect(self, device: BLEDevice) -> bool:
        """Connect to a BLE device."""
        return self._run_async(self._connect_async(device))
    
    async def _connect_async(self, device: BLEDevice) -> bool:
        """Async implementation of device connection."""
        try:
            self.client = BleakClient(device.address)
            await self.client.connect()
            
            if self.client.is_connected:
                self.connected_device = device
                self.is_connected = True
                self._collection_cancelled = False
                print(f"Connected to {device.name}")
                
                # Try to read battery level
                await self._read_battery_async()
                return True
            
            return False
            
        except Exception as e:
            print(f"Connection error: {e}")
            self.is_connected = False
            return False
    
    def disconnect(self) -> bool:
        """Disconnect from the current device."""
        return self._run_async(self._disconnect_async())
    
    async def _disconnect_async(self) -> bool:
        """Async implementation of disconnect."""
        if self.client and self.is_connected:
            try:
                await self._send_command_async("SLEEP")
                await asyncio.sleep(0.2)
                await self.client.disconnect()
                print("Disconnected from device")
            except Exception as e:
                print(f"Disconnect error: {e}")
            finally:
                self.is_connected = False
                self.connected_device = None
                self.client = None
                self._collection_cancelled = True
        
        return True
    
    async def _send_command_async(self, command: str) -> bool:
        """Send a command to the device via RX characteristic."""
        if not self.client or not self.is_connected:
            return False
        
        try:
            await self.client.write_gatt_char(
                NORDIC_UART_RX_CHAR_UUID,
                command.encode('utf-8')
            )
            print(f"Sent command: {command}")
            return True
        except Exception as e:
            print(f"Error sending command: {e}")
            return False
    
    async def _read_battery_async(self) -> int:
        """Read battery level from device."""
        if not self.client or not self.is_connected:
            return 0
        
        try:
            battery_data = await self.client.read_gatt_char(BATTERY_CHAR_UUID)
            self.battery_level = battery_data[0] if battery_data else 0
            print(f"Battery level: {self.battery_level}%")
            return self.battery_level
        except Exception as e:
            print(f"Could not read battery: {e}")
            return 0
    
    def _notification_handler(self, sender, data: bytearray):
        """Handle incoming BLE notifications."""
        try:
            decoded = data.decode('utf-8')
            self._buffer += decoded
            
            # Split by newlines
            lines = self._buffer.split('\n')
            self._buffer = lines[-1]  # Keep partial line
            
            for line in lines[:-1]:
                line = line.strip()
                if not line:
                    continue
                
                parts = line.split(',')
                if len(parts) >= 3:
                    try:
                        values = [int(p.strip()) for p in parts[:3]]
                        # Skip samples with zero values
                        if 0 not in values:
                            self.collected_data.append(line)
                            self.sample_count += 1
                            
                            if self._data_callback:
                                self._data_callback(line)
                    except ValueError:
                        pass
                        
        except Exception as e:
            print(f"Notification handler error: {e}")
    
    def start_data_collection(
        self,
        duration_seconds: int = 60,
        command: str = "1",
        data_callback: Optional[Callable[[str], None]] = None
    ) -> List[str]:
        """Start collecting data from the device."""
        return self._run_async(
            self._start_data_collection_async(duration_seconds, command, data_callback)
        )
    
    async def _start_data_collection_async(
        self,
        duration_seconds: int = 60,
        command: str = "6",
        data_callback: Optional[Callable[[str], None]] = None
    ) -> List[str]:
        """Async implementation of data collection."""
        if not self.client or not self.is_connected:
            raise Exception("Device not connected")
        
        self.collected_data.clear()
        self.sample_count = 0
        self._buffer = ""
        self._collection_cancelled = False
        self.is_collecting = True
        self._data_callback = data_callback
        
        try:
            # Start notifications
            await self.client.start_notify(
                NORDIC_UART_TX_CHAR_UUID,
                self._notification_handler
            )
            
            # Send start command
            await self._send_command_async(command)
            
            # Wait for duration or cancellation
            for _ in range(duration_seconds):
                if self._collection_cancelled:
                    break
                await asyncio.sleep(1)
            
            # Stop notifications
            try:
                await self.client.stop_notify(NORDIC_UART_TX_CHAR_UUID)
            except:
                pass
            
            print(f"Collection complete. {self.sample_count} samples collected.")
            return self.collected_data
            
        except Exception as e:
            print(f"Collection error: {e}")
            raise
        finally:
            self.is_collecting = False
            self._data_callback = None
    
    def cancel_collection(self):
        """Cancel ongoing data collection."""
        self._collection_cancelled = True
        self.is_collecting = False
    
    def save_to_file(self, filepath: Optional[str] = None) -> str:
        """Save collected data to a file."""
        if not self.collected_data:
            raise Exception("No data to save")
        
        if filepath is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filepath = f"files/nadi_data_{timestamp}.txt"
        
        import os
        os.makedirs(os.path.dirname(filepath) if os.path.dirname(filepath) else "files", exist_ok=True)
        
        with open(filepath, 'w') as f:
            f.write('\n'.join(self.collected_data))
        
        print(f"Data saved to {filepath}")
        return filepath
    
    def get_status(self) -> dict:
        """Get current BLE handler status."""
        return {
            "connected": self.is_connected,
            "device_name": self.connected_device.name if self.connected_device else None,
            "device_address": self.connected_device.address if self.connected_device else None,
            "battery_level": self.battery_level,
            "is_collecting": self.is_collecting,
            "sample_count": self.sample_count,
            "discovered_devices": len(self.discovered_devices)
        }


if __name__ == "__main__":
    # Test the BLE handler
    handler = BLEHandler()
    print("Scanning for devices...")
    devices = handler.scan_for_devices(timeout=5.0)
    
    if devices:
        print(f"\nFound {len(devices)} device(s):")
        for i, d in enumerate(devices):
            print(f"  {i+1}. {d.name} ({d.address})")
    else:
        print("No devices found")
