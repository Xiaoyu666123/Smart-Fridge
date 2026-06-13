/// 库存项剩余天数计算（统一用 agent_metadata.expire_at 或 expire_at）。
/// 使用 UTC 时间比较，避免本地时区与服务端不一致导致误判。
int remainDays(Map<String, dynamic> item) {
  final meta = item['agent_metadata'];
  final expireAt = (meta is Map ? meta['expire_at'] : null) ?? item['expire_at'];
  if (expireAt == null) return 1 << 30;
  final dt = DateTime.tryParse(expireAt.toString());
  if (dt == null) return 1 << 30;
  // 统一用 UTC 比较，避免时区偏差
  final expireUtc = dt.isUtc ? dt : dt.toUtc();
  return expireUtc.difference(DateTime.now().toUtc()).inHours ~/ 24;
}

bool hasExpiry(Map<String, dynamic> item) => remainDays(item) < (1 << 29);
