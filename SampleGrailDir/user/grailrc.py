# Grail initialization file

# Turn on remote control.  Ignore error that get's raised if some
# other Grail is being remote controlled.
import RemoteControl
RemoteControl.register_loads()
try:
    RemoteControl.start()
except RemoteControl.ClashError:
    pass
