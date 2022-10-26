
# -*- coding: utf-8 -*-
# 将 iostat -xt nvme0n1 输出转化为 csv
import sys, re

# 正则表达式, 匹配 08/04/2022 04:02:14 PM
MDYHMS = re.compile(r'^[01][0-9]/[0-3][0-9]/[0-9]+ [0-9]{2}:[0-9]{2}:[0-9]{2} [AP]M$')

# 判断 line 是否是时间戳行.
# 当前支持时间戳格式: '08/04/2022 04:02:14 PM'
def is_timestmap(line):
    return MDYHMS.match(line) is not None


def main():
    ts_line = None
    parts = []

    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        if is_timestmap(line):
            print("|".join(parts))
            ts_line = line
            parts = [line]
            continue
        if line.startswith("avg-cpu:"):
            continue
        if line.startswith("Device:"):
            continue
        parts.extend(line.split())
    print("|".join(parts))
    return


if __name__ == '__main__':
    main()

