import atexit
import threading

bl_info = {
    "name": "ArtNet Input",
    "author": "Daniel Hilpert",
    "version": (1, 0),
    "blender": (2, 80, 0),
    "location": "Properties > Scene, driver expression",
    "description": "Adds ArtNet Input Driver Functions #dmx(channel: int), "
                   "#dmxf(channel: int",
    "warning": "",
    "doc_url": "",
    "category": "System",
}

import socket
import bpy
from bpy.props import IntProperty, StringProperty

LOG_PREFIX = "ArtNetIn:"


class Receiver:
    def __init__(
            self, udp_ip='127.0.0.1', udp_port=6454, artnet_universe=0,
            channel_buffer=bytearray((0x00,) * 512)
    ):
        self.sock: socket.socket | None = None
        self.udp_ip = udp_ip
        self.udp_port = udp_port
        self.artnet_universe = artnet_universe
        self._artnet_header = self._build_artnet_header()
        self._data_header = self._build_data_header(artnet_universe)
        self._channels = channel_buffer
        self.do_receive = False
        self.status = "Inactive"

    def __enter__(self):
        self.open()
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        self.close()

    def _build_data_header(self, artnet_universe):
        data_header = bytearray(
            (
                artnet_universe & 0xFF, artnet_universe >> 8 & 0xFF,
                0x02, 0x00  # always 255
            )
        )
        return data_header

    def _build_artnet_header(self):
        header_base = bytearray(map(ord, "Art-Net"))
        header_base.append(0x00)  # null terminated string
        header_base.extend([0x00, 0x50])  # opcode 0x5000 (little endian)
        header_base.extend([0x00, 0x0e])  # protocol version 14
        frame_number = 0x00
        artnet_header = header_base + bytearray((frame_number, 0x00))
        return artnet_header

    def open(self):
        self._data_header = self._build_data_header(self.artnet_universe)
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)  # UDP
        self.sock.bind((self.udp_ip, self.udp_port))
        self.sock.settimeout(0.1)
        self.do_receive = True
        log(f"Opened ArtNet Receiver on {self.udp_ip}:{self.udp_port}")

    def receive(self):
        while self.do_receive:
            self.receive_next()

    def receive_next(self):
        self.receive_into_buffer(self._channels)

    def receive_into_buffer(self, channel_buffer):
        try:
            data, addr = self.sock.recvfrom(1024)
        except TimeoutError:
            self.status = "Timeout"
            return
        except Exception as e:
            self.status = f"Error {e}"
            return

        self.handle_data(channel_buffer, data)

    def handle_data(self, channel_buffer, data):
        header_base = data[0:12]
        expected_header_base = self._artnet_header[0:12]
        if header_base == expected_header_base:
            # frame_number = data[12:14]
            data_header = data[14:18]
            if data_header == self._data_header:
                channels = data[18:]
                self.copy_channels_to_buffer(channels, channel_buffer)
                self.status = f"Receiving {len(channels)} Channels"
            else:
                self.status = "Invalid Data"
        else:
            self.status = "Invalid Data"

    @staticmethod
    def copy_channels_to_buffer(channels, channels_out_buffer):
        received_channel_length = len(channels)
        max_acceptable_channel_length = len(channels_out_buffer)
        copy_length = min(
            max_acceptable_channel_length, received_channel_length
        )
        for i in range(copy_length):
            channels_out_buffer[i] = channels[i]

    def get_channels(self) -> bytearray:
        return self._channels

    def get_channel(self, channel) -> int:
        return self._channels[channel]

    def close(self):
        if self.sock:
            self.sock.close()
        self.status = "Inactive"
        log(f"Closed ArtNet Receiver on {self.udp_ip}:{self.udp_port}")


class MultithreadReceiver(Receiver):
    def __init__(
            self, udp_ip='127.0.0.1', udp_port=6454, artnet_universe=0,
            channel_buffer=bytearray((0x00,) * 512)
    ):
        super().__init__(udp_ip, udp_port, artnet_universe, channel_buffer)
        self._thread: threading.Thread | None = None
        self.stop_event = threading.Event()

    def receive_into_shared_buffer(self, channel_buffer):
        while self.do_receive:
            self.receive_into_buffer(channel_buffer)

    def open(self):
        if self.do_receive:
            self.close()

        super().open()
        self._thread = threading.Thread(
            target=self.receive_into_shared_buffer,
            args=(self._channels,)
        )
        self._thread.start()

    def close(self):
        self.do_receive = False
        self.stop_event.set()
        if self._thread:
            self._thread.join(3)
        super().close()


