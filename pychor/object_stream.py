from socket import *
import threading
import pickle

class ObjectStream:

    def __init__(self, sock):
        self.sock = sock
        self.writer = sock.makefile('wb')
        self.reader = sock.makefile('rb')

    # Objects are sent/received as a 4-byte big-endian integer of
    # the pickled object data length, followed by the pickled data.

    def get_obj(self):
        header = self.reader.read(4)
        if not header:
            return None
        length = int.from_bytes(header,'big')
        return pickle.loads(self.reader.read(length))

    def put_obj(self,obj):
        data = pickle.dumps(obj)
        header = len(data).to_bytes(4,'big')
        self.writer.write(header)
        self.writer.write(data)
        self.writer.flush()  # important!

    def close(self):
        if self.sock is not None:
            self.writer.close()
            self.reader.close()
            self.sock.close()
            self.sock = None
            self.writer = None
            self.reader = None

    # Support for 'with' to close everything.

    def __enter__(self):
        return self

    def __exit__(self,*args):
        self.close()

    # Support for no more references to ObjectStream

    def __del__(self):
        self.close()
