// // ignore_for_file: constant_identifier_names, non_constant_identifier_names

// import 'dart:async';
// import 'dart:convert';
// import 'dart:developer';
// import 'dart:io';
// import 'package:flutter/material.dart';
// import 'package:flutter/services.dart';
// import 'package:flutter_blue_plus/flutter_blue_plus.dart';
// import 'package:geolocator/geolocator.dart';
// import 'package:get/get.dart';
// import 'package:hive/hive.dart';
// import 'package:npulse/features/nadi_history/controllers/nadi_controller.dart';
// import 'package:npulse/features/real_time_graphs/realtime_line_chart.dart';
// import 'package:path_provider/path_provider.dart';
// import 'package:fluttertoast/fluttertoast.dart';
// import 'package:wakelock_plus/wakelock_plus.dart';

// String NORDIC_UART_SERVICE_UUID = "6e400001-b5a3-f393-e0a9-e50e24dcca9e";
// String NORDIC_UART_TX_CHAR_UUID =
//     "6e400003-b5a3-f393-e0a9-e50e24dcca9e"; // NOTIFY
// String NORDIC_UART_RX_CHAR_UUID =
//     "6e400002-b5a3-f393-e0a9-e50e24dcca9e"; // WRITE
// String BATTERY_SERVICE_UUID = "0000180f-0000-1000-8000-00805f9b34fb";
// String BATTERY_CHAR_UUID = "00002a19-0000-1000-8000-00805f9b34fb";

// class UserBluetoothConnectionController extends GetxController {
//   GlobalKey<RealtimeLineChartState>? heartRateChartKey;
//   final RxBool isConnecting = false.obs;
//   final RxBool isLoading = false.obs;
//   final RxBool isReading = false.obs;
//   final RxBool isConnected = false.obs;
//   final RxBool isBluetoothOn = false.obs;
//   final RxString batteryLevel = ''.obs;
//   String fileString = '';
//   bool readingTimer = false;
//   RxInt readingTime = 120.obs;
//   StreamSubscription? scanSubscription;
//   BluetoothDevice? connectedDevice;
//   StreamSubscription<BluetoothConnectionState>? connectionSubscription;
//   StreamSubscription<List<int>>? batterySubscription;
//   bool showDisconnectToast = true;
//   bool isOnWrist = false;
//   BluetoothCharacteristic? _rxCharacteristic;

//   String nadiPersonName = '';
//   List<int> dataToSendData = [];
//   RxBool isVital = false.obs;

//   // New flag to cancel capture if device disconnects mid-read.
//   bool _capturingCancelled = false;

//   // List to store discovered Bluetooth devices.
//   final List<BluetoothDevice> bleDevices = [];

//   @override
//   void onInit() {
//     super.onInit();
//     getNadiPersonName();
//     checkBluetooth();
//   }

//   getNadiPersonName() async {
//     try {
//       var box = Hive.box('appData');
//       var temp = await box.get('username');
//       nadiPersonName = temp.toString().split(' ').first;
//     } catch (e) {
//       log('Error fetching user name: $e');
//     }
//   }

//   @override
//   void onClose() {
//     scanSubscription?.cancel();
//     connectionSubscription?.cancel();
//     batterySubscription?.cancel();
//     notificationSub?.cancel();
//     super.onClose();
//   }

//   // -------------------------------------------------------------
//   // 1) HELPER: Try to fetch TX, RX, and Battery by known UUIDs
//   // -------------------------------------------------------------
//   Future<Map<String, BluetoothCharacteristic>> getHardcodedCharacteristics(
//     BluetoothDevice device,
//   ) async {
//     final Map<String, BluetoothCharacteristic> result = {};

//     // Discover services once.
//     final services = await device.discoverServices();

//     // Attempt Nordic UART service.
//     final uartService = services.firstWhereOrNull(
//       (s) => s.uuid.toString().toLowerCase() == NORDIC_UART_SERVICE_UUID,
//     );
//     if (uartService != null) {
//       final txChar = uartService.characteristics.firstWhereOrNull(
//         (c) => c.uuid.toString().toLowerCase() == NORDIC_UART_TX_CHAR_UUID,
//       );
//       final rxChar = uartService.characteristics.firstWhereOrNull(
//         (c) => c.uuid.toString().toLowerCase() == NORDIC_UART_RX_CHAR_UUID,
//       );
//       if (txChar != null && rxChar != null) {
//         result["tx"] = txChar;
//         result["rx"] = rxChar;
//       }
//     }

//     // Attempt Battery service.
//     final batteryService = services.firstWhereOrNull(
//       (s) => s.uuid.toString().toLowerCase() == BATTERY_SERVICE_UUID,
//     );
//     if (batteryService != null) {
//       final batteryChar = batteryService.characteristics.firstWhereOrNull(
//         (c) => c.uuid.toString().toLowerCase() == BATTERY_CHAR_UUID,
//       );
//       if (batteryChar != null) {
//         result["battery"] = batteryChar;
//       }
//     }

