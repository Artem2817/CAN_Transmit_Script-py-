import ctypes
import time
from ctypes import Structure, c_uint, c_ubyte, c_char, c_void_p, POINTER, byref

# Константы
INVALID_DEVICE_HANDLE = c_void_p(-1).value
STATUS_OK = 1
DEVICE_TYPE_USBCANFD = 41
CHANNEL_INDEX = 0
BITRATE_250K = 250000
CANFD_STANDARD_ISO = 0

# Флаги CAN ID
IS_EXTENDED_ID = 0x80000000  # Бит 31 - признак расширенного ID (29-bit)

PREDEFINED_FRAMES = [
    {"id": 0x131, "data": (0x05, 0x05, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00)},
    {"id": 0x231, "data": (0x01, 0x01, 0x03, 0x00, 0x00, 0x00, 0x00, 0x00)},
    {"id": 0x431, "data": (0x00, 0x00, 0x00, 0x66, 0x40, 0x02, 0x00, 0x00)},
]
# Структуры данных
class ZCAN_DEVICE_INFO(Structure):
    _pack_ = 1
    _fields_ = [
        ("hw_Version", c_uint),
        ("fw_Version", c_uint),
        ("dr_Version", c_uint),
        ("in_Version", c_uint),
        ("irq_Num", c_uint),
        ("can_Num", c_uint),
        ("str_Serial_Num", c_char * 20),
        ("str_hw_Type", c_char * 40),
        ("reserved", c_uint * 4)
    ]


class ZCAN_CHANNEL_INIT_CONFIG(Structure):
    _pack_ = 1
    _fields_ = [
        ("can_type", c_uint),
        ("acc_code", c_uint),
        ("acc_mask", c_uint),
        ("reserved", c_uint),
        ("filter", c_uint),
        ("timing0", c_ubyte),
        ("timing1", c_ubyte),
        ("mode", c_uint),
        ("abit_timing", c_uint),
        ("dbit_timing", c_uint),
        ("brp", c_uint),
        ("pad", c_uint),
        ("reserved2", c_uint * 2)
    ]


class CAN_FRAME(Structure):
    _pack_ = 1
    _fields_ = [
        ("can_id", c_uint),  # ID + флаги (бит 31 - расширенный)
        ("can_dlc", c_ubyte),
        ("__pad", c_ubyte),
        ("__res0", c_ubyte),
        ("__res1", c_ubyte),
        ("data", c_ubyte * 8)
    ]


class ZCAN_Transmit_Data(Structure):
    _pack_ = 1
    _fields_ = [
        ("frame", CAN_FRAME),
        ("transmit_type", c_uint)
    ]


# Загрузка DLL
try:
    zlgcan = ctypes.windll.LoadLibrary(r"C:\Users\Admin\Documents\GIT\Sripts\CAN\ControlCANFD.dll")
except Exception as e:
    print(f"Ошибка загрузки DLL: {e}")
    exit(1)

# Настройка прототипов функций
zlgcan.ZCAN_OpenDevice.restype = c_void_p
zlgcan.ZCAN_OpenDevice.argtypes = [c_uint, c_uint, c_uint]
zlgcan.ZCAN_CloseDevice.restype = c_uint
zlgcan.ZCAN_CloseDevice.argtypes = [c_void_p]
zlgcan.ZCAN_InitCAN.restype = c_void_p
zlgcan.ZCAN_InitCAN.argtypes = [c_void_p, c_uint, POINTER(ZCAN_CHANNEL_INIT_CONFIG)]
zlgcan.ZCAN_StartCAN.restype = c_uint
zlgcan.ZCAN_StartCAN.argtypes = [c_void_p]
zlgcan.ZCAN_Transmit.restype = c_uint
zlgcan.ZCAN_Transmit.argtypes = [c_void_p, POINTER(ZCAN_Transmit_Data), c_uint]
zlgcan.ZCAN_SetAbitBaud.restype = c_uint
zlgcan.ZCAN_SetAbitBaud.argtypes = [c_void_p, c_uint, c_uint]
zlgcan.ZCAN_SetCANFDStandard.restype = c_uint
zlgcan.ZCAN_SetCANFDStandard.argtypes = [c_void_p, c_uint, c_uint]


def send_extended_can_message(num, count):
    frame_data = PREDEFINED_FRAMES[num]
    # 1. Открытие устройства
    device_handle = zlgcan.ZCAN_OpenDevice(DEVICE_TYPE_USBCANFD, 0, 0)
    if device_handle == INVALID_DEVICE_HANDLE:
        print("Ошибка открытия устройства")
        return

    # 2. Настройка стандарта CAN и скорости
    if zlgcan.ZCAN_SetCANFDStandard(device_handle, CHANNEL_INDEX, CANFD_STANDARD_ISO) != STATUS_OK:
        print("Ошибка настройки стандарта ISO CAN")
        zlgcan.ZCAN_CloseDevice(device_handle)
        return

    if zlgcan.ZCAN_SetAbitBaud(device_handle, CHANNEL_INDEX, BITRATE_250K) != STATUS_OK:
        print("Ошибка настройки скорости 250 kbps")
        zlgcan.ZCAN_CloseDevice(device_handle)
        return

    # 3. Инициализация CAN-канала
    init_config = ZCAN_CHANNEL_INIT_CONFIG()
    init_config.can_type = 1  # Режим CANFD
    init_config.acc_code = 0  # Принимать все сообщения
    init_config.acc_mask = 0xFFFFFFFF
    init_config.filter = 1  # Одиночная фильтрация
    init_config.mode = 0  # Нормальный режим

    channel_handle = zlgcan.ZCAN_InitCAN(device_handle, CHANNEL_INDEX, byref(init_config))
    if channel_handle == INVALID_DEVICE_HANDLE:
        print("Ошибка инициализации CAN-канала")
        zlgcan.ZCAN_CloseDevice(device_handle)
        return

    # 4. Запуск CAN-канала
    if zlgcan.ZCAN_StartCAN(channel_handle) != STATUS_OK:
        print("Ошибка запуска CAN-канала")
        zlgcan.ZCAN_CloseDevice(device_handle)
        return

    # 5. Подготовка и отправка сообщения с расширенным ID
    msg = ZCAN_Transmit_Data()
    extended_id = frame_data["id"]  # 29-битный ID здесь
    # Установка бита расширенного ID и самого ID
    msg.frame.can_id = extended_id | IS_EXTENDED_ID

    msg.frame.can_dlc = 8  # Длина данных (8 байт)
    msg.frame.data = frame_data["data"]
    msg.transmit_type = 0  # Нормальная передача

    print(f"Отправка расширенного CAN-сообщения: ID=0x{extended_id:08X}")
    for i in range(count):
        sent = zlgcan.ZCAN_Transmit(channel_handle, byref(msg), 1)
        if sent == 1:
            print("Сообщение успешно отправлено")
        else:
            print(f"Ошибка отправки. Отправлено сообщений: {sent}")
        time.sleep(0.5)
    # 6. Завершение работы
    zlgcan.ZCAN_CloseDevice(device_handle)


if __name__ == "__main__":
    send_extended_can_message(1, 100)