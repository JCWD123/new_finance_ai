from datetime import datetime, timedelta


def calculate_base_time(now: datetime, type: str = None) -> tuple:
    """
    智能计算基准时间点
    Args:
        now: 当前时间
        type: 新闻类型 ReadMorning(早间必读) 或 LogicalReview(逻辑复盘)
    Returns:
        tuple: (end_time, start_time) 时间戳元组
    """
    weekday = now.weekday()  # 0=周一, 6=周日

    # 构造时间点
    today_9am = now.replace(hour=9, minute=0, second=0, microsecond=0)
    today_2pm = now.replace(hour=14, minute=0, second=0, microsecond=0)
    today_3pm = now.replace(hour=15, minute=0, second=0, microsecond=0)

    # 逻辑复盘时间段（9:00-14:00）
    if type == "LogicalReview":
        return int(today_2pm.timestamp()), int(today_9am.timestamp())

    # 早间必读时间段处理
    if type == "ReadMorning":
        if weekday == 0:  # 周一
            # 获取上周五下午3点到周一早上9点的数据
            return int(today_9am.timestamp()), int(
                (today_3pm - timedelta(days=3)).timestamp()
            )
        else:  # 周二到周日
            # 获取昨天下午3点到今天早上9点的数据
            return int(today_9am.timestamp()), int(
                (today_3pm - timedelta(days=1)).timestamp()
            )

    # 默认返回当前时间和前一天时间窗口
    return (
        int(now.replace(second=0, microsecond=0).timestamp()),
        int((now - timedelta(days=1)).timestamp()),
    )