//     return result;
//   }

//   // Bluetooth Methods
//   Future<void> checkBluetooth() async {
//     try {
//       isBluetoothOn.value =
//           await FlutterBluePlus.adapterState.first == BluetoothAdapterState.on;
//       log('Bluetooth is on: ${isBluetoothOn.value}');
//     } catch (e) {
//       log('Error checking Bluetooth state: $e');
//     }
//   }

//   Future<void> turnonBluetooth() async {
//     try {
//       await FlutterBluePlus.turnOn();
//       isBluetoothOn.value =
//           await FlutterBluePlus.adapterState.first == BluetoothAdapterState.on;
//     } catch (e) {
//       Fluttertoast.showToast(msg: 'Failed to turn on Bluetooth: $e');
//     }
//   }

//   Future<void> startDiscovery() async {
//     if (!await Geolocator.isLocationServiceEnabled() && GetPlatform.isAndroid) {
//       showLocationSettingsDialog();
//       return;
//     }
//     isConnecting.value = true;
//     try {
//       await performScan();
//     } catch (e) {
//       log('Error during discovery: ${e.toString()}');
//     } finally {
//       isConnecting.value = false;
//       // if (!isConnected.value) {
//       //   Fluttertoast.showToast(msg: "device_not_found".tr);
//       // }
//     }
//   }

//   void showLocationSettingsDialog() {
//     showDialog(
//       context: Get.context!,
//       builder: (BuildContext context) {
//         return AlertDialog(
//           title: Text("location_services_disabled".tr),
//           content: Text("please_enable_location_services_to_continue".tr),
//           actions: [
//             TextButton(
//               onPressed: () {
//                 Get.back();
//                 openLocationSettings();
//               },
//               child: Text("open_settings".tr),
//             ),
//             TextButton(onPressed: () => Get.back(), child: Text("cancel".tr)),
//           ],
//         );
//       },
//     );
//   }

//   Future<void> openLocationSettings() async {
//     if (!await Geolocator.openLocationSettings()) {
//       Fluttertoast.showToast(msg: "failed_to_open_location_settings".tr);
//     }
//   }

//   // -------------------------------------------------------------
//   // Updated performScan: Gathers unique devices and handles multiple devices.
//   // -------------------------------------------------------------
//   Future<void> performScan() async {
//     // Clear previously discovered devices.
//     bleDevices.clear();
//     final Map<String, ScanResult> discoveredResultsMap = {};

//     final subscription = FlutterBluePlus.onScanResults.listen((results) {
//       for (final result in results) {
//         final mac = result.device.remoteId.toString().toLowerCase();
//         if (!discoveredResultsMap.containsKey(mac)) {
//           discoveredResultsMap[mac] = result;
//           bleDevices.add(result.device);
//           log('$mac: "${result.advertisementData.advName}" found!');
//         }
//       }
//     }, onError: (e) => log('Scan error: $e'));

//     await FlutterBluePlus.adapterState
//         .where((state) => state == BluetoothAdapterState.on)
//         .first;

//     await FlutterBluePlus.startScan(
//       withNames: ["nPulse001", "nPulse", "NADI_PULSE", "IMU_DUAL_CHAR"],
//       timeout: const Duration(seconds: 4),
//     );
//     await FlutterBluePlus.isScanning.where((scanning) => !scanning).first;
//     await subscription.cancel();

//     final discoveredResults = discoveredResultsMap.values.toList();

//     if (discoveredResults.isEmpty) {
//       Fluttertoast.showToast(msg: "device_not_found".tr);
//       return;
//     }

//     // --- New: save all discovered devices to Hive ---
//     final box = await Hive.openBox('appData');
//     // Build a List<Map> with name, mac, serial
//     final List<Map<String, String>> toStore = discoveredResults.map((r) {
//       // Try to decode manufacturer‐data to get a serial string
//       final manuData = r.advertisementData.manufacturerData;
//       String serial = '';
//       if (manuData.isNotEmpty) {
//         try {
//           serial = utf8.decode(manuData.values.first);
//         } catch (_) {}
//       }
//       return {
//         'name': r.advertisementData.advName,
//         'mac': r.device.remoteId.toString(),
//         'serial': serial,
//       };
//     }).toList();
//     await box.put('discoveredDevices', toStore);
//     // --------------------------------------------------

//     if (discoveredResults.length == 1) {
//       connectToDevice(discoveredResults.first.device);
//     } else {
//       _showDeviceSelectionDialog(discoveredDevices: discoveredResults);
//     }
//   }

//   Future<void> connectToDevice(BluetoothDevice device) async {
//     _capturingCancelled = false; // Reset capture cancel flag.
//     final box = await Hive.openBox('appData');

//     // If already connected, optionally you can skip or disconnect first.
//     if (isConnected.value) return;

