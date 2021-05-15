"""audio/basic MIME type handler"""

class parse_audio_basic:

    def __init__(self, viewer, reload=None):
        viewer.send_flowing_data("(Listen to the audio!)\n")
        import audiodev
        self.device = p = audiodev.AudioDev()
        p.setoutrate(8000)
        p.setsampwidth(0)               # Special: U-LAW
        p.setnchannels(1)

    def feed(self, buf):
        self.device.writeframes(buf)

    def close(self):
        self.device.wait()
