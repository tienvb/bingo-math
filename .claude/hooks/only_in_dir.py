#!/usr/bin/env python3
"""PreToolUse hook: chặn agent con ghi file ngoài thư mục được phép.

Dùng: python3 only_in_dir.py <thư mục tương đối so với gốc dự án>
Exit 2 = chặn, nội dung stderr được trả về cho agent.
"""
import json
import os
import sys


def main() -> int:
    if len(sys.argv) < 2:
        print("only_in_dir.py: thiếu tham số thư mục", file=sys.stderr)
        return 2

    project_dir = os.path.realpath(os.environ.get("CLAUDE_PROJECT_DIR", os.getcwd()))
    allowed = os.path.realpath(os.path.join(project_dir, sys.argv[1]))

    try:
        payload = json.load(sys.stdin)
    except json.JSONDecodeError:
        print("only_in_dir.py: không đọc được input của hook", file=sys.stderr)
        return 2

    tool_input = payload.get("tool_input") or {}
    path = tool_input.get("file_path") or tool_input.get("notebook_path")
    if not path:
        return 0

    if not os.path.isabs(path):
        path = os.path.join(payload.get("cwd") or project_dir, path)
    target = os.path.realpath(path)

    if target == allowed or target.startswith(allowed + os.sep):
        return 0

    print(
        f"Bị chặn: chỉ được ghi trong {sys.argv[1]}/, không được ghi {target}. "
        "Cần thay đổi ở nơi khác thì ghi vào báo cáo cho master.",
        file=sys.stderr,
    )
    return 2


if __name__ == "__main__":
    sys.exit(main())