//     try {
//       await device.connect();
//       displayBpm = 0.0;
//       signalQuality = 0.0;
//       signalQualityLabel = '';
//       _capturingCancelled = false; // Reset capture cancel flag.
//       isConnected.value = true;
//       isConnecting.value = false;
//       connectedDevice = device;
//       checkConnection(device); // Monitor connection changes.
//       Fluttertoast.showToast(msg: "connected_to_device".tr);
//       batteryPercentage(0);
//       box.put('savedMac', device.remoteId.toString());
//     } catch (e) {
//       Fluttertoast.showToast(msg: 'Error connecting to device: $e');
//     }
//   }

//   Future<void> sendResetCommand() async {
//     if (connectedDevice == null) {
//       log('[WARN] no device connected—skipping RST');
//       return;
//     }

//     // If we don't have the RX char yet, try to discover it now
//     if (_rxCharacteristic == null && connectedDevice != null) {
//       try {
//         log('[DEBUG] RX char not cached — discovering now');
//         final chars = await getHardcodedCharacteristics(connectedDevice!);
//         _rxCharacteristic = chars['rx'];
//         if (_rxCharacteristic != null) {
//           log(
//             '[DEBUG] RX characteristic found and cached: ${_rxCharacteristic!.uuid}',
//           );
//         } else {
//           log('[WARN] RX characteristic still not found after discovery');
//         }
//       } catch (e) {
//         log('[ERROR] failed to discover RX characteristic: $e');
//       }
//     }

//     // Send RST if we now have the RX char
//     if (_rxCharacteristic != null) {
//       try {
//         log('[DEBUG] sending RST');
//         await _rxCharacteristic!.write(
//           Uint8List.fromList(utf8.encode("SLEEP")),
//         );
//         await Future.delayed(const Duration(milliseconds: 200));
//         log('[DEBUG] RST sent');
//       } catch (e) {
//         log('[ERROR] failed to send RST: $e');
//       }
//     } else {
//       log('[WARN] no RX characteristic available – skipping RST');
//     }
//   }

//   Future<bool> disconnectDevice() async {
//     if (connectedDevice != null) {
//       _capturingCancelled = true;
//       try {
//         await sendResetCommand();
//       } catch (e) {
//         log('Error during disconnect: $e');
//       }
//       displayBpm = 0.0;
//       signalQuality = 0.0;
//       signalQualityLabel = '';
//       isConnected.value = false;
//       isReading.value = false;
//       connectedDevice = null;
//       connectionSubscription?.cancel();
//       connectionSubscription = null;
//       batterySubscription?.cancel();
//       batterySubscription = null;
//       notificationSub?.cancel();
//       notificationSub = null;
//       batteryLevel.value = '';
//       Get.find<NadiController>().testCount = 1.obs;
//     }
//     return true;
//   }

//   void disposeData() {
//     var controller = Get.find<NadiController>();
//     controller.lastMealText.text = '';
//     controller.isLeftHand = true;
//     controller.lastMealTime = null;
//   }

//   void checkConnection(BluetoothDevice device) {
//     connectionSubscription?.cancel();
//     connectionSubscription = device.connectionState.listen(
//       (state) {
//         if (state == BluetoothConnectionState.disconnected) {
//           _capturingCancelled = true;
//           batterySubscription?.cancel();
//           if (showDisconnectToast) {
//             Fluttertoast.showToast(msg: "device_disconnected".tr);
//           }
//           isConnected.value = false;
//           isReading.value = false;
//           startReadingTime();
//           isConnecting.value = false;
//         }
//       },
//       onError: (error) {
//         log('Connection error: $error');
//       },
//     );
//   }

//   // -------------------------------------------------------------
//   // 2) BATTERY PERCENTAGE USING HARDCODED THEN FALLBACK
//   // -------------------------------------------------------------
//   Future<void> batteryPercentage(int cycleCount) async {
//     if (cycleCount >= 5) {
//       log("cycle_limit_reached_ending_loop".tr);
//       return;
//     }
//     if (connectedDevice == null) return;
//     try {
//       // 1) Try to fetch battery characteristic from the known UUID.
//       final charMap = await getHardcodedCharacteristics(connectedDevice!);
//       BluetoothCharacteristic? batteryCharacteristic = charMap["battery"];

//       // 2) If not found, fallback to enumerating everything as before.
//       if (batteryCharacteristic == null) {
//         List<BluetoothService> services = await connectedDevice!
//             .discoverServices();
//         for (BluetoothService service in services) {
//           for (BluetoothCharacteristic characteristic
//               in service.characteristics) {
//             if (characteristic.properties.read &&
//                 characteristic.properties.notify) {
//               batteryCharacteristic = characteristic;
//               break;
//             }
//           }
//           if (batteryCharacteristic != null) break;
//         }
//       }