receiver = MultithreadReceiver()


class ArtNetStartOperator(bpy.types.Operator):
    bl_idname = "scene.artnet_in_start"
    bl_label = "Start Receiving ArtNet Input"

    def invoke(self, context, event):
        scene = context.scene

        if receiver.do_receive:
            receiver.close()

        receiver.udp_ip = scene.artnet_in.udp_ip
        receiver.udp_port = scene.artnet_in.udp_port
        receiver.artnet_universe = scene.artnet_in.artnet_universe

        receiver.open()

        return {'FINISHED'}


class ArtNetStopOperator(bpy.types.Operator):
    bl_idname = "scene.artnet_in_stop"
    bl_label = "Stop Receiving ArtNet Input"

    def invoke(self, context, event):
        global receiver
        if receiver.do_receive:
            receiver.close()

        return {'FINISHED'}


class ArtNetInPanel(bpy.types.Panel):
    """Creates a Panel in the scene context of the properties editor"""
    bl_label = "ArtNet Input"
    bl_idname = "SCENE_PT_layout"
    bl_space_type = 'PROPERTIES'
    bl_region_type = 'WINDOW'
    bl_context = "scene"

    def draw(self, context):
        layout = self.layout

        scene = context.scene

        # Create a simple row.
        layout.label(text=" Network Settings:")

        row = layout.row()
        row.prop(scene.artnet_in, "udp_ip")
        row.prop(scene.artnet_in, "udp_port")

        layout.label(text=" ArtNet Settings:")
        layout.prop(scene.artnet_in, "artnet_universe")

        layout.label(text=" Activation:")
        row = layout.row()
        row.operator("scene.artnet_in_start")
        row.operator("scene.artnet_in_stop")

        row = layout.row()
        row.label(text=f"Status: {receiver.status}")


class ArtNetIn(bpy.types.PropertyGroup):
    udp_ip: StringProperty(
        name="IP",
        default="127.0.0.1"
    )
    udp_port: IntProperty(
        name="Port",
        default=6454
    )
    artnet_universe: IntProperty(
        name="Universe",
        default=0
    )


def get_dmx_channel(channel: int) -> int:
    if receiver:
        channel_value = receiver.get_channel(channel)
        return channel_value
    else:
        return 0


def get_dmx_channel_float(channel: int) -> float:
    return get_dmx_channel(channel) / 255.0


@bpy.app.handlers.persistent
def register_drivers(*args):
    bpy.app.driver_namespace['dmx'] = get_dmx_channel
    bpy.app.driver_namespace['dmxf'] = get_dmx_channel_float


def register():
    bpy.utils.register_class(ArtNetIn)
    bpy.types.Scene.artnet_in = bpy.props.PointerProperty(type=ArtNetIn)

    bpy.utils.register_class(ArtNetStartOperator)
    bpy.utils.register_class(ArtNetStopOperator)
    bpy.utils.register_class(ArtNetInPanel)

    register_drivers()
    bpy.app.handlers.load_post.append(register_drivers)

    watchdog = threading.Thread(target=close_watchdog)
    watchdog.daemon = True
    watchdog.start()


def unregister():
    bpy.utils.unregister_class(ArtNetIn)

    bpy.utils.unregister_class(ArtNetStartOperator)
    bpy.utils.unregister_class(ArtNetStopOperator)
    bpy.utils.unregister_class(ArtNetInPanel)

    bpy.app.handlers.load_post.remove(register_drivers)

    close_receiver()


def close_watchdog():
    main_thread = threading.main_thread()
    main_thread.join()
    log("Main thread exited, closing ArtNet Receiver")
    close_receiver()


def close_receiver():
    log(f"Closing ArtNet Receiver")
    receiver.close()
    log("Bye!")


def log(obj):
    print(f"{LOG_PREFIX} {obj}")


if __name__ == "__main__":
    register()
