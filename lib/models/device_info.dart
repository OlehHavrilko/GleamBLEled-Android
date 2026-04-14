class DeviceInfo {
  final String name;
  final String address;
  final int? rssi;
  final String confidence;
  final String? writeUuid;

  DeviceInfo({
    required this.name,
    required this.address,
    this.rssi,
    this.confidence = 'name',
    this.writeUuid,
  });

  String get rssiBars {
    if (rssi == null) return '???';
    final r = rssi!;
    if (r >= -50) return '████';
    if (r >= -60) return '███░';
    if (r >= -70) return '██░░';
    return '█░░░';
  }

  Map<String, dynamic> toJson() => {
    'name': name,
    'address': address,
    'rssi': rssi,
    'confidence': confidence,
    'writeUuid': writeUuid,
  };

  factory DeviceInfo.fromJson(Map<String, dynamic> json) => DeviceInfo(
    name: json['name'] ?? '',
    address: json['address'] ?? '',
    rssi: json['rssi'],
    confidence: json['confidence'] ?? 'name',
    writeUuid: json['writeUuid'],
  );
}