//       // 3) If we got a battery characteristic, read it.
//       if (batteryCharacteristic != null) {
//         await batteryCharacteristic.setNotifyValue(true);
//         List<int> value = await batteryCharacteristic.read();
//         log('Battery level: $value');
//         batteryLevel.value = value.isNotEmpty ? value.first.toString() : '0';
//         if (batteryLevel.value == '100') {
//           log("battery_full_stopping_notification".tr);
//           await batteryCharacteristic.setNotifyValue(false);
//           return;
//         }
//       }

//       await Future.delayed(const Duration(seconds: 1));
//       await batteryPercentage(cycleCount + 1);
//     } catch (e) {
//       log('Error in batteryPercentage: $e');
//     }
//   }

//   /// Uses a periodic timer to decrement readingTime. When time reaches 0,
//   /// writes the data to file only if the device is still connected.
//   void readingTimeCounter() {
//     Timer.periodic(const Duration(seconds: 1), (timer) {
//       if (readingTime.value <= 0) {
//         timer.cancel();
//         // Only write file if capture wasn’t cancelled.
//         if (connectedDevice != null &&
//             isConnected.value &&
//             !_capturingCancelled) {
//           _writeDataToFile(dataToSendData)
//               .then((path) {
//                 isReading.value = false;
//               })
//               .catchError((e) {
//                 log('Error writing file: $e');
//               });
//         }
//       } else {
//         readingTime.value = (readingTime.value - 1).clamp(0, 60);
//       }
//     });
//   }

//   int _readingSession = 0;
//   Timer? _readingTimer;

//   RxBool isPaused = false.obs;

//   void startReadingTime({bool reset = true}) {
//     // Cancel any existing timer
//     _readingTimer?.cancel();

//     // New session
//     _readingSession++;

//     if (reset) {
//       readingTime.value = 120;
//     }

//     isPaused.value = false;

//     _readingTimer = Timer.periodic(const Duration(seconds: 1), (timer) {
//       // If paused, do nothing
//       if (isPaused.value) return;

//       if (readingTime.value > 0) {
//         readingTime.value--;
//       } else {
//         timer.cancel();
//       }
//     });
//   }

//   void resumeReadingTime() {
//     if (_readingTimer == null || !_readingTimer!.isActive) {
//       startReadingTime(reset: false);
//     }
//     isPaused.value = false;
//   }

//   void stopReadingTime() {
//     _readingTimer?.cancel();
//     _readingSession++;
//   }

//   void pauseReadingTime() {
//     isPaused.value = true;
//   }

//   Future<String> _writeDataToFile(List<int> data, {String? filename}) async {
//     final directory = await getApplicationDocumentsDirectory();
//     final path =
//         '${directory.path}/output_$nadiPersonName${filename ?? ''}.txt';
//     final file = File(path);
//     await file.writeAsString(utf8.decode(data));
//     return path;
//   }

//   StreamSubscription<List<int>>? notificationSub;
//   int skipCounter = 0;

//   String buffer = '';
//   Future<String> sendCommandAndReceiveFile({String? command}) async {
//     await WakelockPlus.enable();
//     if (connectedDevice == null) throw Exception("please_connect_to_device".tr);
//     _capturingCancelled = false;
//     isReading.value = true;
//     dataToSendData.clear();

//     try {
//       isVital.value = (command != null && command == '5') ? true : false;

//       // 1. Try to get hardcoded TX/RX characteristics.
//       final charMap = await getHardcodedCharacteristics(connectedDevice!);
//       BluetoothCharacteristic? notifyCharacteristic = charMap["tx"];
//       BluetoothCharacteristic? writeCharacteristic = charMap["rx"];

//       // 2. If not found, fall back to discovering all characteristics.
//       if (notifyCharacteristic == null || writeCharacteristic == null) {
//         final characteristics = (await connectedDevice!.discoverServices())
//             .expand((service) => service.characteristics)
//             .toList();
//         notifyCharacteristic = characteristics.firstWhereOrNull(
//           (c) => c.properties.notify || c.properties.indicate,
//         );
//         writeCharacteristic = characteristics.firstWhereOrNull(
//           (c) => c.properties.writeWithoutResponse,
//         );
//       }

//       if (notifyCharacteristic == null) {
//         throw Exception("no_notify_characteristic_found".tr);
//       }

//       // 3. Ensure the characteristic supports notify or indicate.
//       if (!(notifyCharacteristic.properties.notify ||
//           notifyCharacteristic.properties.indicate)) {
//         throw Exception(
//           "Characteristic ${notifyCharacteristic.uuid} does NOT support notify or indicate.",
//         );
//       }

//       // 4. Enable notifications.
//       await notifyCharacteristic.setNotifyValue(true);

//       // 5. Listen for incoming data.
//       notificationSub = notifyCharacteristic.onValueReceived.listen((value) {
//         try {
//           buffer += utf8.decode(value); // accumulate

//           // Split by newline (\n or \r\n)
//           List<String> lines = buffer.split(RegExp(r'\r?\n'));

