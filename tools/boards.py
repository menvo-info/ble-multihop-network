"""Bảng board dùng chung cho các script (khớp docs/HUONG_DAN_WSN.md, mục Vai trò)."""
import serial.tools.list_ports

BOARDS = {
    "R": "050BACC7163712E4",  # 12/11/2026: đổi Pico R <-> C
    "A": "99018494FD71AB17",
    "B": "40BEA7129EAAA081",
    "C": "17BCEBA3D9D28BEF",
}


def find_ports():
    """Trả về {tên board: COMx} cho các board đang cắm USB."""
    by_serial = {p.serial_number: p.device for p in serial.tools.list_ports.comports() if p.serial_number}
    return {name: by_serial[s] for name, s in BOARDS.items() if s in by_serial}