//           // Keep last partial line in the buffer
//           buffer = lines.removeLast();

//           for (var line in lines) {
//             line = line.trim();
//             if (line.isEmpty) continue;

//             final parts = line.split(',').map((e) => int.tryParse(e)).toList();
//             final hasZero = parts.any((e) => e == 0);

//             if (!hasZero) {
//               dataToSendData.addAll(value);
//               skipCounter++;
//               heartRateChartKey?.currentState?.handleNewData(line);
//             } else {
//               print('Skipped sample due to zero value: $line');
//             }
//           }
//         } catch (e) {
//           log("Error processing incoming data: $e");
//         }
//       });

//       // 6. Write command to the RX characteristic if available.
//       if (writeCharacteristic != null) {
//         await writeCharacteristic.write(
//           Uint8List.fromList(utf8.encode(command ?? '1')),
//         );
//       }

//       for (var i = 0; i < 60; i++) {
//         await Future.delayed(const Duration(seconds: 1));
//         if (_capturingCancelled) {
//           // immediate cleanup
//           isReading.value = false;
//           notificationSub?.cancel();
//           throw Exception(
//             "device_disconnected_during_capture_aborting_file_write".tr,
//           );
//         }
//       }

//       notificationSub?.cancel();
//       return _writeDataToFile(
//         dataToSendData,
//         filename: command == '5' ? '_BP_file' : '',
//       );
//     } catch (e) {
//       isReading.value = false;
//       log("Error in sendCommandAndReceiveFile: $e");
//       rethrow;
//     }
//   }

//   void isValidFormat(String input) {
//     if (input.isEmpty) {
//       Fluttertoast.showToast(
//         msg: "an_error_occurred_please_reconnect_your_device".tr,
//       );
//       disconnectDevice();
//     }
//   }

//   bool isRemoved = false;
//   bool isWrapped = false;

//   Future<void> disconnectAfterTests() async {
//     if (connectedDevice != null) {
//       await disconnectDevice();
//     }
//   }

//   String uint8ListToString(List<int> data) {
//     // Convert List<int> to Uint8List
//     Uint8List uint8list = Uint8List.fromList(data);

//     // Decode the Uint8List to String, ignoring any invalid characters
//     String result = utf8.decode(uint8list, allowMalformed: true);

//     // Optionally, remove any non-printable/control characters
//     result = result.replaceAll(RegExp(r'[\x00-\x1F\x7F]'), '');

//     return result;
//   }

//   // UI Stuff
//   void _showDeviceSelectionDialog({
//     required List<ScanResult> discoveredDevices,
//   }) async {
//     final box = await Hive.openBox('appData');
//     final String savedMac = box.get('savedMac') ?? '';

//     // 1) Load the persisted scan‐list (each entry: { name, mac, serial })
//     final List<Map<String, String>> stored =
//         (box.get('discoveredDevices') as List<dynamic>?)
//             ?.cast<Map<String, String>>() ??
//         <Map<String, String>>[];

//     // 2) Locate the saved entry (if any)
//     final Map<String, String>? savedEntry =
//         stored
//             .firstWhere(
//               (d) => d['mac'] == savedMac,
//               orElse: () => <String, String>{},
//             )
//             .isNotEmpty
//         ? stored.firstWhere((d) => d['mac'] == savedMac)
//         : null;

//     showDialog(
//       context: Get.context!,
//       builder: (context) {
//         return Dialog(
//           shape: RoundedRectangleBorder(
//             borderRadius: BorderRadius.circular(20),
//           ),
//           backgroundColor: Theme.of(context).colorScheme.surface,
//           child: Padding(
//             padding: const EdgeInsets.all(20),
//             child: Column(
//               mainAxisSize: MainAxisSize.min,
//               crossAxisAlignment: CrossAxisAlignment.start,
//               children: [
//                 // Header
//                 Row(
//                   children: [
//                     const Icon(Icons.bluetooth_searching, size: 28),
//                     const SizedBox(width: 12),
//                     Expanded(
//                       child: Text(
//                         "multiple_devices_found".tr,
//                         style: Theme.of(context).textTheme.titleLarge?.copyWith(
//                           fontWeight: FontWeight.bold,
//                         ),
//                       ),
//                     ),
//                     IconButton(
//                       icon: const Icon(Icons.close),
//                       onPressed: () => Navigator.of(context).pop(),
//                     ),
//                   ],
//                 ),
//                 const SizedBox(height: 16),

//                 // Previously Connected (with name + serial)
//                 if (savedEntry != null) ...[
//                   Text(
//                     "previously_connected".tr,
//                     style: Theme.of(context).textTheme.titleSmall?.copyWith(
//                       color: Theme.of(context).colorScheme.secondary,
//                     ),
//                   ),
//                   const SizedBox(height: 8),
//                   InkWell(
//                     onTap: () async {
//                       Navigator.of(context).pop();
//                       if (isConnected.value) {
//                         await disconnectDevice();
//                       }
//                       // Find the actual BluetoothDevice in bleDevices
//                       connectedDevice = bleDevices.firstWhere(
//                         (d) => d.remoteId.toString() == savedMac,
//                         orElse: () => discoveredDevices.first.device,
//                       );
//                       await connectToDevice(connectedDevice!);
//                     },
//                     borderRadius: BorderRadius.circular(12),
//                     child: Container(
//                       padding: const EdgeInsets.all(12),
//                       decoration: BoxDecoration(
//                         borderRadius: BorderRadius.circular(12),
//                         color: Theme.of(
//                           context,
//                         ).colorScheme.secondaryContainer.withOpacity(0.3),
//                       ),
//                       child: Row(
//                         children: [
//                           Container(
//                             padding: const EdgeInsets.all(8),
//                             decoration: BoxDecoration(
//                               color: Theme.of(
//                                 context,
//                               ).colorScheme.secondaryContainer,
//                               borderRadius: BorderRadius.circular(8),
//                             ),
//                             child: const Icon(Icons.bluetooth_connected),
//                           ),
//                           const SizedBox(width: 12),
//                           Expanded(
//                             child: Column(
//                               crossAxisAlignment: CrossAxisAlignment.start,
//                               children: [
//                                 Text(
//                                   savedEntry['name'] ?? "unknown".tr,
//                                   style: Theme.of(
//                                     context,
//                                   ).textTheme.titleMedium,
//                                 ),
//                                 Text(
//                                   'Serial: ${savedEntry['serial'] ?? ''}',
//                                   style: Theme.of(context).textTheme.bodySmall,
//                                 ),
//                                 Text(
//                                   'MAC: $savedMac',
//                                   style: Theme.of(context).textTheme.bodySmall,
//                                 ),
//                               ],
//                             ),
//                           ),
//                           Icon(
//                             Icons.arrow_forward_ios,
//                             size: 16,
//                             color: Theme.of(
//                               context,
//                             ).colorScheme.onSurfaceVariant,
//                           ),
//                         ],
//                       ),
//                     ),
//                   ),
//                   const SizedBox(height: 16),
//                   const Divider(),
//                   const SizedBox(height: 16),
//                 ],

//                 // Available Devices
//                 Text(
//                   "available_devices".tr,
//                   style: Theme.of(context).textTheme.titleSmall?.copyWith(
//                     color: Theme.of(context).colorScheme.secondary,
//                   ),
//                 ),
//                 const SizedBox(height: 8),
//                 ConstrainedBox(
//                   constraints: BoxConstraints(
//                     maxHeight: MediaQuery.of(context).size.height * 0.4,
//                   ),
//                   child: SingleChildScrollView(
//                     child: Column(
//                       children: discoveredDevices.map((result) {
//                         final manuData =
//                             result.advertisementData.manufacturerData;
//                         final serialStr = manuData.isNotEmpty
//                             ? uint8ListToString(manuData.values.first)
//                             : 'N/A';
//                         final device = result.device;
//                         return Padding(
//                           padding: const EdgeInsets.only(bottom: 8),
//                           child: InkWell(
//                             onTap: () async {
//                               Navigator.of(context).pop();
//                               if (isConnected.value) {
//                                 await disconnectDevice();
//                               }
//                               await connectToDevice(device);
//                             },
//                             borderRadius: BorderRadius.circular(12),
//                             child: Container(
//                               padding: const EdgeInsets.all(12),
//                               decoration: BoxDecoration(
//                                 borderRadius: BorderRadius.circular(12),
//                                 border: Border.all(
//                                   color: Theme.of(
//                                     context,
//                                   ).colorScheme.outline.withOpacity(0.3),
//                                 ),
//                               ),
//                               child: Row(
//                                 children: [
//                                   Container(
//                                     padding: const EdgeInsets.all(8),
//                                     decoration: BoxDecoration(
//                                       color: Theme.of(
//                                         context,
//                                       ).colorScheme.surfaceContainerHighest,
//                                       borderRadius: BorderRadius.circular(8),
//                                     ),
//                                     child: const Icon(Icons.bluetooth),
//                                   ),
//                                   const SizedBox(width: 12),
//                                   Expanded(
//                                     child: Column(
//                                       crossAxisAlignment:
//                                           CrossAxisAlignment.start,
//                                       children: [
//                                         Text(
//                                           result.advertisementData.advName,
//                                           style: Theme.of(
//                                             context,
//                                           ).textTheme.titleMedium,
//                                         ),
//                                         Text(
//                                           'Serial: $serialStr',
//                                           style: Theme.of(
//                                             context,
//                                           ).textTheme.bodySmall,
//                                         ),
//                                         Text(
//                                           'MAC: ${device.remoteId}',
//                                           style: Theme.of(
//                                             context,
//                                           ).textTheme.bodySmall,
//                                         ),
//                                       ],
//                                     ),
//                                   ),
//                                   Icon(
//                                     Icons.arrow_forward_ios,
//                                     size: 16,
//                                     color: Theme.of(
//                                       context,
//                                     ).colorScheme.onSurfaceVariant,
//                                   ),
//                                 ],
//                               ),
//                             ),
//                           ),
//                         );
//                       }).toList(),
//                     ),
//                   ),
//                 ),
//               ],
//             ),
//           ),
//         );
//       },
//     );
//   }

//   Future<String> _captureSegment({
//     required String command, // command to send, e.g. '1' or '5'
//     required String filenameSuffix, // e.g. '_part1' or '_part2' or '_BP_file'
//     int durationSeconds = 60,
//   }) async {
//     if (connectedDevice == null) throw Exception("please_connect_to_device".tr);

//     _capturingCancelled = false;
//     isReading.value = true;

//     // reuse buffer and data list but isolated per segment
//     String localBuffer = '';
//     final List<int> localDataBuffer = [];
//     StreamSubscription<List<int>>? localSub;

//     try {
//       // 1) discover characteristics (try hardcoded first)
//       final charMap = await getHardcodedCharacteristics(connectedDevice!);
//       BluetoothCharacteristic? notifyCharacteristic = charMap["tx"];
//       BluetoothCharacteristic? writeCharacteristic = charMap["rx"];

//       if (notifyCharacteristic == null || writeCharacteristic == null) {
//         final characteristics = (await connectedDevice!.discoverServices())
//             .expand((s) => s.characteristics)
//             .toList();
//         notifyCharacteristic = characteristics.firstWhereOrNull(
//           (c) => c.properties.notify || c.properties.indicate,
//         );
//         writeCharacteristic = characteristics.firstWhereOrNull(
//           (c) => c.properties.writeWithoutResponse || c.properties.write,
//         );
//       }

//       if (notifyCharacteristic == null) {
//         throw Exception("no_notify_characteristic_found".tr);
//       }
//       // 2) enable notify and listen
//       await notifyCharacteristic.setNotifyValue(true);

//       localSub = notifyCharacteristic.onValueReceived.listen((value) {
//         try {
//           // accumulate into local buffers
//           localBuffer += utf8.decode(value);
//           // split lines
//           List<String> lines = localBuffer.split(RegExp(r'\r?\n'));
//           localBuffer = lines.removeLast(); // keep partial for next chunk
//           for (var line in lines) {
//             line = line.trim();
//             if (line.isEmpty) continue;
//             // keep same zero-check logic as earlier
//             final parts = line.split(',').map((e) => int.tryParse(e)).toList();
//             final hasZero = parts.any((e) => e == 0);
//             if (!hasZero) {
//               localDataBuffer.addAll(utf8.encode('$line\n'));
//               skipCounter++;
//               // update chart if available
//               heartRateChartKey?.currentState?.handleNewData(line);
//             } else {
//               // skip sample
//             }
//           }
//         } catch (e) {
//           log("Error processing incoming data (segment): $e");
//         }
//       });

//       // 3) send command to start this segment
//       if (writeCharacteristic != null) {
//         await writeCharacteristic.write(
//           Uint8List.fromList(utf8.encode(command)),
//         );
//       }

//       // 4) wait for durationSeconds or abort on disconnect/cancel
//       final int waitLoop = durationSeconds;
//       for (var i = 0; i < waitLoop; i++) {
//         await Future.delayed(const Duration(seconds: 1));
//         if (_capturingCancelled) {
//           localSub.cancel();
//           isReading.value = false;
//           throw Exception(
//             "device_disconnected_during_capture_aborting_file_write".tr,
//           );
//         }
//       }

//       // 5) done with notifications for this segment
//       await notifyCharacteristic.setNotifyValue(false);
//       await localSub.cancel();

//       // 6) write segment to file
//       final directory = await getApplicationDocumentsDirectory();
//       final path =
//           '${directory.path}/output_$nadiPersonName$filenameSuffix.txt';
//       final file = File(path);
//       await file.writeAsString(utf8.decode(localDataBuffer));
//       isReading.value = false;
//       return path;
//     } catch (e) {
//       isReading.value = false;
//       log("Error in _captureSegment: $e");
//       try {
//         await localSub?.cancel();
//       } catch (_) {}
//       rethrow;
//     }
//   }

//   Future<List<String>> performTwoMinuteCaptureAndSend({
//     required String commandForSegments,
//     int initialDelaySeconds = 2, // requested 2 second delay before each segment
//     // int totalDurationSeconds = 120, // total timer shown to user
//   }) async {
//     if (connectedDevice == null) throw Exception("please_connect_to_device".tr);
//     _capturingCancelled = false;
//     isReading.value = true;

//     final List<String> capturedPaths = [];

//     try {
//       // Start a single total countdown (UI can bind to readingTime)

//       // Wait initial delay before first capture so device can settle
//       await Future.delayed(const Duration(milliseconds: 1000));
//       if (_capturingCancelled) throw Exception("capture_cancelled".tr);
//       startReadingTime();
//       // Capture first 60s segment
//       final firstPath = await _captureSegment(
//         command: commandForSegments,
//         filenameSuffix: '_part1',
//         durationSeconds: 60,
//       );
//       Get.find<NadiController>().isLoading.value = true;
//       pauseReadingTime();
//       capturedPaths.add(firstPath);

//       // Another small delay before second capture (also requested)
//       await Future.delayed(Duration(seconds: initialDelaySeconds));
//       if (_capturingCancelled) throw Exception("capture_cancelled".tr);
//       Get.find<NadiController>().isLoading.value = false;
//       resumeReadingTime();
//       // Capture second 60s segment
//       final secondPath = await _captureSegment(
//         command: commandForSegments,
//         filenameSuffix: '_part2',
//         durationSeconds: 60,
//       );
//       capturedPaths.add(secondPath);
//       stopReadingTime();
//       return capturedPaths;
//     } catch (e) {
//       log("Error in performTwoMinuteCaptureAndSend: $e");
//       stopReadingTime();
//       rethrow;
//     } finally {
//       isReading.value = false;
//     }
//   }

//   final List<String> char1Data = [];
//   final List<String> char2Data = [];

//   Future<void> captureBleFor60SecondsTwoCharacteristics() async {
//     if (connectedDevice == null) {
//       log('[BLE TEST] Device not connected');
//       return;
//     }

//     int char1Samples = 0;
//     int char2Samples = 0;

//     final List<StreamSubscription<List<int>>> subs = [];

//     log('[BLE TEST] Discovering services...');
//     final services = await connectedDevice!.discoverServices();

//     final notifyChars = services
//         .expand((s) => s.characteristics)
//         .where((c) => c.properties.notify || c.properties.indicate)
//         .toList();

//     if (notifyChars.length < 2) {
//       log('[BLE TEST] Less than 2 NOTIFY characteristics found');
//       return;
//     }

//     final BluetoothCharacteristic char1 = notifyChars[0];
//     final BluetoothCharacteristic char2 = notifyChars[1];

//     log('[BLE TEST] CHAR1 → ${char1.uuid}');
//     log('[BLE TEST] CHAR2 → ${char2.uuid}');

//     // ---- Enable notify safely (Android CCCD issue workaround) ----
//     for (final c in [char1, char2]) {
//       await c.setNotifyValue(false);
//       await Future.delayed(const Duration(milliseconds: 150));
//       await c.setNotifyValue(true);
//       await Future.delayed(const Duration(milliseconds: 300));
//     }

//     // ---- Listen CHAR1 ----
//     subs.add(
//       char1.onValueReceived.listen((value) {
//         final decoded = utf8.decode(value, allowMalformed: true).trim();
//         if (decoded.isNotEmpty) {
//           char1Data.add(decoded);
//           char1Samples++;
//           log("first service $char1Samples");
//         }
//       }),
//     );

//     // ---- Listen CHAR2 ----
//     subs.add(
//       char2.onValueReceived.listen((value) {
//         final decoded = utf8.decode(value, allowMalformed: true).trim();
//         if (decoded.isNotEmpty) {
//           char2Data.add(decoded);
//           char2Samples++;
//           log("second service $char2Samples");
//         }
//       }),
//     );

//     log('[BLE TEST] Capturing for 60 seconds...');
//     final startTime = DateTime.now();

//     await Future.delayed(const Duration(seconds: 60));

//     final endTime = DateTime.now();
//     final double elapsedSeconds =
//         endTime.difference(startTime).inMilliseconds / 1000.0;

//     // ---- Stop notify ----
//     for (final c in [char1, char2]) {
//       try {
//         await c.setNotifyValue(false);
//       } catch (_) {}
//     }

//     // ---- Cancel subscriptions ----
//     for (final s in subs) {
//       await s.cancel();
//     }

//     // ---- SPMS calculation ----
//     final double char1Spms = char1Samples / elapsedSeconds;
//     final double char2Spms = char2Samples / elapsedSeconds;

//     // ---- Final result ----
//     log('================ BLE TEST RESULT ================');
//     log('Duration        : ${elapsedSeconds.toStringAsFixed(2)} sec');
//     log('CHAR1 UUID      : ${char1.uuid}');
//     log('CHAR1 samples   : $char1Samples');
//     log('CHAR1 SPMS      : ${char1Spms.toStringAsFixed(2)}');
//     log('-----------------------------------------------');
//     log('CHAR2 UUID      : ${char2.uuid}');
//     log('CHAR2 samples   : $char2Samples');
//     log('CHAR2 SPMS      : ${char2Spms.toStringAsFixed(2)}');
//     log('================================================');
//   }
// }
